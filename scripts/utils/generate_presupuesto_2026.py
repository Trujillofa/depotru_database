#!/usr/bin/env python3
"""Generate 2026 presupuesto_vendedores / presupuesto_lineas from 2025 actuals.

Default: dry-run artifacts under data/export/presupuesto_2026/
Active vendors = last complete calendar month ∪ FEF (Sika), merges 123/133→162.

Usage:
  python scripts/utils/generate_presupuesto_2026.py roster
  python scripts/utils/generate_presupuesto_2026.py generate
  python scripts/utils/generate_presupuesto_2026.py generate --apply
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date, datetime
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
    DEFAULT_CODE_MERGES,
    DEFAULT_GROWTH,
    EXCLUDED_DOC_CODES,
    EXCLUDED_PRODUCT_NAMES,
    SIKA_DOC_CODE,
    apply_code_merge,
    build_h2_revision_comparison,
    build_presupuesto_2026,
    canonical_active_codes,
    last_complete_month,
    normalize_code,
    normalize_name,
    render_h2_revision_markdown,
    year_month_to_periodo,
)

DEFAULT_OUT = ROOT / "data" / "export" / "presupuesto_2026"


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


def _excl_products_sql(alias: str = "") -> str:
    col = f"UPPER(LTRIM(RTRIM({alias}ArticulosNombre)))"
    parts = [f"{col} <> '{n}'" for n in EXCLUDED_PRODUCT_NAMES]
    return " AND " + " AND ".join(parts) if parts else ""


def fetch_max_fecha(conn) -> date:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT MAX(Fecha) FROM banco_datos
        WHERE DocumentosCodigo NOT IN ({_excl_docs_sql()})
        """
    )
    row = cur.fetchone()
    cur.close()
    val = row[0]
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val)[:10])


def fetch_active_codes(conn, year: int, month: int) -> List[str]:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT DISTINCT LTRIM(RTRIM(vendedor_codigo))
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ({_excl_docs_sql()})
          AND YEAR(Fecha) = %s AND MONTH(Fecha) = %s
          AND vendedor_codigo IS NOT NULL AND LTRIM(RTRIM(vendedor_codigo)) <> ''
        UNION
        SELECT DISTINCT LTRIM(RTRIM(vendedor_codigo))
        FROM banco_datos
        WHERE DocumentosCodigo = '{SIKA_DOC_CODE}'
          AND YEAR(Fecha) = %s AND MONTH(Fecha) = %s
          AND vendedor_codigo IS NOT NULL AND LTRIM(RTRIM(vendedor_codigo)) <> ''
        """,
        (year, month, year, month),
    )
    codes = [r[0] for r in cur.fetchall() if r[0]]
    cur.close()
    return codes


def fetch_primary_names(conn, year: int, month: int) -> Dict[str, str]:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT LTRIM(RTRIM(vendedor_codigo)), LTRIM(RTRIM(VendedorFactura)), SUM(TotalSinIva)
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ({_excl_docs_sql()})
          AND YEAR(Fecha) = %s AND MONTH(Fecha) = %s
          AND vendedor_codigo IS NOT NULL AND LTRIM(RTRIM(vendedor_codigo)) <> ''
          AND VendedorFactura IS NOT NULL AND LTRIM(RTRIM(VendedorFactura)) <> ''
        GROUP BY LTRIM(RTRIM(vendedor_codigo)), LTRIM(RTRIM(VendedorFactura))
        """,
        (year, month),
    )
    best: Dict[str, Tuple[float, str]] = {}
    for code, name, sales in cur.fetchall():
        c = apply_code_merge(normalize_code(code) or "", DEFAULT_CODE_MERGES)
        s = float(sales or 0)
        if c not in best or s > best[c][0]:
            best[c] = (s, name)
    cur.close()
    names = {c: n for c, (_s, n) in best.items()}
    names["162"] = "WILLIAM HERNANDO QUINTERO G"
    return names


