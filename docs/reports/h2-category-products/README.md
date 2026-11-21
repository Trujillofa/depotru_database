# Local gates — H2 category products

Base: `origin/main` at `8a00b332d4e85a909767fa733c254d33d18bb623`.
Interpreter: `/home/yderf/Projects/depotru_database/.venv/bin/python` (3.12.12).
No project dependencies or production environments were modified.

## RED first

Before implementation:

```sh
$PY -m pytest tests/platform/test_catalog_category_products.py -q --tb=short
```

**Exit 1**, `1 failed`: `ToolNotFoundError: 'catalog.category_products'`.
Full original output: [red.txt](red.txt).

## Final GREEN

```sh
PYTHONPATH=src AI_PROVIDER=grok TESTING=true $PY -m pytest tests/platform/ -q --tb=short
```

**Exit 0: 301 passed**, 7 warnings. [platform.txt](platform.txt).

```sh
PYTHONPATH=src AI_PROVIDER=grok TESTING=true $PY -m pytest tests/ -v --tb=short \
  --cov=src --cov-report=xml --cov-report=term-missing \
  -m 'not requires_db and not requires_api'
```

**Exit 0: 1685 passed, 4 skipped, 36 deselected**, 27 warnings.
Full output: [pytest.txt](pytest.txt). New modules: nightly computation 90.24%,
snapshot reader/writer 88.73%, category browser 97.70% coverage.

The CI environment matters: an initial platform invocation inherited unsupported
`AI_PROVIDER=commandcode`, and a first full-suite invocation omitted
`PYTHONPATH=src`, breaking subprocess smoke imports. Corrected runner environment,
not code or expectations; the final full runs above passed. No tests were removed.

## Exact CI lint commands

```sh
$PY -m black --check --diff --extend-exclude '(src/business_analyzer/ai/training.py|tests/ai/test_stability.py|tests/test_metabase_connection.py)' src/ tests/ examples/
$PY -m isort --check-only --diff --skip-glob '*.backup' --skip-glob 'src/business_analyzer/ai/training.py' --skip-glob 'tests/ai/test_stability.py' --skip-glob 'tests/test_metabase_connection.py' src/ tests/ examples/
$PY -m flake8 src/ tests/ examples/ --exclude src/business_analyzer/analysis/customer_optimized.py --count --select=E9,F63,F7,F82 --show-source --statistics
$PY -m flake8 src/ tests/ examples/ --exclude src/business_analyzer/analysis/customer_optimized.py --count --select=F811,F841,F401 --show-source --statistics
$PY -m flake8 src/ tests/ examples/ --exclude src/business_analyzer/analysis/customer_optimized.py --count --exit-zero --statistics
bash -n deploy/run_cross_sell_affinity.sh
git diff --check
```

**All exit 0**. `black==23.12.1`, `isort==5.13.2`. Black: 343 files unchanged.
Both blocking flake8 passes report 0; the advisory `--exit-zero` pass retains
existing repository style warnings. Versions and full output: [lint.txt](lint.txt).

## Additional CI gates

```sh
PATH=/home/yderf/Projects/depotru_database/.venv/bin:$PATH \
  PYTHONPATH=src AI_PROVIDER=grok TESTING=true \
  $PY scripts/utils/run_tests.py --quick
$PY -m coverage report --include=src/business_analyzer/reports/monthly.py --fail-under=80 --show-missing
$PY -m coverage report --include=src/business_analyzer/reports/cartera_pdf.py --fail-under=80 --show-missing
$PY -m coverage report --include=src/business_analyzer/analysis/manager_report/queries.py --fail-under=80 --show-missing
$PY -m coverage report --include=src/business_analyzer/core/website_stock_magento_ssh.py --fail-under=80 --show-missing
$PY -m coverage report --include=src/business_analyzer/jobs/monday_cash_pack.py --fail-under=90 --show-missing
$PY -m coverage report --include=src/business_analyzer/jobs/akzonobel_core_lines.py --fail-under=90 --show-missing
$PY -m coverage report --include=src/business_analyzer/jobs/chat_log_guides.py --fail-under=90 --show-missing
```

**All exit 0**. The quick script shells out to bare `pytest`, so its PATH must
point to the tested virtualenv. Full output: [extra-gates.txt](extra-gates.txt).

## Independent review

Spec review: PASS. Quality review: APPROVED after correcting snapshot coverage
fallback, closed public-product validation and consistent padded-SKU handling.
Reviewer independently reran 45 focused and 301 platform tests. Parent verified
the final full-suite and exact CI lint results above after the last code edits.

No remote Actions success is claimed (owner reports GitHub billing prevents
Actions from running). No merge, deployment, service restart, production cron
change, production snapshot publication, migration or production DB write.
