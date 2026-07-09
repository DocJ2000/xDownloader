import json
import os
import tempfile
import unittest
from unittest.mock import patch

import xdownloader_app.server as server
from xdownloader_app.server import app, build_config_status, ensure_config_file, get_download_root


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

    def test_directory_picker_api_returns_selected_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("xdownloader_app.server.open_directory_dialog", return_value=temp_dir):
                response = app.test_client().post(
                    "/api/dialog/directory",
                    json={"initial_dir": "downloads"},
                )

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "path": temp_dir}, response.get_json())

    def test_directory_picker_api_reports_cancel(self):
        with patch("xdownloader_app.server.open_directory_dialog", return_value=""):
            response = app.test_client().post("/api/dialog/directory", json={})

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": False, "path": ""}, response.get_json())

    def test_missing_config_is_created_from_example_for_packaged_app(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = f"{temp_dir}/config.json"
            example_path = f"{temp_dir}/config.example.json"
            with open(example_path, "w", encoding="utf-8") as f:
                f.write('{"save_path": "downloads", "user_list": []}\n')

            ensure_config_file(config_path=config_path, example_path=example_path)

            with open(config_path, "r", encoding="utf-8") as f:
                self.assertIn('"save_path": "downloads"', f.read())

    def test_download_pause_marks_paused_without_clearing_progress(self):
        server.download_state = {
            "running": True,
            "paused": False,
            "terminated": False,
            "logs": [],
            "current": 1,
            "total": 3,
            "stats": None,
        }

        response = app.test_client().post("/api/download/pause")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "state": "paused"}, response.get_json())
        self.assertFalse(server.download_state["running"])
        self.assertTrue(server.download_state["paused"])
        self.assertFalse(server.download_state["terminated"])

    def test_download_terminate_marks_terminated_and_clears_progress(self):
        progress_path = server.download_progress_path()
        with open(progress_path, "w", encoding="utf-8") as f:
            f.write('{"completed": ["openai"]}')
        server.download_state = {
            "running": True,
            "paused": False,
            "terminated": False,
            "logs": [],
            "current": 1,
            "total": 3,
            "stats": None,
        }

        response = app.test_client().post("/api/download/terminate")

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "state": "terminated"}, response.get_json())
        self.assertFalse(server.download_state["running"])
        self.assertFalse(server.download_state["paused"])
        self.assertTrue(server.download_state["terminated"])
        self.assertFalse(server.os.path.exists(progress_path))

    def test_config_accepts_multiple_list_sync_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = f"{temp_dir}/config.json"
            with open(config_path, "w", encoding="utf-8") as f:
                f.write('{"list_sync": {"enabled": true, "lists": []}}\n')
            with patch.object(server, "CONFIG_PATH", config_path):
                response = app.test_client().post(
                    "/api/config",
                    json={
                        "list_sync.lists": [
                            {"name": "AI", "list_id": "123", "enabled": True},
                            {"name": "News", "list_id": "456", "enabled": False},
                        ]
                    },
                )
                self.assertEqual(200, response.status_code)
                saved = server.load_config_data()

        self.assertEqual("123", saved["list_sync"]["lists"][0]["list_id"])
        self.assertEqual("456", saved["list_sync"]["lists"][1]["list_id"])

    def test_text_tweets_are_download_mode_option(self):
        cfg = server.default_config_data()

        self.assertIn("has_text", cfg["mode"])
        self.assertTrue(cfg["mode"]["has_text"])

    def test_prune_users_preview_does_not_modify_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"user_list": ["openai", "missing_user"]}, f)

            with patch.object(server, "CONFIG_PATH", config_path), patch.object(
                server, "find_unavailable_users", return_value=["missing_user"]
            ):
                response = app.test_client().post("/api/users/prune", json={"confirm": False})
                saved = server.load_config_data()

        self.assertEqual(200, response.status_code)
        self.assertEqual({"ok": True, "removed": [], "candidates": ["missing_user"]}, response.get_json())
        self.assertEqual(["openai", "missing_user"], saved["user_list"])

    def test_prune_users_requires_confirmation_before_removing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"user_list": ["openai", "missing_user", "renamed_user"]}, f)

            with patch.object(server, "CONFIG_PATH", config_path), patch.object(
                server, "find_unavailable_users", return_value=["missing_user", "renamed_user"]
            ):
                response = app.test_client().post("/api/users/prune", json={"confirm": True})
                saved = server.load_config_data()

        self.assertEqual(200, response.status_code)
        self.assertEqual(["missing_user", "renamed_user"], response.get_json()["removed"])
        self.assertEqual(["openai"], saved["user_list"])

    def test_config_migration_preserves_values_adds_defaults_and_backs_up(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            old_config = {
                "cookie": "keep-cookie",
                "save_path": "D:/keep/downloads",
                "list_sync": {
                    "enabled": True,
                    "list_id": "12345",
                    "list_owner": "example_owner",
                    "list_slug": "favorites",
                },
            }
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(old_config, f)

            with patch.object(server, "CONFIG_PATH", config_path):
                migrated = server.load_config_data()

            self.assertEqual("keep-cookie", migrated["cookie"])
            self.assertEqual("D:/keep/downloads", migrated["save_path"])
            self.assertEqual(server.CURRENT_CONFIG_VERSION, migrated["config_version"])
            self.assertIn("download", migrated)
            self.assertEqual("12345", migrated["list_sync"]["lists"][0]["list_id"])
            self.assertTrue(os.path.exists(config_path + ".bak"))
            with open(config_path + ".bak", "r", encoding="utf-8") as f:
                backup = json.load(f)
            self.assertNotIn("config_version", backup)
            self.assertEqual("keep-cookie", backup["cookie"])

    def test_save_config_creates_backup_before_replacing_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"cookie": "old-cookie"}, f)

            with patch.object(server, "CONFIG_PATH", config_path):
                server.save_config_data({"cookie": "new-cookie"})

            with open(config_path, "r", encoding="utf-8") as f:
                self.assertEqual("new-cookie", json.load(f)["cookie"])
            with open(config_path + ".bak", "r", encoding="utf-8") as f:
                self.assertEqual("old-cookie", json.load(f)["cookie"])


if __name__ == "__main__":
    unittest.main()
