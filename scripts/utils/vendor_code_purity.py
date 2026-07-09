#!/usr/bin/env python3
"""Vendor code purity report — owner card enforcement baseline.

Read-only against banco_datos. Flags multi-name / wrong-home bookings.

Usage:
  python scripts/utils/vendor_code_purity.py
  python scripts/utils/vendor_code_purity.py --month 2026-06
  python scripts/utils/vendor_code_purity.py --days 7
  python scripts/utils/vendor_code_purity.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from business_analyzer.core.presupuesto_2026 import (  # noqa: E402
    EXCLUDED_DOC_CODES,
    EXCLUDED_PRODUCT_NAMES,
    last_complete_month,
)
from business_analyzer.core.vendor_ownership import (  # noqa: E402
    ACTIVE_META_CODES_2026,
    DEFAULT_MATERIAL_THRESHOLD,
    OWNER_CARD,
    SalesSlice,
    analyze_purity,
    render_purity_markdown,
)

DEFAULT_OUT_DIR = ROOT / "reports"


def get_connection():
    import pymssql

    server = (os.getenv("DB_SERVER") or os.getenv("DB_HOST") or "").strip()
    if not server:
        raise ValueError("Missing DB_SERVER or DB_HOST")
    return pymssql.connect(
        server=server,
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "SmartBusiness"),
        port=os.getenv("DB_PORT", "1433"),
        login_timeout=30,
        timeout=300,
    )


def _excl_docs_sql() -> str:
    return ", ".join(f"'{c}'" for c in EXCLUDED_DOC_CODES)


def _excl_products_sql() -> str:
    col = "UPPER(LTRIM(RTRIM(ArticulosNombre)))"
    parts = [f"{col} <> '{n}'" for n in EXCLUDED_PRODUCT_NAMES]
    return " AND " + " AND ".join(parts) if parts else ""


def fetch_max_fecha(conn) -> date:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT MAX(CAST(Fecha AS DATE))
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ({_excl_docs_sql()})
        {_excl_products_sql()}
        """
    )
    row = cur.fetchone()
    if not row or not row[0]:
        raise RuntimeError("No sales dates in banco_datos")
    d = row[0]
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d)[:10])


def resolve_period(
    *,
    month: Optional[str],
    days: Optional[int],
    as_of: Optional[date],
) -> Tuple[date, date, str]:
    """Return (start, end inclusive, label)."""
    if days is not None and days > 0:
        end = as_of or date.today()
        start = end - timedelta(days=days - 1)
        return start, end, f"last_{days}d_{start.isoformat()}_{end.isoformat()}"
    if month:
        y, m = month.split("-")
        year, mon = int(y), int(m)
        start = date(year, mon, 1)
        end = date(year, mon, monthrange(year, mon)[1])
        return start, end, f"{year}-{mon:02d}"
    # default: last complete calendar month from max sale date
    conn = get_connection()
    try:
        max_f = fetch_max_fecha(conn)
    finally:
        conn.close()
    ly, lm = last_complete_month(max_f)
    start = date(ly, lm, 1)
    end = date(ly, lm, monthrange(ly, lm)[1])
    return start, end, f"{ly}-{lm:02d}"


