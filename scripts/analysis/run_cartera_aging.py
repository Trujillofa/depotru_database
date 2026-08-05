#!/usr/bin/env python3
"""CLI: Cartera / AR aging (banco_cartera snapshot report)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from business_analyzer.reports.cartera_aging import (  # noqa: E402
    build_cartera_result,
    default_as_of_date,
)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Cartera / Aging: cuentas por cobrar, mora, concentración y cupos "
            "(SmartBusiness banco_cartera, último snapshot fecha_carga)"
        )
    )
    p.add_argument(
        "--as-of-date",
        default=default_as_of_date(),
        help="Reference date YYYY-MM-DD (default: yesterday)",
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Max rows per action table (default: 25)",
    )
    p.add_argument(
        "--dso-days",
        type=int,
        default=30,
        help="Sales window in days for DSO (default: 30)",
    )
    p.add_argument(
        "--no-dso",
        action="store_true",
        help="Skip DSO / banco_datos sales query",
    )
    p.add_argument(
        "--output",
        default="",
        help="Output path (default: reports/CARTERA_AGING_<date>.html)",
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
        custom_name = out.name
    else:
        output_dir = _REPO / "reports"
        custom_name = None

    if args.json_only:
        from business_analyzer.core.cartera_aging import CarteraAgingRunner
        from business_analyzer.core.database import Database

        runner = CarteraAgingRunner(
            Database(),
            top_n=args.top_n,
            dso_days=args.dso_days,
            include_dso=not args.no_dso,
        )
        report = runner.build_report(args.as_of_date)
        print(json.dumps(report, indent=2, default=str))
        return 0

    result = build_cartera_result(
        as_of_date=args.as_of_date,
        top_n=args.top_n,
        dso_days=args.dso_days,
        include_dso=not args.no_dso,
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

    print(f"✅ Cartera aging: {written}")
    if args.json:
        print(f"✅ JSON: {written.with_suffix('.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
