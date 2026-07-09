"""Weekly KPI control board generation for API and sidebar UI."""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from business_analyzer.ai.base import Config

REPO_ROOT = Path(__file__).resolve().parents[3]


def last_completed_iso_week(*, today: Optional[date] = None) -> Tuple[int, int]:
    """Return (ISO year, ISO week) for the last completed Mon–Sun window."""
    ref = today or date.today()
    current_week_monday = ref - timedelta(days=ref.weekday())
    previous_week_sunday = current_week_monday - timedelta(days=1)
    iso_year, iso_week, _ = previous_week_sunday.isocalendar()
    return iso_year, iso_week


def iso_week_date_range(iso_year: int, iso_week: int) -> Tuple[str, str]:
    """Return inclusive (start_date, end_date) ISO strings for an ISO week."""
    start = date.fromisocalendar(iso_year, iso_week, 1)
    end = date.fromisocalendar(iso_year, iso_week, 7)
    return start.isoformat(), end.isoformat()


def iso_weeks_in_year(iso_year: int) -> int:
    """Number of ISO weeks in ``iso_year`` (52 or 53)."""
    return date(iso_year, 12, 28).isocalendar()[1]


def kpi_board_output_basename(iso_year: int, iso_week: int) -> str:
    return f"KPI_CONTROL_BOARD_{iso_year}_W{iso_week:02d}.md"


def _import_generate_kpi_control_board():
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from scripts.utils.generate_kpi_control_board import (  # noqa: WPS433
        generate_kpi_control_board,
    )

    return generate_kpi_control_board


def build_kpi_board_result(
    *,
    iso_year: int,
    iso_week: int,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Run the SQL KPI pack and write markdown to the configured output dir."""
    if iso_week < 1 or iso_week > iso_weeks_in_year(iso_year):
        raise ValueError(
            f"Semana ISO inválida {iso_week} para el año {iso_year} "
            f"(máx. {iso_weeks_in_year(iso_year)})."
        )

    start_date, end_date = iso_week_date_range(iso_year, iso_week)
    out_dir = output_dir or Config.ensure_output_dir()
    output_path = out_dir / kpi_board_output_basename(iso_year, iso_week)

    generate = _import_generate_kpi_control_board()
    written = generate(
        start_date=start_date,
        end_date=end_date,
        output=str(output_path),
    )

    filename = Path(written).name
    return {
        "status": "success",
        "format": "markdown",
        "iso_year": iso_year,
        "iso_week": iso_week,
        "start_date": start_date,
        "end_date": end_date,
        "path": str(Path(written).resolve()),
        "message": (
            f"KPI Control Board generado — semana {iso_week} {iso_year} "
            f"({start_date} a {end_date})\n"
            f"Archivo: {filename}"
        ),
    }
