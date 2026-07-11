import json
import os
import re
import csv
import shutil
import subprocess
import threading
import time
import sys
import urllib.error
import urllib.parse
import urllib.request
from io import StringIO

from flask import Flask, jsonify, request, send_file, Response

APP_DIR = os.path.dirname(os.path.abspath(__file__))
IS_FROZEN = getattr(sys, 'frozen', False)
PROJECT_ROOT = os.path.dirname(sys.executable) if IS_FROZEN else os.path.dirname(APP_DIR)
ASSET_ROOT = os.path.join(getattr(sys, '_MEIPASS', APP_DIR), 'xdownloader_app') if IS_FROZEN else APP_DIR
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config.json')
BUNDLED_CONFIG_EXAMPLE = os.path.join(getattr(sys, '_MEIPASS', PROJECT_ROOT), 'config.example.json')
DOWNLOAD_ROOT = os.path.join(PROJECT_ROOT, 'downloads')
PORT = 8765
CURRENT_CONFIG_VERSION = 3
try:
    from ._version import VERSION as BUNDLED_APP_VERSION
except Exception:
    BUNDLED_APP_VERSION = "v0.3.1"
APP_VERSION = os.environ.get("XDOWNLOADER_VERSION", BUNDLED_APP_VERSION)
GITHUB_RELEASES_API = "https://api.github.com/repos/DocJ2000/xDownloader/releases/latest"
GITHUB_RELEASES_LATEST_URL = "https://github.com/DocJ2000/xDownloader/releases/latest"

_BASE_DIR = ASSET_ROOT

app = Flask(__name__, static_folder=None)

@app.after_request
def _no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

download_state = {
    "running": False,
    "paused": False,
    "terminated": False,
    "failed": False,
    "auto_shutdown": False,
    "shutdown_scheduled": False,
    "history_recorded": False,
    "state": "idle",
    "logs": [],
    "current": 0,
    "total": 0,
    "stats": None,
}


def schedule_system_shutdown(delay_seconds=60):
    if os.name == 'nt':
        subprocess.Popen(['shutdown', '/s', '/t', str(int(delay_seconds))])
    else:
        subprocess.Popen(['shutdown', '-h', f'+{max(1, int(delay_seconds // 60))}'])


def finalize_download_state():
    global download_state
    download_state['running'] = False
    if download_state.get('terminated'):
        download_state['state'] = 'terminated'
    elif download_state.get('paused'):
        download_state['state'] = 'paused'
    elif download_state.get('failed'):
        download_state['state'] = 'failed'
    else:
        download_state['state'] = 'complete'
        if download_state.get('stats') and not download_state.get('history_recorded'):
            record_download_history(
                download_state.get('stats') or {},
                download_state.get('requested_users') or [],
                download_state.get('storage_before', 0),
                download_state.get('storage_after', download_state.get('storage_before', 0)),
                started_at=download_state.get('started_at'),
                finished_at=time.time(),
            )
            download_state['history_recorded'] = True
        if download_state.get('auto_shutdown') and not download_state.get('shutdown_scheduled'):
            schedule_system_shutdown()
            download_state['shutdown_scheduled'] = True


def download_progress_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download_progress.json')


def download_history_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download_history.json')


def directory_size_bytes(path):
    total = 0
    if not path or not os.path.isdir(path):
        return 0
    for current_root, _, filenames in os.walk(path):
        for filename in filenames:
            full_path = os.path.join(current_root, filename)
            try:
                total += os.path.getsize(full_path)
            except OSError:
                continue
    return total


def load_download_history():
    path = download_history_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        data = data.get('items', [])
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)][-3:]


def save_download_history(items):
    path = download_history_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(items[-3:], f, ensure_ascii=False, indent=2)


def format_duration(seconds):
    try:
        seconds = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        seconds = 0
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f'{hours}h {minutes}m {seconds}s'
    if minutes:
        return f'{minutes}m {seconds}s'
    return f'{seconds}s'


def record_download_history(
    stats,
    requested_users=None,
    storage_before=0,
    storage_after=0,
    started_at=None,
    finished_at=None,
):
    stats = stats or {}
    finished_at = time.time() if finished_at is None else finished_at
    started_at = finished_at if started_at is None else started_at
    duration_seconds = max(0, int(finished_at - started_at))
    new_media = int(stats.get('images') or 0) + int(stats.get('videos') or 0)
    new_tweets = int(stats.get('text_tweets') or 0)
    new_bytes = max(0, int(storage_after or 0) - int(storage_before or 0))
    entry = {
        'finished_at': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(finished_at)),
        'duration_seconds': duration_seconds,
        'duration': format_duration(duration_seconds),
        'users': int(stats.get('users') or 0),
        'requested_users': len(requested_users or []),
        'new_media': new_media,
        'new_tweets': new_tweets,
        'new_bytes': new_bytes,
        'new_size': _format_bytes(new_bytes),
    }
    history = load_download_history()
    history.append(entry)
    save_download_history(history)
    return entry


def get_download_root(config_data=None):
    if config_data is None:
        config_data = load_config_data()
    save_path = (config_data or {}).get('save_path') or DOWNLOAD_ROOT
    return save_path.rstrip('\\/')


def _is_hidden_value(value):
    return isinstance(value, str) and '[hidden]' in value


def build_config_status(config_data):
    config_data = config_data or {}
    missing = []
    warnings = []

    if not config_data.get('cookie') or _is_hidden_value(config_data.get('cookie')):
        missing.append('cookie')
    if not config_data.get('bearer_token') or _is_hidden_value(config_data.get('bearer_token')):
        missing.append('bearer_token')
    if not config_data.get('save_path'):
        missing.append('save_path')
    if not config_data.get('user_list'):
        missing.append('user_list')

    proxy = (config_data.get('proxy') or '').strip()
    if proxy and not re.match(r'^(https?|socks5h?)://', proxy):
        warnings.append('proxy')

    max_concurrent = (config_data.get('download') or {}).get('max_concurrent')
    if not isinstance(max_concurrent, int) or max_concurrent < 1 or max_concurrent > 32:
        warnings.append('download.max_concurrent')

    save_path = config_data.get('save_path') or ''
    save_path_exists = bool(save_path and os.path.isdir(save_path))
    if save_path and not save_path_exists:
        warnings.append('save_path.exists')

    return {
        'ready': len(missing) == 0,
        'missing': missing,
        'warnings': warnings,
        'save_path_exists': save_path_exists,
        'user_count': len(config_data.get('user_list') or []),
    }


def _count_csv_items(csv_path):
    media_count = 0
    tweet_count = 0
    if not os.path.isfile(csv_path):
        return media_count, tweet_count
    try:
        with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i < 4:
                    continue
                has_media = len(row) >= 7 and row[5] and row[6]
                has_content = len(row) >= 8 and row[7]
                if has_media:
                    media_count += 1
                elif has_content:
                    tweet_count += 1
    except Exception:
        pass
    return media_count, tweet_count


def get_user_folders():
    users = []
    download_root = get_download_root()
    if not os.path.isdir(download_root):
        return users
    for folder in os.listdir(download_root):
        folder_path = os.path.join(download_root, folder)
        if not os.path.isdir(folder_path) or '@' not in folder:
            continue
        parts = folder.rsplit('@', 1)
        display_name = parts[0]
        screen_name = parts[1]
        csv_path = os.path.join(folder_path, f'{screen_name}.csv')
        media_count, tweet_count = _count_csv_items(csv_path)
        users.append({
            'display_name': display_name,
            'screen_name': screen_name,
            'folder': folder,
            'media_count': media_count,
            'tweet_count': tweet_count,
        })
    users.sort(key=lambda u: u['display_name'].lower())
    return users


def parse_media_csv(filepath):
    items = []
    if not os.path.isfile(filepath):
        return items
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception:
        return items
    reader = csv.reader(StringIO(content))
    for row in reader:
        if not row or len(row) < 8:
            continue
        try:
            item = {
                'time': row[0].strip(),
                'display_name': row[1].strip(),
                'username': row[2].strip(),
                'url': row[3].strip(),
                'media_type': row[4].strip() if len(row) > 4 else '',
                'media_url': row[5].strip() if len(row) > 5 else '',
                'local_file': row[6].strip() if len(row) > 6 else '',
                'content': row[7].strip() if len(row) > 7 else '',
                'likes': int(row[8]) if len(row) > 8 and row[8].strip().isdigit() else 0,
                'retweets': int(row[9]) if len(row) > 9 and row[9].strip().isdigit() else 0,
                'replies': int(row[10]) if len(row) > 10 and row[10].strip().isdigit() else 0,
                'source': 'media',
            }
            items.append(item)
        except Exception:
            continue
    return items


