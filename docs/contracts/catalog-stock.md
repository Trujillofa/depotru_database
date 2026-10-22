# Contrato — `catalog.stock` (disponibilidad por SKU/sede)

> **Estado:** BORRADOR — fase contractual. Requiere revisión del coordinador antes de la implementación.
> **Rama:** `feat/bff-b1-stock` — base `9698f4193b96b71dae500100a69a9882f726991f`.
> **Alcance:** define únicamente el contrato de entrada/salida/errores de `catalog.stock`.
> No modifica implementación, tests ni `builtins.py`. No se ejecutan pruebas en esta fase.
>
> **Supersede el borrador anterior:** la decisión vigente de Fredy permite cifras exactas de
> existencia como **dato de herramienta**. Se eliminan los estados gruesos (`hay` /
> `pocas_unidades` / `no_hay`) y el umbral propuesto `5`; se sustituyen por cantidades exactas en
> base-10, sin `float`, sin redondeo y sin umbrales. El valor `5` **no** está aprobado y no aparece
> en este contrato.
>
> **Nota de alcance (pendiente):** la decisión de que las cifras son "dato de herramienta" **no**
> define por sí sola una audiencia pública. La audiencia/scope de exposición está
> **PENDIENTE POR FREDY** (§14.5); hasta resolverlo, `catalog.stock` no se registra ni se expone
> públicamente (§13).

---

## 1. Propósito

Responder, por SKU y sede, con **cantidades exactas de existencia** (base-10, sin redondeo ni
umbral), separando de forma determinista:

- la cantidad física de la sede **confirmada** (`FLO → florencia`, única con evidencia local);
- la cantidad física **no mapeada** a sede (códigos físicos reconocidos sin confirmación de Fredy);
- la bodega virtual `B.ROT`, en línea aparte y **nunca** sumada ni atribuida a una sede.

Es una herramienta de disponibilidad orientada a cliente/vendedor. **No** expone precios ni costos.
Toda cifra emitida debe haber sido **validada por el servidor** (ver §9) antes de poder presentarse.
La herramienta responde **fail-closed**: ante cualquier ambigüedad, bloquea la cifra y **no afirma
nada** sobre existencia.

---

## 2. Entrada (cerrada)

```json
{
  "skus": ["<sku1>", "<sku2>"],   // obligatorio, 1..5 elementos
  "sede": "florencia"             // opcional: "neiva" | "florencia"
}
```

| Campo | Tipo | Regla |
|-------|------|-------|
| `skus` | `string[]` | Obligatorio. 1 a 5 códigos. Cada SKU: no vacío, ≤ 40 caracteres, solo `[A-Za-z0-9._-]`. |
| `sede` | `string \| null` | Opcional. Valores válidos: `"neiva"`, `"florencia"`. `null`/ausente → ambas sedes. |

**Normalización (aplicada antes de cualquier filtro o consulta):**

- Códigos de SKU y de bodega se normalizan con **trim + uppercase** antes de comparar con el
  catálogo, la denylist y el mapeo de sede. `sede` se normaliza con trim + lowercase.
- La normalización **solo** es para clasificar/filtrar; **no** crea ni altera un valor de cantidad.

**Esquema cerrado:** solo se admiten las claves `skus` y `sede`. Cualquier clave extra, tipo
inesperado, o `skus`/`sede` con forma distinta a la declarada → `entrada_invalida` (§5). Esta
validación ocurre **antes** de abrir cualquier conexión a base de datos (fail-closed).

**Violaciones de entrada** → error global `entrada_invalida` (fail-closed, ver §5).

**Consecuencia de mapeo:** como solo `FLO → florencia` tiene evidencia local (§7), el único caso
exitoso es `sede: "florencia"`. `sede: "neiva"` o `sede` ausente (ambas sedes) →
`warehouse_mapping_unconfirmed` (error global, §5). No se devuelve ningún éxito parcial que
implique a `neiva`.

---

## 3. Salida (cerrada)

Hay **dos** envoltorios mutuamente excluyentes:

### 3.1 Éxito global (`ok: true`) — solo con `sede: "florencia"`

