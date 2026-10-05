"""Task storage and daily-task logic.

Pure Python: no Kivy and no OS-specific code, so it behaves identically on
Android, Windows, Linux and macOS and can be unit-tested anywhere.

Data model (same as the desktop version, so an old tasks.json still loads):
  * one-off task : appears only on its own ``date``; ``done`` is a single flag.
  * daily task   : appears every day from its ``created`` day onward; completion
                   is tracked per day in ``done_dates`` - this is the task history.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

Task = Dict[str, Any]


def day_key(d: date) -> str:
    return d.isoformat()


def _valid_day(value: Any) -> Optional[str]:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        return None


class TaskStore:
    def __init__(self, path: str):
        self.path = path
        self.tasks: List[Task] = []
        self.load()

    # ------------------------------------------------------------ storage
    def load(self) -> None:
        """Load tasks. A damaged file is set aside (never deleted) and we start clean."""
        self.tasks = []
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            self._quarantine()
            return
        items = raw.get("tasks") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            self._quarantine()
            return
        seen = set()
        for item in items:
            task = self._normalize(item)
            if task and task["id"] not in seen:
                seen.add(task["id"])
                self.tasks.append(task)

    def _quarantine(self) -> None:
        try:
            os.replace(self.path, f"{self.path}.corrupt-{int(time.time())}")
        except OSError:
            pass

    @staticmethod
    def _normalize(item: Any) -> Optional[Task]:
        if not isinstance(item, dict):
            return None
        title = str(item.get("title", "")).strip()
        created = _valid_day(item.get("created") or item.get("date"))
        if not title or not created:
            return None
        done_dates = sorted({d for d in map(_valid_day, item.get("done_dates") or []) if d})
        return {
            "id": str(item.get("id") or uuid.uuid4().hex),
            "title": title,
            "daily": bool(item.get("daily", False)),
            "created": created,
            "date": _valid_day(item.get("date")) or created,
            "done": bool(item.get("done", False)),
            "done_dates": done_dates,
        }

    def save(self) -> None:
        """Atomic write: a crash or a killed app can never leave a half-written file."""
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.tasks, fh, ensure_ascii=False, indent=2)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    # -------------------------------------------------------------- logic
    def get(self, task_id: str) -> Optional[Task]:
        return next((t for t in self.tasks if t["id"] == task_id), None)

    @staticmethod
    def is_visible(task: Task, day: str) -> bool:
        return day >= task["created"] if task["daily"] else task["date"] == day

    @staticmethod
    def is_done(task: Task, day: str) -> bool:
        return day in task["done_dates"] if task["daily"] else task["done"]

    def visible(self, day: str) -> List[Task]:
        """Tasks shown on ``day``: unfinished first, finished last (stable order)."""
        shown = [t for t in self.tasks if self.is_visible(t, day)]
        shown.sort(key=lambda t: self.is_done(t, day))
        return shown

    def progress(self, day: str) -> Tuple[int, int]:
        shown = [t for t in self.tasks if self.is_visible(t, day)]
        return sum(self.is_done(t, day) for t in shown), len(shown)

    def add(self, title: str, daily: bool, day: str) -> Optional[Task]:
        title = title.strip()
        if not title:
            return None
        task = {"id": uuid.uuid4().hex, "title": title, "daily": bool(daily), "created": day,
                "date": day, "done": False, "done_dates": []}
        self.tasks.append(task)
        self.save()
        return task

    def toggle(self, task_id: str, day: str) -> Optional[bool]:
        """Flip completion for ``day``. Returns the new state, or None if not applicable."""
        task = self.get(task_id)
        if task is None or not self.is_visible(task, day):
            return None
        new_state = not self.is_done(task, day)
        if task["daily"]:
            if new_state:
                task["done_dates"] = sorted(set(task["done_dates"]) | {day})
            else:
                task["done_dates"] = [d for d in task["done_dates"] if d != day]
        else:
            task["done"] = new_state
        self.save()
        return new_state

    def delete(self, task_id: str) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        self.tasks.remove(task)
        self.save()
        return True

    def clear_completed(self, day: str) -> int:
        """Remove finished one-off tasks of ``day``. Daily tasks (and their history) stay."""
        keep = [t for t in self.tasks if t["daily"] or t["date"] != day or not t["done"]]
        removed = len(self.tasks) - len(keep)
        if removed:
            self.tasks = keep
            self.save()
        return removed