def parse_tweets_csv(filepath):
    items = []
    if not os.path.isfile(filepath):
        return items
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception:
        return items
    reader = csv.reader(StringIO(content))
    rows = list(reader)
    if len(rows) < 7:
        return items
    for row in rows[6:]:
        if not row or len(row) < 6:
            continue
        try:
            item = {
                'time': row[0].strip(),
                'display_name': row[1].strip(),
                'username': row[2].strip(),
                'url': row[3].strip(),
                'content': row[4].strip() if len(row) > 4 else '',
                'likes': int(row[5]) if len(row) > 5 and row[5].strip().isdigit() else 0,
                'retweets': int(row[6]) if len(row) > 6 and row[6].strip().isdigit() else 0,
                'replies': int(row[7]) if len(row) > 7 and row[7].strip().isdigit() else 0,
                'media_type': '',
                'media_url': '',
                'local_file': '',
                'source': 'tweet',
            }
            items.append(item)
        except Exception:
            continue
    return items


def extract_status_id(url):
    m = re.search(r'/status/(\d+)', url)
    return m.group(1) if m else None


def get_user_tweets(screen_name):
    found_path = None
    download_root = get_download_root()
    if os.path.isdir(os.path.join(download_root, screen_name)):
        found_path = os.path.join(download_root, screen_name)
    else:
        if not os.path.isdir(download_root):
            return []
        for folder in os.listdir(download_root):
            if folder.endswith('@' + screen_name):
                found_path = os.path.join(download_root, folder)
                break
    if not found_path:
        return []

    folder = os.path.basename(found_path)
    media_csv = os.path.join(found_path, f'{screen_name}.csv')

    all_items = parse_media_csv(media_csv)

    media_by_status = {}
    tweets_by_status = {}
    for item in all_items:
        sid = extract_status_id(item['url'])
        if not sid:
            continue
        if item.get('media_type') and item.get('local_file'):
            media_by_status.setdefault(sid, []).append(item)
        if sid not in tweets_by_status:
            tweets_by_status[sid] = item

    all_status_ids = set(media_by_status.keys()) | set(tweets_by_status.keys())

    entries = []
    for sid in all_status_ids:
        medias = media_by_status.get(sid, [])
        tweet = tweets_by_status.get(sid)
        base = tweet if tweet else (medias[0] if medias else None)
        if not base:
            continue
        content = base.get('content', '')
        display_name = base.get('display_name', '')
        username = base.get('username', '')
        if not content:
            for m in medias:
                c = m.get('content', '')
                if c:
                    content = c
                    break
            if not content and tweet:
                content = tweet.get('content', '')
        if not display_name or display_name == '':
            for m in medias:
                dn = m.get('display_name', '')
                if dn and dn != '':
                    display_name = dn
                    break
            if (not display_name or display_name == '') and tweet:
                display_name = tweet.get('display_name', '')
        if not username or username == '':
            for m in medias:
                un = m.get('username', '')
                if un and un != '':
                    username = un
                    break
            if (not username or username == '') and tweet:
                username = tweet.get('username', '')
        entry = {
            'time': base['time'],
            'display_name': display_name,
            'username': username,
            'url': f"https://x.com/{screen_name}/status/{sid}",
            'content': content,
            'likes': base['likes'],
            'retweets': base['retweets'],
            'replies': base['replies'],
            'media_items': [],
            'folder': folder,
        }
        seen_files = set()
        for m in medias:
            lf = m.get('local_file', '')
            if lf and lf not in seen_files:
                entry['media_items'].append({
                    'media_type': m['media_type'],
                    'local_file': lf,
                    'media_path': f'/media/{folder}/{lf}',
                })
                seen_files.add(lf)
        entries.append(entry)

    entries.sort(key=lambda x: x['time'], reverse=True)
    return entries


def _build_tweet_entries_from_folder(folder_path, folder, screen_name):
    media_csv = os.path.join(folder_path, f'{screen_name}.csv')
    all_items = parse_media_csv(media_csv)

    media_by_status = {}
    tweets_by_status = {}
    for item in all_items:
        sid = extract_status_id(item['url'])
        if not sid:
            continue
        if item.get('media_type') and item.get('local_file'):
            media_by_status.setdefault(sid, []).append(item)
        if sid not in tweets_by_status:
            tweets_by_status[sid] = item

    entries = []
    all_status_ids = set(media_by_status.keys()) | set(tweets_by_status.keys())
    for sid in all_status_ids:
        medias = media_by_status.get(sid, [])
        tweet = tweets_by_status.get(sid)
        base = tweet if tweet else (medias[0] if medias else None)
        if not base:
            continue
        entry = {
            'time': base.get('time', ''),
            'display_name': base.get('display_name', ''),
            'username': base.get('username', screen_name),
            'url': f"https://x.com/{screen_name}/status/{sid}",
            'content': base.get('content', ''),
            'likes': base.get('likes', 0),
            'retweets': base.get('retweets', 0),
            'replies': base.get('replies', 0),
            'folder': folder,
            'media_items': [],
        }
        seen_files = set()
        for media in medias:
            local_file = media.get('local_file', '')
            if local_file and local_file not in seen_files:
                entry['media_items'].append({
                    'media_type': media.get('media_type', ''),
                    'local_file': local_file,
                    'media_path': f'/media/{folder}/{local_file}',
                })
                seen_files.add(local_file)
        entries.append(entry)
    return entries


def _entry_matches_media_filter(entry, media_filter):
    media_filter = (media_filter or 'all').lower()
    media_items = entry.get('media_items') or []
    if media_filter in ('', 'all', 'any'):
        return True
    if media_filter == 'text':
        return not media_items
    if media_filter == 'media':
        return bool(media_items)
    if media_filter == 'image':
        return any(not (m.get('local_file', '').lower().endswith(('.mp4', '.webm')) or 'video' in m.get('media_type', '').lower()) for m in media_items)
    if media_filter == 'video':
        return any(m.get('local_file', '').lower().endswith(('.mp4', '.webm')) or 'video' in m.get('media_type', '').lower() for m in media_items)
    return True


MEDIA_LIBRARY_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.mp4', '.webm'}
_MEDIA_LIBRARY_CACHE = {}


def _is_video_media(local_file='', media_type=''):
    return str(local_file or '').lower().endswith(('.mp4', '.webm')) or 'video' in str(media_type or '').lower()


def _media_type_from_filename(filename):
    return 'Video' if _is_video_media(filename, '') else 'Image'


def _media_item_matches_filter(item, requested):
    requested = (requested or 'all').lower()
    is_video_media = _is_video_media(item.get('local_file', ''), item.get('media_type', ''))
    if requested == 'image' and is_video_media:
        return False
    if requested == 'video' and not is_video_media:
        return False
    return True


def _media_item_matches_query(item, query):
    query = (query or '').strip().lower()
    if not query:
        return True
    haystack = ' '.join([
        item.get('content', ''),
        item.get('display_name', ''),
        item.get('username', ''),
        item.get('folder', ''),
        item.get('local_file', ''),
    ]).lower()
    return query in haystack


def build_timeline_response(download_root, page=1, per_page=30, query='', media_filter='all'):
    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(1, min(100, int(per_page)))
    except (TypeError, ValueError):
        per_page = 30

    query = (query or '').strip().lower()
    items = []
    if os.path.isdir(download_root):
        for folder in os.listdir(download_root):
            folder_path = os.path.join(download_root, folder)
            if not os.path.isdir(folder_path) or '@' not in folder:
                continue
            screen_name = folder.rsplit('@', 1)[1]
            for entry in _build_tweet_entries_from_folder(folder_path, folder, screen_name):
                if not _entry_matches_media_filter(entry, media_filter):
                    continue
                if query:
                    haystack = ' '.join([
                        entry.get('content', ''),
                        entry.get('display_name', ''),
                        entry.get('username', ''),
                    ]).lower()
                    if query not in haystack:
                        continue
                items.append(entry)

    items.sort(key=lambda x: x.get('time', ''), reverse=True)
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    return {
        'items': items[start:end],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'query': query,
        'media_filter': media_filter,
    }