```json
{
  "ok": true,
  "sede": "florencia",
  "results": [
    {
      "sku": "ABC123",
      "status": "ok",
      "sedes": { "florencia": "12.34" },
      "no_mapeado": "5",
      "baja_rotacion": null,
      "baja_rotacion_confirmation": "not_required"
    },
    {
      "sku": "DEF456",
      "status": "ok",
      "sedes": { "florencia": "0" },
      "no_mapeado": "0",
      "baja_rotacion": "7.50",
      "baja_rotacion_confirmation": "required"
    },
    { "sku": "GHI789", "status": "no_encontrado" },
    { "sku": "JKL012", "status": "inventario_desconocido" },
    { "sku": "MNO345", "status": "bloqueado", "reason": "saldo_negativo" }
  ]
}
```

`results` tiene **exactamente un elemento por SKU solicitado**, en el mismo orden de `skus`. Cada
elemento lleva un `status` por SKU que **nunca mezcla** un SKU fallido con cifras ambiguas.

| `status` | Significado | Campos presentes |
|----------|-------------|------------------|
| `"ok"` | SKU en catálogo y con inventario consultable; cifras emitidas. | `sedes`, `no_mapeado`, `baja_rotacion`, `baja_rotacion_confirmation` |
| `"no_encontrado"` | El SKU no existe en `AdmArticulos`. | solo `sku`, `status` |
| `"inventario_desconocido"` | El SKU existe pero **no hay dato de inventario consultable**. | solo `sku`, `status` |
| `"bloqueado"` | Cifras bloqueadas (negativo, código no clasificado, o validación §9 no satisfecha). | `sku`, `status`, `reason` (string fija) |

`reason` de `bloqueado` es una cadena **fija** de un catálogo cerrado (§5): `"saldo_negativo"`,
`"codigo_no_clasificado"`, `"validacion_fallida"`. Nunca texto del driver/SQL/credencial.

**Para un elemento `"ok"`:**

| Campo | Tipo | Regla |
|-------|------|-------|
| `sedes.<sede>` | `string (decimal) \| null` | Cantidad física de la sede **confirmada** (hoy solo `florencia`, §7). `null` = **sin fila** para ese bucket (desconocido); string decimal = valor con evidencia de fila. Ver tri-estado §4. |
| `no_mapeado` | `string (decimal) \| null` | Cantidad física de bodegas físicas **reconocidas y no mapeadas** (`ALM`, `SUR`, `BD6`, `DIS`, `BOD`, §7). **Nunca** se atribuye a `neiva` ni a `florencia`. `null` = sin fila. |
| `baja_rotacion` | `string (decimal) \| null` | Cantidad de la bodega virtual `B.ROT`, en línea **aparte**. `null` = sin fila. |
| `baja_rotacion_confirmation` | `string (enum)` | `"required"` \| `"not_required"` \| `"unknown"` (§8). |

### 3.2 Error global (`ok: false`)

```json
{
  "ok": false,
  "error": { "type": "error_consulta", "message": "error consultando inventario J3" }
}
```

No hay `results` ni **ninguna** cifra cuando la respuesta es `ok: false`.

**Invariantes de salida (no negociables):**

- Toda cantidad emitida es **string decimal canónico base-10** (`^-?\d+(\.\d+)?$`), nunca un número
  JSON (evita `float`/IEEE-754). Ver §9.
- `null` significa **desconocido** (sin fila); **nunca** se traduce a `"0"`. Un `"0"` solo se emite
  cuando hay **evidencia de fila** para ese bucket (§4).
- Nunca se devuelve precio ni costo (`ArticulosVenta`, `VentaMasIva`, etc.).
- `baja_rotacion` **nunca** se suma a `neiva` ni a `florencia`; permanece en su línea aparte.
- `no_mapeado` **nunca** se presenta como saldo de `neiva`.
- Un fallo de ERP **no** produce una cifra ni un "cero"; produce `error_consulta` (§5).

---

## 4. Semántica de cantidades (exactas, sin umbral, tri-estado por bucket)

Cada cantidad es el **saldo exacto en base-10** de `InvDetalleExistencias.SaldoActual`, agregado
(`SUM`) por bucket de bodega, **sin** redondeo, **sin** umbral y **sin** clamp a cero. No existe
umbral de "pocas unidades" ni clasificación por cantidad.

**Tri-estado por bucket (determinista, sin colapsar ausencia a cero):**

| Estado | Condición | Emisión |
|--------|-----------|---------|
| **positivo** | El bucket tiene ≥1 fila y `SUM(SaldoActual) > 0`. | String decimal exacto (p. ej. `"12.34"`). |
| **cero con evidencia** | El bucket tiene ≥1 fila y `SUM(SaldoActual) = 0`. | `"0"` (hay evidencia de fila: el SKU sí tiene dato en ese bucket y no aporta saldo). |
| **ausente** | El bucket **no tiene fila** (no aparece en el `GROUP BY`). | `null` (desconocido). **Nunca** `"0"`. |

