# Physical inventory audit — Distribuciones (`DIS`)

**As of:** 2026-08-29 (J3 `InvDetalleExistencias.Ano=2026`, not a daily snapshot)
**Warehouse:** `AdmAlmacen.AlmacenCodigo = DIS` (`AlmacenID = 10`)
**Branch:** `plan/dis-physical-inventory-audit`
**Workflow:** `dis-physical-inventory-plan` (9 agents, **3/3** verification panels confirmed)

User-facing procedure below is in Colombian Spanish. Identifiers stay as J3 codes.

**One-line recommendation:** ABC + excepciones sobre SKU **con existencias de mercancía** en DIS. No wall-to-wall de 6.813 filas.

---

# Plan operativo — inventario físico DIS (DISTRIBUCIONES)

**Corte:** `InvDetalleExistencias.Ano=2026` al 2026-08-29.
**Conteo J3 ya abierto:** `InvConteoInventario.ConteoID=1`, Estado=0, Almacenes=`DIS`, Detalle=`INVENTARIO GENERAL`, responsable **1075225347 JHON JENIER HERNANDEZ GOMEZ**. No abrir otro encabezado.

## 1. Objetivo

Conteo ciego por olas que cubra **~95 % del capital** de DIS y cierre los huecos de kardex el mismo día, para poder confiar el stock vendible (DIS está en allowlist web; EXD en denylist) y reemplazar el IFD de 2022-10-03.

## 2. Por qué no conteo total (6.813 SKU)

| Universo DIS 2026 | SKU | Qué hacer |
|---|---:|---|
| Mercancía `SaldoActual>0` | **1.984** | Contar (olas 1–3) |
| Mercancía `SaldoActual<0` | **45** | Ola 0, mismo día |
| Ceros | **4.779** | No contar (70,1 % del catálogo; no hay bins) |
| Flete/servicio negativo | **3** | No contar (`0110010001`, `0080500001`, `0130010001`) |
| Servicio positivo (tipo 2) | **2** | No contar (`0130010006` «.» = $36.695.460 y `0130010004`) |
| Total filas | **6.813** | — |

1. **Sin ubicaciones.** `AdmUbicacion=0`, `AdmUbicacionAlmacen` DIS=0. Un wall-to-wall sin bins es caminar 4.779 vacíos.
2. **Concentración.** 182 SKU de mercancía (9,2 % de 1.984) = **80,03 %** del costo ($1.810.471.285,52 de $2.262.240.199,55). 682 SKU = **95,01 %**. ABC recalculado **sin servicios** (el SKU «.» de $36,7 M no entra a clase A).
3. **El neto 59.383,6 und miente.** Tres fletes cargan −65.669 und. Neto mercancía ≈ **125.504,6** und positivas.
4. **IFD desactualizado.** Último posted DIS = IFD `VentaID=17` **2022-10-03**, 878 líneas, `Conteo1`/`Conteo2` NULL. Hoy hay 1.984 SKU vivos.
5. **EXD no es bodega gemela.** 96 SKU / 97 und, 0 negativos; 0 SKU cubren los negativos DIS. EXD es denylist web y de rotación.

## 3. Olas (personal por valor, no por número de SKU)

### Ola 0 — excepciones (mismo día) · 45 SKU

Negativos de mercancía (−459 und; −$4.078.291). Top: tornillo 2"×12 −184; yeso extra −49; piso Cuenca beige −46; cuerda marina 6 mm −35. 23 SKU en −1. Planilla ciega; `Conteo1` en sección `DIS-W0-NEG`. No `AS` el mismo día. Los 3 fletes quedan fuera.

### Ola 1 — clase A · 182 SKU (80,03 % $)

Congelar DIS. Cuadrilla **cerámica primero** (153/182 enchapes: Eurocerámica 72, Paredes y Pisos 32, Alfa 21, Italia 20, EMO 6). Contar **cajas** (= UND J3). `C*x.xxM` solo para validar empaque; no mezclar m². Luego sanitarios, Sika bultos, zinc, cemento. Cualquier `|Δqty|≥1` → `Conteo2`. Sección `DIS-W1-A`.

### Ola 2 — clase B · 500 SKU (hasta 95,01 % $)

Ranks 183–682. Recorrido: PVC (53), grifería (51), sala enchapes (46), Sika (41), sanitarios/lavaplatos/tanques. Reconteo si `|Δvalor|≥ $200.000` o `|Δqty|>2 %`. Sección `DIS-W2-B`.

