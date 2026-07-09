from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import AppConfig
from .models import MediaItem, UserInfo
from .utils import encode_url, timestamp_to_str, time_in_range, parse_twitter_created_at
from .logger import log
import asyncio
import time


class TwitterAPIError(Exception):
    pass


class RateLimitError(TwitterAPIError):
    pass


class ListNotFoundError(TwitterAPIError):
    pass


class TwitterAPI:
    def __init__(self, config: AppConfig, client: httpx.Client = None, debug_logger=None):
        self.config = config
        self.client = client
        self._async_client = None
        self._debug_logger = debug_logger

    HTTP_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}

    def _get(self, url: str) -> str:
        last_error = None
        for attempt in range(3):
            try:
                response = self.client.get(encode_url(url))
                if response.status_code == 429:
                    wait = (attempt + 1) * 15
                    log.warning(f"Rate limited (attempt {attempt + 1}/3), waiting {wait}s...")
                    time.sleep(wait)
                    last_error = RateLimitError("API rate limited (429)")
                    continue
                if response.status_code in {500, 502, 503, 504}:
                    wait = 5 * (attempt + 1)
                    log.warning(f"Server error {response.status_code} (attempt {attempt + 1}/3), waiting {wait}s...")
                    time.sleep(wait)
                    last_error = TwitterAPIError(f"HTTP {response.status_code}")
                    continue
                if response.status_code == 404:
                    raise ListNotFoundError(f"API endpoint returned 404: {url[:120]}")
                if response.status_code >= 400:
                    raise TwitterAPIError(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                return response.text
            except ListNotFoundError:
                raise
            except TwitterAPIError:
                raise
            except RateLimitError:
                raise
            except httpx.TimeoutException as e:
                last_error = e
                wait = 5 * (attempt + 1)
                log.warning(f"Timeout (attempt {attempt + 1}/3), waiting {wait}s...")
                time.sleep(wait)
            except (httpx.NetworkError, httpx.RemoteProtocolError) as e:
                last_error = e
                wait = 5 * (attempt + 1)
                log.warning(f"Network error [{type(e).__name__}] (attempt {attempt + 1}/3), waiting {wait}s...")
                time.sleep(wait)
            except Exception as e:
                last_error = e
                wait = 5 * (attempt + 1)
                log.warning(f"Unexpected error [{type(e).__name__}] (attempt {attempt + 1}/3), waiting {wait}s...")
                time.sleep(wait)
        raise TwitterAPIError(f"HTTP request failed after 3 retries: {last_error}") from last_error

    def _ensure_async_client(self):
        if self._async_client is None:
            from .client import create_async_client
            self._async_client = create_async_client(
                self.config,
                referer="https://twitter.com/",
                timeout=15.0
            )
        return self._async_client

    async def _get_async(self, url: str) -> str:
        client = self._ensure_async_client()
        last_error = None
        for attempt in range(3):
            try:
                response = await client.get(encode_url(url))
                if response.status_code == 429:
                    wait = (attempt + 1) * 15
                    log.warning(f"Rate limited (attempt {attempt + 1}/3), waiting {wait}s...")
                    await asyncio.sleep(wait)
                    last_error = RateLimitError("API rate limited (429)")
                    continue
                if response.status_code in {500, 502, 503, 504}:
                    wait = 5 * (attempt + 1)
                    log.warning(f"Server error {response.status_code} (attempt {attempt + 1}/3), waiting {wait}s...")
                    await asyncio.sleep(wait)
                    last_error = TwitterAPIError(f"HTTP {response.status_code}")
                    continue
                if response.status_code == 404:
                    raise ListNotFoundError(f"API endpoint returned 404: {url[:120]}")
                if response.status_code >= 400:
                    raise TwitterAPIError(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                return response.text
            except ListNotFoundError:
                raise
            except TwitterAPIError:
                raise
            except RateLimitError:
                raise
            except httpx.TimeoutException as e:
                last_error = e
                wait = 5 * (attempt + 1)
                log.warning(f"Timeout (attempt {attempt + 1}/3), waiting {wait}s...")
                await asyncio.sleep(wait)
            except (httpx.NetworkError, httpx.RemoteProtocolError) as e:
                last_error = e
                wait = 5 * (attempt + 1)
                log.warning(f"Network error [{type(e).__name__}] (attempt {attempt + 1}/3), waiting {wait}s...")
                await asyncio.sleep(wait)
            except Exception as e:
                last_error = e
                wait = 5 * (attempt + 1)
                log.warning(f"Unexpected error [{type(e).__name__}] (attempt {attempt + 1}/3), waiting {wait}s...")
                await asyncio.sleep(wait)
        raise TwitterAPIError(f"HTTP request failed after 3 retries: {last_error}") from last_error

    async def close_async(self):
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    async def fetch_user_info(self, screen_name: str) -> Optional[UserInfo]:
        variables = json.dumps({"screen_name": screen_name, "withSafetyModeUserFields": False})
        url = (
            'https://twitter.com/i/api/graphql/xc8f1g7BYqr6VTzTbvNlGw/UserByScreenName'
            '?variables=' + variables +
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
        try:
            response_text = await self._get_async(url)
            data = json.loads(response_text)
            user_result = data['data']['user']['result']
            info = UserInfo(screen_name=screen_name)
            info.rest_id = user_result['rest_id']
            info.name = user_result['legacy']['name']
            info.statuses_count = user_result['legacy']['statuses_count']
            info.media_count = user_result['legacy']['media_count']
            return info
        except KeyError as e:
            log.error(f"Failed to parse user info for {screen_name}: {e}")
            return None
        except json.JSONDecodeError:
            if 'Rate limit exceeded' in response_text:
                raise RateLimitError("API rate limit exceeded")
            log.error(f"Failed to get user info: invalid response")
            return None

    def _features_payload(self) -> str:
        return (
            '"responsive_web_graphql_exclude_directive_enabled":true,'
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
            '"responsive_web_enhance_cards_enabled":false'
        )

    def _build_timeline_url_v2(self, user_info: UserInfo) -> str:
        cfg = self.config
        features = self._features_payload()

        if cfg.has_highlights:
            endpoint = 'w9-i9VNm_92GYFaiyGT1NA/UserHighlightsTweets'
            count = 20
            base_var = f'"userId":"{user_info.rest_id}","count":{count}'
            extra = '"includePromotedContent":true,"withVoice":true'
        elif cfg.has_likes:
            endpoint = '-fbTO1rKPa3nO6-XIRgEFQ/Likes'
            count = 200
            base_var = f'"userId":"{user_info.rest_id}","count":{count}'
            extra = (
                '"includePromotedContent":false,"withClientEventToken":false,'
                '"withBirdwatchNotes":false,"withVoice":true,"withV2Timeline":true'
            )
        elif cfg.has_retweet:
            endpoint = '2GIWTr7XwadIixZDtyXd4A/UserTweets'
            count = 20
            base_var = f'"userId":"{user_info.rest_id}","count":{count}'
            extra = (
                '"includePromotedContent":false,'
                '"withQuickPromoteEligibilityTweetFields":true,'
                '"withVoice":true,"withV2Timeline":true'
            )
            features += ',"rweb_lists_timeline_redesign_enabled":true'
        else:
            endpoint = 'Le6KlbilFmSu-5VltFND-Q/UserMedia'
            count = 500
            base_var = f'"userId":"{user_info.rest_id}","count":{count}'
            extra = (
                '"includePromotedContent":false,"withClientEventToken":false,'
                '"withBirdwatchNotes":false,"withVoice":true,"withV2Timeline":true'
            )

        if user_info.cursor:
            variables = f'{{{base_var},"cursor":"{user_info.cursor}",{extra}}}'
        else:
            variables = f'{{{base_var},{extra}}}'

        return f'https://twitter.com/i/api/graphql/{endpoint}?variables={variables}&features={{{features}}}'

    def _highest_video_quality(self, variants: List[dict]) -> str:
        if not variants:
            return ''
        if len(variants) == 1:
            return variants[0].get('url', '')
        max_bitrate = 0
        best_url = None
        for v in variants:
            if 'bitrate' in v:
                try:
                    br = int(v['bitrate'])
                    if br > max_bitrate:
                        max_bitrate = br
                        best_url = v.get('url') or ''
                except (ValueError, TypeError):
                    pass
        if best_url is None:
            best_url = variants[0].get('url', '')
        return best_url

    @staticmethod
    def _collect_media_from_legacy(legacy: dict) -> List[dict]:
        media_entities = []
        if 'extended_entities' in legacy:
            media_entities.extend(legacy['extended_entities'].get('media', []))
        if 'entities' in legacy:
            for m in legacy['entities'].get('media', []):
                if m not in media_entities:
                    media_entities.append(m)
        if 'note_tweet' in legacy:
            nt = legacy['note_tweet']
            ntr = nt.get('note_tweet_results', {}).get('result', {})
            for m in ntr.get('media', []):
                if m not in media_entities:
                    media_entities.append(m)
        return media_entities

    def _extract_media_from_entities(
        self,
        entities: List[dict],
        timestr: str,
        is_retweet: bool,
        display_name: str,
        screen_name: str,
        tweet_content: str,
        frr: Tuple[int, int, int],
        tweet_msecs: int
    ) -> List[MediaItem]:
        cfg = self.config
        items: List[MediaItem] = []
        retweet_suffix = '-retweet' if is_retweet else ''

        for media in entities:
            media_type = None
            media_url = None

            if 'video_info' in media and cfg.has_video:
                media_url = self._highest_video_quality(media['video_info']['variants'])
                media_type = 'Video'
                prefix = f'{timestr}-vid{retweet_suffix}'
            elif 'media_url_https' in media:
                media_url = media['media_url_https']
                media_type = 'Image'
                prefix = f'{timestr}-img{retweet_suffix}'
            elif 'media_url' in media:
                media_url = media['media_url']
                media_type = 'Image'
                prefix = f'{timestr}-img{retweet_suffix}'

            if media_url and media_type:
                items.append(MediaItem(
                    url=media_url,
                    prefix=prefix,
                    csv_info=[
                        tweet_msecs,
                        display_name,
                        screen_name,
                        media.get('expanded_url', ''),
                        media_type,
                        media_url,
                        '',
                        tweet_content,
                        *frr,
                    ]
                ))

        return items

    async def fetch_timeline_page(
        self,
        user_info: UserInfo,
        ctx: Any
    ) -> Optional[List[MediaItem]]:
        if self._debug_logger:
            self._debug_logger.info(f"fetch_timeline_page() called for @{user_info.screen_name}")
        url = self._build_timeline_url_v2(user_info)
        try:
            response_text = await self._get_async(url)
            data = json.loads(response_text)
        except json.JSONDecodeError:
            log.error("Failed to parse timeline response as JSON")
            if self._debug_logger:
                self._debug_logger.info("fetch_timeline_page FAILED: JSON decode error")
                self._debug_logger.debug(f"Request URL: {url[:200]}...")
                self._debug_logger.debug(f"Response text (first 300 chars): {response_text[:300]}")
            log.debug(f"Request URL: {url[:200]}...")
            log.debug(f"Response text (first 300 chars): {response_text[:300]}")
            return None

        if isinstance(data, dict) and 'data' not in data:
            keys = list(data.keys())[:10]
            log.error(f"Unexpected API response, keys: {keys}")
            if self._debug_logger:
                self._debug_logger.info(f"fetch_timeline_page FAILED: no 'data' key, got: {keys}")
                self._debug_logger.debug(f"Request URL: {url[:200]}...")
                self._debug_logger.debug(f"Response text (first 300 chars): {response_text[:300]}")
            log.debug(f"Request URL: {url[:200]}...")
            log.debug(f"Response text (first 300 chars): {response_text[:300]}")
            return None

        try:
            result = self._parse_timeline(data, user_info, ctx)
            if self._debug_logger:
                count = len(result) if result else 0
                self._debug_logger.info(f"fetch_timeline_page returning {count} items from _parse_timeline")
            return result
        except Exception as e:
            log.error(f"Error parsing timeline: {e}")
            if self._debug_logger:
                self._debug_logger.info(f"fetch_timeline_page FAILED: _parse_timeline exception: {e}")
            return None

    def _parse_timeline(
        self,
        data: dict,
        user_info: UserInfo,
        ctx: Any
    ) -> Optional[List[MediaItem]]:
        cfg = self.config

        if self._debug_logger:
            self._debug_logger.info(f"_parse_timeline() called for @{user_info.screen_name}")

        log.debug(f"API response keys: {list(data.keys())}")
        if self._debug_logger:
            self._debug_logger.debug(f"API response keys: {list(data.keys())}")
        
        try:
            if cfg.has_highlights:
                raw_entries = data['data']['user']['result']['timeline']['timeline']['instructions'][-1]['entries']
            elif cfg.has_retweet or cfg.has_likes:
                raw_entries = data['data']['user']['result']['timeline_v2']['timeline']['instructions'][-1]['entries']
            else:
                raw_entries = data['data']['user']['result']['timeline_v2']['timeline']['instructions']
        except (KeyError, IndexError) as e:
            log.error(f"Invalid API response structure: {e}")
            if self._debug_logger:
                self._debug_logger.debug(f"API response keys: {list(data.keys())}")
                if 'data' in data:
                    self._debug_logger.debug(f"data['data'] keys: {list(data['data'].keys())}")
            log.debug(f"API response keys: {list(data.keys())}")
            if 'data' in data:
                log.debug(f"data['data'] keys: {list(data['data'].keys())}")
            if self._debug_logger:
                self._debug_logger.info("_parse_timeline FAILED: invalid API response structure")
            return None

        log.debug(f"raw_entries type: {type(raw_entries)}, length: {len(raw_entries) if isinstance(raw_entries, (list, tuple)) else 'N/A'}")
        if self._debug_logger:
            self._debug_logger.debug(f"raw_entries type: {type(raw_entries)}, length: {len(raw_entries) if isinstance(raw_entries, (list, tuple)) else 'N/A'}")

        if (cfg.has_retweet or cfg.has_highlights):
            if raw_entries and 'cursor-top' in raw_entries[0].get('entryId', ''):
                return None

        if not cfg.has_retweet and not cfg.has_highlights:
            for entry in raw_entries[-1].get('entries', []):
                if 'bottom' in entry.get('entryId', ''):
                    try:
                        user_info.cursor = entry['content']['value']
                    except (KeyError, TypeError):
                        pass

        if not ctx.start_label:
            if self._debug_logger:
                self._debug_logger.info("_parse_timeline ABORT: start_label is False (time range ended)")
            return None

        media_items: List[MediaItem] = []

        if not cfg.has_retweet and not cfg.has_highlights:
            if ctx.first_page:
                try:
                    entries = raw_entries[-1]['entries'][0]['content']['items']
                    if self._debug_logger:
                        self._debug_logger.debug(f"First page: {len(entries)} items in media timeline")
                    log.debug(f"First page: {len(entries)} items in media timeline")
                except (KeyError, IndexError) as e:
                    log.error(f"Failed to parse first page entries: {e}")
                    if self._debug_logger:
                        self._debug_logger.info(f"_parse_timeline FAILED: cannot parse first page entries: {e}")
                    return None
                ctx.first_page = False
            else:
                if 'moduleItems' not in raw_entries[0]:
                    if self._debug_logger:
                        self._debug_logger.debug("No moduleItems in subsequent page, pagination end")
                    log.debug("No moduleItems in subsequent page, pagination end")
                    return None
                entries = raw_entries[0]['moduleItems']
                if self._debug_logger:
                    self._debug_logger.debug(f"Subsequent page: {len(entries)} moduleItems")
                log.debug(f"Subsequent page: {len(entries)} moduleItems")
        else:
            entries = raw_entries
            if self._debug_logger:
                self._debug_logger.debug(f"Retweet/likes mode: {len(entries)} entries")
            log.debug(f"Retweet/likes mode: {len(entries)} entries")

        for entry in entries:
            try:
                entry_id = entry.get('entryId', '')
                if 'promoted-tweet' in entry_id:
                    continue

                content_key = 'content' if (cfg.has_retweet or cfg.has_highlights) else 'item'

                if 'tweet' in entry_id:
                    content_node = entry.get('content') or entry.get('item') or {}
                    item_content = content_node.get('itemContent', {})
                    tweet_result = item_content.get('tweet_results', {}).get('result', {})

                    if 'tweet' in tweet_result:
                        core_tweet = tweet_result['tweet']
                        legacy = core_tweet['legacy']
                        edit_until = int(core_tweet['edit_control']['editable_until_msecs']) - 3600000
                    else:
                        legacy = tweet_result['legacy']
                        edit_until = int(tweet_result.get('edit_control', {}).get('editable_until_msecs', 0)) - 3600000

                    if edit_until <= 0:
                        edit_until = parse_twitter_created_at(legacy.get('created_at', ''))

                    frr = (
                        legacy.get('favorite_count', 0),
                        legacy.get('retweet_count', 0),
                        legacy.get('reply_count', 0),
                    )

                    if edit_until <= 0:
                        do_download, keep_going = True, True
                    else:
                        do_download, keep_going = time_in_range(
                            edit_until,
                            cfg.time_range[0],
                            cfg.time_range[1]
                        )

                    if not keep_going:
                        ctx.start_label = False
                        break

                    if not do_download:
                        continue

                    timestr = timestamp_to_str(edit_until)

                    media_entities = self._collect_media_from_legacy(legacy)
                    has_extended = 'extended_entities' in legacy
                    has_entities = 'entities' in legacy
                    has_note_tweet = 'note_tweet' in legacy

                    tweet_text_preview = legacy.get('full_text', '')[:50]
                    if media_entities:
                        if self._debug_logger:
                            self._debug_logger.debug(f"Tweet media found: '{tweet_text_preview}...' - {len(media_entities)} items (ext={has_extended}, ent={has_entities}, nt={has_note_tweet})")
                        log.debug(f"Tweet media found: '{tweet_text_preview}...' - {len(media_entities)} items (ext={has_extended}, ent={has_entities}, nt={has_note_tweet})")
                    elif has_extended or has_entities or has_note_tweet:
                        if self._debug_logger:
                            self._debug_logger.debug(f"Tweet has media key but no items: '{tweet_text_preview}...' (ext={has_extended}, ent={has_entities}, nt={has_note_tweet})")
                        log.debug(f"Tweet has media key but no items: '{tweet_text_preview}...' (ext={has_extended}, ent={has_entities}, nt={has_note_tweet})")

                    try:
                        if media_entities and 'retweeted_status_result' not in legacy:
                            items = self._extract_media_from_entities(
                                media_entities,
                                timestr,
                                False,
                                user_info.name,
                                f'@{user_info.screen_name}',
                                legacy.get('full_text', ''),
                                frr,
                                edit_until
                            )
                            media_items.extend(items)

                        elif 'retweeted_status_result' in legacy:
                            rsr = legacy['retweeted_status_result']['result']
                            retweet_legacy = rsr.get('legacy', {})
                            retweet_user = rsr.get('core', {}).get('user_results', {}).get('result', {}).get('legacy', {})

                            r_media = self._collect_media_from_legacy(retweet_legacy)

                            if r_media:
                                items = self._extract_media_from_entities(
                                    r_media,
                                    timestr,
                                    True,
                                    retweet_user.get('name', ''),
                                    f"@{retweet_user.get('screen_name', '')}",
                                    retweet_legacy.get('full_text', ''),
                                    frr,
                                    edit_until
                                )
                                media_items.extend(items)
                    except Exception as e:
                        log.error(f"Tweet media extract error for {entry_id[:40]}: {e}")

                elif 'profile-conversation' in entry_id:
                    content_node = entry.get('content') or entry.get('item') or {}
                    inner_content = content_node
                    items_list = inner_content.get('items', [])
                    if items_list:
                        item_data = items_list[0].get('item', {}).get('itemContent', {}).get('tweet_results', {}).get('result', {})
                        if 'tweet' in item_data:
                            legacy = item_data['tweet']['legacy']
                            edit_until = int(item_data['tweet']['edit_control']['editable_until_msecs']) - 3600000
                        else:
                            legacy = item_data['legacy']
                            edit_until = int(item_data.get('edit_control', {}).get('editable_until_msecs', 0)) - 3600000

                        if edit_until <= 0:
                            edit_until = parse_twitter_created_at(legacy.get('created_at', ''))

                        frr = (
                            legacy.get('favorite_count', 0),
                            legacy.get('retweet_count', 0),
                            legacy.get('reply_count', 0),
                        )

                        if edit_until <= 0:
                            do_download, keep_going = True, True
                        else:
                            do_download, keep_going = time_in_range(
                                edit_until,
                                cfg.time_range[0],
                                cfg.time_range[1]
                            )

                        if not keep_going:
                            ctx.start_label = False
                            break

                        if do_download:
                            pc_media = self._collect_media_from_legacy(legacy)
                            if pc_media:
                                timestr = timestamp_to_str(edit_until)
                                try:
                                    items = self._extract_media_from_entities(
                                        pc_media,
                                    timestr,
                                    False,
                                    user_info.name,
                                    f'@{user_info.screen_name}',
                                    legacy.get('full_text', ''),
                                    frr,
                                    edit_until
                                )
                                    media_items.extend(items)
                                except Exception as e:
                                    log.error(f"Profile-conversation media extract error: {e}")

                if 'cursor-bottom' in entry_id and (cfg.has_retweet or cfg.has_highlights):
                    user_info.cursor = entry['content']['value']

            except (KeyError, IndexError, TypeError) as e:
                log.error(f"Entry parse error [{type(e).__name__}] id='{entry.get('entryId', '?')[:50]}': {e}")
                continue

        if self._debug_logger:
            self._debug_logger.info(f"_parse_timeline() returning {len(media_items) if media_items else 0} items")
        return media_items if media_items else None

    def _list_features_payload(self) -> str:
        return (
            '"responsive_web_graphql_exclude_directive_enabled":true,'
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
            '"responsive_web_enhance_cards_enabled":false,'
            '"rweb_lists_timeline_redesign_enabled":true'
        )

    def _get_list_id(self, owner_screen_name: str, slug: str) -> Optional[str]:
        variables = json.dumps({"screenName": owner_screen_name, "listSlug": slug})
        features = '{' + self._list_features_payload() + '}'
        url = (
            'https://twitter.com/i/api/graphql/K6wihoTiTrzNzSF8y1aeKQ/ListBySlug'
            '?variables=' + variables + '&features=' + features
        )
        try:
            response_text = self._get(url)
            data = json.loads(response_text)
            list_data = data['data']['list']
            return list_data.get('rest_id') or list_data.get('id_str')
        except KeyError:
            log.error(f"List '{slug}' not found for user @{owner_screen_name}")
            raise ListNotFoundError(f"List '{slug}' not found for @{owner_screen_name}")
        except json.JSONDecodeError:
            if 'Rate limit exceeded' in response_text:
                raise RateLimitError("API rate limit exceeded")
            log.error("Failed to get list info: invalid response")
            return None

    def fetch_list_members(
        self,
        owner_screen_name: str,
        slug: str
    ) -> List[str]:
        list_id = self._get_list_id(owner_screen_name, slug)
        if not list_id:
            return []
        return self._fetch_list_members_paginated(list_id, slug, owner_screen_name)

    def fetch_list_members_by_id(self, list_id: str) -> List[str]:
        return self._fetch_list_members_paginated(list_id, "", "")

    def _fetch_list_members_paginated(
        self, list_id: str, slug: str, owner: str
    ) -> List[str]:

        members: List[str] = []
        seen_members = set()
        cursor = ""
        seen_cursors = set()
        page_count = 0
        max_pages = 100
        features = self._list_features_payload()

        while True:
            page_count += 1
            if page_count > max_pages:
                log.warning(f"Stopping list member pagination after {max_pages} pages")
                break
            if cursor:
                variables = json.dumps({"listId": list_id, "count": 400, "cursor": cursor})
            else:
                variables = json.dumps({"listId": list_id, "count": 400})

            url = (
                'https://twitter.com/i/api/graphql/fuVHh5-gFn8zDBBxb8wOMA/ListMembers'
                '?variables=' + variables +
                '&features={' + features + '}'
            )

            try:
                response_text = self._get(url)
                data = json.loads(response_text)
            except TwitterAPIError as e:
                log.warning(f"List members page failed: {e}")
                if members:
                    log.info(f"Returning {len(members)} members collected so far")
                    break
                raise
            except json.JSONDecodeError:
                if 'Rate limit exceeded' in response_text:
                    raise RateLimitError("API rate limit exceeded")
                log.error("Failed to parse list members response")
                break

            try:
                instructions = (
                    data['data']['list']['members_timeline']
                    ['timeline']['instructions']
                )
            except KeyError:
                log.error("Unexpected list members response structure")
                break

            next_cursor = ""
            for instr in instructions:
                if instr.get('type') != 'TimelineAddEntries':
                    continue
                for entry in instr.get('entries', []):
                    entry_id = entry.get('entryId', '')
                    if 'cursor-bottom' in entry_id:
                        next_cursor = entry.get('content', {}).get('value', '')
                        continue
                    if 'user-' in entry_id or 'list-member-' in entry_id:
                        try:
                            user_result = (
                                entry['content']['itemContent']
                                ['user_results']['result']
                            )
                            screen_name = (
                                user_result.get('legacy', {}).get('screen_name')
                                or user_result.get('core', {}).get('screen_name', '')
                            )
                            if screen_name and screen_name not in seen_members:
                                members.append(screen_name)
                                seen_members.add(screen_name)
                        except (KeyError, TypeError):
                            continue

            if not next_cursor:
                break
            if next_cursor == cursor or next_cursor in seen_cursors:
                log.warning("Stopping list member pagination: repeated cursor")
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        if slug or owner:
            log.info(
                f"Fetched {len(members)} members from list '{slug}' "
                f"(@{owner})"
            )
        else:
            log.info(f"Fetched {len(members)} members from list {list_id}")
        return members
