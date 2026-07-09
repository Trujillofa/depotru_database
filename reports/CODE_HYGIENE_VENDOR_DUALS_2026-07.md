# Vendor code hygiene — duals & shared codes (044 / 131)

**As of:** 2026-07-09 (data through ~2026-07-08)
**Scope:** Sales `banco_datos`, excl. test docs `XY/AS/TS`
**Audience:** Comercial / facturación / TI

### Confirmed commercial ownership (2026-07-09)

| Code | Official owner | Notes |
|------|----------------|--------|
| **044** | **HUBER SANTIAGO ENCISO** | Huber’s code (not 163) |
| **131** | **OLGA LUCIA TORRES** | Olga / Calle 5 |
| **163** | **BETSY GUZMAN** | Asignado label; Factura may show Huber — **Asignado wins for budget** |

### Budget attribution priority (locked)

1. **`VendedorAsignado`** leading code (`044-…`, `131-…`)
2. **`VendedorFactura`** → official owner map / name map
3. **`vendedor_codigo`**
4. POOL

Do **not** merge large duals into one meta row; fix process + attribution instead.

---

## 1) Code **044** — deep dive

### Pattern
- Steady multi-name use all through 2025 (2–4 names/month).
- **2026-05 → 2026-07:** collapses to **almost only Huber** on 044 (~$152M Jun, ~$135M early Jul).
- Earlier 2026 H1 still had Daniel + Julian on 044.

### By invoice name (2025 + H1 2026 volume)

| Invoice name | 2025 | 2026 H1 | 2026 Jun | Role |
|--------------|-----:|--------:|---------:|------|
| DANIEL ENRIQUE CAICEDO | $382M | $127M | $0 | Uses **095** as primary (~$4.1B H1) |
| HUBER SANTIAGO ENCISO | $0 | $213M | **$152M** | Uses **163** as primary (~$918M H1); **044 is secondary channel** |
| JULIAN ANDRES PINEDA | $231M | $83M | $0 | Uses **102** as primary (~$886M H1) |
| FELIPE RAMIREZ | $20M | $10M | $0 | Uses **116** as primary |

### By sede
- **FED** dominates (~$532M 2025 / ~$458M H1 2026).
- Negligible FEF/Sika on 044.

### Top customers on 044 (2026 H1)
| Customer | Invoiced as | Amount |
|----------|-------------|-------:|
| FERRECENTRO SVCT ZOMAC SAS | Daniel | $127M |
| LEIDY CATERINE ANDRADE GONZALEZ | Huber | $88M |
| LUIS ALBERTO PAREDES MUNOZ | Julian | $83M |
| FERRECENTRO SVCT ZOMAC SAS | Huber | $81M |
| LUIS ALBERTO PAREDES MUNOZ | Huber | $45M |

→ Same big accounts appear under **different invoice names** on code 044 → classic **shared commission/invoice code**, not a second ID for one rep.

### 044 vs primary (same person, 2026 H1)

| Person | Primary code | On primary | On 044 | Share on 044 |
|--------|--------------|----------:|-------:|-------------:|
| Daniel | **095** | $4,094M | $127M | ~3% of his named sales |
| Huber | **163** | $918M | $213M | ~19% of his named sales |
| Julian | **102** | $886M | $83M | ~9% of his named sales |

---

## 2) Code **131** — deep dive

### Pattern
- Continuous use every month 2025–2026.
- **Two stable users:** Carlos (rising on 131 in 2026) and Olga (stronger on Calle 5).
- Diana appears on 131 mainly 2026 H1 (~$36M) — spillover from **106**.

### By invoice name (2025 + H1 2026)

| Invoice name | 2025 | 2026 H1 | 2026 Jun | Role |
|--------------|-----:|--------:|---------:|------|
| CARLOS EFREY PASCUAS | $139M | **$168M** | $31M | Primary **003** (~$1.16B H1) |
| OLGA LUCIA TORRES | **$235M** | $50M | $9M | **Only material home is 131** (Calle 5) |
| EDILBERTO ESQUIVEL RUBIO | $55M | $0 | $0 | **Left** (no 2026) |
| DIANA PATRICIA CULMA | $1M | $36M | $2M | Primary **106** (~$1.53B H1) |

