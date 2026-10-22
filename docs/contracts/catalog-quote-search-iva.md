# Contract — `catalog.quote_search` price & IVA disambiguation (B0)

> **Status:** Contract only (B0). This document is the closed contract and is
> the only change of this pass — no code, test, `builtins.py`, or SQL change
> was made here. A later local implementation phase is authorized by Fredy's
> current order and MUST comply with this contract exactly.
>
> **Branch:** `feat/bff-b0-iva` · **Base:** `9698f4193b96b71dae500100a69a9882f726991f`
>
> **IVA source confirmed by Fredy (22 oct 2026):** the product IVA rate is
> `AdmLineas.LineasPorcentaje`, reached via `AdmArticulos.LineasID =
> AdmLineas.LineasID`. It is stored as a **percentage** (`19.000`, `5.000`,
> `0.000`), NOT a fraction. `AdmGrupos.Porcentaje` is NULL across the 89 rows
> and is **not** used. `AdmPrecios.PreciosValor` and `AdmArticulos.ArticulosVenta`
> are J3 prices **before IVA**. Both prices are `money`; `LineasPorcentaje` is
> `decimal`. All price/IVA handling is `Decimal`, never `float`.

---

## 1. Purpose

Today `catalog.quote_search` returns a single `price` field whose meaning is
ambiguous: for a J3-only result it is the J3 list price **without** IVA, while
for a J3+Magento or Magento-only result the existing merge code substitutes the
Magento price (which is **with** IVA). Consumers cannot tell which is which.

This contract corrects that ambiguity with explicit, closed fields and fixes
the authoritative price source and the IVA calculation rules.

**Canonical price/IVA source is J3, never Magento.** The canonical price is the
J3 price **before IVA** (`AdmArticulos.ArticulosVenta`). Magento contributes
only product `name`, `product_url`, and — only as a clearly separated display
value — `magento_price`; it is **never** a basis for price, IVA, or
`price_with_iva`.

---

## 2. Input contract (closed)

Tool name: `catalog.quote_search` (unchanged).

| Param  | Type   | Required | Constraint                                            |
|--------|--------|----------|-------------------------------------------------------|
| `query`| string | yes      | non-empty after trim; length ≥ 2, else `query_required` |
| `limit`| int    | no       | default `6`; clamped to `[1, 10]`                     |

No other input parameters are accepted. Extra keys MUST be ignored, not
surfaced, and MUST NOT change behavior.

---

## 3. Output contract (closed)

Top-level object (keys MUST be exactly these; no new top-level keys):

| Key          | Type                     | Notes                                    |
|--------------|--------------------------|------------------------------------------|
| `query`      | string                   | echoed input (trimmed)                   |
| `products`   | array\<product\>         | see §3.1                                 |
| `count`      | int                      | `len(products)`                          |
| `source`     | string                   | `"j3"` \| `"magento"` \| `"none"`        |
| `search_url` | string                   | storefront catalog search URL (unchanged)|
| `status`     | string                   | `"ok"` \| `"empty"` \| `"error"`         |
| `reason`     | string                   | present **only** when `status == "error"`; see §7.1 |

### 3.1 Product object (closed)

