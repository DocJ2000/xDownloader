import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "xdownloader_app"


class IndexUiTest(unittest.TestCase):
    def setUp(self):
        self.html = (APP_DIR / "index.html").read_text(encoding="utf-8")

    def test_sidebar_tabs_default_to_english_labels(self):
        expected = {
            "home": "Home",
            "browse": "Browse",
            "timeline": "Timeline",
            "media": "Media",
            "download": "Download",
            "settings": "Settings",
        }
        for tab, label in expected.items():
            pattern = (
                r'<div class="nav-icon[^"]*" data-tab="' + re.escape(tab) +
                r'"[^>]*>\s*<span class="nav-label">' + re.escape(label) + r"</span>"
            )
            self.assertRegex(self.html, pattern)

    def test_chinese_language_pack_is_available(self):
        for label in ["首页", "浏览", "时间线", "媒体库", "下载", "设置"]:
            self.assertIn(label, self.html)

    def test_language_toggle_sits_above_settings_tab(self):
        self.assertIn('id="languageToggle"', self.html)
        self.assertRegex(
            self.html,
            r'id="languageToggle"[\s\S]+data-tab="settings"',
        )
        self.assertIn("toggleLanguage()", self.html)
        self.assertIn("localStorage.getItem('xdl.language') || 'en'", self.html)

    def test_settings_save_path_has_directory_picker(self):
        self.assertIn("pickSavePath()", self.html)
        self.assertIn("/api/dialog/directory", self.html)
        self.assertIn("cfg_save_path", self.html)
        self.assertIn("browseFolder", self.html)

    def test_settings_keeps_account_storage_and_download_configuration(self):
        for control_id in [
            "cfg_cookie",
            "cfg_bearer_token",
            "cfg_save_path",
            "cfg_proxy",
            "cfg_time_start",
            "cfg_time_end",
            "cfg_image_format",
            "cfg_has_video",
            "cfg_has_text",
            "cfg_has_retweet",
            "cfg_has_highlights",
            "cfg_has_likes",
            "cfg_max_concurrent",
            "cfg_enable_cache",
            "cfg_async_enabled",
            "cfg_download_auto_sync",
            "cfg_verbose",
            "cfg_log_file",
            "cfg_theme",
        ]:
            self.assertIn(control_id, self.html)
        self.assertIn("buildSettingsTimeRange()", self.html)
        self.assertIn("setSettingsTimeRangeControls", self.html)

    def test_settings_use_apply_language(self):
        self.assertIn("applyConfig", self.html)
        self.assertIn("Applied", self.html)
        self.assertIn("应用", self.html)

    def test_settings_has_no_loss_update_controls(self):
        settings_block = self.html.split("async function initSettings()", 1)[1]
        for expected in [
            "softwareUpdate",
            "btnCheckUpdate",
            "updateStatus",
            "sourceUpdateHelp",
            "btnOpenRelease",
            "checkForUpdates()",
            "downloadLatestInstaller()",
            "openLatestRelease()",
            "openDownloadedInstaller()",
            "/api/update/check",
            "/api/update/download",
            "/api/update/open",
        ]:
            self.assertIn(expected, settings_block)

    def test_settings_layout_uses_full_width_columns(self):
        for expected in [
            "settings-layout { padding: 18px; overflow-y: auto; max-width: none;",
            "settings-column",
            "settings-advanced",
            "grid-template-columns: minmax(320px, 1fr) minmax(320px, 1fr) minmax(280px, 0.9fr)",
        ]:
            self.assertIn(expected, self.html)

    def test_download_tab_is_only_list_and_live_download_workflow(self):
        download_block = self.html.split("function initDownloadTab()", 1)[1].split("function normalizeUsers", 1)[0]
        for expected in [
            "download-list-panel",
            "download-live-panel",
            "dl_user_bulk_add",
            "dl_user_table",
            "dl_list_items",
            "syncAllLists",
            "downloadUserList",
            "dedupeUsers",
            "pruneUnavailableUsers",
            "btnStartDl",
            "btnPauseDl",
            "btnTerminateDl",
            "dlProgress",
            "dlLog",
        ]:
            self.assertIn(expected, download_block)
        self.assertIn("confirm(", self.html)
        self.assertIn("/api/users/prune", self.html)

        for removed_control in [
            'id="dl_time_start"',
            'id="dl_time_end"',
            'id="dl_image_format"',
            'id="dl_has_video"',
            'id="dl_has_retweet"',
            'id="dl_has_highlights"',
            'id="dl_has_likes"',
            'id="dl_enable_cache"',
            'id="dl_async_enabled"',
            'id="dl_download_auto_sync"',
            'id="dl_tag_search_tag"',
            'id="dl_text_user_list"',
            "tagSearch",
            "textDownload",
            "filterUsers",
        ]:
            self.assertNotIn(removed_control, download_block)

    def test_download_control_supports_pause_resume_and_terminate(self):
        for expected in [
            "pauseDownload()",
            "terminateDownload()",
            "/api/download/pause",
            "/api/download/terminate",
            "continueDownload",
            "terminateDownload",
        ]:
            self.assertIn(expected, self.html)

    def test_download_control_supports_auto_shutdown_after_completion(self):
        for expected in [
            "dl_auto_shutdown",
            "autoShutdownAfterDownload",
            "autoShutdownHint",
            "shutdownScheduled",
            "downloadFailed",
            "auto_shutdown",
            "shutdown_scheduled",
            "s.failed || s.state === 'failed'",
        ]:
            self.assertIn(expected, self.html)

    def test_download_page_shows_recent_download_history(self):
        for expected in [
            "recentDownloads",
            "dlHistory",
            "renderDownloadHistory",
            "s.history",
            "historyNewMedia",
            "historyNewTweets",
            "historyNewSize",
            "historyFinishedAt",
            "historyDuration",
            "item.duration",
        ]:
            self.assertIn(expected, self.html)

    def test_user_list_manager_supports_reviewing_large_lists(self):
        for expected in [
            "dl_user_bulk_add",
            "dl_user_table",
            "normalizeUsers",
            "renderUserListManager",
            "dedupeUsers",
            "downloadUserList",
            "pruneUnavailableUsers",
        ]:
            self.assertIn(expected, self.html)

    def test_multiple_list_sync_controls_exist(self):
        for expected in [
            "listSyncItems",
            "renderListSyncItems",
            "addListSyncItem",
            "completeListSyncItem",
            "deleteSelectedListSyncItems",
            "syncAllLists",
            "dl_list_items",
            "addListSyncItem()",
            "listSyncHelp",
        ]:
            self.assertIn(expected, self.html)

    def test_list_sync_uses_table_rows_with_draft_completion(self):
        for expected in [
            "list-sync-table",
            "list-sync-head",
            "list-sync-row-grid",
            "data-list-select",
            "completeListSyncItem",
            "syncSelectedOrAllLists",
            "deleteSelectedListSyncItems",
            "deleteConfirmKeyword",
            "parseListReference",
            "btnAddList",
            'data-list-field="list_url"',
        ]:
            self.assertIn(expected, self.html)
        sync_block = self.html.split("function initDownloadTab()", 1)[1].split("download-users-module", 1)[0]
        self.assertNotIn("dl_list_bulk_import", sync_block)
        self.assertNotIn("data-list-field=\"list_owner\"", sync_block)
        self.assertNotIn("data-list-field=\"list_slug\"", sync_block)
        self.assertLess(sync_block.index("btnSyncAll"), sync_block.index("btnAddList"))
        self.assertLess(sync_block.index("btnAddList"), sync_block.index("btnDeleteSelectedLists"))

    def test_list_sync_and_user_list_are_separate_modules(self):
        download_block = self.html.split("function initDownloadTab()", 1)[1].split("function normalizeUsers", 1)[0]
        self.assertIn("download-sync-module", download_block)
        self.assertIn("download-users-module", download_block)
        self.assertLess(download_block.index("download-sync-module"), download_block.index("download-users-module"))

        sync_module = download_block.split("download-sync-module", 1)[1].split("download-users-module", 1)[0]
        users_module = download_block.split("download-users-module", 1)[1]

        for sync_only in ["dl_list_items", "btnSyncAll", "addListSyncItem()", "btnDeleteSelectedLists"]:
            self.assertIn(sync_only, sync_module)
            self.assertNotIn(sync_only, users_module)
        for users_only in ["dl_user_bulk_add", "dl_user_table", "downloadUserList", "dedupeUsers", "pruneUnavailableUsers"]:
            self.assertIn(users_only, users_module)
            self.assertNotIn(users_only, sync_module)

    def test_list_sync_has_item_status_and_error_feedback(self):
        for expected in [
            "setListSyncStatus",
            "list-sync-status",
            "list-sync-item",
            "syncStatusIdle",
            "syncStatusRunning",
            "syncStatusSuccess",
            "syncStatusFailed",
            "renderListSyncError",
        ]:
            self.assertIn(expected, self.html)

    def test_sync_all_lists_recovers_button_and_has_timeout(self):
        sync_block = self.html.split("async function syncSelectedOrAllLists()", 1)[1].split("function waitForSyncCompletion", 1)[0]
        start_block = self.html.split("async function startSync", 1)[1].split("async function syncAllLists", 1)[0]
        payload_block = self.html.split("function buildListSyncPayload", 1)[1].split("function isListSyncReady", 1)[0]
        wait_block = self.html.split("function waitForSyncCompletion", 1)[1].split("function pollSyncStatus", 1)[0]
        self.assertIn("finally", sync_block)
        self.assertIn("btn.disabled = false", sync_block)
        self.assertIn("getSelectedOrAllListSyncItems", sync_block)
        selected_block = self.html.split("function getSelectedOrAllListSyncItems", 1)[1].split("async function deleteSelectedListSyncItems", 1)[0]
        self.assertIn("isListSyncReady", selected_block)
        self.assertIn("buildListSyncPayload", sync_block)
        self.assertIn("buildListSyncPayload", start_block)
        self.assertIn("parseListReference", payload_block)
        self.assertIn("syncTimeoutMs", wait_block)
        self.assertIn("reject", wait_block)
        self.assertNotIn("currently needs a numeric list ID", self.html)
        for label in ["备注名", "URL 短名", "Display name", "URL slug"]:
            self.assertIn(label, self.html)

    def test_download_list_workspace_uses_full_panel_height(self):
        for expected in [
            "download-list-toolbar",
            "download-list-summary",
            "download-user-table",
            "download-fill",
            "dlListSummary",
        ]:
            self.assertIn(expected, self.html)
        self.assertNotIn('style="height:220px', self.html)

    def test_media_library_explains_local_scan_totals(self):
        media_block = self.html.split("function initMediaTab()", 1)[1].split("/* ===== Download Tab ===== */", 1)[0]
        for expected in [
            'option value="200"',
            "mediaRefresh",
            "mediaSourceMeta",
            "mediaIndexedCount",
            "mediaLocalCount",
            "mediaOrphanCount",
            "data.indexed",
            "data.orphan",
            "refresh=1",
        ]:
            self.assertIn(expected, media_block)

    def test_media_library_supports_direct_page_jump(self):
        media_block = self.html.split("function initMediaTab()", 1)[1].split("/* ===== Download Tab ===== */", 1)[0]
        for expected in [
            "mediaPageJump",
            "mediaJumpToPage()",
            "mediaTotalPages",
            "mediaStepPage(-5)",
            "mediaStepPage(5)",
            "onkeydown=\"if(event.key==='Enter')mediaJumpToPage()\"",
            "min=\"1\"",
            "type=\"number\"",
        ]:
            self.assertIn(expected, media_block)

    def test_timeline_supports_full_pagination_controls(self):
        timeline_block = self.html.split("function initTimelineTab()", 1)[1].split("function renderTimelineItem", 1)[0]
        for expected in [
            "timelinePageJump",
            "timelineJumpToPage()",
            "timelineTotalPages",
            "timelineStepPage(-1)",
            "timelineStepPage(1)",
            "timelineStepPage(-5)",
            "timelineStepPage(5)",
            "onkeydown=\"if(event.key==='Enter')timelineJumpToPage()\"",
        ]:
            self.assertIn(expected, timeline_block)

    def test_download_user_list_uses_pagination_controls(self):
        download_block = self.html.split("function initDownloadTab()", 1)[1].split("function normalizeUsers", 1)[0]
        logic_block = self.html.split("function renderUserListManager()", 1)[1].split("function normalizeListSyncItems", 1)[0]
        for expected in [
            "dl_user_pager",
            "downloadUsersPageJump",
            "downloadUserListTotalPages",
            "downloadUserListJumpToPage()",
            "downloadUserListStepPage(-1)",
            "downloadUserListStepPage(1)",
            "downloadUserListStepPage(-5)",
            "downloadUserListStepPage(5)",
        ]:
            self.assertIn(expected, download_block + logic_block)

    def test_home_and_download_use_compact_workflow_layouts(self):
        for expected in [
            "home-viewport",
            "home-summary-grid",
            "home-insight-grid",
            "download-control-strip",
            "download-workflow-grid",
            "download-list-panel",
            "download-live-panel",
        ]:
            self.assertIn(expected, self.html)

        download_block = self.html.split("function initDownloadTab()", 1)[1]
        user_position = download_block.index("dl_user_bulk_add")
        control_position = download_block.index("download-control-strip")
        list_position = download_block.index("dl_list_items")
        log_position = download_block.index("download-log")
        self.assertLess(list_position, control_position)
        self.assertLess(list_position, user_position)
        self.assertLess(control_position, log_position)
        self.assertLess(list_position, log_position)

    def test_pages_have_clear_module_separation(self):
        for expected in [
            "--module-bg",
            "--module-border",
            "--module-shadow",
            ".form-section",
            ".download-module",
            ".home-panel",
            ".timeline-toolbar",
            ".timeline-list",
            ".media-toolbar",
            ".media-library-grid",
            ".browse-layout",
            "box-shadow: var(--module-shadow)",
        ]:
            self.assertIn(expected, self.html)


if __name__ == "__main__":
    unittest.main()
