from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class Logger:
    _instance: Optional[Logger] = None

    def __init__(
        self,
        name: str = "twitter_downloader",
        log_file: Optional[str] = None,
        verbose: bool = False
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
        self.logger.handlers.clear()

        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    @classmethod
    def get(cls) -> logging.Logger:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance.logger

    @classmethod
    def setup(
        cls,
        log_file: Optional[str] = None,
        verbose: bool = False
    ) -> logging.Logger:
        if cls._instance is None:
            cls._instance = cls(log_file=log_file, verbose=verbose)
        else:
            cls._instance.logger.setLevel(logging.DEBUG if verbose else logging.INFO)
            for h in cls._instance.logger.handlers:
                if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
                    h.setLevel(logging.DEBUG if verbose else logging.INFO)
            if log_file:
                Path(log_file).parent.mkdir(parents=True, exist_ok=True)
                fh = logging.FileHandler(log_file, encoding="utf-8")
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(cls._instance.logger.handlers[0].formatter if cls._instance.logger.handlers else logging.Formatter(
                    "[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
                cls._instance.logger.addHandler(fh)
        return cls._instance.logger


log = Logger.get()
