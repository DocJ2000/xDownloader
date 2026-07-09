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

    def test_settings_cover_all_user_config_sections(self):
        expected_controls = [
            "cfg_download_auto_sync",
            "cfg_verbose",
            "cfg_tag_search_tag",
            "cfg_tag_search_filter",
            "cfg_tag_search_count",
            "cfg_tag_search_media_latest",
            "cfg_tag_search_text_mode",
            "cfg_text_user_list",
            "cfg_text_max_tweets",
            "cfg_text_request_delay",
            "cfg_text_max_retries",
        ]
        for control_id in expected_controls:
            self.assertIn(control_id, self.html)

    def test_settings_use_apply_language(self):
        self.assertIn("applyConfig", self.html)
        self.assertIn("Applied", self.html)
        self.assertIn("应用", self.html)

    def test_time_range_uses_date_controls(self):
        self.assertIn('id="cfg_time_start"', self.html)
        self.assertIn('id="cfg_time_end"', self.html)
        self.assertIn('type="date"', self.html)
        self.assertIn("buildTimeRange()", self.html)

    def test_list_sync_labels_and_help_are_bilingual(self):
        for key in ["listId", "listOwner", "listSlug", "listSyncHelp"]:
            self.assertIn(key, self.html)
        self.assertIn("cfg_list_id", self.html)
        self.assertIn("cfg_list_owner", self.html)
        self.assertIn("cfg_list_slug", self.html)


if __name__ == "__main__":
    unittest.main()
