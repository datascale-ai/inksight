"""
Generate invitation codes into InkSight SQLite DB.

Usage (PowerShell):
  cd D:\Codefield\inksight\backend
  python .\scripts\generate_invite_codes.py --count 10

This script inserts rows into table `invitation_codes`:
  - code (TEXT PRIMARY KEY)
  - is_used (0/1)
  - generated_at (DEFAULT CURRENT_TIMESTAMP)
  - used_by_user_id (NULL)
"""

from __future__ import annotations

import argparse
import os
import secrets
import sqlite3
from typing import Iterable


ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/1/O/I


def _db_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(here, ".."))
    return os.path.join(backend_dir, "inksight.db")


def _gen_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS invitation_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            is_used INTEGER DEFAULT 0,
            generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            used_by_user_id INTEGER,
            FOREIGN KEY (used_by_user_id) REFERENCES users(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_invitation_codes_used_by ON invitation_codes(used_by_user_id)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_invitation_codes_code ON invitation_codes(code)"
    )
    conn.commit()


def insert_codes(conn: sqlite3.Connection, codes: Iterable[str]) -> list[str]:
    inserted: list[str] = []
    for code in codes:
        cur = conn.execute(
            "INSERT OR IGNORE INTO invitation_codes (code, is_used, used_by_user_id) VALUES (?, 0, NULL)",
            (code,),
        )
        if cur.rowcount and cur.rowcount > 0:
            inserted.append(code)
    conn.commit()
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate invitation codes into inksight.db")
    parser.add_argument("--count", type=int, default=10, help="How many codes to generate (default: 10)")
    parser.add_argument("--length", type=int, default=8, help="Code length (default: 8)")
    parser.add_argument("--db", type=str, default="", help="Path to inksight.db (optional)")
    args = parser.parse_args()

    count = max(1, int(args.count))
    length = max(4, int(args.length))
    db_path = args.db.strip() or _db_path()

    conn = sqlite3.connect(db_path)
    try:
        _ensure_table(conn)

        # Try a bit more than needed to avoid collisions.
        target = count
        attempts = 0
        inserted_total: list[str] = []
        while len(inserted_total) < target and attempts < target * 10:
            remaining = target - len(inserted_total)
            batch = [_gen_code(length) for _ in range(max(remaining, 5))]
            inserted = insert_codes(conn, batch)
            inserted_total.extend(inserted)
            attempts += len(batch)

        for code in inserted_total[:target]:
            print(code)

        if len(inserted_total) < target:
            raise SystemExit(f"Only inserted {len(inserted_total)} codes (requested {target}). Try again.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

