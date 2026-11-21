# WCX conversations → SmartBusiness sales — D4 design

**Status: proposed design; owner decisions required, not an implementation.**
D3 was released by the owner in the task thread and PR
[#116](https://github.com/Trujillofa/depotru_database/pull/116) is merged at
`3e0509b202a65552c833cae227590f76a3604cdc`. That approval permits this D4 design,
not imports, DB writes, deployment or an operational attribution policy.

**Goal:** define auditable conversation-to-sale, advisor-response and declared-loss
metrics without conflating identity matches with proof that a chat caused a sale.

**Architecture:** retain D3's inbox-owned PostgreSQL history, read SmartBusiness
MSSQL separately, reconcile privately in an authorized local process, and publish
aggregates only. No cross-server SQL join, ERP schema change, scheduled job,
API endpoint, migration, importer or persistent new table is delivered here.

**Tech stack:** existing Python/D3 normalizer; MSSQL metadata/SELECT proposals;
portable relational metric SELECT; SQLite in-memory synthetic specification.

## 1. Reuse and evidence limits

Reuse [D3](crm-wcx-import.md), without renaming or extending its stored tables:

- `wcx_customers(source, source_customer_id, phone_e164, contact_id, link_state)`;
- `wcx_cases(source, source_case_id, source_customer_id, source_status,
  source_channel, source_agent_id, created_at, source_timezone)`;
- `wcx_messages(source, source_case_id, source_message_id, actor, source_type,
  occurred_at)` and the quarantine/fingerprint rules from D3;
- `depotru_integrations.wcx_import.normalize_phone`, unmodified. A validated
  Colombian E.164 candidate is not a verified owner or an ERP identity.

D3's `contact_id`/`link_state` concern the inbox, **not ERP authorization**. Do not
reuse `approved` as an ERP link merely because the inbox link was approved.
D4's logical `case_facts.link_state` below means a separate reviewed ERP bridge.
WCX customer IDs, inbox contact IDs, J3 `TercerosID` and SmartBusiness identity
values are different namespaces. Never equate their numeric/string values.

D3 has **no verified NIT column** and does not map loss reasons, status meaning,
actor enums or timezone automatically. A NIT mentioned in free text is neither
an approved identity field nor permission to extract it. No body-text mining or
LLM classifier is proposed as ground truth. Missing mappings remain unavailable.

Repository evidence, not a live schema check:
`src/business_analyzer/ai/training.py` documents `banco_datos` sales lines with
`TercerosIdentificacion`, `DocumentosCodigo`, `NumeroDocumento`, `Fecha`,
`TotalSinIva`, `TotalMasIva`, `Cantidad`. Verify schema and semantics before use;
training is not a uniqueness constraint. No phone column in `banco_datos` is
verified here. J3 phone tools must NOT be substituted for SmartBusiness master
identity without an explicitly verified crosswalk.

## 2. Identity bridge (proposal, local and reviewable)

Keep a **logical**, private bridge (no table/DDL in this PR) keyed by
`(source, source_customer_id)` with typed ERP customer key, evidence kind,
review status, validity interval, reviewer/time, policy version and revocation.
Use source keys for WCX dedupe, never phone/NIT/name. No automatic contact or ERP
customer creation, overwriting, many-to-one merging or name-based fuzzy matching.

Candidate generation, in order:

1. Read an owner-approved SmartBusiness customer master/crosswalk with stable
   customer key and phone fields, once those field names/permissions are verified.
   Run the **same D3 normalizer** on WCX and master phone candidates. A shared,
   recycled, invalid or temporally unverifiable phone stays unlinked/ambiguous.
2. NIT path requires a separately verified structured source or manually reviewed
   source-customer → ERP binding. Preserve identification type, country, leading
   zeros and check digit semantics; strip only owner-approved display formatting.
   Never cast to integer, drop the DV indiscriminately or match a CC to a NIT.
   There is deliberately no invented NIT normalizer in D4.
3. Require exactly one reviewed source identity ↔ ERP identity within the approved
   historical validity interval. Even matching NIT syntax is not ownership proof.
   If phone and NIT evidence disagree, quarantine; NIT does not silently win.
4. Review key duplicates on **both** sides across the whole approved identity
   population, not just the selected month. Current phone equality cannot prove
   historical ownership; absent historical evidence remains unlinked.
5. Before each run revalidate bridge status, evidence, validity, conflicts and
   scope. Revoked links are excluded. Never log raw bridge keys or hashes.

The eventual local bridge and raw query results may exist only under
`~/wcx/derived/` (directory `0700`, files `0600`) if separately authorized.
Hashes of phones/NIT are not anonymization. Nothing identified enters this repo,
PR, card, external LLM, or report. No real WCX files were opened for D4.

## 3. Read-only discovery and source contract

The companion [discovery SELECTs](drafts/wcx-sales-discovery.sql.template) are
**not executed** against any DB. The first inventories column names/types only;
the second returns bounded aggregate quality counts, not identities. Schema
`dbo` and the training fields are hypotheses to confirm, not installed views.
Use the existing per-thread DB manager, bound `%s` parameters, least-privilege
SELECT credentials, bounded dates, timeout and an approved maintenance window
for any future large scan. Never use `NOLOCK` to trade consistency for speed.
Use a consistent observed cutoff/snapshot; record data freshness and completeness.

Invoice grain proposed for validation: `(ERP company/database namespace,
DocumentosCodigo, NumeroDocumento)`; add branch/series if the owner confirms
numbers can collide. Deduplicate source lines by **verified line identity**, not
`DISTINCT` on amounts or concatenated document strings. Reject invoices with
conflicting customer/date values. Do not sum invoice header totals per line.
`SUM(TotalSinIva)` is appropriate only after confirming it is a line amount.

Always apply canonical exclusions `XY, AS, TS, YX, ISC` (future builder imports
`CANONICAL_EXCLUDED_DOCUMENT_CODES`, never copies a three-code legacy filter).
These exclusions are **not a sales allowlist**. Owner must supply invoice,
credit-note/cancellation and branch document mappings. Returns/negative quantity
stay in accounting totals. Build one invoice fact per original commercial sale,
reconciling linked returns/cancellations through the chosen cutoff. Do not count
a credit note itself as a new sale; unmatched returns are a separate coverage
failure, not silently dropped. Report gross issuance and retained/net conversion
separately once the owner chooses their official KPI.

For any final financial report, use decimal money (not float), amounts before IVA
unless explicitly labelled otherwise, and show returns/cancellations separately.
The template illustrates **retained/net-positive conversion**, not the official
business definition. Its `net_cop` includes signed amounts even when nonpositive.
Specifically, the proposed scenario requires the **sum across the case's uniquely
attributed invoice facts > 0**, not merely any positive retained invoice. A +100
and a −100 invoice produce no conversion here. Choosing a different business
definition requires owner approval and a changed specification/test.

## 4. Logical input relations (NOT production tables)

The [metric SELECT](drafts/wcx-sales-metrics.sql.template) is an executable design
specification over these strictly validated, deduplicated inputs. It cannot run
against D3 alone. A future approved adapter supplies them as private in-memory
relations or parameterized CTEs; creating staging tables needs a new authorization.
No adapter/CLI or runtime integration is shipped.

| Relation | Required contract |
|---|---|
| `case_facts` | One row per `(source, case_id)` from D3; opaque reviewed ERP `customer_key` or null; ERP `link_state`; `opened_epoch`, `window_end_epoch`; nullable `first_response_seconds`; nullable approved `declared_outcome` and `loss_reason` code |
| `invoice_facts` | One row per typed/scoped `invoice_key`; verified ERP `customer_key`; exact `sold_epoch`; signed decimal `net_cop` reconciled with returns; `sale_eligible` 0/1 from approved document mapping |

Epochs are integer UTC seconds converted only after confirmed source zones;
window end is owner-configured with **no production default**. Inputs must reject
bad types, duplicate keys, conflicting variants, unknown enum labels and missing
invoice net/time. No guessed timestamp from import/export time. If ERP exposes
only a date or midnight of unknown precision, flag `date_only` and exclude from
strict intra-day attribution; an owner-approved day-level sensitivity analysis
must stay separate. Missing ERP extract coverage makes the affected period
unmeasurable, not a no-sale. Cutoff is the minimum complete WCX/ERP watermark,
not wall-clock now. A null/noninteger cutoff must be rejected before execution.
Bind `cohort_start_epoch` and `cohort_end_epoch` explicitly, with start < end;
no default operational cohort exists. The SELECT keeps the entire input halo
in candidate competition but publishes only cases opened in this half-open cohort.
Cases without a valid opening instant cannot be assigned to a cohort and require
a separate upstream quality count; never silently assign them to the current run.

## 5. Conversation → sale and double-count protection

**Proposed conservative scenario, awaiting approval:**

- Start at first verified inbound customer message, not case creation/import.
  Use cohort `[start, end)` in UTC; case window `[opened, window_end)`.
- Exact reviewed identity plus sale time inside the window produces a candidate,
  not causal attribution. One invoice may contribute to only one case.
- If an invoice has candidates in multiple cases/sources, quarantine attribution
  for every affected case. Do not silently use last-touch/nearest advisor. This
  sacrifices coverage rather than inventing allocation; show excluded counts.
  Candidate competition includes all valid overlapping cases, including younger
  censored cases, not merely cases in the published cohort. Read an overlap halo
  before/after the cohort so boundary cases cannot steal an invoice unnoticed.
- Multiple unique invoices for one case count **one converted case**, and their
  signed retained values are summed once. Any shared invoice excludes the whole
  affected case in this conservative scenario; do not allocate its other invoices.
- A fully observed window is required even if a sale is seen early. Censored,
  invalid-time, unlinked, conflicting and ambiguous cases stay out of the rate
  denominator, but remain visible as coverage categories. Sales before the first
  customer message are not conversions.
- Net-positive evidence plus a declared loss is `outcome_conflict`, not a clean
  win or an automatically overwritten disposition. Reconcile before publishing.

`rate = SUM(converted_cases) / NULLIF(SUM(eligible_cases), 0)`.
Zero denominator means **unavailable**, never 0%. Also show all-case coverage,
identity coverage, mature coverage, exclusions and matched invoice/return coverage.
The template emits disjoint response/outcome/reason cells: **sum counts first**
for global or response-band rates; never average the per-cell `conversion_rate`
(which is conditional on outcome). Do not double count the same cohort across
runs or combine non-disjoint cohorts. This measures observed association only.

## 6. Advisor response versus closed sale

From D3 messages with accepted scoped identities, verified type/actor mapping,
confirmed timezone and valid `occurred_at`:

1. First inbound external customer **message** anchors the case. Notes, automation,
   system events and unknown actors/types are excluded, not inferred by `isAdmin`.
   D3 does not store an explicit visibility flag. A documented `source_type`
   mapping must distinguish external messages from internal notes using retained
   fields; an actor mapping alone is insufficient. If that distinction cannot be
   established, response metrics remain unavailable until a separately approved
   contract extension. A future adapter must test an internal agent note preceding
   a true external reply; D4 does not implement or claim coverage of that adapter.
2. Find the first human, externally visible agent reply strictly after that inbound
   and inside the observation window. Equal timestamps/unknown ordering are
   flagged for review, not a fabricated zero-second reply. Imported assignment
   `source_agent_id` is not necessarily the responding advisor; D3 does not store
   a verified message-level responder ID, so no advisor ranking is supported yet.
3. Compute elapsed seconds from those instants; no reply remains null. Keep
   never-replied and unmapped/missing-time counts distinct in a future adapter.
   Never substitute `created_at` or discard unanswered cases from coverage.
4. Proposed descriptive bands: ≤5, >5–30, >30–120, >120 minutes; unknown separate.
   These are sensitivity-analysis bins, not an approved SLA. Business-hours time
   requires an approved calendar and holidays; elapsed time is the only proposal.
5. Compare mature eligible conversion counts/rates by response band, with sample
   size and uncertainty. Stratify by period/channel/branch and advisor only when
   valid mappings exist; avoid tiny identifiable cells. Response must precede
   the matched sale for the “response before close” analysis; replies after the
   earliest matched sale belong to a separate reverse-order/confounded bucket.
   The generic template's bands do **not** enforce that temporal condition: its
   input adapter must null such `first_response_seconds` for that analysis and
   emit a separate exclusion count. Do not claim causality or advisor performance.

## 7. Lost sales by reason

A closed case or absent matched invoice is **not a lost sale**. Only a confirmed
WCX disposition or manually reviewed evidence can set `declared_outcome='lost'`.
`no_observed_sale`, censored, unlinked and declared loss remain separate outcomes.
Proposed owner-review taxonomy: `price`, `stock`, `delivery`, `payment`,
`no_follow_up`, `other`, `unknown`. Codes are not vendor enums; no mapping is
assumed. Keep `unknown` when reason is missing; require one primary reviewed
reason per case (secondary reasons, if needed, must not inflate totals).
No original free-text reasons may leave the local protected area.

Report `declared_lost_cases` by approved reason, coverage/outcome and reason
coverage, including censored/unlinked/ambiguous losses. The SELECT preserves
`declared_outcome` and `loss_reason` independently of its coverage/sale `outcome`;
it does not hide a declared loss when that case is ineligible for conversion.
Conflicts retain their declared reason and count separately. Do not label absent
evidence as `no_follow_up`.
Lost **revenue** is unavailable without a reviewed quotation amount/currency/IVA
basis and dedupe key; invoice averages are not a substitute. Taxonomy, SLA and
business conclusions need owner approval before measurement/publication.

## 8. Verification delivered and implementation gates

Synthetic fixture tests in `tests/platform/test_wcx_sales_design.py` execute the
actual metric SELECT in SQLite memory; only DB-API bind syntax is translated.
They do not import a DB adapter, load `.env`, touch WCX or call any service.
The test's fixture DDL/inserts are synthetic only, not production writes.
A read-only SQLite authorizer also rejects writes from the SELECT. This proves
the specified relational behavior, **not** PostgreSQL/MSSQL integration or schema
presence. Discovery and upstream normalization/semantic adapters are not executed.

```bash
PYTHONPATH=src TESTING=true AI_PROVIDER=grok \
  /home/yderf/Projects/depotru_database/.venv/bin/python -m pytest \
  tests/platform/test_wcx_sales_design.py -q
```

Initial RED: 18 failed because the metric template did not exist. Final results
and regression/lint gates are recorded in the PR after actual execution.

Future work (only after separate scope/authorization; no child cards created):

1. Confirm owner decisions below and field-only schema discovery; write synthetic
   RED tests for typed identity/phone/NIT disagreement and temporal bridge validity.
2. Review an adapter design at `src/depotru_integrations/wcx_sales.py` with fake
   per-thread DB collaborators; prove read-only/bound-query behavior and no fallback
   identity inference before implementing. Do not wire any existing public tool.
3. Add synthetic RED tests for actor/type/date precision, first reply, after-sale
   response, censoring/halo, return linkage and watermark incompleteness; only then
   implement approved normalization. Reuse D3, do not change its storage silently.
4. Reconcile local aggregate results independently against original sale/return
   totals and case counts; inspect coverage before any KPI publication. No raw
   customer data enters test fixtures, logs, repo, card or cloud.
5. Request a separate reviewed PR and explicit named authorization for any import,
   migration/write, production execution, merge, deployment or service change.

## 9. Decisions needed from the owner (hard gate)

- Confirm SmartBusiness master/crosswalk, typed NIT/DV semantics, historical phone
  evidence and approval/revocation roles; who can authorize local identified reads?
- Choose conversation eligibility, window length, start event, cohort/halo policy,
  net-retained versus gross-issued sale KPI, document allowlist, return/cancellation
  horizon, invoice uniqueness and date-only handling. Approve/revise conservative
  ambiguity exclusion versus another attribution model; no default is activated.
- Confirm WCX timezone and message/status/actor mappings, primary loss taxonomy,
  documented manual review process, response bands and business-hours definition.
- Confirm privacy/legal basis, local retention/deletion, access scope, audit,
  minimum aggregate cell size and whether advisor-level comparisons are permitted.

**No business decision above is inferred from D3 approval. D4 is handed to owner
review with these unresolved requirements; no implementation is authorized.**
