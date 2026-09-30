# Minería de guías del asistente (`chat_log.jsonl`)

**Issue:** [Phase 3 / n.º 65](https://github.com/Trujillofa/depotru_database/issues/65) (parte C)
**CLI:** `depotru-mine-chat-guides`
**Código:** `business_analyzer.jobs.chat_log_guides`
**Script:** `scripts/analysis/mine_chat_log_guides.py`
**Lista blanca:** `src/business_analyzer/jobs/chat_log_guides_allowlist.txt`

Análisis de solo lectura del registro del asistente de vitrina. **No** cambia
el enrutamiento del asistente, los informes ni el SQL. No habla con la base
de datos ni con un LLM.

El escritor es `modules.assistant.logging.log_assistant_turn` (campos: `ts`,
`session_id`, `audience`, `locale`, `message` ≤500, `reply_preview` ≤200,
`tools_used`, `mode`, `guide_id`, `product_query`, `grounded`). La coincidencia
reutiliza `modules.assistant.problem_guides.match_guide` y un `guide_id` ya
registrado. Ruta por defecto: `data/assistant/chat_log.jsonl` (se cambia con
`--log-path` o Settings `ASSISTANT_CHAT_LOG`). La carpeta `data/assistant/`
está en `.gitignore`. El escritor y el minero leen esa ruta por Settings.

## Privacidad (mejor esfuerzo)

El registro real es **privado**. No lo suba a git.

La salida visible (Markdown, CSV, borradores, consola, nombres de archivo y
`cluster_id`) es **lista blanca por defecto**: del texto del usuario solo
pasan palabras en minúscula, solo letras (tras NFKC, quitar marcas invisibles
y doblar tildes) que estén en
`chat_log_guides_allowlist.txt`. Todo lo demás (dígitos, nombres, handles,
URLs, secretos, palabras desconocidas) se descarta o se cambia por un
marcador neutro (`email`, `tel`, `documento`, `numero`, `secreto`, `nombre`,
`direccion`, `url`, `ref`). **Los dígitos del usuario nunca se escriben.**

El agrupamiento puede usar por dentro el texto normalizado completo. Solo la
proyección de la lista blanca se muestra o se hashea en `cluster_id` / id
propuesto (letras, sin dígitos).

Encima hay una capa regex de **mejor esfuerzo** (correos, celulares de 10
dígitos que empiezan por 3, NIT de 9, grupos con puntos o barras, tarjetas
de 13–19, dígitos tras etiquetas, secretos, URIs). **No garantiza** que no
quede dato personal. **Un humano debe revisar la salida antes de
compartirla o abrir un issue.**

La salida no incluye `session_id` ni el texto de las respuestas.

Para ampliar el vocabulario visible (términos de ferretería, nombres de
informe, columnas), edite el `.txt`: una palabra en minúscula por línea;
`#` inicia comentario. No agregue nombres de personas ni dígitos.

### Brechas conocidas

La lista blanca evita que un token desconocido o un dígito salga a un
archivo, pero **no es una garantía de privacidad**. Un humano debe mirar
estos casos (y cualquier otro) antes de compartir:

- Tras `clave`, `pin`, `password`, `passphrase`, `contraseña` o
  `codigo secreto`, se redacta el resto de la oración (hasta `.` `!` `?`),
  también si hay coma, guion, puntos o `:` (`clave, es X`, `clave - X`).
  Eso también se come texto inocente (`la clave al vendedor` →
  `la secreto`). `clave` sola, sin valor, sigue visible. Una frase de
  contraseña **sin** etiqueta puede dejar palabras de la lista.
- Nombres: se quitaron de la lista blanca entradas tipo nombre propio
  (`ada`, `marco`, `mina`, `cielo`, `blanca`, `estrella`, `diamante`,
  `cortes`, `luz`, `neiva`, `huila`, `mica`). Un nombre que coincida con
  otra palabra de ferretería o de función que siga en el `.txt` puede
  mostrarse.
- Números deletreados: tres o más palabras-dígito seguidas (`cero`…`nueve`,
  p. ej. `cinco tres dos` o `tres uno uno dos dos dos`) se colapsan a
  `numero`. Una o dos (`uno dos`) se muestran como palabras; no se
  convierten a `1`/`2`/`3`. Compuestos (`once`, `veinte`, `trescientos`)
  no son dígitos-palabra y, si están en la lista, se muestran.
- Un término nuevo de ferretería que no esté en el `.txt` desaparece de la
  salida (falso negativo de vocabulario). Agréguelo a la lista a mano.
- La capa regex aún puede etiquetar de más: un NIT de 9 dígitos o un
  celular `3` + 9 dígitos se redacta aunque sea un código de producto; un
  `SKU-123456` **no** se marca como documento (el `123456` no se muestra).
- Ofuscaciones nuevas o dominios partidos de forma rara pueden no
  coincidir con el regex; la lista blanca igual impide que salgan.
- Contraseñas en texto libre **sin** etiqueta (`apikey` suelta, token
  sin `clave`/`pin`/`password`) pueden no entrar al regex; si el valor
  no está en la lista, no se muestra.
- Tratamientos (`Sr.`, `Dr.`, `Ing.`, `cliente:`, `atendido por`, …) son
  heurísticos. `soy constructor` / `soy nuevo` / `cliente frecuente` no
  se tratan como nombre.
- `calle 45 de cemento` no se come la palabra `cemento`; el `45` no
  aparece. Direcciones (`Av. Boyacá 68-45`, `Mz 5 Cs 12`) pierden números
  y nombres de barrio que no estén en la lista.
- `--draft` solo borra archivos regulares (no enlaces, no carpetas) cuyo
  nombre es exactamente `borrador_(guia|issue)_c<12 letras>.md`. No toca
  `borrador_mis_notas.md` ni nada en subcarpetas. Sin `--draft` no borra
  borradores. Si el nombre de salida es un enlace, se reemplaza el enlace
  (no se escribe a través de él). Si es una carpeta, el error lo dice.

La **lista top 10 de preguntas reales sin guía** se obtiene ejecutando este
script contra el registro privado en una máquina que lo tenga. Las guías de
esas preguntas se pueden redactar después. Este repositorio solo incluye un
fixture **SYNTHETIC**.

## Cómo ejecutarlo (sintético, sin registro real)

```bash
PYTHONPATH=src python scripts/analysis/mine_chat_log_guides.py \
  --synthetic --output-dir /tmp/chat_guides_mining --draft

# o
depotru-mine-chat-guides --synthetic --output-dir /tmp/chat_guides_mining
```

Espere `synthetic` en el Markdown/CSV. Revise
`unmatched_question_clusters.md` / `.csv`. `--draft` escribe
`borrador_guia_*.md` y `borrador_issue_*.md` (nunca publica una guía ni abre
un issue). Con `--draft` solo se quitan borradores previos generados por
esta herramienta (`borrador_(guia|issue)_c<12 letras>.md`); no se tocan
archivos del usuario.

## Cómo ejecutarlo (registro privado)

```bash
PYTHONPATH=src python scripts/analysis/mine_chat_log_guides.py \
  --output-dir /tmp/chat_guides_mining --top 10
```

Si el archivo no existe o está vacío, el comando sale con código 0 y un
mensaje en español. No inventa preguntas. Si no hay permiso de lectura, el
archivo es binario o `--output-dir` es un archivo, sale con código 1 y un
mensaje en español (sin traza). Las líneas de más de 4096 bytes se saltan
(el mensaje no dice que el registro esté vacío). Las líneas con UTF-8
inválido se saltan.

## Borradores de guía

Use `--draft` o copie [problem-guide-template.md](problem-guide-template.md).
Un humano revisa el borrador en español colombiano y, si sirve, lo agrega a
mano en `src/modules/assistant/problem_guides.py`.
