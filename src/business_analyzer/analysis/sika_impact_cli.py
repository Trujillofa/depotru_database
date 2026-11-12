"""CLI entry point for the Sika Center impact report."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

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
    SIKA_CENTER_DOCUMENT_CODE,
    build_summary,
    data_window,
    enrich_customer_metrics,
    export_xlsx,
    fetch_sika_customers,
    fetch_sika_window,
    fetch_terceros_contacts,
    fetch_terceros_contacts_by_id,
    merge_contact_lookup,
    resolve_city_join,
    resolve_email_column,
    sugerir_umbrales,
    validar_runrate,
)
from config import Config

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports"


def build_database() -> Database:
    """Open a Database using direct credentials or the NCX file."""
    if not Config.has_direct_db_config() and os.path.exists(Config.NCX_FILE_PATH):
        return Database(connection_type=ConnectionType.NAVICAT)
    return Database()


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Lista de contacto Sika Center (FEF): clientes que no han "
            "comprado recientemente, para WhatsApp / email / llamada. "
            "No genera un plan de visitas (eso es depotru-visitas)."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Ruta del .xlsx de salida " "(default: reports/sika_impact_YYYYMMDD.xlsx)"
        ),
    )
    parser.add_argument(
        "--dias-inactividad",
        type=int,
        default=None,
        help=(
            "Días sin comprar para considerar cliente inactivo "
            "(default: automático según ventana de datos)"
        ),
    )
    parser.add_argument(
        "--dias-riesgo",
        type=int,
        default=None,
        help=(
            "Días sin comprar para considerar cliente en riesgo "
            "(default: automático según ventana de datos)"
        ),
    )
    parser.add_argument(
        "--documento",
        default=SIKA_CENTER_DOCUMENT_CODE,
        help=f"Código de documento de la sede (default: {SIKA_CENTER_DOCUMENT_CODE})",
    )
    return parser.parse_args(argv)


def default_output_path() -> Path:
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().strftime("%Y%m%d")
    return DEFAULT_OUTPUT_DIR / f"sika_impact_{stamp}.xlsx"


def print_summary(summary: dict, output_path: Path) -> None:
    print("=== Reporte de impacto Sika Center ===")
    print(f"Clientes históricos      : {summary['total_clientes']}")
    print(f"Activos                  : {summary['clientes_activos']}")
    print(f"En riesgo                : {summary['clientes_en_riesgo']}")
    print(f"Inactivos                : {summary['clientes_inactivos']}")
    print("Facturación histórica    : " f"${summary['facturacion_total']:,.0f}")
    print(
        "Facturación en riesgo    : "
        f"${summary['facturacion_historica_en_riesgo']:,.0f}"
    )
    print(
        "Aporte mensual en riesgo : "
        f"${summary['facturacion_mensual_en_riesgo']:,.0f}"
    )
    print(
        "Facturación de inactivos : "
        f"${summary.get('facturacion_historica_inactivos', 0):,.0f}"
    )
    print(
        "Aporte mensual inactivos : "
        f"${summary.get('facturacion_mensual_inactivos', 0):,.0f}"
    )
    print(
        f"Con móvil / email validados: {summary['con_movil']} / "
        f"{summary['con_email']}"
    )
    print(f"Archivo                  : {output_path}")


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)
    output_path = (
        args.output.expanduser().resolve() if args.output else default_output_path()
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    db = build_database()
    try:
        customers = fetch_sika_customers(db, document_code=args.documento)
        inicio_sede, _ = fetch_sika_window(db, document_code=args.documento)
    except Exception as error:
        print(f"ERROR consultando banco_datos: {error}", file=sys.stderr)
        return 1

    hoy = dt.date.today()
    inicio_clientes, _ = data_window(customers)
    inicio_ventana = inicio_sede or inicio_clientes
    ventana_dias = (hoy - inicio_ventana).days if inicio_ventana else 0
    riesgo_sugerido, inactivo_sugerido = sugerir_umbrales(ventana_dias)
    dias_riesgo = args.dias_riesgo if args.dias_riesgo else riesgo_sugerido
    dias_inactividad = (
        args.dias_inactividad if args.dias_inactividad else inactivo_sugerido
    )
    print(
        f"Ventana de datos: {inicio_ventana} → {hoy} ({ventana_dias} días) | "
        f"umbrales: riesgo {dias_riesgo}d, inactivo {dias_inactividad}d"
    )

    rows = enrich_customer_metrics(
        customers,
        today=hoy,
        # classify_segment(inactivity_days=<corte Activo→Riesgo>,
        #                  risk_days=<corte Riesgo→Inactivo>)
        inactivity_days=dias_riesgo,
        risk_days=dias_inactividad,
        inicio_ventana=inicio_ventana,
    )

    connection = None
    try:
        connection = db.get_j3system_connection()
        email_column = resolve_email_column(connection)
        city_table, city_name_column = resolve_city_join(connection)
        by_nit = fetch_terceros_contacts(
            [row.get("nit") for row in rows],
            connection,
            email_column=email_column,
            city_table=city_table,
            city_name_column=city_name_column,
        )
        by_id = fetch_terceros_contacts_by_id(
            [row.get("terceros_id") for row in rows],
            connection,
            email_column=email_column,
            city_table=city_table,
            city_name_column=city_name_column,
        )
    except Exception as error:
        print(f"ADVERTENCIA: contactos no disponibles: {error}", file=sys.stderr)
        by_nit, by_id = {}, {}
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    quality_issues: List[Dict[str, str]] = []
    merged = merge_contact_lookup(rows, by_nit, by_id, issues=quality_issues)
    try:
        validar_runrate(merged)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    summary = build_summary(
        merged,
        inactivity_days=dias_inactividad,
        risk_days=dias_riesgo,
        inicio_ventana=inicio_ventana,
        corte=hoy,
    )

    export_xlsx(
        merged,
        str(output_path),
        summary=summary,
        document_code=args.documento,
        quality_issues=quality_issues,
        excluded_documents=Config.EXCLUDED_DOCUMENT_CODES,
    )
    print_summary(summary, output_path)
    if quality_issues:
        print(
            f"Incidencias de calidad  : {len(quality_issues)} (hoja Calidad de datos)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
