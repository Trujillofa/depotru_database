# Contract — `catalog.resolve_customer_phone`

> Contract for the B3 slice "resolve customer by phone". The current worktree
> contains the local implementation in
> `business_analyzer.core.j3system_customer_phone` and fake-only tests in
> `tests/platform/test_catalog_resolve_customer_phone.py`. This contract is
> the executable target for that branch; it is not evidence of a live ERP/BFF
> query, production deployment, or remote verification.
>
> Feeds B2: after exactly one customer with a usable tariff is resolved,
> `_tool_resolve_customer_phone` stores `terceros_id` in the server-maintained
> `ToolContext.extras["verified_customer_terceros_id"]`, which B2 reads as
> `verified_customer_terceros_id` (B2 contract §2/§3). An authorized resolution
> attempt first clears any prior identity; failures and ambiguity leave the key
> absent. The phone is never stored in context. This slice never reads price,
> stock, cost, or margin, and it never writes to ERP.

## 1. Purpose and audience

A sales agent receives a phone number over the phone and needs to resolve it
to the single customer whose tariff list may be quoted. The phone is the
**only** input; the tool returns at most one resolved internal `terceros_id`
with its tariff, or refuses. When more than one customer could match, it
stays ambiguous and requires a human to choose — it never guesses.

This is **sales context only**. It is **not** a public tool and **not** a
customer self-identification tool.

| Property | Value |
|---|---|
| Tool name | `catalog.resolve_customer_phone` |
| Registry scope | `ToolScope.SALES_PORTFOLIO` |
| Usable audiences | `SALES` (and `ADMIN`, per the kernel scope model) |
| Discoverable by `PUBLIC` / `CUSTOMER` / `WAREHOUSE` / `SERVICE` / `AGENT` | No |
| `public_safe` | `False` |
| Side effects | None. Read-only ERP SQL; no writes, Magento, HTTP, or other ERP actions |
| Module | `business_analyzer.core.j3system_customer_phone` |

The registry scope is the primary gate (`ToolRegistry.call` invokes
`audience_may_use` before the handler — `depotru_tools/registry.py`); the
handler additionally refuses any audience outside `{SALES, ADMIN}` so the rule
stays closed even if the scope map changes.

### 1.1 Phone is PII: it never leaves the resolver

The input phone is PII and is treated as a secret-shaped value for this
slice's entire lifetime:

- It is **never returned** in any payload, success or error.
- It is **never logged**, **never** included in metrics, **never** in a trace,
  **never** in an exception message, and **never** in a report.
- It is **never interpolated into SQL** as a literal; it is passed only as
  bound parameters.
- It is **never** surfaced as a candidate value: the ambiguous branch returns
  only the minimal fields in §6.2, never the phone, name, or identification.

## 2. Closed input schema

The model may supply **exactly one** key. Any other key is rejected before
ERP access.

| Key | Type | Notes |
|---|---|---|
| `phone` | string or positive `int` | single value, never a list. Strings are stripped of surrounding whitespace before evaluation |

Accepted input forms (implemented by `phone_keys` in this worktree):

- `None` → `phone_required`.
- `bool` (any) → `phone_invalid` (booleans are never a phone).
- `int` → accepted only when `> 0`, rendered as its decimal string; `0` and
  negatives are empty and therefore `phone_required`/`phone_invalid`.
- `str` → stripped; empty/whitespace-only → `phone_required`.
- any other type → `phone_invalid`.

**Raw length bound.** A raw string longer than `MAX_PHONE_RAW = 40`
characters (before digit extraction) → `phone_invalid`.

**Digit length bounds.** After normalization (§3), the digit count must be
`7..15` inclusive (`MIN_PHONE_DIGITS = 7`, `MAX_PHONE_DIGITS = 15`) and must
contain at least one digit `1..9` (an all-zero number is invalid).

## 3. Normalization rules (allowed vs. disallowed)

The resolver builds **digit keys** used only as bound SQL parameters.

1. Leading/trailing whitespace is stripped from the string.
2. **Allowed** separators are dropped: space, `-`, `+`, `(`, `)`, `.`, `/`,
   and tab. The SQL builder strips exactly this set (`_SEPARATORS`).
3. Digits are kept.
4. **Rejection rule.** Any character other than an ASCII digit or an allowed
   separator fails `phone_invalid`. Letters and any other character are never
   silently dropped, so mixed alphanumeric text never becomes a valid phone.
5. Country-code expansion: a key with a leading `57` also produces its
   national form (drop `57`) only when the national form still has ≥ 7
   digits; a key without a leading `57` also produces its international form
   (`57` prepended) only when that stays ≤ 15 digits. Duplicate keys collapse
   to one. The result is a tuple of 1 or 2 distinct digit keys.

