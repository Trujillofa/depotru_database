# Database Table Decision Summary — SmartBusiness & J3System

**Live inventory date:** 2026-07-29
**Capture timestamps (UTC):** SmartBusiness `2026-07-29T17:37:55.028028+00:00` · J3System `2026-07-29T17:37:55.028028+00:00`
**Server:** 190.60.235.209:1433 (verified live via `scripts/utils/introspect_table_sizes.py`)
**Method:** `sys.partitions` heap/clustered **row counts** (no allocation-unit multiplication); space via separate `sys.allocation_units` aggregate
**Raw evidence (scratch):** `smartbusiness_table_sizes.json`, `j3system_table_sizes.json`, `schemas_smartbusiness_all.json`, `schemas_j3_critical.json`, `j3system_domain_catalog.json`

> This document is a **decision-making catalog**: every inventoried user table is named. SmartBusiness tables get full decision write-ups; J3System gets deep notes for commercial/finance tables and one-line purpose notes for the rest (complete appendix by domain).
>
> **Row-count note:** Counts use partition-only aggregation. An earlier join of `sys.allocation_units` into the rows SUM inflated some tables (e.g. `InvVentas` 3×, `productos_adicional` 2×). Figures below are the corrected partition truth.

---

## 1. Executive framing for decision makers

| Database | Role | Tables | Dominant volume | Use for decisions |
|----------|------|--------|-----------------|-------------------|
| **SmartBusiness** | Analytic / BI mart for the store | **8** | `banco_datos` ~1036.38 MB / 1,582,580 rows | Day-to-day sales, margin, budget, AR snapshot |
| **J3System** | Full ERP system of record | **968** | `InvVentas` ~6284.33 MB / 563,106 rows | Warehouse truth, quotes, stock, deliveries, formal AR/AP, GL, payroll |

**Totals this run:** SmartBusiness ≈ **1042.26 MB** across 8 tables; J3System ≈ **11381.8 MB** across 968 tables.

**What to decide from which system**

1. **Commercial performance (sales, margin, seller, brand)** → start in SmartBusiness `banco_datos` (+ `productos_adicional`).
2. **Budget vs actual** → SmartBusiness `presupuesto_vendedores` / `presupuesto_lineas` vs `banco_datos` (confirm active copy first).
3. **Credit / collections** → SmartBusiness `banco_cartera` for quick aging; J3 `CarCarteraCliente` for ERP open items.
4. **Physical stock, quotes, deliveries, formal returns, e-invoice DIAN** → J3System only.
5. **GL / statutory accounting / payroll / fleet / hotel modules** → J3System; mostly outside weekly commercial KPI board.

**Critical SQL rule (all sales analytics on `banco_datos`):**
```sql
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')  -- also exclude YX, ISC in production packs
```

---

## 2. SmartBusiness — complete table inventory & decision notes

Live count: **8** user tables (all listed below).

| # | Table | Rows (approx.) | Space (MB) | Decision value |
|---|-------|----------------|------------|----------------|
| 1 | `banco_datos` | 1,582,580 | 1036.38 | Critical |
| 2 | `productos_adicional` | 7,133 | 3.57 | High |
| 3 | `banco_cartera` | 2,895 | 1.33 | High (underused) |
| 4 | `presupuesto_lineas` | 8,474 | 0.45 | High (confirm active) |
| 5 | `presupuesto_lineas_copy2` | 5,028 | 0.2 | Low (copy/staging) |
| 6 | `presupuesto_lineas_copy1` | 4,272 | 0.2 | Low (copy/staging) |
| 7 | `presupuesto_vendedores` | 432 | 0.07 | High (confirm active) |
| 8 | `presupuesto_vendedores_copy1` | 204 | 0.07 | Low (copy/staging) |

### `banco_datos`

- **Rows / size (live):** 1,582,580 rows · 1036.38 MB allocated (1036.22 MB used)
- **What it is:** Fact table of sales invoice lines (transaction grain: one row per document line). Primary BI source for revenue, cost, margin, customer, product, and branch analysis.
- **Grain:** One sales line (VentaID + line identity via product/doc fields)
- **Key columns:** Fecha, DocumentosCodigo, TotalSinIva, TotalMasIva, ValorCosto, Cantidad, TercerosNombres, ArticulosCodigo/Nombre, AlmacenCodigo, vendedor_codigo, marca, categoria
- **Schema (live describe, 38 cols):** `VentaID`, `VendedorID`, `VendedorFactura`, `vendedor_codigo`, `VendedorAsignado`, `DocumentosCodigo`, `DocumentosNombre`, `NumeroDocumento`, `Fecha`, `ano`, `mes`, `dia`, `periodo`, `DiasCredito`, `TercerosID`, `TercerosIdentificacion` … (+22 more)
- **How it helps decisions:** Daily/weekly sales KPIs, margin by product/customer/seller, affinity/cross-sell, manager report, Vanna NL→SQL. CRITICAL filter: exclude DocumentosCodigo IN ('XY','AS','TS','YX','ISC').
- **Gaps / caveats:** Does not fully replace ERP for warehouse physical stock, quotations funnel, formal returns docs, or electronic invoice DIAN status.

### `productos_adicional`

- **Rows / size (live):** 7,133 rows · 3.57 MB allocated (3.43 MB used)
- **What it is:** Clean product master attributes (brand, category/subcategory, supplier) joined to sales lines for correct brand/category reporting.
- **Grain:** One product (SKU / artículo)
- **Key columns:** producto code + producto_marca, rubro/subrubro, proveedor fields (see schema dump)
- **Schema (live describe, 9 cols):** `producto_codigo`, `producto_descripcion`, `producto_marca`, `producto_rubro`, `producto_subrubro`, `proveedor_nit`, `proveedor_descripcion`, `producto_caracteristicas`, `web`
- **How it helps decisions:** Brand performance (PINTUCO, SIKA, etc.), category mix, supplier concentration. Prefer over denormalized `banco_datos.marca`.
- **Gaps / caveats:** Not systematically joined in all automated KPI pack queries; still optional in some reports.

### `banco_cartera`

- **Rows / size (live):** 2,895 rows · 1.33 MB allocated (1.16 MB used)
- **What it is:** Accounts receivable (AR) aging snapshot for customers — credit risk and collections dashboard source in SmartBusiness.
- **Grain:** Customer / receivable position snapshot
- **Key columns:** cliente, vendedor, corriente, vencido_30…, dias_vencidos, cliente_cupo, total
- **Schema (live describe, 40 cols):** `cliente_uid`, `cliente_nit`, `cliente_razon_social`, `cliente_sucursal_uid`, `cliente_sucursal_descripcion`, `cliente_ciudad`, `cliente_departamento`, `cliente_pais`, `cliente_lista_codigo`, `cliente_lista_descripcion`, `condicion_pago_codigo`, `condicion_pago_descripcion`, `cliente_cupo`, `cliente_origen`, `regional`, `zona_unica` … (+24 more)
- **How it helps decisions:** DSO, % AR past due >90d, customers over credit limit, collections priority by seller/zone.
- **Gaps / caveats:** Still underused vs banco_datos; reconcile with J3 CarCarteraCliente for formal ERP AR.

### `presupuesto_lineas`

- **Rows / size (live):** 8,474 rows · 0.45 MB allocated (0.36 MB used)
- **What it is:** Sales budget targets by product line/group for a period — enables budget vs actual without leaving SmartBusiness.
- **Grain:** Period × seller/line budget row
- **Key columns:** periodo, vendedor, linea/grupo, valor presupuesto
- **Schema (live describe, 5 cols):** `periodo`, `vendedor_codigo`, `linea`, `grupo`, `valor`
- **How it helps decisions:** Which product lines miss budget; commercial plan adjustments mid-period.
- **Gaps / caveats:** Confirm this is the active version vs copy1/copy2 before wiring production KPIs.

### `presupuesto_lineas_copy2`

- **Rows / size (live):** 5,028 rows · 0.2 MB allocated (0.2 MB used)
- **What it is:** Second copy of presupuesto_lineas (snapshot/staging). Not authoritative until confirmed.
- **Grain:** Same as presupuesto_lineas
- **Key columns:** Same family as presupuesto_lineas
- **Schema (live describe, 5 cols):** `periodo`, `vendedor_codigo`, `linea`, `grupo`, `valor`
- **How it helps decisions:** Low — archive/staging only.
- **Gaps / caveats:** Duplicate clutter in BI catalog.

### `presupuesto_lineas_copy1`

- **Rows / size (live):** 4,272 rows · 0.2 MB allocated (0.16 MB used)
- **What it is:** Copy/backup of presupuesto_lineas (historical snapshot or staging). Not authoritative until confirmed.
- **Grain:** Same as presupuesto_lineas
- **Key columns:** Same family as presupuesto_lineas
- **Schema (live describe, 5 cols):** `periodo`, `vendedor_codigo`, `linea`, `grupo`, `valor`
- **How it helps decisions:** Low — do not use for live budget vs actual without business confirmation.
- **Gaps / caveats:** Duplicate; risk of wrong target if wired by mistake.

### `presupuesto_vendedores`

- **Rows / size (live):** 432 rows · 0.07 MB allocated (0.03 MB used)
- **What it is:** Seller-level sales targets (metas) by period.
- **Grain:** Period × seller
- **Key columns:** periodo, vendedor_codigo, valor meta
- **Schema (live describe, 4 cols):** `periodo`, `vendedor_codigo`, `valor`, `vendedor_nombre`
- **How it helps decisions:** Seller ranking vs target, commission fairness, coaching focus.
- **Gaps / caveats:** Confirm active vs presupuesto_vendedores_copy1.

### `presupuesto_vendedores_copy1`

- **Rows / size (live):** 204 rows · 0.07 MB allocated (0.02 MB used)
- **What it is:** Copy of seller budget table. Staging/history — not primary.
- **Grain:** Period × seller
- **Key columns:** Same family as presupuesto_vendedores
- **Schema (live describe, 4 cols):** `periodo`, `vendedor_codigo`, `valor`, `vendedor_nombre`
- **How it helps decisions:** None until confirmed active.
- **Gaps / caveats:** Duplicate.

---

## 3. J3System — decision map by domain

Live count: **968** user tables. Grouped by naming domain. Every table name appears in **§5 Complete J3 appendix**.

### 3.1 Domain roll-up (live)

| Domain | Tables | Approx. rows (sum) | Space (MB) | Decision priority |
|--------|--------|--------------------|------------|-------------------|
| Otros / técnicos | 244 | 12 | 0.2 | P3–P4 case by case |
| Administración maestra (Adm*) | 196 | 7,410,193 | 1386.2 | P1 dimensions/joins |
| Inventario/Ventas (Inv*) | 155 | 10,134,839 | 8391.3 | P1 commercial ops |
| Vehículos (Veh*) | 147 | 4 | 0.1 | P4 niche |
| Contabilidad (Con*) | 68 | 6,578,315 | 1264.6 | P2 finance |
| Nómina (Nom*) | 61 | 581,333 | 87.9 | P3 HR |
| Cartera (Car*) | 47 | 450,011 | 91.9 | P1 credit/cash |
| Hotel (Hot*) | 30 | 999 | 0.5 | P4 unused |
| Servicios (Ser*) | 16 | 2 | 0.1 | P4 niche |
| Activos fijos (Act*) | 2 | 0 | 0.0 | P4 accounting |
| Historial/auditoría (Historia*) | 1 | 422,937 | 159.0 | P3 audit |
| POS | 1 | 0 | 0.0 | P3 if POS used |

