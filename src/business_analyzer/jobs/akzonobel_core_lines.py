"""AkzoNobel Core Lines — zero-penetration SKUs by territory (Phase 3 / #65).

Read-only report. Core Lines membership comes from an editable YAML/JSON/CSV
file (shipped list is a labelled synthetic placeholder). Territory defaults
to the commercial owner already used by manager reports and presupuesto:
``vendedor_codigo`` + ``VendedorFactura``. ``ciudad`` / ``departamento`` are
documented banco_datos alternatives and are configurable.

Sales SQL is SELECT-only and excludes test documents via the canonical list.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from business_analyzer.core.config import Config, Settings, get_settings
from depotru_kernel.documents import (
    CANONICAL_EXCLUDED_DOCUMENT_CODES,
    excluded_document_sql_in_list,
)

SalesLoader = Callable[[str, str, "TerritoryMapping"], Sequence[Mapping[str, Any]]]

ALLOWED_DIMENSION_FIELDS = frozenset(
    {
        "vendedor_codigo",
        "VendedorFactura",
        "ciudad",
        "departamento",
    }
)
DIMENSION_PRESETS: dict[str, tuple[str, str]] = {
    "vendedor": ("vendedor_codigo", "VendedorFactura"),
    "vendedor_codigo": ("vendedor_codigo", "VendedorFactura"),
    "ciudad": ("ciudad", "ciudad"),
    "departamento": ("departamento", "departamento"),
}

_FORMAT_NUMBER = None


def format_number(value: Any, column_name: str = "") -> str:
    """Load ``ai.formatting.format_number`` without importing ``ai.__init__``."""
    global _FORMAT_NUMBER
    if _FORMAT_NUMBER is None:
        path = Path(__file__).resolve().parents[1] / "ai" / "formatting.py"
        spec = importlib.util.spec_from_file_location(
            "depotru_formatting_standalone", path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"No se pudo cargar {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _FORMAT_NUMBER = module.format_number
    text = _FORMAT_NUMBER(value, column_name)
    if text.startswith("$-"):
        return "-$" + text[2:]
    return text


@dataclass(frozen=True)
class TerritoryMapping:
    key_field: str
    label_field: str

    def __post_init__(self) -> None:
        for value in (self.key_field, self.label_field):
            if value not in ALLOWED_DIMENSION_FIELDS:
                allowed = ", ".join(sorted(ALLOWED_DIMENSION_FIELDS))
                raise ValueError(
                    f"Campo de territorio no documentado: {value}. "
                    f"Use uno de: {allowed}"
                )


@dataclass(frozen=True)
class CoreSku:
    sku: str
    name: str


@dataclass(frozen=True)
class CoreLinesConfig:
    placeholder: bool
    territory: TerritoryMapping
    skus: tuple[CoreSku, ...]


PLACEHOLDER_LIVE_ERROR = (
    "La lista de líneas núcleo sigue marcada como marcador sintético "
    "(placeholder: true). No se consulta la base de datos. "
    "Use --synthetic para una prueba, o edite el YAML, ponga "
    "placeholder: false y cargue los SKUs reales."
)
CSV_FORMULA_PREFIXES = frozenset({"=", "+", "-", "@", "\t", "\r"})


@dataclass(frozen=True)
class GapRow:
    territory_key: str
    territory_label: str
    territory_revenue: float
    sku: str
    sku_name: str
    company_sku_revenue: float
    territory_rank: int


@dataclass
class CoreLinesReport:
    start_date: date
    end_date: date
    config: CoreLinesConfig
    gaps: list[GapRow] = field(default_factory=list)


@dataclass(frozen=True)
class WriteResult:
    html_path: Path
    csv_path: Path


def last_complete_month(run_date: date) -> tuple[date, date]:
    """Previous completed calendar month (same idea as monthly manager reports)."""
    first_this_month = run_date.replace(day=1)
    end = first_this_month - timedelta(days=1)
    start = end.replace(day=1)
    return start, end


def packaged_config_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "akzonobel_core_lines.yaml"


def resolve_config_path(
    explicit: str | Path | None = None,
    settings: Optional[Settings] = None,
) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    cfg = settings or get_settings()
    override = (cfg.AKZONOBEL_CORE_LINES_CONFIG or "").strip()
    if override:
        return Path(override).expanduser()
    return packaged_config_path()


def _parse_skus(raw: Any) -> tuple[CoreSku, ...]:
    items: list[CoreSku] = []
    for row in raw or []:
        if isinstance(row, str):
            sku = row.strip()
            name = sku
        else:
            sku = str(row.get("sku") or "").strip()
            name = str(row.get("name") or sku).strip()
        if sku:
            items.append(CoreSku(sku=sku, name=name or sku))
    return tuple(items)


def _config_from_mapping(data: Mapping[str, Any]) -> CoreLinesConfig:
    territory_raw = data.get("territory") or {}
    mapping = TerritoryMapping(
        key_field=str(territory_raw.get("key_field") or "vendedor_codigo").strip(),
        label_field=str(territory_raw.get("label_field") or "VendedorFactura").strip(),
    )
    skus = _parse_skus(data.get("skus"))
    if not skus:
        raise ValueError("La lista de SKUs de líneas núcleo no puede estar vacía.")
    return CoreLinesConfig(
        placeholder=bool(data.get("placeholder", True)),
        territory=mapping,
        skus=skus,
    )


def load_core_lines_config(path: Path | str) -> CoreLinesConfig:
    """Load YAML, JSON, or SKU CSV. CSV uses the default vendedor mapping."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(str(config_path))
    suffix = config_path.suffix.lower()
    text = config_path.read_text(encoding="utf-8")
    if suffix == ".json":
        data = json.loads(text)
        return _config_from_mapping(data)
    if suffix == ".csv":
        reader = csv.DictReader(io.StringIO(text))
        rows = [
            {"sku": row.get("sku") or row.get("SKU"), "name": row.get("name") or ""}
            for row in reader
        ]
        return _config_from_mapping(
            {
                "placeholder": True,
                "territory": {
                    "key_field": "vendedor_codigo",
                    "label_field": "VendedorFactura",
                },
                "skus": rows,
            }
        )
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - PyYAML is in the lockfile
        raise RuntimeError(
            "PyYAML es necesario para leer el YAML de líneas núcleo. "
            "Pase un .json o .csv, o instale las dependencias del proyecto."
        ) from exc
    try:
        loaded = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise ValueError(
            "El archivo YAML de líneas núcleo no es válido. "
            "Revise la sintaxis (indentación, comillas y listas)."
        ) from exc
    if not isinstance(loaded, Mapping):
        raise ValueError("El archivo de configuración debe ser un mapeo YAML/JSON.")
    return _config_from_mapping(loaded)


