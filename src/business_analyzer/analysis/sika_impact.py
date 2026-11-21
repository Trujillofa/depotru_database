"""Sika Center (FEF) historic sales impact report.

This is a **contact list**, not a visit plan: gerencia uses it to call,
WhatsApp or email Sika Center customers who went quiet. A street visit is
not required. Field routing for recurrent Florencia clients lives in
``visitas_asesor``.

Builds the list from historic Sika Center sales in ``banco_datos``
(``DocumentosCodigo = 'FEF'``), flagging customers who have not purchased
recently and enriching each row with validated contact data (móvil,
telefono, direccion, ciudad, email) from ``J3System.dbo.AdmTerceros``.

Contact cleaning/validation lives in ``customer_contact``; the monthly
run-rate is computed over a FIXED calendar window (never months with
purchase) and a smoke test guards the export against run-rate inflation.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from business_analyzer.analysis.cotizaciones_celular import normalize_cedula
from business_analyzer.analysis.customer_contact import (
    CIUDAD_FIXES,
    GENERIC_NITS,
    canal_preferido,
    clean_ciudad,
    clean_email,
    clean_name,
    clean_text,
    es_cliente_generico,
    find_placeholder_emails_by_frequency,
    margen_es_por_defecto,
    mejor_celular,
    months_elapsed,
    telefono_fijo,
)
from business_analyzer.core.database import Database
from config import Config

SIKA_CENTER_DOCUMENT_CODE = "FEF"
DEFAULT_INACTIVITY_DAYS = 90
DEFAULT_RISK_DAYS = 180
# Thresholds scaled to short product-launch histories (audit S-6).
SHORT_WINDOW_RISK_DAYS = 30
SHORT_WINDOW_INACTIVITY_DAYS = 90
SHORT_WINDOW_DAYS = 365

SEGMENT_ACTIVO = "Activo"
SEGMENT_RIESGO = "En riesgo"
SEGMENT_INACTIVO = "Inactivo"
SEGMENT_ORDER = {
    SEGMENT_INACTIVO: 0,
    SEGMENT_RIESGO: 1,
    SEGMENT_ACTIVO: 2,
}

EMAIL_COLUMN_PREFERENCE = ("TercerosEmail", "Email", "TercerosCorreo")
CITY_NAME_COLUMN_PREFERENCE = (
    "CiudadNombre",
    "CiudadDescripcion",
    "Nombre",
    "Descripcion",
)
CITY_TABLE_NAME = "AdmCiudad"

OUTPUT_COLUMNS = (
    "segmento",
    "cliente",
    "nit",
    "dias_sin_comprar",
    "ultima_compra",
    "primera_compra",
    "dias_compra",
    "facturacion_historica",
    "facturacion_mensual",
    "run_rate_cliente",
    "ganancia_historica",
    "ticket_promedio",
    "costo_estimado",
    "movil",
    "telefono",
    "direccion",
    "ciudad",
    "email",
    "canal_preferido",
)

DISPLAY_HEADERS = {
    "segmento": "Segmento",
    "cliente": "Cliente",
    "nit": "NIT/Cédula",
    "dias_sin_comprar": "Días sin comprar",
    "ultima_compra": "Última compra",
    "primera_compra": "Primera compra",
    "dias_compra": "Días de compra",
    "facturacion_historica": "Facturación histórica",
    "facturacion_mensual": "Aporte mensual a la ventana",
    "run_rate_cliente": "Run-rate del cliente",
    "ganancia_historica": "Ganancia histórica",
    "ticket_promedio": "Ticket promedio",
    "costo_estimado": "Costo estimado",
    "movil": "Móvil (validado)",
    "telefono": "Teléfono",
    "direccion": "Dirección",
    "ciudad": "Ciudad",
    "email": "Email (validado)",
    "canal_preferido": "Canal preferido",
}

CURRENCY_COLUMNS = (
    "facturacion_historica",
    "facturacion_mensual",
    "run_rate_cliente",
    "ganancia_historica",
    "ticket_promedio",
)
DATE_COLUMNS = ("ultima_compra", "primera_compra")
INT_COLUMNS = ("dias_sin_comprar", "dias_compra")
BOOL_COLUMNS = ("costo_estimado",)
STRING_COLUMNS = (
    "cliente",
    "nit",
    "movil",
    "telefono",
    "direccion",
    "ciudad",
    "email",
    "canal_preferido",
)


def to_date(value: Any) -> Optional[dt.date]:
    """Coerce a DB date/datetime/string value to ``datetime.date``."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def to_float(value: Any, default: float = 0.0) -> float:
    """Coerce a DB numeric value to ``float``."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    """Coerce a DB numeric value to ``int``."""
    return int(round(to_float(value, float(default))))


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide safely, returning ``default`` when the denominator is zero."""
    return numerator / denominator if denominator else default