def fetch_sika_sales_by_code(conn, year: int, month: int) -> Dict[str, float]:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT LTRIM(RTRIM(vendedor_codigo)), SUM(TotalSinIva)
        FROM banco_datos
        WHERE DocumentosCodigo = '{SIKA_DOC_CODE}'
          AND YEAR(Fecha) = %s AND MONTH(Fecha) = %s
          AND vendedor_codigo IS NOT NULL AND LTRIM(RTRIM(vendedor_codigo)) <> ''
        GROUP BY LTRIM(RTRIM(vendedor_codigo))
        """,
        (year, month),
    )
    out: Dict[str, float] = {}
    for code, sales in cur.fetchall():
        c = apply_code_merge(normalize_code(code) or "", DEFAULT_CODE_MERGES)
        out[c] = out.get(c, 0.0) + float(sales or 0)
    cur.close()
    return out


def fetch_sales_rows(
    conn, years: Sequence[int]
) -> List[Tuple[Optional[str], Optional[str], Optional[str], int, int, float]]:
    """(code, factura, asignado, year, month, sales) including null codes."""
    cur = conn.cursor()
    year_list = ", ".join(str(y) for y in years)
    cur.execute(
        f"""
        SELECT
          CASE
            WHEN vendedor_codigo IS NULL OR LTRIM(RTRIM(vendedor_codigo)) = ''
              THEN NULL
            ELSE LTRIM(RTRIM(vendedor_codigo))
          END,
          VendedorFactura,
          VendedorAsignado,
          YEAR(Fecha),
          MONTH(Fecha),
          SUM(TotalSinIva)
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ({_excl_docs_sql()})
          AND YEAR(Fecha) IN ({year_list})
          {_excl_products_sql()}
        GROUP BY
          CASE
            WHEN vendedor_codigo IS NULL OR LTRIM(RTRIM(vendedor_codigo)) = ''
              THEN NULL
            ELSE LTRIM(RTRIM(vendedor_codigo))
          END,
          VendedorFactura,
          VendedorAsignado,
          YEAR(Fecha),
          MONTH(Fecha)
        """
    )
    rows = [
        (r[0], r[1], r[2], int(r[3]), int(r[4]), float(r[5] or 0))
        for r in cur.fetchall()
    ]
    cur.close()
    return rows


def fetch_coded_name_sales(conn, years: Sequence[int]) -> List[Tuple[str, str, float]]:
    cur = conn.cursor()
    year_list = ", ".join(str(y) for y in years)
    cur.execute(
        f"""
        SELECT LTRIM(RTRIM(vendedor_codigo)), VendedorFactura, SUM(TotalSinIva)
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ({_excl_docs_sql()})
          AND YEAR(Fecha) IN ({year_list})
          AND vendedor_codigo IS NOT NULL AND LTRIM(RTRIM(vendedor_codigo)) <> ''
          AND VendedorFactura IS NOT NULL AND LTRIM(RTRIM(VendedorFactura)) <> ''
          {_excl_products_sql()}
        GROUP BY LTRIM(RTRIM(vendedor_codigo)), VendedorFactura
        """
    )
    rows = [(r[0], r[1], float(r[2] or 0)) for r in cur.fetchall()]
    cur.close()
    return rows


def fetch_h1_2026(conn) -> Dict[str, float]:
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT LTRIM(RTRIM(vendedor_codigo)), SUM(TotalSinIva)
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ({_excl_docs_sql()})
          AND YEAR(Fecha) = 2026 AND MONTH(Fecha) <= 6
          AND vendedor_codigo IS NOT NULL AND LTRIM(RTRIM(vendedor_codigo)) <> ''
          {_excl_products_sql()}
        GROUP BY LTRIM(RTRIM(vendedor_codigo))
        """
    )
    out: Dict[str, float] = {}
    for code, sales in cur.fetchall():
        c = apply_code_merge(normalize_code(code) or "", DEFAULT_CODE_MERGES)
        out[c] = out.get(c, 0.0) + float(sales or 0)
    cur.close()
    return out


