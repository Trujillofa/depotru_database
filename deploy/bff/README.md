# Stable Platform BFF

Keeps `/v1` (assistant tools) running across reboots and exposes it publicly for Magento.

## Architecture

```
systemd --user depotru-bff.service
    → uvicorn api:app :8000
systemd --user depotru-bff-tunnel.service
    → cloudflared
         named  → fixed hostname (CLOUDFLARE_TUNNEL_TOKEN)
         quick  → *.trycloudflare.com + optional Magento base_url sync
Magento ChatClient → https://…/v1/assistant/chat
```

## Install (this machine)

```bash
cd ~/Projects/depotru_database
./scripts/ops/install_stable_bff.sh
```

Requires:

- `.venv` with project deps
- `deploy/bff/env.bff` (created from example)
- Magento SSH key if `BFF_SYNC_MAGENTO=1` (quick mode)

## Named tunnel (stable hostname — preferred)

Requires Cloudflare login for the account that owns DNS (e.g. `depositotrujillo.co`).
Until you have access, use **quick tunnel** mode (default) — systemd keeps it up and
auto-syncs Magento `base_url` when the hostname changes.

### When you have Cloudflare access

**Dashboard token (easiest):**

1. Zero Trust → Networks → Tunnels → Create → Cloudflared connector → copy **token**
2. Public Hostname: `bff.depositotrujillo.co` → `http://127.0.0.1:8000`
3. Put in `deploy/bff/env.bff`:

```bash
BFF_TUNNEL_MODE=named
CLOUDFLARE_TUNNEL_TOKEN=eyJ...
```

4. Run:

```bash
./scripts/ops/setup_named_tunnel.sh bff.depositotrujillo.co
# or: systemctl --user restart depotru-bff-tunnel
```

5. Magento once: `config:set dt_assistant/general/base_url 'https://bff.depositotrujillo.co'`

**CLI alternative:** `cloudflared tunnel login` then
`./scripts/ops/setup_named_tunnel.sh bff.depositotrujillo.co`

## Quick tunnel (auto Magento sync)

Default after install. On each tunnel start, URL is written to
`deploy/bff/last_tunnel_url.txt` and Magento `dt_assistant/general/base_url` is updated over SSH.

```bash
systemctl --user restart depotru-bff depotru-bff-tunnel
cat deploy/bff/last_tunnel_url.txt
journalctl --user -u depotru-bff-tunnel -n 30 --no-pager
```

## Ops

```bash
systemctl --user status depotru-bff depotru-bff-tunnel
journalctl --user -u depotru-bff -f
curl -s http://127.0.0.1:8000/v1/health
```

Stop:

```bash
systemctl --user disable --now depotru-bff-tunnel depotru-bff
```

## Security

- Do not commit `deploy/bff/env.bff` or tunnel tokens.
- Use `PLATFORM_API_KEYS=…:public` for Magento only.
- Named tunnel + HTTPS hostname is production-grade; quick tunnel is for ops/dev continuity.
