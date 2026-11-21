"""Read-only J3 quote-search probe; run one immutable source tree per process.

Example: python scripts/analysis/run_bff_search_regression.py --source . \
    --env-file /path/to/.env --label integrated --output evidence/integrated.json
Only SELECT statements without semicolons may reach the configured database.
No HTTP, Magento enrichment, schema changes, jobs, or service control.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

QUERIES = [
    "sikafill galon",
    "varila 3/8",
    "cemento gris",
    "sikafill",
    "sikafill 7 galon",
    "sikafill 7 x galon precio",
    "precio sikafill",
    "sikafill galón",
    "sikafill/galon",
    "sika fill galon",
    "varilla 3/8",
    "varilla 1/2",
    "cemento gris 50",
    "cemento argos",
    "sikaflex 1a",
    "sikadur 32",
    "pintura blanca",
    "tubo pvc 1/2",
    "impermeabilizante sika",
    "revestimiento",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from dotenv import load_dotenv

    load_dotenv(args.env_file, override=False)
    os.environ.update(
        DB_LOGIN_TIMEOUT="10",
        DB_TIMEOUT="30",
        DB_QUERY_RETRIES="0",
        DB_POOL_ENABLED="false",
    )
    sys.path.insert(0, str(args.source.resolve() / "src"))
    from business_analyzer.core.database import Database
    from depotru_tools import builtins

    original = Database.execute_query
    calls = []

    def select_only(self, query, params=None, fetch=True):
        if (
            not query.lstrip().upper().startswith("SELECT ")
            or not fetch
            or ";" in query
        ):
            # Semicolons inside a SQL string literal are harmless. Our bounded
            # name predicate replaces ';'; remove literals before this check.
            import re

            structural = re.sub(r"'(?:''|[^'])*'", "''", query)
            if (
                not structural.lstrip().upper().startswith("SELECT ")
                or not fetch
                or ";" in structural
            ):
                raise RuntimeError("read-only probe rejected SQL")
        calls.append({"sql": query, "params": list(params or [])})
        return original(self, query, params, fetch)

    Database.execute_query = select_only
    result = {
        "label": args.label,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "scope": "_quote_search_j3 only; real J3 SELECTs; no HTTP or enrichment",
        "cases": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for i, query in enumerate(QUERIES, 1):
        for limit in (6, 25):
            calls.clear()
            start = time.monotonic()
            try:
                rows = builtins._quote_search_j3(query, limit=limit)
                safe = [
                    {
                        k: r[k]
                        for k in (
                            "sku",
                            "name",
                            "price",
                            "iva_rate",
                            "line_id",
                            "website_qty",
                        )
                    }
                    for r in rows
                ]
                case = dict(
                    id=i,
                    query=query,
                    limit=limit,
                    rows=safe,
                    count=len(safe),
                    status="ok",
                )
            except Exception as exc:
                case = dict(
                    id=i,
                    query=query,
                    limit=limit,
                    rows=[],
                    status="error",
                    error_class=type(exc).__name__,
                )
            case.update(seconds=round(time.monotonic() - start, 3), calls=list(calls))
            result["cases"].append(case)
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str)
            )
            print(args.label, i, limit, case["status"], case.get("count"), flush=True)
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str)
    )
    assert len(result["cases"]) == 40
    return int(any(c["status"] != "ok" for c in result["cases"]))


if __name__ == "__main__":
    raise SystemExit(main())
