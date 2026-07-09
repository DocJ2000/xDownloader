from __future__ import annotations

import httpx
from typing import Dict, Optional

from .config import AppConfig
from .utils import extract_csrf_token


_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/131.0.0.0 Safari/537.36'
)


def _build_headers(config: AppConfig, referer: str) -> Dict[str, str]:
    headers = {
        'user-agent': _USER_AGENT,
        'authorization': f'Bearer {config.bearer_token or ""}',
        'referer': referer,
    }

    if config.cookie:
        headers['cookie'] = config.cookie
        csrf = extract_csrf_token(config.cookie)
        if csrf:
            headers['x-csrf-token'] = csrf

    return headers


def create_http_client(
    config: AppConfig,
    referer: str = "https://twitter.com/",
    timeout: float = 10.0
) -> httpx.Client:
    return httpx.Client(
        headers=_build_headers(config, referer),
        proxy=config.proxy,
        timeout=httpx.Timeout(timeout, connect=10.0),
        follow_redirects=True,
        verify=True,
    )


def create_async_client(
    config: AppConfig,
    referer: str = "https://twitter.com/",
    timeout: float = 15.0
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=_build_headers(config, referer),
        proxy=config.proxy,
        timeout=httpx.Timeout(timeout, connect=10.0),
        follow_redirects=True,
        verify=True,
    )
