# Minería de guías del asistente (`chat_log.jsonl`)

**Issue:** [Phase 3 / n.º 65](https://github.com/Trujillofa/depotru_database/issues/65) (parte C)
**CLI:** `depotru-mine-chat-guides`
**Código:** `business_analyzer.jobs.chat_log_guides`
**Script:** `scripts/analysis/mine_chat_log_guides.py`

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

La redacción de correos, teléfonos, NIT/CC, facturas, secretos, IPs, nombres
y direcciones es de **mejor esfuerzo**. No garantiza que no quede dato
personal. **Un humano debe revisar la salida (Markdown, CSV, borradores,
nombres de archivo y la consola) antes de compartirla o abrir un issue.**

La salida no incluye `session_id` ni el texto de las respuestas. El
`cluster_id` sale de un hash del texto ya redactado.

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

Espere `SYNTHETIC:` en el Markdown/CSV. Revise
`unmatched_question_clusters.md` / `.csv`. `--draft` escribe
`borrador_guia_*.md` y `borrador_issue_*.md` (nunca publica una guía ni abre
un issue). Cada corrida borra los `borrador_*.md` viejos de esa carpeta.

## Cómo ejecutarlo (registro privado)

```bash
PYTHONPATH=src python scripts/analysis/mine_chat_log_guides.py \
  --output-dir /tmp/chat_guides_mining --top 10
```

Si el archivo no existe o está vacío, el comando sale con código 0 y un
mensaje en español. No inventa preguntas. Si no hay permiso de lectura, el
archivo es binario o `--output-dir` es un archivo, sale con código 1 y un
mensaje en español (sin traza). Las líneas con UTF-8 inválido se saltan.

## Borradores de guía

Use `--draft` o copie [problem-guide-template.md](problem-guide-template.md).
Un humano revisa el borrador en español colombiano y, si sirve, lo agrega a
mano en `src/modules/assistant/problem_guides.py`.
