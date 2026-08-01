# Rotación de Existencias

- **Fecha referencia:** 2026-07-28
- **Ventana demanda comercial:** 90 días
- **Modo demanda:** `warehouse` — SKU×bodega via InvVentasDetalle (J3)
- **Bodegas comerciales:** `ALM`, `SUR`, `BD6`, `DIS`, `FLO`
- **Exclusión demanda comercial (DocumentosCodigo):** `XY`, `AS`, `TS`, `YX`, `ISC`
- **Fuentes stock:** `InvDetalleExistencias`; demanda: J3 `InvVentas`/`InvVentasDetalle` (modo warehouse) o `banco_datos` (modo company)
- **Cobertura:** `Stock / Venta_Diaria_Comercial` (misma bodega en modo warehouse)
- **Filas detalle (SKU×bodega):** 6.795

## Avisos de calidad de datos

- ⚠️ Salida física YTD (`SalidasEne…Dic`) es 0 en todas las filas — posible dato mensual vacío; no usar esa columna para decisiones.

## Resumen ejecutivo

- **Filas con stock o venta:** 6.795
- **Posiciones con stock > 0:** 6.105
- **Posiciones con venta comercial:** 4.852
- **QUIEBRE:** 744
- **BAJA_COBERTURA:** 343
- **SALUDABLE:** 1.647
- **SOBRESTOCK:** 2.118
- **MUERTO:** 1.867
- **Stock total (unidades):** 1.186.559
- **Stock en MUERTO:** 47.361 (4,0%)
- **Mediana días cobertura (con demanda):** 91,6

## A — Comprar / transferir (QUIEBRE, 1 fila por SKU = peor bodega)

| SKU | Producto | Bodega | Stock | Venta comercial | Días cob. | Salida física YTD |
|---|---|---|---:|---:|---:|---:|
| 0020390061 | CODO PRESION 90 1/2 T/PESADO | ALM | 4.583 | 61.397 | 6,7 | 0 |
| 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | SUR | 286 | 54.122 | 0,5 | 0 |
| 0030030001 | LADRILLO BLOQUELON SANTA FE 23X80X8 | SUR | -939 | 40.359 | -2,1 | 0 |
| 0020190012 | BARRA CORRUGADA 3/8 X 6 MTS NTC 2289 PESO… | SUR | 603 | 20.762 | 2,6 | 0 |
| 0020220011 | SOLDADURA PAVCO PVC 28 GR (1/128 GA) | ALM | 310 | 8.424 | 3,3 | 0 |
| 0040030002 | ALAMBRE GALVANIZADO N° 12 - 21.13 M | ALM | 206 | 5.460 | 3,4 | 0 |
| 0100050067 | CUCHILLA GUAD/BELL PULIDA C13 1" CUADRADA… | ALM | 159 | 3.606 | 4,0 | 0 |
| 0020190146 | FLEJES FIGURADO 3/8" 20X30  | SUR | 0 | 3.500 | 0,0 | 0 |
| 0020390079 | CODO SANITARIO 90 CC 2" T/PESADO | ALM | 0 | 2.640 | 0,0 | 0 |
| 0020260047 | PERFIL OMEGA P/CIELO RASO PVC 2.44  | DIS | 8 | 2.399 | 0,3 | 0 |
| 0020160003 | ACOPLE LVM/LVP PLASTICO GRIVAL 40 CM | ALM | 73 | 1.951 | 3,4 | 0 |
| 0020400035 | ZINC 0.17 CAL 35 3X10 ACESCO | SUR | -56 | 1.944 | -2,6 | 0 |

## B — Capital atrapado (MUERTO + SOBRESTOCK)