def sugerir_umbrales(ventana_dias: int) -> Tuple[int, int]:
    """Segment thresholds adapted to the observed data window (S-6)."""
    if ventana_dias < SHORT_WINDOW_DAYS:
        return SHORT_WINDOW_RISK_DAYS, SHORT_WINDOW_INACTIVITY_DAYS
    return DEFAULT_INACTIVITY_DAYS, DEFAULT_RISK_DAYS


def data_window(
    rows: Sequence[Mapping[str, Any]],
) -> Tuple[Optional[dt.date], Optional[dt.date]]:
    """First and last purchase dates across all customer rows."""
    fechas = [
        date
        for row in rows
        for date in (
            to_date(row.get("primera_compra")),
            to_date(row.get("ultima_compra")),
        )
        if date is not None
    ]
    if not fechas:
        return None, None
    return min(fechas), max(fechas)


def classify_segment(
    dias_sin_comprar: Optional[int],
    *,
    inactivity_days: int = DEFAULT_INACTIVITY_DAYS,
    risk_days: int = DEFAULT_RISK_DAYS,
) -> str:
    """Segment a customer by days since last purchase."""
    if dias_sin_comprar is None:
        return SEGMENT_INACTIVO
    if dias_sin_comprar <= inactivity_days:
        return SEGMENT_ACTIVO
    if dias_sin_comprar <= risk_days:
        return SEGMENT_RIESGO
    return SEGMENT_INACTIVO


def build_sika_customers_query(
    *,
    database: Optional[str] = None,
    table: Optional[str] = None,
    document_code: str = SIKA_CENTER_DOCUMENT_CODE,
) -> str:
    """Build the parameterized per-customer historic sales aggregate query."""
    db_name = Database.validate_sql_identifier(database or Config.DB_NAME, "database")
    table_name = Database.validate_sql_identifier(table or Config.DB_TABLE, "table")
    Database.validate_sql_identifier(document_code, "document code")
    generic_nits = tuple(sorted(GENERIC_NITS))
    nit_placeholders = ", ".join(["%s"] * len(generic_nits))
    return f"""
        SELECT
            bd.TercerosID AS terceros_id,
            bd.TercerosIdentificacion AS nit,
            MAX(bd.TercerosNombres) AS cliente,
            MIN(CONVERT(date, bd.Fecha)) AS primera_compra,
            MAX(CONVERT(date, bd.Fecha)) AS ultima_compra,
            SUM(bd.Cantidad) AS cantidad,
            SUM(bd.TotalSinIva) AS facturacion,
            SUM(bd.TotalSinIva - bd.ValorCosto) AS ganancia,
            COUNT(DISTINCT CONVERT(date, bd.Fecha)) AS dias_compra
        FROM [{db_name}].[dbo].[{table_name}] bd
        WHERE bd.DocumentosCodigo = %s
          AND bd.Fecha IS NOT NULL
          AND bd.TercerosIdentificacion NOT IN ({nit_placeholders})
        GROUP BY bd.TercerosID, bd.TercerosIdentificacion
    """  # nosec B608


def fetch_sika_customers(
    db: Database,
    *,
    document_code: str = SIKA_CENTER_DOCUMENT_CODE,
) -> List[Dict[str, Any]]:
    """Fetch per-customer historic sales aggregates for Sika Center."""
    query = build_sika_customers_query(document_code=document_code)
    params = (document_code, *sorted(GENERIC_NITS))
    with db:
        rows = db.execute_query(query, params)
    return [
        row
        for row in (rows or [])
        if not es_cliente_generico(row.get("nit"), row.get("cliente"))
    ]


def fetch_sika_window(
    db: Database,
    *,
    document_code: str = SIKA_CENTER_DOCUMENT_CODE,
) -> Tuple[Optional[dt.date], Optional[dt.date]]:
    """First and last FEF dates, including walk-in tickets (window provenance)."""
    db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
    table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
    Database.validate_sql_identifier(document_code, "document code")
    query = f"""
        SELECT
            MIN(CONVERT(date, bd.Fecha)) AS inicio,
            MAX(CONVERT(date, bd.Fecha)) AS fin
        FROM [{db_name}].[dbo].[{table_name}] bd
        WHERE bd.DocumentosCodigo = %s
          AND bd.Fecha IS NOT NULL
    """  # nosec B608
    with db:
        rows = db.execute_query(query, (document_code,))
    if not rows:
        return None, None
    return to_date(rows[0].get("inicio")), to_date(rows[0].get("fin"))


