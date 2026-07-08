# KPI Control Board (Weekly)

## 1) Control Header

- **Week (ISO):** 1
- **Date range:** 2024-12-01 to 2024-12-31
- **Prepared by:** Auto-generated (scripts/utils/generate_kpi_control_board.py)
- **Reviewed with:** Comercial / Compras / Operaciones / Finanzas

## 2) North-Star KPI Scorecard

| KPI | Formula | Baseline | Target | This Week | vs Baseline | Status |
|---|---|---:|---:|---:|---:|---|
| Margen Bruto % | `SUM(TotalSinIva-ValorCosto)/SUM(TotalSinIva)*100` | 12,38% | 13,38% | 12,27% | -0,11 pp | 🔴 |
| Ganancia Bruta ($) | `SUM(TotalSinIva-ValorCosto)` | $225.808.141 | $237.098.548 | $148.398.489 | -34,28% | 🔴 |
| Ticket Promedio ($) | `SUM(TotalMasIva)/COUNT(*)` | $263.288 | $276.452 | $300.288 | 14,05% | 🟢 |
| Concentración Top-10 Clientes % | `Facturación Top10 / Facturación Total * 100` | 18,14% | 16,14% | 18,14% | +0,00 pp | 🔴 |
| DSO (días) | `Cartera Total / (Ventas Netas / días periodo)` | 24 | 45 | 24 | -21 días | 🟢 |
| Cartera vencida >90d % | `SUM(vencido_90+120+360+superior)/Cartera*100` | 12,29% | 12,00% | 12,29% | +0,29 pp | 🟡 |
| Cumplimiento Presupuesto MTD % | `Ventas MTD / Meta prorrateada * 100` | 46,39% | 100,00% | 46,39% | -53,61 pp | 🔴 |
| Tasa Conversión Cotizaciones % | `Convertidas / Cotizaciones * 100` (J3System) | 24,84% | 30,00% | 24,84% | -5,16 pp | 🔴 |
| Días Cotización → Factura | `AVG(DATEDIFF)` post-cotización (J3System) | 0.8 | 7.0 | 0.8 | -6 días | 🟢 |

## 3) Diagnostic Cut (Where we win/lose)

### 3.1 Category/Subcategory
- **Top 5 by ganancia:**
  - PRODUCTOS SIKA / PRODUCTOS SIKA | Ganancia: $78.592.157 | Margen: 17,08%
  - CEMENTO GRIS / CEMENTO GRIS | Ganancia: $62.498.925 | Margen: 9,67%
  - ZINC / ZINC | Ganancia: $59.958.172 | Margen: 8,80%
  - HIERRO / HIERRO | Ganancia: $57.494.887 | Margen: 8,85%
  - TUBERIA Y ACCE PVC / TUBERIA Y ACCE PVC | Ganancia: $50.676.730 | Margen: 15,03%
- **Bottom 5 by margen:**
  - BOLSAS PLASTICAS / BOLSAS PLASTICAS | Margen: 0,00% | Ganancia: $0
  - TEJAS DE FIBROCEMENTO / TEJAS DE FIBROCEMENTO | Margen: 7,95% | Ganancia: $7.533.889
  - ZINC / ZINC | Margen: 8,80% | Ganancia: $59.958.172
  - HIERRO / HIERRO | Margen: 8,85% | Ganancia: $57.494.887
  - ACERO / ACERO | Margen: 8,87% | Ganancia: $4.540.597
- **Biggest WoW drop in margen:** completar con comparación semana anterior.