_EXCLUDED_PRODUCT_NAMES: tuple[str, ...] | None = None


def excluded_product_names() -> tuple[str, ...]:
    """Same names as ``SalesQueryRunner`` / manager_report helpers."""
    global _EXCLUDED_PRODUCT_NAMES
    if _EXCLUDED_PRODUCT_NAMES is None:
        path = (
            Path(__file__).resolve().parents[1]
            / "analysis"
            / "manager_report"
            / "helpers.py"
        )
        spec = importlib.util.spec_from_file_location("depotru_mr_helpers", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"No se pudo cargar {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _EXCLUDED_PRODUCT_NAMES = tuple(
            str(name) for name in module.EXCLUDED_PRODUCT_NAMES
        )
    return _EXCLUDED_PRODUCT_NAMES


def _is_positive_sale(row: Mapping[str, Any]) -> bool:
    revenue = float(row.get("revenue") or 0)
    quantity = float(row.get("quantity") or 0)
    return revenue > 0 and quantity > 0


def _is_excluded_product_name(name: object) -> bool:
    cleaned = str(name or "").strip().upper()
    if not cleaned:
        return False
    return cleaned in {item.strip().upper() for item in excluded_product_names()}


def find_zero_penetration(
    sales_rows: Sequence[Mapping[str, Any]],
    config: CoreLinesConfig,
) -> list[GapRow]:
    """Core Lines SKUs with no positive sales in a territory that sold others."""
    core = {item.sku.strip().upper(): item for item in config.skus}
    territory_revenue: dict[str, float] = {}
    territory_label: dict[str, str] = {}
    sold: dict[str, set[str]] = {}
    sold_other: set[str] = set()
    company_sku_revenue: dict[str, float] = {}

    for row in sales_rows:
        key = str(row.get("territory_key") or "").strip()
        if not key:
            continue
        if _is_excluded_product_name(row.get("product_name")):
            continue
        if not _is_positive_sale(row):
            continue
        sku_code = str(row.get("sku") or "").strip()
        revenue = float(row.get("revenue") or 0)
        territory_revenue[key] = territory_revenue.get(key, 0.0) + revenue
        label = str(row.get("territory_label") or key).strip() or key
        territory_label[key] = label
        if sku_code:
            sku_key = sku_code.upper()
            sold.setdefault(key, set()).add(sku_key)
            company_sku_revenue[sku_key] = (
                company_sku_revenue.get(sku_key, 0.0) + revenue
            )
            if sku_key not in core:
                sold_other.add(key)

    ranked = sorted(
        (
            (key, revenue)
            for key, revenue in territory_revenue.items()
            if key in sold_other
        ),
        key=lambda item: (-item[1], item[0]),
    )
    rank_by_key = {key: index + 1 for index, (key, _rev) in enumerate(ranked)}

    gaps: list[GapRow] = []
    for key, revenue in ranked:
        missing = [
            core[sku_key] for sku_key in core if sku_key not in sold.get(key, set())
        ]
        if not missing:
            continue
        missing.sort(
            key=lambda item: (-company_sku_revenue.get(item.sku.upper(), 0.0), item.sku)
        )
        for core_item in missing:
            gaps.append(
                GapRow(
                    territory_key=key,
                    territory_label=territory_label.get(key, key),
                    territory_revenue=revenue,
                    sku=core_item.sku,
                    sku_name=core_item.name,
                    company_sku_revenue=company_sku_revenue.get(
                        core_item.sku.upper(), 0.0
                    ),
                    territory_rank=rank_by_key[key],
                )
            )
    return gaps