def fetch_line_shares(conn) -> Dict[str, List[Tuple[str, str, float]]]:
    """2024 line shares per vendor; __COMPANY__ fallback."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT LTRIM(RTRIM(vendedor_codigo)), linea, grupo, SUM(valor)
        FROM presupuesto_lineas
        WHERE periodo BETWEEN 20241 AND 202412
        GROUP BY LTRIM(RTRIM(vendedor_codigo)), linea, grupo
        """
    )
    by_code: Dict[str, List[Tuple[str, str, float]]] = {}
    company: Dict[Tuple[str, str], float] = {}
    for code, linea, grupo, valor in cur.fetchall():
        c = apply_code_merge(normalize_code(code) or "", DEFAULT_CODE_MERGES)
        v = float(valor or 0)
        by_code.setdefault(c, []).append((str(linea), str(grupo), v))
        key = (str(linea), str(grupo))
        company[key] = company.get(key, 0.0) + v
    cur.close()

    def to_shares(items: List[Tuple[str, str, float]]) -> List[Tuple[str, str, float]]:
        tot = sum(x[2] for x in items) or 1.0
        return [(a, b, c / tot) for a, b, c in items if c > 0]

    out: Dict[str, List[Tuple[str, str, float]]] = {
        c: to_shares(items) for c, items in by_code.items()
    }
    out["__COMPANY__"] = to_shares([(a, b, v) for (a, b), v in company.items()])
    return out


