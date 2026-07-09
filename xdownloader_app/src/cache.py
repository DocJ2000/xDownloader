from __future__ import annotations

import json
import os
from typing import Set

from .logger import log


class DownloadCache:

    def __init__(self, save_path: str):
        self.cache_path = os.path.join(save_path, "cache_data.log")
        self._data: Set[str] = set()
        self._load()

    def _load(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    self._data = set(json.load(f))
                log.info(f"Cache loaded: {len(self._data)} entries from {self.cache_path}")
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
                log.warning(f"Cache load failed: {e}")
                self._data = set()
        else:
            log.info(f"Cache file not found, starting fresh")

    def save(self):
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(list(self._data), f)
        except OSError:
            pass

    def is_new(self, url: str) -> bool:
        if url in self._data:
            return False
        self._data.add(url)
        return True

    def add(self, url: str):
        self._data.add(url)

    def discard(self, url: str):
        self._data.discard(url)

    def __len__(self) -> int:
        return len(self._data)
