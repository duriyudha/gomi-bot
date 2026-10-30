from datetime import date, timedelta
from pathlib import Path

import pytest

from app.messages import day_text, reminder_text, reply_for, week_text, HELP_TEXT
from app.schedule import load_schedule, parse_schedule

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def schedule():
    return load_schedule(ROOT / "schedule.yml")


# --- weekly rules ---

@pytest.mark.parametrize(
    "d, expected",
    [
        (date(2026, 11, 2), []),                          # Mon
        (date(2026, 11, 3), ["家庭ごみ"]),                 # Tue
        (date(2026, 11, 5), ["プラスチック資源"]),          # Thu
        (date(2026, 11, 6), ["家庭ごみ"]),                 # Fri
        (date(2026, 11, 7), ["缶・びん・ペットボトル等"]),  # Sat
        (date(2026, 11, 8), []),                          # Sun
    ],
)
def test_weekly(schedule, d, expected):
    assert schedule.items_on(d) == expected


# --- nth weekday ---

def test_paper_on_2nd_and_4th_wednesday(schedule):
    # Nov 2026 Wednesdays: 4, 11, 18, 25
    assert schedule.items_on(date(2026, 11, 4)) == []
    assert schedule.items_on(date(2026, 11, 11)) == ["紙類"]
    assert schedule.items_on(date(2026, 11, 18)) == []
    assert schedule.items_on(date(2026, 11, 25)) == ["紙類"]


def test_month_with_five_wednesdays(schedule):
    # Sep 2026 Wednesdays: 2, 9, 16, 23, 30
    weds = [date(2026, 9, d) for d in (2, 9, 16, 23, 30)]
    assert all(d.weekday() == 2 for d in weds)
    paper = [d.day for d in weds if "紙類" in schedule.items_on(d)]
    assert paper == [9, 23]  # not the 5th (30th)


def test_month_starting_on_wednesday(schedule):
    # Jul 2026 starts on Wed: 1, 8, 15, 22, 29
    assert date(2026, 7, 1).weekday() == 2
    assert "紙類" in schedule.items_on(date(2026, 7, 8))
    assert "紙類" in schedule.items_on(date(2026, 7, 22))
    assert "紙類" not in schedule.items_on(date(2026, 7, 29))


def test_fifth_weekday_rule():
    s = parse_schedule({"rules": [{"name": "x", "type": "nth_weekday", "weekday": "水", "nth": [5]}]})
    assert s.items_on(date(2026, 9, 30)) == ["x"]
    assert s.items_on(date(2026, 11, 25)) == []  # Nov 2026 has only 4 Wednesdays


# --- exceptions ---

def test_new_year_holiday(schedule):
    assert schedule.items_on(date(2026, 12, 29)) == []  # Tue, normally 家庭ごみ
    assert schedule.items_on(date(2027, 1, 1)) == []    # Fri, normally 家庭ごみ
    assert schedule.items_on(date(2027, 1, 2)) == []    # Sat, normally 缶・びん
    assert schedule.items_on(date(2026, 12, 26)) == ["缶・びん・ペットボトル等"]  # before
    assert schedule.items_on(date(2027, 1, 5)) == ["家庭ごみ"]                   # after


def test_single_date_exception():
    s = parse_schedule({
        "rules": [{"name": "家庭ごみ", "type": "weekly", "weekdays": ["tue"]}],
        "exceptions": [{"date": "2026-11-03", "note": "臨時"}],
    })
    assert s.items_on(date(2026, 11, 3)) == []
    assert s.items_on(date(2026, 11, 10)) == ["家庭ごみ"]


def test_exception_message(schedule):
    assert "年末年始" in day_text(schedule, date(2026, 12, 29), "今日")


# --- "tomorrow" across boundaries ---

@pytest.mark.parametrize(
    "today, expected",
    [
        (date(2026, 10, 31), []),                  # Sat -> Sun 11/1
        (date(2026, 11, 30), ["家庭ごみ"]),         # Mon -> Tue 12/1
        (date(2026, 2, 28), []),                   # Sat -> Sun 3/1
        (date(2026, 3, 31), []),                   # Tue -> Wed 4/1, 1st Wed (no 紙類)
        (date(2026, 4, 30), ["家庭ごみ"]),          # Thu -> Fri 5/1
        (date(2026, 12, 31), []),                  # year boundary, inside holiday
        (date(2027, 1, 4), ["家庭ごみ"]),           # Mon -> Tue 1/5, first day after holiday
    ],
)
def test_tomorrow_across_month(schedule, today, expected):
    assert schedule.items_on(today + timedelta(days=1)) == expected


def test_reply_tomorrow_across_month(schedule):
    text = reply_for(schedule, "明日", date(2026, 11, 30))
    assert "12/1(火)" in text and "家庭ごみ" in text


# --- week ---

def test_week_is_monday_to_sunday(schedule):
    week = schedule.week_of(date(2026, 10, 30))  # Fri
    assert week[0][0] == date(2026, 10, 26)
    assert week[-1][0] == date(2026, 11, 1)
    assert [d.weekday() for d, _ in week] == list(range(7))


def test_week_text(schedule):
    text = week_text(schedule, date(2026, 11, 11))
    assert "11/11(水) 紙類" in text
    assert "11/9(月) なし" in text


# --- messages ---

def test_reminder_text(schedule):
    assert reminder_text(schedule, date(2026, 11, 3)) == "明日は家庭ごみの日です。朝8:30までに出してください"
    assert reminder_text(schedule, date(2026, 11, 8)) is None


def test_unknown_command_gives_help(schedule):
    assert reply_for(schedule, "こんにちは", date(2026, 11, 3)) == HELP_TEXT
    assert reply_for(schedule, " 今日 ", date(2026, 11, 3)).startswith("今日")


# --- bad yaml ---

def test_unknown_rule_type_fails():
    with pytest.raises(ValueError):
        parse_schedule({"rules": [{"name": "x", "type": "monthly"}]})
