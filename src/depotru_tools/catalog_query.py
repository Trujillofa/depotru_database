"""Parameterized hybrid J3 name/SKU predicates (no synonym correction).

Keep query policy separate from the price/IVA/warehouse SQL builder. Phrase
matches are a ranking shortcut only: they must satisfy the same token guards.
"""

from __future__ import annotations

import re
import unicodedata

_NOISE = frozenset(
    "precio precios valor cuesta cuanto vale de del la el los las un una unos "
    "unas por para con x y en".split()
)
_MATERIALS = frozenset(
    "pvc cpvc ppr pead polietileno cobre bronce acero galvanizado inoxidable "
    "aluminio hierro plastico".split()
)


def normalize(text: str) -> str:
    return "".join(
        c
        for c in unicodedata.normalize("NFD", text.casefold())
        if not unicodedata.combining(c)
    )


def query_tokens(query: str) -> list[str]:
    """Retain fractions, SKU punctuation and literal LIKE metacharacters."""
    # A slash joins a numeric fraction only; elsewhere it is an NL separator.
    cleaned = re.sub(r"(?<!\d)/|/(?!\d)", " ", normalize(query))
    return list(
        dict.fromkeys(
            t
            for raw in re.split(r"[\s+,]+", cleaned)
            if (t := raw.strip(".,;:¿?¡!\"'()")) and t not in _NOISE
        )
    )


def escape_like(text: str) -> str:
    # ESCAPE is portable to SQL Server and SQLite; '[' is special on SQL Server.
    return "".join("!" + c if c in "!%_[" else c for c in text)


def _normalized_name() -> str:
    expr = "a.ArticulosNombre"
    for source, target in zip("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNaeiouun"):
        expr = f"REPLACE({expr}, '{source}', '{target}')"
    return f"LOWER({expr})"


def _bounded_name(name: str, dialect: str) -> str:
    # Slash is deliberately NOT a delimiter: 1/2 != 11/2, 1/256 or 1/2/3.
    for c in ('"', "'", "(", ")", ",", ";", ":", "-", "_", "\t", "\n", "\r"):
        literal = c.replace("'", "''")
        name = f"REPLACE({name}, '{literal}', ' ')"
    if dialect == "sqlite":
        return f"(' ' || {name} || ' ')"
    return f"CONCAT(' ', {name}, ' ')"


def quote_search_statement(
    query: str, *, limit: int = 6, phrase: bool = False, dialect: str = "tsql"
) -> tuple[str, tuple[str, ...]]:
    """Build a safe WHERE over the unchanged J3 price/stock projection."""
    from business_analyzer.core.j3system_website_stock import build_quote_search_sql

    tokens = query_tokens(query)
    sql = build_quote_search_sql(limit=limit, dialect=dialect)
    placeholder = "?" if dialect == "sqlite" else "%s"
    original = (
        f"(a.ArticulosNombre LIKE {placeholder} "
        f"OR a.ArticulosCodigo LIKE {placeholder})"
    )
    if sql.count(original) != 1:
        raise RuntimeError("unrecognized quote-search predicate")
    if not tokens:
        return sql.replace(original, "1 = 0", 1), ()
    name = _normalized_name()
    bounded = _bounded_name(name, dialect)
    clauses, params = [], []
    for token in tokens:
        protected = bool(re.search(r"\d", token)) or token in _MATERIALS
        expr = bounded if protected else name
        pattern = (
            f"% {escape_like(token)} %" if protected else f"%{escape_like(token)}%"
        )
        clause = f"{expr} LIKE {placeholder} ESCAPE '!'"
        params.append(pattern)
        # Catalog weights often omit the space (50KG). Accept only explicit
        # unit suffixes, not arbitrary digits/letters or a substring of a SKU.
        if token.isdecimal():
            unit_clauses = [clause]
            for unit in ("kg", "kl", "gr", "g", "ml", "lt", "mm", "cm", "mts"):
                unit_clauses.append(f"{bounded} LIKE {placeholder} ESCAPE '!'")
                params.append(f"% {escape_like(token)}{unit} %")
            clause = "(" + " OR ".join(unit_clauses) + ")"
        # An explicit code is exact, never a substring rescue for a dimension.
        sku_like = bool(
            re.fullmatch(
                r"\d{6,}|(?=[a-z0-9_-]*[a-z])(?=[a-z0-9_-]*\d)[a-z0-9_-]+",
                token,
            )
        )
        sku_like = sku_like or (token.isalpha() and token not in _MATERIALS)
        if sku_like:
            clause = f"({clause} OR LOWER(a.ArticulosCodigo) = {placeholder})"
            params.append(token)
        clauses.append(clause)
    predicate = " AND ".join(clauses)
    if phrase:
        predicate = f"({predicate}) AND {name} LIKE {placeholder} ESCAPE '!'"
        params.append(f"%{escape_like(normalize(query.strip()))}%")
    return sql.replace(original, predicate, 1), tuple(params)