def _scan_media_library(download_root):
    by_key = {}

    if not os.path.isdir(download_root):
        return []

    for folder in os.listdir(download_root):
        folder_path = os.path.join(download_root, folder)
        if not os.path.isdir(folder_path) or '@' not in folder:
            continue
        screen_name = folder.rsplit('@', 1)[1]
        metadata = {}
        for row in parse_media_csv(os.path.join(folder_path, f'{screen_name}.csv')):
            local_file = row.get('local_file', '').replace('\\', '/').strip()
            if not local_file:
                continue
            if local_file.lower() in ('saved filename', 'filename'):
                continue
            key = (folder, local_file.lower())
            metadata[key] = row
            item = {
                'time': row.get('time', ''),
                'display_name': row.get('display_name', ''),
                'username': row.get('username', screen_name),
                'content': row.get('content', ''),
                'folder': folder,
                'tweet_url': row.get('url', ''),
                'media_type': row.get('media_type', '') or _media_type_from_filename(local_file),
                'local_file': local_file,
                'media_path': f'/media/{folder}/{local_file}',
                'source': 'csv',
            }
            by_key.setdefault(key, item)

        for current_root, _, filenames in os.walk(folder_path):
            for filename in filenames:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in MEDIA_LIBRARY_EXTENSIONS:
                    continue
                full_path = os.path.join(current_root, filename)
                rel_path = os.path.relpath(full_path, folder_path).replace('\\', '/')
                key = (folder, rel_path.lower())
                row = metadata.get(key, {})
                item = by_key.get(key, {})
                if not item:
                    item = {
                        'time': row.get('time', ''),
                        'display_name': row.get('display_name', ''),
                        'username': row.get('username', screen_name),
                        'content': row.get('content', ''),
                        'folder': folder,
                        'tweet_url': row.get('url', ''),
                        'media_type': row.get('media_type', '') or _media_type_from_filename(rel_path),
                        'local_file': rel_path,
                        'media_path': f'/media/{folder}/{rel_path}',
                        'source': 'local',
                    }
                    by_key[key] = item
                elif item.get('source') == 'csv':
                    item['source'] = 'csv+local'
                try:
                    item['modified'] = os.path.getmtime(full_path)
                except OSError:
                    item['modified'] = 0

    return list(by_key.values())


