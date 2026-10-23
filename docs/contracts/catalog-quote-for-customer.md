# Contract — `catalog.quote_for_customer`

> Current contract for the B2 slice "customer quote". Source of truth for the
> implementation (`src/business_analyzer/core/j3system_customer_quote.py`) and
> its tests (`tests/platform/test_catalog_quote_for_customer.py`).
>
> Status: updated for Decisión 2. B.ROT overlap and dispatch origin remain
> POR CONFIRMAR (§4.1). Next slice (`catalog.resolve_customer_phone`)
> is **out of scope** and only sets the server-side identity key used here.

## 1. Purpose and audience

A sales agent asks for the price of a few SKUs **for a customer that the
platform already verified**. The tool returns the customer's own tariff list
price and the inventory available at the requested site's mapped warehouses.
Stock belongs to the inventory view, not to the customer.

`B.ROT` is a **virtual warehouse with no physical site** (§4.1). Its stock is
reported as a separate figure and never folded into a site's physical stock.

| Property | Value |
|---|---|
| Tool name | `catalog.quote_for_customer` |
| Registry scope | `ToolScope.SALES_PORTFOLIO` |
| Usable audiences | `SALES` (and `ADMIN`, per the kernel scope model) |
| Discoverable by `PUBLIC` / `CUSTOMER` / `WAREHOUSE` / `SERVICE` / `AGENT` | No |
| `public_safe` | `False` |
| Side effects | None. Read-only ERP SQL; no writes, Magento, HTTP, or other ERP actions |
| Module | `business_analyzer.core.j3system_customer_quote` |

The registry scope is the primary gate; the handler additionally refuses any
audience outside `{SALES, ADMIN}` so the rule stays closed even if the scope
map changes.

### 1.1 Exact figures are tool data, never model arithmetic

The price and the stock quantities returned by this tool are **exact figures
read from the ERP** and are allowed as current tool data. They are not
bucketed, rounded, or replaced by words such as `hay`, `pocas_unidades` or
`no_hay`.

- The model **must not calculate, derive, round, or remember** price or
  stock. Every customer-facing figure comes from a tool response.
- The tool returns factual tool data only. A successful tool response does
  not by itself prove that an arbitrary customer sentence has passed the
  downstream message validator; every customer-bound price, IVA, quantity
  and total must match the tool evidence and must pass the server-side message validator before it is sent. That validator lives in a separate slice and is **not** proven or exercised by this slice.
- If the ERP read fails, the response carries **no price and no stock
  quantity at all** (see §5.1, `erp_unavailable`).

### 1.2 Exact base-10 representation

Every price and quantity is carried as Python `Decimal` from the read to the
payload. No figure is ever converted to a binary `float`; a database value
that arrives as a `float` or `str` (including `nan`/`inf`) is rejected as
unknown, not trusted: a float cannot prove it did not already lose precision,
and a string cannot prove it preserved the source scale exactly. Only an
exact `Decimal` or a finite `int` is accepted by `_as_decimal`.

- The payload serialises each figure as a **JSON string**, not a JSON number.
- The string is the canonical fixed-point form `format(value, "f")` of the
  exact `Decimal`: no scientific/exponent notation, no trailing `.0` beyond
  the source scale, and fractional digits preserved exactly as the source
  `Decimal` carries them (e.g. `"12.50"`, `"0.0001"`, `"1000000000000000000"`).
- No SQL `CAST(... AS DECIMAL(p,s))` is applied: the source column's own
  scale is preserved, so no scale is imposed without schema evidence. The
  requirement that these columns arrive as `Decimal`/`int` (never `str`/
  `float`) is a **pending confirmation**: no repository schema evidence
  asserts the column types, so `_as_decimal` fails closed on any unexpected
  type rather than claiming compatibility with an unknown schema.
- Raw prices are compared as `Decimal` **before** any serialisation; two
  distinct values that a float would collapse to the same binary number
  therefore still produce `price_ambiguous`, never a false equal quote.

## 2. Closed model input schema

The model may supply **only** these two keys. Any other key (including
`terceros_id`, `customer_id`, `phone`, `telefono`, `tercero`) is rejected
before any ERP access.

| Key | Type | Bound | Notes |
|---|---|---|---|
| `site` | string | one of `neiva`, `florencia` | case-insensitive, trimmed |
| `skus` | string or list of strings | 1..20 raw items before deduplication, each 1..40 chars after trimming, chars `[A-Za-z0-9._-]` | exact `ArticulosCodigo`; duplicates collapse case-insensitively, keeping the first occurrence's spelling |

Server-side only (never a model parameter):