**Scope limitation — not country validation.** `7..15` digits is a generic
bound, not a Colombia-specific (or multi-country) format policy. The `57`/
national expansion is the only format handling this slice performs. Any
country-specific format or validation policy outside that exact algorithm is
**not asserted** by this contract.

## 4. Identity rules (PII exposure)

1. The phone is the sole selector and is used only as bound parameters.
2. `TercerosNombres` (customer name) is **never selected** and never returned.
3. Cost and margin columns are **never selected** (see §5, forbidden
   fragments).
4. `terceros_id` is an **internal** identifier. It is returned in the payload
   **only** to a `SALES`/`ADMIN` audience, because B2 consumes it as
   `verified_customer_terceros_id`. It is never exposed to `PUBLIC` /
   `CUSTOMER`.
5. The tariff payload is `{"codigo", "nombre"}` (§7); it is justified for the
   SALES quoting flow and restricted to SALES.

### 4.1 `TercerosIdentificacion` is never returned

`TercerosIdentificacion` (cédula/NIT) is customer PII and is **not
authorized** for this slice. It is never selected and never returned — neither
in the resolved payload nor in ambiguous candidates. The ambiguous branch
exposes only the minimal candidate fields (`terceros_id` + `tarifa_codigo`),
never an identification, name, phone, or other customer detail. The scope
stays **SALES-only**; no identifiable detail may reach `PUBLIC`/`CUSTOMER`.

### 4.2 Server-side handoff to B2

The handler stores the verified identity in
`ToolContext.extras["verified_customer_terceros_id"]`, the server-side key B2
reads (§2/§3 of the B2 contract). It clears any prior value at the start of an
authorized resolution attempt, before schema/phone validation. Only an `ok`
result with a positive, non-boolean integer ID writes the new value. Invalid,
missing, ambiguous, tariff-refused/missing, not-found, and ERP-error outcomes
leave the key absent. The phone itself is never stored in `extras` or any other
context field; it cannot be supplied as a B2 parameter.

## 5. SQL and data rules (read-only, bound, leak-free)

**Read-only `SELECT` only.** No DDL, no DML, no stored procedure. Tables are
qualified with `qualified_j3_table()` (`J3System.dbo.<table>`).

### 5.1 Allowed columns and joins

- `AdmTerceros` (alias `t`): `TercerosID` and `TarifasID` are selected. The
  three phone columns `TercerosCelular`, `TercerosCelular2`,
  `TelefonoContacto` appear **only** in the `WHERE` predicate (see §5.3) and
  are never selected. `TercerosIdentificacion` is never referenced.
- `AdmTarifas` (alias `tf`), `LEFT JOIN ... ON tf.TarifasID = t.TarifasID`:
  `TarifasCodigo`, `TarifasNombre`.
- The match predicate is `ISNULL(t.<phone_column>, '')` with the allowed
  separators removed via nested `REPLACE`, compared against the bound digit
  keys with `IN (...)` across the three phone columns (an `OR`).

### 5.2 Forbidden fragments (never selected)

`FORBIDDEN_SQL_FRAGMENTS` — the generated SQL must not contain any of:

```
ArticulosCosto, ArticulosUltmoCosto, ArticulosMargen, UltimoCostoCompra,
CostoInicial, CostoDepre, ValorCosto, ListadoPreciosCosto, CostoSinIva,
CostoMasIva, CostoAnterior, PreciosIncremento, PreciosValor, ArticulosVenta,
TercerosNombres
```

No customer name, no cost, no margin, no price column is selected by this
slice.

### 5.3 Phone columns appear only in the `WHERE`, never in the `SELECT`

Raw phone values never cross the driver boundary. The three phone columns are
matched **only** in the `WHERE` predicate (`ISNULL(t.<column>, '')` with the
allowed separators removed via nested `REPLACE`, compared against the bound
digit keys with `IN (...)` across the three columns). They are **not**
selected, so no raw phone value is ever fetched or returned. There is no
in-memory re-check of phone values: the SQL `WHERE` is the single match point,
and every returned row has already matched at least one phone column.

### 5.4 Bound parameters

The digit keys are the **only** bound parameters. `fetch_customer_by_phone`
calls `db.execute_query(sql, tuple(keys) * 3)` — one key pair per phone
column. With 1 key the SQL has 3 `%s` placeholders; with 2 keys it has 6.
`build_phone_match_sql` accepts only `key_count ∈ {1, 2}` and raises
`ValueError` otherwise.

### 5.5 Fail-closed on ERP failure

`fetch_customer_by_phone` wraps the read in a single `try/except` and returns
`erp_unavailable` on any exception; a non-list result is also
`erp_unavailable`. The driver message is **not** returned.

