# Contrato — `catalog.stock` (disponibilidad por SKU/sede)

> **Estado:** Implementado en la rebanada 1 (B0+B1). La implementación, sus
> tests fake-only y el registro en `builtins.py` están incluidos.
> **Alcance:** define únicamente el contrato de entrada/salida/errores de `catalog.stock`.
>
> **Supersede el borrador anterior:** la decisión vigente de Fredy permite cifras exactas de
> existencia como **dato de herramienta**, solo cuando se validan en el servidor (§9); **no** hay
> aritmética del modelo sobre las cifras. Se eliminan los estados gruesos (`hay` /
> `pocas_unidades` / `no_hay`); se sustituyen por cantidades exactas en base-10, sin `float`, sin
> redondeo y sin umbral activo.
>
> **Mapeo de bodega confirmado (22 oct 2026):** `FLO = Florencia`; `ALM`, `SUR`, `BD6`, `DIS` y
> `BOD` = Neiva (§7). Este contrato coincide con el set `SITES` del contrato B2
> (`neiva: (ALM, BD6, SUR, DIS, BOD)`, `florencia: (FLO,)`). `B.ROT` permanece como bodega virtual
> aparte; `CON` permanece excluida.
>
> **Audiencia/scope:** alineado con B2: `ToolScope.SALES_PORTFOLIO`, usable por `SALES` y `ADMIN`,
> `public_safe=False` (§14.5). No hay gate de audiencia pendiente.

---

## 1. Propósito

Responder, por SKU y sede, con **cantidades exactas de existencia** (base-10, sin redondeo ni
umbral activo), separando de forma determinista:

- la cantidad física de la sede **`neiva`** (`ALM`, `BD6`, `SUR`, `DIS`, `BOD`, §7);
- la cantidad física de la sede **`florencia`** (`FLO`, §7);
- la bodega virtual `B.ROT`, en línea aparte y **nunca** sumada ni atribuida a una sede.

Es una consulta de disponibilidad por SKU/sede como **dato de herramienta para un flujo de venta
autorizado** (§14.5). Un resultado de herramienta **no** es, por sí mismo, permiso para enviar un
mensaje no validado a un cliente. **No** expone precios ni costos. Toda cifra emitida debe haber
sido **validada por el servidor** (ver §9) antes de poder presentarse. La herramienta responde
**fail-closed**: ante cualquier ambigüedad, bloquea la cifra y **no afirma nada** sobre existencia.

---

## 2. Entrada (cerrada)

```json
{
  "skus": ["<sku1>", "<sku2>"],   // obligatorio, 1..5 elementos
  "sede": "neiva"                 // opcional: "neiva" | "florencia"
}
```

| Campo | Tipo | Regla |
|-------|------|-------|
| `skus` | `string[]` | Obligatorio. 1 a 5 códigos. Cada SKU: no vacío, ≤ 40 caracteres, solo `[A-Za-z0-9._-]`. |
| `sede` | `string \| null` | Opcional. Valores válidos: `"neiva"`, `"florencia"`. `null`/ausente → ambas sedes. |

**Normalización (orden explícito, antes de cualquier filtro o consulta):**

Por cada elemento de `skus`, el orden es fijo y secuencial: **1) chequeo de tipo** (debe ser
`str`; cualquier otro tipo → `entrada_invalida`) → **2) trim** (espacios al inicio/final) →
**3) uppercase** → **4) validación del alfabeto canónico ASCII** (`[A-Z0-9._-]`, no vacío, ≤ 40
caracteres, aplicado sobre la forma normalizada) → **5) detección de duplicados normalizados**.
Cualquier paso que falle → `entrada_invalida` (global, §5).

- El input crudo puede llevar espacios en blanco al inicio/final o letras en cualquier caja; se
  normalizan (trim + uppercase) **antes** de validar. Un carácter no ASCII o no permitido que
  sobreviva al trim → inválido.
- **Duplicados normalizados:** si dos elementos de `skus` producen el mismo SKU normalizado
  (p. ej. `"abc"` y `"ABC"`, o `" abc "` y `"ABC"`), se rechaza con `entrada_invalida` (global).
  No se deduplican en silencio.
- Códigos de bodega se normalizan con **trim + uppercase** antes de comparar con el catálogo, la
  denylist y el mapeo de sede. `sede` se normaliza con trim + lowercase.
- La normalización **solo** es para clasificar/filtrar/validar; **no** crea ni altera un valor de
  cantidad.

**Esquema cerrado:** solo se admiten las claves `skus` y `sede`. Cualquier clave extra, tipo
inesperado, o `skus`/`sede` con forma distinta a la declarada → `entrada_invalida` (§5). Esta
validación ocurre **antes** de abrir cualquier conexión a base de datos (fail-closed).

**Violaciones de entrada** → error global `entrada_invalida` (fail-closed, ver §5).

**Consecuencia de mapeo:** ambos mapeos (`neiva` y `florencia`) están **confirmados** (§7).
`sede: "neiva"`, `sede: "florencia"` y `sede` ausente (ambas) son todos casos válidos; `sede`
ausente/nulo solicita ambas sedes en un solo `results`.

---

## 3. Salida (cerrada)

Hay **dos** envoltorios mutuamente excluyentes:

### 3.1 Éxito global (`ok: true`)

```json
{
  "ok": true,
  "sede": "ambas",
  "results": [
    {
      "sku": "ABC123",
      "status": "ok",
      "sedes": { "neiva": "12.34", "florencia": "5.00" },
      "baja_rotacion": null,
      "baja_rotacion_confirmation": "not_required"
    },
    {
      "sku": "DEF456",
      "status": "ok",
      "sedes": { "neiva": "0", "florencia": "0" },
      "baja_rotacion": "7.50",
      "baja_rotacion_confirmation": "required"
    },
    { "sku": "GHI789", "status": "no_encontrado" },
    { "sku": "JKL012", "status": "inventario_desconocido" },
    { "sku": "MNO345", "status": "bloqueado", "reason": "saldo_negativo" }
  ]
}
```

> Las cifras de los ejemplos son **ilustrativas**; su escala exacta no está demostrada (§9.1) y no
> fijan un formato de salida. La escala real depende del valor `Decimal` leído y canonicalizado
> (§9.2), no de estos ejemplos.

`sede` (resuelta) refleja la selección de entrada: `"neiva"`, `"florencia"` o `"ambas"` (cuando
`sede` fue `null`/ausente). `results` tiene **exactamente un elemento por SKU solicitado**, en el
mismo orden de `skus`. Cada elemento lleva un `status` por SKU que **nunca mezcla** un SKU fallido
con cifras ambiguas.

| `status` | Significado | Campos presentes |
|----------|-------------|------------------|
| `"ok"` | SKU en catálogo y con inventario consultable; cifras emitidas. | `sedes`, `baja_rotacion`, `baja_rotacion_confirmation` |
| `"no_encontrado"` | El SKU no existe en `AdmArticulos`. | solo `sku`, `status` |
| `"inventario_desconocido"` | El SKU existe pero **no hay dato de inventario consultable**. | solo `sku`, `status` |
| `"bloqueado"` | Cifras bloqueadas (negativo, código no clasificado, NULL de saldo, o validación §9 no satisfecha). | `sku`, `status`, `reason` (string fija) |

