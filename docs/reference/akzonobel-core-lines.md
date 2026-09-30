# AkzoNobel Core Lines — SKUs sin penetración por territorio

**Issue:** [Phase 3 / #65](https://github.com/Trujillofa/depotru_database/issues/65) (part B)
**CLI:** `depotru-akzonobel-core-lines`
**Code:** `business_analyzer.jobs.akzonobel_core_lines`

Recommended ops report: for each **active territory** (it sold other products in
the period), list Core Lines SKUs that had **zero positive sales**. Territories
are ranked by potential (sum of `TotalSinIva`) so the team knows where to push.

A territory is ranked only if it sold at least one **non-Core** SKU. Selling
only Core Lines SKUs does not rank it. Credit notes (`Cantidad` ≤ 0) and
zero-total lines (`TotalSinIva` ≤ 0) do not count as a sale. Returns are
**not netted**: potential is the sum of positive lines only. Service/bag
names from `SalesQueryRunner` (`EXCLUDED_PRODUCT_NAMES`) are dropped, so a
territory that only bought those items is not active.

## Territory dimension

**Default: `vendedor_codigo` (key) + `VendedorFactura` (label).**

That is the commercial owner already used by `manager_report` budget-vs-actual
(`presupuesto_vendedores`) and the KPI board. It is the only sales-territory
grain the existing SmartBusiness reports treat as “who owns the sale.”

Documented alternatives on `banco_datos` (set in the YAML or `--dimension`):

| Value | Fields | When to use |
|-------|--------|-------------|
| `vendedor` (default) | `vendedor_codigo` / `VendedorFactura` | Salesperson / commercial route |
| `ciudad` | `ciudad` / `ciudad` | Customer city on the sales fact |
| `departamento` | `departamento` / `departamento` | Customer department |

`zona_unica` / `regional` exist on J3/cartera master data, not on `banco_datos`
sales facts. Branch / sede (`DocumentosCodigo` FED/FEF/FET, Neiva vs Florencia)
is Phase 4+ and is out of scope here.

## Core Lines SKU list (synthetic placeholder)

The shipped file is **not** a live catalog:

`src/business_analyzer/jobs/data/akzonobel_core_lines.yaml`

It is labelled `SYNTHETIC PLACEHOLDER` (`placeholder: true`). SKUs are
`AKZO-DEMO-001` … `AKZO-DEMO-003`. Matching is by `ArticulosCodigo` only.
The live query reads `banco_datos` only; it does not join
`productos_adicional` or select `proveedor` / `marca`. Replace the list and
set `placeholder: false` before a live run. Live mode **refuses** to query
the database while `placeholder: true`. `--synthetic` and unit tests still
work. Do not invent real AkzoNobel / Pintuco codes in git.

Override path via `--config` or Settings `AKZONOBEL_CORE_LINES_CONFIG`
(pydantic-settings). JSON and a `sku,name` CSV are also accepted (CSV loads
as placeholder).

## How to run locally (synthetic, no DB)

```bash
PYTHONPATH=src python scripts/reports/run_akzonobel_core_lines.py \
  --synthetic --output-dir /tmp/akzonobel_core_lines --run-date 2026-09-30

# or
depotru-akzonobel-core-lines --synthetic --output-dir /tmp/akzonobel_core_lines
```

Inspect `/tmp/akzonobel_core_lines/*.html` and `*.csv`. Expect names like
`Ana Demo` / `AKZO-DEMO-002` only. Period defaults to the last complete
calendar month (August 2026 when `--run-date 2026-09-30`).

```bash
PYTHONPATH=src python scripts/reports/run_akzonobel_core_lines.py \
  --synthetic --dimension ciudad --output-dir /tmp/akzonobel_core_lines
```

## Live run (read-only SQL)

Needs the usual DB Settings (`DB_HOST` / NCX, etc.) and a YAML with
`placeholder: false`. The query is SELECT-only and keeps:

`DocumentosCodigo NOT IN ('XY','AS','TS','YX','ISC')`.

It also requires `Cantidad > 0` and `TotalSinIva > 0`, and excludes
`EXCLUDED_PRODUCT_NAMES`.

```bash
PYTHONPATH=src python scripts/reports/run_akzonobel_core_lines.py \
  --output-dir ~/business_reports/akzonobel_core_lines \
  --config path/to/real_core_lines.yaml
```

Numbers go through `format_number` (Colombian `$1.234.567` / `45,6%`).
User-facing text is Spanish.

## Regenerating

Re-run the same command. Files are named
`akzonobel_core_lines_YYYY-MM-DD.html` / `.csv` using the period end date.

## Monday cash pack

Not hooked here. Combining this report into the Monday email is a later,
optional change if it stays a one-file attach.

## Out of scope

Nightly mart, branch dimension, Cloudflare tunnel, stale-data alerts.
Assistant guide mining: [chat-log-guides-mining.md](chat-log-guides-mining.md).