Un bucket sin fila es **desconocido**, no cero. Cero solo se emite con evidencia directa de fila
para ese bucket.

**Negativos — PENDIENTE POR FREDY (no autorizados):**

- La semántica comercial de un saldo/total negativo **no** está decidida. Marca: **PENDIENTE POR FREDY**.
- Hasta decisión explícita de Fredy, **cualquier** saldo/total negativo detectado en un SKU
  **bloquea** las cifras de ese SKU: `status: "bloqueado"`, `reason: "saldo_negativo"`, **sin
  ningún número**. No se emite `"-2.00"` ni se le da significado comercial.
- El SQL **no** debe filtrar los negativos (no `>= 0`, no `HAVING > 0`): los negativos deben ser
  **visibles** para poder bloquearlos, no silenciados.

Los buckets se computan de forma determinista (§7, §8):

| Bucket | Códigos de bodega (normalizados) |
|--------|----------------------------------|
| `sedes.florencia` | `FLO` (único confirmado). |
| `baja_rotacion` | `B.ROT` (virtual). |
| `no_mapeado` | Solo códigos físicos **reconocidos con evidencia**: `ALM`, `SUR`, `BD6`, `DIS`, `BOD`. |

`CON` (§6.1) y la denylist (§6.2) quedan **excluidas** de los tres buckets. Cualquier código
**desconocido, nulo, blanco o nuevo** (no presente en el set conocido) **no** se agrega
silenciosamente a `no_mapeado`: bloquea el SKU con `reason: "codigo_no_clasificado"` (§5, §6.3).
Distingue **código no mapeado** (reconocido, sin sede) de **código no clasificado** (desconocido).

---

## 5. Errores tipados (fail-closed)

Hay dos niveles: **errores globales** (`ok: false`) y **status por SKU** (dentro de `results`).

### 5.1 Errores globales (`ok: false`)

| `error.type` | Significado | Distinto de |
|--------------|-------------|-------------|
| `entrada_invalida` | Entrada mal formada: SKUs vacíos, >5, caracteres inválidos, sede inválida, clave extra, tipo inesperado. | — |
| `warehouse_mapping_unconfirmed` | Se pidió `sede=neiva` (o ambas sedes) y el mapeo de códigos físicos a `neiva` no está confirmado (ver §7). | cifra cero / éxito parcial |
| `error_consulta` | Fallo de infraestructura o integridad: timeout, conexión caída, error SQL, ERP no disponible, excepción, resultado no `list`, fila sin claves, SKU inesperado, resultado inválido, centinela alcanzado (§11). | `[]` / cero / cifra parcial |

**Reglas duras:**

- `error_consulta` **nunca** se traduce a `[]`, cero ni cifra. Ante fallo la herramienta responde
  `error_consulta` y **no afirma nada** sobre existencia.
- **Mensajes fijos:** `message` es una cadena **fija** del catálogo. **Nunca** se copia texto del
  driver, del SQL, de la excepción ni de credenciales. (p. ej. `"error consultando inventario J3"`,
  no el mensaje de pymssql/pyodbc.)
- Excepción no capturada, `rows` que no sea `list`, fila a la que le falte una clave esperada,
  un SKU en el resultado que no esté entre los solicitados, o un resultado que no se pueda
  interpretar → `error_consulta`, **nunca** `[]`/cero.

### 5.2 Status por SKU (dentro de `results`, solo con `ok: true`)

| Caso | `status` | Efecto |
|------|----------|--------|
| SKU en catálogo y con ≥1 fila J3 consultable. | `"ok"` | Cifras exactas por bucket (tri-estado §4). |
| Falta el artículo (`AdmArticulos` no contiene el SKU). | `"no_encontrado"` | Sin cifras (no cero). |
| El artículo existe pero no hay filas J3 consultables (ningún almacén comercial del set). | `"inventario_desconocido"` | Sin cifras (no cero). |
| Algún bucket del SKU suma **negativo**. | `"bloqueado"` / `reason: "saldo_negativo"` | Sin cifras. PENDIENTE POR FREDY. |
| Aparece un código de bodega **desconocido/nulo/blanco/nuevo**. | `"bloqueado"` / `reason: "codigo_no_clasificado"` | Sin cifras. |
| Una cifra no pasa la validación exacta (§9) o su origen no está demostrado. | `"bloqueado"` / `reason: "validacion_fallida"` | Sin cifras. |

