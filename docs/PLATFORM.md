# Depotru Platform — Multi-Module Architecture

> Phase 0 skeleton (2026-07). Extends `depotru_database` BI into a shared spine for Magento assistant, CRM, WMS, and catalog.

## Three systems

| Plane | Role |
|-------|------|
| SmartBusiness + J3System (MSSQL) | Main BI / store sales / contabilidad |
| b2c.smart-business.app | ERP → Magento stock/price feed (do not replace blindly) |
| depositotrujillo.co (Magento) | B2C storefront + ops toolkit |

## Packages

```
src/depotru_kernel/          # documents, money, attribution, auth audiences
src/depotru_tools/           # capability registry + builtins
src/depotru_integrations/    # magento REST, affinity CSV contract
src/modules/{bi,assistant,crm,wms,catalog}/
src/apps/api/v1.py           # FastAPI /v1 routes
```

Legacy `business_analyzer` remains the bulk of BI implementation; modules grow services on top of the kernel.

## Stable BFF (production-style)

```bash
./scripts/ops/install_stable_bff.sh   # user systemd: depotru-bff + depotru-bff-tunnel
systemctl --user status depotru-bff depotru-bff-tunnel
cat deploy/bff/last_tunnel_url.txt    # current public URL (quick mode)
```

- **BFF** always on `:8000` (survives reboot with linger).
- **Tunnel**: quick mode auto-updates Magento `base_url` (hostname changes on restart).
- **Named tunnel** (fixed `bff.depositotrujillo.co`): needs Cloudflare account access →
  `./scripts/ops/setup_named_tunnel.sh` + `CLOUDFLARE_TUNNEL_TOKEN` (see `deploy/bff/README.md`).

## API v1

Run: `python src/api.py` → `http://localhost:8000`
Or systemd: `depotru-bff.service`

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/health` | Kernel + exclusions |
| `GET /v1/tools` | Tools allowed for audience |
| `POST /v1/tools/call` | Invoke a tool |
| `POST /v1/assistant/chat` | Storefront assistant BFF (tool stub) |
| `GET /v1/affinity/contract` | Versioned Magento CSV contract |

### Auth

- `API_KEY` + header `X-API-Key` (legacy shared key)
- Optional `X-Audience: public|customer|sales|warehouse|admin|service|agent`
- Or `PLATFORM_API_KEYS=pub:public,svc:service` (key→audience map)

**Storefront Magento proxy** should use a **public**-scoped key only:

```bash
export PLATFORM_API_KEYS="storefront-secret:public,ops-secret:service"
```

### Storefront assistant contract

Magento module `DepositoTrujillo_Assistant` (sibling repo) proxies:

```http
POST {BFF}/v1/assistant/chat
Content-Type: application/json
X-API-Key: <public-scoped key>
X-Audience: public

{"message":"¿dónde están las sedes?","session_id":null,"locale":"es_CO"}
```

Response:

```json
{"reply":"...","session_id":"...","tools_used":["info.branches"],"grounded":true,"mode":"stub_tools"}
```

Browser only calls same-origin `/assistant/chat/post` (form_key + message). API key never leaves Magento.

### Chat question log (JSONL)

Each `POST /v1/assistant/chat` appends one line (never fails the request):

```bash
# Path (override with ASSISTANT_CHAT_LOG)
data/assistant/chat_log.jsonl

# Recent questions without a matched problem guide
jq -r 'select(.guide_id == null) | .message' data/assistant/chat_log.jsonl | tail -50

# Top matched guides
jq -r '.guide_id // "none"' data/assistant/chat_log.jsonl | sort | uniq -c | sort -rn
```

Fields: `ts`, `session_id`, `message` (≤500), `reply_preview` (≤200), `tools_used`,
`guide_id`, `product_query`, `grounded`. No API keys or full tool payloads.

### Product deep links

When Magento REST search returns `url_key`, replies include PDP URLs:

`• Nombre del producto — https://www.depositotrujillo.co/{url_key}.html`

Env: `MAGENTO_STOREFRONT_URL` (preferred), `MAGENTO_BASE_URL`, optional
`MAGENTO_PRODUCT_URL_SUFFIX` (default `.html`). banco_datos fallback shows names only.

### Magento stock (optional)

```bash
export MAGENTO_BASE_URL=https://www.depositotrujillo.co
export MAGENTO_ACCESS_TOKEN=...
```

Enables live `inventory.sellable_qty` (MSI − SafetyStock policy).

## Affinity bridge

Contract version **1.0.0** — see `depotru_integrations.affinity.contract`.

Producer: `business_analyzer.analysis.magento_related_export`
Consumer (Magento repo): `scripts/catalog/apply_crosssell_merge_bulk.py`

### E2E dry-run

```bash
# Local export + Magento --dry-run (no DB writes)
PYTHONPATH=src python scripts/analysis/run_affinity_magento_e2e_dry_run.py \
  --affinity ~/business_reports/top_10_related_products_per_sku.csv \
  --output-dir data/export/affinity_e2e_dry_run \
  --limit-skus 50

# SSH validate SKUs on Magento (still no writes)
PYTHONPATH=src python scripts/analysis/run_affinity_magento_e2e_dry_run.py \
  --affinity ~/business_reports/top_10_related_products_per_sku.csv \
  --limit-skus 25 --validate-remote
```

Reports: `reports/AFFINITY_E2E_DRY_RUN_*.md`

## Next

1. Deploy + enable `DepositoTrujillo_Assistant` on Magento (BFF must be reachable from origin)
2. Live sellable qty (`MAGENTO_*` on BFF)
3. LLM tool-calling on assistant stub
4. CRM / WMS modules
5. Split `AIVanna` routing into tools

See also: `docs/ROADMAP.md`, sibling repo `depositotrujillo.co` `custom-modules/DepositoTrujillo/Assistant/`.
