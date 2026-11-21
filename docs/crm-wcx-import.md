# WCX → CRM historical import — D3 design (owner-corrected revision)

**Status: design corrected per owner review (2026-11-21). No import,
migration apply, UI change or production access is authorized by this
document.** The real numbered migration and the idempotent importer live in
the **depotru-inbox** repo PR (branch from `master`, `sql/` numbered). This
repo keeps the design, the corrected count-only prototype and this reference
draft DDL. D4 remains blocked until the owner approves this revision.

## 1. Evidence and boundaries

The archive `~/wcx/wcx-chats-export-12mo.tar.gz` was opened locally, extracted only
to `~/wcx/raw/wcx-chats-export-12mo/` (directory mode `0700`), and each extracted
regular file was checked byte-for-byte by SHA-256 against its archive member.
No symlinks, hardlinks or special members were accepted. The original archive's
SHA-256 was unchanged before/after extraction:
`6a0a26af0b0efcbb264d9d85c6da485ddfcd96b4c473fc919121c382d178adbc`.
Existing originals, including `useful/`, were not modified. No record samples,
customer identifiers, names, message bodies or attachment URLs were sent to an
LLM. Only field names, types, aggregate counts and synthetic fixtures leave the
local machine. Any future local derived output belongs only in
`~/wcx/derived/` (`0700`), never this repo or a worktree.

Archive inventory: **33 members**, comprising 1 directory, 30 JSONL files and
2 JSON files (one metadata object and one top-level array). JSONL has two shapes:

- Inventory rows: flat case objects containing `id`, `idCustomer`, `code`,
  `date_create`, `status`, etc. These are NOT another set of cases to import.
- Detail envelopes: `{id, code, detail, movements, exportedAt}`. `detail` contains
  `id`, `idCustomer`, `customerPhone`, `customerName`, `dateCreated`, `dateUpdated`,
  `status`, `origin`, `assignedAgent`, etc. `movements` is a list, not a page object.
- Movement fields include `id`, `idTicket`, `typeMov`, `contentText`, `content`,
  `dateValue`, `dateReference`, `isAdmin`, `isOwner`, `isAutomation`,
  `lstAttachment`, and nested `from`, `user`, `detailParent`, `transAudio`.
  The nested `detailParent` is NOT recursively imported as another case.
- All detail dates observed use `YYYY-MM-DD HH:MM:SS`, with **no timezone offset**.
  All 301,597 non-null `dateValue` strings share that format. `dateReference`
  also contains other display formats: it is not the authoritative timestamp.
  **Owner decision: the source timezone is `America/Bogota`.**

### Initial-message rule (owner-verified correction)

The previous revision classified 14,399 movements as «wrong case» because their
`idTicket` (0) differed from the envelope ID. The owner verified against the
vendor data that these are **the first movement of every envelope**, with
`typeMov = 8` and `id` equal to the envelope (case) ID: it is the customer's
initial message. An independent local probe confirmed: 14,399 envelopes each
have their movement at position 0 with `idTicket = 0`, `typeMov = 8` and
`id = envelope.id`; the 1,154 remaining `idTicket = 0` entries have `typeMov = 0`,
sit at non-first positions and carry no positive movement ID; there are **zero**
movements with a non-zero `idTicket` pointing at a different case.

**Rule: a movement with `idTicket == 0` belongs to its envelope when
`id == envelope.id` OR it is the first movement of the envelope.** Anything else
with a mismatched case reference is quarantined (currently an empty category).
The regression was written RED-first with synthetic fixtures of that exact shape.

### Count-only baseline (corrected offline scan)

Counts are observations, not approved import eligibility or semantic message totals.

| Measure | Count |
|---|---:|
| JSONL rows | 28,798 |
| Inventory rows | 14,399 |
| Detail envelopes | 14,399 |
| Unique source case IDs | 14,336 |
| Repeated identical case details | 63 |
| Case detail conflicts | 0 |
| Unique positive source customer IDs | 7,948 |
| Envelopes without a positive customer ID | 2 |
| Envelopes with accepted Colombian phone candidate | 11,127 |
| Envelopes without accepted Colombian phone candidate | 3,272 |
| Unique phone candidates attached to positive customer IDs | 6,826 |
| Phone candidates shared by multiple source customers | 4 |
| Source customers with multiple phone candidates | 0 |
| Movement list entries | 302,751 |
| Entries without positive movement ID (kept only in `raw`) | 1,154 |
| Entries accepted via the initial-customer rule (`idTicket=0`) | 14,399 |
| Entries with a non-zero `idTicket` pointing elsewhere | 0 |
| Unique accepted `(source, case ID, movement ID)` keys | 301,136 |
| Identical duplicate accepted movements | 461 |
| Conflicting accepted movement keys | 0 |
| Entries containing attachment metadata (before dedupe) | 11,535 |