### 3.2 Top 25 J3 tables by allocated space (live)

| # | Table | Domain hint | Rows | MB | Decision role |
|---|-------|-------------|------|----|---------------|
| 1 | `InvVentas` | Inv | 563,106 | 6284.33 | Sales header (ERP). Grain: one invoice/document. Links to detalle via VentaID. Authorit… |
| 2 | `AdmAuditoria` | Adm | 3,846,536 | 963.77 | System audit log — ops forensics, not commercial KPIs. |
| 3 | `ConMovimientoDetalle` | Con | 4,552,893 | 924.88 | GL entry lines — largest accounting table; P&L deep dive long-term. |
| 4 | `InvHistoricoEntregas` | Inv | 1,517,872 | 482.77 | Delivery/dispatch history — OTIF, lead time factura→entrega. |
| 5 | `InvVentasDetalle` | Inv | 1,554,601 | 352.72 | Sales lines with AlmacenID — physical warehouse attribution used by manager report ware… |
| 6 | `ConMovimiento` | Con | 767,037 | 269.74 | GL entry headers. |
| 7 | `InvEstadoFacturaElectronica` | Inv | 527,408 | 265.77 | DIAN e-invoice status — compliance % accepted/rejected. |
| 8 | `InvVentasTotales` | Inv | 552,995 | 179.3 | Aggregated sale totals helper; useful for header-level amounts without re-aggregating l… |
| 9 | `InvDetalleExistencias` | Inv | 317,628 | 168.84 | Stock by warehouse×article — stockout risk, days of cover with velocity from banco_datos. |
| 10 | `HistoriaAdmArticulos` | Other | 422,937 | 159.02 | Article change history — price/cost/description audit trail. |
| 11 | `InvFacturaCanceladas` | Inv | 549,928 | 136.65 | Cancelled invoices — void analysis and revenue quality. |
| 12 | `AdmGuardaPagos` | Adm | 642,362 | 124.05 | Administration / master-data or system config table (Adm*). |
| 13 | `InvCotizaDetalle` | Inv | 467,780 | 90.78 | Quotation lines — conversion analysis quote→sale, lost quotes by seller/product. |
| 14 | `InvDevolucionVentas` | Inv | 18,160 | 85.92 | Formal sales returns documents (ERP) — better than only negative lines in banco_datos. |
| 15 | `InvFacturaPorCancelarDetalle` | Inv | 1,510,874 | 76.59 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| 16 | `NomInfoDesprendiblesDevDed` | Nom | 534,558 | 67.77 | Payroll liquidation / payslip table. |
| 17 | `AdmTercerosMovimientoCab` | Adm | 768,540 | 64.8 | Third-party (customer/supplier) master or movement table. |
| 18 | `InvTemporalImpuestoGeneralHKA` | Inv | 1,357,827 | 51.02 | Temporary/staging inventory or tax processing table. |
| 19 | `AdmTerceros` | Adm | 60,997 | 47.7 | Customers/suppliers master (NIT, contact, cellphone used by cotizaciones scripts). |
| 20 | `AdmAuditoriaPermisos` | Adm | 240,789 | 47.09 | Admin audit / permission change log. |
| 21 | `InvFacturaPorCancelar` | Inv | 547,662 | 41.3 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| 22 | `InvImpresionFactura` | Inv | 70,018 | 40.86 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| 23 | `CarCarteraCliente` | Car | 148,962 | 33.84 | ERP customer AR open items — credit risk source of truth. |
| 24 | `Admtransac` | Adm | 84,610 | 32.48 | Administration / master-data or system config table (Adm*). |
| 25 | `ConSaldosContabilidad` | Con | 245,574 | 29.41 | Account balances snapshot. |

### 3.3 Decision-critical J3 tables (deeper)

Column-level describe for these tables is in scratch `schemas_j3_critical.json`.

#### `AdmAlmacen`
- **Volume:** 14 rows · 0.02 MB
- **Purpose / decisions:** Warehouse master — join from AlmacenID for FLO/BD6/SUR etc.
- **Key columns (live, first fields):** `AlmacenID`, `AlmacenCodigo`, `AlmacenNombre`, `AlmacenEstado`, `VentaID`, `AlmacenDetalle`, `ArticulosID`, `PideCotelco`, `Incluye`, `DescargaDe`, `NumCamas`, `Reservas`, `Piso`, `Consignacion` … (+1 more)

#### `AdmArticulos`
- **Volume:** 9,789 rows · 9.2 MB
- **Purpose / decisions:** Article/SKU master in ERP.
- **Key columns (live, first fields):** `ArticulosID`, `ArticulosCodigo`, `ArticulosNombre`, `ArticulosTipo`, `LineasID`, `ArticulosMargen`, `ArticulosUltmoCosto`, `ArticulosIncremento`, `ArticulosCosto`, `ArticulosVenta`, `GruposID`, `ArticulosManejaDecimal`, `ArticulosFechaInicial`, `ArticulosFechaVence` … (+53 more)

#### `AdmAuditoria`
- **Volume:** 3,846,536 rows · 963.77 MB
- **Purpose / decisions:** System audit log — ops forensics, not commercial KPIs.
- **Key columns (live, first fields):** `AuditoriaID`, `Docto`, `Numero`, `Fecha`, `Modulo`, `Accion`, `UsuarioID`, `NombreUsuario`, `Tercero`, `Valor`

#### `AdmDocumentos`
- **Volume:** 67 rows · 0.24 MB
- **Purpose / decisions:** Document type catalog (codes mapped to DocumentosCodigo).
- **Key columns (live, first fields):** `DocumentosID`, `DocumentosCodigo`, `DocumentosTipo`, `SubCentroCostoID`, `DocumentosNombre`, `DocumentosNumeroInicial`, `DocumentosAutomatico`, `DocumentosFormato`, `DocumentosResolucion`, `DocumentosAutoriza`, `DocumentosFechaAutoriza`, `DocumentosCantidadRegistros`, `DocumentosForma`, `DocumentosRotacion` … (+36 more)

#### `AdmPrecios`
- **Volume:** 73,661 rows · 10.9 MB
- **Purpose / decisions:** Price lists.
- **Key columns (live, first fields):** `PreciosID`, `TarifasID`, `ArticulosID`, `PreciosIncremento`, `PreciosValor`, `Cantidad`

#### `AdmTerceros`
- **Volume:** 60,997 rows · 47.7 MB
- **Purpose / decisions:** Customers/suppliers master (NIT, contact, cellphone used by cotizaciones scripts).
- **Key columns (live, first fields):** `TercerosID`, `TercerosTipoDoc`, `TercerosIdentificacion`, `TercerosDv`, `TercerosPrimerNombre`, `TercerosSegundoNombre`, `TercerosPrimerApellido`, `TercerosSegundoApellido`, `TercerosRazonSocial`, `TercerosNombres`, `CiudadID`, `TercerosTeleFax`, `TercerosCelular`, `TercerosDireccion` … (+108 more)

#### `CarCarteraCliente`
- **Volume:** 148,962 rows · 33.84 MB
- **Purpose / decisions:** ERP customer AR open items — credit risk source of truth.
- **Key columns (live, first fields):** `IdCartera`, `DocumentosID`, `NumeroDocto`, `NumeroFactura`, `Fecha`, `FechaVence`, `TercerosID`, `ValorCartera`, `SaldoCartera`, `Detalle`, `VendedorID`, `Tipo`, `Estado`, `Codigo` … (+8 more)

#### `CarCarteraProveedor`
- **Volume:** 20,130 rows · 8.65 MB
- **Purpose / decisions:** Supplier AP open items — cash planning.
- **Key columns (live, first fields):** `IdCartera`, `DocumentosID`, `NumeroDocto`, `NumeroFactura`, `Fecha`, `FechaVence`, `TercerosID`, `ValorCartera`, `SaldoCartera`, `Detalle`, `VendedorID`, `Tipo`, `CuentasPucID`, `SubCentroCostoID` … (+3 more)

#### `CarPagosCliente`
- **Volume:** 58,725 rows · 15.84 MB
- **Purpose / decisions:** Customer payment headers.
- **Key columns (live, first fields):** `CarPagosID`, `DocumentosID`, `NumeroDocumento`, `Fecha`, `Cheque`, `TercerosID`, `VendedorID`, `Detalle`, `Maquina`, `UsuarioCrea`, `UsuarioModifica`

#### `CarPagosClienteDetalle`
- **Volume:** 179,949 rows · 23.34 MB
- **Purpose / decisions:** Customer payment application detail.
- **Key columns (live, first fields):** `DetalleCarteraID`, `CarPagosID`, `IdCartera`, `ValorDescargar`, `ValorReteFuente`, `ValorReteIca`, `ValorReteIva`, `ValorReteOtra`, `ValorDescuento`, `Detalle`, `Interes`, `OtrosDescuentos`

#### `CarPagosProveedor`
- **Volume:** 12,242 rows · 2.4 MB
- **Purpose / decisions:** Supplier payment headers.
- **Key columns (live, first fields):** `CarPagosID`, `DocumentosID`, `NumeroDocumento`, `Fecha`, `Cheque`, `TercerosID`, `VendedorID`, `Detalle`, `Maquina`, `UsuarioCrea`, `UsuarioModifica`

#### `CarPagosProveedorDetalle`
- **Volume:** 21,475 rows · 2.96 MB
- **Purpose / decisions:** Supplier payment detail.
- **Key columns (live, first fields):** `DetalleCarteraID`, `CarPagosID`, `IdCartera`, `ValorDescargar`, `ValorReteFuente`, `ValorReteIca`, `ValorReteIva`, `ValorReteOtra`, `ValorDescuento`, `Detalle`, `Interes`, `OtrosDescuentos`

#### `ConMovimiento`
- **Volume:** 767,037 rows · 269.74 MB
- **Purpose / decisions:** GL entry headers.
- **Key columns (live, first fields):** `MovimientoID`, `DocumentosID`, `MovimientoNumero`, `MovimientoCheque`, `MovimientoFecha`, `VendedorID`, `MovimientoDetalle`, `MovimientoPeriodo`, `MovimientoAno`, `MovimientoFactura`, `Tipo`, `Maquina`, `UsuarioCrea`, `UsuarioModifica` … (+2 more)

#### `ConMovimientoDetalle`
- **Volume:** 4,552,893 rows · 924.88 MB
- **Purpose / decisions:** GL entry lines — largest accounting table; P&L deep dive long-term.
- **Key columns (live, first fields):** `MovimientoDetalleID`, `MovimientoID`, `CuentasPucID`, `TercerosID`, `SubCentroCostoID`, `MovimientoDetalleDetalle`, `MovimientoDetalleTipo`, `MovimientoDetalleValor`, `AreasID`, `ProyectoID`, `NroAutorizacion`, `ActivoID`

