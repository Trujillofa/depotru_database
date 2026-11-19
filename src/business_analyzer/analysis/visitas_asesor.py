"""Generador de programación y control de visitas para asesores comerciales.

This is the **field-visit book for recurrent clients** (purchase history in
the advisor's city). It is not the Sika impact/contact list — that report
is ``sika_impact`` and does not require a street visit.

Combina:
- Clientes reales de ``banco_datos`` (histórico + últimos 12 meses) enriquecidos
  con contactos VALIDADOS de ``J3System.dbo.AdmTerceros`` (filtrados por
  ciudad, p. ej. FLORENCIA).
- Prospectos por categoría desde el Excel fuente del asesor (captación, hoja
  aparte).

El plan usa un cursor compartido entre meses (cada mes continúa la cola del
anterior) y reparte la cuota diaria por segmento en vez de recortar la lista
ordenada. Los clientes con demasiados días sin comprar van a agenda de
llamada, no a visita presencial.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from business_analyzer.analysis.cotizaciones_celular import normalize_cedula
from business_analyzer.analysis.customer_contact import (
    CIUDAD_FIXES,
    canal_preferido,
    clean_ciudad,
    clean_email,
    clean_text,
    es_cliente_generico,
    es_festivo_colombia,
    find_placeholder_emails_by_frequency,
    mejor_celular,
    normalize_for_match,
    prioridad_score,
    telefono_fijo,
)
from business_analyzer.analysis.sika_impact import (
    SEGMENT_ACTIVO,
    SEGMENT_INACTIVO,
    SEGMENT_RIESGO,
    data_window,
    enrich_customer_metrics,
    to_float,
)
from business_analyzer.core.database import Database
from config import Config

DEFAULT_ASESOR = "ARMANDO JOSE"
DEFAULT_CIUDAD = "FLORENCIA"
DEFAULT_VISITAS_POR_DIA = 4
# Por encima de estos días sin comprar la gestión es llamada, no visita (V-2).
CAP_DIAS_PRESENCIAL = 540
SEGMENT_SIN_HISTORIAL = "Sin historial"
AGENDA_VISITA = "Visita"
AGENDA_LLAMADA = "Llamada/WhatsApp"

PROSPECT_CATEGORIES = ("VIDRIERIA", "CONSTRUCTORA", "TORNILLERIA", "ACEROS")
CATEGORIA_CRONOGRAMA = "CRONOGRAMA (sin historial)"
RESULTADO_VISITA_OPTIONS = (
    "Efectiva",
    "No efectiva",
    "Reprogramada",
    "Sin visita",
)
VISITADO_OPTIONS = ("Sí", "No")
# Mezcla diaria por segmento: 2 en riesgo + 1 inactivo + 1 activo (V-2).
MEZCLA_DIARIA = (SEGMENT_RIESGO, SEGMENT_RIESGO, SEGMENT_INACTIVO, SEGMENT_ACTIVO)

MESES_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
DIAS_ES = (
    "Lunes",
    "Martes",
    "Miércoles",
    "Jueves",
    "Viernes",
    "Sábado",
    "Domingo",
)

BASE_COLUMNS = (
    "prioridad",
    "segmento",
    "agenda",
    "score",
    "cliente",
    "nit",
    "direccion",
    "ciudad",
    "movil",
    "telefono",
    "email",
    "canal_preferido",
    "ultima_compra",
    "dias_sin_comprar",
    "facturacion_12m",
    "facturacion_mensual",
    "facturacion_historica",
    "ticket_promedio",
    "costo_estimado",
)
BASE_HEADERS = {
    "prioridad": "No.",
    "segmento": "Segmento",
    "agenda": "Agenda",
    "score": "Score prioridad",
    "cliente": "Cliente",
    "nit": "NIT/CC",
    "direccion": "Dirección",
    "ciudad": "Ciudad",
    "movil": "Móvil (validado)",
    "telefono": "Teléfono",
    "email": "Email (validado)",
    "canal_preferido": "Canal preferido",
    "ultima_compra": "Última compra",
    "dias_sin_comprar": "Días sin comprar",
    "facturacion_12m": "Fact. últimos 12m",
    "facturacion_mensual": "Run-rate mensual histórico",
    "facturacion_historica": "Facturación histórica",
    "ticket_promedio": "Ticket promedio",
    "costo_estimado": "Costo estimado",
}
BASE_CURRENCY_COLUMNS = (
    "facturacion_12m",
    "facturacion_mensual",
    "facturacion_historica",
    "ticket_promedio",
)

PROGRAM_COLUMNS = ("cliente", "nit", "direccion", "ciudad", "movil", "email")
PROGRAM_HEADERS = {
    "cliente": "Cliente",
    "nit": "NIT/CC",
    "direccion": "Dirección",
    "ciudad": "Ciudad",
    "movil": "Móvil (validado)",
    "email": "Email (validado)",
}

CONTROL_HEADERS = (
    "ID visita",
    "Fecha programada",
    "Cliente",
    "NIT/CC",
    "Dirección",
    "Móvil",
    "Hora",
    "Resultado",
    "Valor pedido $",
    "Observaciones",
)


# =============================================================================
# Utilidades de fecha
# =============================================================================


def month_label(year: int, month: int) -> str:
    """Etiqueta corta del mes, p. ej. ``SEP`` para usar en nombres de hoja."""
    return MESES_ES[month - 1][:3].upper()


def weekday_dates(
    year: int,
    month: int,
    start_from: Optional[dt.date] = None,
    *,
    skip_holidays: bool = True,
) -> List[dt.date]:
    """Días hábiles (lun-vie, sin festivos colombianos) de un mes."""
    first = dt.date(year, month, 1)
    next_first = dt.date(year + 1, 1, 1) if month == 12 else dt.date(year, month + 1, 1)
    dates = []
    current = first
    while current < next_first:
        is_weekday = current.weekday() < 5
        is_holiday = skip_holidays and es_festivo_colombia(current)
        after_start = start_from is None or current >= start_from
        if is_weekday and not is_holiday and after_start:
            dates.append(current)
        current += dt.timedelta(days=1)
    return dates


def next_year_month(year: int, month: int) -> Tuple[int, int]:
    """Return the following calendar month."""
    if month == 12:
        return year + 1, 1
    return year, month + 1


def holiday_shortfall(
    year: int, month: int, start_from: Optional[dt.date] = None
) -> int:
    """Working days lost to Colombian holidays in a month."""
    weekdays = weekday_dates(year, month, start_from=start_from, skip_holidays=False)
    working = weekday_dates(year, month, start_from=start_from, skip_holidays=True)
    return max(len(weekdays) - len(working), 0)


def spillover_working_dates(year: int, month: int, days: int) -> List[dt.date]:
    """First ``days`` working days after the given month (holiday-aware)."""
    if days <= 0:
        return []
    dates: List[dt.date] = []
    n_year, n_month = next_year_month(year, month)
    # Bound the search so a bad calendar cannot loop forever.
    for _ in range(6):
        dates.extend(weekday_dates(n_year, n_month))
        if len(dates) >= days:
            return dates[:days]
        n_year, n_month = next_year_month(n_year, n_month)
    return dates[:days]


def normalize_name(value: Any) -> str:
    """Normaliza un nombre para comparación: mayúsculas y espacios únicos."""
    return re.sub(r"\s+", " ", str(value or "").strip().upper())


# =============================================================================
# Lectura de los archivos fuente
# =============================================================================


def read_sheet_rows(path: str, sheet_name: Optional[str] = None) -> List[List[Any]]:
    """Lee una hoja completa con openpyxl (valores calculados)."""
    import openpyxl

    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    worksheet = workbook[sheet_name] if sheet_name else workbook.worksheets[0]
    rows = [list(row) for row in worksheet.iter_rows(values_only=True)]
    workbook.close()
    return rows


def parse_prospectos(
    rows_by_category: Mapping[str, Sequence[Sequence[Any]]],
) -> Dict[str, List[Dict[str, str]]]:
    """Extrae prospectos (nombre comercial + celular) por categoría."""
    prospectos: Dict[str, List[Dict[str, str]]] = {}
    for category, rows in rows_by_category.items():
        entries: List[Dict[str, str]] = []
        for row in rows[1:]:
            nombre = clean_text(row[0] if len(row) > 0 else "")
            celular = clean_text(row[1] if len(row) > 1 else "")
            if celular.endswith(".0"):
                celular = celular[:-2]
            if nombre and nombre.lower() not in (
                "nombre comercial",
                "constructoras",
                "celular",
            ):
                entries.append({"nombre": nombre, "celular": celular})
        prospectos[category] = entries
    return prospectos


def parse_cronograma_clients(
    rows: Sequence[Sequence[Any]],
) -> List[Dict[str, str]]:
    """Extrae clientes del cronograma mensual (nombre, NIT, ferretería).

    Soporta tres layouts del archivo fuente:
    - Filas con fecha: nombre en la segunda columna.
    - Filas con nombre en la segunda columna y NIT numérico en la tercera.
    - Filas con NIT numérico en la primera o segunda columna y nombre al lado.
    """
    clients: Dict[str, Dict[str, str]] = {}

    def add(nombre: Any, nit: Any = "", ferreteria: Any = "") -> None:
        key = normalize_name(nombre)
        if not key or key in clients:
            return
        clients[key] = {
            "cliente": clean_text(nombre),
            "nit": normalize_cedula(nit),
            "ferreteria": clean_text(ferreteria),
        }

    for row in rows[1:]:
        col_a = row[0] if len(row) > 0 else None
        col_b = row[1] if len(row) > 1 else None
        col_c = row[2] if len(row) > 2 else None
        col_d = row[3] if len(row) > 3 else None
        if isinstance(col_a, (dt.date, dt.datetime)):
            add(col_b)
        elif isinstance(col_a, (int, float)) and not isinstance(col_a, bool):
            add(col_b, col_a, col_c)
        elif isinstance(col_b, (int, float)) and not isinstance(col_b, bool):
            add(col_c, col_b)
        elif col_b is not None and str(col_b).strip():
            if isinstance(col_c, (int, float)) and not isinstance(col_c, bool):
                add(col_b, col_c, col_d)
            else:
                add(col_b)
    return list(clients.values())


def parse_barrios(rows: Sequence[Sequence[Any]]) -> List[str]:
    """Extrae barrios (columna FERRETERIA) de la hoja de programación fuente."""
    barrios: List[str] = []
    header_seen = False
    for row in rows:
        cells = [clean_text(cell) for cell in row]
        if "FECHA DE VISITA" in cells:
            header_seen = True
            continue
        if not header_seen:
            continue
        nombre = row[1] if len(row) > 1 else None
        barrio = clean_text(row[2] if len(row) > 2 else None)
        if (
            barrio
            and barrio not in barrios
            and "ENTREGAS" not in clean_text(nombre).upper()
            and "ZONA" not in barrio.upper()
            and "FLORENCIA" not in barrio.upper()
        ):
            barrios.append(barrio)
    return barrios


# =============================================================================
# Consultas a la base de datos
# =============================================================================


def build_customer_history_query(
    *,
    database: Optional[str] = None,
    table: Optional[str] = None,
) -> Tuple[str, Tuple[str, ...]]:
    """Query de histórico por cliente con facturación de últimos 12 meses."""
    db_name = Database.validate_sql_identifier(database or Config.DB_NAME, "database")
    table_name = Database.validate_sql_identifier(table or Config.DB_TABLE, "table")
    excluded = Config.EXCLUDED_DOCUMENT_CODES
    for code in excluded:
        Database.validate_sql_identifier(code, "excluded code")
    placeholders = ", ".join(["%s"] * len(excluded))
    query = f"""
        SELECT
            bd.TercerosID AS terceros_id,
            bd.TercerosIdentificacion AS nit,
            MAX(bd.TercerosNombres) AS cliente,
            MIN(CONVERT(date, bd.Fecha)) AS primera_compra,
            MAX(CONVERT(date, bd.Fecha)) AS ultima_compra,
            SUM(bd.Cantidad) AS cantidad,
            SUM(bd.TotalSinIva) AS facturacion,
            SUM(bd.TotalSinIva - bd.ValorCosto) AS ganancia,
            SUM(CASE WHEN bd.Fecha >= %s THEN bd.TotalSinIva ELSE 0 END)
                AS facturacion_12m,
            COUNT(DISTINCT CONVERT(date, bd.Fecha)) AS dias_compra
        FROM [{db_name}].[dbo].[{table_name}] bd
        WHERE bd.DocumentosCodigo NOT IN ({placeholders})
          AND bd.Fecha IS NOT NULL
        GROUP BY bd.TercerosID, bd.TercerosIdentificacion
    """  # nosec B608
    return query, tuple(excluded)


def fetch_customer_history(
    db: Database,
    *,
    hoy: Optional[dt.date] = None,
) -> List[Dict[str, Any]]:
    """Histórico de compras por cliente desde ``banco_datos``."""
    reference = hoy or dt.date.today()
    desde_12m = reference - dt.timedelta(days=365)
    query, excluded = build_customer_history_query()
    with db:
        rows = db.execute_query(query, (desde_12m, *excluded))
    return list(rows or [])


def build_contacts_by_city_query(
    *,
    email_column: Optional[str] = None,
    city_table: Optional[str] = None,
    city_name_column: Optional[str] = None,
    j3_database: Optional[str] = None,
) -> str:
    """Query de contactos de AdmTerceros filtrados por ciudad (LIKE)."""
    import os

    db_name = Database.validate_sql_identifier(
        j3_database or os.getenv("DB_NAME_J3SYSTEM", "J3System"), "j3 database"
    )
    email_select = ""
    if email_column:
        validated_email = Database.validate_sql_identifier(email_column, "email column")
        email_select = f", t.{validated_email} AS email"
    if not (city_table and city_name_column):
        raise ValueError("Se requiere tabla y columna de ciudad para filtrar")
    validated_city_table = Database.validate_sql_identifier(city_table, "city table")
    validated_city_name = Database.validate_sql_identifier(
        city_name_column, "city name column"
    )
    return (
        "SELECT t.TercerosID AS terceros_id, "
        "t.TercerosIdentificacion AS nit, "
        "t.TercerosNombres AS nombre, "
        "t.TercerosCelular AS celular, "
        "t.TercerosTeleFax AS telefono, "
        "t.TercerosDireccion AS direccion, "
        f"c.{validated_city_name} AS ciudad"
        f"{email_select} "
        f"FROM {db_name}.dbo.AdmTerceros t "
        f"LEFT JOIN {db_name}.dbo.{validated_city_table} c "
        "ON t.CiudadID = c.CiudadID "
        f"WHERE c.{validated_city_name} LIKE %s"
    )  # nosec B608


def fetch_contacts_by_city(
    connection: Any,
    city: str,
    *,
    email_column: Optional[str] = None,
    city_table: Optional[str] = None,
    city_name_column: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """Contactos de terceros cuya ciudad inicia con ``city``.

    Devuelve un dict con dos claves por registro (NIT y ``id:<TercerosID>``)
    para maximizar el emparejamiento con ventas y listas manuales.
    """
    if not city:
        return {}
    query = build_contacts_by_city_query(
        email_column=email_column,
        city_table=city_table,
        city_name_column=city_name_column,
    )

    cursor = connection.cursor(as_dict=True)
    contacts: Dict[str, Dict[str, str]] = {}
    try:
        cursor.execute(query, (f"{city}%",))
        for row in cursor.fetchall():
            contact = {
                "cliente": clean_text(row.get("nombre")),
                "celular": clean_text(row.get("celular")),
                "telefono": clean_text(row.get("telefono")),
                "direccion": clean_text(row.get("direccion")),
                "ciudad": clean_text(row.get("ciudad")),
                "email": clean_text(row.get("email")),
            }
            nit = normalize_cedula(row.get("nit"))
            if nit:
                contacts[nit] = contact
            terceros_id = clean_text(row.get("terceros_id"))
            if terceros_id:
                contacts[f"id:{terceros_id}"] = contact
    finally:
        cursor.close()
    return contacts


# =============================================================================
# Construcción de la base de clientes
# =============================================================================


def build_client_base(
    history_rows: Sequence[Mapping[str, Any]],
    contacts: Mapping[str, Mapping[str, str]],
    *,
    hoy: Optional[dt.date] = None,
    inactivity_days: int = 90,
    risk_days: int = 180,
    issues: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Base de clientes DB con contactos validados y score de prioridad.

    Los clientes que solo existen en el cronograma manual ya no entran aquí:
    van a PROSPECTOS (auditoría V-6).
    """
    reference = hoy or dt.date.today()
    inicio_ventana, _ = data_window(history_rows)
    enriched = enrich_customer_metrics(
        history_rows,
        today=reference,
        inactivity_days=inactivity_days,
        risk_days=risk_days,
        inicio_ventana=inicio_ventana,
    )
    meses_ventana = max((reference - (inicio_ventana or reference)).days / 30.44, 1.0)
    extra_placeholders = find_placeholder_emails_by_frequency(
        [
            str(contact.get("email") or "")
            for key, contact in contacts.items()
            if not str(key).startswith("id:")
        ]
    )

    base: List[Dict[str, Any]] = []
    # enrich_customer_metrics preserva el orden: zip con las filas crudas
    # para acceder a columnas que no pasan por el enriquecido (fact. 12m).
    for row, raw in zip(enriched, history_rows):
        nit = normalize_cedula(row.get("nit"))
        cliente = row.get("cliente") or ""
        if es_cliente_generico(nit, cliente):
            continue
        contact = contacts.get(nit)
        if contact is None:
            contact = contacts.get(f"id:{clean_text(row.get('terceros_id'))}")
        if contact is None:
            continue
        raw_email = contact.get("email", "")
        raw_celular = contact.get("celular", "")
        raw_telefono = contact.get("telefono", "")
        raw_ciudad = contact.get("ciudad", "")
        movil = mejor_celular(raw_celular, raw_telefono)
        email = clean_email(raw_email, extra_placeholders=extra_placeholders)
        ciudad = clean_ciudad(raw_ciudad)
        dias = row.get("dias_sin_comprar")
        fact_12m = to_float(raw.get("facturacion_12m"))
        fact_hist = to_float(row.get("facturacion_historica"))
        agenda = (
            AGENDA_VISITA
            if dias is None or dias <= CAP_DIAS_PRESENCIAL
            else AGENDA_LLAMADA
        )
        cliente = row.get("cliente") or contact.get("cliente", "")
        if issues is not None:
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
        base.append(
            {
                "prioridad": None,
                "segmento": row.get("segmento"),
                "agenda": agenda,
                "score": prioridad_score(fact_12m, fact_hist, meses_ventana, dias),
                "cliente": cliente,
                "nit": nit,
                "direccion": contact.get("direccion", ""),
                "ciudad": ciudad,
                "movil": movil or "",
                "telefono": contacto_telefono(contact),
                "email": email or "",
                "canal_preferido": canal_preferido(
                    movil,
                    email,
                    raw_telefono,
                    contact.get("direccion"),
                ),
                "ultima_compra": row.get("ultima_compra"),
                "dias_sin_comprar": dias,
                "facturacion_12m": fact_12m,
                "facturacion_mensual": row.get("facturacion_mensual"),
                "facturacion_historica": fact_hist,
                "ticket_promedio": row.get("ticket_promedio"),
                "costo_estimado": "Sí" if row.get("costo_estimado") else "",
            }
        )
    base.sort(key=lambda row: -to_float(row.get("score")))
    for index, row in enumerate(base, start=1):
        row["prioridad"] = index
    return base


