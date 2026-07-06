"""CLI entry point for cotizaciones cellphone enrichment."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from business_analyzer.analysis.cotizaciones_celular import (
    DEFAULT_HEADER_ROW_INDEX,
    distinct_normalized_cedulas,
    enrichment_summary,
    export_enriched_xlsx,
    fetch_terceros_celular_batch,
    merge_celular_lookup,
    parse_cotizaciones_rows,
    read_xls_sheet_rows,
)
from business_analyzer.core.database import Database

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "export"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Enrich cotizaciones .xls with TercerosCelular from J3System AdmTerceros"
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to Crystal Reports .xls export",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .xlsx path (default: data/export/<input-stem>_celular.xlsx)",
    )
    parser.add_argument(
        "--header-row",
        type=int,
        default=DEFAULT_HEADER_ROW_INDEX,
        help=f"0-based header row index (default: {DEFAULT_HEADER_ROW_INDEX})",
    )
    return parser.parse_args(argv)


def default_output_path(input_path: Path) -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_OUTPUT_DIR / f"{input_path.stem}_celular.xlsx"


def print_summary(summary: dict, output_path: Path) -> None:
    print("=== Cotizaciones celular enrichment ===")
    print(f"Total CT rows       : {summary['total_rows']}")
    print(f"Distinct Cedula     : {summary['distinct_cedulas']}")
    print(f"AdmTerceros matches : {summary['admterceros_matches']}")
    print(
        "Matched populated   : "
        f"{summary['matched_cedulas_populated']}/{summary['distinct_cedulas']}"
    )
    print(f"Non-empty celular   : {summary['non_empty_celular']}")
    sample_cedula = summary.get("sample_cedula", "")
    sample_celular = summary.get("sample_celular", "")
    if sample_cedula and sample_celular:
        print(
            f"Sample match        : Cedula {sample_cedula} "
            f"→ TercerosCelular {sample_celular}"
        )
    print(f"Output file         : {output_path}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = args.input.expanduser().resolve()
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
        return 1

    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else default_output_path(input_path)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sheet_rows = read_xls_sheet_rows(str(input_path))
    parsed_rows = parse_cotizaciones_rows(sheet_rows, header_row_index=args.header_row)
    cedulas = distinct_normalized_cedulas(parsed_rows)

    db = Database()
    connection = None
    try:
        connection = db.get_j3system_connection()
        lookup = fetch_terceros_celular_batch(cedulas, connection)
    finally:
        if connection is not None:
            connection.close()

    enriched_rows = merge_celular_lookup(parsed_rows, lookup)
    summary = enrichment_summary(parsed_rows, lookup, enriched_rows=enriched_rows)

    export_enriched_xlsx(enriched_rows, str(output_path))
    print_summary(summary, output_path)
    return 0