def enrich_customer_metrics(
    rows: Sequence[Mapping[str, Any]],
    *,
    today: Optional[dt.date] = None,
    inactivity_days: int = DEFAULT_INACTIVITY_DAYS,
    risk_days: int = DEFAULT_RISK_DAYS,
    inicio_ventana: Optional[dt.date] = None,
) -> List[Dict[str, Any]]:
    """Compute recency, monetary and segment metrics for each customer row.

    ``facturacion_mensual`` is the customer's contribution to the window KPI
    (÷ calendar months of ``inicio_ventana → today``). ``run_rate_cliente``
    divides by that customer's own tenure (audit S-13).
    """
    reference = today or dt.date.today()
    primera_global, _ = data_window(rows)
    window_start = inicio_ventana or primera_global or reference
    meses_ventana = max((reference - window_start).days / 30.44, 1.0)

    enriched: List[Dict[str, Any]] = []
    for row in rows:
        ultima = to_date(row.get("ultima_compra"))
        primera = to_date(row.get("primera_compra"))
        dias_sin_comprar = (reference - ultima).days if ultima is not None else None
        facturacion = to_float(row.get("facturacion"))
        ganancia = to_float(row.get("ganancia"))
        dias_compra = to_int(row.get("dias_compra"), 1)
        meses_cliente = months_elapsed(primera, reference, 1.0)
        enriched.append(
            {
                "terceros_id": row.get("terceros_id"),
                "nit": normalize_cedula(row.get("nit")),
                "cliente": clean_name(row.get("cliente")),
                "segmento": classify_segment(
                    dias_sin_comprar,
                    inactivity_days=inactivity_days,
                    risk_days=risk_days,
                ),
                "dias_sin_comprar": dias_sin_comprar,
                "ultima_compra": ultima,
                "primera_compra": primera,
                "dias_compra": dias_compra,
                "cantidad": to_int(row.get("cantidad")),
                "facturacion_historica": facturacion,
                "facturacion_mensual": safe_divide(facturacion, meses_ventana),
                "run_rate_cliente": safe_divide(facturacion, meses_cliente),
                "ganancia_historica": ganancia,
                "ticket_promedio": safe_divide(facturacion, dias_compra),
                "costo_estimado": margen_es_por_defecto(facturacion, ganancia),
                "movil": "",
                "telefono": "",
                "direccion": "",
                "ciudad": "",
                "email": "",
                "canal_preferido": "",
            }
        )
    return enriched


def admterceros_qualified_table(j3_database: Optional[str] = None) -> str:
    """Return the fully qualified ``J3System.dbo.AdmTerceros`` table reference."""
    db_name = j3_database or os.getenv("DB_NAME_J3SYSTEM", "J3System")
    validated = Database.validate_sql_identifier(db_name, "j3 database")
    return f"{validated}.dbo.AdmTerceros"


def qualified_j3_table(table: str, j3_database: Optional[str] = None) -> str:
    """Return a fully qualified table reference inside the J3System database."""
    db_name = j3_database or os.getenv("DB_NAME_J3SYSTEM", "J3System")
    validated_db = Database.validate_sql_identifier(db_name, "j3 database")
    validated_table = Database.validate_sql_identifier(table, "j3 table")
    return f"{validated_db}.dbo.{validated_table}"


def resolve_terceros_column(
    connection: Any,
    table: str,
    column_candidates: Sequence[str],
    *,
    j3_database: Optional[str] = None,
    like_patterns: Sequence[str] = (),
) -> Optional[str]:
    """Find the first existing column matching candidates or LIKE patterns."""
    db_name = Database.validate_sql_identifier(
        j3_database or os.getenv("DB_NAME_J3SYSTEM", "J3System"),
        "j3 database",
    )
    validated_table = Database.validate_sql_identifier(table, "j3 table")
    like_clause = ""
    params: List[Any] = [validated_table]
    if like_patterns:
        like_clause = " OR " + " OR ".join(["COLUMN_NAME LIKE %s"] * len(like_patterns))
        params.extend(like_patterns)
    query = (
        f"SELECT COLUMN_NAME FROM {db_name}.INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_NAME = %s{like_clause}"
    )  # nosec B608
    cursor = connection.cursor(as_dict=True)
    try:
        cursor.execute(query, tuple(params))
        columns = [str(row["COLUMN_NAME"]).strip() for row in cursor.fetchall()]
    except Exception:
        return None
    finally:
        cursor.close()

    columns_upper = {name.upper(): name for name in columns}
    for candidate in column_candidates:
        match = columns_upper.get(candidate.upper())
        if match:
            return match
    return columns[0] if columns else None