### 3.2 SKU Focus (High Volume + Low Margin)
- **Critical SKUs (ACCION_INMEDIATA / ACCION_ALTA):**
  - 0020390061 | CODO PRESION 90 1/2 T/PESADO | Volumen: 16,909 | Margen: 12,72% | Prioridad: ACCION_ALTA
  - 0020390214 | UNION  PRESION 1/2" T/PESADO | Volumen: 9,384 | Margen: 13,18% | Prioridad: ACCION_ALTA
  - 0020240030 | LONA CERRAMIENTO | Volumen: 9,158 | Margen: 13,28% | Prioridad: ACCION_ALTA
  - 0020390025 | ADAPTADOR MACHO 1/2" T/PESADO | Volumen: 6,660 | Margen: 12,65% | Prioridad: ACCION_ALTA
  - 0020240012 | TELA PROTECPLAST BLANCA X MT X 2.0 ANCHO | Volumen: 4,680 | Margen: 13,49% | Prioridad: ACCION_ALTA
  - 0020390151 | TEE PRESION 1/2 T/PESADO | Volumen: 4,482 | Margen: 13,39% | Prioridad: ACCION_ALTA
  - 0020390005 | ADAPTADOR HEMBRA 1/2" T/PESADO | Volumen: 3,663 | Margen: 12,77% | Prioridad: ACCION_ALTA
  - 0020190021 | FLEJES FIGURADO 1/4" 18X8 TRIANGULAR NTC 2289 | Volumen: 2,180 | Margen: 13,29% | Prioridad: ACCION_ALTA
  - 0010150019 | PUNTILLA PUMA 400GR 21/2" | Volumen: 2,174 | Margen: 13,54% | Prioridad: ACCION_ALTA
  - 0020390137 | TAPON PVC SOLDADO 1/2" T/PESADO | Volumen: 1,699 | Margen: 13,00% | Prioridad: ACCION_ALTA

### 3.3 Customer Concentration
- **Top-10 concentration %:** 18,14%
- **Top customers with low margin (< target floor):**
  - FORTEX COLOMBIA SAS | Margen: 7,34% | Facturación: $43.400.966
  - FERRETERIA MAGRETH S A S | Margen: 7,51% | Facturación: $259.102.149
  - LA CASA CERAMICA SAS | Margen: 8,03% | Facturación: $43.492.316
  - CONSTRUIMOS DEL HUILA S.A | Margen: 8,21% | Facturación: $180.782.257
  - MARIO  MEDINA CORTES | Margen: 8,99% | Facturación: $67.466.128

### 3.4 Returns and Margin Erosion
- **Categories with highest return rate %:**
  - HERRAMIENTAS GRAV AL 5% | Tasa devolución: 22,52% | Ganancia: $1.321.778
  - SERVICIOS DE CORTE | Tasa devolución: 14,29% | Ganancia: $252.060
  - DOMESTICO | Tasa devolución: 13,88% | Ganancia: $3.661.153
  - ART Y HERRAMIENTAS AGRICOLAS | Tasa devolución: 7,74% | Ganancia: $7.649.007
  - CUBIERTA TRAPEZOIDAL | Tasa devolución: 6,71% | Ganancia: $28.643.762
- **Estimated margin impact:** completar con análisis comercial.

### 3.5 Cartera y Riesgo de Crédito (banco_cartera)
- **Snapshot cartera:** 2026-07-06 19:01:25.970000
- **Cartera total:** $5.162.955.046 | **Vencida:** 41,95% | **>90d:** 12,29%
- **DSO:** 24 días | **Ventas netas periodo:** $6.693.546.866 | **Días periodo:** 31
- **Clientes con saldo:** 2,972 | **Sobre cupo:** 116 | **Días vencidos prom. ponderado:** 44.0

### 3.6 Presupuesto vs Real (presupuesto_vendedores)
- **Periodo:** 202412 | **Cumplimiento consolidado MTD:** 46,39%
- **Top 5 vendedores por meta mensual:**
  - LUIS ESTEBAN MEDINA (095) | MTD: $561.358.651 | Meta prorr.: $1.149.774.695 | Cumpl.: 48,82%
  - YULI ALEJANDRA HIGUERA (003) | MTD: $169.130.080 | Meta prorr.: $832.772.297 | Cumpl.: 20,31%
  - SIN COMISION (116) | MTD: $498.777.281 | Meta prorr.: $791.885.990 | Cumpl.: 62,99%
  - OSCAR IVAN POLANIA GARCIA (035) | MTD: $731.221.926 | Meta prorr.: $730.678.402 | Cumpl.: 100,07%
  - JULIAN ANDRES PINEDA (044) | MTD: $27.928.723 | Meta prorr.: $619.112.944 | Cumpl.: 4,51%
