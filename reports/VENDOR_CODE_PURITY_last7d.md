# Vendor code purity — last_7d_2026-07-03_2026-07-09 (2026-07-03 → 2026-07-09)

- **Material threshold:** $1.000.000
- **Handoff OK (Asignado 163 + Factura Huber):** $0
- **Findings:** 2 errors, 1 warnings

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
| error | 131 | multi_name | $13.952.092 | Code 131 (OLGA LUCIA TORRES) has material Factura names other than owner — CARLOS EFREY PASCUAS: $13,952,092 |
| error | 131 | wrong_home | $13.952.092 | CARLOS EFREY PASCUAS booked $13,952,092 on 131; home code is 003 — Factura=CARLOS EFREY PASCUAS |
| warn | 131 | sede | $13.952.092 | Code 131 has material sales outside preferred sede(s) FET — FED: $13,952,092 |
| info | 133 | merge_orphan | $82.600 | Code 133 still has sales $82,600; meta is merged into 162 |

## Sales by code (material names)

| Code | Owner (card) | Total | Top Factura names |
|------|--------------|------:|-------------------|
| 035 | OSCAR IVAN POLANIA GARCIA | $196.852.251 | OSCAR IVAN POLANIA GARCIA $186.975.707; HUBER SANTIAGO ENCISO $9.876.544 |
| 095 | DANIEL ENRIQUE CAICEDO | $173.389.655 | DANIEL ENRIQUE CAICEDO $173.285.456 |
| 116 | FELIPE RAMIREZ | $100.396.971 | FELIPE RAMIREZ $100.311.862 |
| 057 | ANDRES FELIPE VARGAS JOVEL | $93.336.704 | ANDRES FELIPE VARGAS JOVEL $93.316.686 |
| 163 | BETSY GUZMAN | $65.755.977 | BETSY GUZMAN $65.755.977 |
| 000 | SIN COMISION | $59.603.558 | SIN COMISION $24.921.185; LUIS ESTEBAN MEDINA $20.299.380; JAVIER ANDRES APACHE $7.956.717; DIANA PATRICIA CULMA $5.026.381 |
| 060 | YULI ALEJANDRA HIGUERA | $44.082.687 | YULI ALEJANDRA HIGUERA $44.082.687 |
| 089 | ANDRES MAURICIO CORTEZ CULMA | $43.405.233 | ANDRES MAURICIO CORTEZ CULMA $42.646.745; HUBER SANTIAGO ENCISO $414.478; LINA ISABEL TOVAR $277.930 |
| 106 | DIANA PATRICIA CULMA | $39.276.131 | DIANA PATRICIA CULMA $39.276.131 |
| 102 | JULIAN ANDRES PINEDA | $33.080.738 | JULIAN ANDRES PINEDA $33.080.738 |
| 003 | CARLOS EFREY PASCUAS | $27.411.792 | CARLOS EFREY PASCUAS $27.411.792 |
| 044 | HUBER SANTIAGO ENCISO | $24.735.191 | HUBER SANTIAGO ENCISO $24.735.191 |
| 140 | LUIS ESTEBAN MEDINA | $17.858.555 | LUIS ESTEBAN MEDINA $17.931.971 |
| 130 | JAVIER ANDRES APACHE | $15.431.973 | JAVIER ANDRES APACHE $15.431.973 |
| 131 | OLGA LUCIA TORRES | $13.973.522 | CARLOS EFREY PASCUAS $13.952.092 |
| 162 | WILLIAM HERNANDO QUINTERO G | $2.066.097 | CRISTIAN GUSTAVO $2.052.777 |
| 164 | CRISTIAN GUSTAVO | $1.561.242 | CRISTIAN GUSTAVO $1.561.242 |
| 156 |  | $916.365 | KERLY JOHANA CAICEDO $916.365 |
| 133 |  | $82.600 |  |
| 159 | LINA ISABEL TOVAR | $-104.042 |  |

## Merge orphans (123/133 → 162)

- **133:** $82.600

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