def resolve_email_column(connection: Any, *, j3_database: Optional[str] = None):
    """Resolve the AdmTerceros email column name, if any."""
    return resolve_terceros_column(
        connection,
        "AdmTerceros",
        EMAIL_COLUMN_PREFERENCE,
        j3_database=j3_database,
        like_patterns=("%mail%", "%correo%"),
    )


def resolve_city_join(
    connection: Any, *, j3_database: Optional[str] = None
) -> Tuple[Optional[str], Optional[str]]:
    """Resolve ``(city_table, city_name_column)`` for ciudad enrichment."""
    name_column = resolve_terceros_column(
        connection,
        CITY_TABLE_NAME,
        CITY_NAME_COLUMN_PREFERENCE,
        j3_database=j3_database,
        like_patterns=("%ciudad%", "%nombre%"),
    )
    if not name_column:
        return None, None
    return CITY_TABLE_NAME, name_column


def build_contact_query(
    chunk_size: int,
    *,
    j3_database: Optional[str] = None,
    email_column: Optional[str] = None,
    city_table: Optional[str] = None,
    city_name_column: Optional[str] = None,
) -> str:
    """Build the parameterized batch contact lookup query for AdmTerceros."""
    table = admterceros_qualified_table(j3_database)
    email_select = ""
    if email_column:
        validated_email = Database.validate_sql_identifier(email_column, "email column")
        email_select = f", t.{validated_email} AS email"
    city_select = ""
    city_join = ""
    if city_table and city_name_column:
        validated_table = qualified_j3_table(city_table, j3_database)
        validated_name = Database.validate_sql_identifier(
            city_name_column, "city name column"
        )
        city_select = f", c.{validated_name} AS ciudad"
        city_join = f" LEFT JOIN {validated_table} c ON t.CiudadID = c.CiudadID"
    placeholders = ",".join(["%s"] * chunk_size)
    return (
        "SELECT t.TercerosID AS terceros_id, "
        "t.TercerosIdentificacion AS nit, "
        "t.TercerosCelular AS celular, "
        "t.TercerosTeleFax AS telefono, "
        "t.TercerosDireccion AS direccion"
        f"{email_select}{city_select} "
        f"FROM {table} t{city_join} "
        f"WHERE t.TercerosIdentificacion IN ({placeholders})"
    )  # nosec B608


def _contact_from_row(row: Mapping[str, Any]) -> Dict[str, str]:
    """Raw contact fields from an AdmTerceros row (validated downstream)."""
    return {
        "celular": clean_text(row.get("celular")),
        "telefono": clean_text(row.get("telefono")),
        "direccion": clean_text(row.get("direccion")),
        "ciudad": clean_text(row.get("ciudad")),
        "email": clean_text(row.get("email")),
    }