`reason` de `bloqueado` es una cadena **fija** de un catálogo cerrado (§5): `"saldo_negativo"`,
`"codigo_no_clasificado"`, `"validacion_fallida"`. Nunca texto del driver/SQL/credencial.

**Para un elemento `"ok"`:**

| Campo | Tipo | Regla |
|-------|------|-------|
| `sedes.neiva` | `string (decimal) \| null` | Cantidad física de la sede `neiva` (`ALM`, `BD6`, `SUR`, `DIS`, `BOD`, §7). `null` = **sin fila** para ese bucket (desconocido); string decimal = valor con evidencia de fila. Ver tri-estado §4. |
| `sedes.florencia` | `string (decimal) \| null` | Cantidad física de la sede `florencia` (`FLO`, §7). `null` = sin fila; string decimal = valor con evidencia de fila. |
| `baja_rotacion` | `string (decimal) \| null` | Cantidad de la bodega virtual `B.ROT`, en línea **aparte**. `null` = sin fila. |
| `baja_rotacion_confirmation` | `string (enum)` | `"required"` \| `"not_required"` \| `"unknown"` (§8). |

Cuando `sede` resuelve a una sola sede, `sedes` contiene solo esa clave; cuando resuelve a
`"ambas"`, contiene `neiva` y `florencia`.

### 3.2 Error global (`ok: false`)

```json
{
  "ok": false,
  "error": { "type": "error_consulta", "message": "error consultando inventario J3" }
}
```

No hay `results` ni **ninguna** cifra cuando la respuesta es `ok: false`.

**Invariantes de salida (no negociables):**

- Toda cantidad emitida es **string decimal canónico base-10 no negativo** (`^\d+(\.\d+)?$`),
  nunca un número JSON (evita `float`/IEEE-754). Ver §9.
- `null` significa **desconocido** (sin fila); **nunca** se traduce a `"0"`. Un `"0"` solo se emite
  cuando hay **evidencia de fila** para ese bucket (§4).
- Nunca se devuelve precio ni costo (`ArticulosVenta`, `VentaMasIva`, etc.).
- `baja_rotacion` **nunca** se suma a `neiva` ni a `florencia`; permanece en su línea aparte.
- Un fallo de ERP **no** produce una cifra ni un "cero"; produce `error_consulta` (§5).

---

## 4. Semántica de cantidades (exactas, sin umbral activo, tri-estado por bucket)

Cada cantidad es el **saldo exacto en base-10** de la fila más reciente de
`InvDetalleExistencias.SaldoActual` por (artículo, almacén), agregado **solo en Python con
`Decimal`** por bucket de bodega, **sin** redondeo, **sin** umbral activo y **sin** clamp a cero.

**Último período por par (artículo × almacén):** el SQL selecciona una fila por par
(`ArticulosID`, `AlmacenID`) usando `ROW_NUMBER() OVER (PARTITION BY ArticulosID, AlmacenID
ORDER BY Ano DESC) = 1` (§11). **No** se usa `MAX(Ano)` global ni un período elegido para toda la
tabla/SKU. `Ano` es numérico. No se afirma que el período elegido sea un año calendario ni que
represente una instantánea en tiempo real: es el **período registrado más reciente** presente en la
tabla para ese par (una cifra histórica registrada, no una garantía de stock actual). No se afirma
que haya **exactamente una** fila por par: la unicidad no está demostrada.

**Empate en el período máximo (fail-closed):** el SQL devuelve además un marcador de multiplicidad
`num_filas_ano` (número de filas que comparten el `(ArticulosID, AlmacenID, Ano)` seleccionado, por
ejemplo `COUNT(*) OVER (PARTITION BY ArticulosID, AlmacenID, Ano)`). Si para la fila seleccionada
(`rn = 1`) ese marcador es `> 1`, hay un **empate** en el período máximo y el origen de la cifra no
es determinista: ese SKU se bloquea con `reason: "validacion_fallida"`, **sin cifras**. No se
inventa un desempate; se falla cerrado. El bloqueo afecta solo al SKU en cuestión.

**Tri-estado por bucket (determinista, sin colapsar ausencia a cero):**

| Estado | Condición | Emisión |
|--------|-----------|---------|
| **positivo** | El bucket tiene ≥1 fila incluida y su suma `Decimal > 0`. | String decimal exacto (p. ej. `"12.34"`). |
| **cero con evidencia** | El bucket tiene ≥1 fila incluida y su suma `Decimal = 0`. | `"0"` (hay evidencia de fila: el SKU sí tiene dato en ese bucket y no aporta saldo). |
| **ausente** | El bucket **no tiene fila incluida**. | `null` (desconocido). **Nunca** `"0"`. |

Un bucket sin fila es **desconocido**, no cero. Cero solo se emite con evidencia directa de fila
para ese bucket.

**Negativos (decidido): revisión por código, antes de agregar.**

- El SQL **no** agrega ni filtra por signo; devuelve el saldo **crudo** de la fila más reciente por
  código de bodega. La clasificación y la revisión de negativos ocurren en el handler, **antes** de
  cualquier suma.
- Orden de evaluación por SKU: normalizar/`trim+uppercase` → excluir `CON`/denylist (§6) →
  clasificar cada código en su bucket (o como no clasificado).
- Para cada código **incluido** (`FLO`, `ALM`, `BD6`, `SUR`, `DIS`, `BOD`, `B.ROT`), se inspecciona
  el saldo de su fila más reciente: si es **negativo**, el SKU se bloquea con
  `reason: "saldo_negativo"`, **sin ningún número**. Un negativo en cualquier bucket incluido
  (`neiva`, `florencia` o `B.ROT`) bloquea el SKU.
- Un negativo en un código **excluido** (`CON` o denylist) se **ignora** para esta herramienta,
  porque ese código está excluido de todo bucket de salida.
- Un código **desconocido, nulo, blanco o nuevo** nunca se descarta en silencio: bloquea el SKU con
  `reason: "codigo_no_clasificado"` (§5, §6.3).
- Un saldo `NULL` en una fila más reciente **incluida** falla cerrado como
  `reason: "validacion_fallida"`; **nunca** se coalesce a cero.
- Solo después de esa revisión se **agregan** las filas incluidas restantes por bucket, en Python,
  usando únicamente `Decimal`. No hay aritmética del modelo sobre las cifras.

**Marcador de fila real, integridad SKU→artículo y empate de período (fail-closed):**

- El SELECT devuelve `d.AlmacenID` como **marcador de existencia de fila** (no nulo = fila real) y
  `ArticulosID` (para detectar que un SKU normalizado no corresponda a más de un artículo). No se
  asume que `AdmArticulos.ArticulosCodigo` sea único, ni que `ArticulosID` sea único a través del
  catálogo (la evidencia disponible no lo demuestra). Las filas de catálogo duplicadas para el
  mismo SKU normalizado y el mismo `ArticulosID` se deduplican **antes** de unir inventario (§10,
  §11), de modo que no multiplican el saldo de detalle.