| Key                  | Type                             | Semantics                                                                 |
|----------------------|----------------------------------|---------------------------------------------------------------------------|
| `sku`                | string                           | SKU (unchanged)                                                           |
| `name`               | string                           | Magento name when present, else J3 name (unchanged)                       |
| `price`              | string \| null                   | **canonical** J3 price before IVA; equals `j3_price`; canonical base-10 decimal string (§6) |
| `price_basis`        | `"J3"` \| `"none"`               | source of `price`; always `"J3"` when a J3 row exists                     |
| `price_includes_iva` | bool \| null                     | `false` when `price_basis == "J3"`; `null` when `"none"`                  |
| `j3_price`           | string \| null                   | J3 `ArticulosVenta` (money, before IVA) as a canonical base-10 decimal string (§6) |
| `iva_rate`           | string \| null                   | percentage from `AdmLineas.LineasPorcentaje` (e.g. `"19.000"`) as a canonical base-10 decimal string (§5, §6) |
| `price_with_iva`     | int \| null                      | server-calculated COP integer (see §6)                                   |
| `price_with_iva_reason` | string \| null               | typed reason when `price_with_iva` is null (see §7)                       |
| `magento_price`      | string \| null                  | display-only Magento price; never a basis; canonical base-10 decimal string (§6) |
| `website_qty`        | string \| null                  | website-allowlist aggregate stock (fractional `Decimal`, e.g. `SaldoActual`); canonical base-10 decimal string preserving the exact fractional digits of the `Decimal` aggregate, never rounded or truncated (§6) |
| `in_stock`           | bool \| null                    | `website_qty > 0` (unchanged)                                           |
| `product_url`        | string                           | Magento PDP URL or `""` (unchanged)                                      |
| `source`             | string                           | `"j3"` \| `"j3+magento"` \| `"magento"` (unchanged, row provenance only)  |

No other product keys are permitted. New fields are **additive**; no existing
field is removed. The legacy numeric fields `price`, `magento_price`, and
`website_qty` are **re-typed** from JSON `number` to canonical base-10 decimal
**string** (§6) as an exactness requirement — never JSON float/number.

---

## 4. Canonical `price`, `price_basis`, `price_includes_iva`

The canonical price is the J3 price **before IVA**, taken from
`AdmArticulos.ArticulosVenta` — the column the existing
`build_quote_search_sql` already selects. A Magento match MUST NOT change
`price`, `price_basis`, or `price_includes_iva`, and MUST NOT be a basis for
IVA.

`AdmPrecios.PreciosValor` is also confirmed to be a J3 price **before IVA**
(`money`), but this tool's existing flow selects `AdmArticulos.ArticulosVenta`
and does **not** read `AdmPrecios`. This contract therefore does **not** assert a
precedence between the two: the value documented in `j3_price` (and `price`) is
`AdmArticulos.ArticulosVenta`, matching the current selection. No rule is added
to switch to or prefer `AdmPrecios.PreciosValor`.

| Condition              | `price_basis` | `price_includes_iva` | `price` source                     |
|------------------------|---------------|----------------------|------------------------------------|
| J3 row present         | `"J3"`        | `false`              | J3 `ArticulosVenta` (before IVA)   |
| No J3 row (Magento-only or no data) | `"none"` | `null`        | `null`                             |

`price_basis` is **always** `"J3"` whenever a J3 row exists; it never takes the
value `"magento"`. `price_includes_iva` is `false` for every J3-backed price,
because the J3 price is before IVA. There is no condition under which a Magento
price sets `price_basis` or `price_includes_iva`.

`price` and `j3_price` carry the **same** J3 value (`ArticulosVenta`) whenever a
J3 row exists. `price` is retained as the legacy display field; `j3_price` is
the explicit `Decimal` base used by the IVA calculation. `j3_price` MUST be
preserved as a full `Decimal` and MUST NOT be truncated to an integer before
any calculation. Both `price` and `j3_price` serialize as a canonical base-10
**string** (§6) carrying the exact `Decimal` value; `j3_price` is the
exact-decimal authority for the IVA calculation, and both carry the same numeric
value whenever a J3 row exists. Neither field may serialize as a JSON number or
pass through `float`.

**Magento contribution is display-only.** Magento may contribute `name`,
`product_url`, and `magento_price`. `magento_price` is a raw, display-only value
whose IVA semantics this contract does **not** assert and does **not** rely on.
It never feeds `price`, `price_basis`, `price_includes_iva`, `j3_price`,
`iva_rate`, or `price_with_iva`.

Consumers that require an IVA-inclusive price MUST use `price_with_iva`; they
MUST NOT infer IVA from `magento_price` or `source`.

---

## 5. Product IVA rate — `iva_rate`

The product's own IVA rate is `AdmLineas.LineasPorcentaje`, reached by the
LEFT JOIN `AdmArticulos.LineasID = AdmLineas.LineasID`. The value is encoded
as a **percentage** number (`19.000`, `5.000`, `0.000`), NOT a fraction.