def fetch_terceros_contacts(
    identificaciones: Sequence[str],
    connection: Any,
    *,
    email_column: Optional[str] = None,
    city_table: Optional[str] = None,
    city_name_column: Optional[str] = None,
    batch_size: int = 500,
    j3_database: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """Batch lookup AdmTerceros contacts keyed by normalized identificacion."""
    normalized = sorted(
        {
            normalize_cedula(value)
            for value in identificaciones
            if normalize_cedula(value)
        }
    )
    if not normalized:
        return {}

    contacts: Dict[str, Dict[str, str]] = {}
    cursor = connection.cursor(as_dict=True)
    try:
        for start in range(0, len(normalized), batch_size):
            chunk = normalized[start : start + batch_size]
            query = build_contact_query(
                len(chunk),
                j3_database=j3_database,
                email_column=email_column,
                city_table=city_table,
                city_name_column=city_name_column,
            )
            cursor.execute(query, tuple(chunk))
            for row in cursor.fetchall():
                key = normalize_cedula(row.get("nit"))
                if key:
                    contacts[key] = _contact_from_row(row)
    finally:
        cursor.close()
    return contacts


def fetch_terceros_contacts_by_id(
    terceros_ids: Sequence[Any],
    connection: Any,
    *,
    email_column: Optional[str] = None,
    city_table: Optional[str] = None,
    city_name_column: Optional[str] = None,
    batch_size: int = 500,
    j3_database: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """Batch lookup AdmTerceros contacts keyed by string TercerosID."""
    ids = sorted(
        {
            str(value).strip()
            for value in terceros_ids
            if value is not None and str(value).strip()
        }
    )
    if not ids:
        return {}

    table = admterceros_qualified_table(j3_database)
    email_select = ""
    if email_column:
        validated_email = Database.validate_sql_identifier(email_column, "email column")
        email_select = f", t.{validated_email} AS email"
    city_select = ""
    city_join = ""
    if city_table and city_name_column:
        validated_table = qualified_j3_table(city_table, j3_database)
        validated_name = Database.validate_sql_identifier(
            city_name_column, "city name column"
        )
        city_select = f", c.{validated_name} AS ciudad"
        city_join = f" LEFT JOIN {validated_table} c ON t.CiudadID = c.CiudadID"

    contacts: Dict[str, Dict[str, str]] = {}
    cursor = connection.cursor(as_dict=True)
    try:
        for start in range(0, len(ids), batch_size):
            chunk = ids[start : start + batch_size]
            placeholders = ",".join(["%s"] * len(chunk))
            query = (
                "SELECT t.TercerosID AS terceros_id, "
                "t.TercerosCelular AS celular, "
                "t.TercerosTeleFax AS telefono, "
                "t.TercerosDireccion AS direccion"
                f"{email_select}{city_select} "
                f"FROM {table} t{city_join} "
                f"WHERE t.TercerosID IN ({placeholders})"
            )  # nosec B608
            cursor.execute(query, tuple(chunk))
            for row in cursor.fetchall():
                key = str(row.get("terceros_id") or "").strip()
                if key:
                    contacts[key] = _contact_from_row(row)
    finally:
        cursor.close()
    return contacts


def _unique_contact_emails(
    *sources: Mapping[str, Mapping[str, str]],
) -> List[str]:
    """One email per distinct contact, so frequency is per person not per key."""
    emails: List[str] = []
    seen = set()
    for source in sources:
        for contact in source.values():
            fingerprint = (
                str(contact.get("celular") or ""),
                str(contact.get("email") or ""),
                str(contact.get("direccion") or ""),
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            emails.append(str(contact.get("email") or ""))
    return emails


def merge_contact_lookup(
    rows: Sequence[Mapping[str, Any]],
    by_nit: Mapping[str, Mapping[str, str]],
    by_terceros_id: Mapping[str, Mapping[str, str]],
    issues: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Attach VALIDATED contact fields (NIT match preferred over TercerosID).

    Fills ``issues`` (when provided) with data-quality problems found:
    invalid celular, garbage teléfono, placeholder emails and city typos
    (audits V-3/V-8/S-3/S-4 and second-pass items 1-4).
    """
    extra_placeholders = find_placeholder_emails_by_frequency(
        _unique_contact_emails(by_nit, by_terceros_id)
    )
    merged: List[Dict[str, Any]] = []
    for row in rows:
        nit = normalize_cedula(row.get("nit"))
        contact = by_nit.get(nit)
        if contact is None:
            contact = by_terceros_id.get(str(row.get("terceros_id") or "").strip())
        enriched = dict(row)
        raw_celular = raw_email = raw_telefono = raw_ciudad = ""
        if contact:
            raw_celular = contact.get("celular", "")
            raw_email = contact.get("email", "")
            raw_telefono = contact.get("telefono", "")
            raw_ciudad = contact.get("ciudad", "")
            movil = mejor_celular(raw_celular, raw_telefono)
            email = clean_email(raw_email, extra_placeholders=extra_placeholders)
            telefono = telefono_fijo(raw_telefono)
            ciudad = clean_ciudad(raw_ciudad)
            enriched["movil"] = movil or ""
            enriched["telefono"] = telefono or ""
            enriched["direccion"] = contact.get("direccion", "")
            enriched["ciudad"] = ciudad
            enriched["email"] = email or ""
            enriched["canal_preferido"] = canal_preferido(
                movil,
                email,
                raw_telefono,
                contact.get("direccion"),
                allow_visita=False,
            )
        else:
            for field in ("movil", "telefono", "direccion", "ciudad", "email"):
                enriched[field] = str(enriched.get(field) or "")
            if enriched["ciudad"]:
                enriched["ciudad"] = clean_ciudad(enriched["ciudad"])
            enriched["canal_preferido"] = "Sin contacto"
        if issues is not None:
            cliente = str(enriched.get("cliente") or "")
            if raw_celular and not mejor_celular(raw_celular):
                issues.append(
                    {
                        "nit": nit,
                        "cliente": cliente,
                        "campo": "Celular",
                        "valor": raw_celular,
                        "problema": "No es un móvil colombiano válido (3XXXXXXXXX)",
                    }
                )
            if raw_email and not clean_email(
                raw_email, extra_placeholders=extra_placeholders
            ):
                issues.append(
                    {
                        "nit": nit,
                        "cliente": cliente,
                        "campo": "Email",
                        "valor": raw_email,
                        "problema": "Correo de relleno o inválido",
                    }
                )
            if (
                raw_telefono
                and not telefono_fijo(raw_telefono)
                and not mejor_celular(raw_telefono)
            ):
                issues.append(
                    {
                        "nit": nit,
                        "cliente": cliente,
                        "campo": "Teléfono",
                        "valor": raw_telefono,
                        "problema": "Valor basura o no es un fijo válido",
                    }
                )
            ciudad_key = clean_text(raw_ciudad).upper()
            if ciudad_key in CIUDAD_FIXES:
                issues.append(
                    {
                        "nit": nit,
                        "cliente": cliente,
                        "campo": "Ciudad",
                        "valor": raw_ciudad,
                        "problema": (
                            "Typo de ciudad; corregido a " f"{CIUDAD_FIXES[ciudad_key]}"
                        ),
                    }
                )
        merged.append({column: enriched.get(column) for column in OUTPUT_COLUMNS})
    return merged


def sort_call_list(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """Order rows lapsed-first, then by the customer's own run-rate (S-13)."""
    return sorted(
        rows,
        key=lambda row: (
            SEGMENT_ORDER.get(str(row.get("segmento")), SEGMENT_ORDER[SEGMENT_ACTIVO]),
            -to_float(row.get("run_rate_cliente") or row.get("facturacion_mensual")),
        ),
    )


def is_lapsed(row: Mapping[str, Any], *, inactivity_days: int) -> bool:
    """True when the customer exceeded the inactivity window."""
    dias = row.get("dias_sin_comprar")
    return dias is None or to_float(dias) > inactivity_days


def validar_runrate(
    rows: Sequence[Mapping[str, Any]],
    *,
    ratio: float = 0.5,
    max_frac: float = 0.2,
) -> None:
    """Smoke test: monthly run-rate must never approach historic totals (S-1)."""
    if not rows:
        return
    inflated = sum(
        1
        for row in rows
        if to_float(row.get("facturacion_mensual"))
        > to_float(row.get("facturacion_historica")) * ratio
    )
    if inflated > len(rows) * max_frac:
        raise ValueError(
            f"Run-rate sospechoso: {inflated}/{len(rows)} clientes con promedio "
            f"mensual > {ratio:.0%} de su total histórico. Revise la ventana."
        )


def build_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    inactivity_days: int = DEFAULT_INACTIVITY_DAYS,
    risk_days: int = DEFAULT_RISK_DAYS,
    inicio_ventana: Optional[dt.date] = None,
    corte: Optional[dt.date] = None,
) -> Dict[str, Any]:
    """Summarize segments, revenue at risk and validated contact coverage."""
    counts = {
        SEGMENT_ACTIVO: 0,
        SEGMENT_RIESGO: 0,
        SEGMENT_INACTIVO: 0,
    }
    facturacion_total = 0.0
    facturacion_historica_en_riesgo = 0.0
    facturacion_mensual_en_riesgo = 0.0
    facturacion_historica_inactivos = 0.0
    facturacion_mensual_inactivos = 0.0
    con_movil = 0
    con_email = 0
    costo_estimado = 0

    for row in rows:
        segmento = str(row.get("segmento") or SEGMENT_ACTIVO)
        counts[segmento] = counts.get(segmento, 0) + 1
        facturacion_total += to_float(row.get("facturacion_historica"))
        aporte = to_float(row.get("facturacion_mensual"))
        historica = to_float(row.get("facturacion_historica"))
        if segmento == SEGMENT_RIESGO:
            facturacion_historica_en_riesgo += historica
            facturacion_mensual_en_riesgo += aporte
        elif segmento == SEGMENT_INACTIVO:
            facturacion_historica_inactivos += historica
            facturacion_mensual_inactivos += aporte
        if str(row.get("movil") or "").strip():
            con_movil += 1
        if str(row.get("email") or "").strip():
            con_email += 1
        if row.get("costo_estimado"):
            costo_estimado += 1

    lapsed = [row for row in rows if is_lapsed(row, inactivity_days=inactivity_days)]
    reference = corte or dt.date.today()
    primera_global, ultima_global = data_window(rows)
    # CLI passes (activo_max, inactivo_min) as (risk_days, inactivity_days);
    # classify_segment uses the swapped pair. Take the ordered cutoffs.
    activo_max, inactivo_min = sorted((risk_days, inactivity_days))
    return {
        "total_clientes": len(rows),
        "clientes_activos": counts[SEGMENT_ACTIVO],
        "clientes_en_riesgo": counts[SEGMENT_RIESGO],
        "clientes_inactivos": counts[SEGMENT_INACTIVO],
        "clientes_sin_comprar": len(lapsed),
        "dias_inactividad": inactivity_days,
        "dias_riesgo": risk_days,
        "activo_max_dias": activo_max,
        "inactivo_min_dias": inactivo_min,
        "fecha_corte": reference,
        "inicio_ventana": inicio_ventana or primera_global,
        "fin_ventana": ultima_global,
        "facturacion_total": facturacion_total,
        "facturacion_historica_en_riesgo": facturacion_historica_en_riesgo,
        "facturacion_mensual_en_riesgo": facturacion_mensual_en_riesgo,
        "facturacion_historica_inactivos": facturacion_historica_inactivos,
        "facturacion_mensual_inactivos": facturacion_mensual_inactivos,
        "con_movil": con_movil,
        "con_email": con_email,
        "costo_estimado": costo_estimado,
    }


def _cell_value(column: str, value: Any) -> Any:
    """Coerce a row value to a native xlsxwriter writable value."""
    if value is None:
        return ""
    if column == "costo_estimado":
        return "Sí" if value else ""
    return value


def export_xlsx(
    rows: Sequence[Mapping[str, Any]],
    output_path: str,
    *,
    summary: Optional[Mapping[str, Any]] = None,
    document_code: str = SIKA_CENTER_DOCUMENT_CODE,
    quality_issues: Optional[Sequence[Mapping[str, str]]] = None,
    excluded_documents: Sequence[str] = (),
) -> None:
    """Write the customer list, provenance summary and data-quality sheet."""
    import xlsxwriter

    from business_analyzer.analysis.excel_helpers import autofit_columns

    workbook = xlsxwriter.Workbook(output_path)
    header_format = workbook.add_format(
        {"bold": True, "bg_color": "#1F4E78", "font_color": "white"}
    )
    currency_format = workbook.add_format({"num_format": '"$"#,##0'})
    date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
    int_format = workbook.add_format({"num_format": "0"})
    text_format = workbook.add_format({"align": "left"})
    label_format = workbook.add_format({"bold": True})

    sorted_rows = sort_call_list(list(rows))

    # --- Clientes (single data sheet, audit S-8) ---------------------------
    worksheet = workbook.add_worksheet("Clientes")
    matrix: List[List[Any]] = []
    for row_index, row in enumerate(sorted_rows, start=1):
        values = [_cell_value(column, row.get(column, "")) for column in OUTPUT_COLUMNS]
        matrix.append(values)
        for col_index, column in enumerate(OUTPUT_COLUMNS):
            value = values[col_index]
            if column in CURRENCY_COLUMNS:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    worksheet.write_number(
                        row_index, col_index, float(value), currency_format
                    )
                else:
                    worksheet.write_blank(row_index, col_index, None, currency_format)
            elif column in DATE_COLUMNS:
                if isinstance(value, dt.date):
                    worksheet.write_datetime(row_index, col_index, value, date_format)
                else:
                    worksheet.write_blank(row_index, col_index, None, date_format)
            elif column in INT_COLUMNS:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    worksheet.write_number(row_index, col_index, int(value), int_format)
                else:
                    worksheet.write_blank(row_index, col_index, None, int_format)
            elif isinstance(value, str):
                worksheet.write_string(row_index, col_index, value, text_format)
            else:
                worksheet.write(row_index, col_index, value)
    for col_index, column in enumerate(OUTPUT_COLUMNS):
        worksheet.write(0, col_index, DISPLAY_HEADERS[column], header_format)
    currency_idx = [i for i, c in enumerate(OUTPUT_COLUMNS) if c in CURRENCY_COLUMNS]
    date_idx = [OUTPUT_COLUMNS.index(c) for c in DATE_COLUMNS]
    autofit_columns(
        worksheet,
        [[DISPLAY_HEADERS[c] for c in OUTPUT_COLUMNS]] + matrix,
        currency_columns=currency_idx,
        date_columns=date_idx,
        extra_widths={
            OUTPUT_COLUMNS.index("cliente"): 40,
            OUTPUT_COLUMNS.index("ultima_compra"): 36,
            OUTPUT_COLUMNS.index("primera_compra"): 37,
        },
    )
    # Pin date columns with *distinct* widths so xlsxwriter does not merge
    # E+F into one <col min="5" max="6"> range. Some readers (and the
    # previous ###### on F) only honor the first column of a grouped range.
    ultima_idx = OUTPUT_COLUMNS.index("ultima_compra")
    primera_idx = OUTPUT_COLUMNS.index("primera_compra")
    worksheet.set_column(ultima_idx, ultima_idx, 36)
    worksheet.set_column(primera_idx, primera_idx, 37)
    worksheet.autofilter(0, 0, len(sorted_rows), len(OUTPUT_COLUMNS) - 1)
    worksheet.freeze_panes(1, 2)

    # --- Resumen (provenance + KPIs, audit S-10) ---------------------------
    if summary:
        resumen = workbook.add_worksheet("Resumen")
        resumen.write(0, 0, "Reporte de impacto Sika Center", header_format)
        row_index = 2
        activo_max = int(
            summary.get("activo_max_dias") or summary.get("dias_riesgo") or 0
        )
        inactivo_min = int(
            summary.get("inactivo_min_dias") or summary.get("dias_inactividad") or 0
        )
        provenance = [
            (
                "Propósito",
                "Lista de contacto (WhatsApp / email / llamada). "
                "No es un plan de visitas.",
            ),
            ("Fecha de corte", str(summary.get("fecha_corte", ""))),
            (
                "Ventana de datos",
                f"{summary.get('inicio_ventana', '')} → "
                f"{summary.get('fin_ventana', '')}",
            ),
            ("Filtro", f"DocumentosCodigo = '{document_code}' (sede Sika Center)"),
            (
                "Documentos excluidos",
                ", ".join(excluded_documents) or "ninguno",
            ),
            (
                "Umbrales de segmento",
                (
                    f"Activo ≤ {activo_max} días; "
                    f"En riesgo {activo_max + 1}-{inactivo_min} días; "
                    f"Inactivo > {inactivo_min} días"
                ),
            ),
            (
                "Método mensual",
                "Aporte a la ventana = total ÷ meses de la ventana fija. "
                "Run-rate del cliente = total ÷ meses desde su primera "
                "compra (piso 1).",
            ),
        ]
        for label, value in provenance:
            resumen.write_string(row_index, 0, label, label_format)
            resumen.write_string(row_index, 1, value)
            row_index += 1
        row_index += 1
        kpis = [
            ("Clientes históricos", summary.get("total_clientes", 0)),
            ("Clientes activos", summary.get("clientes_activos", 0)),
            ("Clientes en riesgo", summary.get("clientes_en_riesgo", 0)),
            ("Clientes inactivos", summary.get("clientes_inactivos", 0)),
            ("Facturación histórica total", summary.get("facturacion_total", 0.0)),
            (
                "Facturación histórica en riesgo",
                summary.get("facturacion_historica_en_riesgo", 0.0),
            ),
            (
                "Aporte mensual de en riesgo",
                summary.get("facturacion_mensual_en_riesgo", 0.0),
            ),
            (
                "Facturación histórica de inactivos",
                summary.get("facturacion_historica_inactivos", 0.0),
            ),
            (
                "Aporte mensual de inactivos",
                summary.get("facturacion_mensual_inactivos", 0.0),
            ),
            ("Con móvil validado", summary.get("con_movil", 0)),
            ("Con email validado", summary.get("con_email", 0)),
            ("Con costo estimado (no real)", summary.get("costo_estimado", 0)),
        ]
        money_prefixes = ("Facturación", "Aporte", "Run-rate")
        for label, value in kpis:
            resumen.write_string(row_index, 0, label)
            if isinstance(value, float) or label.startswith(money_prefixes):
                resumen.write_number(
                    row_index, 1, int(round(float(value))), currency_format
                )
            else:
                resumen.write_number(row_index, 1, int(value), int_format)
            row_index += 1
        resumen.set_column(0, 0, 40)
        resumen.set_column(1, 1, 52)

    # --- Calidad de datos (audits S-2/S-4) ----------------------------------
    issues = list(quality_issues or [])
    calidad = workbook.add_worksheet("Calidad de datos")
    calidad_headers = ("NIT/Cédula", "Cliente", "Campo", "Valor original", "Problema")
    calidad_keys = ("nit", "cliente", "campo", "valor", "problema")
    for col_index, header in enumerate(calidad_headers):
        calidad.write(0, col_index, header, header_format)
    if issues:
        for row_index, issue in enumerate(issues, start=1):
            for col_index, key in enumerate(calidad_keys):
                calidad.write_string(
                    row_index, col_index, str(issue.get(key, "")), text_format
                )
    else:
        calidad.write_string(1, 0, "(sin incidencias detectadas)", text_format)
    autofit_columns(
        calidad,
        [list(calidad_headers)]
        + [[str(issue.get(k, "")) for k in calidad_keys] for issue in issues],
    )
    calidad.freeze_panes(1, 0)

    workbook.close()
