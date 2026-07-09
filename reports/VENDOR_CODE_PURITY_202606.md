# Vendor code purity — 2026-06 (2026-06-01 → 2026-06-30)

- **Material threshold:** $1.000.000
- **Handoff OK (Asignado 163 + Factura Huber):** $-2.316.288
- **Findings:** 3 errors, 1 warnings

## Field one-pager (enforce this week)

| Code | Official owner | Rule |
|------|----------------|------|
| **044** | Huber Santiago Enciso | Own remaining book only; Daniel→**095**, Julian→**102** |
| **163** | Betsy Guzman | + credit from Huber; **Asignado 163** wins if Factura still says Huber |
| **131** | Olga Lucia Torres | Calle 5 (**FET**) only; Carlos→**003**, Diana→**106** |
| **162** | William H. Quintero | Sika; use **162** only (not 123/133) |
| 095 | Daniel | Do not book on 044 |
| 102 | Julian | Do not book on 044 |
| 003 | Carlos | Prefer 003 over 131 |
| 106 | Diana | Prefer 106 over 131 |

## Findings

| Sev | Code | Check | Sales | Message |
|-----|------|-------|------:|---------|
| error | 131 | multi_name | $33.348.793 | Code 131 (OLGA LUCIA TORRES) has material Factura names other than owner — CARLOS EFREY PASCUAS: $30,910,239, DIANA PATRICIA CULMA: $2,438,554 |
| error | 131 | wrong_home | $30.910.239 | CARLOS EFREY PASCUAS booked $30,910,239 on 131; home code is 003 — Factura=CARLOS EFREY PASCUAS |
| error | 131 | wrong_home | $2.438.554 | DIANA PATRICIA CULMA booked $2,438,554 on 131; home code is 106 — Factura=DIANA PATRICIA CULMA |
| warn | 131 | sede | $33.201.029 | Code 131 has material sales outside preferred sede(s) FET — FED: $33,201,029 |
| info | 123 | merge_orphan | $69.051 | Code 123 still has sales $69,051; meta is merged into 162 |
| info | 133 | merge_orphan | $247.800 | Code 133 still has sales $247,800; meta is merged into 162 |
| info | 163 | handoff_ok | $-2.316.288 | Huber→Betsy handoff pattern OK: Asignado 163 + Factura HUBER net $-2,316,288 (not a dual-code violation; negatives = returns/credit notes) |

## Sales by code (material names)

| Code | Owner (card) | Total | Top Factura names |
|------|--------------|------:|-------------------|
| 095 | DANIEL ENRIQUE CAICEDO | $565.246.796 | DANIEL ENRIQUE CAICEDO $537.654.194; FELIPE RAMIREZ $24.473.060; WILLIAM HERNANDO QUINTERO G $2.305.794; CRISTIAN GUSTAVO $813.748 |
| 035 | OSCAR IVAN POLANIA GARCIA | $538.931.608 | OSCAR IVAN POLANIA GARCIA $538.931.608 |
| 116 | FELIPE RAMIREZ | $460.322.127 | FELIPE RAMIREZ $454.612.030; CARLOS EFREY PASCUAS $2.691.892; DANIEL ENRIQUE CAICEDO $1.467.251; CALL CENTER $1.346.000 |
| 163 | BETSY GUZMAN | $250.641.163 | BETSY GUZMAN $252.957.451 |
| 000 | SIN COMISION | $228.941.470 | SIN COMISION $139.671.090; JAVIER ANDRES APACHE $34.254.312; DIANA PATRICIA CULMA $23.018.640; LUIS ESTEBAN MEDINA $21.126.860 |
| 106 | DIANA PATRICIA CULMA | $227.845.040 | DIANA PATRICIA CULMA $227.845.040 |
| 057 | ANDRES FELIPE VARGAS JOVEL | $180.070.646 | ANDRES FELIPE VARGAS JOVEL $180.070.646 |
| 003 | CARLOS EFREY PASCUAS | $173.655.149 | CARLOS EFREY PASCUAS $171.355.384; FELIPE RAMIREZ $2.213.405 |
| 089 | ANDRES MAURICIO CORTEZ CULMA | $156.143.249 | ANDRES MAURICIO CORTEZ CULMA $153.903.500; LINA ISABEL TOVAR $1.098.038; YULI ALEJANDRA HIGUERA $384.626; LUIS ESTEBAN MEDINA $223.192 |
| 044 | HUBER SANTIAGO ENCISO | $151.713.022 | HUBER SANTIAGO ENCISO $151.713.022 |
| 060 | YULI ALEJANDRA HIGUERA | $129.551.546 | YULI ALEJANDRA HIGUERA $125.648.471; KERLY JOHANA CAICEDO $3.732.975; ANDRES MAURICIO CORTEZ CULMA $170.100 |
| 140 | LUIS ESTEBAN MEDINA | $91.035.703 | LUIS ESTEBAN MEDINA $91.015.533 |
| 130 | JAVIER ANDRES APACHE | $67.659.228 | JAVIER ANDRES APACHE $67.659.228 |
| 102 | JULIAN ANDRES PINEDA | $59.231.205 | JULIAN ANDRES PINEDA $59.231.205 |
| 131 | OLGA LUCIA TORRES | $42.699.322 | CARLOS EFREY PASCUAS $30.910.239; OLGA LUCIA TORRES $9.350.529; DIANA PATRICIA CULMA $2.438.554 |
| 162 | WILLIAM HERNANDO QUINTERO G | $6.619.000 | WILLIAM HERNANDO QUINTERO G $4.248.866; CRISTIAN GUSTAVO $2.043.334; DANIEL ENRIQUE CAICEDO $326.800 |
| 159 | LINA ISABEL TOVAR | $2.351.546 | LINA ISABEL TOVAR $1.590.750; ANDRES MAURICIO CORTEZ CULMA $652.450 |
| 164 | CRISTIAN GUSTAVO | $340.946 | CRISTIAN GUSTAVO $340.946 |
| 133 |  | $247.800 | WILLIAM HERNANDO QUINTERO G $247.800 |
| 123 |  | $69.051 |  |

## Merge orphans (123/133 → 162)

- **123:** $69.051
- **133:** $247.800

## Enero 2026 presupuesto smoke

- **Codes with meta:** 18
- **Expected:** 18
- **Total meta (periodo 20261):** $8.352.209.815
- **Status:** OK


## Notes

- Purity is **read-only**; no ERP writes.
- Budget attribution: **Asignado > Factura owner > vendedor_codigo** (see `presupuesto_2026.attribute_sale`).
- Re-generate 2026 metas only after ~30 days of cleaner booking.

*Generated from live SmartBusiness analysis.*