Reconciliation: 302,751 entries = 301,136 unique accepted + 461 identical
duplicates + 1,154 without positive ID. The previous 14,399-entry «wrong case»
quarantine is empty under the corrected rule; those entries are now accepted
as each case's initial customer message. Of the 14,399 accepted initial
messages, 63 are identical repeats of already-seen envelopes and are counted
as duplicates. The 1,154 no-ID entries are not lost: **the complete original
envelope JSON is stored in `wcx_cases.raw`**, so they remain reviewable.
All 301,136 accepted entries are **movement candidates**, including potentially
notes/system events, not a claim that every entry is a WhatsApp chat message.
No channel/status enum meaning is inferred from numeric values.

## 2. Storage (PostgreSQL, inbox-owned)

The **real migration** is a numbered `sql/` file in the depotru-inbox repo
PR, reviewed there with the importer and integration tests. The DDL below
(`drafts/crm-wcx-import.sql`) remains an inert reference draft in this repo:
it aborts before DDL and ends with `ROLLBACK`; it is never applied. No schema
change belongs in MSSQL or Magento.

### `wcx_customers`

One row per source customer identity; **never merge by display name or phone**.
There is **no `contact_id` and no `link_state`**: the inbox link is resolved
in read time by normalized phone (section 3).

| Column(s) | PostgreSQL type | Meaning |
|---|---|---|
| `source` | text | Stable account namespace, not archive name/month; lowercase token |
| `source_customer_id` | bigint | Positive WCX customer ID; PK with source |
| `phone_e164` | text nullable | Conservative `+57` candidate; not identity evidence |
| `phone_shared` | boolean NOT NULL default false | True when the same phone candidate is attached to several source customers; such rows are displayed as «compartido» and **never merged** |
| `display_name` | text nullable | Historical name, never overwrites inbox name |
| `source_fingerprint` | bytea | 32-byte canonical source customer projection hash |
| `first_batch_sha256`, `last_batch_sha256` | bytea | Archive provenance, each 32 bytes |
| `imported_at`, `last_seen_at` | timestamptz | Import bookkeeping, not historical event times |

Indexes: PK `(source, source_customer_id)`; partial nonunique index on
`phone_e164`. Shared phones intentionally preserve the observed ambiguity:
four phone candidates are flagged `phone_shared` and no automatic link is
created for them.

### `wcx_cases`

| Column(s) | PostgreSQL type | Meaning |
|---|---|---|
| `source`, `source_case_id` | text, bigint | Composite PK, positive case ID |
| `source_customer_id` | bigint nullable | Composite FK with source; null for unresolved identities |
| `source_code`, `subject` | text nullable | Historical reference and title |
| `source_status`, `source_channel` | integer nullable | Preserve numeric `status`/`origin`, no invented labels |
| `source_agent_id` | bigint nullable | Historical assignment, NOT inbox `agents.id` |
| `created_local`, `updated_local` | timestamp nullable | Strictly parsed WCX local timestamps |
| `source_timezone` | text NOT NULL default 'America/Bogota' | Owner-confirmed zone; CHECK pins the value |
| `created_at`, `updated_at` | timestamptz nullable | Local timestamps converted at `America/Bogota` |
| `raw` | jsonb NOT NULL | **Complete original envelope JSON**, including the 1,154 no-ID movement entries; nothing is lost |
| fingerprint, batch hashes, bookkeeping | same as customer | Row provenance |

Timeline index `(source, source_customer_id, created_local DESC, source_case_id DESC)`.
No FK to live `cases`, no new open ticket, no assignment, SLA or sales conversion
side effect. Cases without valid customer IDs are preserved unlinked, never
pooled into a fake customer ID `0`.

### `wcx_messages`

