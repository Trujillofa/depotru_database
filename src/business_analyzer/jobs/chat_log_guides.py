"""Mine assistant chat_log.jsonl for unmatched problem-guide clusters.

Read-only. No network, no LLM, no database, no write SQL. Reuses
``modules.assistant.problem_guides.match_guide`` so assistant routing is
unchanged. Redaction is best-effort; a human must review outputs.
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
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, TextIO

from business_analyzer.core.config import Settings, get_settings
from modules.assistant.problem_guides import match_guide

DEFAULT_LOG_RELATIVE = Path("data/assistant/chat_log.jsonl")
DEFAULT_TOP_N = 10
JACCARD_THRESHOLD = 0.5
CLUSTER_MAX_GROUPS = 2000

MSG_MISSING = (
    "No se encontró el archivo de registro de chat (chat_log.jsonl). "
    "Nada que analizar."
)
MSG_EMPTY = "El registro de chat está vacío. No hay preguntas para analizar."
MSG_NOT_FILE = "La ruta del registro de chat no es un archivo. Nada que analizar."
MSG_ALL_MATCHED = "No hay preguntas sin guía coincidente."
MSG_PERMISSION = "No hay permiso para leer el registro de chat. Nada que analizar."
MSG_BINARY = "El registro de chat parece un archivo binario. Nada que analizar."
MSG_OUTPUT_IS_FILE = "La ruta de salida no es una carpeta. Nada que escribir."
MSG_OUTPUT_PERMISSION = "No hay permiso para escribir en la carpeta de salida."
MSG_SYNTHETIC_NOTE = (
    "Fixture SYNTHETIC: no es un registro real. El top 10 real se obtiene "
    "ejecutando este script contra el chat_log.jsonl privado. La redacción "
    "es de mejor esfuerzo: un humano debe revisar la salida antes de "
    "compartirla o abrir un issue."
)
MSG_BEST_EFFORT = (
    "Redacción de mejor esfuerzo. Un humano debe revisar la salida antes "
    "de compartirla o abrir un issue."
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

_ZERO_WIDTH = dict.fromkeys(
    map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"),
    None,
)
_DASH_TRANS = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\uff0d": "-",
    }
)

# Bounded quantifiers — avoid nested +/+ email/doc backtracking.
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}"
    r"\.[A-Za-z]{2,24}",
    re.I,
)
_OBFUSCATED_AT_RE = re.compile(r"\[at\]|\(at\)", re.I)
_ARROBA_RE = re.compile(r"\s+arroba\s+", re.I)
_OBFUSCATED_DOT_RE = re.compile(r"\[dot\]|\(dot\)", re.I)
_WORD_DOT_RE = re.compile(r"(?<=\w)\s+dot\s+(?=\w)", re.I)
_QUERY_SECRET_RE = re.compile(
    r"(?:[?&]|https?://\S+[?&])(?:token|key|api[_-]?key|secret|"
    r"password|pwd|access[_-]?token)=[^\s&#]{1,256}",
    re.I,
)
_BEARER_RE = re.compile(r"\bBearer\s+\S{6,512}", re.I)
_KV_SECRET_RE = re.compile(
    r"\b(?:password|pwd|api[_-]?key|token|secret|access[_-]?token)"
    r"\s*[:=]\s*\S{1,512}",
    re.I,
)
_GITHUB_RE = re.compile(
    r"\b(?:ghp_[A-Za-z0-9]{8,255}|github_pat_[A-Za-z0-9_]{8,255})\b"
)
_AWS_RE = re.compile(r"\bAKIA[0-9A-Z]{8,20}\b")
_SK_RE = re.compile(r"\b(?:sk-ant-|sk-proj-|sk-|xai-)[A-Za-z0-9_-]{6,512}\b")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_RE = re.compile(
    r"\b(?:[0-9a-f]{1,4}:){1,6}:[0-9a-f]{1,4}\b"
    r"|\b[0-9a-f]{1,4}(?::[0-9a-f]{1,4}){2,7}\b",
    re.I,
)
_LABEL_ID_RE = re.compile(
    r"\b(?:facturas?|fv|remisi[oó]n(?:es)?|pedidos?|orden(?:es)?|nit|cc|"
    r"c[eé]dulas?|pasaportes?|tel(?:[eé]fonos?)?|cel(?:ulares?)?)\b"
    r"[\s:.\-]*"
    r"(?:[A-Za-z]{1,6}[\s.\-])?\d[\d\s.,\-]{0,24}",
    re.I,
)
_NAME_RE = re.compile(
    r"\b(?:me\s+llamo|mi\s+nombre\s+es|soy|cliente)\s+(?:\S+\s+){0,3}\S+",
    re.I,
)
_ADDR_RE = re.compile(
    r"\b(?:calle|carrera|cra|cll|cl|kr|avenida|av\.?|diagonal|"
    r"transversal|trans)\s+[\w#.\-]+(?:\s+[\w#.\-]+){0,6}",
    re.I,
)
_HEX_RE = re.compile(r"\b[0-9a-f]{20,256}\b", re.I)
_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{24,512}={0,2}\b")
_DIGIT_RUN_RE = re.compile(r"\d(?:[\s.,\-/\(\)]*\d){6,}")
_PLACEHOLDER_DUP_RE = re.compile(
    r"\b(email|tel|documento|numero|secreto|nombre|direccion|url)" r"(?:\s+\1)+\b",
    re.I,
)
_UNSAFE_CSV_PREFIX = frozenset({"=", "+", "-", "@", "\t", "\r"})
_MD_SPECIALS = (
    ("`", "'"),
    ("|", "\\|"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ("[", "\\["),
    ("]", "\\]"),
    ("@", "(arroba)"),
    ("#", "n.º"),
)


class ChatLogMineError(Exception):
    """User-facing Spanish error; CLI prints the message and exits."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


