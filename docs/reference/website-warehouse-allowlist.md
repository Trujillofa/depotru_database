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
3. Until B2C is fixed, run the **scheduled MSI re-apply** (below).

## Scheduled Magento re-apply (until B2C denylist)

Counteracts b2c.smart-business re-push of denylist warehouses.

```bash
# Install user systemd timer (every 2h 07–17 + 21:30)
./scripts/ops/install_website_stock_timer.sh

systemctl --user status depotru-website-stock-allowlist.timer
journalctl --user -u depotru-website-stock-allowlist.service -n 40
tail -5 ~/business_reports/website_stock_allowlist_sync.log

# Manual / dry-run
PYTHONPATH=src .venv/bin/python scripts/ops/run_website_stock_allowlist_sync.py --dry-run
PYTHONPATH=src .venv/bin/python scripts/ops/run_website_stock_allowlist_sync.py
```

Credentials: `~/.config/depotru/website-stock.env` (install script) plus
`MAGENTO_ENV_PHP` → sibling `depositotrujillo.co/config/env.php` for SSH password.
Requires J3/SmartBusiness DB access from depotru `.env` / NCX.

## Related

- `docs/reference/j3system-sales-warehouse-query.md` — sales warehouse routing
- Sibling runbook: `depositotrujillo.co/docs/runbooks/b2c-website-warehouse-allowlist.md`