def filter_prospectos_existentes(
    prospectos: Mapping[str, Sequence[Mapping[str, str]]],
    known_names: Sequence[str],
) -> Tuple[Dict[str, List[Dict[str, str]]], List[Dict[str, str]]]:
    """Drop prospects whose normalized name already exists in the customer base.

    Also de-duplicates remaining rows by name and by cellphone (V-12 / V-10).
    """
    known = {normalize_for_match(name) for name in known_names if name}
    filtered: Dict[str, List[Dict[str, str]]] = {}
    excluidos: List[Dict[str, str]] = []
    seen_names: set = set()
    seen_phones: set = set()
    for category, entries in prospectos.items():
        kept: List[Dict[str, str]] = []
        for entry in entries:
            nombre = clean_text(entry.get("nombre"))
            celular = clean_text(entry.get("celular"))
            key = normalize_for_match(nombre)
            if not key:
                continue
            if key in known:
                excluidos.append(
                    {
                        "categoria": category,
                        "nombre": nombre,
                        "celular": celular,
                        "motivo": (
                            "Ya está en BASE DE CLIENTES; no es captación en frío"
                        ),
                    }
                )
                continue
            phone_key = re.sub(r"\D", "", celular)
            if key in seen_names:
                excluidos.append(
                    {
                        "categoria": category,
                        "nombre": nombre,
                        "celular": celular,
                        "motivo": "Prospecto duplicado (mismo nombre)",
                    }
                )
                continue
            if phone_key and phone_key in seen_phones:
                excluidos.append(
                    {
                        "categoria": category,
                        "nombre": nombre,
                        "celular": celular,
                        "motivo": "Prospecto duplicado (mismo celular)",
                    }
                )
                continue
            seen_names.add(key)
            if phone_key:
                seen_phones.add(phone_key)
            kept.append({"nombre": nombre, "celular": celular})
        filtered[category] = kept
    return filtered, excluidos


