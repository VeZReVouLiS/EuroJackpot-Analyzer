"""EuroJackpot game rules that changed over time (affect statistics)."""
from __future__ import annotations

from datetime import date, timedelta

FIRST_DRAW = date(2012, 3, 23)
MAIN_MAX = 50
MAIN_COUNT = 5
EURO_COUNT = 2
COLUMN_PRICE = 2.5      # EUR per column in Greece (2.00 base + 0.50 add-on)
MAX_COLUMNS = 12

# (from_date, euro_max) - the euro numbers pool grew twice
_EURO_RULES = [
    (date(2012, 3, 23), 8),
    (date(2014, 10, 10), 10),
    (date(2022, 3, 25), 12),
]
TUESDAY_FROM = date(2022, 3, 29)


def euro_max(d: date) -> int:
    result = _EURO_RULES[0][1]
    for start, mx in _EURO_RULES:
        if d >= start:
            result = mx
    return result


def current_euro_max() -> int:
    return _EURO_RULES[-1][1]


DRAW_TIME_LOCAL = (21, 15)   # draws are held ~21:00 (Helsinki, same clock as Greece); results shortly after


def next_draw_dates(now, n: int = 3) -> list[date]:
    """The next n draw dates (Fri, plus Tue since 2022-03-29). `now` = local datetime.

    On a draw day before the draw (21:15) that day is still the next draw."""
    out: list[date] = []
    d = now.date()
    if (now.hour, now.minute) >= DRAW_TIME_LOCAL:
        d += timedelta(days=1)
    while len(out) < n:
        if d.weekday() == 4 or (d.weekday() == 1 and d >= TUESDAY_FROM):
            out.append(d)
        d += timedelta(days=1)
    return out


def candidate_dates(start: date, end: date):
    """Every date on which a draw may have taken place (Fri, plus Tue since 2022)."""
    d = max(start, FIRST_DRAW)
    while d <= end:
        wd = d.weekday()
        if wd == 4 or (wd == 1 and d >= TUESDAY_FROM):
            yield d
        d += timedelta(days=1)