def _synthetic_jsonl_line(
    session_id: str,
    message: str,
    *,
    guide_id: Optional[str] = None,
    minute: int = 0,
) -> str:
    record: Dict[str, object] = {
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


def prepare_for_redaction(text: str) -> str:
    """NFKC, strip zero-width chars, normalize dashes/spaces, then obfuscation."""
    value = unicodedata.normalize("NFKC", text or "")
    value = value.translate(_ZERO_WIDTH)
    value = value.translate(_DASH_TRANS)
    value = re.sub(r"[\u00a0\u2000-\u200a\u202f\u205f]", " ", value)
    value = _OBFUSCATED_AT_RE.sub("@", value)
    value = _ARROBA_RE.sub("@", value)
    value = _OBFUSCATED_DOT_RE.sub(".", value)
    value = _WORD_DOT_RE.sub(".", value)
    value = re.sub(r"\s*@\s*", "@", value)
    value = re.sub(r"(?<=\w)\s*\.\s*(?=\w)", ".", value)
    return value


def redact_pii(text: str) -> str:
    """Best-effort PII/secret redaction. A human must still review output."""
    value = prepare_for_redaction(text)
    value = _QUERY_SECRET_RE.sub(" url ", value)
    value = _BEARER_RE.sub(" secreto ", value)
    value = _KV_SECRET_RE.sub(" secreto ", value)
    value = _GITHUB_RE.sub(" secreto ", value)
    value = _AWS_RE.sub(" secreto ", value)
    value = _SK_RE.sub(" secreto ", value)
    value = _EMAIL_RE.sub(" email ", value)
    value = _IPV6_RE.sub(" numero ", value)
    value = _IPV4_RE.sub(" numero ", value)
    value = _LABEL_ID_RE.sub(" documento ", value)
    value = _NAME_RE.sub(" nombre ", value)
    value = _ADDR_RE.sub(" direccion ", value)
    value = _HEX_RE.sub(" secreto ", value)
    value = _B64_RE.sub(" secreto ", value)
    value = _DIGIT_RUN_RE.sub(" numero ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return _PLACEHOLDER_DUP_RE.sub(r"\1", value)


def normalize_question(text: str) -> str:
    value = prepare_for_redaction(text).strip().lower()
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


def escape_markdown(text: str) -> str:
    """Neutralize table breaks, HTML, @mentions and issue-close keywords."""
    value = text or ""
    for src, dest in _MD_SPECIALS:
        value = value.replace(src, dest)
    return value


def cluster_id_for(normalized: str) -> str:
    digest = hashlib.sha256((normalized or "").encode("utf-8")).hexdigest()[:12]
    return f"c{digest}"


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


def _records_from_lines(lines: Iterable[str]) -> tuple[list[QuestionRecord], int]:
    records: list[QuestionRecord] = []
    skipped = 0
    for line in lines:
        if not line.strip():
            skipped += 1
            continue
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
    return records, skipped


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
    records, skipped = _records_from_lines(text.splitlines())
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


def _read_log_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except PermissionError as exc:
        raise ChatLogMineError(MSG_PERMISSION) from exc
    except OSError as exc:
        raise ChatLogMineError(MSG_PERMISSION) from exc


def mine_chat_log(path: Path, *, top: int = DEFAULT_TOP_N) -> MineResult:
    target = Path(path)
    if not target.exists():
        return _empty_result(MSG_MISSING)
    if not target.is_file():
        return _empty_result(MSG_NOT_FILE)
    data = _read_log_bytes(target)
    if b"\x00" in data[:8192]:
        raise ChatLogMineError(MSG_BINARY)
    lines: List[str] = []
    skipped_decode = 0
    for raw in data.splitlines():
        try:
            lines.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            skipped_decode += 1
    if not any(line.strip() for line in lines):
        if skipped_decode:
            return _empty_result(MSG_EMPTY, skipped=skipped_decode)
        return _empty_result(MSG_EMPTY)
    result = mine_chat_log_text("\n".join(lines) + "\n", top=top)
    if skipped_decode:
        return MineResult(
            clusters=result.clusters,
            records_read=result.records_read,
            unmatched=result.unmatched,
            skipped_lines=result.skipped_lines + skipped_decode,
            message=result.message,
            empty=result.empty,
        )
    return result


def cluster_unmatched(
    records: Sequence[QuestionRecord],
    *,
    max_groups: int = CLUSTER_MAX_GROUPS,
) -> list[QuestionCluster]:
    groups: dict[str, list[QuestionRecord]] = {}
    for record in records:
        if record.matched:
            continue
        groups.setdefault(record.normalized, []).append(record)

    pending = sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))
    overflow = pending[max_groups:]
    pending = pending[:max_groups]

    merged: list[list[QuestionRecord]] = []
    merged_tokens: list[frozenset[str]] = []
    token_index: dict[str, list[int]] = defaultdict(list)

    for _normalized, members in pending:
        tokens = members[0].tokens
        candidates: set[int] = set()
        for token in tokens:
            candidates.update(token_index.get(token, ()))
        assigned = False
        for index in sorted(candidates):
            if jaccard(tokens, merged_tokens[index]) >= JACCARD_THRESHOLD:
                merged[index].extend(members)
                merged_tokens[index] = merged_tokens[index] | tokens
                for token in tokens:
                    if index not in token_index[token]:
                        token_index[token].append(index)
                assigned = True
                break
        if not assigned:
            new_index = len(merged)
            merged.append(list(members))
            merged_tokens.append(tokens)
            for token in tokens:
                token_index[token].append(new_index)

    built = [_build_cluster(members) for members in merged]
    built.extend(_build_cluster(members) for _key, members in overflow)
    return built


