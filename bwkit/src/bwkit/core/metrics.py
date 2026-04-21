"""SQLite-backed per-user metrics.

Per-user isolation is automatic: the DB lives at ~/.bwkit/bwkit.db, owned
by the user's OS account. No raw inputs/outputs are stored — only an
input_hash for retry grouping.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from .config import ensure_home


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def sha256_of_canonical_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass
class Call:
    ts: str
    tool: str
    caller: str
    transport: str
    latency_ms: int
    status: str
    error_code: Optional[str]
    error_class: Optional[str]
    input_hash: Optional[str]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
  id          INTEGER PRIMARY KEY,
  ts          TEXT NOT NULL,
  tool        TEXT NOT NULL,
  caller      TEXT NOT NULL,
  transport   TEXT NOT NULL,
  latency_ms  INTEGER NOT NULL,
  status      TEXT NOT NULL,
  error_code  TEXT,
  error_class TEXT,
  input_hash  TEXT
);
CREATE INDEX IF NOT EXISTS ix_calls_ts        ON calls(ts);
CREATE INDEX IF NOT EXISTS ix_calls_tool_ts   ON calls(tool, ts);
CREATE INDEX IF NOT EXISTS ix_calls_status_ts ON calls(status, ts);
"""


class Metrics:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        resolved = Path(db_path) if db_path is not None else (ensure_home() / "bwkit.db")
        self.db_path = resolved
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def record(self, call: Call) -> None:
        self._conn.execute(
            "INSERT INTO calls (ts, tool, caller, transport, latency_ms, status, error_code, error_class, input_hash)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                call.ts, call.tool, call.caller, call.transport,
                call.latency_ms, call.status, call.error_code,
                call.error_class, call.input_hash,
            ),
        )

    # ------------- queries -------------

    def recent(self, *, limit: int = 50, tool: Optional[str] = None) -> list[dict]:
        q = "SELECT * FROM calls"
        params: list[Any] = []
        if tool:
            q += " WHERE tool = ?"
            params.append(tool)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def summary(self, *, since: Optional[str] = None, tool: Optional[str] = None) -> list[dict]:
        """Per-tool counts, success rate, p50/p95 latency since `since` (ISO8601)."""
        where, params = [], []
        if since:
            where.append("ts >= ?"); params.append(since)
        if tool:
            where.append("tool = ?"); params.append(tool)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        rows = self._conn.execute(
            f"SELECT tool, status, latency_ms FROM calls{where_sql}", params
        ).fetchall()
        bucket: dict[str, dict[str, Any]] = {}
        for r in rows:
            b = bucket.setdefault(r["tool"], {"tool": r["tool"], "ok": 0, "error": 0, "latencies": []})
            b[r["status"]] = b.get(r["status"], 0) + 1
            b["latencies"].append(int(r["latency_ms"]))
        out = []
        for b in bucket.values():
            lats = sorted(b["latencies"])
            n = len(lats)
            total = b["ok"] + b["error"]
            out.append({
                "tool": b["tool"],
                "total": total,
                "ok": b["ok"],
                "error": b["error"],
                "success_rate": (b["ok"] / total) if total else None,
                "p50_ms": lats[max(0, int(n * 0.50) - 1)] if n else None,
                "p95_ms": lats[max(0, int(n * 0.95) - 1)] if n else None,
            })
        out.sort(key=lambda x: x["tool"])
        return out

    def errors(self, *, since: Optional[str] = None) -> list[dict]:
        """Grouped error counts by (tool, error_code)."""
        where, params = ["status = 'error'"], []
        if since:
            where.append("ts >= ?"); params.append(since)
        where_sql = " WHERE " + " AND ".join(where)
        rows = self._conn.execute(
            f"SELECT tool, error_code, COUNT(*) AS count FROM calls{where_sql}"
            " GROUP BY tool, error_code ORDER BY count DESC",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def iso_since(expr: str) -> str:
    """Parse '24h' / '7d' / '30m' into an ISO8601 UTC timestamp."""
    if not expr:
        return ""
    unit = expr[-1].lower()
    n = int(expr[:-1])
    delta = {
        "s": timedelta(seconds=n),
        "m": timedelta(minutes=n),
        "h": timedelta(hours=n),
        "d": timedelta(days=n),
    }.get(unit)
    if delta is None:
        raise ValueError(f"unrecognized duration: {expr!r} (use e.g. 24h, 7d, 30m)")
    ts = datetime.now(timezone.utc) - delta
    return ts.isoformat(timespec="milliseconds").replace("+00:00", "Z")
