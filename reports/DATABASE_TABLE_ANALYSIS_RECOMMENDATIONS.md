# Análisis de Tablas y Recomendaciones — SmartBusiness & J3System

**Fecha:** 2026-07-07
**Servidor:** 190.60.235.209:1433 (conexión verificada en vivo)
**Método:** Ranking por espacio asignado (`sys.tables` + `sys.partitions`); conteos de filas aproximados vía particiones heap/clustered.

**Evidencia capturada:** `smartbusiness_table_sizes.json`, `j3system_table_sizes.json`, `top_tables_schema.json` (scratch del análisis).

---

## Executive Summary

SmartBusiness es una base **analítica liviana** (8 tablas): el 99% del volumen está en `banco_datos` (~1.56M filas, ~1 GB), que ya alimenta el reporte gerencial, el KPI SQL pack, Vanna/MCP y el mart de afinidad. Las tablas restantes — especialmente `banco_cartera` y `presupuesto_*` — son **oportunidades inmediatas** no explotadas.

J3System es el ERP operativo completo (968 tablas). Las tablas más grandes mezclan **ventas** (`InvVentas`, `InvVentasDetalle`), **contabilidad** (`ConMovimiento*`), **logística** (`InvHistoricoEntregas`), **inventario** (`InvDetalleExistencias`), **cotizaciones** (`InvCotiza*`) y **cartera** (`CarCarteraCliente`). Hoy el repo solo usa un subconjunto estrecho: desglose por almacén vía `InvVentasDetalle` + `AdmAlmacen`, y lookup de celular en `AdmTerceros`.

**Prioridad estratégica:** (1) conectar cartera y presupuesto en SmartBusiness al tablero KPI semanal; (2) enriquecer análisis con cotizaciones, existencias y entregas desde J3System; (3) validar devoluciones y facturación electrónica contra fuentes ERP, no solo signos negativos en `banco_datos`.

---

## SmartBusiness Largest Tables

SmartBusiness contiene **8 tablas** en total (menos de 15; se listan todas).

| # | Tabla | Dominio | Filas (aprox.) | Espacio (MB) | Repo actual |
|---|-------|---------|----------------|--------------|-------------|
| 1 | `dbo.banco_datos` | Transacciones de venta (fact table) | 1,558,240 | 1,020 | Reporte gerencial, KPI pack Q1–Q8, Vanna, affinity mart |
| 2 | `dbo.productos_adicional` | Maestro de producto (marca, rubro, proveedor) | 14,266 | 3.6 | JOIN en training Vanna; no en reportes automatizados |
| 3 | `dbo.banco_cartera` | Cartera / cuentas por cobrar (aging) | 2,972 | 1.2 | **Sin cobertura** |
| 4 | `dbo.presupuesto_lineas_copy2` | Presupuesto por línea/vendedor (copia) | 5,028 | 0.2 | **Sin cobertura** |
| 5 | `dbo.presupuesto_lineas` | Presupuesto por línea de producto | 4,322 | 0.2 | **Sin cobertura** |
| 6 | `dbo.presupuesto_lineas_copy1` | Presupuesto por línea (copia) | 4,272 | 0.2 | **Sin cobertura** |
| 7 | `dbo.presupuesto_vendedores` | Meta de venta por vendedor | 216 | 0.07 | **Sin cobertura** |
| 8 | `dbo.presupuesto_vendedores_copy1` | Meta por vendedor (copia) | 204 | 0.07 | **Sin cobertura** |

### Notas de dominio

- **`banco_datos`:** Líneas de factura con `DocumentosCodigo`, `TercerosNombres`, `ArticulosCodigo`, `TotalSinIva`, `ValorCosto`, `AlmacenCodigo`. Regla crítica: excluir `XY`, `AS`, `TS`, `YX`, `ISC`.
- **`productos_adicional`:** Atributos limpios de marca (`producto_marca`), rubro/subrubro y proveedor — preferir sobre el campo `marca` denormalizado en `banco_datos`.
- **`banco_cartera`:** Snapshot de cartera con buckets `corriente`, `vencido_30`…`vencido_superior`, `dias_vencidos`, `cliente_cupo`, `vendedor_nombre`.
- **`presupuesto_*`:** Metas por `periodo`, `vendedor_codigo`, `linea`/`grupo` — habilitan **presupuesto vs real** sin tocar J3System.