- El SELECT devuelve `num_filas_ano` (multiplicidad de filas en el `(ArticulosID, AlmacenID, Ano)`
  seleccionado). Si la fila seleccionada tiene `num_filas_ano > 1` (empate en el período máximo),
  el SKU se bloquea con `validacion_fallida`, sin cifras. No se inventa un desempate.
- La precedencia de bloqueos por SKU es determinista (§5.2).

Los buckets se computan de forma determinista (§6, §7, §8):

| Bucket | Códigos de bodega (normalizados) |
|--------|----------------------------------|
| `sedes.neiva` | `ALM`, `BD6`, `SUR`, `DIS`, `BOD` (confirmado, §7). |
| `sedes.florencia` | `FLO` (confirmado, §7). |
| `baja_rotacion` | `B.ROT` (virtual). |

`CON` (§6.1) y la denylist (§6.2) quedan **excluidas** de los tres buckets. Cualquier código
**desconocido, nulo, blanco o nuevo** (no presente en el set conocido) **no** se agrega a ningún
bucket: bloquea el SKU con `reason: "codigo_no_clasificado"` (§5, §6.3). No existe un bucket
"no mapeado": todo código reconocido pertenece a `neiva`, `florencia`, `B.ROT`, o a la exclusión.

> **Propuesta informativa (NO aprobada / NO activa):** un umbral de "pocas unidades" de **5
> unidades por sede física** queda registrado solo como propuesta pendiente. **No** está aprobado
> por Fredy y **no** está activo en este contrato; la salida primaria sigue siendo la cantidad
> exacta, sin clasificar ni filtrar por ese umbral. Ver §15.

---

## 5. Errores tipados (fail-closed)

Hay dos niveles: **errores globales** (`ok: false`) y **status por SKU** (dentro de `results`).

### 5.1 Errores globales (`ok: false`)

| `error.type` | Significado | Distinto de |
|--------------|-------------|-------------|
| `entrada_invalida` | Entrada mal formada: SKUs vacíos, >5, caracteres inválidos, sede inválida, clave extra, tipo inesperado. | — |
| `error_consulta` | Fallo de infraestructura o integridad: timeout, conexión caída, error SQL, ERP no disponible, excepción, resultado no `list`, fila sin claves, SKU inesperado, resultado inválido, centinela alcanzado (§11). | `[]` / cero / cifra parcial |

**Reglas duras:**

- `error_consulta` **nunca** se traduce a `[]`, cero ni cifra. Ante fallo la herramienta responde
  `error_consulta` y **no afirma nada** sobre existencia.
- **Mensajes fijos:** `message` es una cadena **fija** del catálogo. **Nunca** se copia texto del
  driver, del SQL, de la excepción ni de credenciales. Catálogo cerrado:
  - `entrada_invalida` → `"entrada inválida para catalog.stock"`.
  - `error_consulta` → `"error consultando inventario J3"`.
- Excepción no capturada, `rows` que no sea `list`, fila a la que le falte una clave esperada,
  un SKU en el resultado que no esté entre los solicitados, o un resultado que no se pueda
  interpretar → `error_consulta`, **nunca** `[]`/cero.

### 5.2 Status por SKU (dentro de `results`, solo con `ok: true`)

Cada fila de detalle es **real** solo si el marcador `d.AlmacenID` (clave del lado detalle, §10) es
**no nulo**. `inventario_desconocido` se define **únicamente** como: el SKU normalizado corresponde
a **un solo** `ArticulosID` y ese artículo **no tiene ninguna fila de detalle real** (marcador
`NULL` para ese SKU). Una fila real con código de bodega desconocido/`NULL`/blanco/no coincidente
es **inventario real pero no clasificable** y **siempre** bloquea (§6.3), nunca se reporta como
"sin dato". La integridad SKU→artículo (uno o varios `ArticulosID` distintos) se evalúa **antes**
que la presencia de filas de detalle reales (precedencia §5.2).

| Caso | `status` | Efecto |
|------|----------|--------|
| SKU en catálogo, con ≥1 fila de detalle real y clasificada en un bucket (tri-estado §4). | `"ok"` | Cifras exactas por bucket (tri-estado §4). |
| Ningún `ArticulosID` corresponde al SKU normalizado (`AdmArticulos` no contiene el SKU). | `"no_encontrado"` | Sin cifras (no cero). |
| El SKU corresponde a **un solo** `ArticulosID` y ese artículo no tiene **ninguna fila de detalle real** (marcador `d.AlmacenID` `NULL`). | `"inventario_desconocido"` | Sin cifras (no cero). |
| El artículo existe y **todas** sus filas de detalle reales caen en códigos **excluidos** (`CON`/denylist), sin ningún bloqueo. | `"ok"` | `sedes.neiva` y `sedes.florencia` = `null`, `baja_rotacion` = `null`, `baja_rotacion_confirmation` = `"not_required"`. |
| Un SKU normalizado corresponde a **más de un** `ArticulosID` distinto (aunque ninguno de esos `ArticulosID` tenga fila de detalle real). | `"bloqueado"` / `reason: "validacion_fallida"` | Sin cifras; nunca se mezclan saldos de artículos distintos. |
| Fila de detalle real con código de bodega **desconocido/`NULL`/blanco/no coincidente**. | `"bloqueado"` / `reason: "codigo_no_clasificado"` | Sin cifras. |
| Algún código **incluido** tiene saldo **negativo** en su fila seleccionada. | `"bloqueado"` / `reason: "saldo_negativo"` | Sin cifras. |
| Empate en el período máximo (`num_filas_ano > 1` en la fila seleccionada). | `"bloqueado"` / `reason: "validacion_fallida"` | Sin cifras. |
| Un saldo incluido es `NULL`, o una cifra no pasa la validación exacta (§9), o su origen no está demostrado. | `"bloqueado"` / `reason: "validacion_fallida"` | Sin cifras. |

- `"no_encontrado"` ≠ cero: "no existe el producto" vs "sé que el saldo es exactamente cero".
- `"inventario_desconocido"` ≠ cero: "no puedo saber" vs "sé que es exactamente cero". Se
  distingue "artículo no encontrado" de "artículo encontrado pero sin dato de inventario real".
- El caso **solo-excluido** (solo `CON`/denylist, sin bloqueos) es `"ok"` con todos los buckets
  `null`: hay inventario, pero ninguno consultable para los buckets de salida. No es
  `inventario_desconocido` (hay filas reales) ni `bloqueado` (no hay condición de bloqueo).
- Un fallo **global** de consulta produce `ok: false` sin **ninguna** cifra; un fallo **de un SKU**
  produce un elemento `bloqueado` sin cifras para ese SKU, sin contaminar a los demás.

