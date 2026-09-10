#!/usr/bin/env bash
# Install user systemd timer for J3 → Magento list prices (venta × 1.19).
#
# Usage:
#   ./scripts/ops/install_website_price_timer.sh
#   systemctl --user status depotru-website-price.timer
#   journalctl --user -u depotru-website-price.service -n 50
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
ENV_FILE="${HOME}/.config/depotru/website-stock.env"
VENV_PY="${HOME}/Projects/depotru_database/.venv/bin/python"
if [[ ! -x "${VENV_PY}" ]]; then
  VENV_PY="${REPO}/.venv/bin/python"
fi

mkdir -p "${UNIT_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE} (install stock timer first, or create Magento SSH + DB env)." >&2
  exit 2
fi
if [[ ! -x "${VENV_PY}" ]]; then
  echo "Missing venv python: ${VENV_PY}" >&2
  exit 2
fi
if [[ ! -f "${REPO}/scripts/ops/run_website_price_sync.py" ]]; then
  echo "Missing price job in ${REPO}" >&2
  exit 2
fi

install -m 644 "${REPO}/deploy/systemd/depotru-website-price.service" \
  "${UNIT_DIR}/depotru-website-price.service"
install -m 644 "${REPO}/deploy/systemd/depotru-website-price.timer" \
  "${UNIT_DIR}/depotru-website-price.timer"

# WorkingDirectory must be this checkout (worktree or clone). Keep venv on main clone.
sed -i "s|^WorkingDirectory=.*|WorkingDirectory=${REPO}|" \
  "${UNIT_DIR}/depotru-website-price.service"
sed -i "s|^ExecStart=.*|ExecStart=${VENV_PY} scripts/ops/run_website_price_sync.py --apply|" \
  "${UNIT_DIR}/depotru-website-price.service"

systemctl --user daemon-reload
systemctl --user enable --now depotru-website-price.timer

echo ""
echo "Installed depotru-website-price.timer"
systemctl --user list-timers depotru-website-price.timer --no-pager || true
echo ""
echo "Manual run:"
echo "  systemctl --user start depotru-website-price.service"
echo "  journalctl --user -u depotru-website-price.service -n 40 --no-pager"
echo "  tail -5 ~/business_reports/website_price_sync.log"
