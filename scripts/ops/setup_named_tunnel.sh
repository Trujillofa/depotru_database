#!/usr/bin/env bash
# Create/configure a *named* Cloudflare tunnel for the Depotru BFF.
#
# Prerequisites:
#   A) Browser login once:  cloudflared tunnel login
#   OR
#   B) Paste a tunnel token from Zero Trust into deploy/bff/env.bff:
#        CLOUDFLARE_TUNNEL_TOKEN=eyJ...
#        BFF_TUNNEL_MODE=named
#
# Usage:
#   ./scripts/ops/setup_named_tunnel.sh [hostname]
#   Default hostname: bff.depositotrujillo.co
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CF="${CLOUDFLARED_BIN:-${REPO}/.tools/cloudflared}"
BFF_DIR="${REPO}/deploy/bff"
ENV_BFF="${BFF_DIR}/env.bff"
HOSTNAME="${1:-bff.depositotrujillo.co}"
TUNNEL_NAME="${BFF_TUNNEL_NAME:-depotru-bff}"
LOCAL_URL="http://127.0.0.1:${BFF_PORT:-8000}"

if [[ ! -x "${CF}" ]]; then
  echo "cloudflared missing at ${CF}" >&2
  exit 1
fi

mkdir -p "${BFF_DIR}" "${HOME}/.cloudflared"
[[ -f "${ENV_BFF}" ]] || cp "${BFF_DIR}/env.bff.example" "${ENV_BFF}"

# --- Path B: token already provided ---
if grep -qE '^CLOUDFLARE_TUNNEL_TOKEN=.+' "${ENV_BFF}" 2>/dev/null; then
  TOKEN="$(grep -E '^CLOUDFLARE_TUNNEL_TOKEN=' "${ENV_BFF}" | head -1 | cut -d= -f2-)"
  if [[ -n "${TOKEN}" && "${TOKEN}" != "eyJ..."* ]]; then
    echo "Found CLOUDFLARE_TUNNEL_TOKEN in env.bff — switching to named mode"
    # ensure mode
    if grep -q '^BFF_TUNNEL_MODE=' "${ENV_BFF}"; then
      sed -i 's/^BFF_TUNNEL_MODE=.*/BFF_TUNNEL_MODE=named/' "${ENV_BFF}"
    else
      echo "BFF_TUNNEL_MODE=named" >> "${ENV_BFF}"
    fi
    systemctl --user daemon-reload
    systemctl --user restart depotru-bff-tunnel.service
    echo "Tunnel service restarted in named mode."
    echo "Map public hostname in Cloudflare Zero Trust → your tunnel → Public Hostname:"
    echo "  ${HOSTNAME}  →  ${LOCAL_URL}"
    echo "Then set Magento once:"
    echo "  php bin/magento config:set dt_assistant/general/base_url 'https://${HOSTNAME}'"
    exit 0
  fi
fi

# --- Path A: cert.pem login ---
if [[ ! -f "${HOME}/.cloudflared/cert.pem" ]]; then
  echo "No ~/.cloudflared/cert.pem — starting browser login…"
  echo "Approve access in the browser window (or open the printed URL)."
  # Run login in background-ish: cloudflared blocks until approved
  "${CF}" tunnel login
fi

if [[ ! -f "${HOME}/.cloudflared/cert.pem" ]]; then
  echo "Login did not produce cert.pem. Aborting." >&2
  exit 2
fi

# Create tunnel if missing
if ! "${CF}" tunnel list 2>/dev/null | grep -q "${TUNNEL_NAME}"; then
  echo "Creating tunnel ${TUNNEL_NAME}…"
  "${CF}" tunnel create "${TUNNEL_NAME}"
else
  echo "Tunnel ${TUNNEL_NAME} already exists"
fi

TUNNEL_ID="$("${CF}" tunnel list -o json 2>/dev/null | python3 -c "
import json,sys
name='${TUNNEL_NAME}'
data=json.load(sys.stdin)
for t in data:
    if t.get('name')==name:
        print(t.get('id','')); break
" 2>/dev/null || true)"

if [[ -z "${TUNNEL_ID}" ]]; then
  # fallback parse table
  TUNNEL_ID="$("${CF}" tunnel list 2>/dev/null | awk -v n="${TUNNEL_NAME}" '$0 ~ n {print $1; exit}')"
fi