**Precedencia de bloqueo por SKU (determinista; primero que aplique gana):** cuando un SKU
satisface varias condiciones, se reporta una sola `reason`, en este orden fijo:

1. `no_encontrado` — ningún `ArticulosID` corresponde al SKU normalizado.
2. `validacion_fallida` — más de un `ArticulosID` distinto para el SKU normalizado (se evalúa antes
   de la presencia de filas de detalle reales).
3. `inventario_desconocido` — un solo `ArticulosID` y sin fila de detalle real.
4. `validacion_fallida` — empate en el período máximo (`num_filas_ano > 1`).
5. `codigo_no_clasificado` — alguna fila real con código desconocido/`NULL`/blanco/no coincidente.
6. `saldo_negativo` — algún código incluido con saldo negativo.
7. `validacion_fallida` — algún saldo incluido `NULL` o cifra que no pasa §9.
8. `ok` — en su defecto.

---

## 6. Política comercial (ya decidida)

1. **`CON` (Contabilidad) queda excluida** de toda agregación de disponibilidad.
2. **Denylist de bodega física** (no vendible en web/tienda) queda excluida de la disponibilidad
   por sede: `CEN` (garantías), `EXH`/`EXD` (exhibición), `BDT` (ajustes temporales), `MDL`
   (Mercado Libre), `TRA` (Comitecafé).
3. **`B.ROT` es bodega virtual sin sede** (ver §8).

> Nota: esta política comercial **no** es idéntica al allowlist web
> (`website_warehouse_policy`), que incluye `CON` y `B.ROT` para la agregación web. El allowlist
> web **no** se reutiliza como política comercial.

**Clasificación determinista de códigos (con normalización trim+uppercase):**

| Código (normalizado) | Clasificación |
|----------------------|---------------|
| `ALM`, `BD6`, `SUR`, `DIS`, `BOD` | `sedes.neiva` |
| `FLO` | `sedes.florencia` |
| `B.ROT` | `baja_rotacion` |
| `CON`, `CEN`, `EXH`, `EXD`, `BDT`, `MDL`, `TRA` | **excluido** (no participa) |
| cualquier otro / nulo / blanco | **no clasificado** → `bloqueado` |

El orden de evaluación es: normalizar → excluir `CON`/denylist → clasificar en bucket; si el código
no cae en ninguno de los sets anteriores, es **no clasificado** y bloquea el SKU (no se agrega a
ningún bucket).

---

## 7. Mapeo códigos físicos → sede

**Confirmado por Fredy el 22 oct 2026: `FLO = Florencia`; `ALM`, `SUR`, `BD6`, `DIS` y
`BOD` = Neiva.** El set coincide con el `SITES` del contrato B2: `neiva: (ALM, BD6, SUR, DIS, BOD)`,
`florencia: (FLO,)`.

| Código | Sede | Estado de la evidencia |
|--------|------|------------------------|
| `FLO` | `florencia` | **Confirmado** (Fredy, 22 oct 2026). |
| `ALM` | `neiva` | **Confirmado** (Fredy, 22 oct 2026). |
| `BD6` | `neiva` | **Confirmado** (Fredy, 22 oct 2026). |
| `SUR` | `neiva` | **Confirmado** (Fredy, 22 oct 2026). |
| `DIS` | `neiva` | **Confirmado** (Fredy, 22 oct 2026). |
| `BOD` | `neiva` | **Confirmado** (Fredy, 22 oct 2026). |

Los códigos de la denylist (§6.2) y `CON`/`B.ROT` (§6.1, §8) **no** participan en este mapeo.

**Consecuencia operativa:** ambos mapeos están confirmados; no existe bucket "no mapeado" ni
ambigüedad de "no mapeado como Neiva o Florencia". Pedir `sede=neiva`, `sede=florencia` o ambas es
válido (§2). Un código **no reconocido** va a `codigo_no_clasificado` (§6), **no** se une a un
bucket de sede.

---

## 8. `B.ROT` (bodega virtual, baja rotación)

- `B.ROT` es una bodega **virtual sin sede** (`PRODUCTOS DE BAJA ROTACION`).
- Se devuelve **únicamente** como la línea aparte `baja_rotacion`, con cantidad exacta (o `null` si
  no hay fila). Nunca entra dentro de `sedes.<sede>`.
- **Nunca** se suma a `neiva` ni a `florencia`.
- **Nunca** se usa sola para afirmar existencia física en una sede.
- Se advierte **posible solapamiento** entre `B.ROT` y las bodegas físicas (el saldo en `B.ROT` puede
  duplicar saldo físico ya contabilizado). Las cantidades permanecen separadas y nunca se totalizan.

**`baja_rotacion_confirmation` — señal tri-estado (cerrada por SKU):**

La señal usa el tri-estado de §4 (positivo / cero con evidencia / ausente) y **no** colapsa
ausencia a cero. Los negativos ya están bloqueados antes de llegar aquí (§4). La señal se calcula
sobre los buckets físicos **solicitados** (los presentes en `sedes`).

- Si `baja_rotacion` es **cero o ausente** → `"not_required"` (no aporta existencia).
- Si `baja_rotacion` es **positivo**:
  - algún bucket físico solicitado es **positivo** → `"not_required"` (existencia física demostrada
    en al menos una sede, independiente de `B.ROT`);
  - todos los buckets físicos solicitados están en **cero con evidencia** → `"required"` (la
    existencia de las sedes solicitadas podría depender **solo** de `B.ROT`; se exige confirmación
    humana del origen físico);
  - en otro caso (algún bucket físico solicitado está **ausente**) → `"unknown"`.

Con ambas sedes solicitadas (tabla de referencia):

| `baja_rotacion` | `sedes.neiva` | `sedes.florencia` | Señal |
|-----------------|---------------|-------------------|-------|
| cero o ausente | (cualquiera) | (cualquiera) | `"not_required"` |
| positivo | positivo | (cualquiera) | `"not_required"` |
| positivo | (cualquiera) | positivo | `"not_required"` |
| positivo | cero | cero | `"required"` |
| positivo | ausente | (cualquiera) | `"unknown"` |
| positivo | (cualquiera) | ausente | `"unknown"` |

- `"required"`: solo `B.ROT` positivo y los buckets físicos solicitados demostrados en cero; se
  exige confirmación humana del origen físico.
- `"not_required"`: demostrable que no hace falta confirmación (`B.ROT` no positivo, o alguna sede
  solicitada positiva).
- `"unknown"`: no se puede determinar (falta dato de fila en un bucket físico solicitado).

La señal **no** afirma disponibilidad física por `B.ROT`; solo indica si falta confirmación humana
del origen físico. La incertidumbre **nunca** se colapsa a `"not_required"` ni a `"required"` cuando
falta dato.

**Pendiente (no decidido, informativo, no bloqueante):** solapamiento exacto `B.ROT` ↔ bodegas
físicas y origen físico de `B.ROT`: **POR CONFIRMAR POR FREDY** (§15). No bloquea el cierre del
contrato; las cantidades permanecen separadas y nunca se totalizan.

---

