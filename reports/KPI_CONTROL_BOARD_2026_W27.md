# KPI Control Board (Weekly)

## 1) Control Header

- **Week (ISO):** 27
- **Date range:** 2026-06-29 to 2026-07-05
- **Prepared by:** Auto-generated (scripts/utils/generate_kpi_control_board.py)
- **Reviewed with:** Comercial / Compras / Operaciones / Finanzas

## 2) North-Star KPI Scorecard

| KPI | Formula | Baseline | Target | This Week | vs Baseline* | Status |
|---|---|---:|---:|---:|---:|---|
| Margen Bruto % | `SUM(TotalSinIva-ValorCosto)/SUM(TotalSinIva)*100` | 14,44% | 15,44% | 13,70% | -0,75 pp | 🔴 |
| Ganancia Bruta ($) | `SUM(TotalSinIva-ValorCosto)` | $209.792.753 | $220.282.391 | $220.946.578 | 5,32% | 🟢 |
| Ticket Promedio ($) | `SUM(TotalMasIva)/COUNT(*)` | $247.859 | $260.251 | $270.908 | 9,30% | 🟢 |
| Concentración Top-10 Clientes % | `Facturación Top10 / Facturación Total * 100` | — | 24,13% | 26,13% | +2,00 pp | 🔴 |
| DSO (días) | `Cartera Total / (Ventas Netas / días periodo)` | — | 45 | 23 | -22 días | 🟢 |
| Cartera vencida >90d % | `SUM(vencido_90+120+360+superior)/Cartera*100` | — | 12,00% | 12,59% | +0,59 pp | 🔴 |
| Cumplimiento Presupuesto MTD % | `Ventas MTD / Meta prorrateada * 100` | — | 100,00% | 58,13% | -41,87 pp | 🔴 |
| Tasa Conversión Cotizaciones % | `Convertidas / Cotizaciones * 100` (J3System) | — | 30,00% | 34,66% | +4,66 pp | 🟢 |
| Días Cotización → Factura | `AVG(DATEDIFF)` post-cotización (J3System) | — | 7.0 | 0.2 | -7 días | 🟢 |
| SKUs Inventario Crítico | Top-N bajo umbral + alta rotación 90d | — | 25 | 25 | +0 | 🟢 |
| Cobertura Inventario (días prom.) | `Saldo / venta_diaria` SKUs críticos | — | 7.0 | 0.0 | -7 días | 🔴 |
| OTIF Entregas % | `A tiempo / total` (InvHistoricoEntregas) | — | 85,00% | 73,81% | -11,19 pp | 🔴 |
| Lead Time Entrega (días prom.) | `AVG(FechaEntrega - FechaFactura)` | — | 3.0 | 0.5 | -3 días | 🟢 |
| Conciliación Devoluciones % | `1 - |ERP-BI|/ERP` por unidades | — | 99,00% | 100,00% | +1,00 pp | 🟢 |
| Aceptación Factura Electrónica % | `Aceptadas / Emitidas` (DIAN) | — | 99,50% | 100,00% | +0,50 pp | 🟢 |
| Rechazo Factura Electrónica % | `Rechazadas / Emitidas` (DIAN) | — | 0,50% | 0,00% | -0,50 pp | 🟢 |
| Margen Contable % | `(Ingresos 4 - Costos 6) / Ingresos` (PUC) | — | 15,00% | 13,86% | -1,14 pp | 🔴 |

*\* vs Baseline: for north-star sales KPIs with Q1 history, delta is vs prior-week average; when baseline is `—`, delta is vs target.*

## 3) Diagnostic Cut (Where we win/lose)

### 3.1 Category/Subcategory
- **Top 5 by ganancia:**
  - ZINC / ZINC | Ganancia: $20.399.247 | Margen: 8,92%
  - TUBERIA Y ACCE PVC / TUBERIA Y ACCE PVC | Ganancia: $17.800.741 | Margen: 16,17%
  - PRODUCTOS SIKA / PRODUCTOS SIKA | Ganancia: $16.733.087 | Margen: 20,50%
  - EUROCERAMICA / EUROCERAMICA | Ganancia: $13.623.046 | Margen: 13,56%
  - OTROS / OTROS | Ganancia: $11.707.998 | Margen: 14,47%
- **Bottom 5 by margen:**
  - CEMENTO GRIS / CEMENTO GRIS | Margen: 7,98% | Ganancia: $9.390.472
  - ZINC / ZINC | Margen: 8,92% | Ganancia: $20.399.247
  - HIERRO / HIERRO | Margen: 9,33% | Ganancia: $9.908.328
  - ALAMBRES Y MALLAS / ALAMBRES Y MALLAS | Margen: 10,27% | Ganancia: $6.272.831
  - CHAPAS Y CANDADOS / CHAPAS Y CANDADOS | Margen: 10,74% | Ganancia: $504.450
