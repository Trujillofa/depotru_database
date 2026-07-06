"""Parse Crystal Reports cotizaciones exports and merge J3System cellphone lookups.

Crystal Reports layout (cotizaciones junio.xls):
- Rows 0-7: banner (company name, date range, etc.)
- Row 8 (0-based): header — Docto, Numero, Fecha, Cedula, Nombres, Detalle
- Section rows: e.g. 'COTIZACIONES FACTURADAS', '000 SIN COMISION' (skipped)
- Data rows: Docto == 'CT' (cotización records)

Join key: Excel ``Cedula`` ↔ ``AdmTerceros.TercerosIdentificacion``.
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence

from business_analyzer.core.database import Database

# Crystal Reports export: header at row index 8 (1-based row 9).
DEFAULT_HEADER_ROW_INDEX = 8
DOC_TYPE_COTIZACION = "CT"
OUTPUT_COLUMNS = (
    "Docto",
    "Numero",
    "Fecha",
    "Cedula",
    "CedulaNormalized",
    "Nombres",
    "Detalle",
    "TercerosCelular",
    "CelularMatch",
)


def normalize_cedula(value: Any) -> str:
    """Normalize Cedula to a string ID suitable for AdmTerceros lookup."""
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        if value == int(value):
            return str(int(value))
        return str(value).strip()

    text = str(value).strip()
    if not text:
        return ""

    if "e" in text.lower():
        try:
            return str(int(float(text)))
        except (ValueError, OverflowError):
            pass

    if text.endswith(".0"):
        text = text[:-2]

    return text


def find_header_row_index(rows: Sequence[Sequence[Any]]) -> int:
    """Return the 0-based index of the row containing Cedula and Docto headers."""
    for index, row in enumerate(rows):
        cells = {str(cell).strip() for cell in row}
        if "Cedula" in cells and "Docto" in cells:
            return index
    raise ValueError("Header row with Cedula and Docto not found")


def build_column_index_map(header_row: Sequence[Any]) -> Dict[str, int]:
    """Map column name to 0-based index from the header row."""
    column_map: Dict[str, int] = {}
    for index, cell in enumerate(header_row):
        name = str(cell).strip()
        if name and name not in column_map:
            column_map[name] = index
    required = ("Docto", "Cedula")
    missing = [name for name in required if name not in column_map]
    if missing:
        raise ValueError(f"Missing required columns in header: {', '.join(missing)}")
    return column_map


def _cell_value(row: Sequence[Any], column_map: Mapping[str, int], name: str) -> Any:
    index = column_map.get(name)
    if index is None or index >= len(row):
        return ""
    return row[index]


def parse_cotizaciones_rows(
    rows: Sequence[Sequence[Any]],
    *,
    header_row_index: Optional[int] = None,
    doc_filter: str = DOC_TYPE_COTIZACION,
) -> List[Dict[str, Any]]:
    """Parse cotización rows, keeping only ``doc_filter`` records (default CT)."""
    header_index = (
        header_row_index
        if header_row_index is not None
        else find_header_row_index(rows)
    )
    column_map = build_column_index_map(rows[header_index])

    parsed: List[Dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        docto = str(_cell_value(row, column_map, "Docto")).strip()
        if docto != doc_filter:
            continue

        raw_cedula = _cell_value(row, column_map, "Cedula")
        normalized = normalize_cedula(raw_cedula)
        parsed.append(
            {
                "Docto": docto,
                "Numero": _cell_value(row, column_map, "Numero"),
                "Fecha": _cell_value(row, column_map, "Fecha"),
                "Cedula": raw_cedula,
                "CedulaNormalized": normalized,
                "Nombres": _cell_value(row, column_map, "Nombres"),
                "Detalle": _cell_value(row, column_map, "Detalle"),
            }
        )
    return parsed


def distinct_normalized_cedulas(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    """Return sorted unique non-empty normalized cédulas."""
    seen = {
        str(row.get("CedulaNormalized", "")).strip()
        for row in rows
        if str(row.get("CedulaNormalized", "")).strip()
    }
    return sorted(seen)


def admterceros_qualified_table(j3_database: Optional[str] = None) -> str:
    """Return the fully qualified ``J3System.dbo.AdmTerceros`` table reference."""
    db_name = j3_database or os.getenv("DB_NAME_J3SYSTEM", "J3System")
    validated = Database.validate_sql_identifier(db_name, "j3 database")
    return f"{validated}.dbo.AdmTerceros"


def build_terceros_celular_query(
    chunk_size: int,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Build the parameterized batch lookup query for ``TercerosCelular``."""
    table = admterceros_qualified_table(j3_database)
    placeholders = ",".join(["%s"] * chunk_size)
    return (
        "SELECT TercerosIdentificacion, TercerosCelular "
        f"FROM {table} "
        f"WHERE TercerosIdentificacion IN ({placeholders})"
    )


