import threading
import time
import sys
import os
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

os.environ['WEBVIEW_GUI'] = 'edgechromium'

from src.logger import Logger
from src.config import load_config

config = load_config('config.json')
Logger.setup(log_file=config.log_file or None, verbose=config.verbose)

from server import create_app, PORT

def start_server():
    create_app().run(host='127.0.0.1', port=PORT, debug=False, use_reloader=False)

t = threading.Thread(target=start_server, daemon=True)
t.start()
time.sleep(1)

url = f'http://127.0.0.1:{PORT}'

try:
    import webview
    webview.create_window('X-Download', url, width=1280, height=800, min_size=(900, 600))
    webview.start()
except Exception as e:
    print(f'Webview error: {e}, falling back to browser')
    webbrowser.open(url)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