### Ola 3 — clase C · 1.302 SKU (4,99 % $)

Barrido por grupo/zona. No igualar horas a A. Aquí vive la cola muerta (~904 SKU con stock y 0 venta 90 d). Cerrar `Conteo1` de los **1.984** positivos. Sección `DIS-W3-C`.

### Ola 4 — no identificados + ceros con demanda · 174 SKU

No se recorren 4.779 ceros. Muestra dirigida: **174** SKU mercancía vendidos 90 d (2026-05-31..2026-08-29, docs FET/FED, excl. XY/AS/TS/YX/ISC) con `SaldoActual=0`. Prioridad: 43 con qty≥20 (combo Urban, Viniltex 5 gal, sanitario Urban, piso Mónaco negro). Hallados sin código → `DIS-W4-SWEEP` (foto + código).

**Opcional después (no es DIS):** barrido corto EXD, 96 SKU / 97 und, planilla propia. Nunca sumar a DIS ni a web.

**Staffing:** cerámica (valor) → bultos/voluminosos → PVC/ferretería (SKU). Grifería es 253 SKU y ~1,9 % del costo: va tarde, en B/C.

**To-count:** 45 + 1.984 + 174 ≈ **2.203 líneas** (+ 96 EXD opcional). No 6.813.

## 4. Corte / freeze

Por **cada** ola, no de toda la semana de una vez (DIS factura FET/FED todos los días; 1.279 SKU movieron en 90 d):

1. Congelar **compras, recepciones y traslados** hacia/desde DIS hasta `Conteo1`+varianza de esa ola.
2. Si el mostrador permanece abierto: **vale de corte** (hora, `ArticulosCodigo`, cantidad, número de FET/FED). Restar esas salidas del `Conteo1` antes de comparar con libro.
3. Mesa de control toma foto `SaldoActual` Ano=2026 `AlmacenID=10` al arranque de la ola. Esa columna **no** va en la planilla del contador.
4. Traslados desde ALM/SUR/BD6/FLO para quiebres DIS se aplazan hasta cerrar la ola del SKU (118/195 quiebres mercancía tienen excedente en esas bodegas; no usar EXD).

## 5. J3 — cómo capturar

Usar el conteo ya abierto; no crear otro encabezado.

| Tabla | Estado hoy | Acción |
|---|---|---|
| `InvConteoInventario` | ConteoID=1, Estado=0, DIS | Seguir este ID |
| `InvSeccionesInventario` | 0 filas | Crear `DIS-W0-NEG`, `DIS-W1-A`, `DIS-W2-B`, `DIS-W3-C`, `DIS-W4-SWEEP` |
| `InvParametroInveFisico` | 0 filas | Ignorar; las listas salen del ranking ABC mercancía |
| `InvInveFisicoDetalle.Conteo1/Conteo2` | 4.601/4.601 NULL (nunca usados) | Aquí va el doble conteo |
| `InvInveFisico` DIS | IFD `VentaID=17`, 2022-10-03, 878 líneas | No reabrir |
| Docs AE/AS/ASI/IET/IF/IFD/IND | IFD = inventario DIS 2022; IND = 14 compras 2022-10-01; último AS DIS = **2025-07-02** | No postear ajustes hasta firma |

Planillas ciegas: `ArticulosCodigo`, `ArticulosNombre`, grupo, unidad, zona, casilla `Conteo1`, casilla `Conteo2`. Sin `SaldoActual`, sin costo, sin clase ABC visible al contador (ABC solo en mesa de control).

## 6. Doble conteo y umbral de varianza

1. Todo SKU de olas 0–3 tiene `Conteo1`.
2. Disparar **`Conteo2`** (otro contador, misma planilla ciega) si:
   - clase **A:** `|Conteo1 − SaldoActual| ≥ 1`;
   - **cualquier clase:** `|Δqty| × ArticulosCosto ≥ $200.000`;
   - clase **B o C:** `|Δqty| / SaldoActual > 2 %` (si `SaldoActual=0` en ola 4, cualquier qty>0 dispara `Conteo2`).
3. Enchapes: comparar **cajas vs cajas**. Si el empaque no coincide con `C*x.xxM` del nombre, anotar m² aparte; no cambiar la UND del ERP.
4. Mesa de control calcula Δ y valor; el piso no ve el libro.

## 7. Ajustes (después de firma)

Paquete de varianza para gerencia, por ola: SKU, nombre, grupo, `Conteo1`, `Conteo2`, `SaldoActual` de corte, Δ qty, Δ $, foto si ola 4.