def write_csv(
    path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def cmd_roster(args: argparse.Namespace) -> None:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        maxf = fetch_max_fecha(conn)
        ly, lm = last_complete_month(maxf)
        raw = fetch_active_codes(conn, ly, lm)
        active = canonical_active_codes(raw, DEFAULT_CODE_MERGES)
        names = fetch_primary_names(conn, ly, lm)
        sika = fetch_sika_sales_by_code(conn, ly, lm)
        rows = []
        for code in active:
            rows.append(
                {
                    "vendedor_codigo": code,
                    "primary_name": names.get(code, ""),
                    "last_month": f"{ly:04d}-{lm:02d}",
                    "sika_fef_sales_last_month": sika.get(code, 0.0),
                    "is_sika": "Y" if sika.get(code, 0.0) > 0 else "N",
                    "merged_from": ",".join(
                        s for s, d in DEFAULT_CODE_MERGES.items() if d == code
                    ),
                }
            )
        write_csv(
            out_dir / "vendor_roster_active.csv",
            rows,
            [
                "vendedor_codigo",
                "primary_name",
                "last_month",
                "sika_fef_sales_last_month",
                "is_sika",
                "merged_from",
            ],
        )
        print(f"Last complete month: {ly}-{lm:02d} (as_of max fecha {maxf})")
        print(
            f"Active codes after merge: {len(active)} → {out_dir / 'vendor_roster_active.csv'}"
        )
        for r in rows:
            print(
                f"  {r['vendedor_codigo']:4} {str(r['primary_name'])[:32]:32} "
                f"SIKA={r['is_sika']} FEF={float(r['sika_fef_sales_last_month']):,.0f}"
            )
    finally:
        conn.close()


def cmd_generate(args: argparse.Namespace) -> None:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    growth = float(args.growth)
    conn = get_connection()
    try:
        maxf = fetch_max_fecha(conn)
        ly, lm = last_complete_month(maxf)
        raw = fetch_active_codes(conn, ly, lm)
        names = fetch_primary_names(conn, ly, lm)
        sales_rows = fetch_sales_rows(conn, [2025, 2026])
        coded_names = fetch_coded_name_sales(conn, [2025, 2026])
        h1 = fetch_h1_2026(conn)
        line_shares = fetch_line_shares(conn)

        result = build_presupuesto_2026(
            active_raw_codes=raw,
            sales_rows=sales_rows,
            coded_name_sales=coded_names,
            line_shares=line_shares,
            h1_2026_by_code=h1,
            primary_names=names,
            growth=growth,
        )

        write_csv(
            out_dir / "metas_vendedores_2026.csv",
            result.vendor_rows,
            ["periodo", "vendedor_codigo", "vendedor_nombre", "valor"],
        )
        write_csv(
            out_dir / "metas_lineas_2026.csv",
            result.line_rows,
            ["periodo", "vendedor_codigo", "linea", "grupo", "valor"],
        )
        write_csv(
            out_dir / "validation_h1_2026.csv",
            result.h1_report,
            ["vendedor_codigo", "meta_h1", "actual_h1", "cumplimiento_pct"],
        )

        # methodology / summary markdown
        company_h1_meta = sum(
            r["meta_h1"] for r in result.h1_report if r.get("meta_h1")
        )
        company_h1_act = sum(
            r["actual_h1"] for r in result.h1_report if r.get("actual_h1")
        )
        cumpl = company_h1_act / company_h1_meta * 100.0 if company_h1_meta else None
        md = out_dir / "validation_h1_2026.md"
        md.write_text(
            "\n".join(
                [
                    "# Presupuesto 2026 — dry-run validation",
                    "",
                    f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
                    f"- Last complete month (active set): {ly:04d}-{lm:02d}",
                    f"- Growth: {growth:.0%}",
                    f"- Active codes: {', '.join(result.active_codes)}",
                    f"- Merges: {DEFAULT_CODE_MERGES}",
                    f"- Company base 2025 (after pool): ${result.company_base_2025:,.0f}",
                    f"- Pool 2025 redistributed: ${result.pool_total_2025:,.0f}",
                    f"- Company meta 2026: ${result.company_meta_2026:,.0f}",
                    f"- H1 meta sum: ${company_h1_meta:,.0f}",
                    f"- H1 actual sum: ${company_h1_act:,.0f}",
                    f"- H1 cumplimiento: {cumpl:.1f}%"
                    if cumpl is not None
                    else "- H1 cumplimiento: n/a",
                    "",
                    "## Per-vendor H1",
                    "",
                    "| Code | Meta H1 | Actual H1 | Cumpl % |",
                    "|---|---:|---:|---:|",
                ]
                + [
                    f"| {r['vendedor_codigo']} | {r['meta_h1']:,.0f} | {r['actual_h1']:,.0f} | "
                    f"{r['cumplimiento_pct']:.1f} |"
                    if r.get("cumplimiento_pct") is not None
                    else f"| {r['vendedor_codigo']} | {r['meta_h1']:,.0f} | {r['actual_h1']:,.0f} | — |"
                    for r in result.h1_report
                ]
                + ["", f"Artifacts in `{out_dir}`", ""],
            ),
            encoding="utf-8",
        )

        print(md.read_text(encoding="utf-8")[:2000])
        print(f"\nWrote CSVs under {out_dir}")

        if args.apply:
            apply_to_db(conn, result.vendor_rows, result.line_rows)
            print(
                "Applied INSERT to presupuesto_vendedores / presupuesto_lineas (2026)."
            )
        else:
            print("Dry-run only (pass --apply to write DB).")
    finally:
        conn.close()


def cmd_compare(args: argparse.Namespace) -> None:
    """Dry-run: flat ×growth vs H1-rebased H2 two-pot+√ (never writes DB)."""
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    growth = float(args.growth)
    conn = get_connection()
    try:
        maxf = fetch_max_fecha(conn)
        ly, lm = last_complete_month(maxf)
        raw = fetch_active_codes(conn, ly, lm)
        names = fetch_primary_names(conn, ly, lm)
        sales_rows = fetch_sales_rows(conn, [2025, 2026])
        coded_names = fetch_coded_name_sales(conn, [2025, 2026])
        h1_code_only = fetch_h1_2026(conn)
        line_shares = fetch_line_shares(conn)

        result = build_presupuesto_2026(
            active_raw_codes=raw,
            sales_rows=sales_rows,
            coded_name_sales=coded_names,
            line_shares=line_shares,
            h1_2026_by_code=h1_code_only,
            primary_names=names,
            growth=growth,
        )

        # Prefer attributed H1 from build (includes null-code + Asignado)
        h1_attr = {
            r["vendedor_codigo"]: float(r["actual_h1"] or 0) for r in result.h1_report
        }
        # Fill gaps from code-only fetch
        for c, s in h1_code_only.items():
            if h1_attr.get(c, 0.0) <= 0 and s > 0:
                h1_attr[c] = float(s)

        rows, summary = build_h2_revision_comparison(
            flat_metas=result.vendor_month_metas,
            h1_by_code=h1_attr,
            seasonality=result.seasonality,
            active_codes=result.active_codes,
            names=result.names,
            growth=growth,
            h2_company_lock=args.h2_company_lock,
        )
        summary["pool_total_2025"] = result.pool_total_2025
        summary["company_base_2025"] = result.company_base_2025
        pool_pct = (
            result.pool_total_2025 / result.company_base_2025 * 100.0
            if result.company_base_2025
            else 0.0
        )

        lock = args.h2_company_lock
        notes = [
            f"H2 company lock: {lock} "
            + (
                "(Σ H2 two-pot = Σ current flat H2; reshape only)"
                if lock == "current"
                else f"(H2 target = H2 base from H1 × {1.0 + growth:.2f})"
            ),
            f"Active set from last complete month {ly:04d}-{lm:02d}",
            f"Pool 2025 redistributed ${result.pool_total_2025:,.0f} "
            f"({pool_pct:.2f}% of company base) — small fairness lever",
            "Attribution: Asignado > Factura owner > codigo (do not revert to raw screen base)",
            "H2 re-base uses attributed H1 actuals + 2025 seasonality shape",
            "No --apply on compare; generate --apply still uses flat full-year method only",
            "Field: keep Carlos off 131 (purity); not a meta formula fix",
        ]
        md = render_h2_revision_markdown(rows, summary, notes=notes)
        # Colombian-style thousands already in renderer for $; keep notes plain
        suffix = "_lockcurrent" if lock == "current" else ""
        out_md = out_dir / f"compare_h2_twopot_vs_flat{suffix}.md"
        out_md.write_text(md, encoding="utf-8")
        write_csv(
            out_dir / f"compare_h2_twopot_vs_flat{suffix}.csv",
            rows,
            [
                "vendedor_codigo",
                "vendedor_nombre",
                "h1_actual",
                "h1_meta_flat",
                "h1_cumpl_pct",
                "h2_base_from_h1",
                "h2_meta_flat_2025",
                "h2_meta_twopot_h1",
                "h2_delta_twopot_vs_flat",
                "h2_delta_pct",
                "full_year_flat",
                "full_year_hybrid",
            ],
        )
        # Also drop a copy under reports/ for easy browsing when default out_dir used
        reports_path = (
            ROOT / "reports" / f"PRESUPUESTO_H2_COMPARE_TWOPOT{suffix.upper()}.md"
        )
        reports: Optional[Path] = reports_path
        try:
            reports_path.write_text(md, encoding="utf-8")
        except OSError:
            reports = None

        print(md[:3500])
        print(f"\nWrote {out_md}")
        if reports:
            print(f"Wrote {reports}")
        print("Dry-run only (no DB writes).")
    finally:
        conn.close()


def apply_to_db(conn, vendor_rows: Sequence[Dict], line_rows: Sequence[Dict]) -> None:
    """Replace 2026 periodos only."""
    cur = conn.cursor()
    # All 2026 period encodings
    periodos = [year_month_to_periodo(2026, m) for m in range(1, 13)]
    ph = ",".join(["%s"] * len(periodos))
    cur.execute(
        f"DELETE FROM presupuesto_vendedores WHERE periodo IN ({ph})",
        tuple(periodos),
    )
    cur.execute(
        f"DELETE FROM presupuesto_lineas WHERE periodo IN ({ph})",
        tuple(periodos),
    )
    for r in vendor_rows:
        cur.execute(
            """
            INSERT INTO presupuesto_vendedores
              (periodo, vendedor_codigo, valor, vendedor_nombre)
            VALUES (%s, %s, %s, %s)
            """,
            (
                int(r["periodo"]),
                str(r["vendedor_codigo"]),
                float(r["valor"]),
                r.get("vendedor_nombre"),
            ),
        )
    for r in line_rows:
        cur.execute(
            """
            INSERT INTO presupuesto_lineas
              (periodo, vendedor_codigo, linea, grupo, valor)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                int(r["periodo"]),
                str(r["vendedor_codigo"]),
                str(r["linea"]),
                str(r["grupo"]),
                float(r["valor"]),
            ),
        )
    conn.commit()
    cur.close()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "command",
        choices=["roster", "generate", "compare"],
        help=(
            "roster: list last-month actives; "
            "generate: build metas (flat); "
            "compare: H2 rebased two-pot vs flat dry-run"
        ),
    )
    p.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUT),
        help="Artifact directory",
    )
    p.add_argument(
        "--growth",
        type=float,
        default=DEFAULT_GROWTH,
        help="Company stretch growth (default 0.25)",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="Write 2026 rows to DB (generate only; compare never applies)",
    )
    p.add_argument(
        "--h2-company-lock",
        choices=["growth", "current"],
        default="growth",
        help=(
            "compare only: H2 company total = H2 base × (1+growth), or "
            "'current' to lock Σ to today's flat H2 metas (reshape only)"
        ),
    )
    return p


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "roster":
        cmd_roster(args)
    elif args.command == "compare":
        cmd_compare(args)
    else:
        cmd_generate(args)


if __name__ == "__main__":
    main()