| Source | Key | Type |
|---|---|---|
| `ToolContext.extras` | `verified_customer_terceros_id` | positive SQL int (ASCII digit strings accepted, surrounding whitespace trimmed; maximum 2147483647; booleans and floats rejected) |

The identity is written by the server (the phone resolver of the next slice).
The model can neither pass nor override it. When the key is absent or
invalid, the tool **fails closed** — a direct API call with an empty context
returns `verified_customer_required` and never touches the ERP.

### 2.1 SKU casing

When duplicate SKUs differ only by case, the spelling of the **first**
occurrence is preserved in both the SQL request and the emitted line `sku`.
The tool never silently uppercases or lowercases a requested SKU. Each result
row is matched to its request SKU case-insensitively, and a returned
`ArticulosCodigo` that does not match (case-insensitively) a requested SKU —
or that repeats an already-seen SKU — fails closed with `erp_unavailable`.

## 3. Identity rules

1. The customer id comes only from `ToolContext.extras`.
2. The customer id is used **only** as a bound SQL parameter
   in the customer-tariff query (`WHERE t.TercerosID = %s`). It is never
   interpolated into SQL or passed to the quote-price query.
3. The customer id is **never returned** in the payload, and no customer name,
   phone, or identification is selected at all.
4. No parameter, alias, or fallback lets the model supply an id.

## 4. Site → warehouse mapping (grounded in repository code)

| Site | Warehouses | Grounding |
|---|---|---|
| `neiva` | `ALM`, `BD6`, `SUR`, `DIS`, `BOD` | `ALM`=001 main warehouse, `BD6`=Bodega 6, `SUR`=Bodega del Sur, `DIS`=Sede Distribuciones, `BOD`=Bodega Mangueras — all Neiva (`depotru_tools.builtins.BRANCHES`, `business_analyzer.core.j3system_sales_warehouse.WAREHOUSE_CODE_TO_NAME`) |
| `florencia` | `FLO` | `FLO` = ALMACEN FLORENCIA (Sika Center) (`j3system_sales_warehouse.WAREHOUSE_CODE_TO_NAME`) |

These lists are **physical** warehouses of the site. `CON` (CONTABILIDAD) is
excluded everywhere: it is neither a site warehouse nor a `B.ROT` source.

### 4.1 `B.ROT` — virtual warehouse without a site

`B.ROT` (PRODUCTOS DE BAJA ROTACION) is **commercial** (per operations) and
is a **virtual warehouse**: it is composed of items that live in several
physical warehouses. It has **no physical site** of its own and belongs to
neither Neiva nor Florencia.

Therefore:

- `B.ROT` is **not** assigned to `neiva` and **not** assigned to `florencia`.
- `B.ROT` never appears in a site warehouse IN-list.
- Its stock is reported in its own per-line field `baja_rotacion` (§5). It is
  **never summed** into the site's physical quantity and never changes the
  site's own quantity or its own latest-`Ano` selection (§7).
- `B.ROT` stock is **never** the only evidence for "sí hay en sede X". The
  line's `stock_status` describes the site's physical warehouses only.
- The physical-site quantity is reported only for the warehouses in
  `stock_coverage.mapped_warehouses`. `stock_coverage.status` is therefore
  `physical_warehouses_only`; it is not a claim that the site is completely
  covered by any wider evidence. The former "unmapped warehouse / partial
  coverage" semantics are gone

  (`stock_coverage.reason = "unmapped_warehouse_stock"` no longer exists).

**Open points that this slice must not guess.** Operations has **not** confirmed

1. whether `B.ROT` quantities may **overlap** the quantities of the physical
   warehouses, and
2. which physical warehouse fulfils a sale that depends on `B.ROT`.

Consequently the output warns that an overlap is possible and that the
physical origin is pending confirmation. Because this request does
not include the requested sale quantity and the physical overlap/origin are
unresolved, `requires_physical_origin_confirmation` is conservatively `true`
whenever `baja_rotacion` is positive, even if physical site quantity is also
positive.

`requires_physical_origin_confirmation` is a **tri-state** flag meaningful
**only together with `baja_rotacion_status`**:

| `baja_rotacion_status` | `requires_physical_origin_confirmation` | Meaning |
|---|---|---|
| `present` | `true` | human confirmation required before any sale that uses or depends on B.ROT |
| `zero` | `false` | no B.ROT stock, no confirmation needed |
| `unknown` | `null` | B.ROT status unknown; the flag is meaningless and a consumer must not read it as "no confirmation needed" |

