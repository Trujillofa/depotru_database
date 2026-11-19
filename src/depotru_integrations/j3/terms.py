"""Catalog word dictionary: the words the ERP actually uses in product names.

Customers misspell product words far more often than brands («semento»,
«sikafles», «blnaco»). Refusing the word ends the conversation; naming the word
the catalogue does use turns a typo into a question the customer can confirm.
The vocabulary is built from a bounded read of the article names and cached in
process for an hour — read-only, no credentials beyond the J3 reader the quote
search already uses.
"""

from __future__ import annotations

import re
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, List

MAX_NAMES = 40_000
MIN_TOKEN_LEN = 3
MAX_TOKEN_LEN = 20
MIN_TOKEN_COUNT = 1
SUGGEST_MIN_SCORE = 0.82
CACHE_TTL_SEC = 3600.0

_TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,20}")

# Spanish stopwords and catalogue filler: a typo in these is not worth a turn.
_STOPWORDS = {
    "para",
    "con",
    "sin",
    "por",
    "los",
    "las",
    "del",
    "una",
    "uno",
    "unos",
    "unas",
    "que",
    "como",
    "mas",
    "muy",
    "tipo",
    "cada",
    "sus",
    "este",
    "esta",
    "entre",
    "sobre",
    "hasta",
    "desde",
    "segun",
}

_cache: Dict[str, Any] = {"at": 0.0, "vocabulary": {}}


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _read_names() -> List[str]:
    from business_analyzer.core.database import Database
    from business_analyzer.core.j3system_website_stock import qualified_j3_table

    table = qualified_j3_table("AdmArticulos")
    sql = f"SELECT TOP {MAX_NAMES} ArticulosNombre FROM {table}"
    with Database(suppress_error_details=True) as db:
        rows = db.execute_query(sql)
    names: List[str] = []
    for row in rows or []:
        if isinstance(row, dict):
            name = row.get("ArticulosNombre")
        elif isinstance(row, (list, tuple)) and row:
            name = row[0]
        else:
            continue
        if isinstance(name, str) and name.strip():
            names.append(name)
    return names


def vocabulary() -> Dict[str, int]:
    """Folded word -> how many article names use it. Cached for an hour."""
    fresh = time.monotonic() - float(_cache["at"]) < CACHE_TTL_SEC
    if fresh and _cache["vocabulary"]:
        return dict(_cache["vocabulary"])
    counts: Dict[str, int] = {}
    for name in _read_names():
        for token in _TOKEN_RE.findall(name):
            word = fold(token)
            if len(word) < MIN_TOKEN_LEN or len(word) > MAX_TOKEN_LEN:
                continue
            if word in _STOPWORDS:
                continue
            counts[word] = counts.get(word, 0) + 1
    vocabulary_words = {
        word: count for word, count in counts.items() if count >= MIN_TOKEN_COUNT
    }
    _cache["vocabulary"] = vocabulary_words
    _cache["at"] = time.monotonic()
    return vocabulary_words


def reset_cache() -> None:
    _cache["vocabulary"] = {}
    _cache["at"] = 0.0


def suggest_terms(word: str, limit: int = 3) -> Dict[str, Any]:
    """Catalogue words that look like the one the customer typed."""
    wanted = fold(word).strip()
    if len(wanted) < MIN_TOKEN_LEN:
        return {"query": word, "status": "empty", "suggestions": []}
    try:
        words = vocabulary()
    except Exception:  # noqa: BLE001 — a tool must never crash the inbox
        return {
            "query": word,
            "status": "error",
            "reason": "catalog_unavailable",
            "suggestions": [],
        }
    if wanted in words:
        return {
            "query": word,
            "status": "ok",
            "exact": True,
            "suggestions": [{"term": wanted, "score": 1.0, "products": words[wanted]}],
        }
    scored: List[tuple[float, str]] = []
    for candidate, count in words.items():
        if abs(len(candidate) - len(wanted)) > 3:
            continue
        score = SequenceMatcher(None, wanted, candidate).ratio()
        # Un prefijo solo vale si no se come media palabra: «barila» no es «bari».
        if candidate.startswith(wanted) or (
            wanted.startswith(candidate) and len(candidate) >= len(wanted) - 1
        ):
            score = max(score, 0.95)
        if score >= SUGGEST_MIN_SCORE:
            scored.append((score, candidate))
    scored.sort(key=lambda item: (-round(item[0], 2), -words[item[1]], item[1]))
    suggestions = [
        {"term": candidate, "score": round(score, 3), "products": words[candidate]}
        for score, candidate in scored[: max(1, min(limit, 5))]
    ]
    return {
        "query": word,
        "status": "ok" if suggestions else "empty",
        "exact": False,
        "suggestions": suggestions,
    }
