"""
QueueManager: holds the live, real-time queue of students waiting for a
shared tuk from USJ to Wijerama, and applies the DispatchCoordinator's
learned policy to decide when to group and dispatch them.

This is deliberately simple in-memory state (a single process, no DB) --
fine for a course demo. If it needs to survive restarts or run across
multiple server workers, swap this for a real store (Redis, SQLite, etc).
"""

import time
import uuid
from coordinator import DispatchCoordinator, MAX_CAPACITY, FARE_FOR_GROUP_SIZE

HARD_WAIT_CAP_MINUTES = 8  # safety net: never make anyone wait longer than this


class QueueManager:
    def __init__(self):
        self.coordinator = DispatchCoordinator()
        self.coordinator.train(episodes=40000)

        self.queue = []          # list of dicts: {id, name, join_time}
        self.dispatch_log = []   # recent dispatches, for the demo dashboard
        self.results = {}        # student_id -> dispatch result (once matched)

    def add_student(self, name: str) -> dict:
        student_id = str(uuid.uuid4())[:8]
        entry = {"id": student_id, "name": name or "Student", "join_time": time.time()}
        self.queue.append(entry)

        # if we just hit capacity, dispatch immediately -- no need to wait
        # for the next background tick
        if len(self.queue) >= MAX_CAPACITY:
            self._dispatch_group(self.queue[:MAX_CAPACITY])

        return entry

    def tick(self):
        """Called periodically by the background loop. Consults the
        learned policy for the current queue state and dispatches if
        the policy (or the hard safety cap) says to."""
        if not self.queue:
            return

        num_waiting = len(self.queue)
        oldest_wait_minutes = (time.time() - self.queue[0]["join_time"]) / 60

        action = self.coordinator.decide(num_waiting, oldest_wait_minutes)
        if oldest_wait_minutes >= HARD_WAIT_CAP_MINUTES:
            action = "dispatch"

        if action == "dispatch":
            group = self.queue[:MAX_CAPACITY]
            self._dispatch_group(group)

    def _dispatch_group(self, group: list):
        group_size = len(group)
        fare_each = FARE_FOR_GROUP_SIZE[group_size]
        names = [s["name"] for s in group]

        result = {
            "status": "matched",
            "group_members": names,
            "group_size": group_size,
            "fare_each": fare_each,
        }
        for student in group:
            self.results[student["id"]] = result

        self.dispatch_log.insert(0, {
            "time": time.strftime("%H:%M:%S"),
            "members": names,
            "fare_each": fare_each,
        })
        self.dispatch_log = self.dispatch_log[:15]

        remaining_ids = {s["id"] for s in group}
        self.queue = [s for s in self.queue if s["id"] not in remaining_ids]

    def get_status(self, student_id: str) -> dict:
        if student_id in self.results:
            return self.results[student_id]

        for i, s in enumerate(self.queue):
            if s["id"] == student_id:
                wait_minutes = (time.time() - s["join_time"]) / 60
                return {
                    "status": "waiting",
                    "position": i + 1,
                    "num_waiting": len(self.queue),
                    "wait_minutes": round(wait_minutes, 1),
                }

        return {"status": "unknown"}

    def admin_snapshot(self) -> dict:
        return {
            "queue": [
                {"name": s["name"], "wait_minutes": round((time.time() - s["join_time"]) / 60, 1)}
                for s in self.queue
            ],
            "recent_dispatches": self.dispatch_log,
        }

    def simulate_student(self, name: str = None):
        """Debug/demo helper: add a fake student instantly, useful when
        testing solo (e.g. for a viva) without real classmates online."""
        import random
        fake_name = name or random.choice(
            ["Kavindi", "Nuhansa", "Mithara", "Chathura", "Dilki", "Ravindu"]
        )
        return self.add_student(fake_name)
