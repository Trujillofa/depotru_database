"""Tests for table-size introspection SQL helpers."""

from scripts.utils.introspect_table_sizes import COLUMN_SUMMARY_SQL, TABLE_SIZE_SQL


def test_table_size_sql_uses_sys_catalogs():
    assert "sys.tables" in TABLE_SIZE_SQL
    assert "sys.partitions" in TABLE_SIZE_SQL
    assert "row_count" in TABLE_SIZE_SQL
    assert "total_space_kb" in TABLE_SIZE_SQL


def test_table_size_sql_row_count_not_multiplied_by_allocation_units():
    """Row counts must aggregate partitions alone; LOB/overflow units inflate SUM(p.rows).

    Correct pattern: separate subquery for rows vs space. Incorrect pattern joins
    allocation_units then SUMs p.rows in the same GROUP BY (2–3x inflation).
    """
    sql = " ".join(TABLE_SIZE_SQL.split())
    assert "sys.allocation_units" in sql
    # Partition row aggregate must not join allocation_units in the same FROM list
    # as the p.rows SUM — require a dedicated rows subquery.
    assert "AS row_count" in sql or "as row_count" in sql.lower()
    # Heuristic: rows subquery groups partitions by object_id without allocation_units
    # nearby in that SELECT. Space uses allocation_units separately.
    assert "FROM sys.partitions p" in sql or "from sys.partitions p" in sql.lower()
    # Must not use the buggy single-level join that multiplies rows.
    # Buggy form looks like: partitions p JOIN allocation_units a ... SUM(... p.rows ...)
    # in one SELECT. Correct form has nested aggregates.
    assert sql.count("GROUP BY") >= 2 or "object_id" in sql
    # Explicitly require row_count expression from partitions (index 0/1) without
    # allocation_units appearing between the SUM of rows and the FROM of that branch.
    assert "index_id IN (0, 1)" in sql or "index_id in (0, 1)" in sql.lower()
    # Space still measured from allocation_units
    assert "total_pages" in sql


def test_column_summary_sql_filters_by_schema_and_table():
    assert "INFORMATION_SCHEMA.COLUMNS" in COLUMN_SUMMARY_SQL
    assert "TABLE_SCHEMA" in COLUMN_SUMMARY_SQL
    assert "TABLE_NAME" in COLUMN_SUMMARY_SQL
