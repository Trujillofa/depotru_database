"""CLI entry point: generador de visitas para asesores comerciales."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Optional

try:
    # Import core.database BEFORE anything that pulls ``config`` to avoid the
    # config.py <-> business_analyzer.core circular import.
    from business_analyzer.core.database import ConnectionType, Database
except ImportError:  # pragma: no cover - direct execution fallback
    src_path = Path(__file__).resolve().parents[2]
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from business_analyzer.core.database import ConnectionType, Database

from business_analyzer.analysis.sika_impact import (
    resolve_city_join,
    resolve_email_column,
)
from business_analyzer.analysis.visitas_asesor import (
    AGENDA_VISITA,
    CATEGORIA_CRONOGRAMA,
    DEFAULT_ASESOR,
    DEFAULT_CIUDAD,
    DEFAULT_VISITAS_POR_DIA,
    PROSPECT_CATEGORIES,
    build_client_base,
    export_xlsx,
    fetch_contacts_by_city,
    fetch_customer_history,
    filter_prospectos_existentes,
    month_label,
    parse_barrios,
    parse_cronograma_clients,
    parse_prospectos,
    read_sheet_rows,
    schedule_programs,
)
from config import Config

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports"
DEFAULT_CRONOGRAMA = REPO_ROOT / "CRONOGRAMA VISITAS.xlsx"
DEFAULT_PROGRAMACION = REPO_ROOT / "PROGRAMACION Y CONTROL DE VISITAS ARMANDO.xlsx"


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Libro de visitas de un asesor para clientes recurrentes "
            "(historial de compra en la ciudad): programación mensual, "
            "control con firma, rutero y prospectos. No es el reporte de "
            "impacto Sika (eso es depotru-sika-impact)."
        )
    )
    parser.add_argument(
        "--asesor",
        default=DEFAULT_ASESOR,
        help=f"Nombre del asesor (default: {DEFAULT_ASESOR})",
    )
    parser.add_argument(
        "--ciudad",
        default=DEFAULT_CIUDAD,
        help=f"Ciudad para filtrar clientes (default: {DEFAULT_CIUDAD})",
    )
    parser.add_argument(
        "--visitas-por-dia",
        type=int,
        default=DEFAULT_VISITAS_POR_DIA,
        help=f"Visitas por día hábil (default: {DEFAULT_VISITAS_POR_DIA})",
    )
    parser.add_argument(
        "--dias-inactividad",
        type=int,
        default=90,
        help="Días sin comprar para segmento inactivo (default: 90)",
    )
    parser.add_argument(
        "--dias-riesgo",
        type=int,
        default=180,
        help="Días sin comprar para segmento en riesgo (default: 180)",
    )
    parser.add_argument(
        "--meses",
        default=None,
        help=(
            "Meses a programar en formato YYYY-MM separados por coma "
            "(default: mes actual desde hoy y mes siguiente)"
        ),
    )
    parser.add_argument(
        "--cronograma",
        type=Path,
        default=DEFAULT_CRONOGRAMA,
        help="Ruta del Excel CRONOGRAMA VISITAS fuente",
    )
    parser.add_argument(
        "--programacion",
        type=Path,
        default=DEFAULT_PROGRAMACION,
        help="Ruta del Excel PROGRAMACION Y CONTROL DE VISITAS fuente",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Ruta del .xlsx de salida (default: reports/VISITAS <ASESOR> ...)",
    )
    return parser.parse_args(argv)


def build_database() -> Database:
    """Open a Database using direct credentials or the NCX file."""
    import os

    if not Config.has_direct_db_config() and os.path.exists(Config.NCX_FILE_PATH):
        return Database(connection_type=ConnectionType.NAVICAT)
    return Database()


def resolve_months(spec: Optional[str], today: dt.date) -> list:
    if spec:
        months = []
        for token in spec.split(","):
            year, month = token.strip().split("-")
            months.append((int(year), int(month)))
        return months
    if today.month == 12:
        return [(today.year, 12), (today.year + 1, 1)]
    return [(today.year, today.month), (today.year, today.month + 1)]


def default_output_path(asesor: str, months: list) -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = asesor.strip().split()[0].upper()
    labels = [month_label(year, month) for year, month in months]
    years = sorted({year for year, _ in months})
    year_text = "-".join(str(year) for year in years)
    name = f"VISITAS {slug} {'-'.join(labels)} {year_text}.xlsx"
    return DEFAULT_OUTPUT_DIR / name


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    today = dt.date.today()

    cronograma_path = args.cronograma.expanduser().resolve()
    programacion_path = args.programacion.expanduser().resolve()
    if not cronograma_path.exists():
        print(f"ERROR: no existe {cronograma_path}", file=sys.stderr)
        return 1
    if not programacion_path.exists():
        print(f"ERROR: no existe {programacion_path}", file=sys.stderr)
        return 1

    months = resolve_months(args.meses, today)
    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else default_output_path(args.asesor, months)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("=== Generador de visitas —", args.asesor, "===")
    print("Leyendo archivos fuente...")
    prospectos = parse_prospectos(
        {
            category: read_sheet_rows(str(cronograma_path), category)
            for category in PROSPECT_CATEGORIES
        }
    )
    file_clients = parse_cronograma_clients(
        read_sheet_rows(str(cronograma_path), "MARZO")
    )
    barrios = parse_barrios(read_sheet_rows(str(programacion_path), "VISITAS-ARMANDO"))
    # Los clientes sin histórico de compras van a PROSPECTOS, no a la BASE
    # (auditoría V-6): no contaminan los conteos por segmento.
    prospectos[CATEGORIA_CRONOGRAMA] = [
        {"nombre": client.get("cliente", ""), "celular": ""} for client in file_clients
    ]
    print(
        f"Prospectos: {sum(len(v) for v in prospectos.values())} | "
        f"Clientes del cronograma: {len(file_clients)} | "
        f"Barrios: {len(barrios)}"
    )

    db = build_database()
    try:
        history = fetch_customer_history(db, hoy=today)
    except Exception as error:
        print(f"ERROR consultando banco_datos: {error}", file=sys.stderr)
        return 1
    print(f"Clientes con histórico de compras: {len(history)}")

    connection = None
    try:
        connection = db.get_j3system_connection()
        email_column = resolve_email_column(connection)
        city_table, city_name_column = resolve_city_join(connection)
        contacts = fetch_contacts_by_city(
            connection,
            args.ciudad,
            email_column=email_column,
            city_table=city_table,
            city_name_column=city_name_column,
        )
    except Exception as error:
        print(f"ERROR consultando contactos: {error}", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
    print(f"Terceros en {args.ciudad}: {len(contacts) // 2}")

    quality_issues: list = []
    client_base = build_client_base(
        history,
        contacts,
        hoy=today,
        inactivity_days=args.dias_inactividad,
        risk_days=args.dias_riesgo,
        issues=quality_issues,
    )
    known_names = [row.get("cliente", "") for row in client_base]
    known_names.extend(row.get("cliente", "") for row in history)
    prospectos, excluidos = filter_prospectos_existentes(prospectos, known_names)
    for entry in excluidos:
        quality_issues.append(
            {
                "nit": "",
                "cliente": entry.get("nombre", ""),
                "campo": "Prospecto",
                "valor": entry.get("categoria", ""),
                "problema": entry.get("motivo", ""),
            }
        )
    print(
        f"Prospectos tras cruce con BASE: "
        f"{sum(len(v) for v in prospectos.values())} "
        f"(excluidos {len(excluidos)})"
    )
    programables = sum(1 for row in client_base if row["agenda"] == AGENDA_VISITA)
    llamada = len(client_base) - programables
    print(
        f"Base de clientes {args.ciudad}: {len(client_base)} "
        f"({programables} visita presencial, {llamada} llamada/WhatsApp)"
    )

    # Un solo scheduler para todos los meses: el cursor continúa la cola
    # entre meses (V-1) y los días perdidos por festivo ruedan al mes
    # siguiente en vez de recortar la cola (residuo V-13).
    programs = schedule_programs(
        client_base,
        months,
        today=today,
        visitas_por_dia=args.visitas_por_dia,
    )
    programados_total = set()
    for label, program in programs:
        programados_total.update(
            (row.get("nit") or row.get("cliente", "")) for row in program
        )
        print(f"Programación {label}: {len(program)} visitas")

    print(
        f"Cobertura total: {len(programados_total)} clientes únicos de "
        f"{len(client_base)} ({len(programados_total) / max(len(client_base), 1):.0%})"
    )
    export_xlsx(
        str(output_path),
        asesor=args.asesor,
        client_base=client_base,
        programs=programs,
        prospectos=prospectos,
        barrios=barrios,
        ciudad=args.ciudad,
        hoy=today,
        quality_issues=quality_issues,
    )
    print(f"Archivo: {output_path}")
    if quality_issues:
        print(f"Incidencias de calidad: {len(quality_issues)} (hoja Calidad de datos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