- **Biggest WoW drop in margen:** VINILTEX / VINILTEX | 23,38% → 18,02% (-5,35 pp) | Ventas: $2.838.580

### 3.2 SKU Focus (High Volume + Low Margin)
- **Critical SKUs (ACCION_INMEDIATA / ACCION_ALTA):**
  - 0020190017 | FLEJES FIGURADO 1/4" 18X8 NTC 2289 | Volumen: 3,185 | Margen: 13,93% | Prioridad: ACCION_ALTA
  - 0020390214 | UNION  PRESION 1/2" T/PESADO | Volumen: 2,744 | Margen: 15,79% | Prioridad: ACCION_ALTA
  - 0020390151 | TEE PRESION 1/2 T/PESADO | Volumen: 1,540 | Margen: 15,39% | Prioridad: ACCION_ALTA
  - 0010150032 | PUNTILLA C.A MEJIA 350GR 21/2" | Volumen: 955 | Margen: 14,09% | Prioridad: ACCION_ALTA
  - 0020190016 | FLEJES FIGURADO 1/4" 15X15 NTC 2289 | Volumen: 903 | Margen: 13,10% | Prioridad: ACCION_ALTA
  - 0010150034 | PUNTILLA C.A MEJIA 350GR 2" | Volumen: 740 | Margen: 14,92% | Prioridad: ACCION_ALTA
  - 0020390079 | CODO SANITARIO 90 CC 2" T/PESADO | Volumen: 655 | Margen: 13,65% | Prioridad: ACCION_ALTA
  - 0020260031 | PERFIL PARAL 2.44 BASE 6 CALIBRE 26 | Volumen: 568 | Margen: 13,66% | Prioridad: ACCION_ALTA
  - 0010150035 | PUNTILLA C.A MEJIA 350GR 3" | Volumen: 544 | Margen: 15,75% | Prioridad: ACCION_ALTA
  - 0020390330 | TUBO PRESION PAVCO RDE 9 1/2" X 6 MTS | Volumen: 540 | Margen: 13,51% | Prioridad: ACCION_ALTA

### 3.3 Customer Concentration
- **Top-10 concentration %:** 26,13%
- **Top customers with low margin (< target floor):**
  - DISTRIBUCIONES SILVA UNO SAS | Margen: 6,95% | Facturación: $9.092.259
  - FERRECENTRO SVCT ZOMAC SAS | Margen: 7,49% | Facturación: $128.595.076
  - FERRETERIA MAGRETH S A S | Margen: 7,50% | Facturación: $36.473.295
  - CORIN DANIELA NARVAEZ RODRIGUEZ | Margen: 9,36% | Facturación: $31.604.145
  - MLW DISEÑOS Y CONSTRUCCIONES S.A.S | Margen: 10,06% | Facturación: $16.012.973

### 3.4 Returns and Margin Erosion
- **Categories with highest return rate %:**
  - CUBIERTA TRAPEZOIDAL | Tasa devolución: 75,04% | Ganancia: $9.955.804
  - CERAMICA ITALIA | Tasa devolución: 15,04% | Ganancia: $1.056.394
  - SALA ENCHAPES | Tasa devolución: 7,98% | Ganancia: $1.432.878
  - ABRAZADERAS | Tasa devolución: 6,76% | Ganancia: $101.635
  - PINTULAND | Tasa devolución: 6,67% | Ganancia: $393.509
- **Estimated margin impact:** $11.294.868 (heurística: Σ tasa_devolución% × ganancia_bruta por categoría)
  - CUBIERTA TRAPEZOIDAL | impacto: $7.471.159 | tasa: 75,04%
  - PRODUCTOS SIKA | impacto: $892.071 | tasa: 5,33%
  - OTROS | impacto: $501.192 | tasa: 4,28%

### 3.5 Cartera y Riesgo de Crédito (banco_cartera)
- **Snapshot cartera:** 2026-07-08 19:01:49.750000
- **Cartera total:** $5.260.732.323 | **Vencida:** 39,27% | **>90d:** 12,59%
- **DSO:** 23 días | **Ventas netas periodo:** $1.613.260.509 | **Días periodo:** 7
- **Clientes con saldo:** 3,004 | **Sobre cupo:** 122 | **Días vencidos prom. ponderado:** 43.4