#### `ConSaldosContabilidad`
- **Volume:** 245,574 rows · 29.41 MB
- **Purpose / decisions:** Account balances snapshot.
- **Key columns (live, first fields):** `SaldosID`, `CuentasPucID`, `SaldosSigno`, `SubCentroCostoID`, `TercerosID`, `SaldosAno`, `SaldosValor`, `AreasID`, `ProyectoID`, `Tipo`

#### `HistoriaAdmArticulos`
- **Volume:** 422,937 rows · 159.02 MB
- **Purpose / decisions:** Article change history — price/cost/description audit trail.
- **Key columns (live, first fields):** `HistoricoID`, `Fecha`, `ArticulosID`, `Tipo`, `Codigo`, `Nombre`, `LineasID`, `GruposID`, `Incremento`, `Margen`, `CostoPromedio`, `PrecioVenta`, `Detalle`, `ArticulosID_New` … (+10 more)

#### `InvCompras`
- **Volume:** 42,167 rows · 12.96 MB
- **Purpose / decisions:** Purchase headers — supply cost and supplier spend.
- **Key columns (live, first fields):** `CompraID`, `DocumentosID`, `NumeroDocumento`, `FacturaNumero`, `Fecha`, `DiasCredito`, `TercerosID`, `VendedorID`, `Detalle`, `RetencionesID`, `OrdenCompraID`, `Maquina`, `UsuarioCrea`, `UsuarioModifica` … (+2 more)

#### `InvComprasDetalle`
- **Volume:** 112,829 rows · 20.96 MB
- **Purpose / decisions:** Purchase lines — cost inflation, supplier mix by SKU.
- **Key columns (live, first fields):** `CompraDetalleID`, `CompraID`, `ArticulosID`, `AlmacenID`, `Cantidad`, `CostoSinIva`, `CostoMasIva`, `PorDescuento`, `ValorDescuento`, `CostoAnterior`, `CantidadAnterior`, `Ipoconsumo`, `Detalle`, `Flete` … (+12 more)

#### `InvCotizaCab`
- **Volume:** 79,643 rows · 26.52 MB
- **Purpose / decisions:** Quotation headers — top of commercial funnel before invoice.
- **Key columns (live, first fields):** `VentaID`, `DocumentosID`, `NumeroDocumento`, `Fecha`, `DiasCredito`, `TercerosID`, `VendedorID`, `Detalle`, `FormaPago`, `ValidezOferta`, `TiempoEntrega`, `LugarEntrega`, `Garantia`, `Sucursales` … (+11 more)

#### `InvCotizaDetalle`
- **Volume:** 467,780 rows · 90.78 MB
- **Purpose / decisions:** Quotation lines — conversion analysis quote→sale, lost quotes by seller/product.
- **Key columns (live, first fields):** `VentaDetalleID`, `VentaID`, `ArticulosID`, `AlmacenID`, `Cantidad`, `VentaSinIva`, `VentaMasIva`, `PorDescuento`, `ValorDescuento`, `VentaMinima`, `ValorCosto`, `Ipoconsumo`, `Detalle`, `CantidadCop` … (+3 more)

#### `InvDetalleExistencias`
- **Volume:** 317,628 rows · 168.84 MB
- **Purpose / decisions:** Stock by warehouse×article — stockout risk, days of cover with velocity from banco_datos.
- **Key columns (live, first fields):** `DetalleExistenciasID`, `ExistenciasID`, `Ano`, `AlmacenID`, `SaldoInicial`, `SaldoActual`, `StockMinimo`, `StockMaximo`, `EntradasEne`, `SalidasEne`, `CostoEne`, `VentaEne`, `EntradasFeb`, `SalidasFeb` … (+42 more)

#### `InvDevolucionVentas`
- **Volume:** 18,160 rows · 85.92 MB
- **Purpose / decisions:** Formal sales returns documents (ERP) — better than only negative lines in banco_datos.
- **Key columns (live, first fields):** `DevolucionID`, `DocumentosID`, `NumeroDocumento`, `Fecha`, `TercerosID`, `VendedorID`, `Detalle`, `Maquina`, `UsuarioCrea`, `UsuarioModifica`, `Cufe`, `CodigoQR`, `tafacele`, `taexpdia` … (+10 more)

#### `InvDevolucionVentasDetalle`
- **Volume:** 28,946 rows · 4.02 MB
- **Purpose / decisions:** Return lines for product/category return rate.
- **Key columns (live, first fields):** `DevolucionDetalleID`, `DevolucionID`, `ArticulosID`, `AlmacenID`, `Cantidad`, `VentaSinIva`, `VentaMasIva`, `PorDescuento`, `ValorDescuento`, `VentaMinima`, `ValorCosto`, `Ipoconsumo`, `Detalle`, `DoctosPadresHijoID` … (+5 more)

#### `InvDevolucionVentasTotales`
- **Volume:** 18,109 rows · 4.34 MB
- **Purpose / decisions:** Return totals helper.
- **Key columns (live, first fields):** `TotalesID`, `DevolucionID`, `SubTotal`, `Exento`, `Excluido`, `Iva10`, `Iva16`, `Gravado10`, `Gravado16`, `Ipoconsumo`, `ReteFuente`, `ReteIca`, `ReteIva`, `Descuento` … (+8 more)

#### `InvEstadoFacturaElectronica`
- **Volume:** 527,408 rows · 265.77 MB
- **Purpose / decisions:** DIAN e-invoice status — compliance % accepted/rejected.
- **Key columns (live, first fields):** `ID`, `Tabla`, `CampoID`, `DocumentosID`, `Numero`, `TercerosID`, `FechaFactura`, `FechaEnvio`, `Enviado`, `Acuse`, `EstatusAcuse`, `DetalleAcuseCliente`, `Codigo`, `Documento` … (+9 more)

#### `InvExistencias`
- **Volume:** 9,786 rows · 0.53 MB
- **Purpose / decisions:** Higher-level stock summary per article (companion to detalle).
- **Key columns (live, first fields):** `ExistenciasID`, `ArticulosID`

#### `InvFacturaCanceladas`
- **Volume:** 549,928 rows · 136.65 MB
- **Purpose / decisions:** Cancelled invoices — void analysis and revenue quality.
- **Key columns (live, first fields):** `ID`, `CancelarID`, `Docto`, `Numero`, `Fecha`, `Cedula`, `Nombres`, `Digitador`, `FormaDePago`, `Valor`, `UsuarioID`, `FechaRegistro`

#### `InvHistoricoEntregas`
- **Volume:** 1,517,872 rows · 482.77 MB
- **Purpose / decisions:** Delivery/dispatch history — OTIF, lead time factura→entrega.
- **Key columns (live, first fields):** `ID`, `Tipo`, `Consecutivo`, `Docto`, `Numero`, `FechaFactura`, `FechaEntrega`, `Cliente`, `Codigo`, `Descripcion`, `Almacen`, `CantidadFacturada`, `EntregaAcumulada`, `Saldo` … (+5 more)

#### `InvTraslados`
- **Volume:** 10,260 rows · 3.59 MB
- **Purpose / decisions:** Inter-warehouse transfer headers — logistics rebalancing.
- **Key columns (live, first fields):** `TrasladosID`, `DocumentosID`, `Numero`, `Fecha`, `VendedorID`, `Detalle`, `SubCentroCostoID1`, `SubCentroCostoID2`, `UsuarioID1`, `UsuarioID2`, `UsuarioCrea`, `UsuarioModifica`

#### `InvTrasladosDetalle`
- **Volume:** 28,400 rows · 2.27 MB
- **Purpose / decisions:** Transfer lines — stock movement between bodegas.
- **Key columns (live, first fields):** `DetalleTrasladoID`, `TrasladosID`, `ArticulosID`, `AlmacenSale`, `AlmacenEntra`, `Cantidad`, `Detalle`, `ValorTraslado`, `ReferenciaID`, `Costo`

#### `InvVentas`
- **Volume:** 563,106 rows · 6284.33 MB
- **Purpose / decisions:** Sales header (ERP). Grain: one invoice/document. Links to detalle via VentaID. Authoritative commercial document list.
- **Key columns (live, first fields):** `VentaID`, `DocumentosID`, `NumeroDocumento`, `Fecha`, `DiasCredito`, `TercerosID`, `VendedorID`, `Detalle`, `TarifasID`, `Maquina`, `UsuarioCrea`, `UsuarioModifica`, `Cufe`, `CodigoQR` … (+15 more)

#### `InvVentasDetalle`
- **Volume:** 1,554,601 rows · 352.72 MB
- **Purpose / decisions:** Sales lines with AlmacenID — physical warehouse attribution used by manager report warehouse breakdown.
- **Key columns (live, first fields):** `VentaDetalleID`, `VentaID`, `ArticulosID`, `AlmacenID`, `Cantidad`, `VentaSinIva`, `VentaMasIva`, `PorDescuento`, `ValorDescuento`, `VentaMinima`, `ValorCosto`, `Ipoconsumo`, `Detalle`, `DoctosPadresHijoID` … (+18 more)

#### `InvVentasTotales`
- **Volume:** 552,995 rows · 179.3 MB
- **Purpose / decisions:** Aggregated sale totals helper; useful for header-level amounts without re-aggregating lines.
- **Key columns (live, first fields):** `TotalesID`, `VentaID`, `SubTotal`, `Exento`, `Excluido`, `Iva10`, `Iva16`, `Gravado10`, `Gravado16`, `Ipoconsumo`, `ReteFuente`, `ReteIca`, `ReteIva`, `Descuento` … (+24 more)

---

## 4. Cross-database decision matrix

| Decision question | Best source | Supporting tables | Status in repo |
|-------------------|-------------|-------------------|----------------|
| Revenue & margin by period/seller/product | `banco_datos` | `productos_adicional` | Strong (manager report, KPI pack, Vanna) |
| Clean brand/category | `productos_adicional` JOIN | `AdmArticulos`, `HistoriaAdmArticulos` | Partial — JOIN not universal |
| Physical warehouse of sale | J3 `InvVentasDetalle`+`AdmAlmacen` | `banco_datos.AlmacenCodigo` | Partial (warehouse branch in manager report) |
| Budget vs actual | `presupuesto_*` + `banco_datos` | — | Gap — data present, reports thin |
| AR aging / credit risk | `banco_cartera` | `CarCarteraCliente`, `AdmTerceros` | Gap — cartera underused |
| Quote → invoice funnel | `InvCotizaCab/Detalle` | `InvVentas`, `AdmTerceros` | Gap (cellphone enrich only) |
| Stockouts / cover days | `InvDetalleExistencias` | `banco_datos` velocity | Gap |
| Delivery OTIF | `InvHistoricoEntregas` | `InvVentas` | Gap |
| Returns quality | `InvDevolucionVentas*` | negatives in `banco_datos` | Partial |
| E-invoice compliance | `InvEstadoFacturaElectronica` | — | Gap |
| Supplier spend / AP | `InvCompras*`, `CarCarteraProveedor` | — | Gap |
| GL / P&L deep finance | `ConMovimiento*` | `ConSaldosContabilidad` | Long-term |
| Payroll cost | `Nom*` | — | Out of commercial board |

