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

    def test_settings_keeps_only_foundational_configuration(self):
        for control_id in [
            "cfg_cookie",
            "cfg_bearer_token",
            "cfg_save_path",
            "cfg_proxy",
            "cfg_verbose",
            "cfg_log_file",
            "cfg_theme",
        ]:
            self.assertIn(control_id, self.html)

        settings_block = self.html.split("async function initSettings()", 1)[1].split("function readLinesFromField", 1)[0]
        for download_only_control in [
            "cfg_time_start",
            "cfg_time_end",
            "cfg_has_video",
            "cfg_download_auto_sync",
            "cfg_tag_search_tag",
            "cfg_text_user_list",
            "cfg_list_id",
        ]:
            self.assertNotIn(download_only_control, settings_block)

    def test_settings_use_apply_language(self):
        self.assertIn("applyConfig", self.html)
        self.assertIn("Applied", self.html)
        self.assertIn("应用", self.html)

    def test_download_tab_owns_download_options(self):
        for control_id in [
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
        ]:
            self.assertIn(control_id, self.html)
        self.assertIn('type="date"', self.html)
        self.assertIn("buildDownloadTimeRange()", self.html)

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

    def test_user_list_manager_supports_reviewing_large_lists(self):
        for expected in [
            "dl_user_filter",
            "dl_user_bulk_add",
            "dl_user_table",
            "normalizeUsers",
            "renderUserListManager",
            "dedupeUsers",
            "clearUsers",
        ]:
            self.assertIn(expected, self.html)

    def test_multiple_list_sync_controls_exist(self):
        for expected in [
            "listSyncItems",
            "renderListSyncItems",
            "addListSyncItem",
            "removeListSyncItem",
            "syncAllLists",
            "dl_list_items",
            "listSyncHelp",
        ]:
            self.assertIn(expected, self.html)


if __name__ == "__main__":
    unittest.main()
