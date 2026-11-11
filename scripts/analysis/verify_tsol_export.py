#!/usr/bin/env python3
"""Verify a TSOL-GENERAL xlsx against the same SQL the exporter uses."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from business_analyzer.core.tsol_export import (  # noqa: E402
    INVENTARIO_HEADERS,
    VENTAS_HEADERS,
    TsolExportRunner,
    assemble_inventario_row,
    assemble_venta_row,
    month_bounds,
)
from business_analyzer.reports.tsol_export import tsol_output_basename  # noqa: E402


def _xlsx_rows(path: Path, sheet: str, headers: tuple) -> List[Dict[str, Any]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    if sheet not in wb.sheetnames:
        raise ValueError(f"{path} missing sheet {sheet!r}: {wb.sheetnames}")
    ws = wb[sheet]
    got = [c.value for c in ws[1]]
    if list(got) != list(headers):
        raise ValueError(f"{sheet} headers mismatch\n got={got}\n exp={list(headers)}")
    rows = []
    for excel_row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None or v == "" for v in excel_row):
            continue
        rows.append(dict(zip(headers, excel_row)))
    return rows


def _sale_key(row: Dict[str, Any]) -> tuple:
    fact = str(row.get("NUMERO\nFACTURAS") or "").strip()
    try:
        fact = str(int(float(fact)))
    except (TypeError, ValueError):
        pass
    sku = str(row.get("CÓDIGO .PRODUCTO") or "").strip()
    return (fact, sku)


def _sale_bag(rows: List[Dict[str, Any]]) -> Counter:
    """Multiset so two lines on the same factura+SKU still compare."""
    bag: Counter = Counter()
    for row in rows:
        fact, sku = _sale_key(row)
        bag[
            (
                fact,
                sku,
                round(_as_float(row.get("CANTIDAD")), 4),
                round(_as_float(row.get("VALOR TOTAL VENTA")), 2),
            )
        ] += 1
    return bag


def _as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def verify_brand(
    brand: str,
    year: int,
    month: int,
    xlsx: Path,
) -> Dict[str, Any]:
    start, end = month_bounds(year, month)
    as_of = end - timedelta(days=1)
    runner = TsolExportRunner()
    raw_sales = runner.fetch_sales(brand, start, end)
    raw_inv = runner.fetch_inventory(brand, as_of.year)
    db_sales = [assemble_venta_row(r) for r in raw_sales]
    db_inv = [assemble_inventario_row(r, as_of=as_of) for r in raw_inv]

    xl_sales = _xlsx_rows(xlsx, "Ventas", VENTAS_HEADERS)
    xl_inv = _xlsx_rows(xlsx, "Inventario", INVENTARIO_HEADERS)

    db_bag = _sale_bag(db_sales)
    xl_bag = _sale_bag(xl_sales)
    db_net = round(sum(_as_float(r["VALOR TOTAL VENTA"]) for r in db_sales), 2)
    xl_net = round(sum(_as_float(r["VALOR TOTAL VENTA"]) for r in xl_sales), 2)
    db_nc = sum(1 for r in db_sales if _as_float(r["CANTIDAD"]) < 0)
    xl_nc = sum(1 for r in xl_sales if _as_float(r["CANTIDAD"]) < 0)
    venta_mismatches = sum((db_bag - xl_bag).values()) + sum((xl_bag - db_bag).values())

    ok = (
        venta_mismatches == 0
        and abs(db_net - xl_net) < 0.05
        and db_nc == xl_nc
        and len(db_sales) == len(xl_sales)
        and len(db_inv) == len(xl_inv)
    )
    return {
        "ok": ok,
        "brand": brand,
        "year": year,
        "month": month,
        "xlsx": str(xlsx),
        "period": f"{start.isoformat()} .. {as_of.isoformat()}",
        "ventas_db": len(db_sales),
        "ventas_xlsx": len(xl_sales),
        "keys_only_db": sum((db_bag - xl_bag).values()),
        "keys_only_xlsx": sum((xl_bag - db_bag).values()),
        "venta_mismatches": venta_mismatches,
        "net_db": db_net,
        "net_xlsx": xl_net,
        "nc_db": db_nc,
        "nc_xlsx": xl_nc,
        "inventario_db": len(db_inv),
        "inventario_xlsx": len(xl_inv),
    }


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--brand", required=True)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--xlsx", type=Path, default=None)
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    xlsx = args.xlsx
    if xlsx is None:
        xlsx = (
            _REPO
            / "data"
            / "export"
            / tsol_output_basename(args.brand, args.year, args.month)
        )
    xlsx = xlsx.expanduser().resolve()
    if not xlsx.is_file():
        print(f"ERROR missing {xlsx}", file=sys.stderr)
        return 2
    result = verify_brand(args.brand, args.year, args.month, xlsx)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
