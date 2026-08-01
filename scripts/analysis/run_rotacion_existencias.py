#!/usr/bin/env python3
"""CLI: Rotación de Existencias (inventory turnover decision report)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

# Repo root on path
_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from business_analyzer.core.inventory_turnover import (  # noqa: E402
    DEMAND_MODE_COMPANY,
    DEMAND_MODE_WAREHOUSE,
)
from business_analyzer.reports.rotacion_existencias import (  # noqa: E402
    build_rotacion_result,
    default_as_of_date,
)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Rotación de Existencias: cobertura comercial, quiebre y capital atrapado "
            "(InvDetalleExistencias + demanda comercial; bodegas comerciales)"
        )
    )
    p.add_argument(
        "--as-of-date",
        default=default_as_of_date(),
        help="Reference date YYYY-MM-DD (default: yesterday)",
    )
    p.add_argument(
        "--velocity-days",
        type=int,
        default=90,
        help="Commercial demand window in days (default: 90)",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="Max rows per action table (default: 50)",
    )
    p.add_argument(
        "--min-velocity",
        type=float,
        default=20,
        help="Min commercial units in window for quiebre cover band (default: 20)",
    )
    p.add_argument(
        "--demand-mode",
        choices=(DEMAND_MODE_WAREHOUSE, DEMAND_MODE_COMPANY),
        default=DEMAND_MODE_WAREHOUSE,
        help=(
            "warehouse=SKU×bodega via InvVentasDetalle (default); "
            "company=SKU-wide via banco_datos"
        ),
    )
    p.add_argument(
        "--output",
        default="",
        help="Markdown output path (default: reports/ROTACION_EXISTENCIAS_<date>.md)",
    )
    p.add_argument(
        "--format",
        choices=("html", "pdf", "markdown", "json"),
        default="html",
        help="Output format (default: html)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Also write sibling .json",
    )
    p.add_argument(
        "--json-only",
        action="store_true",
        help="Print report JSON to stdout only (still hits DB)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if args.output:
        out = Path(args.output).resolve()
        output_dir = out.parent
        # build_rotacion_result always uses basename; allow custom path by
        # writing to parent then renaming if needed.
        custom_name = out.name
    else:
        output_dir = _REPO / "reports"
        custom_name = None

    if args.json_only:
        from business_analyzer.core.database import Database
        from business_analyzer.core.inventory_turnover import InventoryTurnoverRunner

        runner = InventoryTurnoverRunner(
            Database(),
            velocity_days=args.velocity_days,
            min_velocity_qty=args.min_velocity,
            top_n=args.top_n,
            demand_mode=args.demand_mode,
        )
        report = runner.build_report(args.as_of_date)
        print(json.dumps(report, indent=2, default=str))
        return 0

    result = build_rotacion_result(
        as_of_date=args.as_of_date,
        top_n=args.top_n,
        demand_mode=args.demand_mode,
        velocity_days=args.velocity_days,
        min_velocity=args.min_velocity,
        output_dir=output_dir,
        write_json=args.json,
        fmt=args.format,
    )
    if result.get("status") == "error":
        print(f"❌ {result.get('message')}", file=sys.stderr)
        return 1

    written = Path(result["path"])
    if custom_name and written.name != custom_name:
        target = output_dir / custom_name
        written.rename(target)
        if args.json:
            jsrc = written.with_suffix(".json")
            if jsrc.is_file():
                jsrc.rename(target.with_suffix(".json"))
        written = target
        result["path"] = str(written)

    print(f"✅ Rotación de existencias: {written}")
    if args.json:
        print(f"✅ JSON: {written.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
