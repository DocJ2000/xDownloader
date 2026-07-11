import csv
import os
import tempfile
import unittest

from xdownloader_app.server import build_dashboard_response, build_media_library_response, build_timeline_response


class TimelineApiTest(unittest.TestCase):
    def _write_user_csv(self, root, folder, screen_name, rows):
        user_dir = os.path.join(root, folder)
        os.makedirs(user_dir, exist_ok=True)
        csv_path = os.path.join(user_dir, f"{screen_name}.csv")
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Alice", screen_name])
            writer.writerow(["Tweet Range : 2024-01-01:2030-01-01"])
            writer.writerow([f"Save Path : {user_dir}"])
            writer.writerow([
                "Tweet Date", "Display Name", "User Name", "Tweet URL",
                "Media Type", "Media URL", "Saved Filename", "Tweet Content",
                "Favorite Count", "Retweet Count", "Reply Count",
            ])
            writer.writerows(rows)

    def test_builds_paginated_timeline_sorted_by_newest(self):
        with tempfile.TemporaryDirectory() as root:
            self._write_user_csv(root, "Alice@alice", "alice", [
                [
                    "2025-01-02 09:00", "Alice", "alice",
                    "https://x.com/alice/status/2", "photo",
                    "https://pbs.twimg.com/2.jpg", "two.jpg",
                    "newer post", "10", "2", "1",
                ],
                [
                    "2025-01-01 09:00", "Alice", "alice",
                    "https://x.com/alice/status/1", "",
                    "", "", "older text", "3", "1", "0",
                ],
            ])

            response = build_timeline_response(root, page=1, per_page=1)

            self.assertEqual(2, response["total"])
            self.assertEqual(2, response["total_pages"])
            self.assertEqual("https://x.com/alice/status/2", response["items"][0]["url"])
            self.assertEqual("two.jpg", response["items"][0]["media_items"][0]["local_file"])
            self.assertEqual("/media/Alice@alice/two.jpg", response["items"][0]["media_items"][0]["media_path"])

    def test_filters_timeline_by_text_or_user(self):
        with tempfile.TemporaryDirectory() as root:
            self._write_user_csv(root, "Alice@alice", "alice", [
                [
                    "2025-01-02 09:00", "Alice", "alice",
                    "https://x.com/alice/status/2", "", "", "",
                    "launch notes", "10", "2", "1",
                ],
                [
                    "2025-01-01 09:00", "Alice", "alice",
                    "https://x.com/alice/status/1", "", "", "",
                    "quiet update", "3", "1", "0",
                ],
            ])

            response = build_timeline_response(root, page=1, per_page=20, query="launch")

            self.assertEqual(1, response["total"])
            self.assertEqual("launch notes", response["items"][0]["content"])

    def test_filters_timeline_by_media_type(self):
        with tempfile.TemporaryDirectory() as root:
            self._write_user_csv(root, "Alice@alice", "alice", [
                [
                    "2025-01-03 09:00", "Alice", "alice",
                    "https://x.com/alice/status/3", "Video",
                    "https://video.twimg.com/3.mp4", "three.mp4",
                    "video post", "10", "2", "1",
                ],
                [
                    "2025-01-02 09:00", "Alice", "alice",
                    "https://x.com/alice/status/2", "Image",
                    "https://pbs.twimg.com/2.jpg", "two.jpg",
                    "image post", "8", "1", "0",
                ],
                [
                    "2025-01-01 09:00", "Alice", "alice",
                    "https://x.com/alice/status/1", "", "", "",
                    "text post", "3", "1", "0",
                ],
            ])

            videos = build_timeline_response(root, page=1, per_page=20, media_filter="video")
            images = build_timeline_response(root, page=1, per_page=20, media_filter="image")
            texts = build_timeline_response(root, page=1, per_page=20, media_filter="text")

            self.assertEqual(["video post"], [item["content"] for item in videos["items"]])
            self.assertEqual(["image post"], [item["content"] for item in images["items"]])
            self.assertEqual(["text post"], [item["content"] for item in texts["items"]])

    def test_builds_media_library_response(self):
        with tempfile.TemporaryDirectory() as root:
            self._write_user_csv(root, "Alice@alice", "alice", [
                [
                    "2025-01-03 09:00", "Alice", "alice",
                    "https://x.com/alice/status/3", "Video",
                    "https://video.twimg.com/3.mp4", "three.mp4",
                    "video post", "10", "2", "1",
                ],
                [
                    "2025-01-02 09:00", "Alice", "alice",
                    "https://x.com/alice/status/2", "Image",
                    "https://pbs.twimg.com/2.jpg", "two.jpg",
                    "image post", "8", "1", "0",
                ],
            ])

            response = build_media_library_response(root, page=1, per_page=20, media_filter="image")

            self.assertEqual(1, response["total"])
            self.assertEqual("two.jpg", response["items"][0]["local_file"])
            self.assertEqual("/media/Alice@alice/two.jpg", response["items"][0]["media_path"])

    def test_media_library_scans_local_files_without_csv_rows(self):
        with tempfile.TemporaryDirectory() as root:
            user_dir = os.path.join(root, "Alice@alice")
            os.makedirs(user_dir, exist_ok=True)
            with open(os.path.join(user_dir, "orphan.jpg"), "wb") as f:
                f.write(b"image-data")

            response = build_media_library_response(root, page=1, per_page=20)

            self.assertEqual(1, response["total"])
            self.assertEqual("orphan.jpg", response["items"][0]["local_file"])
            self.assertEqual("local", response["items"][0]["source"])

    def test_media_library_is_not_limited_by_timeline_page_size(self):
        with tempfile.TemporaryDirectory() as root:
            rows = []
            user_dir = os.path.join(root, "Alice@alice")
            for i in range(130):
                filename = f"media-{i:03d}.jpg"
                rows.append([
                    f"2025-01-{(i % 28) + 1:02d} 09:00", "Alice", "alice",
                    f"https://x.com/alice/status/{i}", "Image",
                    f"https://pbs.twimg.com/{i}.jpg", filename,
                    f"image post {i}", "8", "1", "0",
                ])
                os.makedirs(user_dir, exist_ok=True)
                with open(os.path.join(user_dir, filename), "wb") as f:
                    f.write(b"image-data")
            self._write_user_csv(root, "Alice@alice", "alice", rows)

            response = build_media_library_response(root, page=1, per_page=200)

            self.assertEqual(130, response["total"])
            self.assertEqual(1, response["total_pages"])

    def test_media_library_cache_refreshes_on_demand(self):
        with tempfile.TemporaryDirectory() as root:
            user_dir = os.path.join(root, "Alice@alice")
            os.makedirs(user_dir, exist_ok=True)
            with open(os.path.join(user_dir, "one.jpg"), "wb") as f:
                f.write(b"one")

            first = build_media_library_response(root, page=1, per_page=20, force_refresh=True)
            with open(os.path.join(user_dir, "two.jpg"), "wb") as f:
                f.write(b"two")
            cached = build_media_library_response(root, page=1, per_page=20)
            refreshed = build_media_library_response(root, page=1, per_page=20, force_refresh=True)

            self.assertEqual(1, first["total"])
            self.assertEqual(1, cached["total"])
            self.assertEqual(2, refreshed["total"])

    def test_builds_dashboard_response_with_library_insights(self):
        with tempfile.TemporaryDirectory() as root:
            self._write_user_csv(root, "Alice@alice", "alice", [
                [
                    "2025-01-03 09:00", "Alice", "alice",
                    "https://x.com/alice/status/3", "Video",
                    "https://video.twimg.com/3.mp4", "three.mp4",
                    "video post", "10", "2", "1",
                ],
                [
                    "2025-01-02 09:00", "Alice", "alice",
                    "https://x.com/alice/status/2", "Image",
                    "https://pbs.twimg.com/2.jpg", "two.jpg",
                    "image post", "8", "1", "0",
                ],
            ])
            with open(os.path.join(root, "Alice@alice", "two.jpg"), "wb") as f:
                f.write(b"image-data")
            with open(os.path.join(root, "Alice@alice", "three.mp4"), "wb") as f:
                f.write(b"video-data-longer")
            os.makedirs(os.path.join(root, "Broken@broken"), exist_ok=True)

            response = build_dashboard_response(root)

            self.assertEqual(2, response["totals"]["users"])
            self.assertEqual(2, response["totals"]["media"])
            self.assertEqual(2, response["totals"]["tweets"])
            self.assertEqual(1, response["media_types"]["image"])
            self.assertEqual(1, response["media_types"]["video"])
            self.assertEqual(27, response["storage"]["bytes"])
            self.assertEqual("Alice@alice", response["recent_users"][0]["folder"])
            self.assertIn("Broken@broken", response["health"]["folders_without_csv"])


if __name__ == "__main__":
    unittest.main()
