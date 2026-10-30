"""Nightly reminder: push "明日は〇〇の日です" to every subscriber.

The function that actually sends a LINE message is passed in (push),
so this file has no LINE imports and is easy to test.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

from app.messages import reminder_text
from app.schedule import JST, Schedule
from app.store import Store

log = logging.getLogger(__name__)

# LINE free plan allows 200 push messages a month. Stop a little before that.
MONTHLY_PUSH_LIMIT = 190


def month_key(now: datetime) -> str:
    return now.astimezone(JST).strftime("%Y-%m")


def send_reminders(
    schedule: Schedule,
    store: Store,
    push: Callable[[str, str], None],
    now: datetime | None = None,
    limit: int = MONTHLY_PUSH_LIMIT,
) -> int:
    """Send tomorrow's reminder. Returns how many messages were sent."""
    now = (now or datetime.now(JST)).astimezone(JST)
    tomorrow = now.date() + timedelta(days=1)

    text = reminder_text(schedule, tomorrow)
    if text is None:
        log.info("No collection on %s, no reminder", tomorrow)
        return 0

    month = month_key(now)
    sent = 0
    for user_id in store.subscribers():
        count = store.push_count(month)
        if count >= limit:
            log.warning("Monthly push limit reached (%d/%d), skipping the rest", count, limit)
            break
        try:
            push(user_id, text)
        except Exception:
            log.exception("Push to %s failed", user_id)
            continue
        store.add_push(month)
        sent += 1

    log.info("Reminder for %s: sent %d, pushes in %s: %d", tomorrow, sent, month, store.push_count(month))
    return sent
