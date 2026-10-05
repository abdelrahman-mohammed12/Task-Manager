"""Run: python -m unittest discover -s tests -v"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from task_store import TaskStore  # noqa: E402

D1, D2, D3 = "2026-10-05", "2026-10-06", "2026-10-07"


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "nested", "tasks.json")   # folder does not exist yet
        self.store = TaskStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_one_off_task_only_on_its_day(self):
        t = self.store.add("Buy milk", False, D1)
        self.assertEqual([x["id"] for x in self.store.visible(D1)], [t["id"]])
        self.assertEqual(self.store.visible(D2), [])
        self.assertEqual(self.store.visible("2026-10-04"), [])

    def test_daily_task_history_is_per_day(self):
        t = self.store.add("Exercise", True, D1)
        self.assertEqual(self.store.toggle(t["id"], D1), True)        # done on D1
        self.assertFalse(self.store.is_done(t, D2))                   # fresh again on D2
        self.assertEqual(self.store.progress(D1), (1, 1))
        self.assertEqual(self.store.progress(D2), (0, 1))
        self.store.toggle(t["id"], D2)
        self.assertEqual(t["done_dates"], [D1, D2])
        self.store.toggle(t["id"], D1)                                # undo the past day only
        self.assertEqual(t["done_dates"], [D2])
        self.assertEqual(self.store.visible("2026-10-04"), [])        # not shown before it existed

    def test_toggle_rejects_invisible_day(self):
        t = self.store.add("Once", False, D1)
        self.assertIsNone(self.store.toggle(t["id"], D2))
        self.assertIsNone(self.store.toggle("missing", D1))

    def test_sort_done_last_and_progress(self):
        a = self.store.add("A", False, D1); self.store.add("B", False, D1)
        self.store.toggle(a["id"], D1)
        self.assertEqual([t["title"] for t in self.store.visible(D1)], ["B", "A"])
        self.assertEqual(self.store.progress(D1), (1, 2))

    def test_clear_completed_keeps_daily_and_history(self):
        once = self.store.add("Once", False, D1); self.store.toggle(once["id"], D1)
        daily = self.store.add("Daily", True, D1); self.store.toggle(daily["id"], D1)
        self.assertEqual(self.store.clear_completed(D1), 1)
        self.assertIsNone(self.store.get(once["id"]))
        self.assertEqual(self.store.get(daily["id"])["done_dates"], [D1])

    def test_delete_and_blank_title(self):
        t = self.store.add("  x  ", False, D1)
        self.assertEqual(t["title"], "x")
        self.assertIsNone(self.store.add("   ", False, D1))
        self.assertTrue(self.store.delete(t["id"])); self.assertFalse(self.store.delete(t["id"]))

    def test_persistence_unicode_and_atomic_file(self):
        t = self.store.add("اشتري الخبز", True, D1); self.store.toggle(t["id"], D2)
        self.assertFalse(os.path.exists(self.path + ".tmp"))
        again = TaskStore(self.path)
        self.assertEqual(again.get(t["id"])["title"], "اشتري الخبز")
        self.assertEqual(again.get(t["id"])["done_dates"], [D2])
        with open(self.path, encoding="utf-8") as fh:
            self.assertIn("اشتري", fh.read())   # stored as real text

    def test_corrupt_file_is_set_aside(self):
        os.makedirs(os.path.dirname(self.path))
        open(self.path, "w").write("{not json")
        s = TaskStore(self.path)
        self.assertEqual(s.tasks, [])
        self.assertTrue(any(".corrupt-" in f for f in os.listdir(os.path.dirname(self.path))))

    def test_loads_desktop_version_file_and_skips_bad_entries(self):
        os.makedirs(os.path.dirname(self.path))
        legacy = [{"id": "1", "title": "Old", "daily": True, "created": D1, "date": D1, "done": False,
                   "done_dates": [D1, "garbage", D1]},
                  {"title": "no id", "date": D2},
                  {"id": "3", "title": "", "date": D1}, "junk", {"id": "4", "title": "bad", "date": "xx"}]
        json.dump(legacy, open(self.path, "w", encoding="utf-8"))
        s = TaskStore(self.path)
        self.assertEqual(sorted(t["title"] for t in s.tasks), ["Old", "no id"])
        self.assertEqual(s.get("1")["done_dates"], [D1])


if __name__ == "__main__":
    unittest.main()