if [[ -z "${TUNNEL_ID}" ]]; then
  echo "Could not resolve tunnel id for ${TUNNEL_NAME}" >&2
  "${CF}" tunnel list || true
  exit 3
fi

echo "Tunnel ID: ${TUNNEL_ID}"

# Credentials file should exist after create
CRED="${HOME}/.cloudflared/${TUNNEL_ID}.json"
if [[ ! -f "${CRED}" ]]; then
  echo "Missing credentials file ${CRED}" >&2
  exit 4
fi

# config.yml for named tunnel
CONFIG="${HOME}/.cloudflared/config.yml"
cat > "${CONFIG}" <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${CRED}

ingress:
  - hostname: ${HOSTNAME}
    service: ${LOCAL_URL}
  - service: http_status:404
EOF
echo "Wrote ${CONFIG}"

# DNS route (requires hostname zone in same CF account)
echo "Routing DNS ${HOSTNAME} → tunnel…"
if "${CF}" tunnel route dns "${TUNNEL_NAME}" "${HOSTNAME}" 2>&1; then
  echo "DNS route OK"
else
  echo "WARN: DNS route failed — add a CNAME in Cloudflare DNS:"
  echo "  ${HOSTNAME}  CNAME  ${TUNNEL_ID}.cfargotunnel.com  (proxied)"
fi

# Switch systemd to named mode via token if we can generate one, else cloudflared tunnel run by name
# Token install is easier for systemd — try:
# cloudflared tunnel token <name>
TOKEN="$("${CF}" tunnel token "${TUNNEL_NAME}" 2>/dev/null || true)"
if [[ -n "${TOKEN}" ]]; then
  # upsert env.bff
  if grep -q '^CLOUDFLARE_TUNNEL_TOKEN=' "${ENV_BFF}"; then
    # use python to avoid sed special chars in token
    python3 - <<PY
from pathlib import Path
p = Path("${ENV_BFF}")
lines = p.read_text().splitlines()
out = []
seen_t = seen_m = False
for ln in lines:
    if ln.startswith("CLOUDFLARE_TUNNEL_TOKEN="):
        out.append("CLOUDFLARE_TUNNEL_TOKEN=${TOKEN}")
        seen_t = True
    elif ln.startswith("BFF_TUNNEL_MODE="):
        out.append("BFF_TUNNEL_MODE=named")
        seen_m = True
    else:
        out.append(ln)
if not seen_t:
    out.append("CLOUDFLARE_TUNNEL_TOKEN=${TOKEN}")
if not seen_m:
    out.append("BFF_TUNNEL_MODE=named")
p.write_text("\\n".join(out) + "\\n")
PY
  else
    {
      echo "CLOUDFLARE_TUNNEL_TOKEN=${TOKEN}"
      echo "BFF_TUNNEL_MODE=named"
    } >> "${ENV_BFF}"
  fi
  echo "Saved token + BFF_TUNNEL_MODE=named to env.bff"
else
  echo "WARN: could not fetch tunnel token; systemd unit may need ExecStart=cloudflared tunnel run ${TUNNEL_NAME}"
  # fallback unit override
  mkdir -p "${HOME}/.config/systemd/user/depotru-bff-tunnel.service.d"
  cat > "${HOME}/.config/systemd/user/depotru-bff-tunnel.service.d/named.conf" <<EOF
[Service]
Environment=
EnvironmentFile=-${REPO}/.env
EnvironmentFile=-${ENV_BFF}
ExecStart=
ExecStart=${CF} tunnel --config ${CONFIG} --no-autoupdate run ${TUNNEL_NAME}
EOF
fi

systemctl --user daemon-reload
systemctl --user restart depotru-bff.service
systemctl --user restart depotru-bff-tunnel.service

sleep 2
systemctl --user --no-pager --full status depotru-bff-tunnel | head -20 || true

echo ""
echo "Named tunnel setup complete."
echo "  Hostname: https://${HOSTNAME}"
echo "  Local:    ${LOCAL_URL}"
echo ""
echo "Magento (set once, if not auto-synced):"
echo "  php bin/magento config:set dt_assistant/general/base_url 'https://${HOSTNAME}'"
echo "  php bin/magento config:set dt_assistant/general/enabled 1"
echo "  php bin/magento cache:clean config full_page"
echo ""
echo "Test: curl -sS https://${HOSTNAME}/v1/health"