### Immediate decision priorities

1. **Wire `banco_cartera` into weekly KPI board** — small table (2,895 rows), high credit risk value.
2. **Budget vs actual** using active `presupuesto_vendedores` / `presupuesto_lineas` (confirm copies).
3. **Mandatory JOIN `productos_adicional`** for brand KPIs.
4. **Quote funnel + stock + OTIF** from J3 for commercial ops depth.
5. **Do not** prioritize Veh/Hot/Nom modules for store sales decisions.

---

## 5. Complete J3System table appendix (every table)

One purpose line per table, ordered by domain then descending size. Live row/size from this run (partition-correct counts).

### 5.1 Otros / técnicos (244 tables · 0.2 MB)

Cross-cutting control documents, staging, misc modules, and technical/system tables without a clear Inv/Adm/Con/Car/Nom prefix.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `EduInfoDatosEstudiantes` | 2 | 0.07 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GruposActivos` | 1 | 0.07 | Point-of-sale related table. |
| `UbicacionActivos` | 5 | 0.02 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `LineasActivos` | 4 | 0.02 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `UserWinJ3` | 0 | 0.02 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduAsignaturas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduSalonAgisnacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduListaCalificacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduGrupos` | 0 | 0.0 | Point-of-sale related table. |
| `EduInfoListadoLogros` | 0 | 0.0 | Pricing / price list related table. |
| `EduDiscDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoListaXDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduParamMatricula` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduDiscEstud` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoNotaGeneralMateriasEstu` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoPazySalvoGrupos` | 0 | 0.0 | Point-of-sale related table. |
| `GanSacrificio` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduParamPrioridad` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduAutores` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanTrasladosDet` | 0 | 0.0 | Warehouse transfer operational table. |
| `EduOrdenListaDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduParamMatriculaGrupos` | 0 | 0.0 | Point-of-sale related table. |
| `EduInfoProcesoEducativo` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoPlanilla` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCalifLogroDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubConceptosQrs` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduPeriodoLect` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCalificacionDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduHorarioSemanal` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoPreguntasEvaluarDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCartera` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubEstrato` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduGenograma` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduConceptosJornada` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduImfoListadoDocentes` | 0 | 0.0 | Pricing / price list related table. |
| `EduInfoPuesto` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduImfoListaEstudiantes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoResultados` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `ComFactura` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfConceptos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInformeCartera` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduSubConceptos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCriteriosPreguntas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduObservacionesDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoResConsolid` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubFacturacionTemporal` | 0 | 0.0 | Temporary/staging inventory or tax processing table. |
| `EduCreacionTitulo` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfEstadistica` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `ComPropiedad` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `HsReporteInicial` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `Table_1` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduComunicacionConceptos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCursos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfBeneficiarios` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduPagos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduEstVacunas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `Acompanantes_Rest_Det` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `HseqProgramas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `ComPropiedadArrendatarios` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfEstadisticaGrupos` | 0 | 0.0 | Point-of-sale related table. |
| `Acompanantes_Rest` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfEstadisticaPrestamo` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoDirectorioDocentes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `HseqRegistroCronograma` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanMovtoExistencias` | 0 | 0.0 | Stock levels, kardex, or physical inventory table. |
| `NiifPoliticasContables` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduPagosDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubComunicaDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `ComCartera` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoCuadroHonor` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoControlExisteBiblioteca` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubCobros` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubVivienda` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoCertificadoMatricula` | 0 | 0.0 | Tax certificates / withholding accounting table. |
| `EduConceptoEvaluacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `NotasCreditoDebito` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduConceptosComunicacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `CafParaGramos_Factor` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoAusentismoEstudiantes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `Tabla1` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduMetodoAsignaturas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfInvBiblioteca` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanDesFactCanal` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `ComFacturaDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoCalificacionDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalPacientes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubInfConsumos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `OrdNewEstadosOrden` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `NotasCreditoDebitoTotales` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoBoletinLogros` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoAusnetismoDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `NotasCreditoDebitoDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoCalificacionGeneralDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalProfesionales` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubLiquidaciones` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoCarnetEstudiante` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalEntidadesSalud` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoDocFaltantes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduFacturaMatricula` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoExistenciasBiblioteca` | 0 | 0.0 | Stock levels, kardex, or physical inventory table. |
| `EduParamMatricDocumExigido` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduProcesoEducativo` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduListaRecuperaciones` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduObservaciones` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanExistencias` | 0 | 0.0 | Stock levels, kardex, or physical inventory table. |
| `OrdTecnicos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubLiquidacionOrtCobros` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GerInfoContab` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduListaHabilitaciones` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduNotasClasico` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanParteCanal` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduDocenteAreasAsignadas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanFacturaCanal` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalHistorial` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `OrdInveVehiculos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanTipoSacrificio` | 0 | 0.0 | Point-of-sale related table. |
| `EduGrupoNiveles` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubLiquidacionesDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanTempLiquidacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanValorTarifa` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `OrdHorasTecnicos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduListaDetalles` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `OrdVehiculos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `CafRemision` | 0 | 0.0 | Remission / delivery note operational table. |
| `SalTarifas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GerParametros` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `CafLiquidacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `MejorasActivosFijos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanInfoInventarioSemovientes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `OrdHorasTecnicos_Cotiza` | 0 | 0.0 | Quotations / quote-related commercial table. |
| `GanLiquidacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `ComSectores` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanInfoTraslados` | 0 | 0.0 | Warehouse transfer operational table. |
| `GanCompraSemovientes` | 0 | 0.0 | Purchasing operational table. |
| `GanDesExistencias` | 0 | 0.0 | Stock levels, kardex, or physical inventory table. |
| `GanInfoFactCanal` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanInfCompraGanadoPie` | 0 | 0.0 | Purchasing operational table. |
| `EduPeriodosAcademicos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanCompraCanal` | 0 | 0.0 | Purchasing operational table. |
| `EduCodifEstudiantes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubRutas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubRelacionFact` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `AlqObras` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubMedidores` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SegurosPolizasActivosFijos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduRegistroAusenciaDocente` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubBarrios` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubFacturacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduTabObservaciones` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `HseqActividades` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `AlqInformeAlquiler` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `AlqInfoAlquiler` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `AlqProductos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduPrestamoLibro` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduAsignacionSalones` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `CafCupos` | 0 | 0.0 | Point-of-sale related table. |
| `EduValoracionSicologica2` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `DeterioroActivosFijos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduValorNota` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCalifLogro` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInstitucion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduFormaPago` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoDirectorioEstudiantes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCantidadAsignaturas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduGrupoAsignatura` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduListaCumpleanos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubFormasPago` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubHistorialLiq` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduDetalleFacturaMatricula` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `OrdSegurosVehiculo` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduOrdenLista` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduVacunas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduAreas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoXgrupo` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduAusenciaEstudiante` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduDocumExigEstudiantes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoValoracionSicologica` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubAutorizaciones` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanTrasladosCab` | 0 | 0.0 | Warehouse transfer operational table. |
| `ComConceptosFacturacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanCompuestoSacrificio` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduSistemaEvaluacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoDisciplina` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `DocumentosActivosFijos` | 0 | 0.0 | Document type / document control admin table. |
| `EduParametrosLogros` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduTemas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduValoracionSicologica` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCertificadoEstudio` | 0 | 0.0 | Tax certificates / withholding accounting table. |
| `EduSalones` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduMesesConceptos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduMesesPension` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduServicios` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduMesesDiferido` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduClave` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanFleteFactura` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubQuejasReclamos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduMetodoSencillo` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubReAjustes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCursosAsignados` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanDescripcionSacrificio` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubLiquidacionMes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCriterioEvaluacionAlfabetico` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubPropiedad` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCriterioEvaluacionNumerico` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `PubComunica` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalInfoProfesionales` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanDescripcionCompra` | 0 | 0.0 | Purchasing operational table. |
| `GerParamDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `MovimientosActivosFijos` | 0 | 0.0 | Accounting journal movement table. |
| `SalInfoContratos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduEstServicios` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduUsuariosJornadas` | 0 | 0.0 | User session / user admin table. |
| `Tabla2` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanDesCompCanal` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduInfoDiscEstadistica` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCreacionTituloDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `AlqAlquiler` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCreacionMetodosEvaluacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `AlqAlquilerDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `OrdOrdenServicioDetalle` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduHorarioEstudiantil` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `HseqSubProgramas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanTransportador` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `OrdOrdenServicio` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalCitas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalTipoRegimen` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduEstudiantes` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalTipoConsultas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduDocenteEstudioRealizado` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `ParTiposVehiculo` | 0 | 0.0 | Point-of-sale related table. |
| `EduDocGrupos` | 0 | 0.0 | Point-of-sale related table. |
| `GanDestare` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `ParMarcasVehiculo` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalTipoTarifa` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalConsultas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduDocenteExperienciaLaboral` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `GanDocumSacrificio` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalProfEspecializacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalContratos` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalEspecializacion` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduDocenteJornada` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `EduCursoTotal` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |
| `SalCausasExternas` | 0 | 0.0 | ERP operational/technical table — see domain grouping; low priority for commercial decision dashboards unless domain … |

### 5.2 Administración maestra (Adm*) (196 tables · 1386.2 MB)

