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


if __name__ == "__main__":
    unittest.main()
