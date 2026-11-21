"""Aggregate the 80 baseline calls and 40 integrated calls without DB access."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

NOTES = {
    1: "Preserves advisor recall and first six.",
    2: "Unchanged empty; typo suggestions remain a separate confirmation path.",
    3: "Same SKU order; stock changed between sequential runs.",
    4: "Preserves advisor recall; stock drift on one SKU.",
    5: "Preserves advisor precision: family 7 must match name, never a SKU substring.",
    6: "Improves main recall at 25; noise removed and family 7 enforced.",
    7: "Improves main recall at 25; price is noise, not a product-name constraint.",
    8: "Improves both: accented galón normalized.",
    9: "Preserves main first six, improves recall at 25; slash separated.",
    10: "Preserves advisor recall and first six.",
    11: "Preserves advisor three literal 3/8 matches; stock drift on one SKU.",
    12: "Preserves advisor three literal 1/2 matches; not a semantic suitability guarantee.",
    13: "Preserves three 50KG/50 KG matches without matching 150KG or SKU digits.",
    14: "Identical to both.",
    15: "Preserves advisor recall and first six; combo relevance is not certified.",
    16: "Identical to both.",
    17: "Identical to both; one result does not certify family coverage.",
    18: "LOWER COUNT: 0 intentionally replaces CPVC/11/2/PEGATUBO 1/256. No valid PVC 1/2 lost from either observed baseline.",
    19: "Unchanged empty; storefront category/semantic search not measured here.",
    20: "Unchanged empty; storefront categories remain a separate path.",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("evidence"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sources = {
        "main": "main-results.json",
        "advisor": "advisor-results.json",
        "integrated": "integrated-final-results.json",
    }
    versions = {}
    for label, filename in sources.items():
        raw = (args.input / filename).read_bytes()
        data = json.loads(raw)
        assert len(data["cases"]) == 40 and data.get("finished_at")
        assert len({(c["id"], c["limit"]) for c in data["cases"]}) == 40
        assert all(c["status"] == "ok" for c in data["cases"])
        # Retain public catalog observations, never env or connection details.
        clean = {k: v for k, v in data.items() if k != "cases"}
        clean["raw_sha256"] = hashlib.sha256(raw).hexdigest()
        clean["cases"] = [
            {k: v for k, v in c.items() if k != "calls"} for c in data["cases"]
        ]
        versions[label] = clean
    lines = [
        "# Read-only J3 comparison",
        "",
        "80 baseline calls (20 queries × 2 limits × 2 refs), plus 40 integrated calls; all completed without errors.",
        "Counts are returned rows, not catalog totals. Precision is evaluated separately from count.",
        "",
        "| # | Limit | Query | Main | Advisor | Integrated | Assessment |",
        "|---|---:|---|---:|---:|---:|---|",
    ]
    price_changes, stock_changes = [], []
    for i, c in enumerate(versions["integrated"]["cases"]):
        cases = [versions[k]["cases"][i] for k in versions]
        assert all(
            (x["id"], x["query"], x["limit"]) == (c["id"], c["query"], c["limit"])
            for x in cases
        )
        lines.append(
            f"| {c['id']} | {c['limit']} | `{c['query']}` | "
            + " | ".join(str(x["count"]) for x in cases)
            + f" | {NOTES[c['id']]} |"
        )
        for label in ("main", "advisor"):
            old = {r["sku"]: r for r in versions[label]["cases"][i]["rows"]}
            for row in c["rows"]:
                if row["sku"] not in old:
                    continue
                delta = [k for k in row if row[k] != old[row["sku"]].get(k)]
                event = dict(
                    id=c["id"],
                    limit=c["limit"],
                    baseline=label,
                    sku=row["sku"],
                    fields=delta,
                )
                if any(k in delta for k in ("price", "iva_rate", "line_id")):
                    price_changes.append(event)
                if "website_qty" in delta:
                    stock_changes.append(event)
    result = {
        "versions": versions,
        "baseline_calls": 80,
        "integrated_calls": 40,
        "shared_price_iva_changes": price_changes,
        "shared_stock_changes": stock_changes,
        "lower_count_requires_owner_visibility": [
            dict(id=18, limits=[6, 25], reason=NOTES[18])
        ],
    }
    (args.output / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output / "comparison.md").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "baseline_calls": 80,
                "integrated_calls": 40,
                "errors": 0,
                "shared_price_iva_changes": len(price_changes),
                "stock_drift_comparisons": len(stock_changes),
            }
        )
    )


if __name__ == "__main__":
    main()
