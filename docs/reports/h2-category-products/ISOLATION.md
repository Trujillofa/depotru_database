# Owner revision: isolate category snapshot from affinity

Scope: the single correction requested on PR #115 at `f077587`.
No changes to the approved category tool, ranking, document codes or price shape.

## Behavior

- `cross_sell_affinity.py` is now identical to the PR's `origin/main` base: no
  snapshot parameter, computation, publication or failure coupling remains.
- The repo wrapper logs affinity `ok (intento ...)` first, then invokes
  `python -m business_analyzer.jobs.category_snapshot --category-snapshot PATH --apply`
  in a **separate process**.
- Snapshot failure logs `category_snapshot fail (rc=1)` independently, leaves the
  preceding affinity `ok` intact and returns **0**. No affinity retry is triggered.
- Snapshot CLI reports the exception type only (no connection/credential details).
  Dry-run remains default; atomic publication preserves the old file on failure.

## RED before fix

```sh
PYTHONPATH=src AI_PROVIDER=grok TESTING=true \
  /home/yderf/Projects/depotru_database/.venv/bin/python -m pytest \
  tests/platform/test_category_snapshot_isolation.py -q --tb=short
```

Ran before modifying implementation. **2 failed, exit 1**. In the failure branch,
`compute_category_snapshot` actually raises `TimeoutError` in the subprocess;
old code logs affinity failures on attempts 1/3, 2/3 and 3/3, exits **1** and never
logs affinity `ok`. The control branch also fails because no separate step exists.
Original output: [isolation-red.txt](isolation-red.txt).

## GREEN and local gates

Initial focused GREEN: **21 passed**, exit 0 ([isolation-green.txt](isolation-green.txt)).
Two additional unit tests then verify affinity writes without calling snapshot
and publication failure returning only its own error. Final full gates include
all **23** focused tests:

| Gate | Actual result |
| --- | --- |
| `tests/platform` standalone | **305 passed**, exit 0 |
| Full CI-safe pytest + coverage | **1689 passed, 4 skipped, 36 deselected**, exit 0 |
| black 23.12.1, exact CI args | **344 files unchanged**, exit 0 |
| isort 5.13.2, exact CI args | exit 0 |
| flake8 fatal / unused selectors | both **0**, exit 0 |
| flake8 advisory `--exit-zero` | exit 0; existing style warnings retained |
| Basic quick runner | **13 passed**, exit 0 |
| Seven CI coverage floors | all exit 0 |
| `bash -n`, `git diff --check` | exit 0 |

Reproducible runner with exact commands:
[run-isolation-gates.sh](run-isolation-gates.sh). Raw results:
`isolation-{versions,lint,platform,pytest,extra}.txt`.

Independent read-only review: **PASS**; reviewer reran **23** focused tests,
`bash -n` and `git diff f077587 --check`. No implementation edits by reviewer.
This is technical evidence, not owner approval or deployment authorization.

## Preserved boundaries

Only SELECTs in J3 when the owner later runs the standalone snapshot. No
production ports, databases, cron, env, services, migrations, first refresh,
merge or deployment touched. No inbox owner-case read. GitHub Actions is not an
acceptance gate per owner direction; local gates above are real executions.

Original tool RED and prior gates remain in this directory's README and logs;
this revision's outputs supersede their counts for the updated head.
