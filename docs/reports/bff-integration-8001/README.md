# BFF :8001 → main integration evidence

## Scope and frozen inputs

- Base: `origin/main` = `02a73d32220ec0d99375394670abeecdf5b1dff7`.
- Integrated history: `origin/prod/advisor-bff-8001` = `7a4b1e9134dcc5b24adc78479f5f6e1068c26e0a` (including `28060f2`). This is a local merge commit on a new feature branch from main, not replacement of main with the production tree.
- Resolution hotspots: `src/depotru_tools/builtins.py`, `CHANGELOG.md`, `pyproject.toml`. Main-only assistant/session/catalog-first behavior, B2B customer quote/cartera and brand reports remain intact.
- No HTTP calls to :8000/:8001, listeners, service changes, deploy, cron activation, production DB writes or affinity job execution. The SELECT probe reaches the real J3 database; "local" describes execution, not a fake backend.

## Hybrid contract

Name search removes natural-language noise, normalizes accents, separates non-fraction slashes and retains numeric fractions. Phrase-first and token fallback obey the same material/dimension checks. Numeric tokens do not match SKU substrings. Explicit SKUs use equality (including alphabetic SKUs); dimensions/materials cannot rescue a match through SKU digits. Closed unit suffixes permit `50KG` and `50 KG` but not `150KG`.

The SQL builder and handler permit an **internal maximum of 40**, default **6**; 25 is honored. This PR changes no Inbox renderer: callers must retain six visible choices rather than render the internal candidate window. Brand/term suggestions remain distinct tools; no suggestion silently rewrites `quote_search`. Conversation-level confirmation and six-visible rendering are consumer contracts, not certified by this isolated backend probe.

`28060f2`/`7a4b1e9` are preserved: UTC `updated_at`, five-day freshness, env-file ordering and missing-J3-env guard. Wrapper, store and original affinity tests match the advisor tip. The only additional affinity behavior is canonical exclusion of noncommercial documents (`XY`, `AS`, `TS`, `YX`, `ISC`) in both live basket selection and materialization, required by main's platform rules. No materialized table was refreshed.

## Real regression comparison

See [all 40 comparisons](comparison.md) and [machine-readable catalog observations](results.json).

The original report's "80 queries" are **20 distinct queries × limits 6/25 × two baseline trees**. Those **80 real SELECT-only baseline invocations were rerun**, followed by **40 final integrated invocations**, with **zero errors** in each tree. Completed measurements recovered from the earlier attempt were retained rather than needlessly rerun. Raw probe snapshots remain local under `evidence/`; committed observations omit SQL/call arrays and contain no env/credentials or customer records. Dates and hashes identify the exact measured inputs.

All 20 queries are at least as good as the editorially preferred baseline for observed precision/coverage, with the following explicit count reduction:

- **`tubo pvc 1/2`, both limits: integrated 0; main 6/10; advisor 3/3.** All advisor hits were `SOLDADURA PVC PEGATUBO 1/256`, `TUBO PAVCO CPVC 1/2`, or `TUBO PAVCO CPVC 11/2`. None satisfies PVC + literal 1/2 + tube. This is an intentional fail-closed precision improvement, **not** improved recall or proof that J3 has no valid product. There is no demonstrated loss of a valid baseline candidate. Owner review should explicitly accept the lower count.
- `varilla 3/8`: integrated 3, not main's five (wrong 5/8 and 1/4 removed); matches advisor.
- `varilla 1/2`: integrated 3, not main's 6/10; matches advisor. Accessory relevance is not guaranteed by lexical matching.
- `cemento gris 50` preserves all three CEMEX matches, including compact `50KG`.
- Natural-language price noise, accent and slash cases now retain main's behavior while gaining advisor's wider window. No measured query has an identified precision/coverage regression against the better baseline. This is a bounded catalog comparison, not a relevance model or an end-to-end sales guarantee.

Measurements are sequential, not a transactionally frozen snapshot. Shared SKU price/IVA/line fields have **zero changes**; stock differs in **17 baseline–integrated case/SKU comparisons** (some repeated across limits and refs), consistent with live inventory drift. No claim of byte-for-byte stock equality is made. Typo `varila 3/8`, `impermeabilizante sika`, and `revestimiento` remain empty in this J3 path; storefront/suggestion tools are separate.

