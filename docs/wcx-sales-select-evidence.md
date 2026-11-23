# D4 — live SELECT evidence and remaining approval gate

## Scope and execution

Owner release recorded in task `t_020a9b10` on 2026-11-23 authorizes design
and SELECT-only discovery against WCX PostgreSQL and SmartBusiness MSSQL.
This supplements the original [design](wcx-conversations-sales.md), not an
implementation or approval of its proposed business rules.

Executed from the assigned `hermes/d4-conversaciones-ventas` worktree. No
import, migration, DB write, service call/restart, merge or deployment. Original
WCX archives and `useful/` were not opened or changed. No message body, customer
name, raw JSON or attachment was selected. Identifiers needed for the candidate
join stayed in local process memory: never printed, saved or sent to an LLM.
Only schema metadata and aggregates were emitted. Credentials were loaded from
existing local env files without printing them or changing configuration.

PostgreSQL reads used `BEGIN READ ONLY`, a 30-second statement timeout and
`ROLLBACK`. MSSQL used direct `pymssql` SELECTs, 30/45-second query timeouts,
12-second login timeout and connection rollback/close. No `NOLOCK` or cross-server
join. These sequential observations are **not** a shared point-in-time snapshot.
The exact queries are in [the evidence SQL](drafts/wcx-sales-evidence.sql.template).
No database rows were persisted; future identified extracts require separate
permission and must remain in protected `~/wcx/derived/` storage.

## Verified schema changes versus the original D3 proposal

The installed tables, not the old draft DDL, are authoritative:

- `wcx_customers` includes `phone_shared`, but has **no `contact_id` or
  `link_state`**. D4 must not read those proposed fields as installed columns.
  There is no structured NIT field. Do not mine `raw` or message bodies for one.
- `wcx_cases` has local/UTC timestamps and timezone fields; all are populated in
  this observation. Population does not independently validate the chosen zone.
- `wcx_messages` additionally retains `is_admin`, `is_owner`, `is_automation`.
  Neither those flags nor the observed two actor labels and eight source-type
  values establish external visibility or the identity of the human responder.
  No raw enum value is relabelled as a business outcome.
- SmartBusiness has `dbo.clientes(uid, nit, telefono, celular, ...)` and
  `dbo.banco_datos(TercerosID, TercerosIdentificacion, DocumentosCodigo,
  NumeroDocumento, Fecha, TotalSinIva, Cantidad, ...)`.
- `banco_datos.Fecha` is SQL **`date`**, not a precise sale timestamp. Strict
  intra-day response-before-sale attribution is unavailable from this table.
- `clientes.uid = banco_datos.TercerosID` is **not** assumed proven merely from
  field names. The exploratory join below uses exact NIT-string equality only;
  it does not establish identification type, DV semantics or historical ownership.

## Aggregate observations

| PostgreSQL check | Observed count |
|---|---:|
| Source namespaces | 1 |
| Customers | 7,948 |
| Customers with phone | 6,830 |
| Distinct source-scoped phone candidates | 6,826 |
| Shared phone groups / flagged customer rows | 4 / 8 |
| Cases / cases with customer reference | 14,336 / 14,334 |
| Cases with local timestamp / UTC / timezone | 14,336 / 14,336 / 14,336 |
| Messages | 301,136 |
| Messages with local timestamp / UTC / timezone | 301,136 / 301,136 / 301,136 |

These counts agree with the approved production-import handoff for customers,
cases and messages; they supersede old prototype message eligibility counts.
They are not counts of externally visible customer conversations.

SmartBusiness discovery interval: **[2025-11-01, 2026-11-01)**, chosen solely as
an explicit bounded exploratory period, not the approved WCX cohort or a claim
of completeness. Canonical document exclusions: `XY, AS, TS, YX, ISC`.

| SmartBusiness check | Observed count |
|---|---:|
| Current master rows / distinct uid / distinct nit | 64,367 / 64,367 / 64,367 |
| Valid distinct current master phones using D3 normalizer | 14,435 |
| Sales-line rows in interval after exclusions | 400,217 |
| Missing identification / document number / net amount rows | 0 / 0 / 0 |
| Negative-quantity rows, retained in discovery | 7,074 |
| Distinct `TercerosID` in interval | 20,483 |

