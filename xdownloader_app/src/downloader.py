from __future__ import annotations

import asyncio
import hashlib
import os
import re
from pathlib import Path
from typing import List, Optional

import httpx

from .config import AppConfig
from .models import DownloadContext, MediaItem, UserInfo
from .twitter_api import TwitterAPI, RateLimitError
from .csv_output import CSVWriter
from .cache import DownloadCache
from .utils import encode_url, timestamp_to_str
from .logger import log


class DownloadError(Exception):
    def __init__(self, status_code: int, message: str = ''):
        self.status_code = status_code
        super().__init__(message)


class MediaDownloader:

    def __init__(
        self,
        config: AppConfig,
        api: TwitterAPI,
        csv_writer: Optional[CSVWriter] = None,
        cache: Optional[DownloadCache] = None,
        ui_logger=None,
    ):
        self.config = config
        self.api = api
        self.csv_writer = csv_writer
        self.cache = cache
        self._ui_logger = ui_logger
        self.download_count = 0
        self.image_count = 0
        self.video_count = 0
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    def _log(self, msg):
        log.info(msg)
        if self._ui_logger:
            self._ui_logger.info(msg)

    async def _ensure_client(self):
        if self._http_client is None:
            limits = httpx.Limits(
                max_connections=max(self.config.max_concurrent * 3, 50),
                max_keepalive_connections=max(self.config.max_concurrent * 2, 20),
            )
            self._http_client = httpx.AsyncClient(
                proxy=self.config.proxy,
                verify=True,
                timeout=httpx.Timeout(3.05, read=20.0),
                limits=limits,
            )

    async def close(self):
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def _download_single(
        self,
        url: str,
        file_path: str,
        csv_info: list,
        order: int,
        save_path: str,
        semaphore: asyncio.Semaphore,
    ) -> bool:
        is_video = url.split('?')[0].lower().endswith('.mp4')

        if not is_video:
            if self.config.is_orig_format:
                url += '?format=jpg&name=orig'
            elif self.config.image_format == 'png':
                url += '?format=png&name=4096x4096'
            else:
                url += f'?format={self.config.image_format}&name=orig'

        orig_fail = 0
        max_retries = 5

        for attempt in range(max_retries):
            try:
                async with semaphore:
                    response = await self._http_client.get(encode_url(url))
                    if response.status_code == 404:
                        raise DownloadError(status_code=404, message=f"Not found: {url}")
                    content = response.content

                with open(file_path, 'wb') as f:
                    f.write(content)
                self.download_count += 1
                if is_video:
                    self.video_count += 1
                else:
                    self.image_count += 1

                if self.csv_writer:
                    csv_info[-5] = os.path.basename(file_path)
                    self.csv_writer.add_row(csv_info)

                if self.config.verbose:
                    log.info(f"Downloaded: {file_path}")

                return True

            except Exception as e:
                is_not_found = isinstance(e, DownloadError) and e.status_code == 404
                if is_video or self.config.image_format == 'png' or not is_not_found:
                    if attempt < max_retries - 1:
                        log.warning(
                            f"Download retry {attempt + 1}/{max_retries} for: {os.path.basename(file_path)}"
                        )
                    else:
                        log.error(f"Failed after {max_retries} retries: {os.path.basename(file_path)}")
                        return False
                elif self.config.is_orig_format and orig_fail == 0:
                    orig_fail = 1
                    url = url.replace('format=jpg', 'format=png')
                    file_path = re.sub(r'jpg$', 'png', file_path)
                elif orig_fail == 1:
                    orig_fail = 2
                    url = url.replace('name=orig', 'name=4096x4096')
                else:
                    log.error(f"Download failed (404): {os.path.basename(file_path)}")
                    return False

        return False

    async def _download_batch(
        self,
        items: List[MediaItem],
        user_info: UserInfo,
    ):
        csv_existing_urls = self.csv_writer.existing_media_urls() if self.csv_writer else set()

        tasks = []
        skipped_cache = 0
        skipped_file = 0
        skipped_csv = 0
        for order, item in enumerate(items):
            ext = 'mp4' if item.url.split('?')[0].lower().endswith('.mp4') else self.config.img_format
            url_hash = hashlib.md5(item.url.encode()).hexdigest()[:8]
            filename = f'{item.prefix}_{url_hash}.{ext}'
            file_path = os.path.join(user_info.save_path, filename)

            if os.path.exists(file_path):
                self._log(f"  SKIP file exists: {filename}")
                skipped_file += 1
                if self.cache:
                    self.cache.add(item.url)
                continue

            if item.url in csv_existing_urls:
                self._log(f"  SKIP csv record: {filename}")
                skipped_csv += 1
                if self.cache:
                    self.cache.add(item.url)
                continue

            if self.cache and not self.cache.is_new(item.url):
                self._log(f"  STALE cache: {item.url[:80]}")
                self.cache.discard(item.url)
                self.cache.add(item.url)

            task = self._download_single(
                item.url,
                file_path,
                item.csv_info,
                order,
                user_info.save_path,
                self._semaphore,
            )
            tasks.append(task)

        if skipped_cache or skipped_file or skipped_csv:
            self._log(f"  {len(items)} items: {skipped_cache} cache skip, {skipped_file} file skip, {skipped_csv} csv skip, {len(tasks)} download")

        if tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=300)
            except asyncio.TimeoutError:
                self._log(f"  TIMEOUT: batch download exceeded 300s, continuing with completed files")
            except asyncio.CancelledError:
                self._log(f"  CANCELLED: batch download interrupted")

        if self.cache:
            self.cache.save()
        user_info.count += len(items)

    async def run(self, user_info: UserInfo, ctx: DownloadContext):
        self._log(f"downloader.run() START for @{user_info.screen_name}")
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        try:
            await self._ensure_client()

            page = 0
            max_pages = 500
            while page < max_pages:
                page += 1
                try:
                    items = await self.api.fetch_timeline_page(user_info, ctx)
                except RateLimitError:
                    log.error(f"API rate limit exceeded for {user_info.screen_name}")
                    self._log(f"RateLimitError for @{user_info.screen_name}")
                    items = None
                except Exception as e:
                    self._log(f"Page {page}: fetch error [{type(e).__name__}] for @{user_info.screen_name}: {e}")
                    items = None

                if items is None:
                    self._log(f"Page {page}: items=None (pagination END) for @{user_info.screen_name}")
                    break
                if not items:
                    self._log(f"Page {page}: 0 items (empty) for @{user_info.screen_name}")
                    await asyncio.sleep(2)
                    continue

                self._log(f"Page {page}: {len(items)} media items for @{user_info.screen_name}")

                if self.config.async_enabled:
                    await self._download_batch(items, user_info)
                else:
                    for order, item in enumerate(items):
                        ext = 'mp4' if item.url.split('?')[0].lower().endswith('.mp4') else self.config.img_format
                        url_hash = hashlib.md5(item.url.encode()).hexdigest()[:8]
                        filename = f'{item.prefix}_{url_hash}.{ext}'
                        file_path = os.path.join(user_info.save_path, filename)
                        if os.path.exists(file_path):
                            self._log(f"  SKIP file exists: {filename}")
                            if self.cache:
                                self.cache.add(item.url)
                            continue
                        if self.cache and not self.cache.is_new(item.url):
                            self._log(f"  STALE cache: {item.url[:80]}")
                            self.cache.discard(item.url)
                            self.cache.add(item.url)
                        await self._download_single(
                            item.url,
                            file_path,
                            item.csv_info,
                            order,
                            user_info.save_path,
                            self._semaphore,
                        )
                    if self.cache:
                        self.cache.save()
                    user_info.count += len(items)

                self._log(f"Processed {user_info.count} media items for @{user_info.screen_name}")
                if page >= max_pages:
                    self._log(f"WARNING: hit max pages ({max_pages}) for @{user_info.screen_name}, data may be incomplete")
        finally:
            await self.close()
