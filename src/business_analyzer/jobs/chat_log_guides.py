"""Mine assistant chat_log.jsonl for unmatched problem-guide clusters.

Read-only. No network, no LLM, no database, no write SQL. Reuses
``modules.assistant.problem_guides.match_guide`` so assistant routing is
unchanged. Output never includes session ids, reply text, or raw PII.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, TextIO

from business_analyzer.core.config import Settings, get_settings
from modules.assistant.problem_guides import match_guide

DEFAULT_LOG_RELATIVE = Path("data/assistant/chat_log.jsonl")
DEFAULT_TOP_N = 10
JACCARD_THRESHOLD = 0.5

MSG_MISSING = (
    "No se encontró el archivo de registro de chat (chat_log.jsonl). "
    "Nada que analizar."
)
MSG_EMPTY = "El registro de chat está vacío. No hay preguntas para analizar."
MSG_NOT_FILE = "La ruta del registro de chat no es un archivo. Nada que analizar."
MSG_ALL_MATCHED = "No hay preguntas sin guía coincidente."
MSG_SYNTHETIC_NOTE = (
    "Fixture SYNTHETIC: no es un registro real. El top 10 real se obtiene "
    "ejecutando este script contra el chat_log.jsonl privado."
)

STOPWORDS = frozenset(
    {
        "el",
        "la",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "de",
        "del",
        "al",
        "a",
        "y",
        "o",
        "en",
        "para",
        "por",
        "con",
        "que",
        "se",
        "me",
        "te",
        "mi",
        "tu",
        "su",
        "es",
        "son",
        "hay",
        "como",
        "cuando",
        "donde",
        "cual",
        "hola",
        "buenas",
        "favor",
        "porfa",
        "gracias",
        "the",
        "and",
        "quiero",
        "necesito",
        "ando",
        "busco",
        "buscar",
    }
)

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b", re.I)
_SECRET_RE = re.compile(
    r"\b(?:xai-[A-Za-z0-9]+|sk-ant-[A-Za-z0-9-]+|sk-[A-Za-z0-9]+)\b"
)
_DOC_LABEL_RE = re.compile(
    r"\b(?:cc|nit|c[eé]dula|cedula|pasaporte)\s*[:.\-]?\s*[\d.\-]+\b",
    re.I,
)
_PHONE_INTL_RE = re.compile(
    r"\+57[\s.\-]*\d{3}[\s.\-]*\d{3}[\s.\-]*\d{4}",
)
_PHONE_MOBILE_SEP_RE = re.compile(r"\b3\d{2}[\s.\-]\d{3}[\s.\-]\d{4}\b")
_PHONE_MOBILE_RE = re.compile(r"\b3\d{9}\b")
_NIT_DOTS_RE = re.compile(r"\b\d{1,3}(?:\.\d{3}){2,3}(?:-\d)?\b")
_LONG_DIGITS_RE = re.compile(r"\d{6,}")
_UNSAFE_CSV_PREFIX = frozenset({"=", "+", "-", "@", "\t", "\r"})


def _synthetic_jsonl_line(
    session_id: str,
    message: str,
    *,
    guide_id: Optional[str] = None,
    minute: int = 0,
) -> str:
    record = {
        "ts": f"2026-09-30T12:{minute:02d}:00+00:00",
        "session_id": session_id,
        "audience": "public",
        "locale": "es_CO",
        "message": message,
        "reply_preview": "SYNTHETIC",
        "tools_used": [],
        "mode": "stub_tools",
        "guide_id": guide_id,
        "product_query": None,
        "grounded": True,
    }
    return json.dumps(record, ensure_ascii=False)


SYNTHETIC_CHAT_LOG_JSONL = (
    "\n".join(
        [
            _synthetic_jsonl_line(
                "SYNTHETIC-SESS-1",
                "SYNTHETIC: cuanto vale el cemento demo xyz",
                minute=0,
            ),
            _synthetic_jsonl_line(
                "SYNTHETIC-SESS-2",
                "SYNTHETIC: ¿Cuánto vale el cemento demo xyz?",
                minute=1,
            ),
            _synthetic_jsonl_line(
                "SYNTHETIC-SESS-3",
                "SYNTHETIC: precio del cemento demo xyz",
                minute=2,
            ),
            _synthetic_jsonl_line(
                "SYNTHETIC-SESS-4",
                "SYNTHETIC: horario de atencion sede demo",
                minute=3,
            ),
            _synthetic_jsonl_line(
                "SYNTHETIC-SESS-5",
                "SYNTHETIC: cotizar a demo.user@example.test tel 3001234567",
                minute=4,
            ),
            _synthetic_jsonl_line(
                "SYNTHETIC-SESS-6",
                "tengo una gotera",
                guide_id="gotera",
                minute=5,
            ),
        ]
    )
    + "\n"
)


@dataclass(frozen=True)
class QuestionRecord:
    message: str
    redacted: str
    normalized: str
    tokens: frozenset[str]
    guide_id: Optional[str]
    matched: bool


@dataclass(frozen=True)
class QuestionCluster:
    cluster_id: str
    count: int
    representative: str
    examples: tuple[str, ...]
    normalized: str


@dataclass(frozen=True)
class MineResult:
    clusters: tuple[QuestionCluster, ...]
    records_read: int
    unmatched: int
    skipped_lines: int
    message: str
    empty: bool


def redact_pii(text: str) -> str:
    """Replace emails, phones, documents, long digits, and API-key-like secrets."""
    value = text or ""
    value = _EMAIL_RE.sub(" email ", value)
    value = _SECRET_RE.sub(" secreto ", value)
    value = _DOC_LABEL_RE.sub(" documento ", value)
    value = _PHONE_INTL_RE.sub(" tel ", value)
    value = _PHONE_MOBILE_SEP_RE.sub(" tel ", value)
    value = _PHONE_MOBILE_RE.sub(" tel ", value)
    value = _NIT_DOTS_RE.sub(" documento ", value)
    value = _LONG_DIGITS_RE.sub(" numero ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(
        r"\b(email|tel|documento|numero|secreto)(?:\s+\1)+\b",
        r"\1",
        value,
        flags=re.I,
    )


def normalize_question(text: str) -> str:
    value = (text or "").strip().lower()
    value = "".join(
        char
        for char in unicodedata.normalize("NFD", value)
        if unicodedata.category(char) != "Mn"
    )
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokenize(normalized: str) -> frozenset[str]:
    return frozenset(
        token
        for token in (normalized or "").split()
        if len(token) >= 3 and token not in STOPWORDS
    )


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def resolve_log_path(
    explicit: Optional[Path] = None,
    settings: Optional[Settings] = None,
) -> Path:
    if explicit is not None and str(explicit).strip():
        return Path(explicit).expanduser()
    snapshot = settings if settings is not None else get_settings()
    configured = (snapshot.ASSISTANT_CHAT_LOG or "").strip()
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_LOG_RELATIVE


def parse_record(raw: object) -> Optional[QuestionRecord]:
    if not isinstance(raw, dict):
        return None
    message = str(raw.get("message") or "").strip()
    if not message:
        return None
    logged_guide = raw.get("guide_id")
    if logged_guide is None:
        guide_id = None
    else:
        guide_id = str(logged_guide).strip() or None
    redacted = redact_pii(message)
    normalized = normalize_question(redacted)
    if not normalized:
        return None
    matched = guide_id is not None or match_guide(message) is not None
    return QuestionRecord(
        message=message,
        redacted=redacted,
        normalized=normalized,
        tokens=tokenize(normalized),
        guide_id=guide_id,
        matched=matched,
    )


def _iter_jsonl_records(text: str) -> tuple[list[QuestionRecord], int, int]:
    records: list[QuestionRecord] = []
    skipped = 0
    seen_lines = 0
    for line in text.splitlines():
        if not line.strip():
            skipped += 1
            continue
        seen_lines += 1
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        record = parse_record(payload)
        if record is None:
            skipped += 1
            continue
        records.append(record)
    return records, seen_lines, skipped


def _empty_result(message: str, *, skipped: int = 0, read: int = 0) -> MineResult:
    return MineResult(
        clusters=(),
        records_read=read,
        unmatched=0,
        skipped_lines=skipped,
        message=message,
        empty=True,
    )


def mine_chat_log_text(text: str, *, top: int = DEFAULT_TOP_N) -> MineResult:
    if not (text or "").strip():
        return _empty_result(MSG_EMPTY)
    records, _seen, skipped = _iter_jsonl_records(text)
    unmatched = [row for row in records if not row.matched]
    if not unmatched:
        return MineResult(
            clusters=(),
            records_read=len(records),
            unmatched=0,
            skipped_lines=skipped,
            message=MSG_ALL_MATCHED if records else MSG_EMPTY,
            empty=True,
        )
    clusters = top_unmatched_clusters(cluster_unmatched(unmatched), n=top)
    return MineResult(
        clusters=tuple(clusters),
        records_read=len(records),
        unmatched=len(unmatched),
        skipped_lines=skipped,
        message="",
        empty=False,
    )


def mine_chat_log(path: Path, *, top: int = DEFAULT_TOP_N) -> MineResult:
    target = Path(path)
    if not target.exists():
        return _empty_result(MSG_MISSING)
    if not target.is_file():
        return _empty_result(MSG_NOT_FILE)
    text = target.read_text(encoding="utf-8")
    if not text.strip():
        return _empty_result(MSG_EMPTY)
    return mine_chat_log_text(text, top=top)


def cluster_unmatched(records: Sequence[QuestionRecord]) -> list[QuestionCluster]:
    groups: dict[str, list[QuestionRecord]] = {}
    for record in records:
        if record.matched:
            continue
        groups.setdefault(record.normalized, []).append(record)

    pending = sorted(groups.items(), key=lambda item: item[0])
    merged: list[list[QuestionRecord]] = []
    merged_tokens: list[frozenset[str]] = []
    for _normalized, members in pending:
        tokens = members[0].tokens
        assigned = False
        for index, existing in enumerate(merged_tokens):
            if jaccard(tokens, existing) >= JACCARD_THRESHOLD:
                merged[index].extend(members)
                merged_tokens[index] = existing | tokens
                assigned = True
                break
        if not assigned:
            merged.append(list(members))
            merged_tokens.append(tokens)
    return [_build_cluster(members) for members in merged]


def _build_cluster(members: Sequence[QuestionRecord]) -> QuestionCluster:
    counts = Counter(item.redacted for item in members)
    representative = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    examples = tuple(
        text
        for text, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if text != representative
    )[:3]
    tokens: set[str] = set()
    for item in members:
        tokens.update(item.tokens)
    frozen = frozenset(tokens)
    normalized = normalize_question(representative)
    digest = hashlib.sha256(" ".join(sorted(frozen)).encode("utf-8")).hexdigest()[:8]
    slug = "_".join(normalized.split()[:6])[:48] or "cluster"
    return QuestionCluster(
        cluster_id=f"{slug}_{digest}",
        count=len(members),
        representative=representative,
        examples=examples,
        normalized=normalized,
    )


def top_unmatched_clusters(
    clusters: Sequence[QuestionCluster],
    n: int = DEFAULT_TOP_N,
) -> list[QuestionCluster]:
    ordered = sorted(clusters, key=lambda item: (-item.count, item.normalized))
    return list(ordered[: max(n, 0)])


def _csv_cell(value: str) -> str:
    if value and value[0] in _UNSAFE_CSV_PREFIX:
        return "'" + value
    return value


def render_markdown(clusters: Sequence[QuestionCluster]) -> str:
    lines = [
        "# Preguntas sin guía coincidente",
        "",
        "Solo texto redactado. No incluye datos personales, secretos ni `session_id`.",
        "",
        "| # | Conteo | Representativa (redactada) | Ejemplos |",
        "|---|--------|----------------------------|----------|",
    ]
    if not clusters:
        lines.append("| — | 0 | — | — |")
        return "\n".join(lines) + "\n"
    for index, cluster in enumerate(clusters, start=1):
        examples = "; ".join(cluster.examples) if cluster.examples else "—"
        lines.append(
            f"| {index} | {cluster.count} | {cluster.representative} | {examples} |"
        )
    return "\n".join(lines) + "\n"


def render_csv(clusters: Sequence[QuestionCluster]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["rango", "conteo", "cluster_id", "representativa", "ejemplos"])
    for index, cluster in enumerate(clusters, start=1):
        writer.writerow(
            [
                index,
                cluster.count,
                cluster.cluster_id,
                _csv_cell(cluster.representative),
                _csv_cell(" | ".join(cluster.examples)),
            ]
        )
    return buffer.getvalue()


def _proposed_guide_id(normalized: str) -> str:
    tokens = [
        token
        for token in normalized.split()
        if token not in STOPWORDS and token != "synthetic"
    ]
    slug = "_".join(tokens[:5]) or "sin_titulo"
    return slug[:60]


def render_draft_guide(cluster: QuestionCluster) -> str:
    guide_id = _proposed_guide_id(cluster.normalized)
    title = cluster.representative
    if title.lower().startswith("synthetic:"):
        title = title.split(":", 1)[1].strip()
    title = title[:1].upper() + title[1:] if title else "Sin título"
    escaped = re.escape(normalize_question(cluster.representative))
    examples = "\n".join(f"- {item}" for item in cluster.examples) or "- (sin otros)"
    return (
        f"# Guía (borrador): {title}\n\n"
        "**Estado:** BORRADOR — no publicar, no crear issue automáticamente.\n"
        f"**Origen:** minería de `chat_log.jsonl` (conteo {cluster.count}).\n"
        f"**id propuesto:** `{guide_id}`\n\n"
        "## Pregunta representativa (redactada)\n\n"
        f"{cluster.representative}\n\n"
        "## Otras formulaciones (redactadas)\n\n"
        f"{examples}\n\n"
        "## Patrones (regex, propuesta)\n\n"
        f"- `{escaped}`\n\n"
        "## Introducción\n\n"
        "Para este trabajo suele hacer falta:\n\n"
        "## Lista de necesidades\n\n"
        "| Etiqueta (cliente) | Búsqueda en catálogo |\n"
        "|--------------------|----------------------|\n"
        "| (completar) | (completar) |\n\n"
        "## Consejo\n\n"
        "Completar con un tip corto en español colombiano.\n\n"
        "## Notas para revisión\n\n"
        "Un humano debe revisar este borrador y, si aplica, añadirlo a "
        "`src/modules/assistant/problem_guides.py` a mano. Este archivo no se "
        "publica solo.\n"
    )


def render_draft_issue_body(cluster: QuestionCluster) -> str:
    guide_id = _proposed_guide_id(cluster.normalized)
    return (
        f"# Borrador de guía: `{guide_id}`\n\n"
        "**Estado:** BORRADOR — no crear este issue automáticamente; no publicar.\n"
        "Parte de #65 (Phase 3c). Plantilla: "
        "`docs/reference/problem-guide-template.md`.\n\n"
        f"**Conteo (redactado):** {cluster.count}\n\n"
        "## Pregunta representativa (redactada)\n\n"
        f"{cluster.representative}\n\n"
        "Incluye una lista de necesidades para el cliente. "
        "Un humano decide si abre el issue y si incorpora la guía.\n"
    )


def _safe_filename(cluster_id: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", cluster_id.lower()).strip("_")
    return (cleaned or "cluster")[:80]


def write_outputs(
    clusters: Sequence[QuestionCluster],
    output_dir: Path,
    *,
    write_drafts: bool = False,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    md_path = output_dir / "unmatched_question_clusters.md"
    csv_path = output_dir / "unmatched_question_clusters.csv"
    md_path.write_text(render_markdown(clusters), encoding="utf-8")
    csv_path.write_text(render_csv(clusters), encoding="utf-8")
    written["markdown"] = md_path
    written["csv"] = csv_path
    if write_drafts:
        for cluster in clusters:
            stem = _safe_filename(cluster.cluster_id)
            guide_path = output_dir / f"borrador_guia_{stem}.md"
            issue_path = output_dir / f"borrador_issue_{stem}.md"
            guide_path.write_text(render_draft_guide(cluster), encoding="utf-8")
            issue_path.write_text(render_draft_issue_body(cluster), encoding="utf-8")
            written[f"guide_{stem}"] = guide_path
            written[f"issue_{stem}"] = issue_path
    return written


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analiza el registro de chat (chat_log.jsonl) y lista las "
            "preguntas sin guía coincidente. Solo lectura. No publica guías "
            "ni crea issues."
        )
    )
    parser.add_argument(
        "--log-path",
        default="",
        help=(
            "Ruta al JSONL. Por defecto: Settings ASSISTANT_CHAT_LOG o "
            "data/assistant/chat_log.jsonl."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help=(
            "Carpeta para Markdown/CSV (por defecto: "
            "data/assistant/guide_mining, gitignorada)."
        ),
    )
    parser.add_argument(
        "--top",
        type=int,
        default=DEFAULT_TOP_N,
        help="Cuántos grupos mostrar (por defecto 10).",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help=(
            "Escribe borradores de guía e issue (no se publica, no se crea "
            "el issue)."
        ),
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Usa el fixture SYNTHETIC (no es un registro real).",
    )
    return parser.parse_args(argv)


def _print_status(message: str, stream: Optional[TextIO] = None) -> None:
    target = sys.stdout if stream is None else stream
    target.write(message.rstrip() + "\n")


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    if args.synthetic:
        result = mine_chat_log_text(SYNTHETIC_CHAT_LOG_JSONL, top=args.top)
        _print_status(MSG_SYNTHETIC_NOTE)
    else:
        explicit = Path(args.log_path) if args.log_path.strip() else None
        result = mine_chat_log(resolve_log_path(explicit), top=args.top)
    if result.empty:
        _print_status(result.message)
        return 0
    output_dir = (
        Path(args.output_dir).expanduser()
        if args.output_dir.strip()
        else Path("data/assistant/guide_mining")
    )
    written = write_outputs(result.clusters, output_dir, write_drafts=args.draft)
    _print_status(render_markdown(result.clusters))
    _print_status(
        f"Se escribieron {len(result.clusters)} grupos en {written['markdown']} "
        f"y {written['csv']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
