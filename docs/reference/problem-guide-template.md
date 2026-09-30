# Plantilla de guía de problema (borrador)

**Estado:** BORRADOR — no publicar, no crear issue automáticamente.
**Idioma:** español colombiano, tono de ferretería / materiales (Neiva).
**Código:** un humano copia esto a `src/modules/assistant/problem_guides.py`
si la guía se aprueba. El minero no publica ni abre issues.

Use esta plantilla para un grupo del top 10 de
[chat-log-guides-mining.md](chat-log-guides-mining.md). Pegue solo texto
**redactado**. Nunca incluya correos, teléfonos, cédulas, NIT, `session_id`
ni claves.

```text
id: (snake_case, corto)
title: (oración para el cliente, sin SKU)
patterns:
  - (regex, español con tildes opcionales)
intro: Para este trabajo suele hacer falta:
needs:
  - label: (cómo lo pide el cliente)
    query: (fragmento de búsqueda en catálogo)
tip: (un consejo corto; seguridad si aplica)
```

## Pregunta representativa (redactada)

(pegar)

## Otras formulaciones (redactadas)

-

## Introducción

Para este trabajo suele hacer falta:

## Lista de necesidades

| Etiqueta (cliente) | Búsqueda en catálogo |
|--------------------|----------------------|
| | |

## Consejo

## Notas para revisión

- ¿Choca con una guía existente (`match_guide`)?
- ¿El cliente habla de un trabajo / problema, no solo de un SKU?
- ¿La lista se entiende sin códigos internos?