Master data and system admin: third parties (customers/suppliers), articles, warehouses, prices, users, permissions, audit. Required joins for human-readable dimensions.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `AdmAuditoria` | 3,846,536 | 963.77 | System audit log — ops forensics, not commercial KPIs. |
| `AdmGuardaPagos` | 642,362 | 124.05 | Administration / master-data or system config table (Adm*). |
| `AdmTercerosMovimientoCab` | 768,540 | 64.8 | Third-party (customer/supplier) master or movement table. |
| `AdmTerceros` | 60,997 | 47.7 | Customers/suppliers master (NIT, contact, cellphone used by cotizaciones scripts). |
| `AdmAuditoriaPermisos` | 240,789 | 47.09 | Admin audit / permission change log. |
| `Admtransac` | 84,610 | 32.48 | Administration / master-data or system config table (Adm*). |
| `AdmConsecutivos` | 551,019 | 21.21 | Document sequence / consecutive numbering control. |
| `AdmReimprimir` | 569,683 | 15.59 | Administration / master-data or system config table (Adm*). |
| `AdmDetalleAccesoDatos` | 146,413 | 12.66 | Administration / master-data or system config table (Adm*). |
| `AdmComisionPorArticulo` | 269,041 | 10.96 | Article/SKU master or article-related admin table. |
| `AdmPrecios` | 73,661 | 10.9 | Price lists. |
| `AdmAuditoriaArticulos` | 45,235 | 9.71 | Admin audit / permission change log. |
| `AdmArticulos` | 9,789 | 9.2 | Article/SKU master in ERP. |
| `AdmBuscarPermisos` | 31,740 | 5.62 | User module permissions / access control. |
| `AdmProveedorArt` | 18,734 | 1.46 | Article/SKU master or article-related admin table. |
| `AdmUsuariosIniciados` | 6,742 | 1.02 | User session / user admin table. |
| `AdmPerInve` | 18,145 | 0.9 | User module permissions / access control. |
| `AdmCuentasPuc` | 582 | 0.7 | Chart of accounts / PUC admin. |
| `AdmPerAdmon` | 7,769 | 0.39 | User module permissions / access control. |
| `AdmPerimisoModuloUsu` | 1,598 | 0.34 | User module permissions / access control. |
| `AdmPerDocumentos` | 2,445 | 0.27 | User module permissions / access control. |
| `AdmDocumentos` | 67 | 0.24 | Document type catalog (codes mapped to DocumentosCodigo). |
| `AdmParaIva` | 45 | 0.21 | Tax / IVA operational table. |
| `AdmBarras` | 2 | 0.21 | Administration / master-data or system config table (Adm*). |
| `AdmPerConta` | 2,915 | 0.2 | User module permissions / access control. |
| `AdmResponsabilidadFiscalTercero` | 1,786 | 0.2 | Third-party (customer/supplier) master or movement table. |
| `AdmConsecutivoFiscal` | 1,538 | 0.2 | Document sequence / consecutive numbering control. |
| `AdmPerNomina` | 293 | 0.2 | User module permissions / access control. |
| `AdmPais` | 231 | 0.2 | Administration / master-data or system config table (Adm*). |
| `AdmConceptoDian` | 189 | 0.2 | Administration / master-data or system config table (Adm*). |
| `AdmRegistrosEliminados` | 108 | 0.2 | Administration / master-data or system config table (Adm*). |
| `AdmUsuarios` | 96 | 0.2 | User session / user admin table. |
| `AdmGenerarPermisos` | 0 | 0.2 | User module permissions / access control. |
| `AdmFormasPagoUsuario` | 239 | 0.14 | User session / user admin table. |
| `AdmTarifasUsuario` | 206 | 0.14 | User session / user admin table. |
| `AdmPerCartera` | 1,158 | 0.13 | User module permissions / access control. |
| `AdmPerGeneral` | 1,210 | 0.08 | User module permissions / access control. |
| `AdmCiudad` | 1,126 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmAbreDias` | 398 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmPerInfoCaja` | 330 | 0.07 | User module permissions / access control. |
| `AdmCuentasFormatos` | 239 | 0.07 | Chart of accounts / PUC admin. |
| `AdmListaConceptoDian` | 183 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmRegistrosEliminadosCVD` | 165 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmPerServiciosPub` | 154 | 0.07 | User module permissions / access control. |
| `AdmControlFormularios` | 70 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmRetenciones` | 35 | 0.07 | Withholding tax (retención) on sales/returns. |
| `AdmBasesInventarios` | 24 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmTiposNegocio` | 17 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmAlmacenUsuario` | 15 | 0.07 | User session / user admin table. |
| `AdmFormatosDoctos` | 10 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmBloquearDoctos` | 5 | 0.07 | Administration / master-data or system config table (Adm*). |
| `Admfacele` | 5 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmUVT` | 5 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmBasesInventariosVenta` | 3 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmIncbp` | 3 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmExamenesEmpleados` | 3 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmMesesPeriodosUsuarios` | 2 | 0.07 | User session / user admin table. |
| `AdmDetalleAddDoctos` | 2 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmAbrirPeriodosUsuarios` | 2 | 0.07 | User session / user admin table. |
| `AdmActividadesEconomicas` | 1 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmSubCentrosUsuario` | 1 | 0.07 | User session / user admin table. |
| `AdmClaveGraph` | 1 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmTarifaTerceros` | 1 | 0.07 | Third-party (customer/supplier) master or movement table. |
| `AdmFamiliasGrupos` | 1 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmComSaludPension` | 0 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmInfoRecordatorios` | 0 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmProyectos` | 0 | 0.07 | Administration / master-data or system config table (Adm*). |
| `AdmSubCentroCosto` | 34 | 0.03 | Administration / master-data or system config table (Adm*). |
| `AdmCentroCosto` | 4 | 0.03 | Administration / master-data or system config table (Adm*). |
| `AdmComunica` | 231 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmAccesoDatos` | 93 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmGrupos` | 89 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmVendedor` | 84 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmCuentasLineas` | 63 | 0.02 | Chart of accounts / PUC admin. |
| `AdmModulosAdd` | 63 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmFormasPago` | 39 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmFormatos` | 36 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmDepartamento` | 34 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmMesesPeriodos` | 25 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmTablasBasicas` | 23 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmProgramas` | 17 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmAlmacen` | 14 | 0.02 | Warehouse master — join from AlmacenID for FLO/BD6/SUR etc. |
| `AdmLineas` | 13 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmTarifas` | 8 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmAbrirPeriodos` | 6 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmClavesAcceso` | 1 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmMedidas` | 1 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmEmpresa` | 1 | 0.02 | Administration / master-data or system config table (Adm*). |
| `AdmLinNominaTerceros` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `AdmObservaciones` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmTipoMonedas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmParamComiC` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmOtrosValores` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmParamDoctosCartera` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmCompromisosVigentes` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmAbreDiasUsuarios` | 0 | 0.0 | User session / user admin table. |
| `AdmTercerosParticipantes` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `AdmPerVehiculos` | 0 | 0.0 | User module permissions / access control. |
| `AdmLineasUsuarios` | 0 | 0.0 | User session / user admin table. |
| `AdmMaquinas_Pc` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmMensaje` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmEmailTerceros` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `AdmModificadores_Art_Res` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmLotesDetalle` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmLinNomina` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmTarTerUsuarios` | 0 | 0.0 | User session / user admin table. |
| `AdmSupervisores` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmContactosTerceros` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `AdmDoctosPuntos` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmDoctosReteVentas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmFiltroPOS` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmTerCastigado` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmFormasPagosVentaMotos` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmFiltroPOSFechas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmViaticos` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmTrmDetalle` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmPerGanadero` | 0 | 0.0 | User module permissions / access control. |
| `AdmRetencionTercero` | 0 | 0.0 | Withholding tax (retención) on sales/returns. |
| `AdmViaticosDetalle` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmParametrosConsignacion` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmTrm` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmClavesAccesoPOS` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmFormasPagoDias` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmPermisosPost` | 0 | 0.0 | User module permissions / access control. |
| `AdmSubArticulos` | 0 | 0.0 | Article/SKU master or article-related admin table. |
| `AdmParametros` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmEmpaques` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmCompuestoCab` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmUbicacion` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmVarios` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmParametroAfilia` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmParametroCategoria` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmUbicacionAlmacen` | 0 | 0.0 | Warehouse master or warehouse-related admin. |
| `AdmCuentasTablasBasicas` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `AdmTiquete` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmDescuentoFormaPago` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmEquivalenciasNiifPucLocal` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `AdmTarifasDocumentos` | 0 | 0.0 | Document type / document control admin table. |
| `AdmParametrosFormasPago` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmCuentasSubCentroCosto` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `AdmSeriesArticulo` | 0 | 0.0 | Article/SKU master or article-related admin table. |
| `AdmSubArticulosDet` | 0 | 0.0 | Article/SKU master or article-related admin table. |
| `AdmDepreciacion` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmCuentasGrupos_Otras` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `AdmDoctosTarifas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmTarjetas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmPadreArticulos` | 0 | 0.0 | Article/SKU master or article-related admin table. |
| `AdmCuentasDeterioroInve` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `AdmCuentasDeterioro` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `AdmCapacidad` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmCamposAdicionales` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmAfiliacion` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmLotes` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmAdmision` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmDoctosOrdenesServicios` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmDoctosPrefacturas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmRetencionesDetalle` | 0 | 0.0 | Withholding tax (retención) on sales/returns. |
| `AdmCuentasGrupos` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `AdmAdicionales` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmPucDistribucion` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `AdmAnticipos` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmVecesAperturaInfoCaja` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmSubFamiliasGrupos` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmControlCierreCaja` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmIntervaloDeterioro` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmPerEducativo` | 0 | 0.0 | User module permissions / access control. |
| `AdmConsecutivo` | 0 | 0.0 | Document sequence / consecutive numbering control. |
| `AdmUbicacionTercero` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `AdmTercerosRelacionados` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `AdmPresentaciones` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmAbonosLotes` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmTercerosSucursales` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `AdmInfoPermisos` | 0 | 0.0 | User module permissions / access control. |
| `AdmConfiguracionNiif` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmZonas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmProgramarRutero` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmCompuestos` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmTercerosDtoFianciero` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `AdmParaAnticipos` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmInfoFamiliares` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmFraccion` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmPreguntasEvaluacion` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmFotoHuella` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmFotos` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmImpresorasLineas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmVinculoFamiliar` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmParamComiD` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmViaticar` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmPerIngresoOperacionVehiculo` | 0 | 0.0 | User module permissions / access control. |
| `AdmEvalucionProveedor` | 0 | 0.0 | Supplier master or supplier-article link. |
| `AdmFamiliaAdmitido` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmAreasAdministrativas` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmBarrios` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmDotacion` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmCuenLineasNom` | 0 | 0.0 | Administration / master-data or system config table (Adm*). |
| `AdmCodigoAlternoTerceros` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |

### 5.3 Inventario/Ventas (Inv*) (155 tables · 8391.3 MB)

