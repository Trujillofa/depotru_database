# BFF deployment: how Magento reaches `b2b.quote`

The B2B pricing path is Magento → BFF (platform `/v1`) → ERP. This note records how
the BFF is actually published, what the Magento side must be set to, and how to
undo it. Verified live 2026-10-29 (transcript at the bottom).

## Why not `src/api.py`

`src/api.py` mounts the `/v1` router **next to** the BI endpoints, and those depend
on `business_analyzer.core.api_auth.require_api_key`, which returns without
checking anything when `API_KEY` is unset:

```python
expected = os.getenv("API_KEY", "").strip()
if not expected:
    return
```

Publishing that app to reach one B2B tool would publish `/analysis/*` with it. Use
`apps.api.bff` instead — it mounts only `/v1` + `/healthz` and refuses to start
without a key→audience map that contains a `b2b` audience (R22).

## Run it

```
PLATFORM_API_KEYS="<b2b-key>:b2b,<other-key>:public" \
B2B_ERP_MODE=j3 \
DATABASE_ENV... \
  uvicorn apps.api.bff:create_app --factory --host 127.0.0.1 --port 8099
```

`B2B_ERP_MODE=j3` is mandatory: `J3CustomerQuoteClient.customer_quote()` raises
`ErpUnavailableError("b2b_erp_disabled")` without it, and the quote comes back as
`{"status": "unavailable", "reason": "erp_unavailable"}` — which looks exactly like
a network failure and is easy to misdiagnose.

Bind to loopback only; reachability is the proxy's job, not the app's.

## Publish it

Magento calls the BFF server-side over the public internet, so it needs a stable
HTTPS endpoint with a valid certificate (a `curl` default-verify client will not
accept a self-signed cert, and an ephemeral quick tunnel is worse than nothing —
the previous staging value was `https://enables-mrs-harris-chairs.trycloudflare.com`,
a URL that stopped existing).

Tailscale Funnel gives a public HTTPS endpoint with a real certificate:

```
sudo tailscale funnel --bg --https=443 http://127.0.0.1:8099
tailscale funnel status
sudo tailscale funnel --https=443 off      # to stop publishing
```

The node needs the `funnel` capability in the tailnet policy
(`tailscale status --json` → `Self.CapMap`).

Keep it alive with a user unit (and `loginctl enable-linger <user>`, or the service
dies when the last session closes):

```ini
[Unit]
Description=Depositotrujillo BFF (platform /v1 for Magento B2B)
After=network-online.target

[Service]
Type=simple
WorkingDirectory=/path/to/depotru_database
EnvironmentFile=/path/to/depotru_database/.env
EnvironmentFile=%h/.config/depotru-bff.env
Environment=PYTHONPATH=src
ExecStart=/path/to/depotru_database/.venv/bin/uvicorn apps.api.bff:create_app \
    --factory --host 127.0.0.1 --port 8099
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

`~/.config/depotru-bff.env` (mode 600) holds only:

```
PLATFORM_API_KEYS=<b2b-key>:b2b,<other-key>:public
B2B_ERP_MODE=j3
```

## Magento side

```
php bin/magento config:set b2b/bff/base_url https://<bff-host>
php bin/magento config:set b2b/bff/api_key <b2b-key>   # encrypted backend model
php bin/magento config:set b2b/bff/enabled 1
php bin/magento config:set b2b/bff/timeout_seconds 15  # clamped 3..30
php bin/magento cache:clean config
```

`b2b/bff/api_key` uses `Magento\Config\Model\Config\Backend\Encrypted`, so
`config:set` stores ciphertext and `B2bConfig::getApiKey()` returns the plaintext
(or `''` when the value cannot be decrypted — an undecryptable key fails closed,
never as ciphertext).

`b2b/general/enabled` cannot be set with `config:set`: the path is declared in
`config.xml` defaults and read by `FeatureFlags::isCompanyEnabled()`, but it has no
`system.xml` field and **no production caller** — it is a declared-but-unused flag.
Do not go hunting for it when a quote fails.

## Verify

Two assertions, in this order:

1. The key model works — a non-B2B key must be refused:

```
POST /v1/tools/call  {"name":"b2b.quote", ...}  X-API-Key: <public key>
→ 403 {"detail":"Audience public cannot use tool b2b.quote (scope=b2b_quote)"}
```

2. Magento's own client gets a price (script at `/tmp/bffprobe.php`, read-only):

```
{
  "bff_enabled": true,
  "base_url": "https://omarchy.tail65d80f.ts.net",
  "api_key_len": 39,
  "timeout_seconds": 15,
  "quote": {
    "status": "ok",
    "quote_reference": "B2B-20261029231420-E8D6A1A6",
    "terceros_id": "7710",
    "currency": "COP",
    "price_includes_iva": false,
    "lines": [{"sku": "0040120004", "qty": "1", "status": "ok",
               "unit_net_price": "2408.00", "line_total": "2408.00", "unit": "UND"}]
  }
}
```

`status: unavailable` + `reason: erp_unavailable` means the BFF answered but the
ERP call failed — check `B2B_ERP_MODE`, ERP reachability, and the BFF log. It does
**not** mean the transport is broken.

3. The customer path writes a real snapshot. `QuoteRequestService::request()` with
   the approved company's buyer (company 2, `customer_id` 128, site `neiva`) created
   `depotru_b2b_quote_snapshot` rows whose JSON holds the ERP price:

```
{"entity_id":3,"quote_reference":"B2B-20261029231718-DB6BFD5E","company_id":2,
 "customer_id":128,"site":"neiva","currency":"COP",
 "snapshot_json":{"lines":[{"sku":"0040120004","qty":"1",
                            "unit_net_price":"2408.00","line_total":"2408.00","unit":"UND"}]}}
```

Note what this path is and is not: there is **no quote total collector** in the
module — nothing rewrites cart prices from a quote. The flow is "customer asks for a
quote, Magento stores the snapshot", and the order still goes through the normal
checkout at list price until the ERP submit work (gated) lands. Do not expect the
storefront cart to show `2408.00`.


## Key rotation

1. Add the new key to `PLATFORM_API_KEYS` and restart the BFF.
2. `config:set b2b/bff/api_key <new>`, `cache:clean config`.
3. Verify with the probe, then drop the old key from `PLATFORM_API_KEYS` and restart.

Never reuse the storefront Assistant or `public` key for this path (R22).

## Rollback

```
php bin/magento config:set b2b/bff/enabled 0 && php bin/magento cache:clean config
sudo tailscale funnel --https=443 off
systemctl --user disable --now bff
```

With `b2b/bff/enabled = 0` the pricing path fails closed — carts keep list prices
and no quote is requested. That is the safe state, not an outage.

## Known gap

The endpoint verified above runs on a developer machine behind a funnel. That is
fine to prove the path and wrong for production: the pilot's price source must not
depend on a laptop. Before the production gate opens, run the same unit on an
always-on host (the Hetzner box already has the `funnel` capability) and repeat the
two assertions above.