def build_media_library_response(download_root, page=1, per_page=60, query='', media_filter='all', force_refresh=False):
    items = []
    requested = (media_filter or 'all').lower()
    cache_key = os.path.realpath(download_root)
    if force_refresh or cache_key not in _MEDIA_LIBRARY_CACHE:
        _MEDIA_LIBRARY_CACHE[cache_key] = {
            'items': _scan_media_library(download_root),
            'scanned_at': time.time(),
        }
    all_items = _MEDIA_LIBRARY_CACHE[cache_key]['items']

    for item in all_items:
        if not _media_item_matches_filter(item, requested):
            continue
        if not _media_item_matches_query(item, query):
            continue
        items.append(item)

    items.sort(key=lambda x: (x.get('time') or '', x.get('modified') or 0, x.get('folder') or '', x.get('local_file') or ''), reverse=True)

    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = max(1, min(200, int(per_page)))
    except (TypeError, ValueError):
        per_page = 60
    total = len(items)
    total_pages = max(1, (total + per_page - 1) // per_page)
    if page > total_pages:
        page = total_pages
    start = (page - 1) * per_page
    end = start + per_page
    return {
        'items': items[start:end],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'query': query or '',
        'media_filter': media_filter,
        'indexed': sum(1 for item in items if 'csv' in item.get('source', '')),
        'local': sum(1 for item in items if 'local' in item.get('source', '')),
        'orphan': sum(1 for item in items if item.get('source') == 'local'),
    }


def _folder_csv_path(folder_path, folder):
    if '@' not in folder:
        return ''
    screen_name = folder.rsplit('@', 1)[1]
    return os.path.join(folder_path, f'{screen_name}.csv')


def _format_bytes(size):
    try:
        size = float(size)
    except (TypeError, ValueError):
        size = 0
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit = 0
    while size >= 1024 and unit < len(units) - 1:
        size /= 1024
        unit += 1
    if unit == 0:
        return f'{int(size)} B'
    return f'{size:.1f} {units[unit]}'


def build_dashboard_response(download_root, detail_limit=120):
    folders = []
    entries = []
    media_files_seen = set()
    storage_bytes = 0
    image_count = 0
    video_count = 0
    missing_media_files = []
    folders_without_csv = []
    candidates = []

    if os.path.isdir(download_root):
        for folder in os.listdir(download_root):
            folder_path = os.path.join(download_root, folder)
            if not os.path.isdir(folder_path) or '@' not in folder:
                continue

            csv_path = _folder_csv_path(folder_path, folder)
            display_name = folder.rsplit('@', 1)[0]
            screen_name = folder.rsplit('@', 1)[1]
            if not os.path.isfile(csv_path):
                folders_without_csv.append(folder)
                folders.append({
                    'folder': folder,
                    'display_name': display_name,
                    'screen_name': screen_name,
                    'tweet_count': 0,
                    'media_count': 0,
                    'latest_time': '',
                    'latest_sort': 0,
                    'size_bytes': 0,
                    'size_label': '0 B',
                })
                continue

            media_count, text_count = _count_csv_items(csv_path)
            try:
                csv_mtime = os.path.getmtime(csv_path)
            except OSError:
                csv_mtime = 0
            folder_info = {
                'folder': folder,
                'display_name': display_name,
                'screen_name': screen_name,
                'tweet_count': media_count + text_count,
                'media_count': media_count,
                'latest_time': '',
                'latest_sort': csv_mtime,
                'size_bytes': 0,
                'size_label': '0 B',
                'csv_path': csv_path,
                'folder_path': folder_path,
            }
            folders.append(folder_info)
            candidates.append(folder_info)

        candidates.sort(key=lambda item: item.get('latest_sort', 0), reverse=True)
        detailed = candidates[:max(1, int(detail_limit or 120))]

        for folder_info in detailed:
            folder = folder_info['folder']
            folder_path = folder_info['folder_path']
            screen_name = folder_info['screen_name']
            folder_entries = _build_tweet_entries_from_folder(folder_path, folder, screen_name)
            folder_media_count = 0
            folder_size = 0
            latest_time = ''

            for entry in folder_entries:
                entries.append(entry)
                if entry.get('time', '') > latest_time:
                    latest_time = entry.get('time', '')
                for media in entry.get('media_items') or []:
                    local_file = media.get('local_file', '')
                    if not local_file:
                        continue
                    media_key = (folder, local_file)
                    if media_key in media_files_seen:
                        continue
                    media_files_seen.add(media_key)
                    folder_media_count += 1
                    is_video_media = local_file.lower().endswith(('.mp4', '.webm')) or 'video' in media.get('media_type', '').lower()
                    if is_video_media:
                        video_count += 1
                    else:
                        image_count += 1
                    media_path = os.path.join(folder_path, local_file)
                    if os.path.isfile(media_path):
                        file_size = os.path.getsize(media_path)
                        storage_bytes += file_size
                        folder_size += file_size
                    else:
                        missing_media_files.append(f'{folder}/{local_file}')

            folder_info['tweet_count'] = len(folder_entries)
            folder_info['media_count'] = folder_media_count
            folder_info['latest_time'] = latest_time
            folder_info['latest_sort'] = latest_time or folder_info.get('latest_sort', 0)
            folder_info['size_bytes'] = folder_size
            folder_info['size_label'] = _format_bytes(folder_size)

    total_tweets = sum(item.get('tweet_count', 0) for item in folders)
    total_media = sum(item.get('media_count', 0) for item in folders)
    sampled = len(candidates) > max(1, int(detail_limit or 120))

    folders.sort(key=lambda item: str(item.get('latest_sort', '')), reverse=True)
    largest_folders = sorted(folders, key=lambda item: item.get('size_bytes', 0), reverse=True)[:8]
    recent_entries = sorted(entries, key=lambda item: item.get('time', ''), reverse=True)[:8]
    public_folders = []
    for item in folders:
        public_item = dict(item)
        public_item.pop('csv_path', None)
        public_item.pop('folder_path', None)
        public_item.pop('latest_sort', None)
        public_folders.append(public_item)
    public_largest = []
    for item in largest_folders:
        public_item = dict(item)
        public_item.pop('csv_path', None)
        public_item.pop('folder_path', None)
        public_item.pop('latest_sort', None)
        public_largest.append(public_item)

    return {
        'totals': {
            'users': len(folders),
            'tweets': total_tweets,
            'media': total_media,
        },
        'media_types': {
            'image': image_count,
            'video': video_count,
        },
        'storage': {
            'bytes': storage_bytes,
            'label': _format_bytes(storage_bytes),
            'sampled': sampled,
        },
        'recent_users': public_folders[:8],
        'largest_folders': public_largest,
        'recent_entries': recent_entries,
        'sampled': sampled,
        'detail_limit': detail_limit,
        'health': {
            'folders_without_csv': folders_without_csv[:20],
            'missing_media_files': missing_media_files[:20],
            'folder_without_csv_count': len(folders_without_csv),
            'missing_media_file_count': len(missing_media_files),
        },
    }


def search_users_and_tweets(query):
    q = query.lower()
    users_result = []
    tweets_result = []
    download_root = get_download_root()
    if not os.path.isdir(download_root):
        return users_result, tweets_result
    for folder in os.listdir(download_root):
        folder_path = os.path.join(download_root, folder)
        if not os.path.isdir(folder_path) or '@' not in folder:
            continue
        parts = folder.rsplit('@', 1)
        display_name = parts[0]
        screen_name = parts[1]
        if q in display_name.lower() or q in screen_name.lower():
            csv_path = os.path.join(folder_path, f'{screen_name}.csv')
            media_count, tweet_count = _count_csv_items(csv_path)
            users_result.append({
                'display_name': display_name,
                'screen_name': screen_name,
                'folder': folder,
                'media_count': media_count,
                'tweet_count': tweet_count,
            })

        media_csv = os.path.join(folder_path, f'{screen_name}.csv')
        all_items = parse_media_csv(media_csv)
        for item in all_items:
            if q in item.get('content', '').lower():
                tweets_result.append({
                    'time': item['time'],
                    'display_name': item['display_name'],
                    'username': item['username'],
                    'url': item['url'],
                    'content': item['content'],
                    'likes': item['likes'],
                    'retweets': item['retweets'],
                    'replies': item['replies'],
                    'local_file': item.get('local_file', ''),
                    'folder': folder,
                    'screen_name': screen_name,
                })
    tweets_result.sort(key=lambda x: x['time'], reverse=True)
    users_result.sort(key=lambda u: u['display_name'].lower())
    return users_result, tweets_result


def default_config_data():
    return {
        "config_version": CURRENT_CONFIG_VERSION,
        "save_path": "downloads",
        "user_list": [],
        "cookie": "",
        "bearer_token": "",
        "proxy": "",
        "time_range": "2015-01-01:2030-01-01",
        "image_format": "orig",
        "mode": {
            "has_video": True,
            "has_text": True,
            "has_retweet": False,
            "has_highlights": False,
            "has_likes": False
        },
        "download": {
            "max_concurrent": 16,
            "async_enabled": True,
            "enable_cache": True,
            "auto_sync": False,
            "checkpoint_expire_hours": 12
        },
        "list_sync": {
            "enabled": False,
            "list_id": "",
            "list_owner": "",
            "list_slug": "",
            "lists": []
        },
        "retry": {
            "max_user_retries": 3,
            "delay_seconds": 10
        },
        "logging": {
            "verbose": False,
            "log_file": ""
        },
        "tag_search": {
            "tag": "",
            "filter": "",
            "download_count": 100,
            "media_latest": False,
            "text_mode": False
        },
        "text_download": {
            "user_list": [],
            "max_tweets": 500,
            "request_delay": 2,
            "max_retries": 3
        },
        "theme": "dark-glass"
    }


def _merge_missing_defaults(config_data, defaults):
    changed = False
    for key, value in defaults.items():
        if key not in config_data:
            config_data[key] = value
            changed = True
        elif isinstance(config_data[key], dict) and isinstance(value, dict):
            child_changed = _merge_missing_defaults(config_data[key], value)
            changed = changed or child_changed
    return changed


def normalize_checkpoint_expire_hours(value, default=12):
    try:
        hours = int(float(value))
    except (TypeError, ValueError):
        hours = default
    return max(0, min(168, hours))


def get_checkpoint_expire_hours(config_data=None):
    if config_data is None:
        config_data = load_config_data()
    download_cfg = (config_data or {}).get('download') or {}
    return normalize_checkpoint_expire_hours(download_cfg.get('checkpoint_expire_hours', 12))


def migrate_config_data(config_data):
    if not isinstance(config_data, dict):
        config_data = {}
    changed = _merge_missing_defaults(config_data, default_config_data())
    list_sync = config_data.get("list_sync") or {}
    if not isinstance(list_sync, dict):
        list_sync = {}
        config_data["list_sync"] = list_sync
        changed = True
    legacy_id = (list_sync.get("list_id") or "").strip()
    legacy_owner = (list_sync.get("list_owner") or "").strip()
    legacy_slug = (list_sync.get("list_slug") or "").strip()
    lists = list_sync.get("lists")
    if not isinstance(lists, list):
        lists = []
        list_sync["lists"] = lists
        changed = True
    if not lists and (legacy_id or legacy_owner or legacy_slug):
        lists.append({
            "name": legacy_slug or legacy_owner or legacy_id or "List",
            "list_id": legacy_id,
            "list_owner": legacy_owner,
            "list_slug": legacy_slug,
            "enabled": list_sync.get("enabled", True) is not False
        })
        changed = True
    if config_data.get("config_version") != CURRENT_CONFIG_VERSION:
        config_data["config_version"] = CURRENT_CONFIG_VERSION
        changed = True
    return config_data, changed


def backup_config_file(config_path=CONFIG_PATH):
    if not os.path.exists(config_path):
        return
    backup_path = config_path + ".bak"
    try:
        shutil.copy2(config_path, backup_path)
    except OSError as e:
        print(f"Failed to back up config: {e}")


def load_config_data():
    ensure_config_file(CONFIG_PATH)
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        migrated, changed = migrate_config_data(data)
        if changed:
            save_config_data(migrated)
        return migrated
    except (OSError, json.JSONDecodeError) as e:
        print(f"Failed to load config: {e}")
        return {}


def ensure_config_file(config_path=CONFIG_PATH, example_path=BUNDLED_CONFIG_EXAMPLE):
    if os.path.exists(config_path):
        return
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    if os.path.exists(example_path):
        with open(example_path, 'r', encoding='utf-8-sig') as src:
            data = src.read()
    else:
        data = json.dumps(default_config_data(), indent=4, ensure_ascii=False)
    with open(config_path, 'w', encoding='utf-8') as dst:
        dst.write(data)
        if not data.endswith('\n'):
            dst.write('\n')


def save_config_data(data):
    try:
        tmp_path = CONFIG_PATH + '.tmp'
        backup_config_file(CONFIG_PATH)
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.write('\n')
        os.replace(tmp_path, CONFIG_PATH)
    except OSError as e:
        print(f"Failed to save config: {e}")


def open_directory_dialog(initial_dir=''):
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    try:
        kwargs = {'title': 'Select download folder'}
        if initial_dir and os.path.isdir(initial_dir):
            kwargs['initialdir'] = initial_dir
        return filedialog.askdirectory(**kwargs)
    finally:
        root.destroy()


def deep_set(d, key_path, value):
    keys = key_path.split('.')
    for k in keys[:-1]:
        if k not in d:
            d[k] = {}
        d = d[k]
    d[keys[-1]] = value


def normalize_version(value):
    value = str(value or "").strip()
    if value.lower().startswith("version "):
        value = value[8:].strip()
    return value[1:] if value.lower().startswith("v") else value


def version_parts(value):
    parts = []
    for item in re.split(r"[^0-9]+", normalize_version(value)):
        if item:
            parts.append(int(item))
    return parts or [0]


def is_newer_version(candidate, current):
    left = version_parts(candidate)
    right = version_parts(current)
    size = max(len(left), len(right))
    left += [0] * (size - len(left))
    right += [0] * (size - len(right))
    return left > right


def fetch_latest_github_release():
    req = urllib.request.Request(
        GITHUB_RELEASES_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "xDownloader-update-checker",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code not in (403, 429):
            raise
        return fetch_latest_github_release_from_page()


def fetch_latest_github_release_from_page():
    req = urllib.request.Request(
        GITHUB_RELEASES_LATEST_URL,
        headers={"User-Agent": "xDownloader-update-checker"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        final_url = resp.geturl()
        page = resp.read(300000).decode("utf-8", "ignore")
    tag = final_url.rstrip("/").rsplit("/", 1)[-1]
    if not tag or tag == "latest":
        match = re.search(r"/DocJ2000/xDownloader/releases/tag/([^\"'<>\s]+)", page)
        tag = match.group(1) if match else ""
    installer_name = f"xDownloader-Setup-{tag}.exe" if tag else ""
    asset_url = f"https://github.com/DocJ2000/xDownloader/releases/download/{tag}/{installer_name}" if tag else ""
    return {
        "tag_name": tag,
        "html_url": final_url,
        "body": "",
        "assets": [
            {
                "name": installer_name,
                "browser_download_url": asset_url,
                "size": 0,
            }
        ] if tag else [],
    }


def find_installer_asset(release):
    for asset in (release or {}).get("assets") or []:
        name = asset.get("name") or ""
        if re.match(r"^xDownloader-Setup-.+\.exe$", name, re.IGNORECASE):
            return asset
    return None


def get_runtime_mode():
    return "packaged" if IS_FROZEN else "source"


def build_update_status(release, current_version=None, runtime_mode=None):
    current_version = current_version or APP_VERSION
    runtime_mode = runtime_mode or get_runtime_mode()
    latest_version = (release or {}).get("tag_name") or (release or {}).get("name") or ""
    asset = find_installer_asset(release)
    update_available = bool(latest_version and is_newer_version(latest_version, current_version))
    can_install_update = runtime_mode == "packaged" and asset is not None
    return {
        "ok": True,
        "current_version": current_version,
        "latest_version": latest_version,
        "update_available": update_available,
        "runtime_mode": runtime_mode,
        "can_install_update": can_install_update,
        "release_url": (release or {}).get("html_url") or "",
        "notes": (release or {}).get("body") or "",
        "installer_name": (asset or {}).get("name") or "",
        "installer_size": (asset or {}).get("size") or 0,
        "download_url": (asset or {}).get("browser_download_url") or "",
        "installer_available": asset is not None,
    }


def is_valid_installer_name(name):
    return bool(re.match(r"^xDownloader-Setup-.+\.exe$", os.path.basename(name or ""), re.IGNORECASE))


def is_valid_update_url(url):
    parsed = urllib.parse.urlparse(url or "")
    return parsed.scheme in ("http", "https") and parsed.netloc and parsed.path.lower().endswith(".exe")


def download_update_asset(url):
    req = urllib.request.Request(url, headers={"User-Agent": "xDownloader-update-downloader"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        while True:
            chunk = resp.read(1024 * 128)
            if not chunk:
                break
            yield chunk


def updates_dir():
    return os.path.join(PROJECT_ROOT, "updates")


def update_file_path(installer_name):
    safe_name = os.path.basename(installer_name or "")
    return os.path.join(updates_dir(), safe_name)


@app.route('/api/users')
def api_users():
    return jsonify(get_user_folders())


@app.route('/api/user/<screen_name>/tweets')
def api_user_tweets(screen_name):
    return jsonify(get_user_tweets(screen_name))


@app.route('/api/stats')
def api_stats():
    total_users = 0
    total_media = 0
    total_tweets = 0
    download_root = get_download_root()
    if os.path.isdir(download_root):
        for folder in os.listdir(download_root):
            folder_path = os.path.join(download_root, folder)
            if not os.path.isdir(folder_path) or '@' not in folder:
                continue
            total_users += 1
            parts = folder.rsplit('@', 1)
            sn = parts[1]
            csv_path = os.path.join(folder_path, f'{sn}.csv')
            mc, tc = _count_csv_items(csv_path)
            total_media += mc
            total_tweets += tc
    return jsonify({
        'total_users': total_users,
        'total_media': total_media,
        'total_tweets': total_tweets,
    })


@app.route('/api/config/status')
def api_config_status():
    return jsonify(build_config_status(load_config_data()))


@app.route('/api/update/check')
def api_update_check():
    try:
        release = fetch_latest_github_release()
        return jsonify(build_update_status(release))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
        return jsonify({'ok': False, 'error': str(e)}), 502


@app.route('/api/update/download', methods=['POST'])
def api_update_download():
    body = request.get_json(silent=True) or {}
    download_url = (body.get('download_url') or '').strip()
    installer_name = (body.get('installer_name') or '').strip()
    if not is_valid_installer_name(installer_name):
        return jsonify({'ok': False, 'error': 'invalid installer name'}), 400
    if not is_valid_update_url(download_url):
        return jsonify({'ok': False, 'error': 'invalid download url'}), 400

    target_dir = updates_dir()
    target_path = update_file_path(installer_name)
    tmp_path = target_path + '.tmp'
    try:
        os.makedirs(target_dir, exist_ok=True)
        with open(tmp_path, 'wb') as f:
            for chunk in download_update_asset(download_url):
                f.write(chunk)
        os.replace(tmp_path, target_path)
        return jsonify({'ok': True, 'file_path': target_path, 'installer_name': installer_name})
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return jsonify({'ok': False, 'error': str(e)}), 502


@app.route('/api/update/open', methods=['POST'])
def api_update_open():
    body = request.get_json(silent=True) or {}
    file_path = os.path.abspath(body.get('file_path') or '')
    allowed_root = os.path.abspath(updates_dir())
    if not file_path.startswith(allowed_root + os.sep) or not is_valid_installer_name(file_path):
        return jsonify({'ok': False, 'error': 'invalid installer path'}), 400
    if not os.path.isfile(file_path):
        return jsonify({'ok': False, 'error': 'installer not found'}), 404
    try:
        if hasattr(os, 'startfile'):
            os.startfile(file_path)
            return jsonify({'ok': True})
        return jsonify({'ok': False, 'error': 'open installer is only supported on Windows'}), 400
    except OSError as e:
        return jsonify({'ok': False, 'error': str(e)}), 502


@app.route('/api/dialog/directory', methods=['POST'])
def api_dialog_directory():
    payload = request.get_json(silent=True) or {}
    selected = open_directory_dialog((payload.get('initial_dir') or '').strip())
    if not selected:
        return jsonify({'ok': False, 'path': ''})
    return jsonify({'ok': True, 'path': selected})


@app.route('/api/search')
def api_search():
    q = request.args.get('q', '')
    if len(q) < 2:
        return jsonify({'users': [], 'tweets': []})
    users, tweets = search_users_and_tweets(q)
    return jsonify({'users': users, 'tweets': tweets})


@app.route('/api/timeline')
def api_timeline():
    return jsonify(build_timeline_response(
        get_download_root(),
        page=request.args.get('page', 1),
        per_page=request.args.get('per_page', 30),
        query=request.args.get('q', ''),
        media_filter=request.args.get('media', 'all'),
    ))


@app.route('/api/media')
def api_media_library():
    return jsonify(build_media_library_response(
        get_download_root(),
        page=request.args.get('page', 1),
        per_page=request.args.get('per_page', 60),
        query=request.args.get('q', ''),
        media_filter=request.args.get('media', 'all'),
        force_refresh=request.args.get('refresh') in ('1', 'true', 'yes'),
    ))


@app.route('/api/dashboard')
def api_dashboard():
    return jsonify(build_dashboard_response(get_download_root()))


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'GET':
        data = load_config_data()
        if 'cookie' in data:
            data['cookie'] = data['cookie'][:20] + '...[hidden]'
        if 'bearer_token' in data:
            data['bearer_token'] = data['bearer_token'][:20] + '...[hidden]'
        return jsonify(data)
    else:
        updates = request.get_json()
        if not updates:
            return jsonify({'error': 'empty body'}), 400
        data = load_config_data()
        for key, value in updates.items():
            if isinstance(value, str) and '[hidden]' in value:
                continue
            if '.' in key:
                deep_set(data, key, value)
            else:
                data[key] = value
        save_config_data(data)
        return jsonify({'ok': True})


def normalize_user_list(users):
    seen = set()
    normalized = []
    for item in users or []:
        user = str(item or '').strip().lstrip('@')
        key = user.lower()
        if user and key not in seen:
            seen.add(key)
            normalized.append(user)
    return normalized


def find_unavailable_users(users):
    if not users:
        return []
    import asyncio
    import sys
    sys.path.insert(0, APP_DIR)
    from src.config import load_config
    from src.client import create_http_client
    from src.twitter_api import TwitterAPI, RateLimitError, TwitterAPIError

    config = load_config(CONFIG_PATH)
    client = create_http_client(config)
    api = TwitterAPI(config, client)
    loop = asyncio.new_event_loop()
    unavailable = []
    try:
        for user in normalize_user_list(users):
            try:
                info = loop.run_until_complete(api.fetch_user_info(user))
                if info is None:
                    unavailable.append(user)
            except (RateLimitError, TwitterAPIError):
                continue
            except Exception:
                continue
    finally:
        client.close()
        loop.close()
    return unavailable


@app.route('/api/users/prune', methods=['POST'])
def api_users_prune():
    body = request.get_json() or {}
    data = load_config_data()
    users = normalize_user_list(data.get('user_list') or [])
    candidates = normalize_user_list(body.get('users') or find_unavailable_users(users))
    if not body.get('confirm'):
        return jsonify({'ok': True, 'candidates': candidates, 'removed': []})

    candidate_set = {u.lower() for u in candidates}
    kept = [u for u in users if u.lower() not in candidate_set]
    removed = [u for u in users if u.lower() in candidate_set]
    data['user_list'] = kept
    save_config_data(data)
    return jsonify({'ok': True, 'candidates': candidates, 'removed': removed})


@app.route('/api/download/start', methods=['POST'])
def api_download_start():
    global download_state
    if download_state['running']:
        return jsonify({'error': 'download already running'}), 409
    body = request.get_json() or {}
    users = body.get('users', [])
    if not users:
        return jsonify({'error': 'no users provided'}), 400
    auto_shutdown = bool(body.get('auto_shutdown'))
    started_at = time.time()
    storage_before = directory_size_bytes(get_download_root())

    download_state = {
        'running': True,
        'paused': False,
        'terminated': False,
        'failed': False,
        'auto_shutdown': auto_shutdown,
        'shutdown_scheduled': False,
        'history_recorded': False,
        'requested_users': list(users),
        'started_at': started_at,
        'storage_before': storage_before,
        'storage_after': storage_before,
        'state': 'running',
        'logs': [],
        'current': 0,
        'total': len(users),
        'stats': None,
    }

    t = threading.Thread(target=_run_download, args=(users,), daemon=True)
    t.start()
    return jsonify({'ok': True})


def _run_download(users):
    global download_state
    queue_log = []

    import json as _json
    progress_file = download_progress_path()
    progress_total = len(users)
    checkpoint_expire_hours = get_checkpoint_expire_hours()

    completed = set()
    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                prog = _json.load(f)
            completed_at = prog.get('completed_at', 0)
            age_hours = (time.time() - completed_at) / 3600 if completed_at else 999
            if checkpoint_expire_hours <= 0 or age_hours > checkpoint_expire_hours:
                line = time.strftime('[%H:%M:%S] ') + f"Checkpoint expired ({age_hours:.1f}h old), clearing"
                queue_log.append(line)
                download_state['logs'] = queue_log[-200:]
                os.remove(progress_file)
            else:
                completed = set(prog.get('completed', []))
        except Exception:
            completed = set()

    if completed:
        users = [u for u in users if u not in completed]
        if not users:
            download_state['stats'] = {
                'users': progress_total,
                'skipped': 0,
                'images': 0,
                'videos': 0,
                'text_tweets': 0,
            }
            download_state['current'] = progress_total
            download_state['total'] = progress_total
            download_state['storage_after'] = directory_size_bytes(get_download_root())
            download_state['logs'] = [
                time.strftime('[%H:%M:%S] All users recently processed, nothing to do'),
                time.strftime(f'[%H:%M:%S] Checkpoint will expire after {checkpoint_expire_hours}h'),
                time.strftime('[%H:%M:%S] Total: ' + str(progress_total) + ' users complete'),
            ]
            finalize_download_state()
            return
    completed_lock = threading.Lock()

    if completed:
        remaining_count = len(users) - len(completed)
        download_state['total'] = progress_total
        download_state['current'] = len(completed)

    _worker_loops = threading.local()

    def _get_worker_loop():
        if not hasattr(_worker_loops, 'loop') or _worker_loops.loop is None or _worker_loops.loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _worker_loops.loop = loop
        return _worker_loops.loop

    class QLogger:
        def info(self, msg):
            line = time.strftime('[%H:%M:%S] ') + msg
            queue_log.append(line)
            download_state['logs'] = queue_log[-200:]

        def error(self, msg):
            line = time.strftime('[%H:%M:%S] ERROR: ') + msg
            queue_log.append(line)
            download_state['logs'] = queue_log[-200:]

        def warning(self, msg):
            line = time.strftime('[%H:%M:%S] WARN: ') + msg
            queue_log.append(line)
            download_state['logs'] = queue_log[-200:]

        def debug(self, msg):
            line = time.strftime('[%H:%M:%S] DEBUG: ') + msg
            queue_log.append(line)
            download_state['logs'] = queue_log[-200:]

    qlog = QLogger()
    completed_count = len(completed)
    stats = {"users": completed_count, "skipped": 0, "images": 0, "videos": 0, "text_tweets": 0}
    stats_lock = threading.Lock()
    user_counter = [completed_count]
    config_lock = threading.Lock()
    rate_limit_until = [0.0]

    def _wait_for_rate_limit():
        with config_lock:
            remaining = rate_limit_until[0] - time.time()
        if remaining > 0:
            qlog.warning(f"Global rate limit cooldown, pausing {remaining:.0f}s...")
            time.sleep(remaining + 1)

    def _set_rate_limited(duration=90.0):
        with config_lock:
            new_until = time.time() + duration
            if new_until > rate_limit_until[0]:
                rate_limit_until[0] = new_until

    try:
        import sys, csv as csv_mod
        from datetime import datetime
        import httpx
        from concurrent.futures import ThreadPoolExecutor, as_completed
        sys.path.insert(0, APP_DIR)
        from src.config import load_config
        from src.client import create_http_client
        from src.twitter_api import TwitterAPI
        from src.downloader import MediaDownloader
        from src.models import UserInfo, DownloadContext
        from src.csv_output import CSVWriter
        from src.cache import DownloadCache
        from src.utils import encode_url, encode_query, timestamp_to_readable, sanitize_filename
        from src.merge import find_existing_folder
        import asyncio

        config = load_config(CONFIG_PATH)
        total = len(users)

        def _process_user(user, idx):
            if not download_state['running']:
                return
            with config_lock:
                qlog.info(f"Processing ({idx}/{total}): @{user}")

            client = create_http_client(config)
            api = TwitterAPI(config, client, debug_logger=qlog)

            loop = _get_worker_loop()

            user_info = None
            for info_attempt in range(3):
                _wait_for_rate_limit()
                try:
                    user_info = loop.run_until_complete(api.fetch_user_info(user))
                    break
                except Exception as e:
                    err_msg = str(e).lower()
                    if '429' in err_msg or 'rate limit' in err_msg:
                        _set_rate_limited(90)
                        wait = 5 * (info_attempt + 1)
                        qlog.warning(f"Fetch info for @{user} attempt {info_attempt+1}/3 rate limited, pausing {wait}s...")
                        time.sleep(wait)
                    elif info_attempt < 2:
                        wait = 5 * (info_attempt + 1)
                        qlog.warning(f"Fetch info for @{user} attempt {info_attempt+1}/3 failed: [{type(e).__name__}] {e}, retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        qlog.error(f"Failed to fetch info for @{user}: [{type(e).__name__}] {e}")
                        with stats_lock:
                            stats["skipped"] += 1
                        with completed_lock:
                            completed.add(user)
                            with open(progress_file, 'w', encoding='utf-8') as f:
                                _json.dump({
                                    'completed': sorted(completed),
                                    'completed_at': time.time(),
                                    'total': progress_total,
                                }, f, ensure_ascii=False)
                        client.close()
                        return

            if user_info is None:
                qlog.warning(f"User @{user} not found (suspended/deleted), skipping")
                with stats_lock:
                    stats["skipped"] += 1
                with completed_lock:
                    completed.add(user)
                    with open(progress_file, 'w', encoding='utf-8') as f:
                        _json.dump({
                            'completed': sorted(completed),
                            'completed_at': time.time(),
                            'total': progress_total,
                        }, f, ensure_ascii=False)
                client.close()
                return

            # --- media download ---
            qlog.info(
                f"User: {user_info.name} (@{user_info.screen_name}) | "
                f"Tweets: {user_info.statuses_count} | Media: {user_info.media_count}"
            )

            safe_name = sanitize_filename(user_info.name)
            folder_name = f"{safe_name}@{user}"
            user_dir = os.path.join(config.save_path, folder_name)
            existing = find_existing_folder(config.save_path, user)
            if existing:
                user_dir = existing
            os.makedirs(user_dir, exist_ok=True)
            user_info.save_path = user_dir

            # --- media download ---
            csv_writer = None
            cache = None
            try:
                csv_writer = CSVWriter(user_dir, user_info.name, user, config.time_range_str)
                cache = DownloadCache(user_dir) if config.enable_cache else None

                downloader = MediaDownloader(config, api, csv_writer, cache, ui_logger=qlog)
                ctx = DownloadContext(user=user_info)

                qlog.info(f"  Starting media download for @{user}...")
                loop.run_until_complete(downloader.run(user_info, ctx))
                qlog.info(f"  Media done: {downloader.image_count} images, {downloader.video_count} videos, {downloader.download_count} total")
                with stats_lock:
                    stats["images"] += downloader.image_count
                    stats["videos"] += downloader.video_count
            except Exception as e:
                qlog.warning(f"Media download error for @{user}: {e}")

            if cache:
                cache.save()

            # --- text tweet download (exclude retweets) ---
            try:
                user_id = user_info.rest_id
                if user_id:
                    if csv_writer is None:
                        try:
                            csv_writer = CSVWriter(user_dir, user_info.name, user, config.time_range_str)
                        except Exception:
                            csv_writer = None
                    if config.has_text:
                        qlog.info(f"Fetching text tweets for @{user}...")
                    else:
                        qlog.info(f"Text tweet download disabled for @{user}")
                    all_tweets = []
                    cursor = ''
                    page = 0
                    max_tweets = (config.text_max_tweets or 1000) if config.has_text else 0
                    tweet_count = 100

                    while download_state['running'] and len(all_tweets) < max_tweets:
                        page += 1
                        cp = ('"cursor":"' + encode_query(cursor) + '",') if cursor else ''
                        tweets_url = (
                            'https://twitter.com/i/api/graphql/9zyyd1hebl7oNWIPdA8HRw/UserTweets'
                            '?variables={"userId":"' + user_id + '","count":' + str(tweet_count) + ',' + cp
                            + '"includePromotedContent":true,'
                            '"withVoice":true,"withV2Timeline":true}'
                            '&features={"responsive_web_graphql_exclude_directive_enabled":true,'
                            '"verified_phone_label_enabled":false,'
                            '"creator_subscriptions_tweet_preview_api_enabled":true,'
                            '"responsive_web_graphql_timeline_navigation_enabled":true,'
                            '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
                            '"c9s_tweet_anatomy_moderator_badge_enabled":true,'
                            '"tweetypie_unmention_optimization_enabled":true,'
                            '"responsive_web_edit_tweet_api_enabled":true,'
                            '"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,'
                            '"view_counts_everywhere_api_enabled":true,'
                            '"longform_notetweets_consumption_enabled":true,'
                            '"responsive_web_twitter_article_tweet_consumption_enabled":false,'
                            '"tweet_awards_web_tipping_enabled":false,'
                            '"freedom_of_speech_not_reach_fetch_enabled":true,'
                            '"standardized_nudges_misinfo":true,'
                            '"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,'
                            '"rweb_video_timestamps_enabled":true,'
                            '"longform_notetweets_rich_text_read_enabled":true,'
                            '"longform_notetweets_inline_media_enabled":true,'
                            '"responsive_web_media_download_video_enabled":false,'
                            '"responsive_web_enhance_cards_enabled":false}'
                        )

                        data = None
                        for attempt in range(3):
                            try:
                                resp = client.get(encode_url(tweets_url))
                                if resp.status_code == 429:
                                    wait = (attempt + 1) * 15
                                    qlog.warning(f"  TT p{page}: rate limited, waiting {wait}s...")
                                    time.sleep(wait)
                                    continue
                                if resp.status_code >= 400:
                                    qlog.warning(f"  TT p{page}: HTTP {resp.status_code}, retry {attempt+1}/3")
                                    time.sleep(2)
                                    continue
                                data = resp.json()
                                break
                            except httpx.TimeoutException:
                                qlog.warning(f"  TT p{page}: timeout (attempt {attempt+1}/3)")
                                time.sleep(1)
                            except Exception as e:
                                qlog.warning(f"  TT p{page}: {type(e).__name__} (attempt {attempt+1}/3)")
                                time.sleep(1)

                        if data is None:
                            qlog.warning(f"  TT p{page}: failed after 3 retries, stopping")
                            break

                        timeline = data.get('data', {}).get('user', {}).get('result', {}).get('timeline_v2', {})
                        instructions = timeline.get('timeline', {}).get('instructions', [])

                        next_cursor = ''
                        page_tweets = 0
                        for inst in instructions:
                            if inst.get('type') != 'TimelineAddEntries':
                                continue
                            for entry in inst.get('entries', []):
                                eid = entry.get('entryId', '')
                                if 'cursor-bottom' in eid:
                                    next_cursor = entry.get('content', {}).get('value', '')
                                if not eid.startswith('tweet-'):
                                    continue
                                try:
                                    ic = entry['content']['itemContent']
                                    tr = ic['tweet_results']
                                    result = tr['result']
                                    td = result.get('tweet', result)
                                    legacy = td['legacy']
                                    full_text = legacy.get('full_text', '')

                                    if full_text.startswith('RT @'):
                                        continue

                                    edit_until = td.get('edit_control', {}).get('editable_until_msecs', 0)
                                    if not edit_until:
                                        edit_until = td.get('edit_control', {}).get('edit_control_initial', {}).get('editable_until_msecs', 0)
                                    ts = int(edit_until) - 3600000 if edit_until else 0

                                    core = td.get('core', {}).get('user_results', {}).get('result', {})
                                    ul = core.get('legacy', {})
                                    dn = ul.get('name', 'Unknown')
                                    sn = '@' + ul.get('screen_name', 'unknown')
                                    sid = legacy.get('id_str', '')

                                    all_tweets.append({
                                        'timestamp': ts,
                                        'display_name': dn,
                                        'screen_name': sn,
                                        'tweet_url': f"https://twitter.com/{ul.get('screen_name','')}/status/{sid}",
                                        'content': full_text,
                                        'favorites': legacy.get('favorite_count', 0),
                                        'retweets': legacy.get('retweet_count', 0),
                                        'replies': legacy.get('reply_count', 0),
                                    })
                                    page_tweets += 1
                                except (KeyError, TypeError, IndexError):
                                    continue

                        if not next_cursor or next_cursor == cursor:
                            break
                        cursor = next_cursor
                        if page_tweets == 0:
                            break
                        qlog.info(f"  TT p{page}: {page_tweets} tweets (total {len(all_tweets)})")

                    if all_tweets and csv_writer:
                        with stats_lock:
                            stats["text_tweets"] += len(all_tweets)
                        existing_urls = csv_writer.existing_tweet_urls()
                        new_rows = []
                        for tweet in all_tweets:
                            url = tweet['tweet_url']
                            if url not in existing_urls:
                                existing_urls.add(url)
                                csv_writer.add_text_row([
                                    timestamp_to_readable(tweet['timestamp']),
                                    tweet['display_name'],
                                    tweet['screen_name'],
                                    url,
                                    tweet['content'],
                                    tweet['favorites'],
                                    tweet['retweets'],
                                    tweet['replies'],
                                ])
                                new_rows.append(url)

                        if new_rows:
                            qlog.info(f"Text tweets for @{user}: {len(new_rows)} new added to CSV ({len(all_tweets)} fetched)")
                        else:
                            qlog.info(f"Text tweets for @{user}: all {len(all_tweets)} already in CSV, skipped")
            except Exception as e:
                qlog.warning(f"Text tweet download error for @{user}: {e}")

            with stats_lock:
                stats["users"] += 1
                download_state['stats'] = dict(stats)
                user_counter[0] += 1
                download_state['current'] = user_counter[0]
            csv_writer.close() if csv_writer else None
            client.close()
            qlog.info(f"Completed @{user}")

            with completed_lock:
                completed.add(user)
                with open(progress_file, 'w', encoding='utf-8') as f:
                    _json.dump({
                        'completed': sorted(completed),
                        'completed_at': time.time(),
                        'total': progress_total,
                    }, f, ensure_ascii=False)

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(_process_user, u, i+1) for i, u in enumerate(users)]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    qlog.error(f"Worker thread crashed: {e}")
                if not download_state['running']:
                    pool.shutdown(wait=False)
                    break

        if download_state.get('terminated'):
            qlog.info("Download terminated. Progress was reset.")
        elif download_state.get('paused'):
            qlog.info("Download paused. Press continue to resume from checkpoint.")
        else:
            qlog.info("=" * 40)
            qlog.info(" DOWNLOAD COMPLETE")
            qlog.info("=" * 40)
            qlog.info(f"  Users processed:   {stats['users']}/{progress_total}")
            qlog.info(f"  Users skipped:     {stats['skipped']}")
            qlog.info(f"  New images:        {stats['images']}")
            qlog.info(f"  New videos:        {stats['videos']}")
            qlog.info(f"  New media total:   {stats['images'] + stats['videos']}")
            qlog.info(f"  New text tweets:   {stats['text_tweets']}")
            qlog.info("=" * 40)
        download_state['stats'] = dict(stats)

        if download_state.get('terminated') and os.path.exists(progress_file):
            os.remove(progress_file)
        elif stats['users'] >= progress_total and os.path.exists(progress_file):
            os.remove(progress_file)

    except Exception as e:
        download_state['failed'] = True
        qlog.error(f"Download crashed: {e}")
    finally:
        download_state['storage_after'] = directory_size_bytes(get_download_root())
        finalize_download_state()
        if download_state.get('shutdown_scheduled'):
            qlog.info("Auto shutdown scheduled in 60 seconds")
        qlog.info("Download finished")


@app.route('/api/download/status')
def api_download_status():
    state = dict(download_state)
    state['history'] = load_download_history()
    return jsonify(state)


def resolve_list_sync_request(body, config_data=None):
    config_data = load_config_data() if config_data is None else config_data
    list_sync = config_data.get('list_sync') or {}
    raw_id = str(body.get('list_url') or body.get('list_id') or list_sync.get('list_url') or list_sync.get('list_id') or '').strip()
    owner = str(body.get('list_owner') or list_sync.get('list_owner') or '').strip().replace('@', '')
    slug = str(body.get('list_slug') or list_sync.get('list_slug') or '').strip()

    url_match = re.search(r'/i/lists/(\d+)', raw_id)
    if url_match:
        raw_id = url_match.group(1)
    elif raw_id.startswith('http') or '/' in raw_id:
        cleaned = re.sub(r'^https?://(www\.)?(x|twitter)\.com/', '', raw_id).strip('/')
        parts = [part for part in cleaned.split('/') if part]
        if len(parts) >= 3 and parts[-2] == 'lists':
            owner = owner or parts[-3].replace('@', '')
            slug = slug or parts[-1]
            raw_id = ''
        elif len(parts) >= 2 and not raw_id.isdigit():
            owner = owner or parts[-2].replace('@', '')
            slug = slug or parts[-1]
            raw_id = ''

    return {
        'list_id': raw_id,
        'list_owner': owner,
        'list_slug': slug,
    }


@app.route('/api/download/sync', methods=['POST'])
def api_download_sync():
    global sync_state
    if sync_state['running']:
        return jsonify({'error': 'sync already running'}), 409
    body = request.get_json() or {}
    list_ref = resolve_list_sync_request(body)
    if not list_ref['list_id'] and not (list_ref['list_owner'] and list_ref['list_slug']):
        return jsonify({'error': 'no list configured'}), 400

    sync_state = {
        'running': True,
        'logs': [],
        'new_users': [],
        'total_members': 0,
    }
    t = threading.Thread(target=_run_sync, args=(list_ref,), daemon=True)
    t.start()
    return jsonify({'ok': True})


sync_state = {'running': False, 'logs': [], 'new_users': [], 'total_members': 0}


def _run_sync(list_ref):
    global sync_state
    queue_log = []

    class QLog:
        def info(self, msg):
            line = time.strftime('[%H:%M:%S] ') + msg
            queue_log.append(line)
            sync_state['logs'] = queue_log[-200:]
        def warning(self, msg):
            line = time.strftime('[%H:%M:%S] WARN: ') + msg
            queue_log.append(line)
            sync_state['logs'] = queue_log[-200:]
        def error(self, msg):
            line = time.strftime('[%H:%M:%S] ERROR: ') + msg
            queue_log.append(line)
            sync_state['logs'] = queue_log[-200:]

    qlog = QLog()
    try:
        list_id = list_ref.get('list_id', '')
        list_owner = list_ref.get('list_owner', '')
        list_slug = list_ref.get('list_slug', '')
        label = list_id or f"@{list_owner}/{list_slug}"
        qlog.info(f"SYNC started for list {label}")

        import sys
        sys.path.insert(0, APP_DIR)
        from src.config import load_config, save_user_list
        from src.client import create_http_client
        from src.twitter_api import TwitterAPI, RateLimitError, ListNotFoundError, TwitterAPIError

        qlog.info("SYNC: loading config...")
        config = load_config(CONFIG_PATH)

        qlog.info(f"SYNC: connecting to Twitter API...")
        client = create_http_client(config)
        api = TwitterAPI(config, client)
        members = []
        for attempt in range(5):
            qlog.info(f"SYNC: fetching list members (attempt {attempt + 1}/5)...")
            try:
                if list_id:
                    members = api.fetch_list_members_by_id(list_id)
                else:
                    members = api.fetch_list_members(list_owner, list_slug)
                break
            except RateLimitError:
                if attempt < 4:
                    wait = (attempt + 1) * 30
                    qlog.info(f"SYNC: rate limited, waiting {wait}s...")
                    time.sleep(wait)
                else:
                    qlog.warning("SYNC: rate limited after max retries")
            except ListNotFoundError:
                qlog.warning(f"SYNC: list {label} not found or API changed")
                break
            except TwitterAPIError as e:
                if attempt < 4:
                    wait = 10 * (attempt + 1)
                    qlog.warning(f"SYNC: API error ({e}), retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    qlog.warning(f"SYNC: API error after max retries ({e})")
            except Exception as e:
                if attempt < 4:
                    wait = 5 * (attempt + 1)
                    qlog.warning(f"SYNC: request failed ({type(e).__name__}: {e}), retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    qlog.warning(f"SYNC: request failed after max retries ({type(e).__name__}: {e})")
        client.close()

        if not members:
            qlog.warning("SYNC: no members fetched")
        else:
            qlog.info(f"SYNC: fetched {len(members)} members from list")

            existing = set(config.user_list)
            new_users = [m for m in members if m not in existing]

            if not new_users:
                qlog.info(f"SYNC: all {len(members)} members already in download list, no new users")
                sync_state['new_users'] = []
                sync_state['total_members'] = len(members)
            else:
                config.user_list = config.user_list + new_users
                save_user_list(CONFIG_PATH, config.user_list)
                sync_state['new_users'] = new_users
                sync_state['total_members'] = len(members)
                qlog.info(f"SYNC: added {len(new_users)} new users → total {len(config.user_list)}")
                for u in new_users:
                    qlog.info(f"  + @{u}")
    except Exception as e:
        import traceback
        qlog.error(f"SYNC crashed: {type(e).__name__}: {e}")
        qlog.error(f"  Traceback: {traceback.format_exc()[-300:]}")
    finally:
        sync_state['running'] = False


@app.route('/api/download/sync_status')
def api_download_sync_status():
    return jsonify(sync_state)


@app.route('/api/download/stop', methods=['POST'])
def api_download_stop():
    return api_download_pause()


@app.route('/api/download/pause', methods=['POST'])
def api_download_pause():
    global download_state
    download_state['running'] = False
    download_state['paused'] = True
    download_state['terminated'] = False
    download_state['state'] = 'paused'
    logs = download_state.setdefault('logs', [])
    logs.append(time.strftime('[%H:%M:%S] Pause requested. Progress checkpoint is kept.'))
    download_state['logs'] = logs[-200:]
    return jsonify({'ok': True, 'state': 'paused'})


@app.route('/api/download/terminate', methods=['POST'])
def api_download_terminate():
    global download_state
    download_state['running'] = False
    download_state['paused'] = False
    download_state['terminated'] = True
    download_state['state'] = 'terminated'
    progress_file = download_progress_path()
    if os.path.exists(progress_file):
        os.remove(progress_file)
    logs = download_state.setdefault('logs', [])
    logs.append(time.strftime('[%H:%M:%S] Terminate requested. Progress checkpoint was cleared.'))
    download_state['logs'] = logs[-200:]
    return jsonify({'ok': True, 'state': 'terminated'})


@app.route('/media/<path:filepath>')
def serve_media(filepath):
    safe_path = os.path.normpath(filepath)
    if safe_path.startswith('..') or os.path.isabs(safe_path):
        return 'Forbidden', 403
    download_root = get_download_root()
    root_path = os.path.realpath(download_root)
    full_path = os.path.realpath(os.path.join(download_root, safe_path))
    if not full_path.startswith(root_path + os.sep):
        return 'Forbidden', 403
    if not os.path.isfile(full_path):
        return 'Not found', 404
    ext = os.path.splitext(full_path)[1].lower()
    content_type = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
        '.png': 'image/png', '.gif': 'image/gif',
        '.webp': 'image/webp', '.mp4': 'video/mp4',
        '.webm': 'video/webm',
    }.get(ext, 'application/octet-stream')
    return send_file(full_path, mimetype=content_type, conditional=True)


@app.route('/')
def serve_index():
    return send_file(os.path.join(_BASE_DIR, 'index.html'), mimetype='text/html; charset=utf-8')


def create_app():
    return app


def main():
    import webbrowser
    import tkinter as tk
    from tkinter import ttk

    def start_flask():
        app.run(host='127.0.0.1', port=PORT, debug=False)

    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    time.sleep(1)
    webbrowser.open(f'http://127.0.0.1:{PORT}/')

    root = tk.Tk()
    root.title('X-Download')
    root.geometry('340x160')
    root.resizable(False, False)
    try:
        root.iconbitmap(default='')
    except Exception:
        pass

    frm = ttk.Frame(root, padding=20)
    frm.pack(fill='both', expand=True)

    ttk.Label(frm, text='xDownloader is running', font=('Segoe UI', 12, 'bold')).pack(pady=(0, 8))
    ttk.Label(frm, text=f'Browser opened at http://127.0.0.1:{PORT}/', foreground='gray').pack()
    ttk.Label(frm, text='Close this window to stop the server', foreground='gray').pack(pady=(4, 12))

    ttk.Button(frm, text='Open browser UI', command=lambda: webbrowser.open(f'http://127.0.0.1:{PORT}/')).pack(side='left', padx=(0, 8))
    ttk.Button(frm, text='Exit', command=lambda: os._exit(0)).pack(side='left')

    root.mainloop()
    os._exit(0)


if __name__ == '__main__':
    main()
