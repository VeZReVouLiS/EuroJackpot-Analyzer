from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from .paths import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS draws(
    draw_date TEXT PRIMARY KEY,
    n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
    e1 INTEGER, e2 INTEGER,
    source TEXT,
    details TEXT
);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


class Database:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else data_dir() / "eurojackpot.db"
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(draws)")}
            if "details" not in cols:            # migrate databases created by v1.0
                self._conn.execute("ALTER TABLE draws ADD COLUMN details TEXT")
            self._conn.commit()

    @contextmanager
    def _tx(self):
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def upsert_draws(self, draws: list[dict]) -> int:
        """draws: dict(date, main=[5], euro=[2], source, details=dict|None). Existing details are kept
        when the new record has none."""
        rows = []
        for d in draws:
            det = d.get("details")
            rows.append((d["date"], *sorted(d["main"]), *sorted(d["euro"]), d.get("source", ""),
                         json.dumps(det, ensure_ascii=False) if det else None))
        with self._tx() as c:
            c.executemany(
                "INSERT INTO draws VALUES(?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(draw_date) DO UPDATE SET n1=excluded.n1,n2=excluded.n2,n3=excluded.n3,"
                "n4=excluded.n4,n5=excluded.n5,e1=excluded.e1,e2=excluded.e2,source=excluded.source,"
                "details=COALESCE(excluded.details, draws.details)",
                rows,
            )
        return len(rows)

    @staticmethod
    def _row(r, with_details: bool) -> dict:
        d = {
            "date": r["draw_date"],
            "main": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]],
            "euro": [r["e1"], r["e2"]],
            "source": r["source"],
        }
        if with_details:
            d["details"] = json.loads(r["details"]) if r["details"] else None
        return d

    def all_draws(self, with_details: bool = False) -> list[dict]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM draws ORDER BY draw_date")
            return [self._row(r, with_details) for r in cur.fetchall()]

    def get_draw(self, date_str: str) -> dict | None:
        with self._lock:
            r = self._conn.execute("SELECT * FROM draws WHERE draw_date=?", (date_str,)).fetchone()
            return self._row(r, True) if r else None

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]

    def last_date(self) -> str | None:
        with self._lock:
            return self._conn.execute("SELECT MAX(draw_date) FROM draws").fetchone()[0]

    def existing_dates(self) -> set[str]:
        with self._lock:
            return {r[0] for r in self._conn.execute("SELECT draw_date FROM draws")}

    def dates_missing_details(self) -> set[str]:
        with self._lock:
            return {r[0] for r in self._conn.execute("SELECT draw_date FROM draws WHERE details IS NULL")}

    def delete_after(self, date_str: str) -> None:
        with self._tx() as c:
            c.execute("DELETE FROM draws WHERE draw_date > ?", (date_str,))

    # meta / settings -------------------------------------------------
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            r = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
            return r[0] if r else default

    def set_meta(self, key: str, value: str) -> None:
        with self._tx() as c:
            c.execute(
                "INSERT INTO meta VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
