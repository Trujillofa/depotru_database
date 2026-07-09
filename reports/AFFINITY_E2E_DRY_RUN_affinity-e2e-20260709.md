# Affinity → Magento E2E dry-run — affinity-e2e-20260709

**Generated:** 2026-07-09T23:01:59.522898+00:00
**Affinity source:** `/home/yderf/business_reports/top_10_related_products_per_sku.csv`
**Contract:** v1.0.0

## Export

- Cross-sell rows: **50**
- Related rows: **50**
- Cross CSV: `data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709.csv`
- Related CSV: `data/export/affinity_e2e_dry_run/affinity-e2e-20260709-related.csv`
- Manifest: `data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709.manifest.json`

### Export stats

```json
{
  "related_rows": 50,
  "cross_rows": 50,
  "merged_skus": 50,
  "related_path": "data/export/affinity_e2e_dry_run/affinity-e2e-20260709-related.csv",
  "cross_path": "data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709.csv",
  "audit_path": "data/export/affinity_e2e_dry_run/affinity-e2e-20260709-audit.json"
}
```

## Magento step

- Mode: `--dry-run`
- OK: **True** (rc=0)

## Next (apply — NOT done by this dry-run)

```bash
cd /home/yderf/Projects/depositotrujillo.co
python3 scripts/catalog/apply_crosssell_merge_bulk.py \
  --csv data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709.csv \
  --config config/env.php --validate-remote   # SKU presence
# then, after review:
# python3 scripts/catalog/apply_crosssell_merge_bulk.py --csv data/export/affinity_e2e_dry_run/import-batch-affinity-e2e-20260709.csv \
#   --config config/env.php --apply --clean-cache
```

Full JSON: `data/export/affinity_e2e_dry_run/affinity-e2e-20260709-e2e-report.json`