## 9. Representación decimal exacta + validación del servidor (gate)

### 9.1 Hechos demostrados vs. pendientes de esquema

**Hechos demostrados (evidencia de esquema portable, §16):**

- `InvDetalleExistencias.AlmacenID` es `int NOT NULL` (evidencia de esquema).
- `InvDetalleExistencias.SaldoActual` es `decimal NULL` (evidencia de esquema).
- `InvDetalleExistencias.Ano` es `numeric NOT NULL` (evidencia de esquema).
- La **precisión/escala exacta** de `SaldoActual` (y de las demás columnas `decimal`/`numeric`) y el
  **tipo concreto que devuelve el driver Python** **no** están demostrados (la evidencia de esquema
  no reporta precisión/escala ni prueba el tipo del driver).
- El SSOT web aplica `CAST(... AS DECIMAL(18, 4))` sobre `SaldoActual` y filtra
  `CAST(...) >= 0` (visible en `j3system_website_stock.py`). `catalog.stock` **no** hereda ese cast
  ni ese filtro.
- El protocolo local `_quote_search_j3` (`builtins.py`) convierte explícitamente
  `float(raw_qty)`. `catalog.stock` **no** hereda esa conversión.

**Pendientes de esquema (no demostrados; no afirmar que lo están):**

- El tipo concreto que devuelve el driver para una columna `DECIMAL` (`Decimal` vía pymssql
  `as_dict`, o `float`, o `str`, etc.) **no** está demostrado en el worktree.
- La **escala nativa** de `SaldoActual` **no** está demostrada. No afirmar que la escala de salida
  "preserva la escala nativa".

**Consecuencia (gate):** hasta que el origen (tipo y valor) de una cifra esté **validado**, la
herramienta **no** emite ninguna cifra: bloquea el SKU con `reason: "validacion_fallida"`.

### 9.2 Canonicalización (requisito de implementación)

- El handler entrega, **antes** del registry/JSON layer, una **string decimal canónica**. **No** se
  confía en el encoder por defecto de FastAPI/Pydantic para `Decimal`.
- Tipos aceptados: **`Decimal` finito** (el valor leído del bucket sin pasar por `float`/`round`/
  cast/clamp) y **`int` no booleano** (valor entero exacto de base-10). Se **rechazan** `float`,
  `str`, `bool` (subclase de `int` en Python), `NaN` y los infinitos: en ese caso se bloquea con
  `validacion_fallida` hasta demostrar el origen. No se afirma qué tipo devuelve el driver para
  `decimal`/`money`; esta regla define qué acepta el handler, no qué produce el driver.
- Regla de canonicalización (solo para un `Decimal` finito, o un `int` no booleano):
  - Se serializa con **`format(d, "f")`** (punto fijo, **sin** exponente). Se **rechaza** cualquier
    representación que contenga un marcador de exponente (`e`/`E`): bloquea, no se emite.
  - Se canonicaliza el **cero negativo** (`"-0"`, `"-0.00"`…) a `"0"` (sin signo).
  - La cadena resultante debe cumplir `^\d+(\.\d+)?$` (no negativa; §4 bloquea los negativos antes
    de emitir).
- **No** se usa `Decimal(str(float))` ni ningún `float`/cast/redondeo/clamp para producir la cifra.

### 9.3 Validación por el servidor (qué cifra se valida exactamente)

Antes de presentar una cifra, el servidor **debe** verificar, para **cada** cifra emitida, que:

1. **Corresponde al bucket probado:** la cifra de `sedes.neiva` proviene solo de
   `ALM`/`BD6`/`SUR`/`DIS`/`BOD`; `sedes.florencia` solo de `FLO`; `baja_rotacion` solo de `B.ROT`.
   Sin cruces.
2. **Corresponde al valor `Decimal` exacto:** el string canónico reparsea a un `Decimal`
   numéricamente igual al valor agregado para ese bucket. (Esto es **correspondencia**, no prueba de
   origen.)
3. **No se alteró ni creó valor:** ninguna operación `float`, `round`, cast, clamp o `>= 0`
   intervino. La validación **no** altera ni inventa la cifra; solo la verifica.

Esta capacidad **no** está demostrada que exista en el worktree (§9.1). Es un **gate**: si el
runtime no puede validar el contenido numérico final de una cifra, **no** se autoriza esa cifra al
consumidor y se responde `bloqueado`/`validacion_fallida`. No se declara que la validación "ya
existe".

---

## 10. Fuente de stock (builder nuevo; no reutilizar el existente)

Reutilizar la **topología** de la fuente J3 (mismas tablas), pero **no** el builder existente:

- **Tabla base `AdmArticulos`** con `LEFT JOIN` hacia la cadena de inventario
  (`InvExistencias`, `InvDetalleExistencias`) y almacén (`AdmAlmacen`), de modo que una fila de
  inventario ausente **no** pueda desaparecer por un `INNER JOIN`. El SELECT devuelve la clave del
  lado detalle `d.AlmacenID` como **marcador de existencia de fila** (no nulo = fila real;
  `InvDetalleExistencias.AlmacenID` es `int NOT NULL`, §16). `d.AlmacenID` `NULL` = ausencia de
  fila → `inventario_desconocido` **solo** cuando el SKU normalizado corresponde a un **solo**
  `ArticulosID` (§4, §5.2), nunca `"0"`; `d.AlmacenID` no nulo = fila real que se clasifica (§4,
  §6).
- Saldo: `InvDetalleExistencias.SaldoActual` **crudo**, sin cast ni filtro de signo, leído **por
  `AlmacenCodigo`** para clasificar en buckets (§4).
- **Último período por par:** `ROW_NUMBER() OVER (PARTITION BY ArticulosID, AlmacenID ORDER BY Ano
  DESC) = 1` (no `MAX(Ano)` global, §4, §11), más el marcador de multiplicidad `num_filas_ano` para
  detectar empates en el período máximo (§4).
- El SELECT devuelve **`ArticulosID`**; no se asume que `AdmArticulos.ArticulosCodigo` sea único.
  Si un SKU normalizado corresponde a más de un `ArticulosID`, ese SKU se bloquea (§5.2). Antes de
  unir la cadena de inventario, la consulta **deduplica** los pares `(SKU normalizado, ArticulosID)`
  distintos (mismo SKU normalizado y mismo `ArticulosID` colapsados a una fila), de modo que filas
  de catálogo duplicadas para el mismo artículo **no** multiplican el saldo de detalle. La
  integridad cuenta `ArticulosID` **distintos** por SKU normalizado; `ArticulosID` distintos siguen
  bloqueando.

**Por qué un builder nuevo (evidencia local, §16):** el builder existente
`build_website_stock_by_sku_sql` **interpola** los SKUs (no usa bind params), usa `INNER JOIN` y
filtra `AlmacenCodigo IS NOT NULL AND <> ''` en el `WHERE`, aplica `CAST(... AS DECIMAL(18, 4))`,
filtra `CAST(...) >= 0` y un `HAVING ... > 0`. Ninguno de esos comportamientos es admisible en
`catalog.stock`:

