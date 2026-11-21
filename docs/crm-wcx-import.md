# WCX → CRM historical import — D3 design proposal

**Status: DRAFT / owner approval required. No import, migration, UI change or
production access is authorized by this document.** This PR ships a count-only
prototype, not a database importer. D4 remains blocked until the owner approves D3.

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
  Do not infer the source timezone from an export's generation time.

### Count-only baseline (one complete offline scan)

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
| Entries without positive movement ID | 1,154 |
| Positive-ID entries whose `idTicket` differs from envelope | 14,399 |
| Unique accepted `(source, case ID, movement ID)` keys | 286,800 |
| Identical duplicate accepted movements | 398 |
| Conflicting accepted movement keys | 0 |
| Entries containing attachment metadata (before dedupe) | 11,535 |

Reconciliation: movement entries are partitioned into no-ID, wrong-case,
unique accepted, identical duplicate and conflicting-key counts. A separate
local set-based verification checks the unique and duplicate totals. The
14,399 wrong-case entries must remain quarantined pending vendor/owner mapping;
they must NOT be silently reassigned to the envelope. No-ID entries also remain
outside `wcx_messages`; their future identity/classification requires a decision.
All 286,800 accepted entries are **movement candidates**, including potentially
notes/system events, not a claim that every entry is a WhatsApp chat message.
No channel/status/actor enum meaning is inferred from numeric values.

## 2. Proposed storage (PostgreSQL, inbox-owned)

Draft DDL: [`drafts/crm-wcx-import.sql`](drafts/crm-wcx-import.sql). It is deliberately
outside `data/sql/` and the inbox's numbered `sql/` migration harness. It aborts
before DDL and ends with `ROLLBACK`; **never applied or tested against a DB**.
A future approved migration must be a new reviewed artifact in the inbox repo,
not execution of this draft. No schema change belongs in MSSQL or Magento.

### `wcx_customers`

One row per source customer identity; **never merge by display name or phone**.

| Column(s) | PostgreSQL type | Meaning |
|---|---|---|
| `source` | text | Stable account namespace, not archive name/month; lowercase token |
| `source_customer_id` | bigint | Positive WCX customer ID; PK with source |
| `phone_e164` | text nullable | Conservative `+57` candidate; not identity evidence |
| `display_name` | text nullable | Historical name, never overwrites inbox name |
| `contact_id` | text nullable | FK to inbox `contacts.id`, `ON DELETE SET NULL` |
| `link_state` | text | `unreviewed`, `ambiguous`, `approved`, `rejected` |
| `source_fingerprint` | bytea | 32-byte canonical source customer projection hash |
| `first_batch_sha256`, `last_batch_sha256` | bytea | Archive provenance, each 32 bytes |
| `imported_at`, `last_seen_at` | timestamptz | Import bookkeeping, not historical event times |

Indexes: PK `(source, source_customer_id)`; partial nonunique index on
`phone_e164`; partial unique indexes on `(source, contact_id)` and
`(source, phone_e164)` for linked rows. Unlinked duplicate phones intentionally
preserve the observed shared-phone ambiguity. A non-null contact link requires
`approved` and a non-null phone. Uniqueness prevents duplicate approved links
per source but cannot prove ownership or detect ambiguous unlinked candidates.
Contact deletion unlinks, but retention/deletion of historical content is an
owner/legal policy gate, not permission to retain indefinitely.

### `wcx_cases`

| Column(s) | PostgreSQL type | Meaning |
|---|---|---|
| `source`, `source_case_id` | text, bigint | Composite PK, positive case ID |
| `source_customer_id` | bigint nullable | Composite FK with source; null for unresolved identities |
| `source_code`, `subject` | text nullable | Historical reference and title |
| `source_status`, `source_channel` | integer nullable | Preserve numeric `status`/`origin`, no invented labels |
| `source_agent_id` | bigint nullable | Historical assignment, NOT inbox `agents.id` |
| `created_local`, `updated_local` | timestamp nullable | Strictly parsed WCX local timestamps |
| `source_timezone` | text nullable | Owner-confirmed IANA zone only |
| `created_at`, `updated_at` | timestamptz nullable | Filled only after confirmed timezone conversion |
| fingerprint, batch hashes, bookkeeping | same as customer | Row provenance |

Timeline index `(source, source_customer_id, created_local DESC, source_case_id DESC)`.
No FK to live `cases`, no new open ticket, no assignment, SLA or sales conversion
side effect. Cases without valid customer IDs can be preserved unlinked, never
pooled into a fake customer ID `0`.

### `wcx_messages`