def build_report(
    sales_rows: Sequence[Mapping[str, Any]],
    config: CoreLinesConfig,
    start_date: date,
    end_date: date,
) -> CoreLinesReport:
    return CoreLinesReport(
        start_date=start_date,
        end_date=end_date,
        config=config,
        gaps=find_zero_penetration(sales_rows, config),
    )


def synthetic_sales_rows(
    config: Optional[CoreLinesConfig] = None,
) -> list[dict[str, Any]]:
    """Demo rows only — fictional names and AKZO-DEMO-* SKUs."""
    _ = config
    return [
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "AKZO-DEMO-001",
            "product_name": "Pintura demo línea núcleo 1",
            "revenue": 800_000,
            "quantity": 8,
            "proveedor": "AKZO-DEMO-VENDOR",
            "marca": "AKZO-DEMO-MARCA",
        },
        {
            "territory_key": "01",
            "territory_label": "Ana Demo",
            "sku": "SKU-OTRO-001",
            "product_name": "Cemento demo",
            "revenue": 4_200_000,
            "quantity": 40,
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        },
        {
            "territory_key": "02",
            "territory_label": "Luis Demo",
            "sku": "SKU-OTRO-002",
            "product_name": "Broca demo",
            "revenue": 1_200_000,
            "quantity": 12,
            "proveedor": "OTRO-DEMO",
            "marca": "OTRO",
        },
    ]


