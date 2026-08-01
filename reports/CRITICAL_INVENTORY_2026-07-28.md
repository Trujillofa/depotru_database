# Inventario Crítico y Quiebres de Stock

- **Fecha referencia:** 2026-07-28
- **Ventana velocidad:** 90 días
- **Fuentes:** `InvDetalleExistencias` + demanda `InvVentas`/`InvVentasDetalle` (bodegas comerciales ALM/SUR/BD6/DIS/FLO)
- **Cobertura (días):** `SaldoActual / venta_diaria` (misma bodega)

## Resumen

- **SKUs críticos (top 12):** 12
- **Quiebre <7 días cobertura:** 12
- **Stock ≤10 unidades:** 12
- **Promedio días cobertura:** -59.0

## Top SKUs críticos (menor cobertura primero)

| SKU | Producto | Bodega | Stock | Venta 90d | Días cob. | Prioridad |
|---|---|---|---:|---:|---:|---|
| 0020240039 | YESO EXTRA X KILO  | DIS | -41 | 36 | -102.5 | QUIEBRE_INMINENTE |
| 0010120004 | CUERDA MARINA 6MM X MTS | DIS | -35 | 35 | -90.0 | QUIEBRE_INMINENTE |
| 0020280480 | SIKA BOOM AMARILLO 300CC  PROMOCION | ALM | -41 | 41 | -90.0 | QUIEBRE_INMINENTE |
| 0090060274 | ESTUCO ACRILICO INTERIOR/EXTERIOR 300 GR | ALM | -58 | 58 | -90.0 | QUIEBRE_INMINENTE |
| 0020280478 | SIKA MULTIUSO UNIVERSAL 130 TRANSPARENTE | FLO | -54 | 54 | -90.0 | QUIEBRE_INMINENTE |
| 0020280296 | SIKA MULTI-SEAL 10CM X ROLLO 10 MTRS ALU | FLO | -34 | 36 | -85.0 | QUIEBRE_INMINENTE |
| 0010190033 | ANGULO 50 X 4.0MM (2" X 3/16) | SUR | -18 | 32 | -50.6 | QUIEBRE_INMINENTE |
| 0020280358 | SIKA 1 MORTERO GRIS 100 IMPERMEABLE 2 KG | FLO | -6 | 21 | -25.7 | QUIEBRE_INMINENTE |
| 0020280464 | SIKAFLEX UNIVERSAL GRIS X 300 ML PROMOCI | FLO | -17 | 60 | -25.5 | QUIEBRE_INMINENTE |
| 0020030035 | ALAMBRE NEGRO RECOCIDO X CHIPA  | SUR | -22 | 80 | -24.8 | QUIEBRE_INMINENTE |
| 0020280463 | SIKAFLEX UNIVERSAL BLANCO X 300 ML PROMO | FLO | -25 | 91 | -24.7 | QUIEBRE_INMINENTE |
| 0020280087 | SIKA 1 MORTERO GRIS 100 IMPERMEABLE 25 K | FLO | -7 | 65 | -9.7 | QUIEBRE_INMINENTE |

## Por bodega

- **ALM** (001): 209 SKUs críticos, 152 quiebre <7d, prom. cobertura 3.6 días
- **DIS** (DISTRIBUCIONES): 117 SKUs críticos, 82 quiebre <7d, prom. cobertura 4.2 días
- **SUR** (SUR): 58 SKUs críticos, 45 quiebre <7d, prom. cobertura 1.4 días
- **BD6** (BD6): 51 SKUs críticos, 35 quiebre <7d, prom. cobertura 5.5 días
- **FLO** (ALMACEN FLORENCIA): 22 SKUs críticos, 15 quiebre <7d, prom. cobertura -3.6 días