---

## J3System Largest Tables

Top 15 por espacio asignado (968 tablas en total).

| # | Tabla | Dominio | Filas (aprox.) | Espacio (MB) | Repo actual |
|---|-------|---------|----------------|--------------|-------------|
| 1 | `dbo.InvVentas` | Encabezado de ventas ERP | 1,665,189 | 6,186 | Parcial: warehouse en reporte gerencial |
| 2 | `dbo.AdmAuditoria` | Auditoría de sistema | 3,788,648 | 949 | Sin cobertura |
| 3 | `dbo.ConMovimientoDetalle` | Líneas contables | 4,492,415 | 911 | Sin cobertura |
| 4 | `dbo.InvHistoricoEntregas` | Historial de entregas/despacho | 1,494,517 | 475 | Sin cobertura |
| 5 | `dbo.InvVentasDetalle` | Líneas de venta + `AlmacenID` | 1,530,587 | 345 | Parcial: `j3system_sales_warehouse.py` |
| 6 | `dbo.ConMovimiento` | Encabezado movimientos contables | 1,511,318 | 263 | Sin cobertura |
| 7 | `dbo.InvEstadoFacturaElectronica` | Estado factura electrónica / DIAN | 519,257 | 260 | Sin cobertura |
| 8 | `dbo.InvVentasTotales` | Totales agregados de venta | 545,197 | 176 | Sin cobertura |
| 9 | `dbo.InvDetalleExistencias` | Existencias por almacén/artículo | 316,405 | 168 | Sin cobertura |
| 10 | `dbo.HistoriaAdmArticulos` | Historial de cambios de artículo | 418,274 | 157 | Sin cobertura |
| 11 | `dbo.InvFacturaCanceladas` | Facturas canceladas | 542,101 | 134 | Sin cobertura |
| 12 | `dbo.AdmGuardaPagos` | Staging de pagos | 633,335 | 122 | Sin cobertura |
| 13 | `dbo.InvCotizaDetalle` | Líneas de cotización | 455,637 | 88 | Sin cobertura |
| 14 | `dbo.InvDevolucionVentas` | Devoluciones de venta | 53,730 | 83 | Sin cobertura (solo negativos en `banco_datos`) |
| 15 | `dbo.InvFacturaPorCancelarDetalle` | Detalle facturas por cancelar | 1,487,773 | 75 | Sin cobertura |

### Notas de dominio

- **`InvVentas` / `InvVentasDetalle`:** Fuente autoritativa ERP; `VentaID` une header y líneas; `AlmacenID` → `AdmAlmacen` para bodega real (ver `docs/reference/j3system-sales-warehouse-query.md`).
- **`InvCotizaCab` / `InvCotizaDetalle`:** Embudo comercial previo a factura — tasa de conversión cotización→venta.
- **`InvDetalleExistencias`:** Stock operativo; complementa márgenes con riesgo de quiebre.
- **`InvHistoricoEntregas`:** Cumplimiento logístico (fecha factura vs entrega).
- **`CarCarteraCliente`:** Cartera nativa ERP; cruzar con `banco_cartera` de SmartBusiness.
- **`ConMovimiento*`:** Libro mayor; útil para conciliación financiera avanzada (largo plazo).

---

## Cross-Database Insights

| Capacidad analítica | Fuente primaria hoy | Fuente ERP alternativa | Estado |
|---------------------|---------------------|------------------------|--------|
| Ventas y margen | `banco_datos` | `InvVentas` + `InvVentasDetalle` | `banco_datos` domina; J3 solo para almacén |
| Marca / categoría limpia | `productos_adicional` JOIN | `HistoriaAdmArticulos` | JOIN documentado pero no en KPI pack |
| Almacén por venta | `banco_datos.AlmacenCodigo` | `InvVentasDetalle` + `AdmAlmacen` | Ambos; manager report usa J3 para desglose |
| Cartera / aging | — | `banco_cartera` (SB) + `CarCarteraCliente` (J3) | **Gap crítico** |
| Presupuesto vs real | — | `presupuesto_lineas` + `presupuesto_vendedores` | **Gap** — datos ya en SmartBusiness |
| Cotizaciones | Export Excel + `AdmTerceros` | `InvCotizaCab` / `InvCotizaDetalle` | Solo script celular; sin embudo SQL |
| Inventario | — | `InvDetalleExistencias` | **Gap** |
| Devoluciones | Cantidad negativa en `banco_datos` | `InvDevolucionVentas` | Parcial / sin conciliación |
| Co-compra / afinidad | Mart sobre `banco_datos` | — | Cubierto (`affinity_indexes_and_mart.sql`) |
| Factura electrónica | — | `InvEstadoFacturaElectronica` | **Gap** compliance/ops |

