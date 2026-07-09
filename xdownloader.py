"""Obvious entry point for launching xDownloader.

Double-click this file on systems that associate `.py` files with Python,
or run `python xdownloader.py` from a terminal.
"""

import sys

from xdownloader_app.server import main


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        from xdownloader_app.server import app, ensure_config_file

        ensure_config_file()
        response = app.test_client().get("/")
        raise SystemExit(0 if response.status_code == 200 and response.data else 1)
    main()
