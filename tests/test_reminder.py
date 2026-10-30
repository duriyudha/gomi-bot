from datetime import datetime
from pathlib import Path

import pytest

from app.reminder import month_key, send_reminders
from app.schedule import JST, load_schedule
from app.store import Store

ROOT = Path(__file__).resolve().parent.parent

# 2026-11-02 is a Monday, so tomorrow (Tue) is 家庭ごみ.
MONDAY_8PM = datetime(2026, 11, 2, 20, 0, tzinfo=JST)
# 2026-11-07 is a Saturday, so tomorrow (Sun) has nothing.
SATURDAY_8PM = datetime(2026, 11, 7, 20, 0, tzinfo=JST)


@pytest.fixture
def schedule():
    return load_schedule(ROOT / "schedule.yml")


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.db")
    for uid in ("U1", "U2", "U3"):
        s.add_subscriber(uid)
    return s


class FakePush:
    def __init__(self):
        self.sent = []

    def __call__(self, user_id, text):
        self.sent.append((user_id, text))


def test_sends_to_all_subscribers(schedule, store):
    push = FakePush()
    assert send_reminders(schedule, store, push, now=MONDAY_8PM) == 3
    assert [u for u, _ in push.sent] == ["U1", "U2", "U3"]
    assert push.sent[0][1] == "明日は家庭ごみの日です。朝8:30までに出してください"
    assert store.push_count("2026-11") == 3


def test_skips_when_nothing_tomorrow(schedule, store):
    push = FakePush()
    assert send_reminders(schedule, store, push, now=SATURDAY_8PM) == 0
    assert push.sent == []
    assert store.push_count("2026-11") == 0


def test_cap_stops_in_the_middle(schedule, store):
    for _ in range(188):
        store.add_push("2026-11")
    push = FakePush()
    # 188 used, limit 190 -> only 2 of the 3 users get it.
    assert send_reminders(schedule, store, push, now=MONDAY_8PM) == 2
    assert store.push_count("2026-11") == 190


def test_cap_reached_sends_nothing(schedule, store):
    for _ in range(190):
        store.add_push("2026-11")
    push = FakePush()
    assert send_reminders(schedule, store, push, now=MONDAY_8PM) == 0
    assert push.sent == []


def test_cap_resets_next_month(schedule, store):
    for _ in range(190):
        store.add_push("2026-10")
    push = FakePush()
    assert send_reminders(schedule, store, push, now=MONDAY_8PM) == 3


def test_failed_push_is_not_counted(schedule, store):
    def push(user_id, text):
        if user_id == "U2":
            raise RuntimeError("LINE error")

    assert send_reminders(schedule, store, push, now=MONDAY_8PM) == 2
    assert store.push_count("2026-11") == 2


def test_month_key_uses_jst():
    # 2026-10-31 15:30 UTC is already 2026-11-01 00:30 in Japan.
    from datetime import timezone
    assert month_key(datetime(2026, 10, 31, 15, 30, tzinfo=timezone.utc)) == "2026-11"


def test_unfollow_removes_subscriber(store):
    store.remove_subscriber("U2")
    assert store.subscribers() == ["U1", "U3"]
    store.add_subscriber("U1")  # adding twice is fine
    assert store.subscribers() == ["U1", "U3"]