**Implicación:** SmartBusiness es el **data mart de BI** listo para consumo; J3System es la **fuente de verdad operativa** para todo lo que `banco_datos` no replica (cotizaciones, existencias, entregas, cartera ERP, contabilidad).

---

## Recommended Reports

### P1 — Tablero Cartera + Riesgo de Crédito
- **Tablas:** `banco_cartera` (SmartBusiness), `CarCarteraCliente` + `AdmTerceros` (J3System)
- **Contenido:** Aging por vendedor/zona, % cartera vencida >90 días, clientes sobre cupo (`cliente_cupo` vs `total`)
- **Encaje repo:** Nuevo bloque Q9 en `scripts/analysis/kpi_sql_pack.sql.template`; sección en `KPI_CONTROL_BOARD_TEMPLATE.md`
- **Prioridad:** Alta — datos pequeños, alto impacto gerencial

### P1 — Presupuesto vs Real por Vendedor y Línea
- **Tablas:** `presupuesto_vendedores`, `presupuesto_lineas` + `banco_datos`
- **Contenido:** % cumplimiento mensual, brecha por `linea`/`grupo`, ranking de vendedores bajo meta
- **Encaje repo:** Extender manager report (`manager_report/queries.py`) con CTE de presupuesto
- **Prioridad:** Alta — tablas ya en SmartBusiness, sin ETL

### P2 — Embudo Cotización → Factura
- **Tablas:** `InvCotizaCab`, `InvCotizaDetalle`, `InvVentas`, `AdmTerceros`
- **Contenido:** Tasa de conversión, tiempo medio cotización→venta, cotizaciones perdidas por vendedor
- **Encaje repo:** Evolucionar `cotizaciones_celular.py` a pipeline SQL nativo; training Vanna
- **Prioridad:** Media-alta

### P2 — Inventario Crítico y Quiebres de Stock
- **Tablas:** `InvDetalleExistencias`, `AdmAlmacen`, `banco_datos` (velocidad de venta)
- **Contenido:** SKUs con existencia < umbral y alta rotación (últimos 90 días)
- **Encaje repo:** Nuevo script en `scripts/analysis/`; tarjeta Metabase
- **Prioridad:** Media

### P3 — Cumplimiento de Entregas (OTIF)
- **Tablas:** `InvHistoricoEntregas`, `InvVentas`
- **Contenido:** % entregas a tiempo, lead time por almacén, clientes con peor SLA
- **Encaje repo:** Sección logística en reporte gerencial HTML
- **Prioridad:** Media (requiere reglas de negocio de “a tiempo”)

### P3 — Conciliación Devoluciones ERP vs BI
- **Tablas:** `InvDevolucionVentas`, `banco_datos` (líneas negativas / `DVE`)
- **Contenido:** Diferencias por categoría/mes, categorías con mayor erosión de margen real
- **Encaje repo:** Complementa KPI pack Q7 (devoluciones por categoría)
- **Prioridad:** Media

---

## Recommended KPIs

| KPI | Fórmula / fuente | Tablas | Integración |
|-----|------------------|--------|-------------|
| **DSO (días cartera)** | `SUM(total * dias_vencidos) / SUM(total)` o saldo / ventas diarias | `banco_cartera` | Nuevo Q9 KPI pack |
| **% Cartera vencida >90d** | `SUM(vencido_90+vencido_120+…)/SUM(total)` | `banco_cartera` | KPI board semanal |
| **Cumplimiento presupuesto %** | `SUM(ventas reales) / SUM(presupuesto.valor)` por periodo | `presupuesto_vendedores`, `banco_datos` | Manager report |
| **Tasa conversión cotizaciones** | `COUNT(ventas) / COUNT(cotizaciones)` mismo periodo | `InvCotizaCab`, `InvVentas` | Nuevo |
| **Cobertura de inventario (días)** | `existencia / venta_diaria_promedio` | `InvDetalleExistencias`, `banco_datos` | Nuevo |
| **Fill rate / OTIF %** | Entregas a tiempo / total entregas | `InvHistoricoEntregas` | Nuevo |
| **Tasa devolución validada** | Unidades devueltas ERP / unidades vendidas | `InvDevolucionVentas`, `banco_datos` | Mejora Q7 existente |
| **Facturas electrónicas rechazadas %** | Rechazadas / emitidas | `InvEstadoFacturaElectronica` | Nuevo (compliance) |
| **Margen con marca real** | Margen JOIN `productos_adicional.producto_marca` | `banco_datos`, `productos_adicional` | Mejora KPI Q2/Q3 |