### By sede (critical)
| Sede | 2025 | 2026 H1 | 2026 Jun | Who |
|------|-----:|--------:|---------:|-----|
| **FED** Principal | $76M | **$206M** | $33M | Mostly **Carlos** (+ Diana spillover) |
| **FET** Calle 5 | **$192M** | $53M | $10M | Mostly **Olga** |

### Top customers on 131 (2026 H1)
| Customer | Invoiced as | Amount |
|----------|-------------|-------:|
| DEPOSITO EL PUNTO DE LA CONSTRUCCION | **Carlos** | $168M |
| QN INGENIERIA S.A.S | Diana | $36M |
| DEPOSITO EL PUNTO… / piscícolas / etc. | **Olga** | $11–21M each |

### 131 vs primary (2026 H1)

| Person | Primary | On primary | On 131 | Note |
|--------|---------|----------:|-------:|------|
| Carlos | **003** | $1,157M | $168M | ~13% of named sales on 131 (almost all FED) |
| Olga | **131 only** | — | $50M | Needs **own clean code** or formal assignment to 131 |
| Diana | **106** | $1,530M | $36M | Spillover; stop using 131 |

---

## 3) Ops hygiene checklist (recommended)

### Immediate (this week)

1. **044 = Huber only**
   - Daniel **095**, Julian **102**, others must not book on 044.
   - Set **VendedorAsignado** = `044-HUBER…` (never 163 with Factura Huber for Huber’s own sales).

2. **131 = Olga only (Calle 5)**
   - Carlos FED → **003** only (never 131).
   - Diana → **106** only.
   - Asignado must be `131-OLGA…` on Olga’s invoices.

3. **163 = Betsy Guzman**
   - Keep separate from Huber/044.
   - Asignado should stay `163-BETSY…` when sales belong to Betsy.

4. **Stop “name on wrong code”**
   - Same customer (e.g. FERRECENTRO, EL PUNTO) should not bounce across codes without a reason.

### Code ownership card (confirmed)

| Code | Official owner(s) | Allowed sedes | Notes |
|------|-------------------|---------------|--------|
| 095 | Daniel Enrique Caicedo | FED (+ minor FEF) | Do not use 044 for Daniel |
| **044** | **Huber Santiago Enciso** | FED | **Huber’s official code** |
| 163 | Betsy Guzman | FED | Keep separate from Huber/044 |
| 102 | Julian Andres Pineda | FED | Prefer 102 over booking on 044 |
| 003 | Carlos Efrey Pascuas | FED | Prefer 003 (not 131) for Carlos |
| **131** | **Olga Lucia Torres** | **FET Calle 5** | Confirmed; Carlos should not use 131 |
| 000 | SIN COMISION / ops | — | Not a salesperson target |
| 162 | William H. Quintero (Sika) | FEF | 123/133 merged in presupuesto |

### Dead / ignore secondaries (no meta needed)
`002`, `110`, `118`, `129`, `126`, `132`, `134`, `135` — no material last-month activity.

### Already correct
- William: presupuesto merge **123 + 133 → 162**.

---

## 4) Impact on presupuesto (no change required now)

| Item | Guidance |
|------|----------|
| Merge 095↔044 or 003↔131? | **No** — 0% NIT overlap; mixed ownership |
| Meta on 044 ($0.8B/yr) | Optional later: reassign base by invoice name, or shrink 044 meta and lift 163/095/102 after hygiene |
| Meta on 131 ($2.7B/yr) | Under-performs H1 (~26% vs meta) partly because Olga volume fell and Carlos dual-books 003+131 — fix process first, then re-run generator |
| Scoreboard | Until hygiene, treat 044/131 cumplimiento as **noisy** |

---

## 5) Suggested next actions (after this note)

1. Comercial confirms **owner card** above (esp. Olga = 131?).
2. One-week pilot: ban multi-name use of 044.
3. Re-measure purity of 044/131 after 30 days.
4. Only then: optional presupuesto re-allocation for those two codes.

---

*Generated from live SmartBusiness analysis (dual-code study + 044/131 sede/name split).*
