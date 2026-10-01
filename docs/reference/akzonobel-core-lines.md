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

AkzoNobel commercial coverage for this house is **regional** (Huila / Caquetá).
The report does **not** use that regional grain. It uses the salesperson who
owns the invoice — the only sales-territory grain existing SmartBusiness
reports treat as “who owns the sale.”

**Default: `vendedor_codigo` (key) + `VendedorFactura` (label).**

That is the commercial owner already used by `manager_report` budget-vs-actual
(`presupuesto_vendedores`) and the KPI board.

Documented alternatives on `banco_datos` (set in the YAML or `--dimension`)
if you need geography instead of salesperson:

| Value | Fields | When to use |
|-------|--------|-------------|
| `vendedor` (default) | `vendedor_codigo` / `VendedorFactura` | Salesperson / commercial route |
| `ciudad` | `ciudad` / `ciudad` | Customer city on the sales fact |
| `departamento` | `departamento` / `departamento` | Customer department |

`zona_unica` / `regional` exist on J3/cartera master data, not on `banco_datos`
sales facts. Branch / sede (`DocumentosCodigo` FED/FEF/FET, Neiva vs Florencia)
is Phase 4+ and is out of scope here.

## Core Lines SKU list (ERP catalog)

`src/business_analyzer/jobs/data/akzonobel_core_lines.yaml`

**Core Lines = every reference of these six brands** in the SmartBusiness ERP
catalog (extracted 2026-10-01, read-only `SELECT` on `banco_datos`, excluding
`XY` / `AS` / `TS` / `YX` / `ISC`):

`marca` values match the ERP / packaged YAML tokens (no accent):

- Vinilico (comercialmente Vinílico; ERP `VINILICO`)
- Viniltex
- Koraza
- Pintulux (comercialmente Pintulux 3en1)
- Estucomastic
- Experto Pro (ERP names `VINILO EXPERTO PRO …`)

The list includes bases, special-price, promotion, and S/I versions. Matching
is by `ArticulosCodigo` only. The live query reads `banco_datos` only; it does
not join `productos_adicional` or select `proveedor` / `marca`.
`ArticulosCodigo` is text (`nvarchar(20)`). SKUs must be quoted 10-digit
ASCII strings (`[0-9]{10}` via `re.fullmatch`); the loader rejects ints,
bools, floats, Unicode digits, mixed letters/hyphens, shorter codes, and
trailing newlines, and it does not pad zeros. The only non-numeric exception
is the synthetic fixture `AKZO-DEMO-N`. Duplicate SKUs fail the load. Each
row may carry an optional `marca` field (ignored by JSON/CSV files that omit
it).

Matching is in Python after the read-only `SELECT` (there is no SQL `IN`
list). An ERP `ArticulosCodigo` that is not exactly 10 ASCII digits simply
does not match the Core Lines list.

Akzo line names that do not appear verbatim in the ERP were covered by **brand
family**, not by inventing codes:

- “Viniltex Advanced” → all Viniltex references
- “Koraza Acrílico Mate” → all Koraza references
- “Experto Pro” → the `VINILO EXPERTO PRO` SKUs

**Intentionally omitted** mixed-brand kits (they mix families and are not a
single Core Line): `0030070245`, `0030070414`, `0090060157`, `0090060205`,
`0090060211`, `0090060212`.

The shipped file is labelled `placeholder: false` (249 unique SKUs). Live mode
will query the database. `--synthetic` and most unit tests use built-in
`AKZO-DEMO-*` fixtures and **do not** read this YAML. One catalog test
(`test_shipped_yaml_is_real_erp_core_lines_catalog`) reads the packaged YAML
to lock those 249 unique 10-digit SKUs.

These are our own product codes, **not** customer data. Do not add customer
names, NIT, or vendor workbook dumps to git.

Override path via `--config` or Settings `AKZONOBEL_CORE_LINES_CONFIG`
(pydantic-settings). JSON and a `sku,name` CSV are also accepted (CSV still
loads as placeholder; an optional `marca` column is tolerated).

## How to run locally (synthetic, no DB)

`--synthetic` uses fictional sales and the three `AKZO-DEMO-*` SKUs. It does
not open the packaged catalog and does not touch the database.

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

To dry-run the packaged 249-SKU list without a database, pass it explicitly:

```bash
PYTHONPATH=src python scripts/reports/run_akzonobel_core_lines.py \
  --synthetic \
  --config src/business_analyzer/jobs/data/akzonobel_core_lines.yaml \
  --output-dir /tmp/akzonobel_core_lines
```

## Live run (read-only SQL)

Needs the usual DB Settings (`DB_HOST` / NCX, etc.). The packaged YAML is
already `placeholder: false`, so a run **without** `--synthetic` issues a
**SELECT-only** query. It never writes. It keeps:

`DocumentosCodigo NOT IN ('XY','AS','TS','YX','ISC')`.

It also requires `Cantidad > 0` and `TotalSinIva > 0`, and excludes
`EXCLUDED_PRODUCT_NAMES`.

```bash
PYTHONPATH=src python scripts/reports/run_akzonobel_core_lines.py \
  --output-dir ~/business_reports/akzonobel_core_lines
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