- `iva_rate` serializes as a **JSON string** carrying the exact base-10 decimal
  value in canonical fixed-point notation — e.g. `"19.000"` (19 %), `"5.000"`
  (5 %), `"0.000"` (0 %). It is parsed to `Decimal` at the wire boundary,
  never `float`, and is emitted straight from the `Decimal` (§6 serialization).
- The §6 formula **divides `iva_rate` by 100**; this division is an explicit,
  documented conversion, never an implicit assumption.
- The rate MUST come **only** from `AdmLineas.LineasPorcentaje` for the article's
  own `LineasID`. The implementation MUST NOT use `AdmGrupos.Porcentaje`,
  `AdmLineas.LineasIndicadorIva`, `Incbp`, `Ipoconsumo`, `VrIBUA`, `VrICUI`, or
  any other indicator to decide or change the rate.
- There is no universal rate and no hardcoded fallback multiplier.

When `iva_rate` is `null` (no line association, line not found, or
`LineasPorcentaje IS NULL`), `price_with_iva` is `null` and a typed reason is
set (§7). The SKU may still appear with its J3 `price`/`j3_price`.

---

## 6. `price_with_iva` calculation

`price_with_iva` MUST be computed **server-side**, and **only** from:

1. the J3 price before IVA (`j3_price` = `AdmArticulos.ArticulosVenta`), and
2. the product's own IVA percentage (`iva_rate` = `AdmLineas.LineasPorcentaje`).

Exact formula (exact `Decimal` arithmetic throughout; no binary float):

```
price_with_iva = ROUND_HALF_UP(
    Decimal(j3_price) * (Decimal(1) + Decimal(iva_rate) / Decimal(100))
)
```

- `iva_rate` is the **percentage** value (e.g. `19.0`); it is divided by `100`
  inside the formula. `Decimal(1)` and `Decimal(100)` are exact.
- `j3_price` is used at its **full decimal value** (SQL Server `money`, 4-decimal
  scale); it is NOT truncated to an integer or to 2 decimals before the
  multiplication. The multiplication and addition use exact `Decimal`
  arithmetic; only the final result is rounded.
- Rounding mode: `HALF_UP`; the result is an **integer** COP.
- At `iva_rate == 0` (0 %) **no IVA is added**: the multiplier is exactly
  `Decimal(1)`, so `price_with_iva == ROUND_HALF_UP(Decimal(j3_price))` — the
  integer-COP rounding of the exact pre-IVA decimal, with no rate added.
- No hardcoded `1.19`, `5 %`, or any other rate/tariff code. The rate MUST come
  from the product's own `LineasPorcentaje`.
- If `j3_price` is `null` → `price_with_iva` is `null` (reason
  `j3_price_missing`).
- If `iva_rate` is `null` (no line / line not found / `LineasPorcentaje IS
  NULL`) → `price_with_iva` is `null` (reason `line_not_found` or
  `iva_rate_null`, §7). Never a default rate.

Serialization: every decimal figure — `price`, `j3_price`, `iva_rate`, and
`magento_price` — serializes as a **JSON string** carrying the exact base-10
value in canonical fixed-point notation — the `format(d, 'f')` rendering of the
`Decimal`: no scientific notation, no thousands separators, no leading `+`, and
fractional digits preserved exactly as the stored `Decimal` scale (e.g.
`"36428.0000"` for `money`, `"19.000"` for `LineasPorcentaje`). `website_qty`
serializes as a JSON string carrying the exact base-10 value of the fractional
`Decimal` aggregate: the fractional digits are preserved exactly as the
`Decimal` aggregation produces them, it is never rounded or truncated to an
integer, and it never passes through `float` or a JSON number. A JSON
number cannot preserve a `Decimal` exactly: the local transport
(FastAPI/Pydantic `jsonable_encoder`) coerces `Decimal` to `float`, so a JSON
number would introduce binary-float loss. Therefore the wire type for these
figures is a **string**, never a JSON number, and the implementation MUST emit
the string from the `Decimal`/`int` directly with no intermediate `float`.
`price_with_iva` serializes as an integer COP JSON number (`int`), and
`count`/`limit` remain non-monetary integers; `in_stock` remains a bool. No
decimal figure ever crosses the wire as a JSON `number` or `float`.