| Column(s) | PostgreSQL type | Meaning |
|---|---|---|
| `source`, `source_case_id`, `source_message_id` | text, bigint, bigint | Composite PK; source movement ID must be positive |
| `source`, `source_case_id` | composite FK | Belongs to exactly one historical case |
| `source_type` | integer nullable | Raw `typeMov`, mapping not approved |
| `actor` | text NOT NULL | Owner-approved mapping: `isAutomation` → `automation`; `isAdmin`/agent → `agent`; everything else → `customer` |
| `is_admin`, `is_owner`, `is_automation` | boolean nullable | Raw flags preserved exactly as exported |
| `body_text` | text nullable | `contentText`, never executed as HTML |
| `has_attachment` | boolean | Metadata placeholder only; no URL fetching |
| `occurred_local` | timestamp nullable | Strictly parsed `dateValue`, null on invalid/missing |
| `source_timezone` | text NOT NULL default 'America/Bogota' | Owner-confirmed zone |
| `occurred_at` | timestamptz nullable | Local timestamp converted at `America/Bogota` |
| fingerprint, batch hashes, bookkeeping | same as customer | Row provenance |

Timeline index `(source, source_case_id, occurred_at, source_message_id)`.
Unknown timestamps display as unknown, never substituted with import time. No
global unique constraint on movement ID until the vendor guarantees its scope.
WCX IDs must not be assigned to inbox `wa_message_id`; those are Meta
identities with a different namespace. Participant emails, tokens and URL
query strings are not projected into queryable columns; they stay only inside
`wcx_cases.raw` (the lossless original), which is never rendered as HTML.

## 3. Phone normalization and the read-time inbox link

The Python normalizer accepts ASCII strings only, optional spaces/dashes and
one balanced parenthesis pair. Accepted forms are Colombian national 10-digit
mobile (`3…`) or current fixed-line (`601/602/604/605/606/607/608…`), optionally
prefixed with `57`, `+57` or `0057`. Output is `+57` plus 10 digits. Reject foreign
numbers, channel prefixes (`tg:`), extensions, multiple numbers, Unicode digits,
legacy dialing prefixes and malformed input. No guessed repairs.

This is conservative syntax validation, **not** proof of ownership, reachability,
WhatsApp membership or a specific person's identity.

Verified inbox source at `a2bff9bbf4cc44e0303588d752f6f6121b05e52d`:

- `sql/001_init.sql`: `contacts.id` is text, `contacts.phone` is text with a
  unique index on the stored string (not on a validated Colombian number).
- `lib/whatsapp/phone.ts::canonicalPhone` strips nondigits and prefixes `+`; it
  does **not** infer `+57` or validate Colombian numbers. The Python function is
  intentionally stricter; do not claim they are equivalent.
- `lib/whatsapp/neon-inbound-repo.ts` resolves existing contacts by exact phone.

**Owner decision: no stored link, no `contact_id`, no manual approval flow.**
The customer history view joins inbox contacts **in read time** by canonical
phone equality against `wcx_customers.phone_e164`:

1. Normalize WCX phone candidates at import time (stored, indexed).
2. At read time, canonicalize the inbox contact phone and select WCX customers
   with the same `phone_e164`.
3. Exactly one match → the history tab shows that customer's cases.
4. Multiple source customers share the phone (`phone_shared`) → the tab shows
   «teléfono compartido» and lists each source customer separately; histories
   are **never merged or interleaved**.
5. No match → no history tab. No auto-creation or overwriting of contacts, ERP
   customers, names or cases. Never resolve by name/email.

## 4. Dedupe and idempotent reimport contract

Namespace `source` must be the same approved WCX account token across exports,
never a filename/date. Different accounts use different tokens. Source identity
keys: customer `(source, customer ID)`, case `(source, case ID)`, movement
`(source, case ID, movement ID)`. Positive **integer** source IDs only; no bool,
float, coerced string, content-only key or order-based fallback.

Dedupe hashes canonical JSON (sorted keys, UTF-8, compact separators), comparing
case `detail` independently of export time and movement lists, and full
movement objects independently of the envelope. Equal key + equal hash is a
duplicate; each additional distinct hash for a key is one conflict. All observed
hash variants are retained in memory, so duplicate/conflict totals are
independent of row order. SHA-256 is for local comparison, **not anonymization**;
neither keys nor hashes are printed.

The **idempotent importer is implemented in the depotru-inbox repo PR** with
`--dry-run` (counts only) and a real mode, plus integration tests against a
local ephemeral PostgreSQL. Its contract:

- `--dry-run` performs zero writes and reports the same aggregate counts as
  this prototype; the real mode stages and publishes atomically in one
  transaction per source.
- Existing identical keys are no-ops except optional `last_seen_at` and last
  batch provenance. Existing changed keys abort/quarantine; never blanket
  `ON CONFLICT DO UPDATE`. Re-running the import changes nothing.
- The 1,154 no-ID movement entries survive inside `wcx_cases.raw`.
- Absent rows in a later partial export are not deletes. **Retention: keep
  everything** (owner rule). No deletion sync, send queue, webhook, analytics,
  automation or AI-training side effect.
- Abort on structural corruption; never print the failing line, filename,
  identifier or exception payload. Only aggregate error categories may escape.

## 5. Experience when a customer writes on WhatsApp

The existing inbound path continues creating/resolving its live case normally.
A **future**, feature-flagged, authenticated inbox view adds a separate tab:
**“Historial WCX (solo lectura)”**. It appears only when the read-time phone
join (section 3) resolves exactly one source customer, and for viewers
authorized to see that contact's history. No public BFF endpoint,
customer-facing replay or advisor/LLM context injection is enabled.

The tab lists historical cases newest first with source badge, historical
date (`America/Bogota`), subject and unmapped status shown as unknown until
approved mapping. Opening a case loads a bounded page of movements ordered by
timestamp and source ID, unknown dates last. Actor is derived from the
owner-approved flag mapping (`automation` / `agent` / `customer`); raw flags
remain available for audit. Render plain escaped text only; never `content`
HTML, scripts or remote images. An attachment displays “Adjunto histórico no
disponible”; no remote URL is loaded. A shared phone displays «teléfono
compartido» with separate, unmerged per-customer histories. Unlinking never
changes the live conversation; a phone change simply stops resolving the tab.

This design contains no inbox UI patch; the depotru-inbox PR ships only the
migration, importer and tests. Role/group visibility for the future tab
remains an owner gate before any UI work.

## 6. Executable count-only prototype and verification

From this repo, with no `.env`, SQL driver or network dependency:

```bash
PYTHONPATH=src python3 -m depotru_integrations.wcx_import \
  --dry-run --source wcx-primary \
  --input "$HOME/wcx/raw/wcx-chats-export-12mo"
```

`wcx-primary` is a **provisional** namespace for counting, not an approved
production account mapping. `--dry-run` is mandatory; there is no `--apply`, DB
connection, network call, output file or import-time configuration loading.
The command only opens local JSONL files for reading and prints integer aggregate
counts. It rejects symlinks, empty input, malformed envelopes and invalid case
identities. Inventory-only input is not evidence of import readiness. Source
files are streamed one row at a time; sets/hashes grow with unique identities,
so resource requirements must be re-estimated for larger exports.

```bash
PYTHONPATH=src TESTING=true AI_PROVIDER=ollama \
  /home/yderf/Projects/depotru_database/.venv/bin/python -m pytest \
  tests/platform/test_wcx_import.py -q
```

Original verification: RED before implementation (module missing), 41/41
after independent review fixes, `tests/platform` 346/346, scoped pre-commit
passed including mypy and gitleaks. **Correction round (this PR):** the
owner-verified initial-message rule was written RED-first — 3 new synthetic
fixtures of the exact shape (`idTicket=0`, `id=envelope.id`, first position,
`typeMov=8`) failed with `movements_wrong_case`/missing counter, then passed
after the rule change; the corrected offline scan of the real export produced
the counts in section 1 (reconciled: 301,136 + 461 + 1,154 = 302,751). No real
records are test fixtures. SQL is reviewed as inert text, never applied.

## 7. Owner decisions applied and remaining gates

Applied in this revision (owner review, 2026-11-21): initial-message counting
rule; no stored link/manual approval (read-time phone join; shared phones
flagged, never merged); `raw` jsonb lossless envelope; timezone
`America/Bogota`; actor mapping with preserved raw flags; keep-everything
retention; real migration + importer moved to depotru-inbox.

Still requiring the owner before any execution: review/merge of the
depotru-inbox PR (numbered migration, importer, integration tests), approval
of the production `source` namespace token, vendor channel/status/type enum
mappings for display, and a separate named authorization for any Neon/test or
production DB write, real import, migration apply, merge, deployment or
service change. Until then nothing is applied and D4 stays blocked.
