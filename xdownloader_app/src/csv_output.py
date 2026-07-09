from __future__ import annotations

import csv
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List


class CSVWriter:

    def __init__(
        self,
        save_path: str,
        user_name: str,
        screen_name: str,
        tweet_range: str
    ):
        self.save_path = save_path
        self.user_name = user_name
        self.screen_name = screen_name
        self.tweet_range = tweet_range
        self.file_path = os.path.join(save_path, f'{screen_name}.csv')
        self._data: List[list] = []
        self._file_created = os.path.exists(self.file_path)
        self._flushed_count = 0

        if self._file_created:
            self._load_existing()

    def _load_existing(self):
        try:
            with open(self.file_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                existing = list(reader)
                self._data = existing[4:] if len(existing) > 4 else []
        except (OSError, UnicodeDecodeError):
            self._data = []

    @staticmethod
    def _stamp_to_str(msecs: int) -> str:
        time_array = time.localtime(msecs / 1000)
        return time.strftime("%Y-%m-%d %H:%M", time_array)

    def existing_media_urls(self) -> set:
        result = set()
        for row in self._data:
            if len(row) >= 7:
                local_file = row[6]
                media_url = row[5]
                if local_file and media_url:
                    if os.path.isfile(os.path.join(self.save_path, local_file)):
                        result.add(media_url)
        return result

    def existing_tweet_urls(self) -> set:
        result = set()
        for row in self._data:
            if len(row) >= 4:
                url = row[3]
                if url:
                    result.add(url)
        return result

    def add_row(self, info: list):
        info[0] = self._stamp_to_str(info[0])
        self._data.append(info)
        self._maybe_flush()

    def add_text_row(self, info: list):
        while len(info) < 11:
            info.insert(4, '')
        self._data.append(info)
        self._maybe_flush()

    def _maybe_flush(self):
        if len(self._data) - self._flushed_count >= 50:
            self._flush_to_disk()

    def _flush_to_disk(self):
        if not self._data:
            return
        os.makedirs(self.save_path, exist_ok=True)
        deduped_media = {}
        text_rows = []
        seen_tweet_urls = set()
        for row in self._data:
            if len(row) < 4:
                continue
            tweet_url = row[3]
            media_url = row[5] if len(row) > 5 else ''
            if media_url and len(row) >= 7:
                local_file = row[6]
                exists = os.path.isfile(os.path.join(self.save_path, local_file)) if local_file else False
                is_hash = bool(re.match(r'.*_[0-9a-fA-F]{8}\.[a-zA-Z]+$', local_file)) if local_file else False
                score = (exists, is_hash)
                if media_url not in deduped_media or score > deduped_media[media_url][0]:
                    deduped_media[media_url] = (score, row)
            else:
                if tweet_url and tweet_url not in seen_tweet_urls:
                    seen_tweet_urls.add(tweet_url)
                    text_rows.append(row)
        merged = [v[1] for v in deduped_media.values()] + text_rows
        tmp_path = self.file_path + '.tmp'
        try:
            with open(tmp_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([self.user_name, self.screen_name])
                writer.writerow([f'Tweet Range : {self.tweet_range}'])
                writer.writerow([f'Save Path : {self.save_path}'])
                writer.writerow([
                    'Tweet Date', 'Display Name', 'User Name',
                    'Tweet URL', 'Media Type', 'Media URL',
                    'Saved Filename', 'Tweet Content',
                    'Favorite Count', 'Retweet Count', 'Reply Count'
                ])
                writer.writerows(merged)
            os.replace(tmp_path, self.file_path)
            self._flushed_count = len(self._data)
        except (OSError, UnicodeEncodeError) as e:
            from .logger import log
            log.error(f"Failed to write CSV {self.file_path}: {e}")

    def close(self):
        self._flushed_count = 0
        self._flush_to_disk()
