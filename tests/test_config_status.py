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

    def test_auto_shutdown_runs_only_after_normal_completion(self):
        for initial_state, expected_called in [
            ({"running": True, "paused": False, "terminated": False, "auto_shutdown": True, "logs": []}, True),
            ({"running": True, "paused": True, "terminated": False, "auto_shutdown": True, "logs": []}, False),
            ({"running": True, "paused": False, "terminated": True, "auto_shutdown": True, "logs": []}, False),
            ({"running": True, "paused": False, "terminated": False, "failed": True, "auto_shutdown": True, "logs": []}, False),
            ({"running": True, "paused": False, "terminated": False, "auto_shutdown": False, "logs": []}, False),
        ]:
            server.download_state = initial_state.copy()
            with patch.object(server, "schedule_system_shutdown") as shutdown:
                server.finalize_download_state()
            self.assertEqual(expected_called, shutdown.called)

    def test_download_start_accepts_auto_shutdown_flag(self):
        server.download_state = {"running": False}
        with patch.object(server.threading, "Thread") as thread_class:
            response = app.test_client().post(
                "/api/download/start",
                json={"users": ["openai"], "auto_shutdown": True},
            )

        self.assertEqual(200, response.status_code)
        self.assertTrue(server.download_state["auto_shutdown"])
        self.assertFalse(server.download_state["shutdown_scheduled"])
        thread_class.return_value.start.assert_called_once()
        server.download_state = {"running": False}

    def test_download_history_keeps_last_three_completed_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = os.path.join(temp_dir, "download_history.json")
            with patch.object(server, "download_history_path", return_value=history_path):
                for idx in range(4):
                    server.record_download_history(
                        stats={
                            "users": idx + 1,
                            "images": idx,
                            "videos": idx + 1,
                            "text_tweets": idx + 2,
                        },
                        requested_users=["a", "b", "c"],
                        storage_before=100,
                        storage_after=100 + idx * 2048,
                        started_at=1000,
                        finished_at=1000 + idx * 61,
                    )

                history = server.load_download_history()

        self.assertEqual(3, len(history))
        self.assertEqual([2, 3, 4], [item["users"] for item in history])
        self.assertEqual([3, 5, 7], [item["new_media"] for item in history])
        self.assertEqual([3, 4, 5], [item["new_tweets"] for item in history])
        self.assertEqual(6144, history[-1]["new_bytes"])
        self.assertEqual("6.0 KB", history[-1]["new_size"])
        self.assertEqual(183, history[-1]["duration_seconds"])
        self.assertEqual("3m 3s", history[-1]["duration"])
        self.assertIn("finished_at", history[-1])

    def test_finalize_records_history_only_after_normal_completion(self):
        for state, should_record in [
            ({"running": True, "paused": False, "terminated": False, "failed": False}, True),
            ({"running": True, "paused": True, "terminated": False, "failed": False}, False),
            ({"running": True, "paused": False, "terminated": True, "failed": False}, False),
            ({"running": True, "paused": False, "terminated": False, "failed": True}, False),
        ]:
            server.download_state = {
                **state,
                "auto_shutdown": False,
                "shutdown_scheduled": False,
                "stats": {"users": 2, "images": 1, "videos": 2, "text_tweets": 3},
                "requested_users": ["openai", "github"],
                "storage_before": 100,
                "storage_after": 4096,
                "started_at": 1000,
                "logs": [],
            }
            with patch.object(server, "record_download_history") as record, patch.object(server.time, "time", return_value=1065):
                server.finalize_download_state()
            self.assertEqual(should_record, record.called)
            if should_record:
                self.assertEqual(1000, record.call_args.kwargs["started_at"])
                self.assertEqual(1065, record.call_args.kwargs["finished_at"])

    def test_download_status_includes_recent_history(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_path = os.path.join(temp_dir, "download_history.json")
            with patch.object(server, "download_history_path", return_value=history_path):
                server.record_download_history(
                    stats={"users": 1, "images": 2, "videos": 3, "text_tweets": 4},
                    requested_users=["openai"],
                    storage_before=0,
                    storage_after=1024,
                    started_at=100,
                    finished_at=165,
                )
                response = app.test_client().get("/api/download/status")

        self.assertEqual(200, response.status_code)
        data = response.get_json()
        self.assertEqual(1, len(data["history"]))
        self.assertEqual(5, data["history"][0]["new_media"])
        self.assertEqual("1m 5s", data["history"][0]["duration"])

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

    def test_resolves_list_sync_request_from_id_owner_slug_or_url(self):
        from xdownloader_app.server import resolve_list_sync_request

        by_id = resolve_list_sync_request({"list_url": "https://x.com/i/lists/12345"}, {})
        by_slug = resolve_list_sync_request({"list_url": "https://x.com/owner/lists/favorites"}, {})
        from_config = resolve_list_sync_request({}, {"list_sync": {"list_owner": "cfg_owner", "list_slug": "cfg_slug"}})

        self.assertEqual("12345", by_id["list_id"])
        self.assertEqual("owner", by_slug["list_owner"])
        self.assertEqual("favorites", by_slug["list_slug"])
        self.assertEqual("cfg_owner", from_config["list_owner"])
        self.assertEqual("cfg_slug", from_config["list_slug"])

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

    def test_update_version_comparison_handles_v_prefixes(self):
        self.assertTrue(server.is_newer_version("v0.3.2", "v0.3.1"))
        self.assertFalse(server.is_newer_version("v0.3.1", "0.3.1"))
        self.assertFalse(server.is_newer_version("v0.3.0", "v0.3.1"))

    def test_update_status_selects_windows_installer_asset(self):
        release = {
            "tag_name": "v0.3.2",
            "html_url": "https://github.com/DocJ2000/xDownloader/releases/tag/v0.3.2",
            "body": "bug fixes",
            "assets": [
                {"name": "xDownloader-v0.3.2-windows.zip", "browser_download_url": "zip-url"},
                {
                    "name": "xDownloader-Setup-v0.3.2.exe",
                    "browser_download_url": "setup-url",
                    "size": 123,
                },
            ],
        }

        status = server.build_update_status(release, current_version="v0.3.1")

        self.assertTrue(status["update_available"])
        self.assertEqual("v0.3.2", status["latest_version"])
        self.assertEqual("xDownloader-Setup-v0.3.2.exe", status["installer_name"])
        self.assertEqual("setup-url", status["download_url"])

    def test_update_status_reports_source_runtime_mode(self):
        release = {"tag_name": "v0.3.2", "html_url": "release-url", "assets": []}

        status = server.build_update_status(release, current_version="v0.3.1", runtime_mode="source")

        self.assertEqual("source", status["runtime_mode"])
        self.assertFalse(status["can_install_update"])
        self.assertTrue(status["update_available"])
        self.assertEqual("release-url", status["release_url"])

    def test_update_check_reports_latest_when_versions_match(self):
        release = {"tag_name": "v0.3.1", "assets": []}
        with patch.object(server, "fetch_latest_github_release", return_value=release):
            response = app.test_client().get("/api/update/check")

        data = response.get_json()
        self.assertEqual(200, response.status_code)
        self.assertFalse(data["update_available"])
        self.assertEqual("v0.3.1", data["latest_version"])

    def test_update_page_fallback_derives_installer_from_latest_tag(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def geturl(self):
                return "https://github.com/DocJ2000/xDownloader/releases/tag/v0.3.2"

            def read(self, *_args):
                return b"<html></html>"

        with patch.object(server.urllib.request, "urlopen", return_value=FakeResponse()):
            release = server.fetch_latest_github_release_from_page()

        self.assertEqual("v0.3.2", release["tag_name"])
        self.assertEqual("xDownloader-Setup-v0.3.2.exe", release["assets"][0]["name"])
        self.assertIn("/releases/download/v0.3.2/", release["assets"][0]["browser_download_url"])

    def test_update_download_saves_installer_inside_updates_folder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            chunks = [b"setup", b"-bytes"]
            with patch.object(server, "PROJECT_ROOT", temp_dir), patch.object(
                server, "download_update_asset", return_value=chunks
            ):
                response = app.test_client().post(
                    "/api/update/download",
                    json={
                        "download_url": "https://github.com/DocJ2000/xDownloader/releases/download/v0.3.2/xDownloader-Setup-v0.3.2.exe",
                        "installer_name": "xDownloader-Setup-v0.3.2.exe",
                    },
                )

            data = response.get_json()
            self.assertEqual(200, response.status_code)
            self.assertTrue(data["ok"])
            self.assertTrue(data["file_path"].startswith(os.path.join(temp_dir, "updates")))
            with open(data["file_path"], "rb") as f:
                self.assertEqual(b"setup-bytes", f.read())

    def test_update_download_rejects_non_installer_name(self):
        response = app.test_client().post(
            "/api/update/download",
            json={"download_url": "https://example.com/file.exe", "installer_name": "tool.exe"},
        )

        self.assertEqual(400, response.status_code)


if __name__ == "__main__":
    unittest.main()