def contacto_telefono(contact: Mapping[str, str]) -> str:
    """Teléfono fijo legible (omite cuándo es en realidad un móvil)."""
    return telefono_fijo(contact.get("telefono")) or ""


# =============================================================================
# Programación de visitas: cursor + cuota por segmento
# =============================================================================


class VisitScheduler:
    """Reparte cupos diarios por segmento con cursor persistente entre meses."""

    def __init__(self, clients: Sequence[Mapping[str, Any]]):
        def score_key(client: Mapping[str, Any]) -> float:
            return to_float(client.get("score"))

        visitables = [c for c in clients if c.get("agenda") == AGENDA_VISITA]
        self.queues: Dict[str, List[Dict[str, Any]]] = {
            SEGMENT_RIESGO: sorted(
                [c for c in visitables if c.get("segmento") == SEGMENT_RIESGO],
                key=score_key,
                reverse=True,
            ),
            SEGMENT_INACTIVO: sorted(
                [c for c in visitables if c.get("segmento") == SEGMENT_INACTIVO],
                key=score_key,
                reverse=True,
            ),
            SEGMENT_ACTIVO: sorted(
                [c for c in visitables if c.get("segmento") == SEGMENT_ACTIVO],
                key=score_key,
                reverse=True,
            ),
        }

    def pendientes(self) -> int:
        """Clientes aún no programados."""
        return sum(len(queue) for queue in self.queues.values())

    def _siguiente(self, segmento: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Saca el siguiente cliente de la cola indicada (o de cualquiera)."""
        if segmento and self.queues.get(segmento):
            return self.queues[segmento].pop(0)
        for queue in self.queues.values():
            if queue:
                return queue.pop(0)
        return None

    def schedule_month(
        self,
        dates: Sequence[dt.date],
        *,
        visitas_por_dia: int = DEFAULT_VISITAS_POR_DIA,
    ) -> List[Dict[str, Any]]:
        """Programa un mes completo consumiendo las colas (cursor compartido)."""
        program: List[Dict[str, Any]] = []
        for date in dates:
            for slot in range(1, visitas_por_dia + 1):
                if slot <= len(MEZCLA_DIARIA):
                    segmento = MEZCLA_DIARIA[slot - 1]
                else:
                    segmento = None
                client = self._siguiente(segmento)
                if client is None:
                    return program
                program.append(self._row(date, slot, client))
        return program

    @staticmethod
    def _row(date: dt.date, slot: int, client: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "fecha": date,
            "slot": slot,
            "cliente": client.get("cliente", ""),
            "nit": client.get("nit", ""),
            "direccion": client.get("direccion", ""),
            "ciudad": client.get("ciudad", ""),
            "movil": client.get("movil", ""),
            "email": client.get("email", ""),
        }


def build_visit_program(
    clients: Sequence[Mapping[str, Any]],
    dates: Sequence[dt.date],
    *,
    visitas_por_dia: int = DEFAULT_VISITAS_POR_DIA,
    scheduler: Optional[VisitScheduler] = None,
) -> List[Dict[str, Any]]:
    """Asigna clientes a slots de visita por día hábil (ver VisitScheduler)."""
    sched = scheduler or VisitScheduler(clients)
    return sched.schedule_month(dates, visitas_por_dia=visitas_por_dia)


def schedule_programs(
    clients: Sequence[Mapping[str, Any]],
    months: Sequence[Tuple[int, int]],
    *,
    today: dt.date,
    visitas_por_dia: int = DEFAULT_VISITAS_POR_DIA,
    rollover_holidays: bool = True,
    scheduler: Optional[VisitScheduler] = None,
) -> List[Tuple[str, List[Dict[str, Any]]]]:
    """Program months in order, rolling holiday-lost days into the next month.

    Skipping a festivo must not drop the clients that would have filled those
    slots (audit V-13 residue): they continue at the head of the next month.
    """
    sched = scheduler or VisitScheduler(clients)
    programs: List[Tuple[str, List[Dict[str, Any]]]] = []
    lost_days = 0
    for year, month in months:
        start_from = today if (year, month) == (today.year, today.month) else None
        dates = weekday_dates(year, month, start_from=start_from)
        lost_days += holiday_shortfall(year, month, start_from=start_from)
        program = sched.schedule_month(dates, visitas_por_dia=visitas_por_dia)
        programs.append((f"{month_label(year, month)}-{year}", program))
    if rollover_holidays and lost_days and sched.pendientes():
        last_year, last_month = months[-1]
        spill = spillover_working_dates(last_year, last_month, lost_days)
        grouped: Dict[Tuple[int, int], List[dt.date]] = {}
        for date in spill:
            grouped.setdefault((date.year, date.month), []).append(date)
        for (year, month), dates in grouped.items():
            program = sched.schedule_month(dates, visitas_por_dia=visitas_por_dia)
            if program:
                programs.append((f"{month_label(year, month)}-{year}", program))
    return programs


def build_visita_id(asesor: str, fecha: dt.date, nit: str, indice: int) -> str:
    """ID estable de visita para reingestar el control diligenciado (V-11)."""
    slug = re.sub(r"[^A-Za-z0-9]+", "", asesor).upper()[:8] or "ASESOR"
    key = re.sub(r"\D", "", str(nit or "")) or f"IDX{indice}"
    return f"{slug}-{fecha.strftime('%Y%m%d')}-{key}"


# =============================================================================
# Exportación a Excel
# =============================================================================


def export_xlsx(
    output_path: str,
    *,
    asesor: str,
    client_base: Sequence[Mapping[str, Any]],
    programs: Sequence[Tuple[str, Sequence[Mapping[str, Any]]]],
    prospectos: Mapping[str, Sequence[Mapping[str, str]]],
    barrios: Sequence[str],
    ciudad: str,
    hoy: Optional[dt.date] = None,
    quality_issues: Optional[Sequence[Mapping[str, str]]] = None,
) -> None:
    """Escribe el libro completo de visitas del asesor."""
    import xlsxwriter

    from business_analyzer.analysis.excel_helpers import autofit_columns

    reference = hoy or dt.date.today()
    workbook = xlsxwriter.Workbook(output_path)

    title_format = workbook.add_format(
        {
            "bold": True,
            "font_size": 14,
            "bg_color": "#1F4E78",
            "font_color": "white",
            "align": "center",
            "valign": "vcenter",
        }
    )
    subtitle_format = workbook.add_format(
        {
            "bold": True,
            "font_size": 11,
            "bg_color": "#D9E1F2",
            "align": "center",
            "valign": "vcenter",
        }
    )
    header_format = workbook.add_format(
        {"bold": True, "bg_color": "#1F4E78", "font_color": "white"}
    )
    currency_format = workbook.add_format({"num_format": '"$"#,##0'})
    score_format = workbook.add_format({"num_format": "#,##0"})
    date_format = workbook.add_format({"num_format": "yyyy-mm-dd"})
    long_date_format = workbook.add_format(
        {"num_format": 'dddd", "d" de" mmmm" de" yyyy'}
    )
    int_format = workbook.add_format({"num_format": "0"})
    text_format = workbook.add_format({"align": "left"})
    firma_format = workbook.add_format({"bg_color": "#F2F2F2", "border": 1})
    hora_format = workbook.add_format({"num_format": "hh:mm"})

    def banner(worksheet, last_col: int, title: str, subtitle: str) -> None:
        worksheet.merge_range(0, 0, 0, last_col, title, title_format)
        worksheet.merge_range(1, 0, 1, last_col, subtitle, subtitle_format)

    # --- BASE DE CLIENTES ---------------------------------------------------
    worksheet = workbook.add_worksheet("BASE DE CLIENTES")
    banner(
        worksheet,
        len(BASE_COLUMNS) - 1,
        f"BASE DE CLIENTES {ciudad.upper()}",
        (
            f"ASESOR: {asesor} — Generado {reference} — Clientes recurrentes "
            "(visita presencial); score = valor × recencia"
        ),
    )
    headers_row = [BASE_HEADERS[column] for column in BASE_COLUMNS]
    for col_index, header in enumerate(headers_row):
        worksheet.write(2, col_index, header, header_format)
    base_matrix: List[List[Any]] = []
    for row_index, row in enumerate(client_base, start=3):
        values: List[Any] = []
        for column in BASE_COLUMNS:
            value = row.get(column)
            if column in BASE_CURRENCY_COLUMNS:
                values.append(to_float(value))
            elif column == "prioridad":
                values.append(int(to_float(value, row_index - 2)))
            else:
                values.append(value if value is not None else "")
        base_matrix.append(values)
        for col_index, column in enumerate(BASE_COLUMNS):
            value = values[col_index]
            if column == "score":
                worksheet.write_number(
                    row_index, col_index, to_float(value), score_format
                )
            elif column in BASE_CURRENCY_COLUMNS:
                worksheet.write_number(
                    row_index, col_index, to_float(value), currency_format
                )
            elif column == "ultima_compra":
                if isinstance(value, dt.date):
                    worksheet.write_datetime(row_index, col_index, value, date_format)
                else:
                    worksheet.write_blank(row_index, col_index, None, date_format)
            elif column == "dias_sin_comprar":
                if isinstance(value, (int, float)):
                    worksheet.write_number(row_index, col_index, int(value), int_format)
                else:
                    worksheet.write_blank(row_index, col_index, None, int_format)
            elif isinstance(value, str):
                worksheet.write_string(row_index, col_index, value, text_format)
            else:
                worksheet.write(row_index, col_index, value)
    autofit_columns(
        worksheet,
        [headers_row] + base_matrix,
        currency_columns=[
            i for i, c in enumerate(BASE_COLUMNS) if c in BASE_CURRENCY_COLUMNS
        ],
        extra_widths={BASE_COLUMNS.index("cliente"): 40},
    )
    worksheet.autofilter(2, 0, len(client_base) + 2, len(BASE_COLUMNS) - 1)
    worksheet.freeze_panes(3, 3)

    # --- PROGRAMACION <MES> -------------------------------------------------
    control_rows: List[Dict[str, Any]] = []
    for label, program in programs:
        worksheet = workbook.add_worksheet(f"PROGRAMACION {label}")
        headers = ["Fecha", "No."] + [PROGRAM_HEADERS[c] for c in PROGRAM_COLUMNS]
        banner(
            worksheet,
            len(headers) - 1,
            f"PROGRAMACIÓN DE VISITAS {label}",
            f"ASESOR: {asesor}",
        )
        for col_index, header in enumerate(headers):
            worksheet.write(2, col_index, header, header_format)
        matrix: List[List[Any]] = []
        for row_index, row in enumerate(program, start=3):
            fecha = row.get("fecha")
            values = [fecha if isinstance(fecha, dt.date) else "", row.get("slot", 0)]
            values += [clean_text(row.get(c)) for c in PROGRAM_COLUMNS]
            matrix.append(values)
            worksheet.write_datetime(row_index, 0, fecha, long_date_format)
            worksheet.write_number(row_index, 1, int(row.get("slot", 0)), int_format)
            for col_index, column in enumerate(PROGRAM_COLUMNS, start=2):
                worksheet.write_string(
                    row_index, col_index, clean_text(row.get(column)), text_format
                )
            control_rows.append({**row, "mes": label})
        autofit_columns(
            worksheet,
            [headers] + matrix,
            extra_widths={0: 30, PROGRAM_COLUMNS.index("cliente") + 2: 40},
        )
        worksheet.autofilter(2, 0, len(program) + 2, len(headers) - 1)
        worksheet.freeze_panes(3, 2)

    # --- CONTROL DE VISITAS -------------------------------------------------
    worksheet = workbook.add_worksheet("CONTROL DE VISITAS")
    banner(
        worksheet,
        len(CONTROL_HEADERS) - 1,
        "CONTROL DE VISITAS",
        f"ASESOR: {asesor} — Registro diario con firma de quien atiende",
    )
    for col_index, header in enumerate(CONTROL_HEADERS):
        worksheet.write(2, col_index, header, header_format)
    control_matrix: List[List[Any]] = []
    for indice, row in enumerate(control_rows, start=1):
        fecha = row.get("fecha")
        visita_id = build_visita_id(asesor, fecha, row.get("nit", ""), indice)
        values = [
            visita_id,
            fecha if isinstance(fecha, dt.date) else "",
            clean_text(row.get("cliente")),
            clean_text(row.get("nit")),
            clean_text(row.get("direccion")),
            clean_text(row.get("movil")),
            "",
            "",
            "",
            "",
        ]
        control_matrix.append(values)
        excel_row = indice + 2
        worksheet.write_string(excel_row, 0, visita_id, text_format)
        worksheet.write_datetime(excel_row, 1, fecha, long_date_format)
        worksheet.write_string(
            excel_row, 2, clean_text(row.get("cliente")), text_format
        )
        worksheet.write_string(excel_row, 3, clean_text(row.get("nit")), text_format)
        worksheet.write_string(
            excel_row, 4, clean_text(row.get("direccion")), text_format
        )
        worksheet.write_string(excel_row, 5, clean_text(row.get("movil")), text_format)
        worksheet.write_blank(excel_row, 6, None, hora_format)
        worksheet.write_blank(excel_row, 7, None, firma_format)
        worksheet.write_blank(excel_row, 8, None, currency_format)
        worksheet.write_blank(excel_row, 9, None, firma_format)
        worksheet.set_row(excel_row, 26)
    last_control_row = len(control_rows) + 2
    worksheet.data_validation(
        3,
        7,
        last_control_row,
        7,
        {"validate": "list", "source": list(RESULTADO_VISITA_OPTIONS)},
    )
    worksheet.data_validation(
        3,
        8,
        last_control_row,
        8,
        {"validate": "decimal", "criteria": ">=", "value": 0, "ignore_blank": True},
    )
    autofit_columns(
        worksheet,
        [list(CONTROL_HEADERS)] + control_matrix,
        extra_widths={2: 38, 4: 36, 9: 30},
    )
    worksheet.autofilter(2, 0, last_control_row, len(CONTROL_HEADERS) - 1)
    worksheet.freeze_panes(3, 3)

    # --- RUTERO ---------------------------------------------------------------
    worksheet = workbook.add_worksheet("RUTERO")
    banner(
        worksheet,
        4,
        "HOJA DE RUTA — SALIDAS A MUNICIPIOS",
        f"ASESOR: {asesor}",
    )
    worksheet.set_column(0, 0, 34)
    worksheet.set_column(1, 1, 26)
    worksheet.set_column(2, 4, 18)
    row_index = 2
    fecha_out_format = workbook.add_format({"num_format": "yyyy-mm-dd", "border": 1})
    hora_out_format = workbook.add_format({"num_format": "hh:mm", "border": 1})
    for destino_num in range(1, 4):
        for label in (
            f"{destino_num}° DESTINO:",
            "Fecha de salida",
            "Hora de salida",
            "Hora de llegada",
            "Clientes visitados / horario con el cliente",
        ):
            worksheet.write_string(row_index, 0, label, header_format)
            if "Fecha" in label:
                worksheet.write_blank(row_index, 1, None, fecha_out_format)
            elif "Hora" in label:
                worksheet.write_blank(row_index, 1, None, hora_out_format)
            else:
                worksheet.write_blank(row_index, 1, None, firma_format)
            row_index += 1
        for slot in range(1, 5):
            worksheet.write_number(row_index, 0, slot, int_format)
            worksheet.write_blank(row_index, 1, None, firma_format)
            worksheet.write_blank(row_index, 2, None, hora_out_format)
            worksheet.write_blank(row_index, 3, None, firma_format)
            row_index += 1
        worksheet.write_string(row_index, 0, "Hospedaje en destino", header_format)
        worksheet.write_string(row_index, 1, "SI / NO", text_format)
        row_index += 1
        worksheet.write_string(row_index, 0, "Observaciones", header_format)
        worksheet.merge_range(row_index, 1, row_index, 3, "", firma_format)
        worksheet.set_row(row_index, 26)
        row_index += 2
    worksheet.write_string(row_index, 0, "REGRESO A FLORENCIA", header_format)
    worksheet.write_blank(row_index, 1, None, fecha_out_format)

    # --- PROSPECTOS (tabla plana por categoría, audit V-10) -------------------
    worksheet = workbook.add_worksheet("PROSPECTOS")
    banner(
        worksheet,
        4,
        "PROSPECTOS POR CATEGORÍA",
        "Captación — registrar resultado de visita",
    )
    prospect_headers = (
        "Categoría",
        "Nombre comercial",
        "Celular",
        "Visitado",
        "Observaciones",
    )
    for col_index, header in enumerate(prospect_headers):
        worksheet.write(2, col_index, header, header_format)
    prospect_matrix: List[List[Any]] = []
    row_index = 3
    categories = list(PROSPECT_CATEGORIES) + [CATEGORIA_CRONOGRAMA]
    for category in categories:
        for entry in prospectos.get(category, []):
            values = [
                category,
                clean_text(entry.get("nombre")),
                clean_text(entry.get("celular")),
                "",
                "",
            ]
            prospect_matrix.append(values)
            worksheet.write_string(row_index, 0, category, text_format)
            worksheet.write_string(row_index, 1, values[1], text_format)
            worksheet.write_string(row_index, 2, values[2], text_format)
            worksheet.write_blank(row_index, 3, None, firma_format)
            worksheet.write_blank(row_index, 4, None, firma_format)
            row_index += 1
    last_prospect_row = max(row_index - 1, 3)
    worksheet.data_validation(
        3,
        3,
        last_prospect_row,
        3,
        {"validate": "list", "source": list(VISITADO_OPTIONS)},
    )
    autofit_columns(
        worksheet,
        [list(prospect_headers)] + prospect_matrix,
        extra_widths={1: 40, 4: 30},
    )
    worksheet.autofilter(2, 0, last_prospect_row, len(prospect_headers) - 1)
    worksheet.freeze_panes(3, 1)

    # --- ZONAS (barrios, separados de prospectos, audit V-10) -----------------
    worksheet = workbook.add_worksheet("ZONAS")
    banner(
        worksheet,
        2,
        "ZONA NORTE DE FLORENCIA — BARRIOS",
        f"Visitas de barrido por barrio — ASESOR: {asesor}",
    )
    zona_headers = ("Barrio", "Fecha visita", "Observaciones")
    for col_index, header in enumerate(zona_headers):
        worksheet.write(2, col_index, header, header_format)
    for row_index, barrio in enumerate(barrios, start=3):
        worksheet.write_string(row_index, 0, barrio, text_format)
        worksheet.write_blank(row_index, 1, None, date_format)
        worksheet.write_blank(row_index, 2, None, firma_format)
    autofit_columns(
        worksheet,
        [list(zona_headers)] + [[b, "", ""] for b in barrios],
        extra_widths={2: 30},
    )
    worksheet.autofilter(2, 0, len(barrios) + 2, len(zona_headers) - 1)
    worksheet.freeze_panes(3, 1)

    # --- Calidad de datos (segunda auditoría, ítem 4) -----------------------
    issues = list(quality_issues or [])
    calidad = workbook.add_worksheet("Calidad de datos")
    calidad_headers = ("NIT/Cédula", "Cliente", "Campo", "Valor original", "Problema")
    calidad_keys = ("nit", "cliente", "campo", "valor", "problema")
    banner(
        calidad,
        len(calidad_headers) - 1,
        "CALIDAD DE DATOS",
        "Incidencias de contacto, ciudad y cruce de prospectos",
    )
    for col_index, header in enumerate(calidad_headers):
        calidad.write(2, col_index, header, header_format)
    if issues:
        for row_index, issue in enumerate(issues, start=3):
            for col_index, key in enumerate(calidad_keys):
                calidad.write_string(
                    row_index, col_index, str(issue.get(key, "")), text_format
                )
    else:
        calidad.write_string(3, 0, "(sin incidencias detectadas)", text_format)
    autofit_columns(
        calidad,
        [list(calidad_headers)]
        + [[str(issue.get(k, "")) for k in calidad_keys] for issue in issues],
        extra_widths={1: 36, 4: 40},
    )
    last_calidad = max(len(issues) + 2, 3)
    calidad.autofilter(2, 0, last_calidad, len(calidad_headers) - 1)
    calidad.freeze_panes(3, 0)

    workbook.close()
