from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserInfo:
    screen_name: str
    rest_id: Optional[str] = None
    name: Optional[str] = None
    statuses_count: Optional[int] = None
    media_count: Optional[int] = None
    save_path: str = ""
    cursor: str = ""
    count: int = 0


@dataclass
class MediaItem:
    url: str
    prefix: str
    csv_info: list = field(default_factory=list)


@dataclass
class TweetData:
    timestamp: int
    display_name: str
    screen_name: str
    tweet_url: str
    content: str
    favorite_count: int = 0
    retweet_count: int = 0
    reply_count: int = 0


@dataclass
class DownloadContext:
    user: UserInfo
    request_count: int = 0
    download_count: int = 0
    start_label: bool = True
    first_page: bool = True