---

## 7. Typed errors and null reasons

### 7.1 Tool-level errors (`status == "error"`)

| `reason`              | When                                                                  |
|-----------------------|-----------------------------------------------------------------------|
| `query_required`      | `query` missing or trimmed length < 2                                  |
| `catalog_unavailable` | the J3 query/connection to SmartBusiness fails (driver/connection error, timeout, or unreadable result set) |

No other tool-level error states. The tool MUST NOT crash the chat; it returns
`status`/`reason` instead of raising, and the SQL builder MUST NOT throw or
crash on a driver/connection error.

On the error path, the response contains the standard top-level fields —
`query`, `products` as `[]`, `count` as `0`, `source` as `"none"`, `search_url`,
and `status` as `"error"` — **plus** the top-level `reason` key (§3). An error
response carries **no prices or figures**: no `price`, `j3_price`, `iva_rate`,
`price_with_iva`, or `magento_price` values, and no product rows.
Successful (`"ok"` / `"empty"`) responses MUST NOT include `reason`.

`catalog_unavailable` is a **fixed** reason string. The response, logs, and any
surfaced detail MUST NOT include driver/SQL/connection content: no driver error
message, no SQL text, no bound parameter values, no host/DSN. Nothing about the
query or connection is surfaced to the customer or logged at `INFO` or above
(§10). Whether the current runtime already satisfies this is **not** asserted
here; it is a requirement the implementation phase must satisfy and prove with
the fake-only tests (§12).

### 7.2 `price_with_iva_reason` (typed, when `price_with_iva` is `null`)

| `reason`           | Meaning                                                        |
|--------------------|----------------------------------------------------------------|
| `j3_price_missing` | no J3 row, or `j3_price` null / not a finite parseable decimal   |
| `line_not_found`   | article has no matching `AdmLineas.LineasID` (LEFT JOIN → NULL)  |
| `iva_rate_null`    | line matched, but `AdmLineas.LineasPorcentaje` is NULL           |

`price_with_iva_reason` is `null` when `price_with_iva` is non-null.

**Precedence (deterministic; highest first):**

1. `j3_price_missing` — there is no J3 price to compute from.
2. `line_not_found` — a J3 price exists but the article's `LineasID` resolves
   to no `AdmLineas` row (no rate reachable).
3. `iva_rate_null` — a J3 price and a line exist, but `LineasPorcentaje` is NULL.

This ordering yields a single, deterministic reason per product even when more
than one condition is true.

---

## 8. Server-side figure validation (implementation gate)

Every tool figure emitted to a customer — in particular `price_with_iva`, and
any IVA-inclusive price surfaced in a customer-facing reply — MUST be
recomputed and validated **server-side against the exact J3 result** before it
is emitted.

This is a **requirement/gate for the implementation phase**, not a claim that a
validator already exists. The implementation MUST:

- compute the figure from the exact `Decimal` J3 values, and
- reject any outgoing figure that does not exactly equal the server-side
  recomputation (no float arithmetic anywhere in the comparison path), and
- serialize every validated decimal figure as a canonical base-10 decimal
  string (§6), never a JSON number and never through `float`.

No float interpolation, no client-supplied arithmetic, SQL read-only. The
validation path is fail-closed: a figure that cannot be obtained as an exact
allowed type (`Decimal`/`int`) MUST NOT be emitted as a `float` or JSON number;
it is returned as `null`/reason, or omitted only when the schema permits.
Driver/connection errors surface only as the fixed `catalog_unavailable`
reason (§7.1), never raw driver/connection detail.

---

## 9. Backward compatibility

