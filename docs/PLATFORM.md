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

## API v1

Run: `python src/api.py` → `http://localhost:8000`

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

### Magento

```bash
export MAGENTO_BASE_URL=https://www.depositotrujillo.co
export MAGENTO_ACCESS_TOKEN=...
```

Enables live `inventory.sellable_qty` (MSI − SafetyStock policy).

## Affinity bridge

Contract version **1.0.0** — see `depotru_integrations.affinity.contract`.

Producer: `business_analyzer.analysis.magento_related_export`
Consumer (Magento repo): `scripts/catalog/apply_crosssell_merge_bulk.py`

## Next

1. Magento `DepositoTrujillo_Assistant` widget → `/v1/assistant/chat`
2. E2E affinity job dry-run → staging apply
3. CRM / WMS tool implementations
4. Split `AIVanna` routing into tools

See also: `docs/ROADMAP.md`, sibling repo `depositotrujillo.co`.