Inventory, sales documents, quotations, deliveries, stock levels, purchases, transfers, and e-invoice operational tables. **Highest decision value** for commercial ops beyond banco_datos.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `InvVentas` | 563,106 | 6284.33 | Sales header (ERP). Grain: one invoice/document. Links to detalle via VentaID. Authoritative commercial document list. |
| `InvHistoricoEntregas` | 1,517,872 | 482.77 | Delivery/dispatch history — OTIF, lead time factura→entrega. |
| `InvVentasDetalle` | 1,554,601 | 352.72 | Sales lines with AlmacenID — physical warehouse attribution used by manager report warehouse breakdown. |
| `InvEstadoFacturaElectronica` | 527,408 | 265.77 | DIAN e-invoice status — compliance % accepted/rejected. |
| `InvVentasTotales` | 552,995 | 179.3 | Aggregated sale totals helper; useful for header-level amounts without re-aggregating lines. |
| `InvDetalleExistencias` | 317,628 | 168.84 | Stock by warehouse×article — stockout risk, days of cover with velocity from banco_datos. |
| `InvFacturaCanceladas` | 549,928 | 136.65 | Cancelled invoices — void analysis and revenue quality. |
| `InvCotizaDetalle` | 467,780 | 90.78 | Quotation lines — conversion analysis quote→sale, lost quotes by seller/product. |
| `InvDevolucionVentas` | 18,160 | 85.92 | Formal sales returns documents (ERP) — better than only negative lines in banco_datos. |
| `InvFacturaPorCancelarDetalle` | 1,510,874 | 76.59 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvTemporalImpuestoGeneralHKA` | 1,357,827 | 51.02 | Temporary/staging inventory or tax processing table. |
| `InvFacturaPorCancelar` | 547,662 | 41.3 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvImpresionFactura` | 70,018 | 40.86 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvCotizaCab` | 79,643 | 26.52 | Quotation headers — top of commercial funnel before invoice. |
| `InvComprasDetalle` | 112,829 | 20.96 | Purchase lines — cost inflation, supplier mix by SKU. |
| `InvInfoMovimientoVentas` | 33,983 | 14.27 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvCompras` | 42,167 | 12.96 | Purchase headers — supply cost and supplier spend. |
| `InvUtilidadVentas` | 25,581 | 8.9 | Sales profitability / utility operational table. |
| `InvComprasTotales` | 30,544 | 7.21 | Purchasing operational table. |
| `InvListadoPrecios` | 11,498 | 4.71 | Pricing / price list related table. |
| `InvDevolucionVentasTotales` | 18,109 | 4.34 | Return totals helper. |
| `InvDevolucionVentasDetalle` | 28,946 | 4.02 | Return lines for product/category return rate. |
| `InvTraslados` | 10,260 | 3.59 | Inter-warehouse transfer headers — logistics rebalancing. |
| `InvRelacionFacturas` | 7,222 | 3.57 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvTrasladosDetalle` | 28,400 | 2.27 | Transfer lines — stock movement between bodegas. |
| `InvRetencionVentas` | 60,238 | 2.02 | Withholding tax (retención) on sales/returns. |
| `InvInfoRelacionCotizaion` | 3,167 | 1.96 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvCargueFacturas` | 0 | 1.95 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvInfoInventarioValorizado` | 7,387 | 1.9 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvInfoEntradasSalidas` | 290 | 1.71 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvDoctoTraslados` | 20,520 | 1.34 | Document linkage/control for inventory movements. |
| `InvDoctosDevueltos` | 17,721 | 1.27 | Document linkage/control for inventory movements. |
| `InvInfoRegDocumentos` | 5,924 | 1.15 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvInfoFacturaCanceladas` | 1,917 | 1.15 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvDevolucionCompras` | 1,612 | 0.77 | Returns (sales or purchase) operational table. |
| `InvExistencias` | 9,786 | 0.53 | Higher-level stock summary per article (companion to detalle). |
| `InvDevolucionComprasTotales` | 1,516 | 0.46 | Returns (sales or purchase) operational table. |
| `InvDevolucionComprasDetalle` | 2,424 | 0.4 | Returns (sales or purchase) operational table. |
| `InvKardex` | 323 | 0.39 | Stock levels, kardex, or physical inventory table. |
| `InvInformeTraslados` | 211 | 0.34 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvEntregaPorUsuario` | 302 | 0.33 | Delivery, loading, or dispatch logistics table. |
| `InvHistoricoCargue` | 2,406 | 0.32 | Delivery, loading, or dispatch logistics table. |
| `InvInfoMovimientoInventario` | 878 | 0.32 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvVentasGrupos` | 0 | 0.32 | Inventory/sales module operational table (Inv*). |
| `InvRemisiones` | 732 | 0.27 | Remission / delivery note operational table. |
| `InvInfoListadoArticulos` | 91 | 0.27 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvRetencionDevolucion` | 4,741 | 0.2 | Returns (sales or purchase) operational table. |
| `InvContaFleteCargue` | 529 | 0.2 | Delivery, loading, or dispatch logistics table. |
| `InvInveFisicoDetalle` | 4,601 | 0.2 | Stock levels, kardex, or physical inventory table. |
| `InvTerVencidos` | 820 | 0.2 | Inventory/sales module operational table (Inv*). |
| `InvRelacionVentasxVendedor` | 0 | 0.14 | Inventory/sales module operational table (Inv*). |
| `InvDoctosDevueltosCompras` | 1,546 | 0.13 | Document linkage/control for inventory movements. |
| `InvSugeridos` | 0 | 0.09 | Inventory/sales module operational table (Inv*). |
| `InvInfoMovimientoValorizado` | 92 | 0.08 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvComprasSemanalesDetalle` | 11 | 0.07 | Purchasing operational table. |
| `InvInveFisico` | 6 | 0.07 | Stock levels, kardex, or physical inventory table. |
| `InvFacturaRemision` | 3 | 0.07 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvOrdenPedidoDetalle` | 2 | 0.07 | Inventory/sales module operational table (Inv*). |
| `InvCuotasFacturas` | 1 | 0.07 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvOrdenCompraCab` | 1 | 0.07 | Purchasing operational table. |
| `InvInfoOrdenPedidoCompras` | 0 | 0.07 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvCajas` | 0 | 0.07 | Inventory/sales module operational table (Inv*). |
| `InvRotulos` | 0 | 0.07 | Inventory/sales module operational table (Inv*). |
| `InvAutorizarVentas` | 0 | 0.07 | Inventory/sales module operational table (Inv*). |
| `InvInfoListadoArticulosProveedores` | 0 | 0.0 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvComandaRestauranteDetalle` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvCompras_A_C_S_P` | 0 | 0.0 | Purchasing operational table. |
| `InvSedesRestaurantes` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvNcCompra` | 0 | 0.0 | Purchasing operational table. |
| `InvComandaRestaurante` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvComprasSemanales` | 0 | 0.0 | Purchasing operational table. |
| `InvCompraTrassladoAut` | 0 | 0.0 | Purchasing operational table. |
| `InvSalidaAcompanantes` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvReferenciasMotos` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvSepararDetalle` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvSaldoInventarioCosto` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvCambioVentas` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvMercanciaConsignacionCompra` | 0 | 0.0 | Purchasing operational table. |
| `InvAutorizaDtoVentas` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvFacturacionActiv` | 0 | 0.0 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvIncremenventaPos` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvFechaRealFacturas` | 0 | 0.0 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvSolicitud` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvVentasDivididas` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvParametroInveFisico` | 0 | 0.0 | Stock levels, kardex, or physical inventory table. |
| `InvMercanciaConsignacion` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvPuntosClientes` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvSeparar` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvMercanciaConsignacionDetalle` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvFacturacionActivDetalle` | 0 | 0.0 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvTrazabilidadOrden` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvFacturaRemisionDetalle` | 0 | 0.0 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvRemisionesCompras` | 0 | 0.0 | Purchasing operational table. |
| `InvPuntosClientesDv` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvInventarioPorPunto` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvSolicitudDetalle` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvArqueoCajaDes` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvOrdenCompraFE` | 0 | 0.0 | Purchasing operational table. |
| `InvInventarioPorIvaRangos` | 0 | 0.0 | Tax / IVA operational table. |
| `InvGarantias` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvInfHorasTecnico` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvAutorizaPrefacturas` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvContratosOrdenesDetalle` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvSeccionesInventario` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvOrdenesEjecutadas` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvInfoFechas` | 0 | 0.0 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvConteoInventario` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvListadoSemanal` | 0 | 0.0 | Pricing / price list related table. |
| `InvListadoCompuesto` | 0 | 0.0 | Pricing / price list related table. |
| `InvGarantiasDetalle` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvInfoContratos` | 0 | 0.0 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvDatosMotosRetoma` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvCompraRemisionDetalle` | 0 | 0.0 | Purchasing operational table. |
| `InvAutorizaPedido` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvDireccionDomicilio` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvGuardaTemporalPost` | 0 | 0.0 | Temporary/staging inventory or tax processing table. |
| `InvDoctosAnulados` | 0 | 0.0 | Document linkage/control for inventory movements. |
| `InvAutorizaSolicitud` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvDoctosPadresHijo` | 0 | 0.0 | Document linkage/control for inventory movements. |
| `InvEntradasSeries` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvVentasDetalleCocina` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvSalidasSeries` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvDatosMotos` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvExistenciasPresentacion` | 0 | 0.0 | Stock levels, kardex, or physical inventory table. |
| `InvRetirosPost` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvMermaEnCompras` | 0 | 0.0 | Purchasing operational table. |
| `InvResumenVentas` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvCompraRemision` | 0 | 0.0 | Purchasing operational table. |
| `InvVecesAperturaInfoCaja` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvDatosCodigo` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvDatosActas` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvDepreciacion` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvDireccionDomicilio2` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvComprasBloque` | 0 | 0.0 | Purchasing operational table. |
| `InvArtPrincipal` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvBateriasRecibidas` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvCamposAdicionales` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvInfoRelacionCostoVenta` | 0 | 0.0 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvContratosOrdenes` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvComponentesQI` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvPrincipalDetalle` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvArqueoCaja` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvTemporalFactActiv` | 0 | 0.0 | Temporary/staging inventory or tax processing table. |
| `InvActividades` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvTablaTemp` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvArqueo` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvInfoListadoClientesProveedores` | 0 | 0.0 | Inventory/sales report staging or precomputed informe table (ops UI support). |
| `InvVendedoresReferidos` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvSolicitudOtros` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvTrazabilidadCotizacion` | 0 | 0.0 | Quotations / quote-related commercial table. |
| `InvVentaMerma` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvVendedoresReferidosAct` | 0 | 0.0 | Inventory/sales module operational table (Inv*). |
| `InvArticulosDescuentoIva` | 0 | 0.0 | Tax / IVA operational table. |
| `InvSegundaFactura` | 0 | 0.0 | Sales invoicing lifecycle / cancel / print / e-invoice related operational table. |
| `InvInfoRelacionActiv` | 0 | 0.0 | Inventory/sales report staging or precomputed informe table (ops UI support). |

### 5.4 Vehículos (Veh*) (147 tables · 0.1 MB)

Fleet / vehicle module tables. Low relevance for hardware-store commercial KPIs unless logistics cost allocation is required.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `VehExamen` | 4 | 0.07 | Fleet/vehicle module table (low commercial BI value). |
| `VehProCamBase` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehConfiguracionVehiculo` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehDatosEquiposSeguros` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehLiquidacion` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehOrdenCarga` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehInspeccionRutinas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRepMantenimiento` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehFacturacionDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTerProCombustible` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehGestionAmbiental` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehFacturaTotales` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehItinerarioDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehPlanilla` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehLineasMarcas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTaquilla` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehComunicacionRutas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehDestinos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehControlEnProcesos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehContratos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutinasDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehAverias` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehSubRutas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTipoTrabajo` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehReparacionLlanta` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehParametrosMantenimiento` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehDimensiones` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTaquillaDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehPagosLiquidacionTerceros` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `VehRangosRutinas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutinasClaseVehiculos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehMaestroLlantas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTiposMantenimiento` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehModelo` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutinasComponentes` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehColores` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutaPlan` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehFacturacionDetalle3` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehGastosPeajesOtros` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRetencionVentas` | 0 | 0.0 | Withholding tax (retención) on sales/returns. |
| `VehOrdenTrabajoDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehNovedadDetalle2` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutaFletesEspecialesTerceros` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `VehOrdenTrabajoProveedores` | 0 | 0.0 | Supplier master or supplier-article link. |
| `VehFacturacionDetalle2` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehCombustible` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehManifiesto` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehComisionCancelada` | 0 | 0.0 | Commission rules or calculations. |
| `VehOrdenTrabajoDescripcionTrabajo` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehOrdenVehiculos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehDevolucionFactDet` | 0 | 0.0 | Returns (sales or purchase) operational table. |
| `VehRegistraRutinas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehHorasTecnicos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRegistraRutinasDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehNovedadDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehGastosPeajesOtrosDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehSolicitudMantenimiento` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehPasajeros` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehExamenesConductor` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehDevolucionFact` | 0 | 0.0 | Returns (sales or purchase) operational table. |
| `VehPlanillaDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehDocumContab` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehPlacasLiquidar` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehBandas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehGastosDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehBase` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehGastos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehPagosLiquidacionTercerosDetalle` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `VehLiquidacionTerceroDetalle` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `VehFacturasLiquidar` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehAmortizaSeguros` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehFacturacionDetalle4` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehConductoresArmados` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehSegurosVehiculo` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRegistroComparendos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehNomninaDias` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehSegurosVehiculo2` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRepFacturasLiq` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehNominaPlacas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTransportadora` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehUtilidadVehiculo` | 0 | 0.0 | Sales profitability / utility operational table. |
| `VehReporteComparendos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehPlanMantenimientoDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehConductoresVehiculos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehCampos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehHistorialPropietarios` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehItinerario` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehAutorizacionOrdenes` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutinas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehCombustibleDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehClientesContratos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTempCombustibleUtilidad` | 0 | 0.0 | Sales profitability / utility operational table. |
| `VehTipos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehCodigosComparendos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTipoAsociado` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRemesaTiquete` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehCodigoCarga` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTemDotacion` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehMovimientoLlantas` | 0 | 0.0 | Accounting journal movement table. |
| `VehTemCombustible` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehFacturacion` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTemOtros` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehOrdenTrabajo` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehClases` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTemFletes` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehNovedadesFacturacion` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTemfacturas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehOrdenTrabajoRepuestos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehTemAnticipos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehInspeccionRutinaDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehSeguroPoliza` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehAprovechamientoLlantas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehNomina` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehMarcas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehVehiculos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehVehiculosArmados` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehMontajeLlantas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutinasContratos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehInformeAnticipos` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutasCombustibleMarcas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehInfoPlanilla` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehCuentasCodigoCarga` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `VehInfoRegistroRutinas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehConductores` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehRutas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehAprovechamientoLlantasDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehAnticiposSolicitados` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehInfoServiciosTransporte` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehAnticiposLiquidar` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehLlantas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehConductorOrden` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehSolicitudMantenimientoDetalle` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehPosicionLlantas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehServiciosCamionVacio` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehNovedad` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehLaboroCond` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehLiquidacionTercero` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `VehArticulosVehiculos` | 0 | 0.0 | Article/SKU master or article-related admin table. |
| `VehConsecutivoClientes` | 0 | 0.0 | Document sequence / consecutive numbering control. |
| `VehOficinas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehGastosViaje` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehSegurosNoAplicados` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehIncrementarValor` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehInfoCombustible` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehPlanMantenimiento` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehInfMovtoLlantas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |
| `VehInfAdmonLlantas` | 0 | 0.0 | Fleet/vehicle module table (low commercial BI value). |

