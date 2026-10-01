"""Mine assistant chat_log.jsonl for unmatched problem-guide clusters.

Read-only. No network, no LLM, no database, no write SQL. Reuses
``modules.assistant.problem_guides.match_guide`` so assistant routing is
unchanged. Display is default-deny (allowlist) plus best-effort regex
redaction; a human must review outputs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import logging
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, TextIO

from business_analyzer.core.config import Settings, read_assistant_chat_log
from modules.assistant.problem_guides import match_guide

DEFAULT_LOG_RELATIVE = Path("data/assistant/chat_log.jsonl")
DEFAULT_TOP_N = 10
JACCARD_THRESHOLD = 0.5
CLUSTER_MAX_GROUPS = 2000
MAX_MSG_CHARS = 800
MAX_REDACT_CHARS = 20000
MAX_LINE_BYTES = 4096
_GENERATED_DRAFT_RE = re.compile(r"^borrador_(?:guia|issue)_c[a-z]{12}\.md$")
_ALLOWLIST_PATH = Path(__file__).with_name("chat_log_guides_allowlist.txt")
_ALPHA = "abcdefghijklmnopqrstuvwxyz"
_LETTER_TOKEN_RE = re.compile(r"[a-z]+")

MSG_MISSING = (
    "No se encontró el archivo de registro de chat (chat_log.jsonl). "
    "Nada que analizar."
)
MSG_EMPTY = "El registro de chat está vacío. No hay preguntas para analizar."
MSG_LONG_LINES = (
    "Hay líneas que superan el límite y no se pudieron usar. " "Nada que analizar."
)
MSG_NOT_FILE = "La ruta del registro de chat no es un archivo. Nada que analizar."
MSG_ALL_MATCHED = "No hay preguntas sin guía coincidente."
MSG_PERMISSION = "No hay permiso para leer el registro de chat. Nada que analizar."
MSG_BINARY = "El registro de chat parece un archivo binario. Nada que analizar."
MSG_OUTPUT_IS_FILE = "La ruta de salida no es una carpeta. Nada que escribir."
MSG_OUTPUT_PERMISSION = "No hay permiso para escribir en la carpeta de salida."
MSG_OUTPUT_COLLISION_DIR = (
    "Hay una carpeta en el camino del archivo de salida. Nada que escribir."
)
MSG_SYNTHETIC_NOTE = (
    "Fixture SYNTHETIC: no es un registro real. El top 10 real se obtiene "
    "ejecutando este script contra el chat_log.jsonl privado. La redacción "
    "es de mejor esfuerzo: un humano debe revisar la salida antes de "
    "compartirla o abrir un issue."
)
MSG_BEST_EFFORT = (
    "Redacción de mejor esfuerzo (lista blanca + regex). Un humano debe "
    "revisar la salida antes de compartirla o abrir un issue."
)
MSG_ALLOWLIST_MISSING = (
    "No se encontró el archivo de lista blanca (%s). "
    "Se usa solo el vocabulario mínimo."
)

logger = logging.getLogger(__name__)

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

_PLACEHOLDER_WORDS = frozenset(
    {
        "email",
        "tel",
        "documento",
        "numero",
        "secreto",
        "nombre",
        "direccion",
        "url",
        "ref",
        "pregunta",
        "x",
    }
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

# Bounded quantifiers — collapse whitespace first; avoid nested +/+ backtracking.
_EMAIL_RE = re.compile(
    r"(?<![\w.%+-])[\w.%+-]{1,64}@[\w.-]{1,253}[.,][\w]{2,24}",
    re.I,
)
_OBFUSCATED_AT_RE = re.compile(r"\[(?:at|arroba)\]|\((?:at|arroba)\)", re.I)
_ARROBA_RE = re.compile(r"\s+(?:arroba|at)\s+", re.I)
_UNDERSCORE_ARROBA_RE = re.compile(r"_arroba_", re.I)
_OBFUSCATED_DOT_RE = re.compile(r"\[(?:dot|punto)\]|\((?:dot|punto)\)", re.I)
_WORD_DOT_RE = re.compile(r"(?<=\w)\s+(?:dot|punto)\s+(?=\w)", re.I)
_URL_RE = re.compile(r"(?:https?://|www\.)[^\s<>\"']{1,512}", re.I)
_QUERY_SECRET_RE = re.compile(
    r"(?:[?&]|https?://\S+[?&])(?:token|key|api[_-]?key|apikey|secret|"
    r"password|pwd|pass|auth|sig|code|session|sid|client_secret|"
    r"refresh_token|access[_-]?token)=[^\s&#]{1,256}",
    re.I,
)
_BEARER_RE = re.compile(r"\bBearer\s+\S{6,512}", re.I)
_BASIC_RE = re.compile(r"\bBasic\s+[A-Za-z0-9+/]{8,512}={0,2}")
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{4,512}\.[A-Za-z0-9_-]{4,512}\.[A-Za-z0-9_-]{4,512}\b"
)
_PASSWORD_RE = re.compile(
    r"(?:contrase[nñ]a|password|passwd|pwd|psw|db_password|"
    r"apikey|api[_-]?key|token(?:\s+de\s+acceso)?|clave\s+de\s+acceso|"
    r"c[oó]digo\s+de\s+verificaci[oó]n|mi\s+pin\s+es)\s*"
    r"(?:es|[:=])?\s*\S{1,256}"
    r"|clave\s*(?:es|[:=])\s*\S{1,256}"
    r"|[\"']password[\"']\s*:\s*[\"'][^\"']{1,256}[\"']",
    re.I,
)
_PIN_OTP_RE = re.compile(r"\b(?:pin|otp|cvv|cvc)\b\s*[:=]?\s*\S{2,16}", re.I)
_PASSPHRASE_LABEL_RE = re.compile(
    r"\b(?:"
    r"clave|contrase[nñ]a|password|passwd|pwd|psw|passphrase|"
    r"pin|otp|pass|c[oó]digo\s+secreto|token\s+secreto"
    r")\b",
    re.I,
)
_PASSPHRASE_SEP = frozenset(" \t,.:-=…")
_SENTENCE_END = frozenset(".!?\n")
_DIGIT_WORD = r"(?:cero|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve)"
_DIGIT_WORD_RUN_RE = re.compile(
    rf"\b{_DIGIT_WORD}(?:\s+{_DIGIT_WORD}){{2,}}\b",
    re.I,
)
_KV_SECRET_RE = re.compile(
    r"\b(?:password|pwd|psw|api[_-]?key|apikey|token|secret|access[_-]?token)"
    r"\s*[:=]\s*\S{1,512}",
    re.I,
)
_KEY_PREFIX_RE = re.compile(
    r"\b(?:sk_live_|sk_test_|pk_live_|pk_test_|rk_live_|gho_|ghs_|ghu_|"
    r"ghp_|github_pat_|sk-ant-|sk-proj-|sk-|xai-|xoxp-|xoxb-|"
    r"glpat-|npm_|dop_v1_|shpat_)"
    r"[A-Za-z0-9_-]{4,512}\b"
    r"|SG\.[A-Za-z0-9_-]{4,512}"
)
_AWS_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{8,20}\b")
_CONN_RE = re.compile(
    r"(?:AccountKey|SharedAccessKey|DefaultEndpointsProtocol)\s*=\s*\S{1,512}",
    re.I,
)
_DB_URI_RE = re.compile(
    r"(?:postgres(?:ql)?|mssql|mysql|sqlserver|mongodb)://\S{1,512}",
    re.I,
)
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6_RE = re.compile(
    r"(?<![\da-f:])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\da-f:])",
    re.I,
)
_MAC_RE = re.compile(
    r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b|\b[0-9a-f]{2}(?:-[0-9a-f]{2}){5}\b",
    re.I,
)
_LABEL_ID_RE = re.compile(
    r"\b(?:"
    r"facturas?|factura\s+no\.?|fv|fe|fed|oc|gu[ií]as?|"
    r"remisi[oó]n(?:es)?|remision\s+no\.?|pedidos?|orden(?:es)?|"
    r"nit|rut|ruc|dni|cc|c\.?\s*c\.?|ce|ti|"
    r"c[eé]dulas?(?:\s+de\s+ciudadan[ií]a)?|pasaportes?|"
    r"tel(?:[eé]fonos?)?|cel(?:ulares?)?|cuentas?"
    r")\b"
    r"[\s:.#\-]*"
    r"(?:[A-Za-z]{1,6}[\s.\-])?\d[\d\s.,\-]{0,24}",
    re.I,
)
_DOC_CODE_RE = re.compile(r"\b(?:FV|FE|FED|OC|CC|CE|TI|NIT)-\d{1,12}\b", re.I)
_GH_REF_RE = re.compile(r"\bGH-\d{1,8}\b", re.I)
_NAME_INTRO_RE = re.compile(
    r"\b(?:me\s+llamo|mi\s+nombre\s+es|a\s+nombre\s+de)\s+" r"(?:\S+\s+){0,3}\S+",
    re.I,
)
_NAME_TITLE_RE = re.compile(
    r"\b(?:[Ss]r\.?|[Ss]ra\.?|[Dd]oña|[Dd]ona|[Dd]on|[Ss]e[nñ]or|"
    r"[Ss]e[nñ]ora|[Dd]r\.?|[Dd]ra\.?|[Ii]ng\.?|[Ll]ic\.?)\s+"
    r"[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü]+"
    r"(?:\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü]+){0,3}"
)
_NAME_SOY_RE = re.compile(
    r"\b[Ss]oy\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü]+"
    r"(?:\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü]+){0,3}"
)
_NAME_CLIENTE_RE = re.compile(
    r"\b[Cc]liente\s*:\s*(?:\S+\s+){0,3}\S+"
    r"|\b[Cc]liente\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü]+"
    r"(?:\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü]+){0,3}"
)
_NAME_HABLA_RE = re.compile(
    r"\b(?:[Hh]abla|[Aa]tiende|[Aa]tendido\s+por|[Aa]tendida\s+por)\s+"
    r"[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü]+"
    r"(?:\s+[A-ZÁÉÍÓÚÑÜ][\wÁÉÍÓÚÑÜáéíóúñü]+){0,3}"
)
_ADDR_RE = re.compile(
    r"\b(?:calle|cll\.?|cl\.?|carrera|cra\.?|kra|kr\.?|avenida|av\.?|"
    r"diagonal|diag\.?|transversal|trans\.?|tv\.?|apto\.?|apartamento|"
    r"torre|casa|barrio|manzana|mz|conjunto|cs)\s+"
    r"[\w#.\-]*\d[\w#.\-]*(?:\s+[\w#.\-]*\d[\w#.\-]*){0,5}",
    re.I,
)
_HEX_RE = re.compile(r"\b[0-9a-f]{20,256}\b", re.I)
_B64_RE = re.compile(r"\b[A-Za-z0-9+/]{24,512}={0,2}\b")
_GROUP_PHONE_RE = re.compile(r"\b\d{1,4}(?:[\s\-]\d{1,4}){2,5}\b")
_SHORT_PHONE_RE = re.compile(r"\b\d{3,4}[\s\-]\d{3,4}\b")
_CARD_SEP_RE = re.compile(r"\b\d{4}(?:[\s\-]\d{4}){2,4}\b")
_CARD_CONTIG_RE = re.compile(r"\b\d{13,19}\b")
_MOBILE10_RE = re.compile(r"(?<!\d)(?:\+?57)?3\d{9}(?!\d)")
_NIT9_RE = re.compile(r"(?<!\d)\d{9}(?!\d)")
_DOTTED_GROUP_RE = re.compile(r"(?<!\d)\d{1,4}(?:[./]\d{1,4}){1,6}(?:-?\d{1,4})?(?!\d)")
_DIGIT_SEP_RUN_RE = re.compile(r"\+?\d(?:[\s.\-/]*\d){6,18}")
_PLACEHOLDER_DUP_RE = re.compile(
    r"\b(email|tel|documento|numero|secreto|nombre|direccion|url|ref)" r"(?:\s+\1)+\b",
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
    displayed: str
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


def _strip_invisible(text: str) -> str:
    """Drop Cf, combining marks, CGJ and variation selectors after NFKC."""
    out: list[str] = []
    for char in text:
        code = ord(char)
        category = unicodedata.category(char)
        if category in {"Cf", "Mn"}:
            continue
        if code == 0x034F or 0xFE00 <= code <= 0xFE0F:
            continue
        out.append(char)
    return "".join(out)


def fold_letters(text: str) -> str:
    """NFKC, strip format marks, lowercase, fold accents to ASCII letters."""
    value = unicodedata.normalize("NFKC", text or "")
    value = _strip_invisible(value)
    value = "".join(
        char
        for char in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(char) != "Mn"
    )
    return value


def load_allowlist(path: Optional[Path] = None) -> frozenset[str]:
    """Load the human-editable display allowlist (letters-only words)."""
    words = set(STOPWORDS) | set(_PLACEHOLDER_WORDS)
    target = path if path is not None else _ALLOWLIST_PATH
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        logger.warning(MSG_ALLOWLIST_MISSING, target)
        return frozenset(words)
    for line in text.splitlines():
        raw = line.split("#", 1)[0].strip().lower()
        if not raw:
            continue
        folded = fold_letters(raw)
        if _LETTER_TOKEN_RE.fullmatch(folded):
            words.add(folded)
    return frozenset(words)


ALLOWLIST = load_allowlist()


def project_for_display(
    text: str,
    allowlist: Optional[frozenset[str]] = None,
) -> str:
    """Keep only allowlisted lowercase letter-words. Digits are never emitted."""
    vocab = ALLOWLIST if allowlist is None else allowlist
    folded = fold_letters(text)
    kept = [token for token in _LETTER_TOKEN_RE.findall(folded) if token in vocab]
    displayed = collapse_digit_word_runs(" ".join(kept))
    if len(displayed) > MAX_MSG_CHARS:
        displayed = displayed[:MAX_MSG_CHARS]
        if " " in displayed:
            displayed = displayed.rsplit(" ", 1)[0]
    return displayed.strip()


def prepare_for_redaction(text: str, *, keep_newlines: bool = False) -> str:
    """Collapse whitespace first, then NFKC, strip format marks, deobfuscate."""
    if not text:
        return ""
    if keep_newlines:
        value = text.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"[^\S\n]+", " ", value)
        value = re.sub(r"\n+", "\n", value).strip()
    else:
        value = re.sub(r"\s+", " ", text).strip()
    if len(value) > MAX_REDACT_CHARS:
        value = value[:MAX_REDACT_CHARS]
    value = unicodedata.normalize("NFKC", value)
    value = _strip_invisible(value)
    value = value.translate(_DASH_TRANS)
    value = _UNDERSCORE_ARROBA_RE.sub("@", value)
    value = _OBFUSCATED_AT_RE.sub("@", value)
    value = _ARROBA_RE.sub("@", value)
    value = _OBFUSCATED_DOT_RE.sub(".", value)
    value = _WORD_DOT_RE.sub(".", value)
    value = re.sub(r"\s*@\s*", "@", value)
    value = re.sub(r"(?<=[a-záéíóúñ])[^\S\n]*\.[^\S\n]*(?=[a-záéíóúñ])", ".", value)
    if keep_newlines:
        return re.sub(r"[^\S\n]+", " ", value).strip()
    return re.sub(r"\s+", " ", value).strip()


def collapse_digit_word_runs(text: str) -> str:
    """Replace 3+ consecutive Spanish digit-words with ``numero``."""
    value = _DIGIT_WORD_RUN_RE.sub(" numero ", text or "")
    return re.sub(r"\s+", " ", value).strip()


def _redact_labeled_passphrases(text: str) -> str:
    """Redact from a secret label through the end of the sentence."""
    if not text:
        return ""
    pieces: list[str] = []
    pos = 0
    for match in _PASSPHRASE_LABEL_RE.finditer(text):
        if match.start() < pos:
            continue
        cursor = match.end()
        while cursor < len(text) and text[cursor] in _PASSPHRASE_SEP:
            cursor += 1
        if cursor >= len(text) or text[cursor] in _SENTENCE_END:
            continue
        stop = len(text)
        for index in range(cursor, len(text)):
            if text[index] in _SENTENCE_END:
                stop = index
                break
        pieces.append(text[pos : match.start()])
        pieces.append(" secreto ")
        pos = stop
    pieces.append(text[pos:])
    return "".join(pieces)


def _redact_digit_run(match: re.Match[str]) -> str:
    raw = match.group(0)
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("57") and len(digits) >= 12:
        digits = digits[2:]
        raw_has_sep = True
    else:
        raw_has_sep = any(char in raw for char in "./-+")
    if len(digits) == 10 and digits.startswith("3"):
        return " tel "
    if len(digits) == 9:
        return " documento "
    if 13 <= len(digits) <= 19:
        return " numero "
    if raw_has_sep and len(digits) >= 7:
        return " numero "
    return raw


def _redact_phone_like(text: str) -> str:
    def _if_long(match: re.Match[str]) -> str:
        digits = re.sub(r"\D", "", match.group(0))
        return " numero " if len(digits) >= 7 else match.group(0)

    value = _CARD_SEP_RE.sub(_if_long, text)
    value = _GROUP_PHONE_RE.sub(_if_long, value)
    value = _SHORT_PHONE_RE.sub(_if_long, value)
    value = _CARD_CONTIG_RE.sub(" numero ", value)
    value = _DOTTED_GROUP_RE.sub(" numero ", value)
    value = _DIGIT_SEP_RUN_RE.sub(_redact_digit_run, value)
    value = _MOBILE10_RE.sub(" tel ", value)
    value = _NIT9_RE.sub(" documento ", value)
    return value


def redact_pii(text: str) -> str:
    """Best-effort PII/secret redaction. A human must still review output."""
    value = prepare_for_redaction(text, keep_newlines=True)
    value = re.sub(r"\((\d+)\)", r"\1", value)
    value = _URL_RE.sub(" url ", value)
    value = _QUERY_SECRET_RE.sub(" url ", value)
    value = _BEARER_RE.sub(" secreto ", value)
    value = _BASIC_RE.sub(" secreto ", value)
    value = _JWT_RE.sub(" secreto ", value)
    value = _redact_labeled_passphrases(value)
    value = _PASSWORD_RE.sub(" secreto ", value)
    value = _PIN_OTP_RE.sub(" secreto ", value)
    value = _KV_SECRET_RE.sub(" secreto ", value)
    value = _KEY_PREFIX_RE.sub(" secreto ", value)
    value = _AWS_RE.sub(" secreto ", value)
    value = _CONN_RE.sub(" secreto ", value)
    value = _DB_URI_RE.sub(" secreto ", value)
    value = _UUID_RE.sub(" secreto ", value)
    value = _EMAIL_RE.sub(" email ", value)
    value = _IPV6_RE.sub(" numero ", value)
    value = _IPV4_RE.sub(" numero ", value)
    value = _MAC_RE.sub(" numero ", value)
    value = _LABEL_ID_RE.sub(" documento ", value)
    value = _DOC_CODE_RE.sub(" documento ", value)
    value = _GH_REF_RE.sub(" ref ", value)
    value = _NAME_INTRO_RE.sub(" nombre ", value)
    value = _NAME_TITLE_RE.sub(" nombre ", value)
    value = _NAME_SOY_RE.sub(" nombre ", value)
    value = _NAME_CLIENTE_RE.sub(" nombre ", value)
    value = _NAME_HABLA_RE.sub(" nombre ", value)
    value = _ADDR_RE.sub(" direccion ", value)
    value = _HEX_RE.sub(" secreto ", value)
    value = _B64_RE.sub(" secreto ", value)
    value = _redact_phone_like(value)
    value = collapse_digit_word_runs(value)
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
    """Neutralize table breaks, HTML, URLs, @mentions and issue-close keywords."""
    value = text or ""
    value = _URL_RE.sub("url", value)
    value = _GH_REF_RE.sub("ref", value)
    for src, dest in _MD_SPECIALS:
        value = value.replace(src, dest)
    return value


def _letters_hash(text: str, length: int) -> str:
    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    number = int.from_bytes(digest, "big")
    chars: list[str] = []
    for _ in range(length):
        chars.append(_ALPHA[number % 26])
        number //= 26
    return "".join(chars)


def cluster_id_for(displayed: str) -> str:
    """Stable letters-only id from the allowlisted projection (no digits)."""
    return "c" + _letters_hash(displayed, 12)


def resolve_log_path(
    explicit: Optional[Path] = None,
    settings: Optional[Settings] = None,
) -> Path:
    if explicit is not None and str(explicit).strip():
        return Path(explicit).expanduser()
    if settings is not None:
        configured = (settings.ASSISTANT_CHAT_LOG or "").strip()
    else:
        configured = (read_assistant_chat_log() or "").strip()
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
    displayed = project_for_display(redacted)
    if not displayed:
        displayed = "pregunta"
    normalized = normalize_question(redacted)
    if not normalized:
        return None
    matched = guide_id is not None or match_guide(message) is not None
    return QuestionRecord(
        message=message,
        redacted=redacted,
        displayed=displayed,
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
    skipped_overlong = 0
    for raw in data.splitlines():
        if len(raw) > MAX_LINE_BYTES:
            skipped_overlong += 1
            continue
        try:
            lines.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            skipped_decode += 1
    skipped_extra = skipped_decode + skipped_overlong
    if not any(line.strip() for line in lines):
        if skipped_overlong:
            return _empty_result(MSG_LONG_LINES, skipped=skipped_extra)
        if skipped_decode:
            return _empty_result(MSG_EMPTY, skipped=skipped_decode)
        return _empty_result(MSG_EMPTY)
    records, skipped = _records_from_lines(lines)
    unmatched = [row for row in records if not row.matched]
    if not unmatched:
        return MineResult(
            clusters=(),
            records_read=len(records),
            unmatched=0,
            skipped_lines=skipped + skipped_extra,
            message=MSG_ALL_MATCHED if records else MSG_EMPTY,
            empty=True,
        )
    clusters = top_unmatched_clusters(cluster_unmatched(unmatched), n=top)
    return MineResult(
        clusters=tuple(clusters),
        records_read=len(records),
        unmatched=len(unmatched),
        skipped_lines=skipped + skipped_extra,
        message="",
        empty=False,
    )


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
    return _unique_cluster_ids(built)


def _unique_cluster_ids(
    clusters: Sequence[QuestionCluster],
) -> list[QuestionCluster]:
    """Keep ``cluster_id`` unique when two groups project to the same text."""
    used: set[str] = set()
    next_nonce: dict[tuple[str, str], int] = {}
    unique: list[QuestionCluster] = []
    for cluster in clusters:
        cid = cluster.cluster_id
        if cid not in used:
            used.add(cid)
            unique.append(cluster)
            continue
        key = (cluster.representative, cluster.normalized)
        nonce = next_nonce.get(key, 0) + 1
        cid = cluster_id_for(f"{cluster.representative}\n{cluster.normalized}\n{nonce}")
        while cid in used:
            nonce += 1
            cid = cluster_id_for(
                f"{cluster.representative}\n{cluster.normalized}\n{nonce}"
            )
        next_nonce[key] = nonce
        used.add(cid)
        unique.append(
            QuestionCluster(
                cluster_id=cid,
                count=cluster.count,
                representative=cluster.representative,
                examples=cluster.examples,
                normalized=cluster.normalized,
            )
        )
    return unique


def _build_cluster(members: Sequence[QuestionRecord]) -> QuestionCluster:
    counts = Counter(item.displayed for item in members)
    representative = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
    examples = tuple(
        text
        for text, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        if text != representative
    )[:3]
    normalized = normalize_question(representative)
    return QuestionCluster(
        cluster_id=cluster_id_for(representative),
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
        "Solo texto de la lista blanca. No incluye `session_id` ni respuestas.",
        "",
        "| # | Conteo | Representativa (lista blanca) | Ejemplos |",
        "|---|--------|-------------------------------|----------|",
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


def _proposed_guide_id(displayed: str) -> str:
    return "g" + _letters_hash(displayed, 10)


def render_draft_guide(cluster: QuestionCluster) -> str:
    guide_id = _proposed_guide_id(cluster.representative)
    title = cluster.representative
    if title.lower().startswith("synthetic"):
        title = title.split("synthetic", 1)[-1].strip()
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
        "## Pregunta representativa (lista blanca)\n\n"
        f"{escape_markdown(cluster.representative)}\n\n"
        "## Otras formulaciones (lista blanca)\n\n"
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
    guide_id = _proposed_guide_id(cluster.representative)
    return (
        f"# Borrador de guía: `{guide_id}`\n\n"
        "**Estado:** BORRADOR — no crear este issue automáticamente; no publicar.\n"
        "Parte de issue 65 (Phase 3c). Plantilla: "
        "docs/reference/problem-guide-template.md.\n\n"
        f"{MSG_BEST_EFFORT}\n\n"
        f"**Conteo (lista blanca):** {cluster.count}\n\n"
        "## Pregunta representativa (lista blanca)\n\n"
        f"{escape_markdown(cluster.representative)}\n\n"
        "Incluye una lista de necesidades para el cliente. "
        "Un humano decide si abre el issue y si incorpora la guía.\n"
    )


def _safe_filename(cluster_id: str) -> str:
    cleaned = re.sub(r"[^a-z_]+", "_", cluster_id.lower()).strip("_")
    return (cleaned or "cluster")[:80]


def _is_generated_draft_file(path: Path) -> bool:
    if not _GENERATED_DRAFT_RE.fullmatch(path.name):
        return False
    try:
        if path.is_symlink():
            return False
        return path.is_file()
    except OSError:
        return False


def _clear_generated_drafts(output_dir: Path) -> None:
    """Remove only regular files named like this tool's drafts. Never glob users."""
    try:
        entries = list(output_dir.iterdir())
    except OSError as exc:
        raise ChatLogMineError(MSG_OUTPUT_PERMISSION) from exc
    for entry in entries:
        if not _is_generated_draft_file(entry):
            continue
        try:
            entry.unlink()
        except OSError:
            continue


