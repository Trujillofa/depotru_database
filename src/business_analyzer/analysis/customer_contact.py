"""Shared customer contact cleaning and validation helpers.

Single source of truth for contact fields used by every field/report export:
mobile coalescing with Colombian pattern validation, placeholder email
blacklist, name/city text cleanup and window-based monthly run-rate math.
"""

from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from typing import Any, Dict, Optional, Sequence

# Colombian mobile numbers: 10 digits starting with 3.
CO_MOVIL = re.compile(r"^3\d{9}$")

# Placeholder emails found in the ERP master (audit V-8 / S-2 / second pass).
EMAIL_PLACEHOLDERS = {
    "nocorreo@gmail.com",
    "nocorreo@hotmail.com",
    "ventascontado@yahoo.com",
    "ventascontadodeposito@yahoo.com",
    "ventas@yahoo.com",
    "fe@gmail.com",
    "clientes@depositotrujillo.com",
    "clientes@depositrujillo.com",  # missing "o" in the company domain
}
PLACEHOLDER_LOCALS = {
    "nocorreo",
    "nocorreo1",
    "fe",
    "ventascontado",
    "ventascontadodeposito",
}
# Pattern for new placeholder spellings (second audit, open item 1).
# Applied to the local part only — do not match a real ventas@empresa.com.
PLACEHOLDER_LOCAL_PATTERN = re.compile(r"^(nocorreo|notiene|sincorreo|ventascontado)")
# Company-owned domains are never a customer's email (audit S-14).
PLACEHOLDER_DOMAINS = {
    "depositotrujillo.com",
    "depositrujillo.com",
}
# Any email shared by this many distinct clients is filler, no matter how
# it is written (second audit, open item 1).
EMAIL_FRECUENCIA_RELLENO = 3

# Walk-in / POS catch-all third parties, not real customers (audit S-14).
GENERIC_NITS = frozenset({"222222222222", "2222222222", "111111111"})
GENERIC_CUSTOMER_NAMES = frozenset({"CONSUMIDOR FINAL"})

# cp1252 round-trip losses: Ñ stored as '?' between uppercase letters.
MOJIBAKE_MARK = re.compile(r"(?<=[A-Z])\?(?=[A-Z])")

# Known city typos in the master (second audit, open item 3).
CIUDAD_FIXES = {"FLORENCIA CAU": "FLORENCIA CAQ"}

# Default margins applied by the ERP when real cost is missing (audit S-7).
MARGINES_POR_DEFECTO = (0.310, 0.200, 0.137)
MARGEN_TOLERANCIA = 0.0015


def _digits(value: Any) -> str:
    """Keep only digits from a phone-ish value."""
    return re.sub(r"\D", "", str(value or ""))


def mejor_celular(celular: Any, telefono: Any = None) -> Optional[str]:
    """Return the first valid Colombian mobile among celular/telefono."""
    for value in (celular, telefono):
        digits = _digits(value)
        if CO_MOVIL.match(digits):
            return digits
    return None


def telefono_fijo(telefono: Any) -> Optional[str]:
    """Return a plausible fixed-line phone (7-10 digits, not a mobile)."""
    digits = _digits(telefono)
    if 7 <= len(digits) <= 10 and not CO_MOVIL.match(digits):
        return digits
    return None


def clean_email(
    value: Any, *, extra_placeholders: Optional[set] = None
) -> Optional[str]:
    """Normalize an email, discarding placeholders and malformed values."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or "@" not in text:
        return None
    local, _, domain = text.partition("@")
    if not local or not domain or "." not in domain:
        return None
    lowered = text.lower()
    local_lower = local.lower()
    extra = extra_placeholders or set()
    domain_lower = domain.lower()
    if (
        lowered in EMAIL_PLACEHOLDERS
        or lowered in extra
        or local_lower in PLACEHOLDER_LOCALS
        or PLACEHOLDER_LOCAL_PATTERN.match(local_lower)
        or domain_lower in PLACEHOLDER_DOMAINS
    ):
        return None
    return text


def find_placeholder_emails_by_frequency(
    emails: Sequence[Any], *, min_repeat: int = EMAIL_FRECUENCIA_RELLENO
) -> set:
    """Emails used by ``min_repeat``+ distinct clients are filler."""
    counts: Dict[str, int] = {}
    for value in emails:
        text = str(value or "").strip().lower()
        if text:
            counts[text] = counts.get(text, 0) + 1
    return {email for email, count in counts.items() if count >= min_repeat}


def es_nit_generico(value: Any) -> bool:
    """True for POS / walk-in catch-all identification numbers."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits in GENERIC_NITS


def es_cliente_generico(nit: Any = None, nombre: Any = None) -> bool:
    """True when the row is the walk-in bucket, not a real customer."""
    if es_nit_generico(nit):
        return True
    key = normalize_for_match(nombre) if nombre else ""
    return key in GENERIC_CUSTOMER_NAMES


def strip_accents(text: str) -> str:
    """Remove diacritics for name matching (Á→A, é→e)."""
    return "".join(
        char
        for char in unicodedata.normalize("NFD", text)
        if not unicodedata.combining(char)
    )


def normalize_for_match(value: Any) -> str:
    """Uppercase, accent-stripped, space-collapsed key for name matching."""
    return re.sub(r"\s+", " ", strip_accents(str(value or "")).strip().upper())