A consumer must never interpret `requires_physical_origin_confirmation` in
isolation from `baja_rotacion_status`. A physical-only sale may proceed only
after the server validates the requested quantity against the site's physical
quantity. B.ROT never establishes site availability and the tool never claims
a physical origin for its stock.

## 5. Closed output schema

```jsonc
{
  "status": "ok" | "partial" | "error",
  "reason": "<reason enum>",      // present only when status != "ok"
  "site": "neiva" | "florencia",  // present when the site is known
  "iva_status": "unknown",       // IVA is never derived here; see §6
  "tariff": {"codigo": "...", "nombre": "..."},   // only on a successful unique lookup; never echoed on refusal/missing
  "stock_coverage": { ... },                       // only when the site is known
  "lines": [
    {
      "sku": "SYN-SKU-0001",      // first-occurrence spelling (§2.1)
      "name": "PRODUCTO SINTETICO",
      "status": "ok" | "article_not_found" | "price_missing" | "price_ambiguous",
      "price": "12345.67",        // exact fixed-point decimal string; null when not quotable
      "qty": "12.00",             // physical site stock; null when unknown
      "stock_status": "available" | "zero_in_mapped_warehouses" | "unknown",
      "baja_rotacion": "3.00",    // exact B.ROT stock; null when unknown
      "baja_rotacion_status": "present" | "zero" | "unknown",
      "requires_physical_origin_confirmation": true | false | null
    }
  ]
}
```

- `price`, `qty` and `baja_rotacion` are **strings** in the exact fixed-point
  representation of §1.2. They are never JSON numbers and never floats.
- There is **no `unit` field**: the read does not select a unit column, and no
  `UND` (or any other unit) is asserted anywhere.
- There is **no `price_includes_iva` field**. IVA status is reported once as
  `iva_status: "unknown"` (§6); this slice neither asserts net nor gross nor
  derives a `price_with_iva` or a `1.19` factor.

`qty` is the stock of the article across the **physical mapped warehouses of
the site** only (see §4). It never includes `B.ROT`.

`baja_rotacion` is the exact stock of the article in the **virtual** `B.ROT`
warehouse. It is a separate figure: it is never added to `qty` and never
replaces it.

Missing stock rows, missing quantities, nonnumeric, nonfinite, boolean, float,
string, or negative quantities yield `qty: null` and `stock_status: unknown` for the
physical figure, and `baja_rotacion: null` and
`baja_rotacion_status: unknown` for the virtual figure; they never imply
zero stock. Unexpected source types fail closed per figure, never as a
whole-read cast failure: `_as_decimal` accepts only an exact `Decimal` or a
finite `int` (strings and floats are rejected). Explicit numeric zero means
zero only in the warehouses it
was measured in (`zero_in_mapped_warehouses` for the site,
`baja_rotacion_status: zero` for `B.ROT`). The warehouse breakdown is not
returned; the site's physical codes are listed in
`stock_coverage.mapped_warehouses` and the virtual warehouse in
`stock_coverage.virtual_warehouses`.

### 5.1 Status enum

| Value | Meaning |
|---|---|
| `ok` | every requested line is quoted |
| `partial` | at least one line quoted and at least one line failed |
| `error` | nothing could be quoted (fatal reason) |

A fatal error carries `lines: []`: there is **no price and no stock** in the
payload, for either the site or `B.ROT`.

### 5.2 Reason enum (closed)

`audience_not_allowed`, `unexpected_parameters`, `verified_customer_required`,
`site_invalid`, `skus_required`, `too_many_skus`, `invalid_sku`,
`customer_not_found`, `customer_ambiguous`, `tariff_missing`,
`tariff_refused`, `erp_unavailable`, `article_not_found`, `price_missing`,
`price_ambiguous`.

For `partial` / line-level `error` the reason is the first failing line
reason; for a fatal error it is the fatal reason.

### 5.3 Stock coverage block

```jsonc
"stock_coverage": {
  "status": "physical_warehouses_only",
  "mapped_warehouses": ["ALM", "BD6", "SUR", "DIS", "BOD"],
  "virtual_warehouses": [
    {"code": "B.ROT", "name": "PRODUCTOS DE BAJA ROTACION", "kind": "virtual", "site": null}
  ],
  "virtual_warehouses_reported_separately": true,
  "overlap_possible": true,
  "note": "<short Spanish note: B.ROT es una bodega virtual sin sede; su stock se reporta aparte y nunca se suma al de la sede. El posible solapamiento con las bodegas físicas y el origen físico de cualquier venta que use o dependa de B.ROT están pendientes de confirmación>"
}
```

