#!/usr/bin/env python3
"""Rank MSSQL tables by row count and allocated space for a given database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Allow running from repo root without install
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from business_analyzer.core.database import Database  # noqa: E402

# Row counts must come from sys.partitions alone. Joining allocation_units first
# multiplies p.rows by LOB/overflow units (often 2–3x inflation).
TABLE_SIZE_SQL = """
SELECT
    s.name AS schema_name,
    t.name AS table_name,
    r.row_count,
    sp.total_space_kb,
    sp.used_space_kb
FROM sys.tables t
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
INNER JOIN (
    SELECT
        p.object_id,
        SUM(CASE WHEN p.index_id IN (0, 1) THEN p.rows ELSE 0 END) AS row_count
    FROM sys.partitions p
    GROUP BY p.object_id
) r ON t.object_id = r.object_id
INNER JOIN (
    SELECT
        p.object_id,
        SUM(a.total_pages) * 8 AS total_space_kb,
        SUM(a.used_pages) * 8 AS used_space_kb
    FROM sys.partitions p
    INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
    GROUP BY p.object_id
) sp ON t.object_id = sp.object_id
WHERE t.is_ms_shipped = 0
ORDER BY sp.total_space_kb DESC, r.row_count DESC
"""
COLUMN_SUMMARY_SQL = """
SELECT
    c.COLUMN_NAME AS column_name,
    c.DATA_TYPE AS data_type,
    c.CHARACTER_MAXIMUM_LENGTH AS max_length,
    c.IS_NULLABLE AS is_nullable
FROM INFORMATION_SCHEMA.COLUMNS c
WHERE c.TABLE_SCHEMA = %s AND c.TABLE_NAME = %s
ORDER BY c.ORDINAL_POSITION
"""


def fetch_table_sizes(conn) -> list[dict[str, Any]]:
    cursor = conn.cursor(as_dict=True)
    cursor.execute(TABLE_SIZE_SQL)
    rows = list(cursor)
    cursor.close()
    return rows


def fetch_column_summary(conn, schema: str, table: str) -> list[dict[str, Any]]:
    cursor = conn.cursor(as_dict=True)
    cursor.execute(COLUMN_SUMMARY_SQL, (schema, table))
    rows = list(cursor)
    cursor.close()
    return rows


def introspect_database(
    db: Database,
    database_name: str,
    *,
    schema_limit: int | None = 10,
) -> dict[str, Any]:
    """Introspect table sizes and optional column summaries.

    schema_limit: max tables to describe (largest first). None = all tables.
    """
    if (
        database_name.lower()
        == db.validate_sql_identifier(
            __import__("config").Config.DB_NAME_J3SYSTEM, "j3 database"
        ).lower()
    ):
        conn = db.get_j3system_connection()
    else:
        db.connect()
        conn = db._connection

    try:
        sizes = fetch_table_sizes(conn)
        describe_rows = sizes if schema_limit is None else sizes[:schema_limit]
        schemas: dict[str, list[dict[str, Any]]] = {}
        for row in describe_rows:
            key = f"{row['schema_name']}.{row['table_name']}"
            schemas[key] = fetch_column_summary(
                conn, row["schema_name"], row["table_name"]
            )
        return {
            "database": database_name,
            "table_count": len(sizes),
            "tables": sizes,
            "top_10_schema": schemas,
            "schema_table_count": len(schemas),
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        choices=("smartbusiness", "j3system", "both"),
        default="both",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--schema-limit",
        type=int,
        default=10,
        help="Max tables to column-describe per DB (largest first). "
        "Use 0 for all tables.",
    )
    args = parser.parse_args()

    from config import Config

    args.output_dir.mkdir(parents=True, exist_ok=True)
    db = Database()
    schema_limit: int | None = None if args.schema_limit == 0 else args.schema_limit

    targets: list[tuple[str, str]] = []
    if args.database in ("smartbusiness", "both"):
        targets.append(("smartbusiness", Config.DB_NAME or "SmartBusiness"))
    if args.database in ("j3system", "both"):
        targets.append(("j3system", Config.DB_NAME_J3SYSTEM or "J3System"))

    all_schema: dict[str, Any] = {}
    for slug, name in targets:
        # SmartBusiness is small: always describe every table for decision docs.
        limit = None if slug == "smartbusiness" else schema_limit
        payload = introspect_database(db, name, schema_limit=limit)
        out_file = args.output_dir / f"{slug}_table_sizes.json"
        out_file.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        print(f"Wrote {out_file} ({payload['table_count']} tables)")
        all_schema[name] = payload["top_10_schema"]

    schema_file = args.output_dir / "top_tables_schema.json"
    schema_file.write_text(
        json.dumps(all_schema, indent=2, default=str), encoding="utf-8"
    )
    print(f"Wrote {schema_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