def clean_ciudad(value: Any) -> str:
    """Clean a city name, fixing known master-data typos."""
    text = clean_text(value).upper()
    return CIUDAD_FIXES.get(text, text)


def canal_preferido(
    movil: Optional[str],
    email: Optional[str],
    telefono: Any = None,
    direccion: Any = None,
    *,
    allow_visita: bool = True,
) -> str:
    """Derive the preferred contact channel from validated fields.

    Sika impact is a call list: pass ``allow_visita=False`` so an address
    alone does not look like a scheduled street visit.
    """
    if movil:
        return "WhatsApp"
    if email:
        return "Email"
    if telefono_fijo(telefono):
        return "Llamada"
    if allow_visita and direccion and str(direccion).strip():
        return "Visita"
    return "Sin contacto"


def repair_mojibake(text: str) -> str:
    """Restore Ñ lost in cp1252 round-trips (``DISE?O`` → ``DISEÑO``)."""
    return MOJIBAKE_MARK.sub("Ñ", text)


def clean_text(value: Any) -> str:
    """Squeeze inner whitespace and strip stray trailing dots/commas."""
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = " ".join(str(value).split())
    return text.rstrip(".").strip()


def clean_name(value: Any) -> str:
    """Clean a customer name, repairing mojibake Ñ."""
    return repair_mojibake(clean_text(value))


def months_elapsed(start: Any, end: Any, minimo: float = 1.0) -> float:
    """Calendar months elapsed between two dates (floor ``minimo``)."""
    start_date = start if isinstance(start, dt.date) else None
    end_date = end if isinstance(end, dt.date) else None
    if start_date is None or end_date is None:
        return minimo
    return max((end_date - start_date).days / 30.44, minimo)


def facturacion_mensual(
    total: float,
    inicio_ventana: Any,
    corte: Any,
    minimo_meses: float = 1.0,
) -> float:
    """Monthly run-rate over a FIXED calendar window (audit defect 1)."""
    meses = months_elapsed(inicio_ventana, corte, minimo_meses)
    return total / meses


def margen_es_por_defecto(facturacion: float, ganancia: float) -> bool:
    """True when the margin matches an ERP default instead of real cost."""
    if not facturacion:
        return False
    margen = ganancia / facturacion
    return any(
        abs(margen - default) <= MARGEN_TOLERANCIA for default in MARGINES_POR_DEFECTO
    )


def prioridad_score(
    facturacion_12m: float,
    facturacion_historica: float,
    meses_ventana: float,
    dias_sin_comprar: Optional[int],
) -> float:
    """Explicit value × recency priority score (audit V-4).

    Recent measured monthly revenue plus the lifetime monthly run-rate
    decayed by 0.5 every 180 days without purchase.
    """
    mensual_12m = facturacion_12m / 12.0
    mensual_historica = facturacion_historica / max(meses_ventana, 1.0)
    dias = dias_sin_comprar if dias_sin_comprar is not None else 1095
    recencia = 0.5 ** (dias / 180.0)
    return mensual_12m + mensual_historica * recencia


# =============================================================================
# Calendario de festivos de Colombia (Ley Emiliani) — auditoría V-13
# =============================================================================


def _siguiente_lunes(date: dt.date) -> dt.date:
    """Move a date to the next Monday unless it already is one."""
    if date.weekday() == 0:
        return date
    return date + dt.timedelta(days=(7 - date.weekday()) % 7 or 7)


def festivos_colombia(year: int) -> set:
    """Set of Colombian national holidays for a year (Ley 51 de 1983)."""
    from dateutil.easter import easter

    pascua = easter(year)
    # Fechas fijas que NO se mueven.
    fijos = (
        dt.date(year, 1, 1),  # Año Nuevo
        dt.date(year, 5, 1),  # Día del Trabajo
        dt.date(year, 7, 20),  # Independencia
        dt.date(year, 8, 7),  # Batalla de Boyacá
        dt.date(year, 12, 8),  # Inmaculada Concepción
        dt.date(year, 12, 25),  # Navidad
    )
    # Fechas fijas trasladadas al lunes siguiente (Ley Emiliani).
    emiliani = (
        dt.date(year, 1, 6),  # Reyes Magos
        dt.date(year, 3, 19),  # San José
        dt.date(year, 6, 29),  # San Pedro y San Pablo
        dt.date(year, 8, 15),  # Asunción de la Virgen
        dt.date(year, 10, 12),  # Día de la Raza
        dt.date(year, 11, 1),  # Todos los Santos
        dt.date(year, 11, 11),  # Independencia de Cartagena
    )
    # Festivos religiosos: Jueves y Viernes Santo fijos; Corpus y Sagrado
    # Corazón trasladados al lunes.
    semana_santa = (
        pascua - dt.timedelta(days=3),  # Jueves Santo
        pascua - dt.timedelta(days=2),  # Viernes Santo
    )
    moviles = (
        _siguiente_lunes(pascua + dt.timedelta(days=39)),  # Ascensión
        _siguiente_lunes(pascua + dt.timedelta(days=60)),  # Corpus Christi
        _siguiente_lunes(pascua + dt.timedelta(days=68)),  # Sagrado Corazón
    )
    festivos = set(fijos) | {_siguiente_lunes(date) for date in emiliani}
    festivos |= set(semana_santa) | set(moviles)
    return festivos


def es_festivo_colombia(date: dt.date) -> bool:
    """True when ``date`` is a Colombian national holiday."""
    return date in festivos_colombia(date.year)