| Column(s) | PostgreSQL type | Meaning |
|---|---|---|
| `source`, `source_case_id`, `source_message_id` | text, bigint, bigint | Composite PK; source movement ID must be positive |
| `source`, `source_case_id` | composite FK | Belongs to exactly one historical case |
| `source_type` | integer nullable | Raw `typeMov`, mapping not approved |
| `actor` | text | `customer`, `agent`, `automation`, `system`, `unknown`; default unknown |
| `body_text` | text nullable | `contentText`, never executed as HTML |
| `has_attachment` | boolean | Metadata placeholder only; no URL fetching |
| `occurred_local` | timestamp nullable | Strictly parsed `dateValue`, null on invalid/missing |
| `source_timezone`, `occurred_at` | text, timestamptz nullable | Zone/conversion gate as above |
| fingerprint, batch hashes, bookkeeping | same as customer | Row provenance |

Timeline index `(source, source_case_id, occurred_local, source_message_id)`;
query explicitly sorts null dates last. Unknown timestamps display as unknown,
never substituted with import time. No global unique constraint on movement ID
until the vendor guarantees its scope. WCX IDs must not be assigned to inbox
`wa_message_id`; those are Meta identities with a different namespace.

Do not store entire raw envelopes, HTML, participant emails, tokens or URL
query strings in JSONB as a shortcut. Future customer projection is restricted
to source ID, canonical phone and historical display name. Multiple different
projections for one customer ID in a batch must be quarantined, not chosen by
file order. The prototype does not claim to resolve those attribute conflicts.

## 3. Phone normalization and inbox link

The Python normalizer accepts ASCII strings only, optional spaces/dashes and
one balanced parenthesis pair. Accepted forms are Colombian national 10-digit
mobile (`3…`) or current fixed-line (`601/602/604/605/606/607/608…`), optionally
prefixed with `57`, `+57` or `0057`. Output is `+57` plus 10 digits. Reject foreign
numbers, channel prefixes (`tg:`), extensions, multiple numbers, Unicode digits,
legacy dialing prefixes and malformed input. No guessed repairs.

This is conservative syntax validation, **not** proof of ownership, reachability,
WhatsApp membership or a specific person's identity. A recycled/shared number
must not expose another customer's history.

Verified inbox source at `a2bff9bbf4cc44e0303588d752f6f6121b05e52d`:

- `sql/001_init.sql`: `contacts.id` is text, `contacts.phone` is text with a unique
  index on the stored string (not on a validated Colombian number).
- `lib/whatsapp/phone.ts::canonicalPhone` strips nondigits and prefixes `+`; it
  does **not** infer `+57` or validate Colombian numbers. The Python function is
  intentionally stricter; do not claim they are equivalent.
- `lib/whatsapp/neon-inbound-repo.ts` resolves existing contacts by exact phone.
  This PR reads code only; it has not queried live contacts or verified matches.

Future linking procedure, OFF until approved:

1. Normalize WCX phone candidates locally. Keep invalid rows unlinked.
2. In a separately authorized process, derive candidates from inbox WhatsApp
   contacts with the same strict normalizer; do not rewrite `contacts.phone`
   and do not normalize Telegram identities into phone numbers.
3. Require one unambiguous source customer ↔ one unambiguous contact per phone.
   Multiple source customers, multiple contacts after normalization, missing
   contact, changed phone or rejected link produces no automatic link.
4. Proposed default: explicit owner-approved link review, with contact phone
   revalidation before display and an audit of approver/time/reason in the
   future implementation. That audit mechanism is not shipped here.
5. No auto-creation or overwriting of contacts, ERP customers, names or cases.
   Never resolve by name/email or expose unresolved candidate history to agents.

## 4. Dedupe and idempotent reimport contract

Namespace `source` must be the same approved WCX account token across exports,
never a filename/date. Different accounts use different tokens. Source identity
keys: customer `(source, customer ID)`, case `(source, case ID)`, movement
`(source, case ID, movement ID)`. Positive **integer** source IDs only; no bool,
float, coerced string, content-only key or order-based fallback.

The prototype hashes canonical JSON (sorted keys, UTF-8, compact separators),
comparing case `detail` independently of export time and movement lists, and
full movement objects independently of the envelope. Equal key + equal hash
is a duplicate; each additional distinct hash for a key is one conflict. All
observed hash variants are retained in memory, so duplicate/conflict totals
are independent of row order. A conflicted key is never eligible merely because
one of its versions was counted as the first unique observation. SHA-256 is for local
comparison, **not anonymization**; neither keys nor hashes are printed.
A changed nested `detailParent` can conservatively trigger a movement conflict;
this is preferable to silent mutation. The future minimal stored projection
needs a versioned canonicalizer and a separately reviewed revision mechanism.

