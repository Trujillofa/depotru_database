# Minería de guías del asistente (`chat_log.jsonl`)

**Issue:** [Phase 3 / #65](https://github.com/Trujillofa/depotru_database/issues/65) (part C)
**CLI:** `depotru-mine-chat-guides`
**Code:** `business_analyzer.jobs.chat_log_guides`
**Script:** `scripts/analysis/mine_chat_log_guides.py`

Read-only analysis of the storefront assistant log. It does **not** change
assistant routing, reports, or SQL. It never talks to the database or an LLM.

The writer is `modules.assistant.logging.log_assistant_turn` (schema: `ts`,
`session_id`, `audience`, `locale`, `message` ≤500, `reply_preview` ≤200,
`tools_used`, `mode`, `guide_id`, `product_query`, `grounded`). Matching reuses
`modules.assistant.problem_guides.match_guide` plus a logged `guide_id` if
present. Default path: `data/assistant/chat_log.jsonl` (override with
`--log-path` or Settings `ASSISTANT_CHAT_LOG`). The directory `data/assistant/`
is gitignored.

## Privacy

The real log is **private**. Do not commit it. The miner redacts emails,
phones, document numbers (CC / NIT / cédula), long digit strings, and
API-key-like secrets (`xai-…`, `sk-…`). Output never includes `session_id`,
reply text, or raw personal data.

The **top-10 list of real unmatched questions** must be produced by running
this script against the private log on a machine that has it. Guides for those
real questions can be drafted afterwards. This repository only ships a
labelled **SYNTHETIC** fixture.

## How to run (synthetic, no real log)

```bash
PYTHONPATH=src python scripts/analysis/mine_chat_log_guides.py \
  --synthetic --output-dir /tmp/chat_guides_mining --draft

# or
depotru-mine-chat-guides --synthetic --output-dir /tmp/chat_guides_mining
```

Expect `SYNTHETIC:` in the Markdown/CSV. Inspect
`unmatched_question_clusters.md` / `.csv`. `--draft` writes
`borrador_guia_*.md` and `borrador_issue_*.md` only (never publishes a guide,
never opens a GitHub issue).

## How to run (private log)

```bash
PYTHONPATH=src python scripts/analysis/mine_chat_log_guides.py \
  --output-dir /tmp/chat_guides_mining --top 10
```

If the file is missing or empty, the command exits 0 and prints a clear
Spanish message. It does not invent questions.

## Draft guides

Use `--draft` or copy [problem-guide-template.md](problem-guide-template.md).
A human reviews the Spanish (Colombian) draft and, if it is useful, adds it
by hand to `src/modules/assistant/problem_guides.py`.
