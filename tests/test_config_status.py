import tempfile
import unittest

from xdownloader_app.server import build_config_status, get_download_root


class ConfigStatusTest(unittest.TestCase):
    def test_reports_missing_required_personal_settings(self):
        cfg = {
            "cookie": "",
            "bearer_token": "",
            "save_path": "",
            "user_list": [],
            "proxy": "not-a-url",
            "download": {"max_concurrent": 64},
        }

        status = build_config_status(cfg)

        self.assertFalse(status["ready"])
        self.assertIn("cookie", status["missing"])
        self.assertIn("bearer_token", status["missing"])
        self.assertIn("save_path", status["missing"])
        self.assertIn("user_list", status["missing"])
        self.assertIn("proxy", status["warnings"])
        self.assertIn("download.max_concurrent", status["warnings"])

    def test_accepts_complete_personal_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cfg = {
                "cookie": "example-cookie",
                "bearer_token": "example-token",
                "save_path": temp_dir,
                "user_list": ["openai"],
                "proxy": "http://127.0.0.1:7890",
                "download": {"max_concurrent": 16},
            }

            status = build_config_status(cfg)

        self.assertTrue(status["ready"])
        self.assertEqual([], status["missing"])
        self.assertEqual([], status["warnings"])

    def test_download_root_comes_from_config_save_path(self):
        cfg = {"save_path": "downloads"}

        self.assertEqual("downloads", get_download_root(cfg))


if __name__ == "__main__":
    unittest.main()
