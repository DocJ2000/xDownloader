from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .utils import str_to_timestamp


APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.path.dirname(sys.executable)) if getattr(sys, "frozen", False) else APP_DIR.parent


@dataclass
class AppConfig:
    save_path: str
    user_list: List[str]
    cookie: str
    bearer_token: str
    proxy: Optional[str]
    has_retweet: bool
    has_highlights: bool
    has_likes: bool
    has_video: bool
    time_range: Tuple[int, int]
    image_format: str
    max_concurrent: int
    async_enabled: bool
    enable_cache: bool
    auto_sync: bool
    verbose: bool
    log_file: str
    max_user_retries: int
    retry_delay: int
    tag_search_tag: str
    tag_search_filter: str
    tag_search_count: int
    tag_search_media_latest: bool
    tag_search_text_mode: bool
    text_user_list: List[str]
    text_max_tweets: int
    text_request_delay: float
    text_max_retries: int

    list_sync_enabled: bool = False
    list_sync_list_id: str = ""
    list_sync_owner: str = ""
    list_sync_slug: str = ""

    time_range_str: str = ""

    @property
    def start_time_stamp(self) -> int:
        return self.time_range[0]

    @property
    def end_time_stamp(self) -> int:
        return self.time_range[1]

    @property
    def is_orig_format(self) -> bool:
        return self.image_format == 'orig'

    @property
    def img_format(self) -> str:
        return 'jpg' if self.image_format == 'orig' else self.image_format


def load_config(config_path: str = "config.json") -> AppConfig:
    if not os.path.isabs(config_path):
        config_path = str(PROJECT_ROOT / config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        raw: Dict[str, Any] = json.load(f)

    save_path = raw.get('save_path', os.getcwd())
    if not save_path.endswith(os.sep):
        save_path += os.sep

    time_range_str = raw.get('time_range', '2015-01-01:2030-01-01')
    start_str, end_str = time_range_str.split(':')
    start_ts = str_to_timestamp(start_str)
    end_ts = str_to_timestamp(end_str)

    mode = raw.get('mode', {})
    has_retweet = mode.get('has_retweet', False)
    has_highlights = mode.get('has_highlights', False)
    has_likes = mode.get('has_likes', False)

    if has_highlights:
        has_retweet = False
    if has_likes:
        has_retweet = True
        has_highlights = False
        import sys
        print("[config] has_likes=true → forcing has_retweet=true, has_highlights=false", file=sys.stderr)

    download_cfg = raw.get('download', {})
    logging_cfg = raw.get('logging', {})
    retry_cfg = raw.get('retry', {})
    tag_cfg = raw.get('tag_search', {})
    text_cfg = raw.get('text_download', {})
    list_sync_cfg = raw.get('list_sync', {})

    return AppConfig(
        save_path=save_path,
        user_list=raw.get('user_list', []),
        cookie=raw.get('cookie', ''),
        bearer_token=raw.get('bearer_token', ''),
        proxy=raw.get('proxy') or None,
        has_retweet=has_retweet,
        has_highlights=has_highlights,
        has_likes=has_likes,
        has_video=mode.get('has_video', True),
        time_range=(start_ts, end_ts),
        time_range_str=time_range_str,
        image_format=raw.get('image_format', 'orig'),
        max_concurrent=download_cfg.get('max_concurrent', 16),
        async_enabled=download_cfg.get('async_enabled', True),
        enable_cache=download_cfg.get('enable_cache', True),
        auto_sync=download_cfg.get('auto_sync', False),
        verbose=logging_cfg.get('verbose', False),
        log_file=logging_cfg.get('log_file', ''),
        max_user_retries=retry_cfg.get('max_user_retries', 3),
        retry_delay=retry_cfg.get('delay_seconds', 10),
        tag_search_tag=tag_cfg.get('tag', ''),
        tag_search_filter=tag_cfg.get('filter', ''),
        tag_search_count=tag_cfg.get('download_count', 100),
        tag_search_media_latest=tag_cfg.get('media_latest', False),
        tag_search_text_mode=tag_cfg.get('text_mode', False),
        text_user_list=text_cfg.get('user_list', []),
        text_max_tweets=text_cfg.get('max_tweets', 500),
        text_request_delay=text_cfg.get('request_delay', 2),
        text_max_retries=text_cfg.get('max_retries', 3),
        list_sync_enabled=list_sync_cfg.get('enabled', False),
        list_sync_list_id=list_sync_cfg.get('list_id', ''),
        list_sync_owner=list_sync_cfg.get('list_owner', ''),
        list_sync_slug=list_sync_cfg.get('list_slug', ''),
    )


def save_user_list(config_path: str, user_list: List[str]) -> None:
    if not os.path.isabs(config_path):
        config_path = str(PROJECT_ROOT / config_path)

    with open(config_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    raw['user_list'] = user_list

    tmp_path = config_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(raw, f, indent=4, ensure_ascii=False)
        f.write('\n')
    os.replace(tmp_path, config_path)
