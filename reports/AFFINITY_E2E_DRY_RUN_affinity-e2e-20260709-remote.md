# Affinity → Magento E2E dry-run — affinity-e2e-20260709-remote

**Generated:** 2026-07-09T23:02:03.739915+00:00
**Affinity source:** `/home/yderf/business_reports/top_10_related_products_per_sku.csv`
**Contract:** v1.0.0

## Export

- Cross-sell rows: **25**
- Related rows: **25**
- Cross CSV: `data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709-remote.csv`
- Related CSV: `data/export/affinity_e2e_dry_run/affinity-e2e-20260709-remote-related.csv`
- Manifest: `data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709-remote.manifest.json`

### Export stats

```json
{
  "related_rows": 25,
  "cross_rows": 25,
  "merged_skus": 25,
  "related_path": "data/export/affinity_e2e_dry_run/affinity-e2e-20260709-remote-related.csv",
  "cross_path": "data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709-remote.csv",
  "audit_path": "data/export/affinity_e2e_dry_run/affinity-e2e-20260709-remote-audit.json"
}
```

## Magento step

- Mode: `--validate-remote`
- OK: **True** (rc=0)

### Remote validate result

```json
{
  "mode": "validate",
  "source_count": 25,
  "candidate_links": 200,
  "links_added": 0,
  "links_skipped_existing": 0,
  "skipped_missing_source": 0,
  "skipped_missing_linked": 0,
  "missing_skus_sample": [
    "0020280001",
    "0020280100",
    "0090060016"
  ],
  "missing_skus_count": 3
}
```

## Next (apply — NOT done by this dry-run)

```bash
cd /home/yderf/Projects/depositotrujillo.co
python3 scripts/catalog/apply_crosssell_merge_bulk.py \
  --csv data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709-remote.csv \
  --config config/env.php --validate-remote   # SKU presence
# then, after review:
# python3 scripts/catalog/apply_crosssell_merge_bulk.py --csv data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709-remote.csv \
#   --config config/env.php --apply --clean-cache
```

Full JSON: `data/export/affinity_e2e_dry_run/affinity-e2e-20260709-remote-e2e-report.json`