### 3.6 Presupuesto vs Real (presupuesto_vendedores)
- **Periodo ventas:** 20267 | **Periodo meta:** 20247 | **Origen meta:** proxy: mismo mes en el último año con meta cargada (periodo meta 20247)
- **Cumplimiento consolidado MTD:** 58,13% (ventas $707.376.535 / meta prorr. $1.216.931.001)
- **Nota:** no hay filas en `presupuesto_vendedores` para el periodo de ventas; se usa la meta del mismo mes calendario en el último año disponible, prorrateada al MTD actual. Cargar metas del periodo corriente para comparación exacta.
- **Top 5 vendedores por meta mensual:**
  - WILLIAM HERNANDO QUINTERO G (095) | MTD: $146.166.498 | Meta prorr.: $171.753.514 | Cumpl.: 85,10%
  - HUBER SANTIAGO ENCISO (044) | MTD: $111.693.972 | Meta prorr.: $115.833.535 | Cumpl.: 96,43%
  - HUBER SANTIAGO ENCISO (116) | MTD: $61.768.312 | Meta prorr.: $106.537.847 | Cumpl.: 57,98%
  - 135 (135) | MTD: $0 | Meta prorr.: $94.015.059 | Cumpl.: 0,00%
  - CARLOS EFREY PASCUAS (003) | MTD: $30.748.102 | Meta prorr.: $92.915.613 | Cumpl.: 33,09%
- **Bajo 90% cumplimiento (acción comercial):**
  - WILLIAM HERNANDO QUINTERO G — 85,10% (brecha $25.587.016)
  - HUBER SANTIAGO ENCISO — 57,98% (brecha $44.769.535)
  - 135 — 0,00% (brecha $94.015.059)
  - CARLOS EFREY PASCUAS — 33,09% (brecha $62.167.511)
  - OSCAR IVAN POLANIA GARCIA — 52,53% (brecha $41.236.154)

### 3.7 Margen por marca real (productos_adicional)
- **Top 5 marcas por ganancia bruta** (COALESCE producto_marca, banco_datos.marca):
  - MULTIMARCA | Ganancia: $48.096.869 | Margen: 12,23% | Ventas: $393.422.189
  - ACESCO | Ganancia: $22.509.176 | Margen: 8,92% | Ventas: $252.238.667
  - PAVCO | Ganancia: $17.756.620 | Margen: 15,65% | Ventas: $113.479.334
  - SIKA | Ganancia: $15.461.703 | Margen: 20,93% | Ventas: $73.860.963
  - CEMEX | Ganancia: $12.518.547 | Margen: 8,95% | Ventas: $139.830.844

### 3.8 Embudo cotización → factura (J3System InvCotiza*)
- **Cotizaciones:** 629 | **Convertidas:** 218 | **Perdidas:** 411 | **Tasa:** 34,66% | **Días prom.:** 0.2
- **Top 5 vendedores por cotizaciones:**
  - CALL CENTER (121) | Cotiz.: 68 | Conv.: 8 | Tasa: 11,76%
  - DIANA PATRICIA CULMA (106) | Cotiz.: 65 | Conv.: 44 | Tasa: 67,69%
  - ANDRES FELIPE VARGAS JOVEL (057) | Cotiz.: 62 | Conv.: 15 | Tasa: 24,19%
  - KERLY JOHANA CAICEDO (156) | Cotiz.: 52 | Conv.: 22 | Tasa: 42,31%
  - JAVIER ANDRES APACHE (130) | Cotiz.: 46 | Conv.: 10 | Tasa: 21,74%
- **Mayor volumen perdido (sin factura):**
  - CALL CENTER — 60 perdidas (11,76%)
  - ANDRES FELIPE VARGAS JOVEL — 47 perdidas (24,19%)
  - JAVIER ANDRES APACHE — 36 perdidas (21,74%)
  - KERLY JOHANA CAICEDO — 30 perdidas (42,31%)
  - LUIS ESTEBAN MEDINA — 27 perdidas (38,64%)

### 3.9 Inventario crítico y quiebres (InvDetalleExistencias)
- **SKUs críticos (top 25):** 25 | **Quiebre <7d:** 25 | **Stock ≤10:** 25 | **Cobertura prom.:** 0.0 días
- **Top 10 SKUs por riesgo de quiebre (menor cobertura):**
  - 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | ALM | Stock: 0 | Venta 90d: 75371 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | CON | Stock: 0 | Venta 90d: 75371 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | BDT | Stock: 0 | Venta 90d: 75371 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | CEN | Stock: 0 | Venta 90d: 75371 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | B.ROT | Stock: 0 | Venta 90d: 75371 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | EXH | Stock: 0 | Venta 90d: 75371 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | BOD | Stock: 0 | Venta 90d: 75371 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | FLO | Stock: 0 | Venta 90d: 75371 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020390061 | CODO PRESION 90 1/2 T/PESADO | SUR | Stock: 0 | Venta 90d: 66026 | Cobertura: 0.0d | QUIEBRE_INMINENTE
  - 0020390061 | CODO PRESION 90 1/2 T/PESADO | EXH | Stock: 0 | Venta 90d: 66026 | Cobertura: 0.0d | QUIEBRE_INMINENTE

