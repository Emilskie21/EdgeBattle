from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from game.paths import repo_root


@dataclass(frozen=True)
class ScoreEntry:
    name: str
    hp_remaining: int
    score: int
    timestamp: datetime


class LeaderboardDB:
    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or (repo_root() / "data" / "leaderboard.sqlite3")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    hp_remaining INTEGER NOT NULL,
                    score INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def insert_score(self, entry: ScoreEntry) -> int:
        ts = entry.timestamp.isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO scores (name, hp_remaining, score, timestamp) VALUES (?, ?, ?, ?)",
                (entry.name, entry.hp_remaining, entry.score, ts),
            )
            conn.commit()
            return int(cur.lastrowid or 0)

    def fetch_scores(self, limit: int = 50) -> list[sqlite3.Row]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id, name, hp_remaining, score, timestamp
                FROM scores
                ORDER BY score DESC, timestamp ASC, id ASC
                LIMIT ?
                """,
                (int(limit),),
            )
            return list(cur.fetchall())

    def fetch_total_count(self) -> int:
        with self._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) AS c FROM scores")
            row = cur.fetchone()
            return int(row["c"] if row else 0)

    def fetch_rank_for_id(self, row_id: int) -> int:
        if row_id <= 0:
            return 0
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id
                FROM scores
                ORDER BY score DESC, timestamp ASC, id ASC
                """,
            )
            ids = [int(r["id"]) for r in cur.fetchall()]
        try:
            return ids.index(int(row_id)) + 1
        except ValueError:
            return 0


def now_manila() -> datetime:
    # Manila is UTC+8 and does not observe DST.
    return datetime.now(timezone(timedelta(hours=8)))

