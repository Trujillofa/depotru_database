#!/usr/bin/env python3
"""Verify golden-question SQL routing (no LLM, no cache)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from business_analyzer.ai.base import AIVanna  # noqa: E402

# Reuse matrix from tests/ai/test_sql_routing.py
GOLDEN = [
    (
        "Top 10 clientes con mayor facturación",
        ["ganancia_neta", "top 10"],
        [],
    ),
    (
        "Vendedores con mejor desempeño este mes",
        ["month(fecha)", "total_vendido"],
        ["group by vendedorfactura, vendedor_codigo"],
    ),
    (
        "Promedio de ventas diarias por mes",
        ["sum(totalmasiva)", "promedio_ventas_diarias"],
        ["ventatotal"],
    ),
    (
        "Comparación de ventas por tipo de documento",
        ["documentoscodigo in ('fed', 'fef', 'fet')"],
        ["ventatotal"],
    ),
    (
        "Ventas de los últimos 30 días",
        ["group by fecha", "ventas_diarias"],
        ["tabla"],
    ),
    (
        "Ventas de la sede Sika Center por mes",
        ["documentoscodigo = 'fef'"],
        ["marca_proveedor"],
    ),
    (
        "Ventas a crédito vs contado",
        ["diascredito"],
        [],
    ),
    (
        "Productos de SIKA más vendidos",
        ["top 10", "group by articulosnombre"],
        ["marca_proveedor"],
    ),
    (
        "Ventas de productos SIKA",
        ["marca_proveedor"],
        ["group by articulosnombre"],
    ),
    (
        "Productos más vendidos de HIERRO",
        ["group by articulosnombre", "categoria"],
        ["marca_proveedor"],
    ),
    (
        "Top 10 productos más vendidos por facturación este año",
        ["top 10", "group by articulosnombre", "facturacion_total"],
        ["marca_proveedor"],
    ),
]


def _generate_sql(question: str) -> str:
    vn = object.__new__(AIVanna)
    vn._query_cache = MagicMock()
    vn._query_cache.get.return_value = None
    vn.provider = "grok"
    return AIVanna.generate_sql(vn, question)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SQL routing golden questions")
    parser.add_argument(
        "--db",
        action="store_true",
        help="Execute product SQL against DB (requires connection)",
    )
    args = parser.parse_args()

    failed = 0
    for question, must_contain, must_not_contain in GOLDEN:
        sql = _generate_sql(question)
        lower = (sql or "").lower()
        ok = True
        for frag in must_contain:
            if frag not in lower:
                print(f"FAIL [{question}]: missing '{frag}'")
                ok = False
        for frag in must_not_contain:
            if frag in lower:
                print(f"FAIL [{question}]: unexpected '{frag}'")
                ok = False
        if ok:
            print(f"OK   {question}")
        else:
            failed += 1
            print(f"      SQL: {sql[:120]}...")

    if args.db and failed == 0:
        try:
            from business_analyzer.core.db_factory import get_database

            db = get_database()
            sql = _generate_sql("Productos de SIKA más vendidos")
            rows = db.execute_query(sql)
            count = len(rows) if rows else 0
            if count <= 1:
                print(f"FAIL [DB] Productos SIKA returned {count} rows (expected >1)")
                failed += 1
            else:
                print(f"OK   [DB] Productos SIKA returned {count} rows")
        except Exception as exc:
            print(f"WARN [DB] skipped: {exc}")

    print(f"\n{len(GOLDEN) - failed}/{len(GOLDEN)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())