### 5.5 Contabilidad (Con*) (68 tables · 1264.6 MB)

General ledger movements, balances, statutory formats (1001/1003/1007/1008), P&L, trial balance. Finance decision support; lower priority than sales/AR for store ops BI.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `ConMovimientoDetalle` | 4,552,893 | 924.88 | GL entry lines — largest accounting table; P&L deep dive long-term. |
| `ConMovimiento` | 767,037 | 269.74 | GL entry headers. |
| `ConSaldosContabilidad` | 245,574 | 29.41 | Account balances snapshot. |
| `ControlDocumentos` | 563,382 | 16.27 | Document type / document control admin table. |
| `ConConecutivos` | 398,559 | 9.91 | Document sequence / consecutive numbering control. |
| `ConMovimientoDetalle_NewDatos` | 17,779 | 3.27 | Accounting journal movement table. |
| `ConFormato1007` | 14,643 | 2.09 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConInformeDiario` | 4,293 | 1.65 | Accounting report / book / balance helper table. |
| `ConFormato1001v2` | 1,015 | 1.27 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConLibroDiario` | 7,820 | 1.21 | Accounting report / book / balance helper table. |
| `ConAuxiliar` | 624 | 0.9 | Accounting report / book / balance helper table. |
| `ConBalancePrueba` | 460 | 0.6 | Accounting report / book / balance helper table. |
| `ConPyG` | 911 | 0.45 | Accounting report / book / balance helper table. |
| `ConInformeRetencion` | 799 | 0.34 | Withholding tax (retención) on sales/returns. |
| `ConCertificados` | 409 | 0.34 | Tax certificates / withholding accounting table. |
| `ConDoctoDiario` | 61 | 0.29 | Accounting module table (Con*). |
| `ConInformeIca` | 313 | 0.27 | Accounting report / book / balance helper table. |
| `ConFormato1003` | 653 | 0.21 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConFormato1008` | 343 | 0.2 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConFormato1005` | 243 | 0.15 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConFormato1009` | 178 | 0.15 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConFormato1006` | 71 | 0.09 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConInfPyGActivos` | 124 | 0.07 | Accounting module table (Con*). |
| `ConRelacionCheques` | 54 | 0.07 | Accounting module table (Con*). |
| `ConIva` | 34 | 0.07 | Tax / IVA operational table. |
| `ConPlantillaDetalle` | 14 | 0.07 | Accounting module table (Con*). |
| `ConPresupuestoDetalle` | 12 | 0.07 | Accounting module table (Con*). |
| `ConCuentasCartera` | 6 | 0.07 | Chart of accounts / PUC admin. |
| `ConParaBalanceEstado` | 5 | 0.07 | Accounting module table (Con*). |
| `ConRecordatorios` | 2 | 0.07 | Accounting module table (Con*). |
| `ConConciliacionCab` | 1 | 0.07 | Accounting module table (Con*). |
| `ConCuentasInformeCaja` | 1 | 0.07 | Chart of accounts / PUC admin. |
| `ConPresupuesto` | 1 | 0.07 | Accounting module table (Con*). |
| `ConPlantilla` | 1 | 0.07 | Accounting module table (Con*). |
| `ConFormato1002` | 0 | 0.07 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConGirado` | 0 | 0.0 | Accounting module table (Con*). |
| `ConSaldoCuentaTercero` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `ConAiu` | 0 | 0.0 | Accounting module table (Con*). |
| `ConAiuServicios` | 0 | 0.0 | Accounting module table (Con*). |
| `ConRevelaciones` | 0 | 0.0 | Accounting module table (Con*). |
| `ConTramites` | 0 | 0.0 | Accounting module table (Con*). |
| `ConTramitesFacturados` | 0 | 0.0 | Accounting module table (Con*). |
| `ConRegistrosBaseImpuestos` | 0 | 0.0 | Tax / IVA operational table. |
| `ConParametrosPlanilla` | 0 | 0.0 | Accounting module table (Con*). |
| `ConParametrosPyg` | 0 | 0.0 | Accounting module table (Con*). |
| `ConPresupuestoTem` | 0 | 0.0 | Accounting module table (Con*). |
| `ConEgresosLegalizacion` | 0 | 0.0 | Accounting module table (Con*). |
| `ConPlanillaDiariaCaja` | 0 | 0.0 | Accounting module table (Con*). |
| `ConPucInformes` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `Conexion` | 0 | 0.0 | Accounting module table (Con*). |
| `ConEnumerarLibros` | 0 | 0.0 | Accounting module table (Con*). |
| `ConProcesoBancos` | 0 | 0.0 | Accounting module table (Con*). |
| `ConPresupuestoTem2` | 0 | 0.0 | Accounting module table (Con*). |
| `ConAntCruzado` | 0 | 0.0 | Accounting module table (Con*). |
| `ConFormato1001` | 0 | 0.0 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConInfoFacturaServicios` | 0 | 0.0 | Accounting module table (Con*). |
| `ConConciliacionDet` | 0 | 0.0 | Accounting module table (Con*). |
| `ConInfoContaSucur` | 0 | 0.0 | Accounting module table (Con*). |
| `ConImpresionMesAnualCuentas` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `ConImpresionAnualCuentas` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `ConFormato1012` | 0 | 0.0 | Statutory tax/accounting format (DIAN/exogenous) export table. |
| `ConComparativo` | 0 | 0.0 | Accounting module table (Con*). |
| `ConConceptosRevelaciones` | 0 | 0.0 | Accounting module table (Con*). |
| `ConParametrosDetallePyg` | 0 | 0.0 | Accounting module table (Con*). |
| `ConImpuestos` | 0 | 0.0 | Tax / IVA operational table. |
| `ConInformeAnticipo` | 0 | 0.0 | Accounting report / book / balance helper table. |
| `ConTramitesDetalle` | 0 | 0.0 | Accounting module table (Con*). |
| `ConInfPyGAgrupado` | 0 | 0.0 | Accounting module table (Con*). |

### 5.6 Nómina (Nom*) (61 tables · 87.9 MB)

Payroll liquidations, payslips, electronic payroll, novedades. HR cost decisions — out of commercial BI scope unless headcount cost is needed.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `NomInfoDesprendiblesDevDed` | 534,558 | 67.77 | Payroll liquidation / payslip table. |
| `NomLiquidaciones` | 5,177 | 7.52 | Payroll liquidation / payslip table. |
| `NomNovedades` | 5,308 | 4.7 | Payroll novelty (bonus, discount, balance) table. |
| `NomNominaElectronica` | 5,139 | 1.84 | Electronic payroll (nómina electrónica) compliance table. |
| `NomDesprendibles` | 1,198 | 1.59 | Payroll liquidation / payslip table. |
| `NomNovDecuentos` | 10,753 | 0.9 | Payroll novelty (bonus, discount, balance) table. |
| `NomNovSaldos` | 10,517 | 0.71 | Account balances table. |
| `NomInfoLiquidacionNomina` | 638 | 0.65 | Payroll liquidation / payslip table. |
| `NomNovBonificaciones` | 7,439 | 0.59 | Payroll novelty (bonus, discount, balance) table. |
| `NomInformePlanilla` | 103 | 0.07 | Payroll module table (Nom*). |
| `NomInfPrima` | 97 | 0.07 | Payroll module table (Nom*). |
| `NomPrimaServicios` | 92 | 0.07 | Payroll module table (Nom*). |
| `NomInfDatosEmple` | 75 | 0.07 | Payroll module table (Nom*). |
| `NomDocumContab` | 56 | 0.07 | Payroll module table (Nom*). |
| `NomInfoDctosBonificacionEmp` | 29 | 0.07 | Payroll module table (Nom*). |
| `NomBonificaciones` | 20 | 0.07 | Payroll module table (Nom*). |
| `NomExames` | 15 | 0.07 | Payroll module table (Nom*). |
| `NomDescuentos` | 14 | 0.07 | Payroll module table (Nom*). |
| `NomInfoHistorialNomina` | 12 | 0.07 | Payroll module table (Nom*). |
| `NomOtrosDevengos` | 7 | 0.07 | Payroll module table (Nom*). |
| `NomValoresApropiacion` | 6 | 0.07 | Payroll module table (Nom*). |
| `NomValoresLiquidacion` | 6 | 0.07 | Payroll liquidation / payslip table. |
| `NomHisLiqPrestaciones` | 6 | 0.07 | Payroll module table (Nom*). |
| `NomDependencias` | 3 | 0.07 | Payroll module table (Nom*). |
| `NomBancos` | 2 | 0.07 | Payroll module table (Nom*). |
| `NomEstudiosRealizados` | 2 | 0.07 | Payroll module table (Nom*). |
| `NomLiqPrestaciones` | 1 | 0.07 | Payroll module table (Nom*). |
| `NomInfoCarnetizacion` | 1 | 0.07 | Payroll module table (Nom*). |
| `NomHistorialContratos` | 1 | 0.07 | Payroll module table (Nom*). |
| `NomReferenciasPersonales` | 1 | 0.07 | Payroll module table (Nom*). |
| `NomInfoListadoEmpleados` | 0 | 0.07 | Pricing / price list related table. |
| `NomCargos` | 37 | 0.02 | Payroll module table (Nom*). |
| `NomSalud` | 7 | 0.02 | Payroll module table (Nom*). |
| `NomTipoRiesgos` | 5 | 0.02 | Payroll module table (Nom*). |
| `NomPension` | 5 | 0.02 | Payroll module table (Nom*). |
| `NomTerminoContrato` | 2 | 0.02 | Payroll module table (Nom*). |
| `NomRiesgo` | 1 | 0.02 | Payroll module table (Nom*). |
| `NomHistorialPri` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomHoras` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomHistorialVac` | 0 | 0.0 | Payroll module table (Nom*). |
| `Nom_Vac_Inca_Lic_NE` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomInfoEntraSaleEmpleado` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomFechasVac` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomNovHorasExtras` | 0 | 0.0 | Payroll novelty (bonus, discount, balance) table. |
| `NomInfoDescuentosEmp` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomDevLiquidacion` | 0 | 0.0 | Payroll liquidation / payslip table. |
| `NomCancelacion` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomHorasExtras` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomDedLiquidacion` | 0 | 0.0 | Payroll liquidation / payslip table. |
| `NomInformesBasicos` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomInfoListadoJudicialEmple` | 0 | 0.0 | Pricing / price list related table. |
| `NomInfTermContrato` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomNovDecuentos_Otras_Liqui` | 0 | 0.0 | Payroll novelty (bonus, discount, balance) table. |
| `NomRegistroHoras` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomReferenciasLaborales` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomInfoContratos` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomControlEntSal` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomCesantias` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomInfBeneficiarios` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomInfNomConsolid` | 0 | 0.0 | Payroll module table (Nom*). |
| `NomHistorialLiq` | 0 | 0.0 | Payroll module table (Nom*). |

### 5.7 Cartera (Car*) (47 tables · 91.9 MB)

ERP accounts receivable/payable, payments, commissions, credit. Authoritative AR/AP; cross-check with SmartBusiness banco_cartera.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `CarCarteraCliente` | 148,962 | 33.84 | ERP customer AR open items — credit risk source of truth. |
| `CarPagosClienteDetalle` | 179,949 | 23.34 | Customer payment application detail. |
| `CarPagosCliente` | 58,725 | 15.84 | Customer payment headers. |
| `CarCarteraProveedor` | 20,130 | 8.65 | Supplier AP open items — cash planning. |
| `CarPagosProveedorDetalle` | 21,475 | 2.96 | Supplier payment detail. |
| `CarInformeCartera` | 3,474 | 2.65 | Customer accounts receivable / collections table. |
| `CarPagosProveedor` | 12,242 | 2.4 | Supplier payment headers. |
| `CarFacturasCanceladas` | 2,746 | 1.13 | AR/AP portfolio module table (Car*). |
| `CarComisiones` | 1,621 | 0.46 | Commission rules or calculations. |
| `CarCreditosDesembolsos` | 508 | 0.27 | Credit / disbursement related AR table. |
| `CarAuxiliarCartera` | 160 | 0.21 | Customer accounts receivable / collections table. |
| `CarInformeCruce` | 4 | 0.14 | AR/AP portfolio module table (Car*). |
| `CarCuentasDeCobro` | 15 | 0.07 | Chart of accounts / PUC admin. |
| `CarChequesPorFechadosDetalle` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarChequesPorFechados` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarCarteraCuotas` | 0 | 0.0 | Customer accounts receivable / collections table. |
| `CarCausacion` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarAportes` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarPagosProveedorDetalles` | 0 | 0.0 | Supplier master or supplier-article link. |
| `CarMovimientoDetalle` | 0 | 0.0 | Accounting journal movement table. |
| `CarPagosCreditosInteres` | 0 | 0.0 | Credit / disbursement related AR table. |
| `CarPagosCreditosDetalle` | 0 | 0.0 | Credit / disbursement related AR table. |
| `CarHistoricoDeterioroCartera` | 0 | 0.0 | Customer accounts receivable / collections table. |
| `CarGestionCartera` | 0 | 0.0 | Customer accounts receivable / collections table. |
| `CarAmortizacionDetalle` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarAmortizacionExtras` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarInfoAmortizacion` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarAmortizacionCodeudores` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarEstadoCuenta` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `CarPagosCreditos` | 0 | 0.0 | Credit / disbursement related AR table. |
| `CarPlantilla` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarSaldosCredito` | 0 | 0.0 | Account balances table. |
| `CarChequesDevueltos` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarAportesDetalle` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarHistoricoDeterioro` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarCausacionDetalle` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarPlantillaDetalle` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarMovimientoDetalleClientes` | 0 | 0.0 | Accounting journal movement table. |
| `CarAmortizacionRotativo` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarAportesCuentas` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `CarAmortizacion` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarAhorro` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarPagosCuentasRete` | 0 | 0.0 | Chart of accounts / PUC admin. |
| `CarPagosOtrosValores` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarInformeLotes` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarAmortizacionInteres` | 0 | 0.0 | AR/AP portfolio module table (Car*). |
| `CarInteres` | 0 | 0.0 | AR/AP portfolio module table (Car*). |