No document allowlist or return/cancellation reconciliation was invented. These
are sales-source quality counts, not approved invoice or conversion counts.

## Exploratory phone → master NIT → period-presence join

Local in-memory algorithm, using the existing unmodified D3 `normalize_phone`:

1. SELECT only `(source, source_customer_id, phone_e164, phone_shared)` from WCX.
2. SELECT only `(uid, nit, telefono, celular)` from the current ERP master.
   Normalize each phone field independently; do not split lists, repair legacy
   formats or change phone-normalization policy. Index by valid phone with sets
   of distinct `(uid, nit)` pairs, so the same phone in two fields is not doubled.
3. Exclude WCX missing/shared phones. Require exactly one ERP pair and a nonempty
   NIT attached to exactly one master uid. Keep unmatched and ambiguous separate.
4. Read only period sales-line counts grouped by `TercerosIdentificacion`.
   Check candidate NIT against that set using **exact string equality**, without
   trimming, numeric casts, dropping DV or merging identification types.
5. Emit counts only; destroy local process state on exit. No persistent bridge.

| Disjoint WCX customer partition | Count |
|---|---:|
| No phone | 1,118 |
| Shared WCX phone excluded | 8 |
| No valid current-master phone match | 6,470 |
| Multiple master `(uid, nit)` candidates | 10 |
| Single pair but empty/nonunique master NIT | 0 |
| Single current phone/uid/NIT candidate | 342 |
| **Partition total** | **7,948** |

Of the 342 candidates, **241** have an exact NIT-string occurrence in the
bounded sales period; **101** do not. The sum of the partition was asserted
against the WCX population and the 241 candidate-presence result independently
reconciled with a set-intersection calculation in the local process (PASS).
This checks internal arithmetic, not source independence or semantic correctness.

**Do not calculate a conversion rate from 241/342.** These are customers, not
cases; presence in a year is not a sale after a conversation. Current phone
matches do not prove historical ownership. NIT comes from the same matched ERP
row, so it is **not independent WCX NIT corroboration**. The 6,470 unmatched
customers do not prove absence from ERP or absence of purchases. Strict phone
normalization, current-master coverage and changed/shared numbers limit recall.
The crosswalk remains unapproved; no row is automatically linked.

## What can and cannot be delivered now

- **Conversation → sale:** relational design and synthetic metric tests already
  exist in PR #119. Real association needs an approved historical identity bridge,
  cohort/window/halo, invoice grain, document allowlist and return policy.
- **Advisor response versus closed sale:** response visibility/type mapping and
  responder identity remain unverified; ERP date-only prevents strict intraday
  ordering. A day-level sensitivity study would be a separate owner decision,
  never an implicit substitute. No advisor ranking or real response KPI published.
- **Losses by reason:** installed columns do not provide a verified structured
  loss disposition/reason. No-match/closed status is not a loss. No text mining
  or invented reason taxonomy was applied; lost revenue remains unavailable.

## Required owner decisions before another stage

1. Approve using `clientes` as the master, exact NIT identification semantics and
   an audited historical phone/identity bridge. Supply structured WCX NIT evidence
   or an explicitly reviewed binding; decide shared/recycled-phone handling.
2. Choose cohort, window, conservative ambiguity handling versus another attribution
   rule, invoice uniqueness, sale documents, returns and gross/net official KPI.
   Decide whether a separately labelled **day-level** association is acceptable.
3. Confirm source timezone semantics, external-message/source-type/actor mapping
   and whether a message-level responder can be established without new imports.
4. Supply loss status/reason mapping or approve a controlled manual-review process;
   approve privacy, retention, permitted access and minimum publication cell size.

Until then, stop at this design and aggregate discovery. No scheduled analysis,
public metric, DB write or change to `wcx_*` is authorized. PR #119 stays open
for the owner's approval; this task returns to the requested approval gate.
