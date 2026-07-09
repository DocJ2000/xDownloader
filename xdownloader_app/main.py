"""Twitter/X media and text downloader CLI.

Usage:
    python -m xdownloader_app.main download
    python -m xdownloader_app.main tag
    python -m xdownloader_app.main text
    python -m xdownloader_app.main merge
    python -m xdownloader_app.main list-sync --list-id <list_id>

Configure private settings in the root-level config.json before running.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import AppConfig, load_config, save_user_list
from src.models import DownloadContext, UserInfo
from src.client import create_http_client
from src.twitter_api import TwitterAPI, TwitterAPIError, RateLimitError, ListNotFoundError
from src.downloader import MediaDownloader
from src.csv_output import CSVWriter
from src.cache import DownloadCache
from src.utils import timestamp_to_str, str_to_timestamp, sanitize_filename
from src.logger import Logger, log
from src.merge import (merge_user_folders, list_duplicates, find_existing_folder,
                        cleanup_duplicates, preview_duplicates)

BACKUP_START_STAMP = 655028357000


class UserMediaDownloader:
    """Core media download workflow for specified users."""

    def __init__(self, config: AppConfig):
        self.config = config

    def _resolve_auto_sync_time(self, save_path: str) -> int:
        files = sorted(os.listdir(save_path))
        if not files:
            return BACKUP_START_STAMP
        re_rule = r'\d{4}-\d{2}-\d{2}'
        for filename in reversed(files):
            match = os.path.splitext(filename)[0]
            if '-img_' in filename or '-vid_' in filename:
                import re
                found = re.findall(re_rule, filename)
                if found:
                    return str_to_timestamp(found[0])
        return BACKUP_START_STAMP

    def run_user(self, screen_name: str):
        client = create_http_client(
            self.config,
            referer=f'https://twitter.com/{screen_name}'
        )
        api = TwitterAPI(self.config, client)

        result = {"user": screen_name, "ok": False, "images": 0, "videos": 0, "total": 0}
        downloader = None
        csv_writer = None
        cache = None

        try:
            log.info(f"Fetching info for @{screen_name}...")
            user_info = asyncio.get_event_loop().run_until_complete(api.fetch_user_info(screen_name))
            if user_info is None:
                log.error(f"Failed to get user info for @{screen_name}")
                return result

            log.info(
                f"User: {user_info.name} (@{user_info.screen_name}) | "
                f"Tweets: {user_info.statuses_count} | "
                f"Media: {user_info.media_count}"
            )

            safe_name = f"{sanitize_filename(user_info.name)}@{user_info.screen_name}"
            save_path = os.path.join(self.config.save_path, safe_name)

            existing_path = find_existing_folder(self.config.save_path, user_info.screen_name)
            if existing_path and existing_path != save_path:
                log.info(f"检测到已有文件夹，复用: {os.path.basename(existing_path)}")
                save_path = existing_path
            elif not os.path.exists(save_path):
                os.makedirs(save_path)
            user_info.save_path = save_path

            if not self.config.has_likes:
                csv_writer = CSVWriter(
                    save_path,
                    user_info.name,
                    user_info.screen_name,
                    self.config.time_range_str
                )

            cache = None
            if self.config.enable_cache:
                cache = DownloadCache(save_path)

            downloader = MediaDownloader(self.config, api, csv_writer, cache)

            ctx = DownloadContext(user=user_info)

            if self.config.auto_sync:
                new_start = self._resolve_auto_sync_time(save_path)
                if new_start > BACKUP_START_STAMP:
                    log.info(f"Auto-sync: resuming from {timestamp_to_str(new_start)}")
                    ctx.start_time = new_start

            asyncio.get_event_loop().run_until_complete(downloader.run(user_info, ctx))

            result["images"] = downloader.image_count
            result["videos"] = downloader.video_count
            result["total"] = downloader.download_count

            if csv_writer:
                csv_writer.close()
            if cache:
                cache.save()

            log.info(f"Completed @{screen_name} — {downloader.download_count} files downloaded")
            result["ok"] = True
            return result

        except RateLimitError:
            log.error(f"Rate limit hit for @{screen_name}")
            return result
        except Exception as e:
            log.error(f"Error processing @{screen_name}: {e}")
            if downloader is not None:
                result["images"] = downloader.image_count
                result["videos"] = downloader.video_count
                result["total"] = downloader.download_count
                if downloader.download_count > 0:
                    log.info(f"Partial @{screen_name} — {downloader.download_count} files downloaded before error")
                    result["ok"] = True
            if csv_writer:
                csv_writer.close()
            if cache:
                cache.save()
            return result
        finally:
            client.close()


def _auto_list_sync(config: AppConfig, config_path: str = "config.json"):
    from src.client import create_http_client
    from src.config import save_user_list

    if not config.list_sync_list_id:
        log.warning("list_sync enabled but no list_id configured, skipping sync")
        return

    log.info(f"AUTO-SYNC: fetching members from list {config.list_sync_list_id}...")

    client = create_http_client(config)
    api = TwitterAPI(config, client)
    members = []
    for attempt in range(5):
        try:
            members = api.fetch_list_members_by_id(config.list_sync_list_id)
            break
        except RateLimitError:
            if attempt < 4:
                wait = (attempt + 1) * 30
                log.info(f"AUTO-SYNC: rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                log.warning("AUTO-SYNC: rate limited after max retries, skipping")
        except ListNotFoundError:
            log.warning(
                f"AUTO-SYNC: list {config.list_sync_list_id} not found or API changed. "
                f"Skipping sync."
            )
            break
        except TwitterAPIError as e:
            log.warning(f"AUTO-SYNC: API error ({e}), skipping sync")
            break
        except Exception as e:
            log.warning(f"AUTO-SYNC: request failed ({e}), retrying...")
            time.sleep(5)
    client.close()

    if not members:
        log.warning("AUTO-SYNC: no members fetched, skipping")
        return

    existing = set(config.user_list)
    new_users = [m for m in members if m not in existing]

    if not new_users:
        log.info(f"AUTO-SYNC: all {len(members)} members already in download list")
        return

    config.user_list = config.user_list + new_users
    save_user_list(config_path, config.user_list)
    log.info(
        f"AUTO-SYNC: added {len(new_users)} new users → total {len(config.user_list)}"
    )
    log.info(
        f"  New: " + ", ".join(f"@{u}" for u in new_users)
    )


def cmd_download(config: AppConfig, config_path: str = "config.json"):
    """Subcommand: download media from configured user_list."""
    if config.list_sync_enabled:
        _auto_list_sync(config, config_path)

    users = [u.strip() for u in config.user_list if u.strip()]
    if not users:
        log.error("No users configured. Add usernames to config.json -> user_list")
        return

    import json as _json
    progress_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'download_progress.json')
    completed_users = set()
    skip_count = 0

    if os.path.exists(progress_file):
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                prog = _json.load(f)
            completed_at = prog.get('completed_at', 0)
            age_hours = (time.time() - completed_at) / 3600 if completed_at else 999
            if age_hours > 12:
                log.info(f"Checkpoint expired ({age_hours:.1f}h old), clearing")
                os.remove(progress_file)
            else:
                completed_users = set(prog.get('completed', []))
                skip_count = len(completed_users)
                log.info(f"Resuming from checkpoint: {skip_count} users already done, {len(users) - skip_count} remaining")
        except Exception:
            log.warning("Failed to read progress file, starting from beginning")

    remaining = [u for u in users if u not in completed_users]
    if not remaining:
        log.info("All users already processed, nothing to do")
        if os.path.exists(progress_file):
            os.remove(progress_file)
        return

    log.info(f"Starting download: {len(remaining)} user(s) remaining (total: {len(users)})")
    downloader = UserMediaDownloader(config)

    stats = {"users": skip_count, "failed": 0, "skipped": 0, "images": 0, "videos": 0, "total": 0}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        for offset, user in enumerate(remaining):
            current = skip_count + offset + 1
            log.info(f"\n{'='*50}")
            log.info(f"Processing ({current}/{len(users)}): @{user}")
            log.info(f"{'='*50}")

            retries = 0
            while retries < config.max_user_retries:
                try:
                    result = downloader.run_user(user)
                    if result["ok"]:
                        stats["users"] += 1
                        stats["images"] += result["images"]
                        stats["videos"] += result["videos"]
                        stats["total"] += result["total"]
                        completed_users.add(user)
                        with open(progress_file, 'w', encoding='utf-8') as f:
                            _json.dump({
                                'completed': sorted(completed_users),
                                'completed_at': time.time(),
                                'total': len(users),
                            }, f, ensure_ascii=False)
                    else:
                        stats["failed"] += 1
                    break
                except Exception as e:
                    retries += 1
                    log.warning(
                        f"User @{user} attempt {retries}/{config.max_user_retries} failed: {e}"
                    )
                    time.sleep(config.retry_delay)
            else:
                stats["skipped"] += 1
                log.error(f"User @{user} skipped after {config.max_user_retries} retries")
    finally:
        loop.close()

    if stats["users"] >= len(users):
        if os.path.exists(progress_file):
            os.remove(progress_file)
            log.info("All users complete, checkpoint cleared")

    log.info("=" * 50)
    log.info(" DOWNLOAD COMPLETE")
    log.info("=" * 50)
    log.info(f"  Users processed:  {stats['users']}")
    log.info(f"  Users failed:     {stats['failed']}")
    log.info(f"  Users skipped:    {stats['skipped']}")
    log.info(f"  Images downloaded:{stats['images']}")
    log.info(f"  Videos downloaded:{stats['videos']}")
    log.info(f"  Total new media:  {stats['total']}")
    log.info("=" * 50)


def cmd_tag(config: AppConfig):
    """Subcommand: search and download by tag/keyword."""
    import json
    import httpx
    from src.utils import (
        sanitize_tag_name, timestamp_to_str, encode_url, encode_query, md5_short
    )
    from src.client import create_http_client

    tag = config.tag_search_tag
    search_filter = ' ' + config.tag_search_filter if config.tag_search_filter else ''

    if config.tag_search_text_mode:
        entries_count = 20
        product = 'Latest'
    elif config.tag_search_media_latest:
        entries_count = 20
        product = 'Latest'
    else:
        entries_count = 50
        product = 'Media'

    if tag:
        folder_name = sanitize_tag_name(tag)
    else:
        folder_name = sanitize_tag_name(config.tag_search_filter)

    folder_path = os.path.join(os.getcwd(), folder_name) + os.sep
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    client = create_http_client(
        config,
        referer=f'https://twitter.com/search?q={encode_query(tag + search_filter)}&src=typed_query&f=media'
    )

    total_pages = config.tag_search_count // entries_count

    log.info(f"Tag search: '{tag}' | Filter: '{config.tag_search_filter}'")
    log.info(f"Mode: {'Text' if config.tag_search_text_mode else 'Media'} | Pages: {total_pages}")

    semaphore = asyncio.Semaphore(config.max_concurrent)
    cursor = ""

    async def download_media_batch(media_lst):
        async def save_one(item):
            url, csv_info, is_image = item
            if is_image:
                url += '?format=png&name=4096x4096'
            for attempt in range(5):
                try:
                    async with semaphore:
                        async with httpx.AsyncClient(proxy=config.proxy, verify=True) as cl:
                            resp = await cl.get(encode_url(url), timeout=(3.05, 16))
                    with open(csv_info[6], 'wb') as f:
                        f.write(resp.content)
                    return
                except Exception as e:
                    if attempt == 4:
                        log.error(f"Failed to download: {csv_info[6]}")
                    else:
                        log.debug(f"Retry {attempt + 1}: {os.path.basename(csv_info[6])}")

        await asyncio.gather(*[save_one(m) for m in media_lst])

    def get_highest_video(variants):
        if len(variants) == 1:
            return variants[0]['url']
        max_br = 0
        best = None
        for v in variants:
            if 'bitrate' in v and int(v['bitrate']) > max_br:
                max_br = int(v['bitrate'])
                best = v['url']
        return best

    async def process_page(page_idx):
        nonlocal cursor
        query = encode_query(tag + search_filter)
        url = (
            f'https://twitter.com/i/api/graphql/tUJgNbJvuiieOXvq7OmHwA/SearchTimeline'
            f'?variables={{"rawQuery":"{query}","count":{entries_count},'
            f'"cursor":"{cursor}","querySource":"typed_query","product":"{product}"}}'
            f'&features={{"rweb_tipjar_consumption_enabled":true,'
            f'"responsive_web_graphql_exclude_directive_enabled":true,'
            f'"verified_phone_label_enabled":false,'
            f'"creator_subscriptions_tweet_preview_api_enabled":true,'
            f'"responsive_web_graphql_timeline_navigation_enabled":true,'
            f'"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
            f'"communities_web_enable_tweet_community_results_fetch":true,'
            f'"c9s_tweet_anatomy_moderator_badge_enabled":true,'
            f'"articles_preview_enabled":true,'
            f'"tweetypie_unmention_optimization_enabled":true,'
            f'"responsive_web_edit_tweet_api_enabled":true,'
            f'"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,'
            f'"view_counts_everywhere_api_enabled":true,'
            f'"longform_notetweets_consumption_enabled":true,'
            f'"responsive_web_twitter_article_tweet_consumption_enabled":true,'
            f'"tweet_awards_web_tipping_enabled":false,'
            f'"freedom_of_speech_not_reach_fetch_enabled":true,'
            f'"standardized_nudges_misinfo":true,'
            f'"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,'
            f'"longform_notetweets_rich_text_read_enabled":true,'
            f'"longform_notetweets_inline_media_enabled":true,'
            f'"responsive_web_enhance_cards_enabled":false}}'
        )
        url = encode_url(url)

        resp = client.get(url)
        try:
            data = resp.json()
        except json.JSONDecodeError:
            if 'Rate limit exceeded' in resp.text:
                log.error("API rate limit exceeded")
                return False
            log.error(f"Failed to parse page {page_idx}")
            return False

        try:
            timeline = data['data']['search_by_raw_query']['search_timeline']['timeline']
            instructions = timeline['instructions']
        except KeyError:
            log.error(f"Invalid API response on page {page_idx}")
            return False

        if not cursor:
            entries = instructions[-1].get('entries', [])
            if len(entries) <= 2:
                return False
            cursor = entries[-1]['content']['value']
            if config.tag_search_media_latest or config.tag_search_text_mode:
                raw_items = entries[:-2]
            else:
                raw_items = entries[0]['content']['items']
        else:
            if len(instructions) < 2:
                return False
            cursor = instructions[-1].get('entry', {}).get('content', {}).get('value', '')
            if config.tag_search_media_latest or config.tag_search_text_mode:
                if 'entries' in instructions[0]:
                    raw_items = instructions[0]['entries']
                else:
                    return False
            else:
                if 'moduleItems' in instructions[0]:
                    raw_items = instructions[0]['moduleItems']
                else:
                    return False

        if config.tag_search_text_mode:
            for tweet_entry in raw_items:
                if 'promoted' in tweet_entry.get('entryId', ''):
                    continue
                tweet = tweet_entry['content']['itemContent']['tweet_results']['result']
                if 'tweet' in tweet and 'edit_control' in tweet['tweet']:
                    tweet = tweet['tweet']
                try:
                    ts = int(tweet['edit_control']['editable_until_msecs']) - 3600000
                except (KeyError, TypeError):
                    try:
                        ts = int(tweet['edit_control']['edit_control_initial']['editable_until_msecs']) - 3600000
                    except (KeyError, TypeError):
                        continue
                try:
                    dn = tweet['core']['user_results']['result']['legacy']['name']
                    sn = '@' + tweet['core']['user_results']['result']['legacy']['screen_name']
                except (KeyError, TypeError):
                    continue
                try:
                    fav = tweet['legacy']['favorite_count']
                    rt = tweet['legacy']['retweet_count']
                    rp = tweet['legacy']['reply_count']
                    sid = tweet['legacy']['conversation_id_str']
                    tw_url = f'https://twitter.com/{sn}/status/{sid}'
                    content = tweet['legacy']['full_text'].split('https://t.co/')[0]
                except (KeyError, TypeError):
                    continue
                print(f"[{timestamp_to_str(ts)}] {dn}({sn}): {content[:100]}")
            return True

        if config.tag_search_media_latest:
            source_entries = raw_items
            extract_key = 'content'
        else:
            source_entries = raw_items
            extract_key = None

        media_lst = []
        for entry in source_entries:
            if extract_key == 'content':
                if 'promoted' in entry.get('entryId', ''):
                    continue
                tweet = entry['content']['itemContent']['tweet_results']['result']
            else:
                tweet = entry['item']['itemContent']['tweet_results']['result']

            try:
                dn = tweet['core']['user_results']['result']['legacy']['name']
                sn = '@' + tweet['core']['user_results']['result']['legacy']['screen_name']
            except (KeyError, TypeError):
                continue

            try:
                ts = int(tweet['edit_control']['editable_until_msecs']) - 3600000
            except (KeyError, TypeError):
                try:
                    ts = int(tweet['edit_control']['edit_control_initial']['editable_until_msecs']) - 3600000
                except (KeyError, TypeError):
                    continue

            try:
                fav = tweet['legacy']['favorite_count']
                rt = tweet['legacy']['retweet_count']
                rp = tweet['legacy']['reply_count']
                sid = tweet['legacy']['conversation_id_str']
                tw_url = f'https://twitter.com/{sn}/status/{sid}'
                content = tweet['legacy']['full_text'].split('https://t.co/')[0]
            except (KeyError, TypeError):
                continue

            try:
                raw_media = tweet['legacy']['extended_entities']['media']
            except KeyError:
                continue

            for med in raw_media:
                if 'video_info' in med:
                    m_url = get_highest_video(med['video_info']['variants'])
                    m_type = 'Video'
                    is_img = False
                    fname = f'{folder_path}{timestamp_to_str(ts)}_{sn}_{md5_short(m_url)}.mp4'
                else:
                    m_url = med['media_url_https']
                    m_type = 'Image'
                    is_img = True
                    fname = f'{folder_path}{timestamp_to_str(ts)}_{sn}_{md5_short(m_url)}.png'

                csv_info = [ts, dn, sn, tw_url, m_type, m_url, fname, content, fav, rt, rp]
                media_lst.append([m_url, csv_info, is_img])

        if media_lst:
            await download_media_batch(media_lst)
            log.info(f"Page {page_idx}: downloaded {len(media_lst)} items")

        return True

    for page_idx in range(1, total_pages + 1):
        log.info(f"Processing page {page_idx}/{total_pages}...")
        try:
            should_continue = asyncio.run(process_page(page_idx))
            if not should_continue or should_continue is False:
                break
        except Exception as e:
            log.error(f"Error on page {page_idx}: {e}")
            break
        time.sleep(1)

    client.close()
    log.info("Tag search completed")


def cmd_text(config: AppConfig):
    """Subcommand: download text-only tweets from users."""
    import csv
    import re
    from src.utils import (
        sanitize_filename, str_to_timestamp, timestamp_to_readable,
        encode_url, encode_query
    )
    from src.client import create_http_client
    from src.merge import find_existing_folder

    users = [u.strip() for u in config.text_user_list if u.strip()]
    if not users:
        log.error("No users for text download. Set text_download.user_list in config.json")
        return

    log.info(f"Text download for {len(users)} user(s)")

    start_ts, end_ts = config.start_time_stamp, config.end_time_stamp
    log.info(f"Time range: {config.time_range}")

    for user in users:
        log.info(f"\nProcessing @{user}...")

        client = create_http_client(config)

        try:
            info_url = (
                'https://twitter.com/i/api/graphql/xc8f1g7BYqr6VTzTbvNlGw/UserByScreenName'
                '?variables={"screen_name":"' + user + '","withSafetyModeUserFields":false}'
                '&features={"hidden_profile_likes_enabled":false,'
                '"hidden_profile_subscriptions_enabled":false,'
                '"responsive_web_graphql_exclude_directive_enabled":true,'
                '"verified_phone_label_enabled":false,'
                '"subscriptions_verification_info_verified_since_enabled":true,'
                '"highlights_tweets_tab_ui_enabled":true,'
                '"creator_subscriptions_tweet_preview_api_enabled":true,'
                '"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,'
                '"responsive_web_graphql_timeline_navigation_enabled":true}'
                '&fieldToggles={"withAuxiliaryUserLabels":false}'
            )
            resp = client.get(encode_url(info_url))
            user_data = resp.json()['data']['user']['result']
            user_id = user_data['rest_id']
            user_name = user_data['legacy']['name']

            safe_name = sanitize_filename(user_name)
            safe_sn = sanitize_filename(user)
            user_dir = os.path.join(config.save_path, f"{safe_name}@{safe_sn}")

            existing_path = find_existing_folder(config.save_path, user)
            if existing_path and existing_path != user_dir:
                log.info(f"检测到已有文件夹，复用: {os.path.basename(existing_path)}")
                user_dir = existing_path
            else:
                os.makedirs(user_dir, exist_ok=True)

            all_tweets = []
            cursor = ""
            tweet_count = 0
            page = 0

            while True:
                if config.text_max_tweets > 0 and tweet_count >= config.text_max_tweets:
                    log.info(f"Reached max tweets limit ({config.text_max_tweets})")
                    break

                page += 1
                log.info(f"Fetching page {page}...")

                tweet_count = 20
                cursor_part = ('"cursor":"' + encode_query(cursor) + '",' if cursor else '')
                tweets_url = (
                    'https://twitter.com/i/api/graphql/9zyyd1hebl7oNWIPdA8HRw/UserTweets'
                    '?variables={"userId":"' + user_id + '","count":' + str(tweet_count) + ',' + cursor_part
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

                retries = 0
                while retries < config.text_max_retries:
                    try:
                        resp = client.get(encode_url(tweets_url))
                        if resp.status_code == 429:
                            retries += 1
                            wait = retries * 10
                            log.warning(f"TT: rate limited, waiting {wait}s...")
                            time.sleep(wait)
                            continue
                        if resp.status_code >= 400:
                            retries += 1
                            log.warning(f"TT: HTTP {resp.status_code}, retry {retries}/{config.text_max_retries}")
                            time.sleep(3)
                            continue
                        data = resp.json()
                        break
                    except Exception:
                        retries += 1
                        if retries >= config.text_max_retries:
                            log.error("Max retries reached for API request")
                            data = None
                            break
                        time.sleep(2)

                if data is None:
                    break

                timeline = data.get('data', {}).get('user', {}).get('result', {}).get('timeline_v2', {})
                timeline_inner = timeline.get('timeline', {})
                instructions = timeline_inner.get('instructions', [])

                next_cursor = ""
                page_tweets = []

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
                            if 'tweet' in result:
                                td = result['tweet']
                            else:
                                td = result

                            legacy = td['legacy']
                            edit_ctrl = td.get('edit_control', {})
                            edit_until = edit_ctrl.get('editable_until_msecs')
                            if not edit_until:
                                edit_until = edit_ctrl.get('edit_control_initial', {}).get('editable_until_msecs', 0)

                            ts = int(edit_until) - 3600000 if edit_until else 0

                            core = td.get('core', {}).get('user_results', {}).get('result', {})
                            ul = core.get('legacy', {})
                            dn = ul.get('name', 'Unknown')
                            sn = '@' + ul.get('screen_name', 'unknown')

                            if start_ts <= ts <= end_ts:
                                page_tweets.append({
                                    'timestamp': ts,
                                    'display_name': dn,
                                    'screen_name': sn,
                                    'tweet_url': f"https://twitter.com/{ul.get('screen_name', '')}/status/{legacy.get('id_str', '')}",
                                    'content': legacy.get('full_text', ''),
                                    'favorites': legacy.get('favorite_count', 0),
                                    'retweets': legacy.get('retweet_count', 0),
                                    'replies': legacy.get('reply_count', 0),
                                })
                        except (KeyError, TypeError, IndexError):
                            continue

                all_tweets.extend(page_tweets)
                tweet_count += len(page_tweets)
                log.info(f"Page {page}: {len(page_tweets)} tweets (total: {tweet_count})")

                if not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor

            if all_tweets:
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                csv_path = os.path.join(user_dir, f"tweets_{ts_str}.csv")
                with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([user_name, f'@{user}'])
                    writer.writerow(['Tweet Range', config.time_range])
                    writer.writerow(['Save Path', user_dir])
                    writer.writerow(['Collected', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                    writer.writerow([])
                    writer.writerow([
                        'Time', 'Display Name', 'Username', 'URL',
                        'Content', 'Likes', 'Retweets', 'Replies'
                    ])
                    for tweet in all_tweets:
                        writer.writerow([
                            timestamp_to_readable(tweet['timestamp']),
                            tweet['display_name'],
                            tweet['screen_name'],
                            tweet['tweet_url'],
                            tweet['content'],
                            tweet['favorites'],
                            tweet['retweets'],
                            tweet['replies'],
                        ])
                log.info(f"Saved {len(all_tweets)} tweets to {csv_path}")
            else:
                log.warning(f"No tweets found for @{user} in time range")

        except Exception as e:
            log.error(f"Error processing @{user}: {e}")
        finally:
            client.close()

    log.info("Text download completed")


def cmd_list_sync(config: AppConfig, owner: str, slug: str, list_id: str = "", config_path: str = "config.json"):
    import time as time_module
    client = create_http_client(config)
    api = TwitterAPI(config, client)
    max_retries = 5
    for attempt in range(max_retries):
        try:
            if list_id:
                members = api.fetch_list_members_by_id(list_id)
            else:
                members = api.fetch_list_members(owner, slug)
            break
        except ListNotFoundError:
            if list_id:
                log.error(f"List {list_id} not found or not accessible.")
            else:
                log.error(
                    f"List '{slug}' not found for @{owner}. "
                    f"Please check the owner screen name and list slug are correct."
                )
            client.close()
            sys.exit(1)
        except RateLimitError:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 30
                log.info(f"Rate limited, waiting {wait}s before retry {attempt + 2}/{max_retries}...")
                time_module.sleep(wait)
            else:
                log.error("Rate limited by Twitter after max retries. Please try again later.")
                client.close()
                sys.exit(1)
        except TwitterAPIError as e:
            if attempt < max_retries - 1:
                wait = 10 * (attempt + 1)
                log.warning(f"API error ({e}), retrying in {wait}s...")
                time_module.sleep(wait)
            else:
                log.error(f"API error after max retries: {e}")
                client.close()
                sys.exit(1)
    else:
        client.close()
        return

    client.close()

    if not members:
        if list_id:
            log.warning(f"No members found in list {list_id}")
        else:
            log.warning(f"No members found in list '{slug}' (@{owner})")
        return

    existing = set(config.user_list)
    new_users = [m for m in members if m not in existing]
    existing_in_list = [m for m in members if m in existing]

    if existing_in_list:
        log.info(
            f"{len(existing_in_list)} user(s) already in download list: "
            + ', '.join(f'@{u}' for u in existing_in_list)
        )

    if not new_users:
        log.info("No new users to add — all list members already in download list.")
        return

    updated_list = config.user_list + new_users
    save_user_list(config_path, updated_list)

    log.info(
        f"Added {len(new_users)} new user(s) to download list:\n  "
        + '\n  '.join(f'@{u}' for u in new_users)
    )
    log.info(f"Total users in list: {len(updated_list)}")


def main():
    parser = argparse.ArgumentParser(
        description="Twitter (X) Media & Text Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m xdownloader_app.main download
    python -m xdownloader_app.main download -u user1,user2
    python -m xdownloader_app.main tag
    python -m xdownloader_app.main text
    python -m xdownloader_app.main list-sync --list-id 1234567890
        """
    )
    parser.add_argument(
        'command',
        choices=['download', 'tag', 'text', 'merge', 'merge-list',
                 'cleanup', 'cleanup-preview', 'list-sync'],
        help='Operation mode'
    )
    parser.add_argument(
        '-c', '--config',
        default='config.json',
        help='Path to config file (default: config.json)'
    )
    parser.add_argument(
        '-u', '--users',
        help='Comma-separated user list (overrides config.json)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--list-owner',
        help='Twitter screen name of the list owner (for list-sync)'
    )
    parser.add_argument(
        '--list-slug',
        default='',
        help='List slug/name when syncing by owner and slug'
    )
    parser.add_argument(
        '--list-id',
        help='Twitter list ID (for list-sync; overrides --list-owner/--list-slug)'
    )
    parser.add_argument(
        '--no-sync',
        action='store_true',
        help='Skip auto list-sync before download'
    )

    args = parser.parse_args()

    config = load_config(args.config)

    if args.verbose:
        config.verbose = True
    Logger.setup(log_file=config.log_file or None, verbose=config.verbose)

    if args.users:
        config.user_list = [u.strip() for u in args.users.split(',') if u.strip()]

    if args.no_sync:
        config.list_sync_enabled = False

    log.info(f"Twitter Downloader starting in '{args.command}' mode")
    log.info(f"Save path: {config.save_path}")
    log.info(f"Proxy: {config.proxy or 'None'}")

    if args.command == 'download':
        cmd_download(config, args.config)
    elif args.command == 'tag':
        cmd_tag(config)
    elif args.command == 'text':
        cmd_text(config)
    elif args.command == 'merge':
        merge_user_folders(config.save_path, screen_name=args.users or "")
    elif args.command == 'merge-list':
        list_duplicates(config.save_path, screen_name=args.users or "")
    elif args.command == 'cleanup':
        cleanup_duplicates(config.save_path, dry_run=False,
                           screen_name=args.users or "")
    elif args.command == 'cleanup-preview':
        preview_duplicates(config.save_path, screen_name=args.users or "")
    elif args.command == 'list-sync':
        if args.list_id:
            cmd_list_sync(config, "", "", list_id=args.list_id, config_path=args.config)
        elif not args.list_owner:
            log.error(
                "--list-owner or --list-id is required for list-sync.\n"
                "Examples:\n"
                "  python -m xdownloader_app.main list-sync --list-owner YourScreenName --list-slug YourList\n"
                "  python -m xdownloader_app.main list-sync --list-id 1234567890"
            )
            sys.exit(1)
        else:
            cmd_list_sync(config, args.list_owner, args.list_slug, config_path=args.config)


if __name__ == '__main__':
    main()