Future writer, NOT present in this PR:

- Preflight the complete archive locally, verify batch SHA-256, parser version,
  account namespace, reconciliation counts and approved link policy.
- Quarantine invalid identities, mismatched case references and conflicting
  keys; do not resolve by latest shard or `exportedAt` (export time is not a
  business version). Preserve originals for later review.
- Stage an approved batch and publish atomically in one transaction with
  serialized per-source imports. Enforce unique keys in PostgreSQL; in-memory
  dedupe alone is not a concurrent import guarantee.
- Existing identical keys are no-ops except optional `last_seen_at` and last
  batch provenance. Existing changed keys abort/quarantine pending revision
  policy; never blanket `ON CONFLICT DO UPDATE`. Retry after rollback safely.
- Absent rows in a later partial export are not deletes. No deletion sync,
  send queue, webhook, analytics, automation or AI-training side effect.
- Abort on structural corruption; never print the failing line, filename,
  identifier or exception payload. Only aggregate error categories may escape.

## 5. Proposed experience when a customer writes on WhatsApp

The existing inbound path continues creating/resolving its live case normally.
A **future**, feature-flagged, authenticated inbox view adds a separate tab:
**“Historial WCX (solo lectura)”**. It appears only for approved, still-valid
links and viewers authorized to access that contact's history. No public BFF
endpoint, customer-facing replay or advisor/LLM context injection is enabled.

The tab lists historical cases newest first with source badge, historical date,
subject and unmapped status shown as unknown until approved mapping. Opening a
case loads a bounded page of movements ordered by local date and source ID,
with unknown dates last. Cross-case/cross-source ties have explicit stable ID
ordering. Actor stays “Sin clasificar” until vendor mapping is approved. Render
plain escaped text only; never `content` HTML, scripts or remote images. An
attachment displays “Adjunto histórico no disponible”; no remote URL is loaded.
A missing/conflicting link displays **“Historial no vinculado; requiere revisión”**
without previewing possible matches. Phone changes/revocation immediately hide
the tab. Unlinking never changes the live conversation.

This PR contains no inbox UI patch. Before implementation, owner approval must
specify role/group visibility (no cross-group leakage), retention/deletion,
audit, phone ownership/recycling handling and access revocation. Archive content
is historical untrusted input, never instructions to tools or the assistant.

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
so resource requirements must be re-evaluated for larger exports. Use only the
approved raw directory for real data; arbitrary temp input is for synthetic tests.

```bash
PYTHONPATH=src TESTING=true AI_PROVIDER=ollama \
  /home/yderf/Projects/depotru_database/.venv/bin/python -m pytest \
  tests/platform/test_wcx_import.py -q
```

RED was executed **before** the implementation: collection exited 2 with
`ModuleNotFoundError: depotru_integrations.wcx_import`. Initial GREEN: 34 synthetic
tests passed. Independent review then exposed ASCII-boundary, empty-input and
order-dependent conflict-count gaps: regression RED was 5 failed / 36 passed;
after correction the final targeted suite passed **41/41**, and the offline
`tests/platform` regression suite passed **346/346** (6 warnings). Scoped
`pre-commit run --files ...` passed, including mypy and gitleaks. Fixtures cover
strict phones, source/case-scoped identity,
duplicate vs conflict, reimport stability, no phone-based merging, quarantines,
malformed structures, mandatory dry-run, read-only input and sanitized errors.
No real records are test fixtures. SQL is reviewed as inert text, never applied;
DB transaction/concurrency, UI authorization, enum and timezone mappings remain
unimplemented acceptance gates, not implied test coverage. The draft CHECKs only
require timezone presence for converted times; the future writer must validate
the owner-approved IANA zone and verify local↔UTC correspondence. The DDL does
not itself enforce timezone policy, contact ownership, or inbox authorization.

## 7. Decisions required from the owner (before any implementation/apply)

1. Approve or revise this design and the stable WCX account namespace.
2. Confirm source timezone, vendor channel/status/type/actor mappings, and the
   meaning of mismatched-ticket/no-ID entries; do not silently discard history.
3. Approve strict phone policy and manual link review, shared/recycled number
   handling, contact changes and the future link audit mechanism.
4. Approve historical content scope, attachment exclusion, retention/deletion,
   lawful processing basis and authorized role/group visibility.
5. Approve a conflict/revision policy and the inbox-owned deployment path.
   A separate named authorization is required for any Neon/test/production DB
   write, real import, migration, merge, deployment or service change.

The requested deliverable is this design PR plus aggregate evidence. It does
not authorize execution. D3 stays awaiting the owner; D4 must not start yet.
