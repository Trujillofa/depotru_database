# Strategic Roadmap — Depotru Platform

> Updated 2026-07-09 for **v2.1.0 BI** + multi-module platform ambition.
> Supersedes older “Path A quick wins” framing (much of that is already shipped).

---

## Current state (shipped)

- Vanna multi-provider NL→SQL, Colombian formatting, recommended reports UI
- Weekly KPI board Q1–Q17 (cartera, presupuesto, cotización, inventory, OTIF, DIAN, contabilidad)
- Manager report + contabilidad economic PyG
- Presupuesto 2026 + H2 two-pot go-live; vendor attribution Asignado > Factura
- Magento related/cross-sell **export** from sales affinity
- MCP database server for agents
- **Phase 0 platform skeleton**: `depotru_kernel`, tool registry, `/v1` API, assistant stub, module scaffolds

## Three-plane reality

BI (this repo) ≠ Magento MSI stock ≠ b2c.smart-business feed.
Platform adapters bridge them; Magento never free-form queries MSSQL.

---

## Phases

### Phase 0 — Platform skeleton ✅ (in progress / landed)

- [x] Kernel: documents, money, attribution wrapper, audiences
- [x] Tool registry + public-safe builtins
- [x] Magento REST client stub + sellable qty
- [x] Affinity CSV contract v1.0.0
- [x] Modules scaffolds: bi, assistant, crm, wms, catalog
- [x] FastAPI `/v1` health, tools, assistant chat, affinity contract
- [ ] AIVanna routing extract (next foundation PR)
- [ ] Config package fold + CLI re-layer

### Phase 1 — Catalog bridge + Magento assistant alpha

- [x] E2E affinity → `apply_crosssell_merge_bulk` dry-run + remote validate (no writes)
- [x] Affinity **apply** on Magento (merge-only, 25+50 SKU batches; mostly already present)
- [ ] Magento `DepositoTrujillo_Assistant` widget → BFF
- [ ] Live sellable qty with production token (scoped)
- [ ] LLM tool-calling on top of registry (replace stub router)

### Phase 2 — CRM core

- [ ] Cotización opportunities service (Q12)
- [ ] Party resolution cédula ↔ tercero
- [ ] Portfolio / handoff APIs

### Phase 3 — WMS control tower

- [ ] Ops coverage / critical stock APIs (J3, not MSI)
- [ ] OTIF service
- [ ] Reorder candidates

### Phase 4 — Multi-channel depth

- [ ] Webhooks Magento → events
- [ ] Web vs store channel reconciliation
- [ ] WhatsApp on same tool registry (optional)

---

## Non-goals (near term)

- Replace b2c.smart-business inventory writer
- Full CRM SPA before APIs
- Public exposure of cost / cartera

---

## Docs

- `docs/PLATFORM.md` — package + API reference
- Sibling: `depositotrujillo.co` AGENTS.md + ERP sync runbooks
