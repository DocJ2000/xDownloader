from __future__ import annotations

import re
import time
import calendar
from datetime import datetime
from urllib.parse import quote
from typing import Optional


def parse_twitter_created_at(created_at: str) -> int:
    try:
        dt = datetime.strptime(created_at, '%a %b %d %H:%M:%S %z %Y')
        return int(calendar.timegm(dt.utctimetuple()) * 1000)
    except (ValueError, OverflowError):
        return int(time.time() * 1000)


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)


def sanitize_tag_name(string: str) -> str:
    return re.sub(
        r'[^#\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a\u3040-\u31FF\.]',
        '', string
    )


def timestamp_to_str(msecs_stamp: int) -> str:
    timestamp_sec = msecs_stamp / 1000
    if timestamp_sec < 0:
        timestamp_sec = time.time()
    try:
        time_array = time.localtime(timestamp_sec)
    except OSError:
        time_array = time.localtime(time.time())
    return time.strftime("%Y-%m-%d %H-%M", time_array)


def timestamp_to_readable(msecs_stamp: int) -> str:
    timestamp_sec = msecs_stamp / 1000
    if timestamp_sec < 0:
        timestamp_sec = time.time()
    try:
        time_array = time.localtime(timestamp_sec)
    except OSError:
        time_array = time.localtime(time.time())
    return time.strftime("%Y-%m-%d %H:%M", time_array)


def str_to_timestamp(time_str: str) -> int:
    datetime_obj = datetime.strptime(time_str, "%Y-%m-%d")
    msecs_stamp = int(
        calendar.timegm(datetime_obj.timetuple()) * 1000.0
        + datetime_obj.microsecond / 1000.0
    )
    return msecs_stamp


def time_in_range(now: int, start: int, end: int) -> tuple[bool, bool]:
    start_down = start <= now <= end
    start_label = now >= start
    return start_down, start_label


def encode_url(url: str) -> str:
    return url.replace('{', '%7B').replace('}', '%7D').replace('|', '%7C')


def encode_query(value: str) -> str:
    return quote(value, safe='')


def extract_csrf_token(cookie: str) -> Optional[str]:
    match = re.search(r'ct0=(.*?);', cookie)
    return match.group(1) if match else None


def md5_short(text: str, length: int = 4) -> str:
    import hashlib
    return hashlib.md5(text.encode('utf-8')).hexdigest()[:length]