- `"no_encontrado"` ≠ cero: "no existe el producto" vs "sé que el saldo es exactamente cero".
- `"inventario_desconocido"` ≠ cero: "no puedo saber" vs "sé que es exactamente cero".
- Un fallo **global** de consulta produce `ok: false` sin **ninguna** cifra; un fallo **de un SKU**
  produce un elemento `bloqueado` sin cifras para ese SKU, sin contaminar a los demás.

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
| `FLO` | `sedes.florencia` |
| `B.ROT` | `baja_rotacion` |
| `ALM`, `SUR`, `BD6`, `DIS`, `BOD` | `no_mapeado` |
| `CON`, `CEN`, `EXH`, `EXD`, `BDT`, `MDL`, `TRA` | **excluido** (no participa) |
| cualquier otro / nulo / blanco | **no clasificado** → `bloqueado` |

El orden de evaluación es: normalizar → excluir `CON`/denylist → clasificar en bucket; si el código
no cae en ninguno de los sets anteriores, es **no clasificado** y bloquea el SKU (no se agrega a
`no_mapeado`).

---

## 7. Mapeo códigos físicos → sede

Derivado **únicamente** de `website_warehouse_policy.py` y `j3system_sales_warehouse.py`
(ver §16 por evidencia exacta).

| Código | Sede | Estado de la evidencia |
|--------|------|------------------------|
| `FLO` | `florencia` | **Confirmado** — `WAREHOUSE_CODE_TO_NAME["FLO"] = "ALMACEN FLORENCIA (Sika Center)"`. |
| `ALM` (`001`) | `POR CONFIRMAR POR FREDY` | Las fuentes no contienen "Neiva". |
| `SUR` | `POR CONFIRMAR POR FREDY` | Las fuentes no contienen "Neiva". |
| `BD6` | `POR CONFIRMAR POR FREDY` | Las fuentes no contienen "Neiva". |
| `DIS` (`DISTRIBUCIONES`) | `POR CONFIRMAR POR FREDY` | Las fuentes no contienen "Neiva". |
| `BOD` (`MANGUERAS`) | `POR CONFIRMAR POR FREDY` | Las fuentes no contienen "Neiva". |

Los códigos de la denylist (§6.2) y `CON`/`B.ROT` (§6.1, §8) **no** participan en este mapeo.

**Consecuencia operativa:** `FLO → Florencia` es la única derivación con evidencia local. Los demás
códigos físicos reconocidos (`ALM`, `SUR`, `BD6`, `DIS`, `BOD`) van al bucket `no_mapeado`: **no**
se listan como mapeo a `neiva` ni a ninguna sede, y **no** se presentan como saldo de Neiva. Por
tanto, pedir `sede=neiva` (o ambas sedes) produce `warehouse_mapping_unconfirmed` (§5.1). Un código
**no reconocido** va a `codigo_no_clasificado` (§6), no a `no_mapeado`.

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
ausencia a cero. Los negativos ya están bloqueados antes de llegar aquí (§4).

| `baja_rotacion` | `sedes.florencia` | `no_mapeado` | Señal |
|-----------------|-------------------|--------------|-------|
| cero o ausente | (cualquiera) | (cualquiera) | `"not_required"` |
| positivo | positivo | (cualquiera) | `"not_required"` |
| positivo | cero | cero | `"required"` |
| positivo | ausente | (cualquiera) | `"unknown"` |
| positivo | cero | positivo | `"unknown"` |
| positivo | cero | ausente | `"unknown"` |

- `"required"`: la existencia de la sede confirmada podría depender **solo** de `B.ROT` (solo
  `B.ROT` positivo, y los buckets físicos demostrados en cero); se exige confirmación humana del
  origen físico.
- `"not_required"`: demostrable que no hace falta confirmación (`B.ROT` no positivo, o `florencia`
  positivo).
- `"unknown"`: no se puede determinar (falta dato de fila en un bucket físico, o hay saldo físico
  no mapeado cuya sede de despacho es `POR CONFIRMAR POR FREDY`).

La señal **no** afirma disponibilidad física por `B.ROT`; solo indica si falta confirmación humana
del origen físico. La incertidumbre **nunca** se colapsa a `"not_required"` ni a `"required"` cuando
falta dato.

