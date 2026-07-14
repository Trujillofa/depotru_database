"""CLI: website stock from J3 allowlist vs all warehouses (issue #182).

Dry-run by default. Optional Magento compare when MAGENTO_* env is set.
Optional Magento MSI write with --apply (gated; fights b2c.smart-business if
that feed is still active — prefer configuring B2C denylist first).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_website_stock import WebsiteStockRunner
from business_analyzer.core.website_warehouse_policy import (
    MAGENTO_WEBSITE_MSI_SOURCES,
    policy_summary,
)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Website stock allowlist (J3): impact of excluding garantías, "
            "exhibición, ajustes temporales, MDL, COMITECAFE"
        )
    )
    p.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Top SKUs with excluded stock to list (default 30)",
    )
    p.add_argument(
        "--sku",
        action="append",
        default=[],
        help="Limit to SKU (repeatable)",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Print JSON report",
    )
    p.add_argument(
        "--compare-magento",
        action="store_true",
        help="Compare sample SKUs to Magento MSI (needs MAGENTO_BASE_URL + token)",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Write website_qty to Magento MSI source-items for --sku list "
            "(requires --source-code; dangerous if B2C still overwrites)"
        ),
    )
    p.add_argument(
        "--source-code",
        default="default",
        choices=list(MAGENTO_WEBSITE_MSI_SOURCES),
        help="MSI source to update when using --apply (default: default)",
    )
    p.add_argument(
        "--output",
        default="",
        help="Optional path to write markdown/JSON report",
    )
    return p.parse_args(argv)


def _magento_compare(skus: List[str]) -> List[Dict[str, Any]]:
    from depotru_integrations.magento.client import MagentoConfig, MagentoRestClient

    config = MagentoConfig.from_env()
    if not config:
        return [
            {
                "status": "skipped",
                "reason": "MAGENTO_BASE_URL / MAGENTO_ACCESS_TOKEN not set",
            }
        ]
    client = MagentoRestClient(config)
    out: List[Dict[str, Any]] = []
    for sku in skus:
        try:
            payload = client.sellable_qty(sku)
            out.append(
                {
                    "sku": sku,
                    "magento_raw_qty": payload.get("raw_qty"),
                    "magento_sellable_qty": payload.get("sellable_qty"),
                    "magento_sources": payload.get("sources"),
                    "status": "ok",
                }
            )
        except Exception as exc:  # noqa: BLE001 — surface per-SKU errors
            out.append({"sku": sku, "status": "error", "error": str(exc)})
    return out


def _magento_apply(
    rows: List[Dict[str, Any]],
    *,
    source_code: str,
) -> List[Dict[str, Any]]:
    from depotru_integrations.magento.client import MagentoConfig, MagentoRestClient

    config = MagentoConfig.from_env()
    if not config:
        raise RuntimeError("Magento not configured (MAGENTO_BASE_URL + token)")
    client = MagentoRestClient(config)
    items = []
    for row in rows:
        sku = str(row.get("sku") or "")
        qty = float(row.get("website_qty") or 0)
        if not sku:
            continue
        items.append(
            {
                "sku": sku,
                "source_code": source_code,
                "quantity": qty,
                "status": 1 if qty > 0 else 0,
            }
        )
    if not items:
        return []
    result = client.post_source_items(items)
    return [{"posted": len(items), "result": result}]


def render_markdown(report: Dict[str, Any]) -> str:
    pol = report.get("policy") or {}
    summary = report.get("impact_summary") or {}
    lines = [
        "# Website stock — J3 warehouse allowlist",
        "",
        f"- **Generated:** {report.get('generated_at')}",
        f"- **Issue:** {pol.get('issue')}",
        "",
        "## Policy",
        "",
        f"- **Denylist:** {', '.join(pol.get('denylist') or [])}",
        f"- **Allowlist:** {', '.join(pol.get('allowlist') or [])}",
        f"- **Magento MSI:** {', '.join(pol.get('magento_msi_sources') or [])}",
        f"- **Note:** {pol.get('magento_dual_source_note')}",
        "",
        "## J3 impact summary",
        "",
        f"- **Website qty (allowlist sum):** {summary.get('website_qty_sum')}",
        f"- **Excluded qty (denylist sum):** {summary.get('excluded_qty_sum')}",
        f"- **All warehouses qty:** {summary.get('all_warehouses_qty_sum')}",
        f"- **SKUs touched:** {summary.get('sku_rows_touched')}",
        "",
        "## Top SKUs with stock on denylisted warehouses",
        "",
        "| SKU | Name | Website qty | Excluded qty | All qty |",
        "|-----|------|------------:|-------------:|--------:|",
    ]
    for row in report.get("excluded_skus") or []:
        name = str(row.get("name") or "")[:40]
        lines.append(
            f"| {row.get('sku')} | {name} | "
            f"{float(row.get('website_qty') or 0):.0f} | "
            f"{float(row.get('excluded_qty') or 0):.0f} | "
            f"{float(row.get('all_warehouses_qty') or 0):.0f} |"
        )
    if report.get("magento_compare"):
        lines.extend(["", "## Magento compare", ""])
        for row in report["magento_compare"]:
            lines.append(f"- `{row}`")
    lines.extend(
        [
            "",
            "## Next steps",
            "",
            "1. Prefer configuring the same denylist in **b2c.smart-business.app** "
            "so the live feed stops aggregating excluded almacenes.",
            "2. Use this CLI to measure impact and spot-check SKUs.",
            "3. Only use `--apply` if intentionally replacing B2C for listed SKUs "
            "(B2C may overwrite during business hours).",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.apply and not args.sku:
        print("ERROR: --apply requires at least one --sku", file=sys.stderr)
        return 2

    runner = WebsiteStockRunner(Database())
    report: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy": policy_summary(),
        "impact_summary": runner.impact_summary(),
        "excluded_skus": (
            runner.stock_by_sku(skus=args.sku)
            if args.sku
            else runner.skus_with_excluded_stock(top_n=args.top_n)
        ),
        "mode": "apply" if args.apply else "dry-run",
    }

    if args.compare_magento:
        sample = [
            str(r.get("sku")) for r in report["excluded_skus"][:15] if r.get("sku")
        ]
        if args.sku:
            sample = list(args.sku)
        report["magento_compare"] = _magento_compare(sample)

    if args.apply:
        print(
            "WARNING: Writing Magento MSI. B2C may overwrite during business hours.",
            file=sys.stderr,
        )
        report["magento_apply"] = _magento_apply(
            report["excluded_skus"],
            source_code=args.source_code,
        )

    if args.json:
        text = json.dumps(report, indent=2, default=str, ensure_ascii=False)
    else:
        text = render_markdown(report)

    print(text)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            text + ("\n" if not text.endswith("\n") else ""), encoding="utf-8"
        )
        print(f"Wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