Separar: faltante mercancía vs sobrante vs hueco de kardex ola 0 vs servicio (estos últimos **no** se ajustan como inventario).

Investigar `0130010006` «.» ($36.695.460, qty 6, tipo 2) como fantasma de libro **antes** de cualquier cierre de costo; no entra a IFD.

**No postear AE/AS** (ni ASI/IET) hasta firma. Recién entonces:

- Faltantes → `AS` (`AJUSTE DE SALIDA`) o el flujo que J3 exija sobre el conteo.
- Sobrantes → `AE` (`AJUSTE DE ENTRADA`).
- El documento histórico de cierre DIS es **`IFD`**. Si gerencia elige IFD vs AE/AS línea a línea, se documenta en el paquete; **no improvisar IND** (eso fue compra de apertura 2022-10-01).

El proceso AS DIS está **parado desde 2025-07-02** (13+ meses) con 45 negativos vivos: este conteo es el reinicio, no un AS suelto.

## 8. Métodos de conteo por familia (sin bins)

| Zona / grupo | Cómo contar | Nota |
|---|---|---|
| Eurocerámica, Alfa, Italia, Paredes y Pisos, EMO, Decorados | Cajas + sueltas | UND = caja; m² solo cuadre empaque |
| Sala enchapes | Varillas / piezas | No m² |
| PVC accesorios | Pieza (codos, uniones) | 190 SKU / 42.040 und |
| Tubos y perfilería | Varilla | |
| Grifería, tornillos, empaques | Empaque interno sellado | Alta SKU, bajo $ |
| Sika / cemento / yeso / pegante | Pallet × bulto; cartuchos y rollos aparte | Tres sub-recorridos Sika |
| Sanitarios, tanques, lavaplatos | Unidad | |
| Servicios / flete / «.» | No contar | Tipo 2 |

## 9. Siguiente ciclo (cuando este cierre quede estable)

| Clase | Universo | Frecuencia |
|---|---|---|
| A | ~182 SKU (rehacer ranking cada ciclo) | **Mensual** |
| B | ~500 SKU | **Trimestral** |
| C | ~1.302 SKU positivos | **Anual** (con barrido de piso) |
| Excepciones | Negativos mercancía + vendidos-90d-con-cero | Con cada ciclo A |
| Ceros de catálogo | 4.779 | No ciclar; limpieza de surtido |

Rehacer ABC con `SaldoActual>0` AND `ArticulosTipo<>2` AND código no denylist, mismo corte DIS Ano vigente. Mantener EXD fuera. Tras el primer cierre, poblar `InvSeccionesInventario` permanente por zona física aunque J3 no tenga bins.

## 10. Fuera de alcance / no hacer

- Wall-to-wall 6.813 o conteo de ceros «por si acaso».
- Mezclar EXD, CON, B.ROT, CEN u otras bodegas en las planillas DIS.
- Mostrar existencias al contador.
- Tratar enchapes como m² en el ERP.
- Ajustar fletes `008050*` / `0110010001` / `0130010001` como mercancía.
- Publicar AE/AS sin firma.
- Cubrir quiebres DIS con exhibición.

---

## What this repo already has (do not rebuild)

| Tool | Role |
|---|---|
| `inventory_warehouse_policy.py` | `DIS` commercial allowlist; `EXD` excluded |
| `scripts/analysis/run_critical_inventory.py` | Quiebre shortlist (DIS already appears) |
| `scripts/analysis/run_rotacion_existencias.py` | MUERTO / SOBRESTOCK / QUIEBRE |
| J3 `InvConteoInventario` / `InvInveFisico*` | The actual count, not a new Python module |

A later change (only if ops asks) can emit **blind count sheets** (CSV/XLSX) from `InvDetalleExistencias` for DIS with ABC class and grupo, **without** `SaldoActual` on the counter copy.

## Related

- `docs/reference/j3system-sales-warehouse-query.md` — warehouse codes; no bin master
- `docs/reference/website-warehouse-allowlist.md` — `DIS` sellable, `EXD` denylist
- Workflow definition (gitignored): `.grok/workflows/dis-physical-inventory-plan.rhai`

## Open decisions for ops

1. Confirm Jhon Jenier is count lead; name a second counter + a variance desk who is **not** counting.
2. Confirm posting document: **`IFD` vs AE/AS línea a línea** (do not use `IND`).
3. Whether the store stays open (cut-off tickets) or DIS picking pauses per wave.
4. Whether Wave 4 includes the `EXD` exhibit sweep the same week.