| SKU | Producto | Bodega | Stock | Venta comercial | Días cob. | Bandera |
|---|---|---|---:|---:|---:|---|
| 0020030001 | AMARRES PARA TEJA | ALM | 72.837 | 52.907 | 123,9 | SOBRESTOCK |
| 0020110063 | TORNILLO AUTOPERFORANTE 2.1/2"X12 P/ZINC | ALM | 26.093 | 7.183 | 326,9 | SOBRESTOCK |
| 0020110069 | TORNILLO AUTOPERF 11/2" T/SOMBRILLA ROJO … | ALM | 19.987 | 3.050 | 589,8 | SOBRESTOCK |
| 0020110070 | TORNILLO AUTOPERF 11/2" T/SOMBRILLA AZUL … | ALM | 14.200 | 1.720 | 743,0 | SOBRESTOCK |
| 0020110061 | TORNILLO AUTOPERFORANTE 2"X12 P/ZINC | ALM | 10.820 | 2.460 | 395,9 | SOBRESTOCK |
| 0020190021 | FLEJES FIGURADO 1/4" 18X8 TRIANGULAR NTC … | SUR | 10.328 | 2.240 | 415,0 | SOBRESTOCK |
| 0020190015 | FLEJES FIGURADO 1/4" 10X20 NTC 2289  | SUR | 9.395 | 2.015 | 419,6 | SOBRESTOCK |
| 0040030027 | ALAMBRE GALVANIZADO N° 10.5- 15.47M | ALM | 8.960 | 4.322 | 186,6 | SOBRESTOCK |
| 0030030003 | LADRILLO PRENSADO MACIZO | SUR | 8.208 | 5.918 | 124,8 | SOBRESTOCK |
| 0020390097 | CURVA PVC 1/2" PROTUCOL | ALM | 6.294 | 3.567 | 158,8 | SOBRESTOCK |
| 0040050014 | CABO PARA PALA | ALM | 5.613 | 3.331 | 151,7 | SOBRESTOCK |
| 0010150018 | PUNTILLA BOLSA ZINC ECONOMICA | ALM | 5.033 | 1.078 | 420,2 | SOBRESTOCK |

## C — Traslados sugeridos (superávit → quiebre, mismo SKU)

| SKU | Producto | Desde | Hacia | Stock origen | Stock dest. | Venta dest. | Sugerido mover |
|---|---|---|---|---:|---:|---:|---:|
| 0020220011 | SOLDADURA PAVCO PVC 28 GR (1/128 GA) | DIS | ALM | 200 | 310 | 8.424 | 100,0 |
| 0040030002 | ALAMBRE GALVANIZADO N° 12 - 21.13 M | SUR | ALM | 2.277 | 206 | 5.460 | 643,3 |
| 0100050067 | CUCHILLA GUAD/BELL PULIDA C13 1" CUADRADA… | DIS | ALM | 99 | 159 | 3.606 | 49,5 |
| 0020260047 | PERFIL OMEGA P/CIELO RASO PVC 2.44  | SUR | DIS | 1.620 | 8 | 2.399 | 365,2 |
| 0020160003 | ACOPLE LVM/LVP PLASTICO GRIVAL 40 CM | DIS | ALM | 160 | 73 | 1.951 | 80,0 |
| 0020400035 | ZINC 0.17 CAL 35 3X10 ACESCO | BD6 | SUR | 144 | -56 | 1.944 | 72,0 |
| 0020390211 | UNION  PRESION 1 1/2 T/PESADO | DIS | ALM | 181 | 97 | 1.487 | 90,5 |
| 0020260031 | PERFIL PARAL 2.44 BASE 6 CALIBRE 26 | BD6 | SUR | 1.731 | 18 | 1.289 | 182,5 |
| 0020260031 | PERFIL PARAL 2.44 BASE 6 CALIBRE 26 | DIS | SUR | 332 | 18 | 1.289 | 166,0 |
| 0020220010 | SOLDADURA PAVCO PVC 225 GR (1/16 GA) | DIS | ALM | 69 | 86 | 1.239 | 34,5 |
| 0020260006 | PERFIL ANGULO 2.44 CALIBRE 26 | DIS | SUR | 295 | 11 | 1.131 | 147,5 |
| 0020240069 | INVECRYL X 750 GR | DIS | ALM | 150 | 29 | 926 | 75,0 |

