# Website stock — J3 warehouse allowlist

**Issue:** [depositotrujillo.co#182](https://github.com/Trujillofa/depositotrujillo.co/issues/182)
**Code SSOT:** `business_analyzer.core.website_warehouse_policy`
**CLI:** `depotru-website-stock`

## Problem

b2c.smart-business.app aggregates J3 inventory into Magento MSI (`default` + `CENTRO`).
If **all** J3 almacenes are included, website salable qty can include stock that must not be sold online (garantías, exhibición, ML, etc.).

Magento never stores J3 codes — filtering must happen **before** Magento (B2C config) or via a controlled writer that only posts allowlisted totals.

## Policy (ops 2026-07-14)

### Denylist (exclude)

| Code | Name |
|------|------|
| CEN | 005 GARANTIAS |
| EXH | BOD EXHIBICION ALMACEN |
| EXD | BOD EXHIBICION DISTRIBUCIONES |
| BDT | BODEGA AJUSTES TEMPORALES |
| MDL | MERCADO LIBRE |
| TRA | MCIA COMITECAFE |

### Allowlist (include)

ALM, SUR, BD6, BOD, DIS, FLO, B.ROT, CON

### Magento dual source

Website channel uses stock **Total Disponible** = `default` + `CENTRO` **intentionally** (promos).
Do not collapse MSI stock linkage without a new product decision.

## CLI

```bash
# Impact: how much qty sits on denylisted warehouses
depotru-website-stock

# Top SKUs with excluded stock (JSON)
depotru-website-stock --json --top-n 50

# Compare a SKU to Magento MSI (needs MAGENTO_BASE_URL + MAGENTO_ACCESS_TOKEN)
depotru-website-stock --sku 0020280079 --compare-magento

# Gated write (optional; B2C may overwrite)
depotru-website-stock --sku 0020280079 --apply --source-code default
```

## Preferred ops path

1. Apply the same denylist in **b2c.smart-business.app** warehouse selection.
2. Use this repo’s CLI to **measure** impact and verify SKUs.
3. Only use `--apply` if intentionally shadowing B2C for listed SKUs.

## Related

- `docs/reference/j3system-sales-warehouse-query.md` — sales warehouse routing
- Sibling runbook: `depositotrujillo.co/docs/runbooks/b2c-website-warehouse-allowlist.md`
