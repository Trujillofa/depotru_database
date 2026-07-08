# Inventario Crítico y Quiebres de Stock

- **Fecha referencia:** 2024-12-31
- **Ventana velocidad:** 90 días
- **Fuentes:** `InvDetalleExistencias` (J3System) + `banco_datos` (SmartBusiness)
- **Cobertura (días):** `SaldoActual / venta_diaria_promedio`

## Resumen

- **SKUs críticos (top 10):** 10
- **Quiebre <7 días cobertura:** 10
- **Stock ≤10 unidades:** 10
- **Promedio días cobertura:** 0.0

## Top SKUs críticos (menor cobertura primero)

| SKU | Producto | Bodega | Stock | Venta 90d | Días cob. | Prioridad |
|---|---|---|---:|---:|---:|---|
| 0020030001 | AMARRES PARA TEJA | BDT | 0 | 100415 | 0.0 | QUIEBRE_INMINENTE |
| 0020030001 | AMARRES PARA TEJA | SUR | 0 | 100415 | 0.0 | QUIEBRE_INMINENTE |
| 0020030001 | AMARRES PARA TEJA | CEN | 0 | 100415 | 0.0 | QUIEBRE_INMINENTE |
| 0020030001 | AMARRES PARA TEJA | BOD | 0 | 100415 | 0.0 | QUIEBRE_INMINENTE |
| 0020030001 | AMARRES PARA TEJA | BD6 | 0 | 100415 | 0.0 | QUIEBRE_INMINENTE |
| 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | ALM | 0 | 79426 | 0.0 | QUIEBRE_INMINENTE |
| 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | BOD | 0 | 79426 | 0.0 | QUIEBRE_INMINENTE |
| 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | CON | 0 | 79426 | 0.0 | QUIEBRE_INMINENTE |
| 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | EXH | 0 | 79426 | 0.0 | QUIEBRE_INMINENTE |
| 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | CEN | 0 | 79426 | 0.0 | QUIEBRE_INMINENTE |

## Por bodega

- **BDT** (BODEGA AJUSTES TEMPORALES): 1287 SKUs críticos, 1278 quiebre <7d, prom. cobertura 0.1 días
- **CEN** (005 GARANTIAS): 1278 SKUs críticos, 1278 quiebre <7d, prom. cobertura 0.0 días
- **BOD** (MANGUERAS): 1251 SKUs críticos, 1245 quiebre <7d, prom. cobertura 0.1 días
- **BD6** (BD6): 1168 SKUs críticos, 1141 quiebre <7d, prom. cobertura 0.4 días
- **SUR** (SUR): 1121 SKUs críticos, 1099 quiebre <7d, prom. cobertura 0.3 días
- **DIS** (DISTRIBUCIONES): 1064 SKUs críticos, 888 quiebre <7d, prom. cobertura 2.7 días
- **EXH** (BOD EXHIBICION ALMACEN): 996 SKUs críticos, 996 quiebre <7d, prom. cobertura 0.0 días
- **TRA** (MCIA COMITECAFE): 610 SKUs críticos, 606 quiebre <7d, prom. cobertura 0.1 días
- **CON** (CONTABILIDAD): 559 SKUs críticos, 559 quiebre <7d, prom. cobertura 0.0 días
- **ALM** (001): 554 SKUs críticos, 523 quiebre <7d, prom. cobertura 0.9 días