1. `AdmArticulos` como base con `LEFT JOIN`; **no** filtrar códigos nulos/en blanco en el SQL
   (clasificarlos en el handler).
2. Obtener el saldo **por `AlmacenCodigo`** (no solo el total allowlist).
3. **Leer `SaldoActual` sin cast** y **sin** filtro `>= 0` ni `HAVING` (los negativos deben ser
   visibles para bloquearse, §4).
4. **No agregar en SQL**; devolver la fila más reciente por (artículo, almacén) y agregar en Python
   con `Decimal` (§4).
5. Excluir `CON` y la denylist tras normalizar trim+uppercase (§6).
6. Mapear `ALM`/`BD6`/`SUR`/`DIS`/`BOD` → `neiva`; `FLO` → `florencia` (§7); `B.ROT` → línea
   `baja_rotacion` (§8); código desconocido/nulo/blanco → `codigo_no_clasificado` (§6).
7. SKUs pasados como **parámetros bind** (nunca interpolación desde entrada de usuario).

Solo se reutiliza un helper (p. ej. `sql_in_list`) para valores **fijos de policy** (códigos de
bodega, constantes no derivadas de entrada), y únicamente si la evidencia local demuestra que es
seguro para ese uso. Nunca para los SKUs de entrada.

---

## 11. SQL (solo lectura, parametrizado, timeout, límite verificable)

- **Solo lectura:** `SELECT` únicamente. Sin `INSERT`/`UPDATE`/`DELETE`/`MERGE`.
- **Parametrizado:** cada SKU de entrada se pasa como **parámetro bind** (nunca interpolación de
  strings desde entrada del usuario). Los códigos de bodega provienen de la policy fija, no de
  entrada de usuario.
- **Comparación case/collation-safe:** para el alfabeto ASCII permitido (`[A-Z0-9._-]`), el SQL
  normaliza la columna con `UPPER(LTRIM(RTRIM(AdmArticulos.ArticulosCodigo)))` y la compara contra
  el valor bind ya normalizado (trim+uppercase, §2), de modo que la coincidencia no dependa de la
  collation de la columna. Si el resultado devuelve una fila cuyo SKU normalizado no está entre los
  solicitados (SKU inesperado), → `error_consulta` (§5.1).
- **Base + LEFT JOIN:** `AdmArticulos` como tabla base; `LEFT JOIN` a la cadena de inventario y a
  almacén (§10). **No** se filtran códigos nulos/en blanco en el SQL.
- **Deduplicación del mapeo SKU→artículo antes del JOIN de inventario:** la consulta construye
  primero el conjunto **distinto** de pares `(SKU normalizado, ArticulosID)` — usando
  `DISTINCT`/`GROUP BY` sobre `(UPPER(LTRIM(RTRIM(AdmArticulos.ArticulosCodigo))), ArticulosID)` —
  y **luego** hace el `LEFT JOIN` a la cadena de inventario sobre ese conjunto. Así, filas de
  catálogo duplicadas para el mismo SKU normalizado y el mismo `ArticulosID` no multiplican el
  saldo de detalle. La integridad cuenta `ArticulosID` **distintos** por SKU normalizado (§5.2).
- **Último período por par:** `ROW_NUMBER() OVER (PARTITION BY ArticulosID, AlmacenID ORDER BY Ano
  DESC) = 1` para quedarse con una fila por (artículo, almacén). **No** `MAX(Ano)` global. `Ano` es
  numérico; no se afirma que sea año calendario ni stock en tiempo real (es el período registrado
  más reciente). Se devuelve `num_filas_ano` para detectar empates (§4). El filtro `rn = 1` se
  aplica en un CTE/tabla derivada (no en `WHERE` directo) y **no** debe descartar las filas `NULL`
  del `LEFT JOIN`.
- **Timeout y reintentos (camino propio obligatorio):** la implementación usa un **camino dedicado
  acotado** (o anula explícitamente vía opt-in) con timeout de conexión/consulta **explícito ≤ 10
  s**, **cero reintentos** y **sin logging del texto crudo del error** (mensaje fijo §5). El
  `Database.execute_query` compartido reintenta por defecto (`DB_QUERY_RETRIES`, default 2); la
  implementación **no** puede heredar esos reintentos en silencio. Timeout → `error_consulta`.
- **Límite verificable (sin truncado silencioso):** **no** se afirma un tope de una fila por
  (SKU, `AlmacenCodigo`) — un SKU puede corresponder a varios `ArticulosID` y `AlmacenCodigo` no es
  único. Se fija un **techo global de recursos** explícito e independiente `MAX_RESULT_ROWS = 1000`
  y un **centinela** (`TOP (1001)` en T-SQL) para detectar desbordamiento **patológico**: solo
  superar `MAX_RESULT_ROWS` filas causa `error_consulta` global sin cifras. **No** se usa
  `TOP`/`LIMIT` para truncar cantidades ni para imponer el tope de integridad por SKU. **T-SQL no
  usa `LIMIT`**; solo `TOP`. Dentro del techo, un código desconocido/nulo/blanco se clasifica por
  SKU como `codigo_no_clasificado` (§6), **no** como condición de centinela/desbordamiento global;
  nunca se filtra en el SQL.
- **Datos sintéticos/fake-only en tests:** nunca datos reales de producción.

---

## 12. Seguridad / privacidad

- **Ningún** teléfono, PII, ni dato de contacto en salida ni en logs.
- **Ningún** precio/costo en salida ni en logs.
- Cantidades exactas **sí** se emiten (decisión vigente), pero **solo** si pasan la validación exacta
  de §9; nunca cifras inventadas, redondeadas ni negativas (negativos → `bloqueado`, §4).
- Sin credenciales hardcodeadas; solo `require_env()` / `os.getenv()`.
- Sin credenciales ni valores de contacto reproducidos en este contrato.
- Mensajes de error fijos (§5); **nunca** texto del driver/SQL/credenciales en salida ni en logs.

---

## 13. Handler (contrato de comportamiento)

1. **Validación de entrada primero:** validar esquema cerrado y rechazar claves extra (§2) **antes**
   de abrir cualquier conexión a base de datos. Violación → `entrada_invalida`, sin tocar DB.
2. **Errores de driver con mensaje fijo:** cualquier excepción del driver/DB se captura y se traduce
   a `error_consulta` con `message` fijo; **nunca** se propaga el texto del driver/exception/SQL.
3. **Resultado no `list`, fila sin claves, SKU inesperado, resultado inválido** → `error_consulta`,
   nunca `[]`/cero (§5.1).
4. **Clasificar en handler, no en SQL:** códigos nulos/en blanco/desconocidos se clasifican en el
   handler y bloquean con `codigo_no_clasificado`; nunca se descartan en silencio (§4, §6).
5. **Revisión de negativos antes de agregar:** por código incluido, antes de sumar (§4); agregación
   posterior solo con `Decimal` en Python.
