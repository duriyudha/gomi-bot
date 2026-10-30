"""Builds the Japanese text the bot sends. No LINE or FastAPI imports."""

from __future__ import annotations

from datetime import date, timedelta

from app.schedule import WEEKDAY_JA, Schedule

HELP_TEXT = (
    "ごみ出しの日をお知らせします。\n"
    "次のことばを送ってください。\n"
    "・今日\n"
    "・明日\n"
    "・今週"
)


def _label(d: date) -> str:
    return f"{d.month}/{d.day}({WEEKDAY_JA[d.weekday()]})"


def _join(items: list[str]) -> str:
    return "、".join(items)


def day_text(schedule: Schedule, d: date, word: str) -> str:
    """Reply for 「今日」 or 「明日」. word is "今日" or "明日"."""
    items = schedule.items_on(d)
    if items:
        return (
            f"{word} {_label(d)} は{_join(items)}の日です。\n"
            f"朝{schedule.deadline}までに出してください。"
        )
    ex = schedule.exception_for(d)
    if ex and ex.note:
        return f"{word} {_label(d)} は{ex.note}のため収集はありません。"
    return f"{word} {_label(d)} は収集はありません。"


def week_text(schedule: Schedule, d: date) -> str:
    lines = [f"今週のごみ出し（{schedule.area}）"]
    for day, items in schedule.week_of(d):
        lines.append(f"{_label(day)} {_join(items) if items else 'なし'}")
    return "\n".join(lines)


def reminder_text(schedule: Schedule, tomorrow: date) -> str | None:
    """Text for the 20:00 reminder, or None if nothing goes out tomorrow."""
    items = schedule.items_on(tomorrow)
    if not items:
        return None
    return f"明日は{_join(items)}の日です。朝{schedule.deadline}までに出してください"


def reply_for(schedule: Schedule, text: str, today: date) -> str:
    """Pick the reply for a message the user sent."""
    command = text.strip()
    if command == "今日":
        return day_text(schedule, today, "今日")
    if command == "明日":
        return day_text(schedule, today + timedelta(days=1), "明日")
    if command == "今週":
        return week_text(schedule, today)
    return HELP_TEXT
