#!/usr/bin/env python3
"""
Inspect SQLite cache for NULL/None-like values.

This script:
1) Lists tables in the cache DB.
2) For each table, prints columns and a few sample rows where
   JSON/text fields contain "null" (common encoding of None).
"""

import sqlite3
from pathlib import Path
from typing import List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "CircuitCollector" / "database" / "cache.db"


def list_tables(cur: sqlite3.Cursor) -> List[str]:
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    )
    return [row[0] for row in cur.fetchall()]


def table_columns(cur: sqlite3.Cursor, table: str) -> List[Tuple[str, str]]:
    cur.execute(f"PRAGMA table_info({table});")
    return [(row[1], row[2]) for row in cur.fetchall()]


def detect_json_like_columns(columns: List[Tuple[str, str]]) -> List[str]:
    json_cols = []
    for name, col_type in columns:
        t = (col_type or "").upper()
        if "TEXT" in t or "JSON" in t:
            json_cols.append(name)
    return json_cols


def main() -> None:
    db_path = DEFAULT_DB
    if not db_path.exists():
        print(f"[!] DB not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        tables = list_tables(cur)
        if not tables:
            print("[!] No tables found.")
            return

        print(f"DB: {db_path}")
        print(f"Tables: {tables}\n")

        for table in tables:
            cols = table_columns(cur, table)
            col_names = [c[0] for c in cols]
            print(f"== Table: {table}")
            print(f"Columns: {cols}")

            json_cols = detect_json_like_columns(cols)
            if not json_cols:
                print("No TEXT/JSON columns to scan.\n")
                continue

            # Build WHERE clause to find "null" literal in JSON/text
            where_parts = [f"{c} LIKE '%null%'" for c in json_cols]
            where_sql = " OR ".join(where_parts)
            sql = f"SELECT {', '.join(col_names)} FROM {table} WHERE {where_sql} LIMIT 5;"

            try:
                cur.execute(sql)
                rows = cur.fetchall()
                if not rows:
                    print("No rows with 'null' in TEXT/JSON fields.\n")
                    continue

                print(f"Sample rows with 'null' in {json_cols}:")
                for r in rows:
                    print(r)
                print()
            except Exception as e:
                print(f"Failed to query {table}: {e}\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