- **Bajo 90% cumplimiento (acción comercial):**
  - LUIS ESTEBAN MEDINA — 48,82% (brecha $588.416.044)
  - YULI ALEJANDRA HIGUERA — 20,31% (brecha $663.642.217)
  - SIN COMISION — 62,99% (brecha $293.108.709)
  - JULIAN ANDRES PINEDA — 4,51% (brecha $591.184.221)
  - YULI ALEJANDRA HIGUERA — 30,69% (brecha $394.062.859)

### 3.7 Margen por marca real (productos_adicional)
- **Top 5 marcas por ganancia bruta** (COALESCE producto_marca, banco_datos.marca):
  - MULTIMARCA | Ganancia: $196.182.147 | Margen: 10,94% | Ventas: $1.793.877.411
  - SIKA | Ganancia: $78.357.948 | Margen: 17,05% | Ventas: $459.454.094
  - CEMEX | Ganancia: $74.891.515 | Margen: 10,36% | Ventas: $723.086.293
  - ACESCO | Ganancia: $67.510.474 | Margen: 8,89% | Ventas: $759.012.709
  - PAVCO | Ganancia: $47.386.667 | Margen: 14,55% | Ventas: $325.611.534

### 3.8 Embudo cotización → factura (J3System InvCotiza*)
- **Cotizaciones:** 1,920 | **Convertidas:** 477 | **Perdidas:** 1,443 | **Tasa:** 24,84% | **Días prom.:** 0.8
- **Top 5 vendedores por cotizaciones:**
  - EDILBERTO ESQUIVEL RUBIO (132) | Cotiz.: 215 | Conv.: 49 | Tasa: 22,79%
  - ANDRES FELIPE VARGAS JOVEL (057) | Cotiz.: 183 | Conv.: 13 | Tasa: 7,10%
  - CARLOS EFREY PASCUAS (003) | Cotiz.: 177 | Conv.: 34 | Tasa: 19,21%
  - AMELIA SOTELO NARVAEZ (126) | Cotiz.: 150 | Conv.: 64 | Tasa: 42,67%
  - LUIS ESTEBAN MEDINA (140) | Cotiz.: 147 | Conv.: 51 | Tasa: 34,69%
- **Mayor volumen perdido (sin factura):**
  - ANDRES FELIPE VARGAS JOVEL — 170 perdidas (7,10%)
  - EDILBERTO ESQUIVEL RUBIO — 166 perdidas (22,79%)
  - CARLOS EFREY PASCUAS — 143 perdidas (19,21%)
  - LUIS ESTEBAN MEDINA — 96 perdidas (34,69%)
  - JUAN CARLOS CALLEJAS — 87 perdidas (2,25%)

## 4) Weekly Action Plan (Execution)

| Priority | Lever | Action | Owner | Due Date | Expected KPI Impact |
|---|---|---|---|---|---|
| High | Pricing |  |  |  | +pp margen |
| High | Mix/Bundles |  |  |  | +ticket / +margen |
| High | Customer Terms / Cobranza | Revisar clientes sobre cupo y >90d vencidos | Finanzas |  | -DSO / -cartera 90+ |
| Medium | Customer Terms |  |  |  | +margen cliente |
| Medium | Inventory |  |  |  | +capital / +margen |

## 6) AI Narrative Summary

La ferretería cerró la semana con un Margen Bruto de 12.27% y una Ganancia Bruta de $148.398.489, impulsada por un Ticket Promedio de $300.288. La concentración en los 10 clientes principales (18.14%) y el DSO de 24 días reflejan una base diversificada y un ciclo de cobro aceptable; sin embargo, la cartera vencida >90 días (12.29%) exige atención inmediata. El cumplimiento presupuestal MTD del 46.39% indica que se requiere acelerar la captura de demanda. La tasa de conversión de cotizaciones del 24.84% (0.8 días promedio) es moderada, mientras que PRODUCTOS SIKA y MULTIMARCA lideran las ventas. Se recomienda lanzar, durante los próximos 10 días, una campaña de “día sin IVA” focalizada en SIKA para los clientes con cotizaciones activas, con incentivos de pronto pago que reduzcan la cartera vencida y eleven el ticket promedio en un 8%.

## 5) SQL Blocks Used (Traceability)

- [x] Q1
- [x] Q2
- [x] Q3
- [x] Q4
- [x] Q5
- [x] Q6
- [x] Q7
- [x] Q8
- [x] Q9
- [x] Q10
- [x] Q11
- [x] Q12
