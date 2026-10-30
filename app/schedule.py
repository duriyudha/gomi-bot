"""Garbage collection schedule logic.

This module only knows about dates and schedule.yml.
It does not import LINE or FastAPI, so it can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

JST = ZoneInfo("Asia/Tokyo")

WEEKDAYS = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
    "月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6,
}
WEEKDAY_JA = "月火水木金土日"


def today_jst() -> date:
    return datetime.now(JST).date()


def _parse_weekday(value: str) -> int:
    key = str(value).strip().lower()
    if key not in WEEKDAYS:
        raise ValueError(f"unknown weekday: {value!r}")
    return WEEKDAYS[key]


def _parse_date(value) -> date:
    # PyYAML already turns 2026-12-29 into a date, but accept strings too.
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass(frozen=True)
class WeeklyRule:
    name: str
    weekdays: frozenset[int]

    def matches(self, d: date) -> bool:
        return d.weekday() in self.weekdays


@dataclass(frozen=True)
class NthWeekdayRule:
    name: str
    weekday: int
    nth: frozenset[int]

    def matches(self, d: date) -> bool:
        # Day 1-7 is the 1st week, 8-14 the 2nd, and so on.
        return d.weekday() == self.weekday and (d.day - 1) // 7 + 1 in self.nth


@dataclass(frozen=True)
class NoCollection:
    start: date
    end: date
    note: str = ""

    def covers(self, d: date) -> bool:
        return self.start <= d <= self.end


@dataclass
class Schedule:
    area: str
    deadline: str
    rules: list[WeeklyRule | NthWeekdayRule]
    exceptions: list[NoCollection] = field(default_factory=list)

    def exception_for(self, d: date) -> NoCollection | None:
        for ex in self.exceptions:
            if ex.covers(d):
                return ex
        return None

    def items_on(self, d: date) -> list[str]:
        """Names of the garbage types collected on day d (empty if none)."""
        if self.exception_for(d):
            return []
        return [rule.name for rule in self.rules if rule.matches(d)]

    def week_of(self, d: date) -> list[tuple[date, list[str]]]:
        """Monday to Sunday of the week that contains d."""
        monday = d - timedelta(days=d.weekday())
        days = [monday + timedelta(days=i) for i in range(7)]
        return [(day, self.items_on(day)) for day in days]


def _parse_rule(raw: dict) -> WeeklyRule | NthWeekdayRule:
    name = raw["name"]
    kind = raw.get("type")
    if kind == "weekly":
        weekdays = frozenset(_parse_weekday(w) for w in raw["weekdays"])
        return WeeklyRule(name=name, weekdays=weekdays)
    if kind == "nth_weekday":
        nth = frozenset(int(n) for n in raw["nth"])
        if not nth or not all(1 <= n <= 5 for n in nth):
            raise ValueError(f"{name}: nth must be between 1 and 5")
        return NthWeekdayRule(name=name, weekday=_parse_weekday(raw["weekday"]), nth=nth)
    raise ValueError(f"{name}: unknown rule type {kind!r}")


def _parse_exception(raw: dict) -> NoCollection:
    if "date" in raw:
        start = end = _parse_date(raw["date"])
    else:
        start, end = _parse_date(raw["from"]), _parse_date(raw["to"])
    if end < start:
        raise ValueError(f"exception ends before it starts: {raw}")
    return NoCollection(start=start, end=end, note=raw.get("note", ""))


def parse_schedule(data: dict) -> Schedule:
    return Schedule(
        area=data.get("area", ""),
        deadline=str(data.get("deadline", "8:30")),
        rules=[_parse_rule(r) for r in data.get("rules", [])],
        exceptions=[_parse_exception(e) for e in data.get("exceptions") or []],
    )


def load_schedule(path: str | Path) -> Schedule:
    with open(path, encoding="utf-8") as f:
        return parse_schedule(yaml.safe_load(f))