**Pendientes (no decididos):**
- Solapamiento exacto `B.ROT` ↔ bodegas físicas: **POR CONFIRMAR POR FREDY**.
- Bodega de despacho (cuál sede/bodega efectivamente despacha): **POR CONFIRMAR POR FREDY**.

---

## 9. Representación decimal exacta + validación del servidor (gate)

### 9.1 Hechos demostrados vs. pendientes de esquema

**Hechos demostrados en el worktree (fuentes en §16):**

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
- Regla de canonicalización (solo si el valor es un `Decimal` exacto):
  - Se serializa con **`format(d, "f")`** (punto fijo, **sin** exponente). Se **rechaza** cualquier
    representación que contenga un marcador de exponente (`e`/`E`): bloquea, no se emite.
  - Se canonicaliza el **cero negativo** (`"-0"`, `"-0.00"`…) a `"0"` (sin signo).
  - La cadena resultante debe cumplir `^-?\d+(\.\d+)?$`.
- Si el valor llega como `float`, `int` o `str` (evidencia de una conversión intermedia) en el punto
  de validación, **no** se asume exactitud: se bloquea con `validacion_fallida` hasta demostrar el
  origen.
- **No** se usa `Decimal(str(v)) == v` como prueba de exactitud (es tautológico para un `Decimal`
  ya exacto). La exactitud se establece validando el **origen** (que el valor es el `Decimal` leído
  del bucket, sin pasar por `float`/`round`/cast/clamp), no reparseando.

### 9.3 Validación por el servidor (qué cifra se valida exactamente)

Antes de presentar una cifra, el servidor **debe** verificar, para **cada** cifra emitida, que:

1. **Corresponde al bucket probado:** la cifra de `sedes.florencia` proviene solo de filas `FLO`;
   `no_mapeado` solo de `ALM`/`SUR`/`BD6`/`DIS`/`BOD`; `baja_rotacion` solo de `B.ROT`. Sin cruces.
2. **Corresponde al valor `Decimal` exacto:** el string canónico reparsea a un `Decimal` numéricamente
   igual al valor agregado para ese bucket. (Esto es **correspondencia**, no prueba de origen.)
3. **No se alteró ni creó valor:** ninguna operación `float`, `round`, cast, clamp o `>= 0` intervino.
   La validación **no** altera ni inventa la cifra; solo la verifica.

Esta capacidad **no** está demostrada que exista en el worktree (§9.1). Es un **gate**: si el
runtime no puede validar el contenido numérico final de una cifra, **no** se autoriza esa cifra al
consumidor y se responde `bloqueado`/`validacion_fallida`. No se declara que la validación "ya
existe".

---

## 10. Fuente de stock (builder nuevo; no reutilizar el existente)

Reutilizar la **topología** de la fuente J3 (mismas tablas y joins), pero **no** el builder
existente:

- Tablas/joins: `InvDetalleExistencias → InvExistencias → AdmArticulos → AdmAlmacen`
  (misma topología que `build_website_stock_by_sku_sql`).
- Saldo: `InvDetalleExistencias.SaldoActual` (año vigente = `MAX(Ano)`), leído **por
  `AlmacenCodigo`** para clasificar en buckets (§4).

**Por qué un builder nuevo (evidencia local, §16):** el builder existente
`build_website_stock_by_sku_sql` **interpola** los SKUs (no usa bind params), aplica
`CAST(... AS DECIMAL(18, 4))`, filtra `CAST(...) >= 0` y un `HAVING ... > 0`. Ninguno de esos
comportamientos es admisible en `catalog.stock`:

1. Obtener el saldo **por `AlmacenCodigo`** (no solo el total allowlist).
2. **Leer `SaldoActual` sin cast** y **sin** filtro `>= 0` ni `HAVING` (los negativos deben ser
   visibles para bloquearse, §4).
3. Excluir `CON` y la denylist tras normalizar trim+uppercase (§6).
4. Mapear `FLO → florencia` (§7); `ALM`/`SUR`/`BD6`/`DIS`/`BOD` → `no_mapeado`; `B.ROT` → línea
   `baja_rotacion` (§8); código desconocido → `codigo_no_clasificado` (§6).
5. SKUs pasados como **parámetros bind** (nunca interpolación desde entrada de usuario).

