#!/usr/bin/env python3
"""Audit TSOL-GENERAL Excel files for blank and invalid sell-out fields."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from business_analyzer.core.tsol_export import (  # noqa: E402
    INVENTARIO_HEADERS,
    VENTAS_HEADERS,
)

PLACEHOLDER_NITS = {"222222222222", "22222222", "0", "0000000000"}
PLACEHOLDER_PHONES = {"3000000000", "0000000000", "0"}
GENERIC_NAMES = {"CONSUMIDOR FINAL", "CONSUMIDOR  FINAL", "CLIENTE GENERAL"}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _load_ventas(path: Path) -> List[Dict[str, Any]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    ws = wb["Ventas"]
    headers = [c.value for c in ws[1]]
    if list(headers) != list(VENTAS_HEADERS):
        raise ValueError(f"Unexpected Ventas headers in {path}")
    rows = []
    for excel_row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None or v == "" for v in excel_row):
            continue
        rows.append(dict(zip(VENTAS_HEADERS, excel_row)))
    return rows


def _load_inventario(path: Path) -> List[Dict[str, Any]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    ws = wb["Inventario"]
    headers = [c.value for c in ws[1]]
    if list(headers) != list(INVENTARIO_HEADERS):
        raise ValueError(f"Unexpected Inventario headers in {path}")
    rows = []
    for excel_row in ws.iter_rows(min_row=2, values_only=True):
        if all(v is None or v == "" for v in excel_row):
            continue
        rows.append(dict(zip(INVENTARIO_HEADERS, excel_row)))
    return rows


def _blank(row: Dict[str, Any], key: str) -> bool:
    return not _clean(row.get(key))


def audit_file(path: Path) -> Dict[str, Any]:
    ventas = _load_ventas(path)
    inventario = _load_inventario(path)
    n = len(ventas)
    issues: List[Dict[str, Any]] = []

    def count(pred) -> int:
        return sum(1 for r in ventas if pred(r))

    missing = {
        "numero_factura": count(lambda r: _blank(r, "NUMERO\nFACTURAS")),
        "fecha": count(lambda r: _blank(r, "FECHA VENTA")),
        "codigo_vendedor": count(lambda r: _blank(r, "CODIGO VENDEDOR")),
        "nombre_vendedor": count(lambda r: _blank(r, "NOMBRE VENDEDOR")),
        "cedula_vendedor": count(lambda r: _blank(r, "CEDULA VENDEDOR")),
        "codigo_municipio": count(lambda r: _blank(r, "CODIGO DE MUNICIPIO")),
        "nombre_municipio": count(lambda r: _blank(r, "NOMBRE DEL MUNICIPIO")),
        "cod_cliente": count(lambda r: _blank(r, "COD. CLIENTE")),
        "nom_cliente": count(lambda r: _blank(r, "NOM.CLIENTE")),
        "nit": count(lambda r: _blank(r, "NIT CLIENTE")),
        "direccion": count(lambda r: _blank(r, "DIRECCIÓN CLIENTE")),
        "codigo_producto": count(lambda r: _blank(r, "CÓDIGO .PRODUCTO")),
        "descripcion": count(lambda r: _blank(r, "DESCRIPCIÓN. PRODUCTO")),
        "barcode": count(lambda r: _blank(r, "CODIGO DE BARRA")),
        "tipo_negocio_codigo": count(lambda r: _blank(r, "CODIGO TIPO NEGOCIO")),
        "tipo_negocio_nombre": count(lambda r: _blank(r, "NOMBRE TIPO NEGOCIO")),
    }

    placeholder_nit = count(
        lambda r: _clean(r.get("NIT CLIENTE")).replace("-", "") in PLACEHOLDER_NITS
        or _clean(r.get("NIT CLIENTE")).startswith("222222")
    )
    generic_customer = count(
        lambda r: _clean(r.get("NOM.CLIENTE")).upper() in GENERIC_NAMES
        or "CONSUMIDOR FINAL" in _clean(r.get("NOM.CLIENTE")).upper()
    )
    short_address = count(lambda r: 0 < len(_clean(r.get("DIRECCIÓN CLIENTE"))) < 8)
    bad_divipola = count(
        lambda r: bool(_clean(r.get("CODIGO DE MUNICIPIO")))
        and not re.fullmatch(r"\d{5}", _clean(r.get("CODIGO DE MUNICIPIO")))
    )
    zero_qty = count(lambda r: float(r.get("CANTIDAD") or 0) == 0)
    missing_cost = count(lambda r: r.get("COSTO") is None or r.get("COSTO") == "")
    missing_venta = count(
        lambda r: r.get("VALOR TOTAL VENTA") is None or r.get("VALOR TOTAL VENTA") == ""
    )
    cost_gt_sale = 0
    for r in ventas:
        qty = float(r.get("CANTIDAD") or 0)
        cost = float(r.get("COSTO") or 0)
        sale = float(r.get("VALOR TOTAL VENTA") or 0)
        if qty > 0 and sale > 0 and abs(cost) > abs(sale) * 1.001:
            cost_gt_sale += 1

    inv_blank_code = sum(1 for r in inventario if not _clean(r.get("CODIGO")))
    inv_blank_name = sum(1 for r in inventario if not _clean(r.get("NOMBRE PRODUCTO")))
    inv_zero = sum(1 for r in inventario if float(r.get("CANTIDAD") or 0) == 0)
    inv_neg = sum(1 for r in inventario if float(r.get("CANTIDAD") or 0) < 0)

    # Distinct masters behind blanks
    tipo_blank_customers = sorted(
        {
            (
                _clean(r.get("NIT CLIENTE")),
                _clean(r.get("NOM.CLIENTE")),
            )
            for r in ventas
            if _blank(r, "CODIGO TIPO NEGOCIO")
        }
    )
    cedula_blank_sellers = sorted(
        {
            (
                _clean(r.get("CODIGO VENDEDOR")),
                _clean(r.get("NOMBRE VENDEDOR")),
            )
            for r in ventas
            if _blank(r, "CEDULA VENDEDOR")
        }
    )
    codigo_vend_blank = sorted(
        {
            _clean(r.get("NOMBRE VENDEDOR"))
            for r in ventas
            if _blank(r, "CODIGO VENDEDOR")
        }
    )

    if missing["tipo_negocio_codigo"]:
        issues.append(
            {
                "id": "blank_tipo_negocio",
                "severity": "high",
                "rows": missing["tipo_negocio_codigo"],
                "distinct": len(tipo_blank_customers),
                "samples": tipo_blank_customers[:15],
            }
        )
    if missing["cedula_vendedor"]:
        issues.append(
            {
                "id": "blank_cedula_vendedor",
                "severity": "high",
                "rows": missing["cedula_vendedor"],
                "distinct": len(cedula_blank_sellers),
                "samples": cedula_blank_sellers[:20],
            }
        )
    if missing["codigo_vendedor"]:
        issues.append(
            {
                "id": "blank_codigo_vendedor",
                "severity": "medium",
                "rows": missing["codigo_vendedor"],
                "samples": codigo_vend_blank[:15],
            }
        )
    if missing["barcode"] == n and n:
        issues.append(
            {
                "id": "barcode_empty_all",
                "severity": "medium",
                "rows": n,
                "note": "AdmBarras has almost no EAN; TSOL barcode column is empty.",
            }
        )
    if placeholder_nit:
        issues.append(
            {
                "id": "placeholder_nit",
                "severity": "high",
                "rows": placeholder_nit,
            }
        )
    if generic_customer:
        issues.append(
            {
                "id": "generic_customer",
                "severity": "medium",
                "rows": generic_customer,
            }
        )
    if short_address:
        issues.append(
            {
                "id": "short_address",
                "severity": "low",
                "rows": short_address,
            }
        )
    if bad_divipola:
        issues.append(
            {
                "id": "invalid_divipola",
                "severity": "high",
                "rows": bad_divipola,
            }
        )
    if cost_gt_sale:
        issues.append(
            {
                "id": "cost_gt_sale",
                "severity": "medium",
                "rows": cost_gt_sale,
            }
        )
    if inv_zero:
        issues.append(
            {
                "id": "inventory_zero",
                "severity": "info",
                "rows": inv_zero,
                "of": len(inventario),
            }
        )
    if inv_neg:
        issues.append(
            {
                "id": "inventory_negative",
                "severity": "high",
                "rows": inv_neg,
            }
        )

    canal = Counter(_clean(r.get("NOMBRE TIPO NEGOCIO")) or "(blank)" for r in ventas)
    return {
        "file": str(path),
        "venta_rows": n,
        "inventario_rows": len(inventario),
        "missing": missing,
        "placeholder_nit": placeholder_nit,
        "generic_customer": generic_customer,
        "short_address": short_address,
        "invalid_divipola": bad_divipola,
        "zero_qty": zero_qty,
        "missing_cost": missing_cost,
        "missing_venta": missing_venta,
        "cost_gt_sale": cost_gt_sale,
        "inventario_blank_code": inv_blank_code,
        "inventario_blank_name": inv_blank_name,
        "inventario_zero": inv_zero,
        "inventario_negative": inv_neg,
        "canal": dict(canal.most_common()),
        "tipo_blank_customers": tipo_blank_customers,
        "cedula_blank_sellers": cedula_blank_sellers,
        "codigo_vendedor_blank_names": codigo_vend_blank,
        "issues": issues,
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    reports = []
    for path in args.xlsx:
        path = path.expanduser().resolve()
        reports.append(audit_file(path))
    text = json.dumps(reports, indent=2, ensure_ascii=False)
    print(text)
    if args.json_out:
        args.json_out.write_text(text + "\n", encoding="utf-8")
    high = sum(
        1
        for r in reports
        for i in r["issues"]
        if i.get("severity") == "high" and i["id"] != "barcode_empty_all"
    )
    return 0 if high == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