`stock_coverage.status` is `physical_warehouses_only`: the site's physical
warehouses are reported for the mapped set only, and `B.ROT` is reported
separately as a virtual warehouse with `site: null`. There is no `unmapped_warehouses` list
and no `unmapped_warehouse_stock` reason any more. Quote status (§5.1)
describes price availability independently.

## 6. Data rules (ERP read)

| Rule | Detail |
|---|---|
| Price source | `AdmPrecios.PreciosValor` for the customer's verified tariff (`AdmTerceros.TarifasID`), unit price rows only (`Cantidad = 0`). The ambiguity count (`price_rows`) and the `MIN`/`MAX` all operate on the **same** set of strictly-positive rows (`PreciosValor > 0`): a zero, negative, or `NULL` price is an **absent** price, not a valid price row, and never inflates the count nor erases a valid positive price. No valid positive row → `price_missing`; one valid positive row plus any absent rows → quote that price; multiple distinct positive rows → `price_ambiguous`; equal duplicate positive rows may quote |
| IVA | **Never computed, never asserted.** Whether `PreciosValor` includes IVA is **unknown** until the B0 branch is evidenced; `iva_status` is `unknown` and no `price_includes_iva`, net/gross wording, or `1.19` factor is emitted |
| Increment / mostrador price | Never applied (`PreciosIncremento`, `ArticulosVenta` are not selected) |
| Cost / margin | Never selected (`ArticulosCosto`, `ArticulosUltmoCosto`, `ArticulosMargen`, `ValorCosto`, `CostoSinIva`, `CostoMasIva`, `UltimoCostoCompra`, `ListadoPreciosCosto`, …) |
| Magento | Not consulted; no Magento price may appear |
| Customer PII | `TercerosNombres`, `TercerosCelular`, `TercerosIdentificacion` are never selected |
| Tariff | Missing tariff → `tariff_missing`. Tariff id `6` / code `006` / name `AL COSTO` → `tariff_refused`. Both are decided **before** any item-price query, and the refusal payload does **not** echo tariff metadata |
| Site stock | `InvDetalleExistencias` × `InvExistencias` × `AdmAlmacen`, latest `Ano` **per (ArticulosID, AlmacenID)**; null/negative source quantities make that article's stock unknown rather than silently discarding them |
| `B.ROT` stock | Same three tables, filtered to `AlmacenCodigo = 'B.ROT'` only, aggregated **separately** with its **own** latest-`Ano` selection; never merged into the site's physical quantity. `CON` is never part of any warehouse set used by this tool |

**Limits not proven by this slice.** No vigency / status column is read or
filtered on `AdmPrecios` or the inventory tables: no such column is evidenced
in the repository, and assuming one would be inventing schema. The price read
is `Cantidad = 0` plus the verified tariff only. The downstream outbound
message validator (§1.1) lives in a separate slice and is **not** exercised
here.

## 7. SQL and safety rules

- Read-only `SELECT` only. No DDL, no DML, no stored procedure.
- Tables qualified with `qualified_j3_table()` (`J3System.dbo.<table>`).
- Bounded literal sets built with `sql_in_list()` (site warehouses, SKUs).
- The server-controlled customer ID is the sole bound parameter (`%s`) in the
  customer-tariff lookup. The verified tariff ID is the sole bound parameter
  (`%s`) in the separate quote-price query. Neither is model supplied.
- SKU and warehouse sets are safely rendered with repository `sql_in_list()`,
  limited to 20 requested SKUs and at most 5 mapped warehouses.
- The customer lookup uses `TOP 2` to detect duplicate customer/tariff joins.
  The target article CTE and final result use `TOP 21` as overflow guards,
  ordered by `ArticulosCodigo, ArticulosID` for deterministic tie-breaking.
  Price and stock aggregates
  filter to that target article set internally, before aggregation.
- **Per-pair latest-year selection.** Both `stock_rows` and
  `baja_rotacion_rows` are wrapped in a ranking CTE that keeps the latest row
  of each `(ArticulosID, AlmacenID)` pair with
  `ROW_NUMBER() OVER (PARTITION BY ArticulosID, AlmacenID ORDER BY Ano DESC) = 1`.
  There is **no** global `MAX(Ano)` filter: each pair selects its own latest
  year independently, and adding another SKU or `B.ROT` cannot change the year
  another pair selects.
- **Same-year duplicate guard.** A `COUNT(*) OVER (PARTITION BY ArticulosID,
  AlmacenID, Ano)` tie counter is carried through the ranking; the aggregate
  requires `MAX(ties) = 1`. If a pair has more than one row in its latest
  year, the quantity becomes unknown (`NULL`) instead of being double-counted.
