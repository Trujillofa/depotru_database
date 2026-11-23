# J3 exact-SKU quote lookup: EXPLAIN diagnosis and the `catalog.quote_skus` fix

Task BFF-PRECIO-SKU (p8). Read-only diagnosis against the live J3/SmartBusiness
server (SELECTs + `SET SHOWPLAN_ALL ON`, which compiles a plan without executing).
No ERP indexes were created or changed.

## Symptom (measured by the owner, post #121)

`catalog.quote_search` by SKU against J3System:

| Profile                        | Time       |
| ------------------------------ | ---------- |
| 1 SKU lookup                   | ~3.0 s     |
| 6 parallel lookups             | 6.8–14 s   |
| 12 parallel lookups            | all > 20 s |

## Where the time goes (this diagnosis, 2026-11-21)

| Step                                                | Time      |
| --------------------------------------------------- | --------- |
| Cold `Database()` connect + `SELECT 1`              | 0.32 s    |
| `quote_search` SKU query, **warm connection**       | 2.4 s avg |
| Same query, fresh `Database()` per call (today)     | 2.6–2.9 s |
| 6 parallel (fresh `Database` each)                  | 12.0 s    |
| 12 parallel (fresh `Database` each)                 | 21.2 s    |
| 6/12 parallel on per-thread reused `db_factory` conns | 11.5 / 21.2 s |

The connection is **not** the bottleneck (0.32 s; pooling changes nothing —
see the `db_factory` rows). The query itself costs ~2.4 s of SQL Server time
per call.

## Plan: why one SKU costs 2.4 s

`SHOWPLAN_ALL` for the current statement (name/SKU LIKE predicate over
`build_quote_search_sql`):

```
SELECT TOP 6 ... FROM J3System.dbo.AdmArticulos a
LEFT JOIN J3System.dbo.AdmLineas l ...
LEFT JOIN ( SELECT e.ArticulosID, SUM(CASE WHEN al.AlmacenCodigo IN (allowlist) ...)
            FROM InvDetalleExistencias d ... GROUP BY e.ArticulosID ) s ...
WHERE <REPLACE-chain over ArticulosNombre> LIKE '%sku%' ...
```

- Total subtree cost **16.55**; the stock-aggregate branch alone costs
  **15.87**, dominated by a **Clustered Index Scan of
  `InvDetalleExistencias` with est. 320,760 rows** (cost 14.20) feeding a
  parallel hash aggregate over the whole inventory.
- The name predicate (`LOWER(REPLACE(...)) LIKE`) is non-sargable, so SQL
  Server cannot push the SKU filter into the derived table: it aggregates
  **all** inventory for every call, hash-joins it against all ~10k
  articles, and only then filters to ≤ 6 rows.
- 12 parallel calls run 12 concurrent full-inventory aggregates on the ERP;
  that is the 20 s+ degradation.

## Plan: why the exact-code `IN (...)` predicate is cheap

Replacing the predicate with `LOWER(a.ArticulosCodigo) IN (%s, ...)` (same
projection) changes the plan to Nested Loops with `OUTER REFERENCES:
a.ArticulosID` — **predicate pushdown**: per-SKU Index Seeks into
`InvDetalleExistencias`/`InvExistencias` instead of the full scan.

- Subtree cost **0.50** vs 16.55 (**~33× cheaper**).
- Measured: 6 / 12 / 20 SKUs in ONE query = **0.73–1.26 s total**
  (vs 2.4 s × N).

## Fix shipped

1. **`catalog.quote_skus`** (public catalog tool): resolves 1–20 exact
   `ArticulosCodigo` in ONE query via `quote_skus_statement`
   (`depotru_tools/catalog_query.py`), reusing the unchanged
   `build_quote_search_sql` projection (J3 `ArticulosVenta` before IVA,
   `AdmLineas.LineasPorcentaje`, website-allowlist stock; no cost columns,
   no `ArticulosEstado` filter, no writes). Same exact-code matching
   semantics as quote_search's SKU branch (`LOWER(col) = code`:
   case-insensitive, no trimming). Reports `found`/`missing` per code and
   fails closed with the fixed `catalog_unavailable` reason.
2. **Short TTL cache** (`depotru_tools/quote_cache.py`): per-SKU row cache,
   TTL `QUOTE_SKU_CACHE_TTL_SECONDS` (default **120 s**, `0` disables),
   bounded by `QUOTE_SKU_CACHE_MAX_ENTRIES` (default 1024). Single-flight
   per key: N concurrent misses for the same SKU collapse into one query;
   the batch fetch fills sibling entries (and caches empty answers for
   missing codes). Failures are never cached. The TTL is a latency guard,
   not a price cache of record — a price change in J3 is visible within the
   window.

## Measured RED → GREEN (live, read-only)

| Profile                             | Before (per-SKU quote_search) | After (`catalog.quote_skus`) |
| ----------------------------------- | ----------------------------- | ---------------------------- |
| 1 SKU                               | 2.6–2.9 s                     | **0.73 s**                   |
| 6 SKUs                              | 12.0 s (parallel)             | **0.73 s** (one call)        |
| 12 parallel identical lookups       | 21.2 s                        | **0.73 s** (1 query)         |
| 12 parallel distinct lookups        | 21.2 s                        | **1.07 s**                   |
| 20 SKUs, one call                   | ~48 s at 2.4 s each           | **1.26 s**                   |
| Same 20 SKUs again (TTL window)     | ~48 s                         | **0.000 s**                  |

## What is intentionally NOT changed

- `catalog.quote_search` semantics and SQL are untouched (name search still
  needs the LIKE predicate; it keeps its ranking and Magento merge).
- No ERP-side index was created (out of scope without owner authorization);
  the `InvDetalleExistencias` scan for name searches remains as-is.
- The BFF deployment/restart is the owner's; this ships as a PR only.
