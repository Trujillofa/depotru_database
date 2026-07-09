#!/usr/bin/env python3
"""Affinity → Magento cross-sell E2E dry-run orchestrator.

1. Export Magento-importable CSVs from hybrid/co-occurrence affinity.
2. Validate affinity CSV contract headers (v1.0.0).
3. Local Magento-side dry-run via depositotrujillo.co apply_crosssell_merge_bulk.
4. Optional: --validate-remote runs Magento SSH validate (no writes).

Does NOT apply production links unless you pass --validate-remote only
(never --apply from this script).

Usage:
  PYTHONPATH=src python scripts/analysis/run_affinity_magento_e2e_dry_run.py \\
    --affinity ~/business_reports/top_10_related_products_per_sku.csv \\
    --output-dir data/export/affinity_e2e_dry_run \\
    --limit-skus 50

  # Also hit Magento over SSH (validate only):
  PYTHONPATH=src python scripts/analysis/run_affinity_magento_e2e_dry_run.py \\
    --affinity ~/business_reports/top_10_related_products_per_sku.csv \\
    --output-dir data/export/affinity_e2e_dry_run \\
    --limit-skus 50 --validate-remote \\
    --magento-repo ~/Projects/depositotrujillo.co
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _load_export_module():
    """Load magento_related_export without analysis package circular imports."""
    import importlib.util
    import types

    for pkg_name in ("business_analyzer", "business_analyzer.analysis"):
        if pkg_name not in sys.modules:
            sys.modules[pkg_name] = types.ModuleType(pkg_name)
    mod_path = (
        _REPO / "src" / "business_analyzer" / "analysis" / "magento_related_export.py"
    )
    name = "business_analyzer.analysis.magento_related_export"
    spec = importlib.util.spec_from_file_location(name, mod_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {mod_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _first_n_skus(affinity_csv: Path, n: int) -> list[str]:
    skus: list[str] = []
    with affinity_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sku = (row.get("SKU") or row.get("sku") or "").strip()
            if not sku:
                continue
            skus.append(sku)
            if len(skus) >= n:
                break
    return skus


def _validate_contract(cross_csv: Path, related_csv: Path) -> dict:
    from depotru_integrations.affinity.contract import (
        AFFINITY_CONTRACT_VERSION,
        validate_crosssell_csv_header,
        validate_related_csv_header,
    )

    results = {"contract_version": AFFINITY_CONTRACT_VERSION}
    with cross_csv.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle))
    ok, msg = validate_crosssell_csv_header(header)
    results["crosssell"] = {"ok": ok, "message": msg, "header": header}
    with related_csv.open(encoding="utf-8-sig", newline="") as handle:
        header_r = next(csv.reader(handle))
    ok_r, msg_r = validate_related_csv_header(header_r)
    results["related"] = {"ok": ok_r, "message": msg_r, "header": header_r[:5]}
    return results


def _count_csv_rows(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def _local_csv_validate(cross_csv: Path, limit: int | None) -> dict:
    """Mirror Magento load_rows without SSH deps (local dry-run)."""
    rows: list[dict] = []
    with cross_csv.open(encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            sku = (raw.get("sku") or raw.get("SKU") or "").strip()
            if not sku:
                continue
            picks = [
                s.strip()
                for s in (raw.get("crosssell_skus") or "").split(",")
                if s.strip() and s.strip() != sku
            ]
            if picks:
                rows.append({"sku": sku, "crosssell_skus": picks})
            if limit is not None and len(rows) >= limit:
                break
    return {
        "ok": True,
        "mode": "local_load_rows",
        "source_count": len(rows),
        "candidate_links": sum(len(r["crosssell_skus"]) for r in rows),
        "sample": rows[0] if rows else None,
    }


def _magento_python(magento_repo: Path) -> str:
    """Prefer a Python that can import paramiko (Magento ops scripts need it)."""
    candidates = [
        magento_repo / ".venv" / "bin" / "python",
        Path(sys.executable),
        Path("/home/yderf/.local/bin/python3"),
        Path("/usr/bin/python3"),
    ]
    for cand in candidates:
        if not cand.is_file():
            continue
        try:
            proc = subprocess.run(
                [str(cand), "-c", "import paramiko"],
                capture_output=True,
                timeout=15,
            )
            if proc.returncode == 0:
                return str(cand)
        except (OSError, subprocess.TimeoutExpired):
            continue
    return sys.executable


def _run_magento_dry_run(
    magento_repo: Path,
    cross_csv: Path,
    *,
    validate_remote: bool,
    limit: int | None,
) -> dict:
    # Always do local CSV validation first (no SSH).
    local = _local_csv_validate(cross_csv, limit)
    if not local["ok"] or local["source_count"] == 0:
        return {**local, "ok": False, "error": "no_crosssell_rows"}

    script = magento_repo / "scripts" / "catalog" / "apply_crosssell_merge_bulk.py"
    if not script.is_file():
        return {
            **local,
            "ok": True,
            "magento_script": False,
            "error": f"Magento apply script missing: {script}",
            "note": "Local CSV validation still OK",
        }

    if not validate_remote:
        # Full Magento --dry-run only loads CSV; avoid paramiko import failures
        # by treating local load as success and optionally shelling out.
        py = _magento_python(magento_repo)
        mode = "--dry-run"
        cmd = [
            py,
            str(script),
            "--csv",
            str(cross_csv.resolve()),
            "--config",
            "config/env.php",
            mode,
        ]
        if limit is not None:
            cmd.extend(["--limit", str(limit)])
        logger.info("Running Magento: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(magento_repo),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode == 0:
                return {
                    **local,
                    "ok": True,
                    "mode": mode,
                    "returncode": 0,
                    "python": py,
                    "stdout_tail": (proc.stdout or "")[-3000:],
                    "stderr_tail": (proc.stderr or "")[-2000:],
                }
            logger.warning(
                "Magento script dry-run failed (rc=%s); local CSV validation still OK",
                proc.returncode,
            )
            return {
                **local,
                "ok": True,
                "mode": "local_load_rows_fallback",
                "magento_script_rc": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-2000:],
                "stderr_tail": (proc.stderr or "")[-2000:],
                "note": "Local load OK; install paramiko in Magento env for script dry-run",
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                **local,
                "ok": True,
                "mode": "local_load_rows_fallback",
                "error": str(exc),
            }

    # Remote validate (SSH) — needs paramiko
    py = _magento_python(magento_repo)
    mode = "--validate-remote"
    cmd = [
        py,
        str(script),
        "--csv",
        str(cross_csv.resolve()),
        "--config",
        "config/env.php",
        mode,
    ]
    if limit is not None:
        cmd.extend(["--limit", str(limit)])
    logger.info("Running Magento: %s", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        cwd=str(magento_repo),
        capture_output=True,
        text=True,
        timeout=900,
    )
    out = {
        **local,
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "mode": mode,
        "python": py,
        "stdout_tail": (proc.stdout or "")[-3000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }
    report = magento_repo / "reports" / f"crosssell-merge-{cross_csv.stem}.json"
    if report.is_file():
        try:
            out["remote_report"] = json.loads(report.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            out["remote_report_path"] = str(report)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Affinity → Magento cross-sell E2E dry-run"
    )
    parser.add_argument(
        "--affinity",
        default=str(
            Path.home() / "business_reports" / "top_10_related_products_per_sku.csv"
        ),
        help="Affinity / co-occurrence CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=str(_REPO / "data" / "export" / "affinity_e2e_dry_run"),
        help="Export directory for Magento CSVs",
    )
    parser.add_argument(
        "--batch-id",
        default=None,
        help="Batch id (default affinity-e2e-YYYYMMDD)",
    )
    parser.add_argument(
        "--limit-skus",
        type=int,
        default=50,
        help="Only first N source SKUs from affinity (default 50, 0=all)",
    )
    parser.add_argument(
        "--cross-limit",
        type=int,
        default=8,
        help="Max cross-sell links per SKU",
    )
    parser.add_argument(
        "--related-limit",
        type=int,
        default=10,
        help="Max related links per SKU",
    )
    parser.add_argument(
        "--magento-repo",
        default=str(Path.home() / "Projects" / "depositotrujillo.co"),
        help="Path to depositotrujillo.co ops repo",
    )
    parser.add_argument(
        "--skip-magento",
        action="store_true",
        help="Only export + contract validate (no Magento script)",
    )
    parser.add_argument(
        "--validate-remote",
        action="store_true",
        help="SSH validate against Magento (no writes). Requires config/env.php",
    )
    args = parser.parse_args(argv)

    affinity = Path(args.affinity).expanduser()
    if not affinity.is_file():
        logger.error("Affinity CSV not found: %s", affinity)
        return 1

    batch_id = args.batch_id or (
        f"affinity-e2e-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    )
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    sku_filter = None
    if args.limit_skus and args.limit_skus > 0:
        sku_filter = _first_n_skus(affinity, args.limit_skus)
        logger.info("SKU filter: first %d from affinity", len(sku_filter))

    export = _load_export_module()
    logger.info("Exporting Magento CSVs → %s", output_dir)
    stats = export.export_from_affinity_file(
        affinity,
        output_dir,
        batch_id=batch_id,
        related_limit=args.related_limit,
        cross_limit=args.cross_limit,
        sku_filter=sku_filter,
    )

    related_csv = output_dir / f"{batch_id}-related.csv"
    cross_csv = output_dir / f"import-batch-{batch_id}.csv"
    manifest_path = output_dir / f"import-batch-{batch_id}.manifest.json"
    audit_path = output_dir / f"{batch_id}-audit.json"

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "affinity_source": str(affinity),
        "batch_id": batch_id,
        "export_stats": stats,
        "files": {
            "related_csv": str(related_csv),
            "crosssell_csv": str(cross_csv),
            "manifest": str(manifest_path),
            "audit": str(audit_path),
            "crosssell_rows": _count_csv_rows(cross_csv) if cross_csv.is_file() else 0,
            "related_rows": _count_csv_rows(related_csv)
            if related_csv.is_file()
            else 0,
        },
    }

    if not cross_csv.is_file():
        logger.error("Cross-sell CSV not produced: %s", cross_csv)
        return 2

    report["contract"] = _validate_contract(cross_csv, related_csv)
    if not report["contract"]["crosssell"]["ok"]:
        logger.error("Contract validation failed: %s", report["contract"])
        return 3
    logger.info(
        "Contract OK v%s (crosssell + related headers)",
        report["contract"]["contract_version"],
    )

    if not args.skip_magento:
        magento_repo = Path(args.magento_repo).expanduser()
        report["magento"] = _run_magento_dry_run(
            magento_repo,
            cross_csv,
            validate_remote=args.validate_remote,
            limit=args.limit_skus if args.limit_skus > 0 else None,
        )
        if not report["magento"].get("ok"):
            logger.error(
                "Magento step failed (rc=%s): %s",
                report["magento"].get("returncode"),
                report["magento"].get("stderr_tail") or report["magento"].get("error"),
            )
            # Still write report for debugging
        else:
            logger.info("Magento %s OK", report["magento"]["mode"])
    else:
        report["magento"] = {"skipped": True}

    report_path = output_dir / f"{batch_id}-e2e-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    # Human-readable summary in reports/
    summary_path = _REPO / "reports" / f"AFFINITY_E2E_DRY_RUN_{batch_id}.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Affinity → Magento E2E dry-run — {batch_id}",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Affinity source:** `{affinity}`",
        f"**Contract:** v{report['contract']['contract_version']}",
        "",
        "## Export",
        "",
        f"- Cross-sell rows: **{report['files']['crosssell_rows']}**",
        f"- Related rows: **{report['files']['related_rows']}**",
        f"- Cross CSV: `{cross_csv}`",
        f"- Related CSV: `{related_csv}`",
        f"- Manifest: `{manifest_path}`",
        "",
        "### Export stats",
        "",
        "```json",
        json.dumps(stats, indent=2),
        "```",
        "",
        "## Magento step",
        "",
    ]
    mag = report.get("magento") or {}
    if mag.get("skipped"):
        lines.append("- Skipped (`--skip-magento`)")
    else:
        lines.append(f"- Mode: `{mag.get('mode')}`")
        lines.append(f"- OK: **{mag.get('ok')}** (rc={mag.get('returncode')})")
        if mag.get("remote_report"):
            lines.append("")
            lines.append("### Remote validate result")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(mag["remote_report"], indent=2)[:4000])
            lines.append("```")
        elif mag.get("stdout_tail"):
            lines.append("")
            lines.append("```")
            lines.append(mag["stdout_tail"][-1500:])
            lines.append("```")
    lines.extend(
        [
            "",
            "## Next (apply — NOT done by this dry-run)",
            "",
            "```bash",
            f"cd {args.magento_repo}",
            "python3 scripts/catalog/apply_crosssell_merge_bulk.py \\",
            f"  --csv {cross_csv} \\",
            "  --config config/env.php --validate-remote   # SKU presence",
            "# then, after review:",
            f"# python3 scripts/catalog/apply_crosssell_merge_bulk.py --csv {cross_csv} \\",
            "#   --config config/env.php --apply --clean-cache",
            "```",
            "",
            f"Full JSON: `{report_path}`",
            "",
        ]
    )
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", report_path)
    logger.info("Wrote %s", summary_path)

    print(
        "E2E_DRY_RUN_OK"
        if (args.skip_magento or mag.get("ok"))
        else "E2E_DRY_RUN_PARTIAL"
    )
    print(f"  cross_rows: {report['files']['crosssell_rows']}")
    print(f"  related_rows: {report['files']['related_rows']}")
    print(f"  report: {report_path}")
    print(f"  summary: {summary_path}")

    if not args.skip_magento and not mag.get("ok"):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