**GATE — do not assume a distinction.** `erp_unavailable` is a single
catch-all in the worktree implementation; it does **not** distinguish a SQL error from
a timeout, and this contract does not add a distinction without code
evidence. Cite: the single `except Exception` in `fetch_customer_by_phone`
collapses both to the same reason.

**GATE — registry validates scope, not parameters.** `ToolRegistry.call`
(`depotru_tools/registry.py`) checks only `audience_may_use(ctx.audience,
spec.scope)` before dispatching; it does **not** validate parameters. Parameter
validation is the handler's job: the handler must validate the phone (length,
type, allowed characters) **before** any `Database` is constructed or any
query is executed, so a junk phone fails closed without ERP access. The B3 unit
test replaces `Database` with a fake and asserts `phone_invalid` is returned
first.

## 6. Decision rules (one usable list, or refuse)

`decide_phone_rows(rows)` applies in order (the phone match has already been
applied by the SQL `WHERE`, so `rows` is the matched set):

1. Parse a positive `terceros_id`; drop rows without one.
2. **Duplicate `terceros_id`** among the matched set → `erp_unavailable`
   (fail closed; an ERP inconsistency is never resolved by guessing).
3. No match → `customer_not_found`.
4. `usable` = matched rows where `tariff_decision(row) is None` (tariff id
   present, not `0`, not `006 AL COSTO`, with a code/name — see §6.1).
5. Exactly one usable → `ok` with `terceros_id` + `tarifa` payload.
6. Zero usable: one matched row → `tariff_refused` (006) or `tariff_missing`
   (missing), with no customer or tariff metadata echoed; several matched rows
   → `customer_not_found`. This matches B2's refusal boundary (§6).
7. More than `MAX_CANDIDATES = 12` usable → `phone_ambiguous`,
   `truncated: true`, `candidates: []` (no partial choice).
8. Otherwise (2..12 usable) → `phone_ambiguous`, `truncated: false`, with a
   candidate list sorted by `terceros_id`.

Ambiguity is **never** resolved by guessing: it always requires human
intervention.

### 6.1 Tariff rules (reused from B2)

`tariff_decision` (B2 `j3system_customer_quote`) decides:

- Tariff id `6`, code `006`, or name `AL COSTO` → `tariff_refused`.
- Missing id, or missing code **and** missing name → `tariff_missing`.
- Otherwise → usable (`None`).

**`006 AL COSTO` never resolves.** A customer whose only tariff is 006 is
refused, never quoted, and never silently re-selected.

### 6.2 Ambiguous candidates (closed shape)

Each candidate carries only:

```jsonc
{ "terceros_id": 8, "tarifa_codigo": "001" }
```

`identificacion` is **never** emitted (§4.1). The candidate set is exactly
`terceros_id` + `tarifa_codigo`. The phone is **never** a candidate field.

## 7. Closed output schema

```jsonc
// success (exactly one usable list)
{
  "status": "ok",
  "terceros_id": 8,                 // internal; becomes B2 verified_customer_terceros_id
  "tarifa": { "codigo": "005", "nombre": "FERRETERIA AAA" }
}

// error
{
  "status": "error",
  "reason": "<closed reason enum>",
  // per-reason extra fields only (see table below)
}
```

Per-reason extra fields:

| reason | extra fields |
|---|---|
| `phone_required` | none |
| `phone_invalid` | none |
| `customer_not_found` | none |
| `tariff_missing` | none (reason only) |
| `tariff_refused` | none (reason only) |
| `phone_ambiguous` | `truncated` (bool), `candidates` (list) |
| `erp_unavailable` | none |

- The payload **omits the phone entirely**; `terceros_id` and `tarifa` are
  present only where justified and only for a `SALES` audience.
- No customer name, no cost, no margin, and no identification.

## 8. Reason enum (closed) and fixed messages

The reason is a fixed machine-readable enum, consistent with the `reason`
convention already used by `depotru_tools.builtins`. Each reason maps to a
**fixed** Spanish message; none interpolates the phone or the driver text.

| reason | fixed Spanish message (constant, never the phone) |
|---|---|
| `phone_required` | "El teléfono es obligatorio." |
| `phone_invalid` | "El teléfono no es válido." |
| `customer_not_found` | "No se encontró un cliente con tarifa usable para ese teléfono." |
| `tariff_missing` | "El cliente no tiene una tarifa asignada." |
| `tariff_refused` | "La tarifa del cliente (AL COSTO) no permite cotizar." |
| `phone_ambiguous` | "Hay varios clientes posibles; se requiere intervención humana para elegir." |
| `erp_unavailable` | "No fue posible consultar el sistema en este momento." |