Solo se reutiliza un helper (p. ej. `sql_in_list`) para valores **fijos de policy** (códigos de
bodega, constantes no derivadas de entrada), y únicamente si la evidencia local demuestra que es
seguro para ese uso. Nunca para los SKUs de entrada.

---

## 11. SQL (solo lectura, parametrizado, timeout, límite verificable)

- **Solo lectura:** `SELECT` únicamente. Sin `INSERT`/`UPDATE`/`DELETE`/`MERGE`.
- **Parametrizado:** cada SKU de entrada se pasa como **parámetro bind** (nunca interpolación de
  strings desde entrada del usuario). Los códigos de bodega provienen de la policy fija, no de
  entrada de usuario.
- **Timeout:** timeout de conexión/consulta acotado a un valor **explícito ≤ 10 s**. Si la
  configuración local de timeout no está definida, se define una explícita en el builder. Timeout →
  `error_consulta`. (No se asume la existencia de una constante `DB_TIMEOUT`; es un requisito a
  definir.)
- **Límite verificable (sin truncado silencioso):** la consulta agrupa por (SKU, `AlmacenCodigo`)
  con `WHERE` sobre los ≤5 SKUs. El máximo de filas esperado es `5 × |códigos conocidos|`. **No** se
  usa `TOP`/`LIMIT` para truncar cantidades. Se usa un **centinela** (`TOP (max_esperado + 1)` en
  T-SQL) para detectar desbordamiento: si se alcanza el centinela/tope, o no se puede demostrar la
  integridad del resultado, → `error_consulta` sin cifras. **T-SQL no usa `LIMIT`**; solo `TOP`.
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
4. **Convención de respuesta:** este contrato usa el envoltorio `{ok, error}` (fail-closed), que
   **difiere** de la convención `{status, reason}` de algunos tools locales (`builtins.py`). Se
   **justifica** la diferencia: un fallo de consulta no debe poder confundirse con un resultado
   vacío (`status: "empty"`), y `{ok: false}` + `error.type` fijo es más seguro para fail-closed. La
   decisión de adoptar o no esta convención es parte del contrato, no de la implementación.

### 13.1 Matriz mínima de tests (fake-only)

Todos los tests usan **datos sintéticos/fake**, nunca DB real ni credenciales.

| # | Caso | Resultado esperado |
|---|------|--------------------|
| 1 | `skus` vacío / >5 / caracteres inválidos / clave extra / tipo inesperado. | `entrada_invalida` (global). |
| 2 | `sede: "neiva"` o `sede` ausente. | `warehouse_mapping_unconfirmed` (global, sin éxito parcial). |
| 3 | `sede: "florencia"`, SKU en catálogo, fila `FLO` positiva. | `ok`, `status: "ok"`, `sedes.florencia` = string decimal. |
| 4 | SKU en catálogo, sin fila para un bucket. | bucket ausente = `null` (**no** `"0"`). |
| 5 | SKU en catálogo, fila con `SUM = 0` para un bucket. | bucket = `"0"` (cero con evidencia). |
| 6 | SKU no en `AdmArticulos`. | `status: "no_encontrado"` (sin cifras, no cero). |
| 7 | SKU en catálogo, sin filas J3 consultables. | `status: "inventario_desconocido"` (sin cifras). |
| 8 | Algún bucket suma negativo. | `status: "bloqueado"`, `reason: "saldo_negativo"`, sin números. |
| 9 | Código de bodega desconocido/nulo/blanco. | `status: "bloqueado"`, `reason: "codigo_no_clasificado"`. |
| 10 | `CON` y denylist (`CEN`,`EXH`,`EXD`,`BDT`,`MDL`,`TRA`) presentes. | excluidas de los buckets (no suman). |
| 11 | Driver lanza excepción / `rows` no es `list` / fila sin claves / SKU inesperado / centinela alcanzado. | `error_consulta` (global), mensaje fijo, sin cifras. |
| 12 | Valor llega como `float`/`int`/`str` (origen no `Decimal` demostrado) o no pasa §9. | `status: "bloqueado"`, `reason: "validacion_fallida"`. |
| 13 | Mezcla de SKUs: uno `ok`, uno `no_encontrado`, uno `bloqueado`. | `results` con un elemento por SKU, sin mezclar cifras ambiguas. |
| 14 | Canonicalización: `format(d, "f")` sin exponente; cero negativo → `"0"`. | string `^-?\d+(\.\d+)?$`. |

---

## 14. Límites de implementación

