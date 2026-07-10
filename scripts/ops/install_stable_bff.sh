#!/usr/bin/env bash
# Install user systemd units for Depotru BFF + public tunnel.
#
# Usage:
#   ./scripts/ops/install_stable_bff.sh
#   systemctl --user status depotru-bff depotru-bff-tunnel
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
BFF_DIR="${REPO}/deploy/bff"

mkdir -p "${UNIT_DIR}"
mkdir -p "${BFF_DIR}"

if [[ ! -f "${BFF_DIR}/env.bff" ]]; then
  cp "${BFF_DIR}/env.bff.example" "${BFF_DIR}/env.bff"
  echo "Created ${BFF_DIR}/env.bff — edit PLATFORM_API_KEYS / tunnel settings"
fi

# Ensure PLATFORM_API_KEYS present
if ! grep -q '^PLATFORM_API_KEYS=' "${BFF_DIR}/env.bff" 2>/dev/null; then
  echo "PLATFORM_API_KEYS=storefront-dt-assistant-2026:public" >> "${BFF_DIR}/env.bff"
fi

# Magento sync defaults for quick tunnel
if ! grep -q '^BFF_SYNC_MAGENTO=' "${BFF_DIR}/env.bff" 2>/dev/null; then
  cat >> "${BFF_DIR}/env.bff" <<EOF

BFF_TUNNEL_MODE=quick
BFF_SYNC_MAGENTO=1
MAGENTO_SSH_HOST=174.142.205.80
MAGENTO_SSH_USER=deptrujillob2c
MAGENTO_SSH_KEY=${HOME}/Projects/depositotrujillo.co/.ssh/id_rsa
MAGENTO_SSH_KEY_PASSPHRASE_FILE=${HOME}/Projects/depositotrujillo.co/.ssh/MAGENTO_SSH_KEY.txt
EOF
fi

install -m 644 "${BFF_DIR}/depotru-bff.service" "${UNIT_DIR}/depotru-bff.service"
install -m 644 "${BFF_DIR}/depotru-bff-tunnel.service" "${UNIT_DIR}/depotru-bff-tunnel.service"
chmod +x "${REPO}/scripts/ops/run_bff_tunnel.py"

# cloudflared binary
if [[ ! -x "${REPO}/.tools/cloudflared" ]]; then
  echo "Downloading cloudflared…"
  mkdir -p "${REPO}/.tools"
  curl -sSL -o "${REPO}/.tools/cloudflared" \
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
  chmod +x "${REPO}/.tools/cloudflared"
fi

systemctl --user daemon-reload
systemctl --user enable --now depotru-bff.service
systemctl --user enable --now depotru-bff-tunnel.service

# Linger already often on; ensure reboot survival
loginctl enable-linger "${USER}" 2>/dev/null || true

echo ""
echo "Installed:"
echo "  systemctl --user status depotru-bff"
echo "  systemctl --user status depotru-bff-tunnel"
echo "  journalctl --user -u depotru-bff -u depotru-bff-tunnel -f"
echo ""
echo "Stable hostname (recommended): set CLOUDFLARE_TUNNEL_TOKEN + BFF_TUNNEL_MODE=named in deploy/bff/env.bff"
echo "Quick mode: URL written to deploy/bff/last_tunnel_url.txt and Magento base_url auto-synced when possible."