def fetch_sales_slices(conn, start: date, end: date) -> List[SalesSlice]:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT
          LTRIM(RTRIM(CAST(vendedor_codigo AS NVARCHAR(20)))) AS codigo,
          LTRIM(RTRIM(VendedorFactura)) AS factura,
          LTRIM(RTRIM(VendedorAsignado)) AS asignado,
          LTRIM(RTRIM(DocumentosCodigo)) AS sede,
          SUM(CAST(TotalSinIva AS FLOAT)) AS sales
        FROM banco_datos
        WHERE CAST(Fecha AS DATE) BETWEEN %s AND %s
          AND DocumentosCodigo NOT IN ({_excl_docs_sql()})
          {_excl_products_sql()}
        GROUP BY
          LTRIM(RTRIM(CAST(vendedor_codigo AS NVARCHAR(20)))),
          LTRIM(RTRIM(VendedorFactura)),
          LTRIM(RTRIM(VendedorAsignado)),
          LTRIM(RTRIM(DocumentosCodigo))
        """,
        (start.isoformat(), end.isoformat()),
    )
    out: List[SalesSlice] = []
    for code, factura, asignado, sede, sales in cur.fetchall():
        out.append(
            SalesSlice(
                code=str(code).strip() if code is not None else None,
                factura_name=str(factura or ""),
                asignado=str(asignado) if asignado else None,
                sede=str(sede or ""),
                sales=float(sales or 0.0),
            )
        )
    return out


def smoke_enero_2026(conn) -> Dict[str, Any]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
          LTRIM(RTRIM(CAST(vendedor_codigo AS NVARCHAR(20)))) AS codigo,
          MAX(vendedor_nombre) AS nombre,
          SUM(CAST(valor AS FLOAT)) AS meta
        FROM presupuesto_vendedores
        WHERE periodo IN (20261, 202601)
        GROUP BY LTRIM(RTRIM(CAST(vendedor_codigo AS NVARCHAR(20))))
        ORDER BY 1
        """
    )
    rows = cur.fetchall()
    codes = [str(r[0]).strip() for r in rows]
    total = sum(float(r[2] or 0) for r in rows)
    expected = set(ACTIVE_META_CODES_2026)
    have = set(codes)
    missing = sorted(expected - have)
    extra = sorted(have - expected)
    ok = len(codes) == len(expected) and not missing
    return {
        "code_count": len(codes),
        "expected": len(expected),
        "total_meta": total,
        "codes": codes,
        "missing_codes": missing,
        "extra_codes": extra,
        "status": "OK" if ok else "MISMATCH",
        "names": {str(r[0]).strip(): str(r[1] or "") for r in rows},
    }


def report_to_dict(
    report, enero_smoke: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    return {
        "period_label": report.period_label,
        "material_threshold": report.material_threshold,
        "handoff_ok_sales": report.handoff_ok_sales,
        "findings": [
            {
                "severity": f.severity,
                "code": f.code,
                "check": f.check,
                "message": f.message,
                "sales": f.sales,
                "detail": f.detail,
            }
            for f in report.findings
        ],
        "by_code_sales": report.by_code_sales,
        "merge_orphan_sales": report.merge_orphan_sales,
        "owner_card_codes": list(OWNER_CARD.keys()),
        "enero_smoke": enero_smoke,
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Vendor code purity / owner-card enforcement"
    )
    p.add_argument(
        "--month",
        default="",
        help="Calendar month YYYY-MM (default: last complete month)",
    )
    p.add_argument(
        "--days",
        type=int,
        default=0,
        help="If >0, analyze last N days ending today (or --as-of)",
    )
    p.add_argument(
        "--as-of",
        default="",
        help="Anchor date YYYY-MM-DD for last-month / last-N-days",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_MATERIAL_THRESHOLD,
        help="Material COP threshold for flags",
    )
    p.add_argument(
        "--output",
        default="",
        help="Markdown output path (default: reports/VENDOR_CODE_PURITY_<period>.md)",
    )
    p.add_argument("--json", action="store_true", help="Print JSON to stdout")
    p.add_argument(
        "--no-enero-smoke",
        action="store_true",
        help="Skip Enero 2026 presupuesto smoke check",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze but do not write report file",
    )
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    start, end, label = resolve_period(
        month=args.month or None,
        days=args.days if args.days > 0 else None,
        as_of=as_of,
    )

    conn = get_connection()
    try:
        slices = fetch_sales_slices(conn, start, end)
        enero = None if args.no_enero_smoke else smoke_enero_2026(conn)
    finally:
        conn.close()

    report = analyze_purity(
        slices,
        period_label=f"{label} ({start.isoformat()} → {end.isoformat()})",
        material_threshold=float(args.threshold),
    )
    md = render_purity_markdown(report, enero_smoke=enero)

    out_path: Optional[Path] = None
    if not args.dry_run:
        out_path = (
            Path(args.output)
            if args.output
            else DEFAULT_OUT_DIR / f"VENDOR_CODE_PURITY_{label.replace('-', '')}.md"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")

    if args.json:
        print(json.dumps(report_to_dict(report, enero), indent=2, default=str))
    else:
        print(md)
        if out_path:
            print(f"\n# wrote {out_path}", file=sys.stderr)

    # Non-zero exit if errors (useful for CI/cron later)
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