### 3.10 OTIF — cumplimiento de entregas (InvHistoricoEntregas)
- **Total entregas:** 6,747 | **A tiempo:** 4,980 | **OTIF:** 73,81% | **Lead prom.:** 0.5d | **Fill rate:** 99,47%
- **Bodegas con peor OTIF:**
  - BOD | OTIF: 10,78% | Entregas: 102 | Lead: 2.6d
  - SUR | OTIF: 29,13% | Entregas: 745 | Lead: 1.3d
  - BD6 | OTIF: 66,27% | Entregas: 845 | Lead: 0.5d
  - DIS | OTIF: 75,27% | Entregas: 744 | Lead: 0.4d
  - ALM | OTIF: 83,97% | Entregas: 4210 | Lead: 0.3d

### 3.11 Conciliación devoluciones ERP vs BI
- **Unidades ERP:** 14,611 | **BI:** 14,611 | **Conciliación:** 100,00% | **Tasa validada:** 12,23% | **Brechas categoría:** 0
- **Sin brechas por categoría en el periodo (ERP = BI).**
- **Mayor erosión de margen (devoluciones):**
  - CUBIERTA TRAPEZOIDAL | Impacto: $1.243.270 | Tasa validada: 75,04%
  - PRODUCTOS SIKA | Impacto: $595.235 | Tasa validada: 5,33%
  - TANQUES | Impacto: $583.203 | Tasa validada: 2,42%
  - LAVAPLATOS | Impacto: $498.252 | Tasa validada: 5,48%
  - EUROCERAMICA | Impacto: $459.366 | Tasa validada: 2,77%

### 3.12 Factura electrónica DIAN
- **Emitidas:** 2,356 | **Aceptadas:** 2,356 | **Rechazadas:** 0 | **Aceptación:** 100,00% | **Rechazo:** 0,00%
- **Sin rechazos DIAN en el periodo.**
- **Mayor volumen electrónico:**
  - FED | Emitidas: 1816 | Aceptación: 100,00%
  - FET | Emitidas: 329 | Aceptación: 100,00%
  - DVE | Emitidas: 77 | Aceptación: 100,00%
  - DSE | Emitidas: 63 | Aceptación: 100,00%
  - FEF | Emitidas: 62 | Aceptación: 100,00%

### 3.13 Contabilidad — PyG PUC
- **Ingresos (créditos clase 4):** $1.636.912.906 | **Costos (débitos clase 6):** $1.410.104.012 | **Gastos (débitos clase 5):** $662.571.552
- **Margen bruto contable:** $226.808.894 | **Margen %:** 13,86%
  - Clase 4 (Ingresos) | Créditos: $1.636.912.906 | Débitos: $28.874.603 | Saldo: $1.608.038.303
  - Clase 5 (Gastos) | Créditos: $1.816.900 | Débitos: $662.571.552 | Saldo: $660.754.652
  - Clase 6 (Costos) | Créditos: $56.512.580 | Débitos: $1.410.104.012 | Saldo: $1.353.591.432

## 4) Weekly Action Plan (Execution)

| Priority | Lever | Action | Owner | Due Date | Expected KPI Impact |
|---|---|---|---|---|---|
| High | Pricing |  |  |  | +pp margen |
| High | Mix/Bundles |  |  |  | +ticket / +margen |
| High | Customer Terms / Cobranza | Revisar clientes sobre cupo y >90d vencidos | Finanzas |  | -DSO / -cartera 90+ |
| Medium | Customer Terms |  |  |  | +margen cliente |
| Medium | Inventory |  |  |  | +capital / +margen |

## 6) AI Narrative Summary

Durante la semana, la ferretería registró un margen bruto de 13,70% sobre una ganancia bruta de $220.946.578 y un ticket promedio de $270.908. La concentración en los 10 principales clientes alcanzó 26,13%, mientras que el DSO se mantuvo en 23 días y la cartera vencida mayor a 90 días representó 12,59%. El cumplimiento presupuestal MTD llegó a 58,13% y la tasa de conversión de cotizaciones fue 34,66% con un ciclo de 0,2 días. Se detectaron 25 SKUs en inventario crítico sin cobertura, y el OTIF de entregas fue 73,81% con lead time de 0,5 días. Las devoluciones se conciliaron al 100% y la facturación electrónica mantuvo 100% de aceptación. El margen contable cerró en 13,86% con ingresos de $1.636.912.906; ZINC y MULTIMARCA lideraron categorías y marcas. Se recomienda priorizar la reposición inmediata de los SKUs críticos y lanzar promociones dirigidas a los clientes top para elevar el ticket promedio y mejorar la liquidez.

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
- [x] Q13
- [x] Q14
- [x] Q15
- [x] Q16
- [x] Q17
