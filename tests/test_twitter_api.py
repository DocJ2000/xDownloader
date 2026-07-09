import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "xdownloader_app"
sys.path.insert(0, str(APP_DIR))

from src.twitter_api import TwitterAPI


class RepeatingCursorListApi(TwitterAPI):
    def __init__(self):
        super().__init__(None, None)
        self.calls = 0

    def _get(self, url):
        self.calls += 1
        return json.dumps({
            "data": {
                "list": {
                    "members_timeline": {
                        "timeline": {
                            "instructions": [{
                                "type": "TimelineAddEntries",
                                "entries": [
                                    {
                                        "entryId": "list-member-1",
                                        "content": {
                                            "itemContent": {
                                                "user_results": {
                                                    "result": {
                                                        "legacy": {"screen_name": "alice"}
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "entryId": "cursor-bottom-1",
                                        "content": {"value": "same-cursor"},
                                    },
                                ],
                            }]
                        }
                    }
                }
            }
        })


class TwitterApiListTest(unittest.TestCase):
    def test_list_member_sync_stops_on_repeated_cursor(self):
        api = RepeatingCursorListApi()

        members = api.fetch_list_members_by_id("123")

        self.assertEqual(["alice"], members)
        self.assertEqual(2, api.calls)


if __name__ == "__main__":
    unittest.main()
