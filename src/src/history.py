"""NetDrop — Historique SQLite des transferts."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import HISTORY_DB


@dataclass
class TransferRecord:
    id: int
    timestamp: str
    direction: str
    filename: str
    size_bytes: int
    peer_identity: str
    peer_ip: str
    status: str
    duration_sec: float
    speed_bps: float
    local_path: Optional[str] = None
    error_msg: Optional[str] = None

    @property
    def direction_icon(self) -> str:
        return "↑" if self.direction == "sent" else "↓"

    @property
    def status_icon(self) -> str:
        return {"success": "✓", "failed": "✗", "checksum_fail": "⚠"}.get(self.status, "?")

    @property
    def human_size(self) -> str:
        n = self.size_bytes
        for u in ("B", "KB", "MB", "GB"):
            if n < 1024: return f"{n:.1f} {u}"
            n /= 1024
        return f"{n:.1f} TB"

    @property
    def human_speed(self) -> str:
        b = self.speed_bps
        if b >= 1_048_576: return f"{b/1_048_576:.1f} MB/s"
        if b >= 1024: return f"{b/1024:.1f} KB/s"
        return f"{b:.0f} B/s"

    @property
    def human_duration(self) -> str:
        s = int(self.duration_sec)
        return f"{s//60}m {s%60}s" if s >= 60 else f"{s}s"

    @property
    def short_date(self) -> str:
        try: return datetime.fromisoformat(self.timestamp).strftime("%d/%m %H:%M")
        except Exception: return self.timestamp[:16]


_DDL = """
CREATE TABLE IF NOT EXISTS transfers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT NOT NULL,
    direction     TEXT NOT NULL,
    filename      TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    peer_identity TEXT NOT NULL DEFAULT '',
    peer_ip       TEXT NOT NULL DEFAULT '',
    status        TEXT NOT NULL DEFAULT 'success',
    duration_sec  REAL NOT NULL DEFAULT 0.0,
    speed_bps     REAL NOT NULL DEFAULT 0.0,
    local_path    TEXT,
    error_msg     TEXT
);
"""


class HistoryDB:
    def __init__(self, db_path: Path = HISTORY_DB):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c: c.execute(_DDL)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def log(self, *, direction: str, filename: str, size_bytes: int,
            peer_identity: str, peer_ip: str, status: str,
            duration_sec: float, speed_bps: float,
            local_path: Optional[str] = None, error_msg: Optional[str] = None) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO transfers (timestamp,direction,filename,size_bytes,peer_identity,"
                "peer_ip,status,duration_sec,speed_bps,local_path,error_msg) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (datetime.now().isoformat(), direction, filename, size_bytes,
                 peer_identity, peer_ip, status, duration_sec, speed_bps, local_path, error_msg),
            )
            return cur.lastrowid

    def get_all(self, limit: int = 500, offset: int = 0) -> list[TransferRecord]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM transfers ORDER BY id DESC LIMIT ? OFFSET ?",
                             (limit, offset)).fetchall()
        return [TransferRecord(**dict(r)) for r in rows]

    def search(self, query: str, limit: int = 200) -> list[TransferRecord]:
        q = f"%{query}%"
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM transfers WHERE filename LIKE ? OR peer_identity LIKE ? "
                "OR peer_ip LIKE ? ORDER BY id DESC LIMIT ?", (q, q, q, limit)).fetchall()
        return [TransferRecord(**dict(r)) for r in rows]

    def get_stats(self) -> dict:
        with self._conn() as c:
            r = c.execute(
                "SELECT COUNT(*) total,"
                "SUM(CASE WHEN direction='sent' THEN 1 ELSE 0 END) sent_count,"
                "SUM(CASE WHEN direction='received' THEN 1 ELSE 0 END) recv_count,"
                "SUM(CASE WHEN status='success' THEN size_bytes ELSE 0 END) total_bytes,"
                "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) success_count "
                "FROM transfers").fetchone()
        return dict(r) if r else {}

    def delete(self, record_id: int) -> None:
        with self._conn() as c: c.execute("DELETE FROM transfers WHERE id=?", (record_id,))

    def clear(self) -> int:
        with self._conn() as c:
            cur = c.execute("DELETE FROM transfers"); return cur.rowcount

    def trim(self, max_entries: int) -> None:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM transfers").fetchone()[0]
            if total > max_entries:
                c.execute("DELETE FROM transfers WHERE id IN "
                          "(SELECT id FROM transfers ORDER BY id ASC LIMIT ?)",
                          (total - max_entries,))

    def count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM transfers").fetchone()[0]

    def export_csv(self, path: Path) -> int:
        records = self.get_all(limit=100_000)
        with open(path, "w", encoding="utf-8") as f:
            f.write("id,timestamp,direction,filename,size_bytes,peer_identity,"
                    "peer_ip,status,duration_sec,speed_bps,local_path,error_msg\n")
            for r in records:
                row = [str(r.id), r.timestamp, r.direction, r.filename,
                       str(r.size_bytes), r.peer_identity, r.peer_ip,
                       r.status, f"{r.duration_sec:.2f}", f"{r.speed_bps:.0f}",
                       r.local_path or "", r.error_msg or ""]
                f.write(",".join(f'"{v}"' for v in row) + "\n")
        return len(records)


history_db = HistoryDB()