- **≤ 300 líneas de lógica** por herramienta (`catalog.stock`).
- **`builtins.py` solo con registro mínimo** del `ToolSpec` (nombre, descripción, scope,
  `parameters_schema`, handler); **sin lógica nueva** en `builtins.py`.
- La lógica vive en un módulo dedicado (p. ej. bajo `modules/catalog`), no en `builtins.py`.
- Tests futuros **fake-only** (nunca DB real ni credenciales).

### 14.5 Audiencia / scope — PENDIENTE POR FREDY

- **No** se declara ni registra `PUBLIC_STOCK` / `public_safe=True` como autorización para publicar
  cantidades o estructura interna. El enum `ToolScope.PUBLIC_STOCK` **existe** en
  `depotru_kernel/auth.py` (hecho), pero **no** es por sí solo una autorización de audiencia
  pública para estas cifras.
- La decisión vigente ("cifras exactas como dato de herramienta") **no** define por sí sola la
  audiencia pública.
- Marca: audiencia/scope **PENDIENTE POR FREDY**. Hasta resolverlo, `catalog.stock` **no** se
  registra ni se expone públicamente (sin registro/exposición pública).

---

## 15. Por confirmar por Fredy (resumen)

1. Mapeo de `ALM`/`SUR`/`BD6`/`DIS`/`BOD` a una sede (hipótesis `neiva` **no probada** por las dos
   fuentes; pendiente de Fredy).
2. Solapamiento `B.ROT` ↔ bodegas físicas.
3. Bodega de despacho.
4. Semántica comercial de saldos/totales **negativos** (hasta decisión, bloquean la cifra, §4).
5. Audiencia/scope de exposición pública de las cantidades (§14.5).

> Eliminado respecto al borrador anterior: el umbral numérico de "pocas unidades" (propuesta `5`),
> que **no** está aprobado.

---

## 16. Evidencia local

| Evidencia | Archivo | Confirma |
|-----------|---------|----------|
| `WAREHOUSE_CODE_TO_NAME` incluye `FLO = "ALMACEN FLORENCIA (Sika Center)"`, `CON = "CONTABILIDAD"`, `B.ROT = "PRODUCTOS DE BAJA ROTACION"`. | `src/business_analyzer/core/j3system_sales_warehouse.py` | `FLO → Florencia` (única ciudad nombrada). Resto sin ciudad. |
| Denylist web (`CEN`, `EXH`, `EXD`, `BDT`, `MDL`, `TRA`) y allowlist web (incluye `CON` y `B.ROT`). | `src/business_analyzer/core/website_warehouse_policy.py` | Política web ≠ política comercial. |
| `build_website_stock_by_sku_sql` interpola SKUs (no bind), aplica `CAST(... AS DECIMAL(18, 4))`, filtro `CAST(...) >= 0` y `HAVING ... > 0`. | `src/business_analyzer/core/j3system_website_stock.py` | Requiere builder nuevo (§10); cast/filtro **no** se heredan. |
| Conversión explícita `float(raw_qty)` en `_quote_search_j3`. | `src/depotru_tools/builtins.py` | El protocolo local actual usa `float`; justifica el gate §9. |
| Enum `ToolScope.PUBLIC_STOCK` y `public_safe` existen en el `ToolSpec`. | `src/depotru_kernel/auth.py`, `src/depotru_tools/registry.py` | El scope **existe**, pero **no** autoriza audiencia pública (§14.5). |
| La API monta `ToolCallResponse` con `result: Any` vía Pydantic/`response_model`. | `src/apps/api/v1.py`, `src/api.py` | No hay un encoder `Decimal`→string custom demostrado; el default no se asume (§9.1). |

**No afirmado / no encontrado en el worktree:**

- No se halló un encoder JSON custom ni emisión de string para `Decimal` (el camino de
  serialización local no está demostrado como exacto).
- No se halló `jsonable_encoder` en `src/apps/api/v1.py` ni `src/api.py` (afirmación retirada del
  borrador anterior).
- El tipo concreto del driver para columnas `DECIMAL` y la escala nativa de `SaldoActual` **no**
  están demostrados (pendientes de esquema, §9.1).
- `docs/CRM` (orden de Fredy) no existe como archivo en esta rama; la política comercial de este
  contrato se deriva del encargo y de las dos políticas locales citadas. Si la orden de Fredy vive
  en otro worktree/repo, debe adjuntarse para validar §6–§8.
