# Vendor code hygiene — duals & shared codes (044 / 131)

**As of:** 2026-07-09 (data through ~2026-07-08)
**Scope:** Sales `banco_datos`, excl. test docs `XY/AS/TS`
**Audience:** Comercial / facturación / TI

### Confirmed commercial ownership (2026-07-09)

| Code | Official owner | Notes |
|------|----------------|--------|
| **044** | **HUBER SANTIAGO ENCISO** | Huber’s **own** remaining activity |
| **163** | **BETSY GUZMAN** | Includes **credit customers Huber transferred to Betsy** |
| **131** | **OLGA LUCIA TORRES** | Olga / Calle 5 |

### Why 044 vs 163 looked confusing

**Huber gave his credit customers to Betsy** — a real portfolio handoff, not “Huber has two codes.”

| What you see in ERP | Correct reading |
|---------------------|-----------------|
| Asignado `163-BETSY…` + Factura often **HUBER** | Sale belongs to **Betsy** (transferred book); Factura name lagging |
| Code / Asignado **044** | **Huber’s** own remaining sales |
| 0% NIT overlap 044↔163 (2025 snapshot) | Separate books after handoff — **do not merge metas** |

**Budget rule:** **Asignado > Factura** so transferred credit stays on **163**, and is not yanked back to 044 by Factura “HUBER”.

### Budget attribution priority (locked)

1. **`VendedorAsignado`** leading code (`044-…`, `163-BETSY…`, `131-…`)
2. **`VendedorFactura`** → official owner map / name map (fallback when Asignado empty)
3. **`vendedor_codigo`**
4. POOL

Do **not** merge 044↔163 into one meta row.

---

## 1) Code **044** — deep dive

### Pattern
- Steady multi-name use all through 2025 (2–4 names/month).
- **2026-05 → 2026-07:** collapses to **almost only Huber** on 044 (~$152M Jun, ~$135M early Jul).
- Earlier 2026 H1 still had Daniel + Julian on 044.

### By invoice name (2025 + H1 2026 volume)

| Invoice name | 2025 | 2026 H1 | 2026 Jun | Role |
|--------------|-----:|--------:|---------:|------|
| DANIEL ENRIQUE CAICEDO | $382M | $127M | $0 | Should use **095** (not 044) |
| HUBER SANTIAGO ENCISO | $0 | $213M | **$152M** | **044 = Huber’s code**; Jun–Jul mostly Huber-only on 044 |
| JULIAN ANDRES PINEDA | $231M | $83M | $0 | Should use **102** (not 044) |
| FELIPE RAMIREZ | $20M | $10M | $0 | Should use **116** |

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

→ Historically multi-name on 044 (Daniel/Julian shared use). **Huber’s official code is 044**; large Factura-HUBER volume under **163** is the **transferred book to Betsy** (Asignado 163), not Huber’s second code.

### 044 vs other codes (2026 H1, by Factura name)

| Person | Home code | On home code | Also on 044 | Note |
|--------|-----------|-------------:|------------:|------|
| Huber | **044** | (see 044) | — | Own remaining book |
| Betsy | **163** | large | — | **Credit book from Huber**; Factura may still say Huber |
| Daniel | **095** | $4,094M | $127M | Should not use 044 |
| Julian | **102** | $886M | $83M | Should not use 044 |

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
| Olga | **131** | — | $50M | **Confirmed owner** of 131 (Calle 5) |
| Diana | **106** | $1,530M | $36M | Spillover; stop using 131 |

---

## 3) Ops hygiene checklist (recommended)

### Immediate (this week)

1. **044 = Huber’s remaining book only**
   - Daniel **095**, Julian **102** must not book on 044.
   - Huber’s own sales: Asignado `044-HUBER…`.

2. **163 = Betsy (credit book received from Huber)**
   - Transferred credit customers: Asignado **`163-BETSY…`** even if Factura still says Huber.
   - Do **not** reassign those rows to 044 by Factura name.

3. **131 = Olga only (Calle 5)**
   - Carlos FED → **003** only.
   - Diana → **106** only.
   - Asignado `131-OLGA…` on Olga’s invoices.

4. **Optional cleanup**
   - Update Factura name to **Betsy** on transferred accounts so screens match Asignado.

### Code ownership card (confirmed)

| Code | Official owner(s) | Allowed sedes | Notes |
|------|-------------------|---------------|--------|
| 095 | Daniel Enrique Caicedo | FED (+ minor FEF) | Do not use 044 for Daniel |
| **044** | **Huber Santiago Enciso** | FED | Huber’s **own** remaining book |
| **163** | **Betsy Guzman** | FED | **+ credit customers from Huber** |
| 102 | Julian Andres Pineda | FED | Prefer 102 over booking on 044 |
| 003 | Carlos Efrey Pascuas | FED | Prefer 003 (not 131) for Carlos |
| **131** | **Olga Lucia Torres** | **FET Calle 5** | Confirmed |
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
