# Send this today

Forward **`REQUEST-cloudflare-tunnel-owner.md`** to whoever owns the Cloudflare
login for `depositotrujillo.co` (DNS: `gail.ns` / `jack.ns.cloudflare.com`).

Ask for **Option A**: tunnel token only (preferred).

When the token arrives, on the ops host:

```bash
# in deploy/bff/env.bff
BFF_TUNNEL_MODE=named
CLOUDFLARE_TUNNEL_TOKEN='eyJ…'
BFF_SYNC_MAGENTO=1

systemctl --user daemon-reload
systemctl --user restart depotru-bff-tunnel
# then once Magento:
# config:set dt_assistant/general/base_url 'https://bff.depositotrujillo.co'
```

Until then: keep `depotru-bff-tunnel` on **quick** (already running) and Magento
`dt_assistant/general/base_url` synced to `deploy/bff/last_tunnel_url.txt`.
