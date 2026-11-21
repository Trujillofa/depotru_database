"""Shared text and number formatting for report renderers.

All helpers use Colombian conventions: ``$1.234.567``, ``45,6%``.
"""

from __future__ import annotations

import math
from typing import Any

MISSING = "—"


def shorten(text: Any, limit: int = 48) -> str:
    """Trim ``text`` to ``limit`` characters at a word boundary, adding ``…``."""
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    cut = clean[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:-")
    return f"{cut or clean[: limit - 1]}…"


def decimal_es(value: Any, decimals: int = 0) -> str:
    """Format a number with thousands dots and a decimal comma."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return MISSING
    if math.isnan(number) or math.isinf(number):
        return MISSING
    if decimals == 0:
        return f"{number:,.0f}".replace(",", ".")
    return (
        f"{number:,.{decimals}f}".replace(",", "\x00")
        .replace(".", ",")
        .replace("\x00", ".")
    )


def percent_es(value: Any, decimals: int = 1) -> str:
    """Format a percentage with a decimal comma (``45,6%``)."""
    formatted = decimal_es(value, decimals)
    return MISSING if formatted == MISSING else f"{formatted}%"


def money_compact(value: Any) -> str:
    """Compact currency for chart labels and tight cells (``$1,2M``)."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return MISSING
    if number >= 1_000_000_000:
        return f"${decimal_es(number / 1_000_000_000, 1)}MM"
    if number >= 1_000_000:
        return f"${decimal_es(number / 1_000_000, 1)}M"
    if number >= 1_000:
        return f"${decimal_es(number / 1_000, 0)}K"
    return f"${decimal_es(number, 0)}"


def strip_markdown(text: Any) -> str:
    """Remove Markdown markers for plain-text/PDF renderers."""
    import re

    t = str(text or "")
    t = re.sub(r"^\s{0,3}#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", t)
    t = re.sub(r"^\s*[-*_]{3,}\s*$", "", t, flags=re.M)
    t = re.sub(r"^\s*[-*+]\s+", "• ", t, flags=re.M)
    return t.strip()


_EMOJI_RANGES = (
    "\U0001F000-\U0001FAFF"
    "\u2190-\u21FF"
    "\u2300-\u23FF"
    "\u2600-\u27BF"
    "\u2B00-\u2BFF"
    "\uFE0F\u200D"
)


def strip_emoji(text: Any) -> str:
    """Remove emoji/symbol glyphs that ReportLab fonts render as boxes."""
    import re

    cleaned = re.sub(f"[{_EMOJI_RANGES}]", " ", str(text or ""))
    return re.sub(r"[ \t]{2,}", " ", cleaned).strip()


def strip_html(text: Any) -> str:
    """Flatten a small HTML fragment (used by PDF renderers)."""
    import re

    value = str(text or "")
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</?(strong|em|code|p|div|span)[^>]*>", "", value, flags=re.I)
    value = re.sub(r"</?ol[^>]*>", "\n", value, flags=re.I)
    value = re.sub(r"<li[^>]*>", "• ", value, flags=re.I)
    value = re.sub(r"</li>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(value.split())


def markdown_to_reportlab(text: Any) -> str:
    """Convert simple Markdown to ReportLab inline markup (safe for Paragraph)."""
    import html as html_lib
    import re

    value = html_lib.escape(str(text or ""), quote=False)
    value = re.sub(r"^\s{0,3}#{1,6}\s*(.+)$", r"<b>\1</b>", value, flags=re.M)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", value)
    value = re.sub(r"^\s*[-*+]\s+", "• ", value, flags=re.M)
    value = re.sub(r"^\s*[-*_]{3,}\s*$", "", value, flags=re.M)
    return value.strip()
