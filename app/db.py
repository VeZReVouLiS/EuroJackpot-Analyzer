from __future__ import annotations

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
    source TEXT
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
        """draws: dict(date='YYYY-MM-DD', main=[5], euro=[2], source=str). Returns rows written."""
        rows = []
        for d in draws:
            m = sorted(d["main"])
            e = sorted(d["euro"])
            rows.append((d["date"], *m, *e, d.get("source", "")))
        with self._tx() as c:
            c.executemany(
                "INSERT INTO draws VALUES(?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(draw_date) DO UPDATE SET n1=excluded.n1,n2=excluded.n2,n3=excluded.n3,"
                "n4=excluded.n4,n5=excluded.n5,e1=excluded.e1,e2=excluded.e2,source=excluded.source",
                rows,
            )
        return len(rows)

    def all_draws(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM draws ORDER BY draw_date")
            return [
                {
                    "date": r["draw_date"],
                    "main": [r["n1"], r["n2"], r["n3"], r["n4"], r["n5"]],
                    "euro": [r["e1"], r["e2"]],
                    "source": r["source"],
                }
                for r in cur.fetchall()
            ]

    def count(self) -> int:
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM draws").fetchone()[0]

    def last_date(self) -> str | None:
        with self._lock:
            return self._conn.execute("SELECT MAX(draw_date) FROM draws").fetchone()[0]

    def existing_dates(self) -> set[str]:
        with self._lock:
            return {r[0] for r in self._conn.execute("SELECT draw_date FROM draws")}

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