def _build_cluster(members: Sequence[QuestionRecord]) -> QuestionCluster:
    counts = Counter(item.redacted for item in members)
    representative = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    examples = tuple(
        text
        for text, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if text != representative
    )[:3]
    normalized = normalize_question(representative)
    return QuestionCluster(
        cluster_id=cluster_id_for(normalized),
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
        MSG_BEST_EFFORT,
        "",
        "Solo texto redactado. No incluye `session_id` ni respuestas.",
        "",
        "| # | Conteo | Representativa (redactada) | Ejemplos |",
        "|---|--------|----------------------------|----------|",
    ]
    if not clusters:
        lines.append("| — | 0 | — | — |")
        return "\n".join(lines) + "\n"
    for index, cluster in enumerate(clusters, start=1):
        examples = (
            "; ".join(escape_markdown(item) for item in cluster.examples)
            if cluster.examples
            else "—"
        )
        lines.append(
            f"| {index} | {cluster.count} | "
            f"{escape_markdown(cluster.representative)} | {examples} |"
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
    return "g" + hashlib.sha256((normalized or "").encode("utf-8")).hexdigest()[:10]


def render_draft_guide(cluster: QuestionCluster) -> str:
    guide_id = _proposed_guide_id(cluster.normalized)
    title = cluster.representative
    if title.lower().startswith("synthetic:"):
        title = title.split(":", 1)[1].strip()
    title = title[:1].upper() + title[1:] if title else "Sin título"
    escaped = re.escape(normalize_question(cluster.representative))
    examples = (
        "\n".join(f"- {escape_markdown(item)}" for item in cluster.examples)
        or "- (sin otros)"
    )
    return (
        f"# Guía (borrador): {escape_markdown(title)}\n\n"
        "**Estado:** BORRADOR — no publicar, no crear issue automáticamente.\n"
        f"**Origen:** minería de chat_log.jsonl (conteo {cluster.count}).\n"
        f"**id propuesto:** `{guide_id}`\n\n"
        f"{MSG_BEST_EFFORT}\n\n"
        "## Pregunta representativa (redactada)\n\n"
        f"{escape_markdown(cluster.representative)}\n\n"
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
        "src/modules/assistant/problem_guides.py a mano. Este archivo no se "
        "publica solo.\n"
    )


def render_draft_issue_body(cluster: QuestionCluster) -> str:
    guide_id = _proposed_guide_id(cluster.normalized)
    return (
        f"# Borrador de guía: `{guide_id}`\n\n"
        "**Estado:** BORRADOR — no crear este issue automáticamente; no publicar.\n"
        "Parte de issue 65 (Phase 3c). Plantilla: "
        "docs/reference/problem-guide-template.md.\n\n"
        f"{MSG_BEST_EFFORT}\n\n"
        f"**Conteo (redactado):** {cluster.count}\n\n"
        "## Pregunta representativa (redactada)\n\n"
        f"{escape_markdown(cluster.representative)}\n\n"
        "Incluye una lista de necesidades para el cliente. "
        "Un humano decide si abre el issue y si incorpora la guía.\n"
    )


def _safe_filename(cluster_id: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", cluster_id.lower()).strip("_")
    return (cleaned or "cluster")[:80]


def _clear_stale_drafts(output_dir: Path) -> None:
    for stale in output_dir.glob("borrador_*.md"):
        try:
            stale.unlink()
        except OSError as exc:
            raise ChatLogMineError(MSG_OUTPUT_PERMISSION) from exc


def write_outputs(
    clusters: Sequence[QuestionCluster],
    output_dir: Path,
    *,
    write_drafts: bool = False,
) -> dict[str, Path]:
    if output_dir.exists() and output_dir.is_file():
        raise ChatLogMineError(MSG_OUTPUT_IS_FILE)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ChatLogMineError(MSG_OUTPUT_PERMISSION) from exc
    _clear_stale_drafts(output_dir)
    written: dict[str, Path] = {}
    md_path = output_dir / "unmatched_question_clusters.md"
    csv_path = output_dir / "unmatched_question_clusters.csv"
    try:
        md_path.write_text(render_markdown(clusters), encoding="utf-8")
        csv_path.write_text(render_csv(clusters), encoding="utf-8-sig")
    except OSError as exc:
        raise ChatLogMineError(MSG_OUTPUT_PERMISSION) from exc
    written["markdown"] = md_path
    written["csv"] = csv_path
    if write_drafts:
        for cluster in clusters:
            stem = _safe_filename(cluster.cluster_id)
            guide_path = output_dir / f"borrador_guia_{stem}.md"
            issue_path = output_dir / f"borrador_issue_{stem}.md"
            try:
                guide_path.write_text(render_draft_guide(cluster), encoding="utf-8")
                issue_path.write_text(
                    render_draft_issue_body(cluster), encoding="utf-8"
                )
            except OSError as exc:
                raise ChatLogMineError(MSG_OUTPUT_PERMISSION) from exc
            written[f"guide_{stem}"] = guide_path
            written[f"issue_{stem}"] = issue_path
    return written


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analiza el registro de chat (chat_log.jsonl) y lista las "
            "preguntas sin guía coincidente. Solo lectura. No publica guías "
            "ni crea issues. La redacción es de mejor esfuerzo."
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


def _grupo_word(count: int) -> str:
    return "grupo" if count == 1 else "grupos"


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
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
    except ChatLogMineError as exc:
        _print_status(exc.message)
        return exc.exit_code
    _print_status(render_markdown(result.clusters))
    _print_status(MSG_BEST_EFFORT)
    count = len(result.clusters)
    _print_status(
        f"Se escribieron {count} {_grupo_word(count)} en "
        f"{written['markdown']} y {written['csv']}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