def build_synthetic_report(
    run_date: date,
    config: Optional[CoreLinesConfig] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> CoreLinesReport:
    cfg = config or load_core_lines_config(packaged_config_path())
    if start_date is None or end_date is None:
        start_date, end_date = last_complete_month(run_date)
    return build_report(synthetic_sales_rows(cfg), cfg, start_date, end_date)


def build_live_report(
    start_date: date,
    end_date: date,
    config: CoreLinesConfig,
    sales_loader: Optional[SalesLoader] = None,
) -> CoreLinesReport:
    if config.placeholder and sales_loader is None:
        raise ValueError(PLACEHOLDER_LIVE_ERROR)
    loader = sales_loader or fetch_territory_sku_sales
    rows = loader(start_date.isoformat(), end_date.isoformat(), config.territory)
    return build_report(rows, config, start_date, end_date)


def _assert_readonly_sql(sql: str) -> None:
    lowered = f" {sql.lower()} "
    for banned in (
        " insert ",
        " update ",
        " delete ",
        " merge ",
        " drop ",
        " alter ",
        " truncate ",
        " allow_write ",
    ):
        if banned in lowered:
            raise ValueError("Solo se permite SQL de lectura.")
    if not sql.lstrip().upper().startswith("SELECT"):
        raise ValueError("La consulta de territorio debe comenzar con SELECT.")


def build_territory_sku_sql(
    mapping: TerritoryMapping,
    start_date: str,
    end_date: str,
) -> tuple[str, tuple[Any, ...]]:
    """Read-only sales-by-territory/SKU query on ``banco_datos`` only."""
    from business_analyzer.core.database import Database

    db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
    table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
    key_field = Database.validate_sql_identifier(mapping.key_field, "territorio")
    label_field = Database.validate_sql_identifier(mapping.label_field, "territorio")
    excluded = list(Config.EXCLUDED_DOCUMENT_CODES)
    if tuple(excluded) != CANONICAL_EXCLUDED_DOCUMENT_CODES:
        excluded = list(CANONICAL_EXCLUDED_DOCUMENT_CODES)
    for code in excluded:
        Database.validate_sql_identifier(code, "excluded code")
    placeholders = ", ".join(["%s"] * len(excluded))
    product_names = tuple(name.upper() for name in excluded_product_names())
    product_clauses = " ".join(
        "AND UPPER(LTRIM(RTRIM(bd.ArticulosNombre))) <> %s" for _ in product_names
    )
    sql = f"""
        SELECT
            LTRIM(RTRIM(bd.{key_field})) AS territory_key,
            MAX(LTRIM(RTRIM(bd.{label_field}))) AS territory_label,
            LTRIM(RTRIM(bd.ArticulosCodigo)) AS sku,
            MAX(bd.ArticulosNombre) AS product_name,
            SUM(bd.TotalSinIva) AS revenue,
            SUM(bd.Cantidad) AS quantity
        FROM [{db_name}].[dbo].[{table_name}] bd
        WHERE bd.Fecha BETWEEN %s AND %s
          AND bd.DocumentosCodigo NOT IN ({placeholders})
          AND bd.Cantidad > 0
          AND bd.TotalSinIva > 0
          AND bd.{key_field} IS NOT NULL
          AND LTRIM(RTRIM(bd.{key_field})) <> ''
          AND bd.ArticulosCodigo IS NOT NULL
          AND LTRIM(RTRIM(bd.ArticulosCodigo)) <> ''
          {product_clauses}
        GROUP BY LTRIM(RTRIM(bd.{key_field})), LTRIM(RTRIM(bd.ArticulosCodigo))
    """  # nosec B608
    _assert_readonly_sql(sql)
    params: tuple[Any, ...] = (start_date, end_date, *excluded, *product_names)
    return sql, params


def _open_database() -> Any:
    from business_analyzer.core.database import Database

    return Database()


def fetch_territory_sku_sales(
    start_date: str,
    end_date: str,
    mapping: TerritoryMapping,
) -> list[dict[str, Any]]:
    sql, params = build_territory_sku_sql(mapping, start_date, end_date)
    try:
        db = _open_database()
        with db:
            rows = db.execute_query(sql, params)
    except Exception as exc:
        raise RuntimeError(
            "No se pudo leer la base de datos (consulta de solo lectura)."
        ) from exc
    return list(rows or [])


def _html(value: Any) -> str:
    return escape("" if value is None else str(value), quote=True)


def render_html(report: CoreLinesReport) -> str:
    excluded = excluded_document_sql_in_list()
    mapping = report.config.territory
    gap_rows = []
    for gap in report.gaps:
        potential = format_number(gap.territory_revenue, "TotalSinIva")
        company = format_number(gap.company_sku_revenue, "TotalSinIva")
        gap_rows.append(
            "<tr>"
            f"<td>{_html(gap.territory_rank)}</td>"
            f"<td>{_html(gap.territory_label)}</td>"
            f"<td>{_html(gap.territory_key)}</td>"
            f"<td>{_html(gap.sku)}</td>"
            f"<td>{_html(gap.sku_name)}</td>"
            f"<td>{_html(potential)}</td>"
            f"<td>{_html(company)}</td>"
            "</tr>"
        )
    if not gap_rows:
        gap_rows.append(
            "<tr><td colspan='7'>Sin SKUs de líneas núcleo sin penetración "
            "en el periodo.</td></tr>"
        )

    placeholder_note = ""
    if report.config.placeholder:
        placeholder_note = (
            "<p class='note'><strong>Marcador sintético:</strong> la lista de "
            "SKUs es de demostración (<code>AKZO-DEMO-*</code>). No son "
            "códigos reales de catálogo. Edite "
            "<code>akzonobel_core_lines.yaml</code> y ponga "
            "<code>placeholder: false</code> antes de un corrido en vivo.</p>"
        )

    return f"""<!DOCTYPE html>
<html lang="es-CO">
<head>
  <meta charset="utf-8">
  <title>Líneas núcleo AkzoNobel — SKUs sin penetración</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; color: #1f2933; margin: 24px; }}
    h1, h2 {{ color: #102a43; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .note {{ background: #fff8e1; padding: 12px; border-left: 4px solid #f0b429; }}
  </style>
</head>
<body>
  <h1>Líneas núcleo AkzoNobel — SKUs sin penetración por territorio</h1>
  {placeholder_note}
  <p>
    Periodo: {_html(report.start_date.isoformat())} a
    {_html(report.end_date.isoformat())}.
    Dimensión: <code>{_html(mapping.key_field)}</code> /
    <code>{_html(mapping.label_field)}</code>
    (dueño comercial de <code>manager_report</code> /
    <code>presupuesto_vendedores</code> por defecto).
  </p>
  <p>
    Un territorio entra al ranking si vendió <em>otros</em> productos en el
    periodo y no vendió el SKU de líneas núcleo. El potencial es la
    suma de las líneas positivas del territorio
    (<code>TotalSinIva &gt; 0</code> y <code>Cantidad &gt; 0</code>);
    las devoluciones no se netean.
  </p>
  <table>
    <thead>
      <tr>
        <th>Rango</th>
        <th>Territorio</th>
        <th>Código</th>
        <th>SKU</th>
        <th>Producto</th>
        <th>Ventas territorio</th>
        <th>Ventas SKU en empresa</th>
      </tr>
    </thead>
    <tbody>
      {''.join(gap_rows)}
    </tbody>
  </table>
  <p>
    Consultas de ventas en <code>banco_datos</code> excluyen
    <code>DocumentosCodigo NOT IN ({_html(excluded)})</code>.
    Solo lectura; no hay SQL de escritura.
  </p>
</body>
</html>
"""


def csv_guard_cell(value: Any) -> str:
    """Prefix formula-like *strings* so Excel/LibreOffice will not execute them.

    Numbers (including negatives) are written as-is. Only text cells that
    start with ``= + - @`` / tab / CR get a leading quote.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        text = str(value)
    elif isinstance(value, (int, float, Decimal)):
        return str(value)
    else:
        text = str(value)
    if text[:1] in CSV_FORMULA_PREFIXES:
        return "'" + text
    return text


def render_csv(report: CoreLinesReport) -> str:
    buffer = io.StringIO()
    fieldnames = [
        "RangoPotencial",
        "Territorio",
        "CodigoTerritorio",
        "SKU",
        "Producto",
        "VentasTerritorio",
        "VentasSKUEmpresa",
        "PeriodoInicio",
        "PeriodoFin",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for gap in report.gaps:
        writer.writerow(
            {
                "RangoPotencial": csv_guard_cell(gap.territory_rank),
                "Territorio": csv_guard_cell(gap.territory_label),
                "CodigoTerritorio": csv_guard_cell(gap.territory_key),
                "SKU": csv_guard_cell(gap.sku),
                "Producto": csv_guard_cell(gap.sku_name),
                "VentasTerritorio": csv_guard_cell(gap.territory_revenue),
                "VentasSKUEmpresa": csv_guard_cell(gap.company_sku_revenue),
                "PeriodoInicio": csv_guard_cell(report.start_date.isoformat()),
                "PeriodoFin": csv_guard_cell(report.end_date.isoformat()),
            }
        )
    return buffer.getvalue()


def write_report(report: CoreLinesReport, output_dir: Path) -> WriteResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"akzonobel_core_lines_{report.end_date.isoformat()}"
    html_path = output_dir / f"{stem}.html"
    csv_path = output_dir / f"{stem}.csv"
    html_path.write_text(render_html(report), encoding="utf-8")
    csv_path.write_text(render_csv(report), encoding="utf-8-sig")
    return WriteResult(html_path=html_path, csv_path=csv_path)


def apply_dimension(
    config: CoreLinesConfig,
    dimension: str,
) -> CoreLinesConfig:
    if not dimension:
        return config
    key = dimension.strip()
    if key not in DIMENSION_PRESETS:
        allowed = ", ".join(sorted(DIMENSION_PRESETS))
        raise ValueError(f"Dimensión de territorio no válida: {key}. Use: {allowed}")
    key_field, label_field = DIMENSION_PRESETS[key]
    return CoreLinesConfig(
        placeholder=config.placeholder,
        territory=TerritoryMapping(key_field=key_field, label_field=label_field),
        skus=config.skus,
    )


def parse_iso_date(raw: str, flag: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"Fecha no válida en {flag}: '{raw}'. "
            "Use el formato ISO 8601 AAAA-MM-DD."
        ) from exc


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Informe de líneas núcleo AkzoNobel: SKUs sin penetración por "
            "territorio. Solo lectura. El YAML enviado es un marcador sintético."
        )
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Prueba con datos sintéticos (sin base de datos).",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Carpeta para HTML/CSV (por defecto: OUTPUT_DIR/akzonobel_core_lines).",
    )
    parser.add_argument(
        "--run-date",
        default="",
        help="Fecha de referencia, ISO 8601 AAAA-MM-DD (periodo: mes anterior).",
    )
    parser.add_argument(
        "--start-date",
        default="",
        help="Inicio del periodo, ISO 8601 AAAA-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        default="",
        help="Fin del periodo, ISO 8601 AAAA-MM-DD.",
    )
    parser.add_argument(
        "--config",
        default="",
        help="Lista YAML/JSON/CSV de líneas núcleo (por defecto: archivo sintético).",
    )
    parser.add_argument(
        "--dimension",
        default="",
        help=(
            "Dimensión de territorio: vendedor (predeterminada), "
            "ciudad, departamento."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    try:
        run_date = (
            parse_iso_date(args.run_date, "--run-date")
            if args.run_date
            else date.today()
        )
        if args.start_date and args.end_date:
            start_date = parse_iso_date(args.start_date, "--start-date")
            end_date = parse_iso_date(args.end_date, "--end-date")
        else:
            start_date, end_date = last_complete_month(run_date)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    try:
        config = load_core_lines_config(resolve_config_path(args.config or None))
        config = apply_dimension(config, args.dimension)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"❌ No se pudo leer la config de líneas núcleo: {exc}", file=sys.stderr)
        return 1

    if args.synthetic:
        report = build_synthetic_report(
            run_date=run_date,
            config=config,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        if config.placeholder:
            print(f"❌ {PLACEHOLDER_LIVE_ERROR}", file=sys.stderr)
            return 1
        try:
            report = build_live_report(
                start_date=start_date,
                end_date=end_date,
                config=config,
            )
        except RuntimeError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser()
    else:
        output_dir = Config.ensure_output_dir() / "akzonobel_core_lines"

    result = write_report(report, output_dir)
    print(f"Informe HTML: {result.html_path}")
    print(f"Informe CSV: {result.csv_path}")
    print("Solo lectura: no se escribió en la base de datos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