6. **Integridad SKU→artículo (conteo de `ArticulosID` distintos):** el handler cuenta los
   `ArticulosID` **distintos** por SKU normalizado sobre el conjunto deduplicado (§10, §11). Más de
   uno → `bloqueado`/`validacion_fallida`, evaluado **antes** de `inventario_desconocido` (§5.2
   precedencia).
7. **Convención de respuesta:** este contrato usa el envoltorio `{ok, error}` (fail-closed), que
   **difiere** de la convención `{status, reason}` de algunos tools locales (`builtins.py`). Se
   **justifica** la diferencia: un fallo de consulta no debe poder confundirse con un resultado
   vacío (`status: "empty"`), y `{ok: false}` + `error.type` fijo es más seguro para fail-closed. La
   decisión de adoptar o no esta convención es parte del contrato, no de la implementación.

### 13.1 Matriz mínima de tests (fake-only)

Todos los tests usan **datos sintéticos/fake**, nunca DB real ni credenciales.

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 1 | `skus` vacío / >5 / caracteres inválidos / clave extra / tipo inesperado. | `entrada_invalida` (global). |
| 2 | `sede: "neiva"`, `sede: "florencia"` y `sede` ausente. | `ok` (todos válidos); `sede` resuelta `"neiva"`/`"florencia"`/`"ambas"`. |
| 3 | `sede: "neiva"`, SKU en catálogo, fila `ALM` positiva. | `ok`, `status: "ok"`, `sedes.neiva` = string decimal. |
| 4 | `sede: "florencia"`, SKU en catálogo, fila `FLO` positiva. | `ok`, `status: "ok"`, `sedes.florencia` = string decimal. |
| 5 | `sede` ausente, filas `ALM` y `FLO` positivas. | `ok`, `sedes` = `{ "neiva": …, "florencia": … }`, `sede` = `"ambas"`. |
| 6 | SKU en catálogo, sin fila para un bucket. | bucket ausente = `null` (**no** `"0"`). |
| 7 | SKU en catálogo, fila con suma `Decimal = 0` para un bucket. | bucket = `"0"` (cero con evidencia). |
| 8 | SKU en catálogo, sin filas de inventario (LEFT JOIN sin filas). | `status: "inventario_desconocido"` (no `"0"`). |
| 9 | SKU no en `AdmArticulos`. | `status: "no_encontrado"` (sin cifras, no cero). |
| 10 | Fila más reciente con saldo negativo en `neiva` (`ALM`), `florencia` (`FLO`) o `B.ROT`. | `status: "bloqueado"`, `reason: "saldo_negativo"`, sin números. |
| 11 | Cancelación: `ALM = +3` y `BD6 = -3` en el mismo bucket `neiva`. | `status: "bloqueado"`, `reason: "saldo_negativo"` (se inspecciona antes de agregar). |
| 12 | Negativo solo en un código excluido (`CON` o denylist). | excluido/ignorado; el SKU **no** se bloquea por ese negativo. |
| 13 | Código de bodega desconocido/nulo/blanco. | `status: "bloqueado"`, `reason: "codigo_no_clasificado"` (no se descarta en silencio). |
| 14 | Saldo `NULL` en una fila más reciente incluida. | `status: "bloqueado"`, `reason: "validacion_fallida"` (no coalesce a cero). |
| 15 | Varios `Ano` por (artículo, almacén): se selecciona la fila más reciente por par. | `ROW_NUMBER() … ORDER BY Ano DESC = 1`; no `MAX(Ano)` global. |
| 16 | Año más nuevo con datos parciales (solo algunos almacenes). | buckets con fila = valor; buckets sin fila = `null` (ausente), no `"0"`. |
| 17 | `CON` y denylist (`CEN`,`EXH`,`EXD`,`BDT`,`MDL`,`TRA`) presentes. | excluidas de los buckets (no suman). |
| 18 | `B.ROT` presente y positivo; buckets físicos solicitados en cero/ausente/positivo. | `baja_rotacion` en línea aparte; señal §8 (`required`/`not_required`/`unknown`). |
| 19 | Driver lanza excepción / `rows` no es `list` / fila sin claves / SKU inesperado / centinela alcanzado. | `error_consulta` (global), mensaje fijo, sin cifras. |
| 20 | Valor llega como `float`/`str` (origen no `Decimal` demostrado) o no pasa §9. | `status: "bloqueado"`, `reason: "validacion_fallida"`. |
| 21 | Mezcla de SKUs: uno `ok`, uno `no_encontrado`, uno `bloqueado`. | `results` con un elemento por SKU, sin mezclar cifras ambiguas. |
| 22 | Canonicalización: `format(d, "f")` sin exponente; cero negativo → `"0"`; regex `^\d+(\.\d+)?$`. | string decimal canónico no negativo. |
| 23 | Dos filas con el mismo `Ano` máximo (empate) y una fila de `Ano` menor, mismo par. | `ROW_NUMBER()` elige el período máximo; `num_filas_ano > 1` bloquea ese SKU con `validacion_fallida`, sin cifras. |
| 24 | SKU en catálogo, **sin fila de detalle** (marcador `d.AlmacenID` `NULL`). | `status: "inventario_desconocido"`. |
| 25 | SKU en catálogo, **fila real** (`d.AlmacenID` no nulo) con `AlmacenCodigo` `NULL`/blanco/sin coincidencia. | `status: "bloqueado"`, `reason: "codigo_no_clasificado"` (no se colapsa a `inventario_desconocido`). |
| 26 | Solo filas en códigos excluidos (`CON`/denylist), sin bloqueos. | `status: "ok"`; `sedes.neiva`/`sedes.florencia`/`baja_rotacion` = `null`; `baja_rotacion_confirmation` = `"not_required"`. |
| 27 | Un SKU normalizado corresponde a dos `ArticulosID` distintos. | `status: "bloqueado"`, `reason: "validacion_fallida"` (no se mezclan saldos). |
| 28 | 71 filas de detalle incluyendo un código desconocido (dentro de `MAX_RESULT_ROWS`). | el código desconocido bloquea **solo ese SKU** (`codigo_no_clasificado`); no hay `error_consulta` global. |
| 29 | Consulta que supera `MAX_RESULT_ROWS` (1001 filas). | `error_consulta` global, sin salida parcial. |
| 30 | Varias condiciones de bloqueo a la vez en un SKU (negativo + código desconocido + `NULL`). | una sola `reason`, según la precedencia determinista de §5.2. |
| 31 | SKUs con espacios en blanco alrededor y variantes de caja (`" abc "`, `"ABC"`, `"abc"`). | se normalizan (trim+uppercase) y resuelven igual; sin `entrada_invalida`. |
| 32 | Duplicados normalizados (`"abc"` y `"ABC"`). | `entrada_invalida` (global). |
| 33 | Collation de columna case-sensitive simulada. | comparación `UPPER(LTRIM(RTRIM(...)))` vs bind normalizado es case/collation-safe; SKU inesperado → `error_consulta`. |
| 34 | Mensaje fijo de `entrada_invalida`. | `message` = `"entrada inválida para catalog.stock"` (catálogo fijo §5.1). |
| 35 | Valor de saldo `Decimal` finito / `int` no booleano vs `float`/`str`/`bool`/`NaN`/infinito. | finito/`int` se aceptan (canonicalizan); el resto → `validacion_fallida`. |
| 36 | Un SKU normalizado corresponde a dos `ArticulosID` distintos y **ninguno** tiene fila de detalle real. | `status: "bloqueado"`, `reason: "validacion_fallida"` (sin cifras), **no** `inventario_desconocido` (la integridad SKU→artículo precede a la ausencia de fila, §5.2). |
| 37 | Filas de catálogo duplicadas para el mismo SKU normalizado y el **mismo** `ArticulosID`, con una fila de inventario de saldo positivo. | El par `(SKU normalizado, ArticulosID)` se deduplica antes del JOIN (§10, §11); el saldo **no** se duplica y el bucket emite el valor único. `ArticulosID` **distintos** no se deduplican: siguen bloqueando (§5.2). |

