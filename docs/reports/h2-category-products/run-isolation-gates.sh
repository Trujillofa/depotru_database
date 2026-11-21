#!/usr/bin/env bash
# Local-only verification; never invokes the production refresh wrapper.
set -eu
export PYTHONPATH=src AI_PROVIDER=grok TESTING=true
PY=/home/yderf/Projects/depotru_database/.venv/bin/python
export PATH="$(dirname "$PY"):$PATH"
OUT=docs/reports/h2-category-products
run() {
  name=$1
  shift
  printf '\n$ %s\n' "$*" >> "$OUT/isolation-$name.txt"
  set +e
  "$@" >> "$OUT/isolation-$name.txt" 2>&1
  rc=$?
  set -e
  printf '\nexit=%s\n' "$rc" >> "$OUT/isolation-$name.txt"
  printf '%s: exit=%s\n' "$name" "$rc"
  [ "$rc" -eq 0 ]
}
run versions "$PY" -m black --version
run versions "$PY" -m isort --version-number
run lint "$PY" -m black --check --diff --extend-exclude '(src/business_analyzer/ai/training.py|tests/ai/test_stability.py|tests/test_metabase_connection.py)' src/ tests/ examples/
run lint "$PY" -m isort --check-only --diff --skip-glob '*.backup' --skip-glob 'src/business_analyzer/ai/training.py' --skip-glob 'tests/ai/test_stability.py' --skip-glob 'tests/test_metabase_connection.py' src/ tests/ examples/
run lint "$PY" -m flake8 src/ tests/ examples/ --exclude src/business_analyzer/analysis/customer_optimized.py --count --select=E9,F63,F7,F82 --show-source --statistics
run lint "$PY" -m flake8 src/ tests/ examples/ --exclude src/business_analyzer/analysis/customer_optimized.py --count --select=F811,F841,F401 --show-source --statistics
run lint "$PY" -m flake8 src/ tests/ examples/ --exclude src/business_analyzer/analysis/customer_optimized.py --count --exit-zero --statistics
run platform "$PY" -m pytest tests/platform/ -q --tb=short
run pytest "$PY" -m pytest tests/ -v --tb=short --cov=src --cov-report=xml --cov-report=term-missing -m 'not requires_db and not requires_api'
run extra "$PY" scripts/utils/run_tests.py --quick
for module in reports/monthly reports/cartera_pdf analysis/manager_report/queries core/website_stock_magento_ssh jobs/monday_cash_pack jobs/akzonobel_core_lines jobs/chat_log_guides; do
  floor=80
  case "$module" in jobs/*) floor=90;; esac
  run extra "$PY" -m coverage report --include="src/business_analyzer/$module.py" --fail-under="$floor" --show-missing
done
run extra bash -n deploy/run_cross_sell_affinity.sh
run extra git diff --check