def _replace_output_file(path: Path, content: str, encoding: str) -> None:
    """Write a new regular file. Never follow a generated-name symlink."""
    try:
        if path.is_symlink():
            path.unlink()
        elif path.exists() and path.is_dir():
            raise ChatLogMineError(MSG_OUTPUT_COLLISION_DIR)
        path.write_text(content, encoding=encoding)
    except ChatLogMineError:
        raise
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
    if write_drafts:
        _clear_generated_drafts(output_dir)
    written: dict[str, Path] = {}
    md_path = output_dir / "unmatched_question_clusters.md"
    csv_path = output_dir / "unmatched_question_clusters.csv"
    _replace_output_file(md_path, render_markdown(clusters), "utf-8")
    _replace_output_file(csv_path, render_csv(clusters), "utf-8-sig")
    written["markdown"] = md_path
    written["csv"] = csv_path
    if write_drafts:
        for cluster in clusters:
            stem = _safe_filename(cluster.cluster_id)
            guide_path = output_dir / f"borrador_guia_{stem}.md"
            issue_path = output_dir / f"borrador_issue_{stem}.md"
            _replace_output_file(guide_path, render_draft_guide(cluster), "utf-8")
            _replace_output_file(issue_path, render_draft_issue_body(cluster), "utf-8")
            written[f"guide_{stem}"] = guide_path
            written[f"issue_{stem}"] = issue_path
    return written


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Analiza el registro de chat (chat_log.jsonl) y lista las "
            "preguntas sin guía coincidente. Solo lectura. No publica "
            "guías ni crea issues. La salida usa lista blanca (mejor "
            "esfuerzo)."
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