---

## 14. Límites de implementación

- **≤ 300 líneas de lógica** por herramienta (`catalog.stock`).
- **`builtins.py` solo con registro mínimo** del `ToolSpec` (nombre, descripción, scope,
  `parameters_schema`, handler); **sin lógica nueva** en `builtins.py`.
- La lógica vive en un módulo dedicado (p. ej. bajo `modules/catalog`), no en `builtins.py`.
- Tests futuros **fake-only** (nunca DB real ni credenciales).

### 14.5 Audiencia / scope (alineado con B2)

- `catalog.stock` se registra bajo **`ToolScope.SALES_PORTFOLIO`** (como el
  `catalog.quote_for_customer` de B2), usable por **`SALES`** y **`ADMIN`**, con
  **`public_safe=False`**. No es descubrible ni usable por `PUBLIC`/`CUSTOMER`/etc.
- No se declara ni registra `PUBLIC_STOCK` / `public_safe=True` para estas cifras. El enum
  `ToolScope.PUBLIC_STOCK` **existe** en `depotru_kernel/auth.py` (hecho), pero **no** se usa para
  `catalog.stock`.
- Redacción neutra: es **dato de herramienta de disponibilidad exacta para un flujo de venta
  autorizado**; un resultado de herramienta **no** es por sí mismo permiso para enviar un mensaje
  no validado a un cliente. No hay gate de audiencia pendiente.

---

## 15. Por confirmar por Fredy (resumen — solo pendientes no bloqueantes)

1. **Propuesta informativa de umbral "pocas unidades"** (sugerencia: **5 unidades por sede
   física**). **NO aprobada / NO activa**; no se aplica en este contrato. La salida primaria sigue
   siendo la cantidad exacta (§4).
2. **Solapamiento y origen físico de `B.ROT`** (§8). Informativo y no bloqueante; las cantidades
   permanecen separadas.

> Resuelto respecto al borrador anterior: mapeo de bodegas a sede (confirmado por Fredy 22 oct
> 2026, §7); semántica de saldos negativos (revisión por código antes de agregar, §4); audiencia /
> scope (alineado con B2, §14.5); elección del año de inventario (última fila por par, §4/§11);
> bodega de despacho (fuera de alcance de este contrato de disponibilidad). El umbral numérico de
> "pocas unidades" **no** está aprobado.

---

## 16. Evidencia local

| Evidencia | Archivo | Confirma |
|-----------|---------|----------|
| Mapeo de bodegas confirmado por Fredy (22 oct 2026): `FLO = Florencia`; `ALM`, `SUR`, `BD6`, `DIS`, `BOD` = Neiva. | Instrucción de Fredy (22 oct 2026) | §7; coincide con el `SITES` del contrato B2 (`neiva: (ALM, BD6, SUR, DIS, BOD)`, `florencia: (FLO,)`). |
| Evidencia de esquema J3 (solo metadatos): `InvDetalleExistencias.AlmacenID` = `int NOT NULL`, `SaldoActual` = `decimal NULL`, `Ano` = `numeric NOT NULL`; sin precisión/escala ni tipo del driver. | `docs/reference/j3-inventory-schema-evidence.md` | §4, §9.1, §10, §11; marcador de fila, tipos de columna y límite de evidencia. |
| `WAREHOUSE_CODE_TO_NAME` incluye `FLO = "ALMACEN FLORENCIA (Sika Center)"`, `CON = "CONTABILIDAD"`, `B.ROT = "PRODUCTOS DE BAJA ROTACION"`, y nombres de bodega para `ALM`/`SUR`/`BD6`/`DIS`/`BOD`. | `src/business_analyzer/core/j3system_sales_warehouse.py` | Nombres de códigos; el mapeo a sede proviene de la instrucción de Fredy (no solo del archivo). |
| Denylist web (`CEN`, `EXH`, `EXD`, `BDT`, `MDL`, `TRA`) y allowlist web (incluye `CON` y `B.ROT`). | `src/business_analyzer/core/website_warehouse_policy.py` | Política web ≠ política comercial. |
| `build_website_stock_by_sku_sql` interpola SKUs (no bind), usa `INNER JOIN` y filtra `AlmacenCodigo IS NOT NULL AND <> ''`, aplica `CAST(... AS DECIMAL(18, 4))`, filtro `CAST(...) >= 0` y `HAVING ... > 0`. | `src/business_analyzer/core/j3system_website_stock.py` | Requiere builder nuevo (§10); cast/filtro/joins **no** se heredan. |
| Conversión explícita `float(raw_qty)` en `_quote_search_j3`. | `src/depotru_tools/builtins.py` | El protocolo local actual usa `float`; justifica el gate §9. |
| Enum `ToolScope.PUBLIC_STOCK` y `public_safe` existen en el `ToolSpec`; `ToolScope.SALES_PORTFOLIO` (B2) para `catalog.stock`. | `src/depotru_kernel/auth.py`, `src/depotru_tools/registry.py` | El scope correcto para `catalog.stock` es `SALES_PORTFOLIO`, no `PUBLIC_STOCK` (§14.5). |
| La API monta `ToolCallResponse` con `result: Any` vía Pydantic/`response_model`. | `src/apps/api/v1.py`, `src/api.py` | No hay un encoder `Decimal`→string custom demostrado; el default no se asume (§9.1). |

**No afirmado / no encontrado en el worktree:**

- No se halló un encoder JSON custom ni emisión de string para `Decimal` (el camino de
  serialización local no está demostrado como exacto).
- No se halló `jsonable_encoder` en `src/apps/api/v1.py` ni `src/api.py` (afirmación retirada del
  borrador anterior).
- La precisión/escala exacta de `SaldoActual` y el tipo concreto del driver Python para columnas
  `DECIMAL` **no** están demostrados (pendientes de esquema, §9.1).
- El mapeo a sede proviene de la **instrucción de Fredy (22 oct 2026)** y coincide con el `SITES`
  del contrato B2; no se depende de un archivo `docs/CRM` local para validar §6–§8.