## ABC por demanda comercial (SKU)

| ABC | SKU | Producto | Venta comercial | Stock total | % venta acum. |
|---|---|---|---:|---:|---:|
| A | 0020090002 | CEMENTO GRIS USO GENERAL CEMEX 50KG  | 70.634 | 1.469 | 4,5% |
| A | 0020390061 | CODO PRESION 90 1/2 T/PESADO | 64.768 | 5.353 | 8,6% |
| A | 0020030001 | AMARRES PARA TEJA | 54.911 | 73.204 | 12,0% |
| A | 0020030012 | ALAMBRE NEGRO RECOCIDO X KILO CONTINUO | 49.465 | 11.759 | 15,2% |
| A | 0030030001 | LADRILLO BLOQUELON SANTA FE 23X80X8 | 40.359 | 0 | 17,7% |
| A | 0020390214 | UNION  PRESION 1/2" T/PESADO | 37.375 | 14.285 | 20,1% |
| A | 0020190010 | ROLLO CORRUGADO X KG 1/4" SR NTC 2289 | 31.235 | 24.841 | 22,1% |
| A | 0020190017 | FLEJES FIGURADO 1/4" 18X8 NTC 2289 | 29.533 | 16.416 | 23,9% |
| A | 0020190001 | BARRA CORRUGADA 1/2 X 6 MTS NTC 2289 PESO… | 27.762 | 5.400 | 25,7% |
| A | 0020110072 | TORNILLO AUTOPERF 21/2" T/SOMBRILLA NEGRO… | 27.642 | 19.226 | 27,5% |
| A | 0020390025 | ADAPTADOR MACHO 1/2" T/PESADO | 25.056 | 16.278 | 29,0% |
| A | 0020190012 | BARRA CORRUGADA 3/8 X 6 MTS NTC 2289 PESO… | 22.770 | 982 | 30,5% |

## Por bodega comercial

- **ALM** (001): QUIEBRE=358, MUERTO=801, SOBRESTOCK=1.185, stock=763.230, med. cob.=98,6 d
- **DIS** (DISTRIBUCIONES): QUIEBRE=212, MUERTO=884, SOBRESTOCK=631, stock=109.724, med. cob.=117,0 d
- **SUR** (SUR): QUIEBRE=63, MUERTO=74, SOBRESTOCK=103, stock=204.663, med. cob.=59,9 d
- **BD6** (BD6): QUIEBRE=59, MUERTO=53, SOBRESTOCK=97, stock=101.536, med. cob.=56,6 d
- **FLO** (ALMACEN FLORENCIA): QUIEBRE=52, MUERTO=55, SOBRESTOCK=102, stock=7.406, med. cob.=90,0 d

## Metodología

1. **Demanda comercial** (`Venta_Comercial_Nd`): modo `warehouse` — SKU×bodega via InvVentasDetalle (J3). Exclusión de venta `XY, AS, TS, YX, ISC` (no aplica a salidas de inventario TS/ISC).
2. **Stock**: `InvDetalleExistencias.SaldoActual` (incluye negativos); solo bodegas ALM, SUR, BD6, DIS, FLO.
3. **Salida física YTD**: suma mensual `SalidasEne…Dic` en existencias (movimientos de inventario ya contados en el ERP).
4. **Banderas:** QUIEBRE (stock≤0 o cob.<7d con demanda en esa bodega), BAJA_COBERTURA (7–30d), SALUDABLE (30–120d), SOBRESTOCK (>120d), MUERTO (stock>0 sin venta comercial en esa bodega).
5. La exclusión de códigos de documento es un **filtro de hechos de venta**, no implica que esos documentos no muevan inventario físico.