def merge_celular_lookup(
    rows: Sequence[Mapping[str, Any]],
    lookup: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """Attach ``TercerosCelular`` and ``CelularMatch`` from a cédula → celular map."""
    enriched: List[Dict[str, Any]] = []
    for row in rows:
        normalized = str(row.get("CedulaNormalized", "")).strip()
        matched = normalized in lookup
        celular = lookup.get(normalized, "") if matched else ""
        enriched.append(
            format_enriched_row(
                {
                    **dict(row),
                    "TercerosCelular": celular if celular is not None else "",
                    "CelularMatch": matched,
                }
            )
        )
    return enriched


def format_enriched_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Project a row onto ``OUTPUT_COLUMNS`` with explicit string celular values."""
    formatted: Dict[str, Any] = {}
    for column in OUTPUT_COLUMNS:
        value = row.get(column, "")
        if column == "TercerosCelular":
            if value is None:
                formatted[column] = ""
            elif isinstance(value, float) and math.isnan(value):
                formatted[column] = ""
            else:
                formatted[column] = str(value)
        elif column == "CelularMatch":
            formatted[column] = bool(value)
        else:
            formatted[column] = value
    return formatted


def format_enriched_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Format all enriched rows using ``OUTPUT_COLUMNS`` column order."""
    return [format_enriched_row(row) for row in rows]


def find_sample_non_empty_match(
    enriched_rows: Sequence[Mapping[str, Any]],
    *,
    preferred_cedula: str = "1080933848",
) -> tuple[str, str]:
    """Return a cédula/celular pair with a non-empty digit cellphone."""
    preferred = str(preferred_cedula).strip()
    fallback = ("", "")
    for row in enriched_rows:
        celular = str(row.get("TercerosCelular", "")).strip()
        if not celular or not celular.isdigit():
            continue
        cedula = str(row.get("CedulaNormalized", "")).strip()
        if not cedula:
            continue
        if cedula == preferred:
            return cedula, celular
        if not fallback[0]:
            fallback = (cedula, celular)
    return fallback


def count_matched_cedulas_populated(
    rows: Sequence[Mapping[str, Any]],
    lookup: Mapping[str, str],
) -> int:
    """Count matched cédulas whose ``TercerosCelular`` field is explicitly set."""
    distinct = distinct_normalized_cedulas(rows)
    return sum(1 for ced in distinct if ced in lookup)


def enrichment_summary(
    rows: Sequence[Mapping[str, Any]],
    lookup: Mapping[str, str],
    *,
    enriched_rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Summarize enrichment results for CLI logging."""
    distinct = distinct_normalized_cedulas(rows)
    matched_ids = {ced for ced in distinct if ced in lookup}
    non_empty = sum(1 for ced in matched_ids if str(lookup.get(ced, "")).strip())
    populated = count_matched_cedulas_populated(rows, lookup)
    sample_cedula, sample_celular = "", ""
    if enriched_rows:
        sample_cedula, sample_celular = find_sample_non_empty_match(enriched_rows)

    return {
        "total_rows": len(rows),
        "distinct_cedulas": len(distinct),
        "admterceros_matches": len(matched_ids),
        "matched_cedulas_populated": populated,
        "non_empty_celular": non_empty,
        "sample_cedula": sample_cedula,
        "sample_celular": sample_celular,
    }


def fetch_terceros_celular_batch(
    identifications: Sequence[str],
    connection: Any,
    *,
    batch_size: int = 500,
) -> Dict[str, str]:
    """Query ``AdmTerceros.TercerosCelular`` by ``TercerosIdentificacion`` in batches."""
    if not identifications:
        return {}

    result: Dict[str, str] = {}
    ids = list(identifications)
    cursor = connection.cursor(as_dict=True)
    try:
        for start in range(0, len(ids), batch_size):
            chunk = ids[start : start + batch_size]
            query = build_terceros_celular_query(len(chunk))
            cursor.execute(query, tuple(chunk))
            for row in cursor.fetchall():
                key = str(row["TercerosIdentificacion"]).strip()
                value = row.get("TercerosCelular")
                result[key] = "" if value is None else str(value).strip()
    finally:
        cursor.close()
    return result


def _xlsx_cell_value(column: str, value: Any) -> str | bool | int | float:
    """Coerce a row value for xlsxwriter while keeping empty celular as ``''``."""
    if column == "TercerosCelular":
        if value is None:
            return ""
        if isinstance(value, float) and math.isnan(value):
            return ""
        return str(value)
    if column == "CelularMatch":
        return bool(value)
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return value


def export_enriched_xlsx(
    rows: Sequence[Mapping[str, Any]],
    output_path: str,
) -> None:
    """Write enriched rows to Excel with explicit ``''`` for empty ``TercerosCelular``."""
    import xlsxwriter

    formatted = format_enriched_rows(rows)
    workbook = xlsxwriter.Workbook(output_path)
    worksheet = workbook.add_worksheet("cotizaciones")

    for col_index, column in enumerate(OUTPUT_COLUMNS):
        worksheet.write_string(0, col_index, column)

    for row_index, row in enumerate(formatted, start=1):
        for col_index, column in enumerate(OUTPUT_COLUMNS):
            value = _xlsx_cell_value(column, row.get(column, ""))
            if column in {
                "TercerosCelular",
                "Cedula",
                "CedulaNormalized",
                "Nombres",
                "Detalle",
                "Docto",
                "Fecha",
            }:
                worksheet.write_string(row_index, col_index, str(value))
            elif column == "CelularMatch":
                worksheet.write_boolean(row_index, col_index, bool(value))
            elif isinstance(value, (int, float)):
                worksheet.write_number(row_index, col_index, value)
            else:
                worksheet.write_string(row_index, col_index, str(value))

    workbook.close()


def read_xls_sheet_rows(path: str, sheet_index: int = 0) -> List[List[Any]]:
    """Read all rows from a legacy ``.xls`` workbook via xlrd."""
    import xlrd

    workbook = xlrd.open_workbook(path)
    sheet = workbook.sheet_by_index(sheet_index)
    return [
        [sheet.cell_value(row_index, col_index) for col_index in range(sheet.ncols)]
        for row_index in range(sheet.nrows)
    ]