### 5.8 Hotel (Hot*) (30 tables · 0.5 MB)

Hotel module (likely unused or legacy for this business). Minimal decision value for ferretería BI.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `HotInfoHabitaciones` | 996 | 0.45 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotMotivoVisita` | 3 | 0.07 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotControlReservas` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotVentasDetalle` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotValoresFijosGrupos` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotOtrosHuesped` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotObjetosHuesped` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotAgruparLineas` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotPrecomada` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotAcomodacionesHuesped` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotPrecomadaDetalle` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotComunicaCostoHabita` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotReservas` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotSalones` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotListdoFidelidad` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotLimpieza` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotImpresionReserva` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotHuespedAdicionales` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotForeCast` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotLineaRestaurante` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotLineaHospedaje` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotConvenios` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotEncuesta` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotDatosHospedados` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotControlMinibares` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotConsecutivoCocina` | 0 | 0.0 | Document sequence / consecutive numbering control. |
| `HotMesas` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotBloqueosHabitaciones` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotReservasDetalle` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |
| `HotHuespedes` | 0 | 0.0 | Hotel module table (legacy/unused for ferretería core BI). |

### 5.9 Servicios (Ser*) (16 tables · 0.1 MB)

Services module tables. Low commercial priority unless service lines grow.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `SerFactura` | 2 | 0.07 | Services module table. |
| `SerFacturaDatosSectorSalud` | 0 | 0.0 | Services module table. |
| `SerFacturaTotales` | 0 | 0.0 | Services module table. |
| `SerConceptos` | 0 | 0.0 | Services module table. |
| `SerSuspenderCortar` | 0 | 0.0 | Services module table. |
| `SerTemporalConceptosAdicionales` | 0 | 0.0 | Temporary/staging inventory or tax processing table. |
| `SerComunicacionConceptos` | 0 | 0.0 | Services module table. |
| `SerRetencionVentas` | 0 | 0.0 | Withholding tax (retención) on sales/returns. |
| `SerFacturaDetalle` | 0 | 0.0 | Services module table. |
| `SerInfoFalraEntrega` | 0 | 0.0 | Delivery, loading, or dispatch logistics table. |
| `SerTerceroCosto` | 0 | 0.0 | Third-party (customer/supplier) master or movement table. |
| `SerPagoConcepto` | 0 | 0.0 | Services module table. |
| `SerInfoTotalVentas` | 0 | 0.0 | Services module table. |
| `SerOperaciones` | 0 | 0.0 | Services module table. |
| `SerAfiliados` | 0 | 0.0 | Services module table. |
| `SerEntradaServicio` | 0 | 0.0 | Services module table. |

### 5.10 Activos fijos (Act*) (2 tables · 0.0 MB)

Fixed assets. Accounting/asset management only.

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `ActivosFijos` | 0 | 0.0 | Fixed assets table. |
| `ActivosHistoricoDepreciacion` | 0 | 0.0 | Fixed assets table. |

### 5.11 Historial/auditoría (Historia*) (1 tables · 159.0 MB)

Change history on master entities (e.g. article history).

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `HistoriaAdmArticulos` | 422,937 | 159.02 | Article change history — price/cost/description audit trail. |

### 5.12 POS (1 tables · 0.0 MB)

Point-of-sale related table(s).

| Table | Rows | MB | Purpose (decision note) |
|-------|------|----|-------------------------|
| `PosAperturaCaja` | 0 | 0.0 | Point-of-sale related table. |

---

## 6. Inventory integrity & how to refresh

```bash
# From repo root with DB_* env loaded
python scripts/utils/introspect_table_sizes.py --database both --output-dir /path/to/scratch
```

- SmartBusiness table_count this run: **8**
- J3System table_count this run: **968**
- Row counts: `sys.partitions` only (index_id 0/1); space from separate `sys.allocation_units` aggregate
- Full column describe: all SmartBusiness tables; critical J3 set in `schemas_j3_critical.json`
- Prior strategy note: `reports/DATABASE_TABLE_ANALYSIS_RECOMMENDATIONS.md` — recommendations still useful; **volumes above supersede older figures**.

---

*Generated for decision making from live MSSQL introspection on 2026-07-29 (partition-correct row counts).*
