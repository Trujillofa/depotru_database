"""Tests for table-size introspection SQL helpers."""

from scripts.utils.introspect_table_sizes import COLUMN_SUMMARY_SQL, TABLE_SIZE_SQL


def test_table_size_sql_uses_sys_catalogs():
    assert "sys.tables" in TABLE_SIZE_SQL
    assert "sys.partitions" in TABLE_SIZE_SQL
    assert "row_count" in TABLE_SIZE_SQL
    assert "total_space_kb" in TABLE_SIZE_SQL


def test_column_summary_sql_filters_by_schema_and_table():
    assert "INFORMATION_SCHEMA.COLUMNS" in COLUMN_SUMMARY_SQL
    assert "TABLE_SCHEMA" in COLUMN_SUMMARY_SQL
    assert "TABLE_NAME" in COLUMN_SUMMARY_SQL
