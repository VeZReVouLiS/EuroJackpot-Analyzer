"""Import draws from user supplied CSV / JSON files (flexible column detection)."""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%y", "%d.%m.%y", "%Y%m%d")


def parse_date(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}T", s):  # ISO timestamp
        s = s[:10]
    # drop weekday names etc.: keep the first date-looking token
    m = re.search(r"\d{1,4}[./-]\d{1,2}[./-]\d{1,4}|\d{8}", s)
    if m:
        s = m.group(0)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _valid(main: list[int], euro: list[int]) -> bool:
    return (
        len(main) == 5
        and len(set(main)) == 5
        and all(1 <= n <= 50 for n in main)
        and len(euro) == 2
        and len(set(euro)) == 2
        and all(1 <= n <= 12 for n in euro)
    )


def _ints(value) -> list[int]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        out: list[int] = []
        for v in value:
            out.extend(_ints(v))
        return out
    return [int(x) for x in re.findall(r"\d+", str(value))]


def _record(rec) -> dict | None:
    """rec: dict or list (csv row). Returns draw dict or None."""
    d = None
    main: list[int] = []
    euro: list[int] = []
    if isinstance(rec, dict):
        flat: list[int] = []
        for k, v in rec.items():
            kl = str(k).lower()
            if d is None and ("date" in kl or "ημερ" in kl or kl in ("draw", "day")):
                d = parse_date(v)
                if d:
                    continue
            if re.search(r"euro|bonus|star|extra|\be\d|^e\d", kl):
                euro.extend(_ints(v))
            elif re.search(r"main|number|num|winning|^n\d|^b\d|ball", kl):
                main.extend(_ints(v))
            elif not isinstance(v, str) or re.fullmatch(r"[\d\s,;|-]+", v):
                flat.extend(_ints(v))
        if not main and not euro:
            if len(flat) == 7:
                main, euro = flat[:5], flat[5:]
        elif main and not euro and len(main) == 7:
            main, euro = main[:5], main[5:]
        if d is None:  # any value that looks like a date
            for v in rec.values():
                d = parse_date(v)
                if d:
                    break
    else:
        cells = [str(c).strip() for c in rec]
        idx = next((i for i, c in enumerate(cells) if parse_date(c) and re.search(r"[./-]|\d{8}", c)), None)
        if idx is None:
            return None
        d = parse_date(cells[idx])
        nums = []
        for i, c in enumerate(cells):
            if i == idx:
                continue
            if re.fullmatch(r"\d{1,2}", c):
                nums.append(int(c))
            elif re.fullmatch(r"[\d\s,;|-]+", c) and re.search(r"\d\D+\d", c):
                nums.extend(_ints(c))
        if len(nums) >= 7:
            main, euro = nums[:5], nums[5:7]
    if not d:
        return None
    if main and euro and _valid(sorted(main), sorted(euro)):
        return {"date": d, "main": sorted(main), "euro": sorted(euro), "source": "import"}
    return None


def parse_text(text: str, filename: str = "") -> list[dict]:
    text = text.lstrip("﻿").strip()
    records: list = []
    if text[:1] in "[{" or filename.lower().endswith(".json"):
        data = json.loads(text)
        if isinstance(data, dict):
            for key in ("draws", "results", "data", "items", "rows"):
                if isinstance(data.get(key), list):
                    data = data[key]
                    break
            else:
                data = list(data.values()) if all(isinstance(v, dict) for v in data.values()) else [data]
        records = data
    else:
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect))
        # header row -> use DictReader semantic when first row has no date
        if rows and not any(parse_date(c) and re.search(r"[./-]|\d{8}", c) for c in rows[0]):
            header = rows[0]
            records = [dict(zip(header, r)) for r in rows[1:]]
        else:
            records = rows
    out: dict[str, dict] = {}
    for rec in records:
        if isinstance(rec, (list, tuple)) and rec and not isinstance(rec[0], (str, int, float)):
            continue
        r = _record(rec)
        if r:
            out[r["date"]] = r
    return sorted(out.values(), key=lambda x: x["date"])


def parse_file(path: str) -> list[dict]:
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "cp1253", "latin-1"):
        try:
            return parse_text(raw.decode(enc), path)
        except UnicodeDecodeError:
            continue
    return []