## Commands and results

Interpreter: `/home/yderf/Projects/depotru_database/.venv/bin/python` (Python 3.12.12). Run from the feature worktree.

```bash
# Snapshots extracted with git archive from the two frozen refs.
PYTHONPATH=src "$PYTHON" scripts/analysis/run_bff_search_regression.py \
  --source evidence/main --env-file "$EXISTING_J3_ENV" \
  --label main --output evidence/main-results.json
PYTHONPATH=src "$PYTHON" scripts/analysis/run_bff_search_regression.py \
  --source evidence/advisor --env-file "$EXISTING_J3_ENV" \
  --label advisor --output evidence/advisor-results.json
PYTHONPATH=src "$PYTHON" scripts/analysis/run_bff_search_regression.py \
  --source . --env-file "$EXISTING_J3_ENV" \
  --label integrated-final --output evidence/integrated-final-results.json
# 40 completed calls per tree, zero errors, exit 0.

python3 scripts/analysis/summarize_bff_search_regression.py \
  --output docs/reports/bff-integration-8001
# baseline_calls=80 integrated_calls=40 errors=0 shared_price_iva_changes=0

AI_PROVIDER=ollama PYTHONPATH=src "$PYTHON" -m pytest \
  tests/platform tests/analysis/test_affinity_engines.py \
  tests/analysis/test_affinity_mart.py -q --disable-warnings -p no:cacheprovider
# 267 passed, 6 warnings; exit 0 (262 platform + 5 analysis).

pre-commit run --files $(git diff --cached --name-only)
# trailing whitespace, EOF, large files, merge conflicts, debug statements,
# Black, isort, flake8, mypy, gitleaks: PASS; YAML skipped (no applicable files).

git diff --cached --check
# exit 0
```

The first suite inherited `AI_PROVIDER=commandcode`, unsupported by this app, and failed on import. Selecting supported `ollama` for fake-only tests resolved the environment failure without changing production config. Initial Black/isort runs reformatted files; reruns passed. The later exact-SKU fallback required updating a FakeDB's expected bound parameter tuple; no pricing/stock assertions were relaxed.

### RED/GREEN

The hybrid test was copied into each archived baseline tree and run there against the baseline's actual builtins/SQL:

```bash
(cd evidence/main && AI_PROVIDER=ollama PYTHONPATH=src "$PYTHON" -m pytest \
  tests/platform/test_hybrid_red.py -q --disable-warnings -p no:cacheprovider)
(cd evidence/advisor && AI_PROVIDER=ollama PYTHONPATH=src "$PYTHON" -m pytest \
  tests/platform/test_hybrid_red.py -q --disable-warnings -p no:cacheprovider)
# Each: 16 failed, 4 passed; exit 1.
# Includes 14 behavioral/limit failures and 2 missing-new-module failures.
```

Behavioral failures include accents/noise, fraction boundaries, PVC versus CPVC, numeric SKU leakage, exact SKU, wildcard literals and phrase-path bypass. They are not merely missing-module assertions. These logs are from the 20-test revision before the final alphabetic-SKU test was added. The final integrated suite exercises the added case too.

Canonical affinity exclusions were separately shown RED before the SQL fix: **2 failed**, including an actual SQLite materialization whose confidence was polluted by test baskets. Both are GREEN in the final suite. Tests execute only temporary SQLite writes, never J3/Neon writes.

## Review and remaining gates

Two bounded Codex/Hermes read-only rounds were performed. Round 1 found missing canonical document exclusions in imported affinity and loss of alphabetic SKU matching; both fixed with tests. Round 2: **PASS signed, no blocking findings**, verifying those fixes and preservation of `28060f2`/`7a4b1e9`. The reviewer inspected the 267-test log and three 40-case probe artifacts; it did not independently rerun them.

GitHub Actions billing is unavailable per the owner plan; local gates are the evidence. Storefront HTTP, actual affinity refresh, customer identity authorization against live systems, consumer conversation confirmation and renderer were not live-tested. This PR installs/activates nothing. Owner must separately approve merge and any later production switch with its own backup/rollback plan.
