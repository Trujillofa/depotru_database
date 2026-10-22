# Contract — `catalog.quote_for_customer`

> Current contract for the B2 slice "customer quote". Source of truth for the
> implementation (`src/business_analyzer/core/j3system_customer_quote.py`) and
> its tests (`tests/platform/test_catalog_quote_for_customer.py`).
>
> Status: updated for Decisión 2. B.ROT overlap and dispatch origin remain
> POR CONFIRMAR POR FREDY (§4.1). Next slice (`catalog.resolve_customer_phone`)
> is **out of scope** and only sets the server-side identity key used here.

## 1. Purpose and audience

A sales agent asks for the price of a few SKUs **for a customer that the
platform already verified**. The tool returns the customer's own net list
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
  and total must match the tool evidence and must pass the server-side message validator before it is sent.
- If the ERP read fails, the response carries **no price and no stock
  quantity at all** (see §5.1, `erp_unavailable`).

## 2. Closed model input schema

The model may supply **only** these two keys. Any other key (including
`terceros_id`, `customer_id`, `phone`, `telefono`, `tercero`) is rejected
before any ERP access.

| Key | Type | Bound | Notes |
|---|---|---|---|
| `site` | string | one of `neiva`, `florencia` | case-insensitive, trimmed |
| `skus` | string or list of strings | 1..20 raw items before deduplication, each 1..40 chars after trimming, chars `[A-Za-z0-9._-]` | exact `ArticulosCodigo`; duplicates collapse (case-insensitive) |

Server-side only (never a model parameter):

| Source | Key | Type |
|---|---|---|
| `ToolContext.extras` | `verified_customer_terceros_id` | positive SQL int (ASCII digit strings accepted, surrounding whitespace trimmed; maximum 2147483647; booleans and floats rejected) |

The identity is written by the server (the phone resolver of the next slice).
The model can neither pass nor override it. When the key is absent or
invalid, the tool **fails closed** — a direct API call with an empty context
returns `verified_customer_required` and never touches the ERP.

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

`B.ROT` (PRODUCTOS DE BAJA ROTACION) is **commercial** (confirmed by Fredy)
and is a **virtual warehouse**: it is composed of items that live in several
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

**Open points that this slice must not guess.** Fredy has **not** confirmed

1. whether `B.ROT` quantities may **overlap** the quantities of the physical
   warehouses, and
2. which physical warehouse fulfils a sale that can only be served from
   `B.ROT`.

Consequently the output warns that an overlap is possible. Because this request does
not include the requested sale quantity and the physical overlap/origin are
unresolved, `requires_physical_origin_confirmation` is conservatively `true`
whenever `baja_rotacion` is positive, even if physical site quantity is also
positive. Treat the flag as a required human check before a proposed sale uses
or relies on B.ROT. A physical-only sale may proceed only after the server
validates the requested quantity against the site's physical quantity. B.ROT
never establishes site availability and the tool never claims a physical origin
for its stock.

## 5. Closed output schema

```jsonc
{
  "status": "ok" | "partial" | "error",
  "reason": "<reason enum>",      // present only when status != "ok"
  "site": "neiva" | "florencia",  // present when the site is known
  "unit": "UND",                 // present for line-level quote results
  "price_includes_iva": false,
  "tariff": {"codigo": "...", "nombre": "..."},   // metadata after a unique customer lookup
  "stock_coverage": { ... },                       // only when the site is known
  "lines": [
    {
      "sku": "SYN-SKU-0001",
      "name": "PRODUCTO SINTETICO",
      "status": "ok" | "article_not_found" | "price_missing" | "price_ambiguous",
      "price": 12345.67,                          // net, before IVA; null when not quotable
      "qty": 12.0,                               // physical site stock; null when unknown
      "stock_status": "available" | "zero_in_mapped_warehouses" | "unknown",
      "baja_rotacion": 3.0,                      // exact B.ROT stock; null when unknown
      "baja_rotacion_status": "present" | "zero" | "unknown",
      "requires_physical_origin_confirmation": false
    }
  ]
}
```

`qty` is the stock of the article across the **physical mapped warehouses of
the site** only (see §4). It never includes `B.ROT`.

`baja_rotacion` is the exact stock of the article in the **virtual** `B.ROT`
warehouse. It is a separate figure: it is never added to `qty` and never
replaces it.