These are constants; the handler returns the reason enum, and any user-facing
renderer must use the fixed string, never the raw input.

### 8.1 Handler guard reasons (fixed, non-resolution)

The handler (`_tool_resolve_customer_phone` in `depotru_tools.builtins`)
emits two additional fixed reasons before any resolution or ERP access. They
never carry the phone, the driver text, or any customer data:

| reason | fixed Spanish message |
|---|---|
| `audience_not_allowed` | "No autorizado para esta audiencia." |
| `unexpected_parameters` | "Parámetros no esperados." |

`audience_not_allowed` is returned only when an audience outside
`{SALES, ADMIN}` reaches the handler directly (the registry normally raises
`ToolPermissionError` first — §1). `unexpected_parameters` is returned when
`params` is not a mapping or contains any key other than `phone`. A missing
`phone` key is `phone_required` (§2). These two are defense-in-depth gates and
are not part of the resolution result enum above.

## 9. Safety rules

- Read-only `SELECT`; tables qualified via `qualified_j3_table()`.
- Bound parameters only; the phone is never a SQL literal.
- Forbidden cost/margin/name fragments never appear in generated SQL.
- Fail closed: driver messages never leak; `erp_unavailable` only.
- No logging of input, parameters, rows, or customer data.
- Phone columns are never selected (§5.3); the phone never leaves the resolver.
- No customer name, no cost, no margin in any output.

## 10. Test matrix (fake, runtime-generated fixtures only)

Fixtures are generated at runtime (e.g. a seeded fake-phone builder); **no
literal customer phone number, PII, credential, secret, or URL is stored** in
tests. Coverage:

| # | Case |
|---|---|
| 1 | SALES-only registration; `PUBLIC` cannot discover or invoke (`ToolPermissionError`) |
| 2 | Handler validates phone before any `Database` is constructed (junk phone → `phone_invalid`, DB untouched) |
| 3 | Invalid phone: `None`/blank → `phone_required`; `bool`, short, all-zero, too long, disallowed chars → `phone_invalid` |
| 4 | Normalization: `57`/national equivalence and bound-parameter shape (3 vs 6 placeholders) |
| 5 | Bound params only; no phone literal in SQL; forbidden fragments absent |
| 6 | One usable list among several rows resolves; no phone/name/cost in the dump |
| 7 | Three OR-ed `WHERE` predicates, each with the full bound key set; no phone column is selected |
| 8 | Two usable lists → `phone_ambiguous` without the phone |
| 9 | Two ids sharing one identification stay ambiguous (no false merge) |
| 10 | > 12 usable → `phone_ambiguous`, `truncated: true`, empty candidates |
| 11 | No usable list / missing tariff / 006 AL COSTO → fail closed; 006 → `tariff_refused` with no candidates |
| 12 | Duplicate `terceros_id` → `erp_unavailable` (never guessed) |
| 13 | ERP error → `erp_unavailable`, no driver text, no phone |
| 14 | B2 handoff key is set only on unique success; stale identity is cleared on every failed resolution |

## 11. Implementation decisions versus the sanitized source mirror

The worktree implementation preserves useful source behavior and applies the
divergences below to satisfy this contract and the B2 safety boundary.

These decisions are resolved as follows:

1. **Letters are rejected, not stripped** (§3) — enforced; `phone_keys` fails
   `phone_invalid` on any non-digit/non-separator character.
2. **`7..15` generic digit bound** (§3) — retained as a generic bound, not a
   country/format policy; the `57`/national expansion is the only format
   handling, and nothing beyond it is asserted.
3. **`TercerosIdentificacion`** (§4.1) — omitted from all outputs.
4. **`erp_unavailable` is a single catch-all** (§5.5) — retained; the registry
   validates scope and the handler validates parameters, no driver-text
   distinction is invented.
5. **Phone columns** (§5.3) — moved out of the `SELECT`; matched only in the
   `WHERE`.
6. **`tarifa_payload`** — built locally in B3 (a minimal `{"codigo",
   "nombre"}` dict); `tariff_decision` is reused from B2 unchanged.
7. **Tariff refusal omits metadata** (§6/§7) — aligned with B2 contract §6:
   `tariff_missing` and `tariff_refused` return only the closed reason; they do
   not echo `terceros_id` or tariff metadata.

## 12. Scope boundary (never exceeded)

This slice resolves a phone to an internal `terceros_id` + tariff for a SALES
quote. It does not read price, stock, cost, or margin; it does not write; it
is not a public tool; it is not a customer self-identification tool. Any
identifier it emits is internal, SALES-only, and justified only as input to
B2's quoting flow.