- **Latest year is a local-read assumption.** "Latest `Ano`" means the maximum
  `Ano` present in the read for that pair; it is **not** a verified carry-over
  semantics between exercises. The read neither joins nor verifies how one
  exercise's closing stock becomes the next exercise's opening stock.
- **Two independent stock aggregates.** `stock_rows` holds the site's
  physical warehouses only and `baja_rotacion_rows` holds `B.ROT` only. The
  site's quantity aggregates `FROM stock_latest`; the `B.ROT` quantity
  aggregates `FROM baja_rotacion_latest`. Adding `B.ROT` cannot change the
  site's physical quantity nor the year it selects.
- `B.ROT` appears in exactly one warehouse IN-list, the one of its own
  aggregate. `CON` appears in none.
- Duplicate article results, unexpected SKUs, result overflow, and malformed
  query result shapes fail closed with `erp_unavailable`. Conflicting prices
  for one article yield `price_ambiguous`; equal duplicate prices may quote.
  The price ambiguity count (`price_rows`) and the `MIN`/`MAX` fold over the
  same strictly-positive unit-price rows, so a zero, negative, or `NULL`
  price is absent and never inflates the count or erases a valid positive
  price.
- Failures never surface the driver message: the payload carries
  `erp_unavailable` and nothing else.
- No logging of inputs, SQL parameters, query rows, or customer data.

## 8. Test matrix (fake DB only)

| # | Case |
|---|---|
| 1 | Sales-only registration; `PUBLIC` cannot discover or invoke |
| 2 | Missing server-verified identity → fail closed, no ERP access |
| 3 | `terceros_id` / unknown key → rejected before ERP access |
| 4 | Invalid site, empty SKUs, > 20 SKUs, invalid SKU chars → rejected before ERP access |
| 5 | Missing tariff → `tariff_missing`, no item-price query |
| 6 | Tariff `006` → `tariff_refused`, no item-price query, no tariff metadata echoed |
| 7 | Correct tariff price, no cost/margin in the payload; `iva_status: unknown`, no `price_includes_iva`, no `unit` |
| 8 | Site warehouses only; `B.ROT` and `CON` in no site list; coverage reported for the returned physical warehouses only |
| 9 | Unknown SKU → `article_not_found` |
| 10 | Missing price → `price_missing`; ambiguous price → `price_ambiguous`; zero/nonpositive price → `price_missing` |
| 11 | ERP error → `erp_unavailable`, no exception text, no identity data, no price and no stock |
| 12 | The payload never contains the customer id or any identity field (structural, not substring) |
| 13 | Invalid or missing stock stays unknown, never coerced to zero |
| 14 | Bound server IDs, aggregate filters, row caps, and duplicate guards |
| 15 | Exact physical `qty` is unchanged and excludes `B.ROT` |
| 16 | Exact `baja_rotacion` quantity is surfaced separately with its own status |
| 17 | `B.ROT` may overlap and is never added to the physical total (structural, not arithmetic tautology) |
| 18 | Tri-state `requires_physical_origin_confirmation` for `present`/`zero`/`unknown`, never read without `baja_rotacion_status` |
| 19 | Missing/invalid `B.ROT` quantity stays unknown and the flag is `null` |
| 20 | Generated SQL selects the latest year per `(ArticulosID, AlmacenID)` via `ROW_NUMBER`, carries the same-year duplicate guard, and keeps the two year selections independent; no global `MAX(Ano)` |
| 21 | No `unmapped_warehouse_stock` / always-partial coverage behaviour; the contract documents `B.ROT` as a virtual warehouse with no site |
| 22 | Exact decimal representation: large values, adjacent distinct prices, and fractional-scale stock are preserved as fixed-point strings and never collapse through float |
| 23 | First-occurrence SKU casing is preserved on case-insensitive deduplication |

## 9. Module size exception (one-time, B2 only)

The implementation module
`src/business_analyzer/core/j3system_customer_quote.py` is **exactly 486
physical lines** (`wc -l`) and **376 code lines** (nonblank physical lines
excluding comments/docstrings, including the embedded SQL templates).

This one-time exception was explicitly authorized by **Fredy on
2026-10-22**. The reason: this single tool combines server-verified identity
and tariff checks, bounded parameterized J3 reads, exact `Decimal`-only
price/stock handling, per-pair latest-year and tie guards, physical-vs-virtual
`B.ROT` separation, fail-closed response validation, and sanitized errors.

This exception applies **only to B2** and is **not precedent** for B0/B1/B3.
The B2 module hard ceiling is **486 physical lines**. Any future code
correction must be extracted to an auxiliary module and must not increase the
B2 module past 486 physical lines.