Missing stock rows, missing quantities, nonnumeric, nonfinite, boolean, or
negative quantities yield `qty: null` and `stock_status: unknown` for the
physical figure, and `baja_rotacion: null` and
`baja_rotacion_status: unknown` for the virtual figure; they never imply
zero stock. Invalid database casts may instead fail the whole read with
`erp_unavailable`. Explicit numeric zero means zero only in the warehouses it
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
  "note": "<short Spanish note: B.ROT es una bodega virtual sin sede; su stock se reporta aparte y nunca se suma al de la sede. Sus cantidades pueden solaparse con las físicas y una venta servida sólo desde B.ROT exige confirmar el origen físico con una persona>"
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
| Price source | `AdmPrecios.PreciosValor` for the customer's verified tariff (`AdmTerceros.TarifasID`), unit price rows only (`Cantidad = 0`) |
| IVA | Never computed here. `price_includes_iva` is always `false` |
| Increment / mostrador price | Never applied (`PreciosIncremento`, `ArticulosVenta` are not selected) |
| Cost / margin | Never selected (`ArticulosCosto`, `ArticulosUltmoCosto`, `ArticulosMargen`, `ValorCosto`, `CostoSinIva`, `CostoMasIva`, `UltimoCostoCompra`, `ListadoPreciosCosto`, …) |
| Magento | Not consulted; no Magento price may appear |
| Customer PII | `TercerosNombres`, `TercerosCelular`, `TercerosIdentificacion` are never selected |
| Tariff | Missing tariff → `tariff_missing`. Tariff `006` / id `6` / `AL COSTO` → `tariff_refused`. Both are decided **before** any item-price query |
| Site stock | `InvDetalleExistencias` × `InvExistencias` × `AdmAlmacen`, latest `Ano` within the requested articles and the site's physical warehouses; null/negative source quantities make that article's stock unknown rather than silently discarding them |
| `B.ROT` stock | Same three tables, filtered to `AlmacenCodigo = 'B.ROT'` only, aggregated **separately** with its **own** latest-`Ano` selection; never merged into the site's physical quantity. `CON` is never part of any warehouse set used by this tool |

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
  The target article CTE and final result use `TOP 21` as overflow guards.
  Price and stock aggregates filter to that target article set internally,
  before aggregation; even the latest-year aggregate reads only bounded
  stock rows for those articles and mapped warehouses.
- **Two independent stock aggregates.** `stock_rows` holds the site's
  physical warehouses only and `baja_rotacion_rows` holds `B.ROT` only. The
  site's quantity aggregates `FROM stock_rows` with
  `Ano = (SELECT MAX(Ano) FROM stock_rows)`; the `B.ROT` quantity aggregates
  `FROM baja_rotacion_rows` with
  `Ano = (SELECT MAX(Ano) FROM baja_rotacion_rows)`. Adding `B.ROT` therefore
  cannot change the site's physical quantity nor the year it selects.
- `B.ROT` appears in exactly one warehouse IN-list, the one of its own
  aggregate. `CON` appears in none.
- Duplicate article results, unexpected SKUs, result overflow, and malformed
  query result shapes fail closed with `erp_unavailable`. Conflicting prices
  for one article yield `price_ambiguous`; equal duplicate prices may quote.
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
| 6 | Tariff `006` → `tariff_refused`, no item-price query |
| 7 | Correct tariff price, no cost/margin/IVA in the payload |
| 8 | Site warehouses only; `B.ROT` and `CON` in no site list; coverage reported for the returned physical warehouses only |
| 9 | Unknown SKU → `article_not_found` |
| 10 | Missing price → `price_missing`; ambiguous price → `price_ambiguous` |
| 11 | ERP error → `erp_unavailable`, no exception text, no identity data, no price and no stock |
| 12 | The payload never contains the customer id or any identity field |
| 13 | Invalid or missing stock stays unknown, never coerced to zero |
| 14 | Bound server IDs, aggregate filters, row caps, and duplicate guards |
| 15 | Exact physical `qty` is unchanged and excludes `B.ROT` |
| 16 | Exact `baja_rotacion` quantity is surfaced separately with its own status |
| 17 | `B.ROT` may overlap and is never added to the physical total |
| 18 | Any positive `baja_rotacion` sets `requires_physical_origin_confirmation` conservatively (even when site stock is positive); only a sale using/relying on `B.ROT` needs the human origin check, and B.ROT never proves site availability |
| 19 | Missing/invalid `B.ROT` quantity stays unknown and raises no confirmation flag |
| 20 | The generated query puts `B.ROT` only in its own aggregate, excludes `CON`, and keeps the two year selections independent |
| 21 | No `unmapped_warehouse_stock` / always-partial coverage behaviour; the contract documents `B.ROT` as a virtual warehouse with no site |