---

## Recommended Analysis Improvements

1. **Unificar atributos de producto:** Reemplazar análisis por `banco_datos.marca` (tax/grupo) con JOIN sistemático a `productos_adicional` en manager report y KPI pack — alinea reportes SIKA con marcas reales (PINTUCO, SIKA, etc.).

2. **Dual-source warehouse:** Mantener `DocumentosCodigo` para sucursales comerciales (FED/FEF/FET) y J3 `AlmacenCodigo` para bodegas físicas (FLO, BD6, SUR) — documentado en `j3system-sales-warehouse-query.md`; extender a inventario y entregas.

3. **Cartera como primer ciudadano:** El KPI pack hoy es 100% `banco_datos`. Agregar cartera desbloquea decisiones de crédito y cobranza sin consultar ERP.

4. **Mart de cotizaciones:** Tabla materializada `cotizacion_embudo` refrescada nightly (patrón affinity mart) para no escanear 455k+ líneas de `InvCotizaDetalle` en cada pregunta Vanna.

5. **Vanna / MCP training:** Agregar ejemplos para `banco_cartera`, `presupuesto_lineas`, `InvCotizaCab`, `InvDetalleExistencias` — hoy el training J3System cubre warehouse pero no cotizaciones ni existencias.

6. **Limpiar tablas duplicadas:** `presupuesto_lineas_copy1/2` y `presupuesto_vendedores_copy1` — confirmar cuál es la versión activa antes de cablear reportes (evitar metas incorrectas).

7. **Contabilidad (largo plazo):** `ConMovimiento`/`ConMovimientoDetalle` habilitan EBITDA, gastos por centro de costo — solo después de dominar ventas/cartera/inventario.

---

## Quick Wins vs Longer-Term

### Quick Wins (1–2 semanas)
- Agregar Q9 cartera a `kpi_sql_pack.sql.template` usando `banco_cartera`
- Sección presupuesto vs real en reporte gerencial (`presupuesto_vendedores` + `banco_datos`)
- JOIN obligatorio a `productos_adicional` en queries de marca del KPI pack
- Documentar en Vanna 3 preguntas tipo: “cartera vencida por vendedor”, “cumplimiento presupuesto”, “margen por marca real”

### Longer-Term (1–3 meses)
- Pipeline embudo cotizaciones (`InvCotiza*` → mart)
- Tablero inventario crítico (`InvDetalleExistencias`)
- OTIF con `InvHistoricoEntregas`
- Conciliación devoluciones ERP (`InvDevolucionVentas`)
- Exploración contable (`ConMovimiento*`) para finanzas

---

## Referencias del Repositorio

| Asset | Tablas que cubre | Brecha vs hallazgos |
|-------|------------------|---------------------|
| `data/database_explained.json` | `banco_datos`, `productos_adicional` | No documenta `banco_cartera` ni `presupuesto_*` |
| `scripts/analysis/kpi_sql_pack.sql.template` | `banco_datos` only | Sin cartera, presupuesto, inventario |
| `src/business_analyzer/analysis/manager_report/` | `banco_datos` + J3 warehouse | Sin cartera, cotizaciones, inventario |
| `docs/reference/j3system-sales-warehouse-query.md` | `InvVentas`, `InvVentasDetalle`, `AdmAlmacen` | No cubre cotizaciones ni existencias |
| `data/sql/affinity_indexes_and_mart.sql` | Derivado de `banco_datos` | OK para co-compra |
| `src/business_analyzer/analysis/cotizaciones_celular.py` | `AdmTerceros` | No usa `InvCotiza*` nativo |

---

*Generado por introspección live MSSQL. Script reutilizable: `scripts/utils/introspect_table_sizes.py`.*