- Existing keys (`sku`, `name`, `price`, `website_qty`, `in_stock`,
  `product_url`, `source`, and top-level `query`, `products`, `count`,
  `source`, `search_url`, `status`) MUST remain present. `sku`, `name`,
  `website_qty`, `in_stock`, `product_url`, `source`, `search_url`, and
  `status` keep their unchanged meaning and value source.
- `price` changes meaning by design: it is now **always** the J3 price before
  IVA (`ArticulosVenta`), and is no longer replaced by a Magento price. The
  ambiguity is resolved by the additive `price_basis` / `price_includes_iva`
  fields plus `price_with_iva`; Magento's price, when needed, is the separate
  `magento_price` field.
- The legacy numeric fields `price`, `magento_price`, and `website_qty` are
  **re-typed** from JSON `number` to canonical base-10 decimal **string** (§6).
  This is a deliberate exactness requirement of Fredy's rule ("todo en
  `Decimal`, nada en `float`"), because the local transport (`jsonable_encoder`)
  coerces `Decimal` to `float`. Consumers MUST treat these fields as decimal
  strings, never as JSON numbers. `website_qty` likewise preserves the exact
  fractional digits of the `Decimal` stock aggregate and is never rounded or
  truncated to an integer.
- The public tool registration name `catalog.quote_search`, its
  `parameters_schema` (`query`, `limit`), and its `ToolScope.PUBLIC_CATALOG`
  / `public_safe=True` MUST NOT change.
- The existing test `tests/platform/test_catalog_quote_search.py` continues to
  exercise the J3 `price` value (`ArticulosVenta`); its assertion updates from
  `price == 36428` to the canonical decimal string `price == "36428.0000"`
  because `price` remains the J3 value but now serializes as a base-10 decimal
  string (§6). The implementation phase adds the IVA fields additively and
  updates tests without changing that J3 value source.

---

## 10. Logging constraints

- Logging changes MUST be minimal and additive only.
- No new per-query log lines are required; existing log behavior is unchanged.
- No customer/SKU names, query strings, or prices may be logged at `INFO` or
  above. If any debug logging of a calculation is added, it MUST be `DEBUG`
  level and MUST omit SKU, name, and query text.

---

## 11. ERP query constraints

The J3 query backing `quote_search` MUST remain:

- **Read-only** (`SELECT` only).
- **Parameterized** (`%s` placeholders; no string interpolation of user input).
- **Bounded** (`TOP {limit}` with `limit` clamped to `[1, 10]`).
- **No cost columns or cost calculations** — MUST NOT select `ArticulosCosto`,
  `ArticulosUltmoCosto`, `UltimoCostoCompra`, or any cost-derived value.
- **No margin/PII** — no customer or third-party data.
- **No hardcoded rate code** and no hardcoded universal IVA multiplier.
- **No `AdmArticulos.ArticulosEstado` filter.** The meaning of `ArticulosEstado`
  is not confirmed; the implementation MUST NOT filter on `ArticulosEstado = 1`
  or invent a meaning for it.
- **No new exact inventory quantities** — `quote_search` keeps only the
  website-allowlist aggregate `website_qty`; it MUST NOT add per-warehouse
  exact `SaldoActual` breakdowns.

The IVA rate is added via a LEFT JOIN `AdmArticulos.LineasID =
AdmLineas.LineasID` selecting `AdmLineas.LineasPorcentaje` (aliased to the IVA
rate). A missing line or a NULL `LineasPorcentaje` MUST NOT filter the product
out; it yields `iva_rate = null` (§5, §7).

This contract does **not** reproduce real queries or customer data; the above
are constraints only.

---

## 12. Test contract (fake-only, no live ERP/BFF, shared SQL builder)

Tests MUST be fake-only and MUST NEVER contact ERP, Magento, or BFF. Tests use
synthetic data in an in-memory **SQLite** database, executed through the **same
production SQL builder** — a single builder function that parameterizes the SQL
dialect (T-SQL in production, SQLite in tests). Tests MUST NOT hand-write a
second, duplicated query.

Cases to cover (minimum):

1. **Rates** — synthetic `19.0`, `5.0`, and `0.0` percentages produce the exact
   `price_with_iva` (e.g. a pre-IVA `100.00` → `119`, `105`, `100`).
