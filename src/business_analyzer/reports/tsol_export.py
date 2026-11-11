"""Write the TSOL-GENERAL Excel workbook and CLI wrapper."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from business_analyzer.ai.base import Config
from business_analyzer.core.tsol_export import (
    INVENTARIO_HEADERS,
    VENTAS_HEADERS,
    TsolExportRunner,
    previous_calendar_month,
    quality_issues,
    quality_summary,
)

TEXT_VENTAS = {
    "NUMERO\nFACTURAS",
    "FECHA VENTA",
    "CODIGO VENDEDOR",
    "NOMBRE VENDEDOR",
    "CEDULA VENDEDOR",
    "CODIGO DE MUNICIPIO",
    "NOMBRE DEL MUNICIPIO",
    "COD. CLIENTE",
    "NOM.CLIENTE",
    "NIT CLIENTE",
    "DIRECCIÓN CLIENTE",
    "CÓDIGO .PRODUCTO",
    "DESCRIPCIÓN. PRODUCTO",
    "CODIGO DE BARRA",
    "CODIGO TIPO NEGOCIO",
    "NOMBRE TIPO NEGOCIO",
}
MONEY_VENTAS = {"COSTO", "VALOR TOTAL VENTA"}
TEXT_INVENTARIO = {"FECHA", "CODIGO", "NOMBRE PRODUCTO", "UN MEDIDA"}


def tsol_output_basename(
    brand: str,
    year: Optional[int] = None,
    month: Optional[int] = None,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> str:
    label = (brand or "all").strip().lower() or "all"
    if start and end:
        return f"TSOL_{label.upper()}_{start}_{end}.xlsx"
    return f"TSOL_{label.upper()}_{int(year):04d}-{int(month):02d}.xlsx"


def _col_width(header: str) -> int:
    sample = header.replace("\n", " ")
    return max(14, min(36, len(sample) + 4))


def _write_sheet(
    ws: Any,
    headers: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
    *,
    text_cols: set,
    money_cols: Optional[set] = None,
) -> None:
    money_cols = money_cols or set()
    header_font = None
    try:
        from openpyxl.styles import Alignment, Font, numbers

        header_font = Font(bold=True)
        wrap = Alignment(wrap_text=True, vertical="center")
    except ImportError:  # pragma: no cover
        Alignment = None  # type: ignore[misc, assignment]
        numbers = None  # type: ignore[misc, assignment]
        wrap = None

    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        if header_font is not None:
            cell.font = header_font
            cell.alignment = wrap
        ws.column_dimensions[cell.column_letter].width = _col_width(header)

    for r_i, row in enumerate(rows, start=2):
        for c_i, header in enumerate(headers, start=1):
            value = row.get(header)
            cell = ws.cell(row=r_i, column=c_i, value=value)
            if numbers is None:
                continue
            if header in text_cols:
                cell.number_format = "@"
                if value is not None and value != "":
                    cell.value = str(value)
            elif header in money_cols:
                cell.number_format = numbers.FORMAT_NUMBER_00

    ws.auto_filter.ref = (
        f"A1:{ws.cell(row=1, column=len(headers)).column_letter}"
        f"{max(1, len(rows) + 1)}"
    )
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 30


def write_tsol_xlsx(
    path: Path,
    ventas: Sequence[Mapping[str, Any]],
    inventario: Sequence[Mapping[str, Any]],
) -> Path:
    from openpyxl import Workbook

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws_ventas = wb.active
    ws_ventas.title = "Ventas"
    _write_sheet(
        ws_ventas,
        VENTAS_HEADERS,
        ventas,
        text_cols=TEXT_VENTAS,
        money_cols=MONEY_VENTAS,
    )
    ws_inv = wb.create_sheet("Inventario")
    _write_sheet(
        ws_inv,
        INVENTARIO_HEADERS,
        inventario,
        text_cols=TEXT_INVENTARIO,
    )
    wb.save(out)
    return out


def build_tsol_result(
    *,
    brand: str = "sika",
    year: Optional[int] = None,
    month: Optional[int] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    output_dir: Optional[Path] = None,
    output_path: Optional[Path] = None,
    db: Any = None,
    payload: Optional[Mapping[str, Any]] = None,
    strict: bool = False,
    write_quality: bool = True,
) -> Dict[str, Any]:
    if payload is None:
        try:
            runner = TsolExportRunner(db)
            payload = runner.build_export(
                brand,
                None if start is not None else year,
                None if start is not None else month,
                start=start,
                end=end,
            )
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "message": f"Error consultando TSOL: {exc}",
            }

    ventas = list(payload.get("ventas") or [])
    inventario = list(payload.get("inventario") or [])
    quality = payload.get("quality") or quality_summary(ventas, inventario)
    issues = quality_issues(quality)
    brand_key = str(payload.get("brand") or brand)
    year = int(payload.get("year") or year or 0)
    month = int(payload.get("month") or month or 0)
    period_start = str(payload.get("period_start") or "")
    period_end = str(payload.get("period_end") or "")

    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_dir = Path(output_dir) if output_dir else Config.ensure_output_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        if start is not None and end is not None:
            path = out_dir / tsol_output_basename(
                brand_key, start=period_start, end=period_end
            )
        else:
            path = out_dir / tsol_output_basename(brand_key, year, month)

    try:
        write_tsol_xlsx(path, ventas, inventario)
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "message": f"Error escribiendo Excel: {exc}",
        }

    quality_path = path.with_suffix(".calidad.json")
    if write_quality:
        try:
            quality_path.write_text(
                json.dumps(
                    {
                        "brand": brand_key,
                        "year": year,
                        "month": month,
                        "period_start": period_start,
                        "period_end": period_end,
                        "path": str(path.resolve()),
                        "quality": quality,
                        "issues": issues,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        except OSError:
            quality_path = None

    if not ventas and not inventario:
        return {
            "status": "error",
            "path": str(path.resolve()),
            "quality": quality,
            "message": (
                f"Sin filas para {brand_key} {year:04d}-{month:02d}. "
                "Revise marca y periodo."
            ),
        }

    blocking = [i for i in issues if i.get("severity") == "high"]
    status = "error" if strict and blocking else "success"
    message = (
        f"TSOL {brand_key} {period_start} a {period_end}: "
        f"{quality.get('venta_rows')} ventas, "
        f"{quality.get('inventario_rows')} inventario → {path.name}"
    )
    if strict and blocking:
        message += " | BLOQUEADO: " + ", ".join(
            f"{i['id']}={i['rows']}" for i in blocking
        )
    return {
        "status": status,
        "path": str(path.resolve()),
        "quality_path": str(quality_path.resolve()) if quality_path else None,
        "brand": brand_key,
        "year": year,
        "month": month,
        "period_start": payload.get("period_start"),
        "period_end": payload.get("period_end"),
        "quality": quality,
        "issues": issues,
        "message": message,
    }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    default_year, default_month = previous_calendar_month()
    parser = argparse.ArgumentParser(
        description=(
            "Exportar ventas e inventario al formato mínimo TSOL-GENERAL "
            "(Sika / Pintuco sell-out)."
        )
    )
    parser.add_argument(
        "--brand",
        default="sika",
        help="sika, pintuco, or all (default: sika)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=default_year,
        help=f"Sales year (default: previous month {default_year})",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=default_month,
        help=f"Sales month 1-12 (default: previous month {default_month})",
    )
    parser.add_argument(
        "--from-date",
        dest="from_date",
        default="",
        help="Inclusive start YYYY-MM-DD (overrides --year/--month)",
    )
    parser.add_argument(
        "--to-date",
        dest="to_date",
        default="",
        help="Inclusive end YYYY-MM-DD",
    )
    parser.add_argument(
        "--ytd",
        action="store_true",
        help="Year to date: 1 Jan of --year through today",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output .xlsx path (default: data/export/TSOL_<brand>_<YYYY-MM>.xlsx)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print/write the full result JSON as a sibling file",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 2 when high-severity quality issues are present",
    )
    parser.add_argument(
        "--no-quality-json",
        action="store_true",
        help="Do not write the sibling .calidad.json",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_dir = None
    else:
        output_path = None
        output_dir = _repo_root() / "data" / "export"

    start = end = None
    if args.ytd:
        start = date(int(args.year), 1, 1)
        end = date.today()
    elif args.from_date or args.to_date:
        if not args.from_date or not args.to_date:
            print(
                "ERROR --from-date and --to-date are required together",
                file=sys.stderr,
            )
            return 2
        start = date.fromisoformat(args.from_date)
        end = date.fromisoformat(args.to_date)

    result = build_tsol_result(
        brand=args.brand,
        year=None if start else args.year,
        month=None if start else args.month,
        start=start,
        end=end,
        output_dir=output_dir,
        output_path=output_path,
        strict=args.strict,
        write_quality=not args.no_quality_json,
    )
    if result.get("status") != "success":
        print(f"ERROR {result.get('message')}", file=sys.stderr)
        return 1

    print(result["message"])
    quality = result.get("quality") or {}
    print(
        "Calidad: "
        f"NIT vacíos={quality.get('missing_nit')} "
        f"dir={quality.get('missing_direccion')} "
        f"mpio={quality.get('missing_municipio')} "
        f"canal={quality.get('missing_tipo_negocio')} "
        f"cedula_vendedor={quality.get('missing_cedula_vendedor')} "
        f"barras={quality.get('missing_barcode')} "
        f"stock_negativo={quality.get('inventory_negative', 0)}"
    )
    issues = result.get("issues") or []
    if issues:
        print("Incidencias: " + ", ".join(f"{i['id']}={i['rows']}" for i in issues))
    if result.get("quality_path"):
        print(f"Calidad JSON: {result['quality_path']}")
    print(f"Archivo: {result['path']}")
    if args.json:
        json_path = Path(result["path"]).with_suffix(".calidad.json")
        payload = {
            "brand": result.get("brand"),
            "year": result.get("year"),
            "month": result.get("month"),
            "period_start": result.get("period_start"),
            "period_end": result.get("period_end"),
            "quality": quality,
            "path": result.get("path"),
        }
        json_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Calidad JSON: {json_path}")
    return 2 if result.get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