2. **0 % exempt** — `iva_rate == 0` adds no IVA; `price_with_iva ==
   ROUND_HALF_UP(Decimal(j3_price))`.
3. **Null rate / missing line** — no `AdmLineas` match → `iva_rate` null,
   `price_with_iva` null, reason `line_not_found`; `LineasPorcentaje IS NULL` →
   reason `iva_rate_null`. The SKU still appears with its J3 `price`/`j3_price`.
4. **HALF_UP of COP** — a boundary value ending in `.5` rounds half-up to the
   integer COP.
5. **`money`/`decimal` precision** — `j3_price` preserves `money` scale (4
   decimals) as `Decimal`; no `float` truncation before the final rounding.
6. **J3 vs Magento** — a Magento match never changes `price`, `price_basis`,
   `price_includes_iva`, `j3_price`, `iva_rate`, or `price_with_iva`; Magento
   contributes only `name`, `product_url`, and the separate `magento_price`.
7. **Group rate ignored** — a synthetic `AdmGrupos.Porcentaje` value MUST NOT
   affect `iva_rate` or `price_with_iva`.
8. **`ArticulosEstado` not filtered** — a synthetic row with any
   `ArticulosEstado` value is returned; no `ArticulosEstado = 1` filter is
   present in the SQL.
9. **No floats / cost / PII** — the query selects no cost column and no
   float-based arithmetic; the output contains no cost or PII keys.
10. **Existing-shape compatibility** — the J3 `price` value and top-level shape
    for the current J3-merge happy path still hold, with `price` asserted as the
    canonical decimal string `"36428.0000"` (not a JSON number).
11. **`catalog_unavailable`** — a simulated driver/connection failure (SQLite
    fixture returning a connection error) yields `status == "error"` with the
    fixed `reason == "catalog_unavailable"`, `products == []`, `count == 0`,
    `source == "none"`, and **no** `price`/`j3_price`/`iva_rate`/
    `price_with_iva` values; the response carries no driver/SQL/parameter text.
12. **Exact decimal string serialization** — `price`, `j3_price`, `iva_rate`,
    `magento_price`, and `website_qty` serialize as canonical base-10 decimal
    strings (e.g. `"100.0000"`, `"19.000"`, and a fractional `website_qty`
    such as `"12.5000"` preserving its exact `Decimal` digits), never a JSON
    number and never through `float`, and never rounded or truncated to an
    integer; no decimal figure crosses the wire as a JSON `number` or
    `float`; `price_with_iva` stays an integer COP, `count`/`limit` stay
    non-monetary integers, and `in_stock` stays a bool.

No test may assert a concrete IVA rate value sourced from a live ERP; all rates
are synthetic.

---

## 13. Size constraints

- New per-tool logic MUST stay under 300 lines.
- `builtins.py` MUST NOT be bloated: new IVA/price logic goes into a separate
  module (e.g. under `business_analyzer` or `depotru_tools`), not inline growth
  of `_tool_quote_search`.

---

## 14. Out of scope (non-goals)

- No implementation, SQL, or test changes were made in this pass; this document
  is contract only. A later local implementation phase is authorized by the
  current order and MUST comply with this contract exactly (including §7.1 and
  §8).
- No change to `catalog.search_products` or `inventory.sellable_qty`.
- No hardcoding of any specific Colombian IVA rate or tariff code.
- No Magento-derived IVA.
- No cost/margin columns or PII.
- No use of `AdmGrupos.Porcentaje`, `AdmLineas.LineasIndicadorIva`, `Incbp`, or
  other indicators to decide the rate.

---

## 15. Open uncertainty (to coordinator)

1. **`AdmLineas.LineasIndicadorIva` semantics** — its meaning (e.g. gravado /
   excluido / bolsas) is **not confirmed**. It is **not used** in the IVA
   calculation and MUST NOT influence `iva_rate`, `price_with_iva`, or any
   emitted figure. This is the only open uncertainty retained by this contract.
