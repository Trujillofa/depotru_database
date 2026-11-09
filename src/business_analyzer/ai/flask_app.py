"""
Vanna Flask app with cache-backed raw DataFrames for smart chart generation.

The stock VannaFlaskApp caches only the formatted display DataFrame from run_sql.
Chart generation runs in a separate HTTP request, so thread-local chart context
is lost under Waitress. This subclass stores df_raw in the query cache and always
builds charts from numeric data instead of stale LLM plotly code.
"""

from __future__ import annotations

import logging
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

import flask
import pandas as pd
from flask import Response, jsonify, send_from_directory
from vanna.legacy.flask import VannaFlaskApp
from vanna.legacy.flask.assets import html_content, js_content

from business_analyzer.ai.base import Config
from business_analyzer.ai.charts import (
    build_plotly_code,
    build_smart_figure,
    clear_chart_query_context,
    fig_to_browser_json,
    set_chart_query_context,
)
from business_analyzer.ai.formatting import coerce_chart_dataframe
from business_analyzer.ai.recommended_reports import (
    inject_recommended_reports_ui,
    recommended_reports_payload,
)

_MANAGER_REPORT_JS_SNIPPET = (
    'if(n.type==="manager_report"){'
    'Se({type:"text",id:n.id,text:n.text||""});'
    'n.download_url&&window.open(n.download_url,"_blank");return;}'
    'if(Se(n),n.type!=="sql")return;'
)

_MANAGER_REPORT_JS_SNIPPET_E = (
    'if(E.type==="manager_report"){'
    'Se({type:"text",id:E.id,text:E.text||""});'
    'E.download_url&&window.open(E.download_url,"_blank");return;}'
    'if(Se(E),E.type!=="sql")return;'
)


def _chart_dataframe(vn, df_display: pd.DataFrame) -> pd.DataFrame:
    """Resolve numeric chart data from the Vanna instance or formatted display."""
    raw = getattr(vn, "_last_result_df", None)
    if raw is not None and not raw.empty:
        return raw
    return coerce_chart_dataframe(df_display)


def _replace_route_view(flask_app, path: str, methods: list[str], view_func) -> None:
    """Swap the handler for an existing Flask route (keeps endpoint name)."""
    for rule in flask_app.url_map.iter_rules():
        if rule.rule != path:
            continue
        if not set(methods).issubset(rule.methods):
            continue
        flask_app.view_functions[rule.endpoint] = view_func
        return
    raise RuntimeError(f"No Flask route found for {path} {methods}")


def manager_report_download_path(file_path: Optional[str]) -> Optional[str]:
    """Map an absolute report path to the Flask download URL."""
    if not file_path:
        return None
    return f"/reports/{Path(file_path).name}"


def manager_report_status_text(result: Dict[str, Any]) -> str:
    """One-line sidebar status; full narrative stays in ``text`` for the chat."""
    from business_analyzer.ai.recommended_reports import MONTH_NAMES_ES

    year = result.get("year")
    month = result.get("month")
    fmt = str(result.get("format") or "html").upper()
    month_name = MONTH_NAMES_ES.get(month, str(month))
    filename = Path(result["path"]).name if result.get("path") else None
    if filename:
        return f"✓ Informe {fmt} listo — {month_name} {year} ({filename})"
    return f"✓ Informe {fmt} — {month_name} {year}"


def kpi_board_status_text(result: Dict[str, Any]) -> str:
    iso_year = result.get("iso_year")
    iso_week = result.get("iso_week")
    start_date = result.get("start_date")
    end_date = result.get("end_date")
    filename = Path(result["path"]).name if result.get("path") else None
    if filename:
        return (
            f"✓ KPI board listo — semana {iso_week} {iso_year} "
            f"({start_date} a {end_date}, {filename})"
        )
    return f"✓ KPI board — semana {iso_week} {iso_year}"


def kpi_board_api_payload(result: Dict[str, Any], cache_id: str) -> Dict[str, Any]:
    status = result.get("status")
    if status == "error":
        return {
            "type": "error",
            "id": cache_id,
            "error": result.get("message", "Error generando KPI board"),
        }
    return {
        "type": "kpi_board",
        "id": cache_id,
        "text": result.get("message", ""),
        "status_text": kpi_board_status_text(result),
        "download_url": manager_report_download_path(result.get("path")),
        "format": result.get("format", "markdown"),
        "iso_year": result.get("iso_year"),
        "iso_week": result.get("iso_week"),
        "start_date": result.get("start_date"),
        "end_date": result.get("end_date"),
    }


def rotacion_status_text(result: Dict[str, Any]) -> str:
    as_of = result.get("as_of_date")
    filename = Path(result["path"]).name if result.get("path") else None
    if filename:
        return f"✓ Rotación de existencias lista — {as_of} ({filename})"
    return f"✓ Rotación de existencias — {as_of}"


def rotacion_api_payload(result: Dict[str, Any], cache_id: str) -> Dict[str, Any]:
    status = result.get("status")
    if status == "error":
        return {
            "type": "error",
            "id": cache_id,
            "error": result.get("message", "Error generando rotación de existencias"),
        }
    return {
        "type": "rotacion",
        "id": cache_id,
        "text": result.get("message", ""),
        "status_text": rotacion_status_text(result),
        "download_url": manager_report_download_path(result.get("path")),
        "format": result.get("format", "html"),
        "as_of_date": result.get("as_of_date"),
        "demand_mode": result.get("demand_mode"),
        "insights_count": result.get("insights_count"),
    }


def cartera_status_text(result: Dict[str, Any]) -> str:
    as_of = result.get("as_of_date")
    filename = Path(result["path"]).name if result.get("path") else None
    if filename:
        return f"✓ Cartera / aging lista — {as_of} ({filename})"
    return f"✓ Cartera / aging — {as_of}"


def tsol_status_text(result: Dict[str, Any]) -> str:
    filename = Path(result["path"]).name if result.get("path") else None
    brand = result.get("brand") or "TSOL"
    start = result.get("period_start") or ""
    end = result.get("period_end") or ""
    if filename:
        return f"✓ TSOL {brand} {start}–{end} ({filename})"
    return f"✓ TSOL {brand} listo."


def tsol_api_payload(result: Dict[str, Any], cache_id: str) -> Dict[str, Any]:
    status = result.get("status")
    if status == "error":
        return {
            "type": "error",
            "id": cache_id,
            "error": result.get("message", "Error generando TSOL"),
        }
    return {
        "type": "tsol",
        "id": cache_id,
        "text": result.get("message", ""),
        "status_text": tsol_status_text(result),
        "download_url": manager_report_download_path(result.get("path")),
        "format": "xlsx",
        "brand": result.get("brand"),
        "period_start": result.get("period_start"),
        "period_end": result.get("period_end"),
        "quality": result.get("quality"),
    }


def cartera_api_payload(result: Dict[str, Any], cache_id: str) -> Dict[str, Any]:
    status = result.get("status")
    if status == "error":
        return {
            "type": "error",
            "id": cache_id,
            "error": result.get("message", "Error generando cartera / aging"),
        }
    return {
        "type": "cartera",
        "id": cache_id,
        "text": result.get("message", ""),
        "status_text": cartera_status_text(result),
        "download_url": manager_report_download_path(result.get("path")),
        "format": result.get("format", "html"),
        "as_of_date": result.get("as_of_date"),
        "insights_count": result.get("insights_count"),
    }


def manager_report_api_payload(result: Dict[str, Any], cache_id: str) -> Dict[str, Any]:
    """Serialize a manager report routing result for the Vanna web UI."""
    status = result.get("status")
    if status == "needs_period":
        return {
            "type": "text",
            "id": cache_id,
            "text": result.get("message", ""),
        }
    if status == "error":
        return {
            "type": "error",
            "id": cache_id,
            "error": result.get("message", "Error generando informe"),
        }

    return {
        "type": "manager_report",
        "id": cache_id,
        "text": result.get("message", ""),
        "status_text": manager_report_status_text(result),
        "download_url": manager_report_download_path(result.get("path")),
        "format": result.get("format"),
        "year": result.get("year"),
        "month": result.get("month"),
        "summary": result.get("summary", {}),
        "record_count": result.get("record_count", 0),
    }


def patched_vanna_js_content() -> str:
    """Inject manager-report handling into the bundled Vanna chat client."""
    patched: str = js_content.replace(
        'if(Se(n),n.type!=="sql")return;',
        _MANAGER_REPORT_JS_SNIPPET,
    )
    patched = patched.replace(
        'if(Se(E),E.type!=="sql")return;',
        _MANAGER_REPORT_JS_SNIPPET_E,
    )
    return patched


class SmartVannaFlaskApp(VannaFlaskApp):
    """VannaFlaskApp that caches raw query results for deterministic charts."""

    def __init__(self, *args, **kwargs):
        # Waitress cannot serve Vanna's /api/v0/log WebSocket, so the debug
        # console would fail on every page load. Callers on a WS-capable
        # server can still opt in explicitly with debug=True.
        kwargs.setdefault("debug", False)
        super().__init__(*args, **kwargs)
        self._patch_api_catch_all()
        self._patch_chart_routes()
        self._patch_manager_report_routes()
        self._patch_plotly_cdn()

    def _patch_api_catch_all(self) -> None:
        """Return 404 for unknown /api/v0 paths instead of Vanna's 200 stub."""

        def api_not_found(catch_all: str = ""):
            return (
                jsonify(
                    {
                        "type": "error",
                        "error": f"Not found: /api/v0/{catch_all}",
                    }
                ),
                404,
            )

        try:
            _replace_route_view(
                self.flask_app,
                "/api/v0/<path:catch_all>",
                ["GET", "POST"],
                api_not_found,
            )
        except RuntimeError:
            pass

    def _patch_plotly_cdn(self) -> None:
        """Use a maintained Plotly.js build instead of deprecated plotly-latest."""
        patched_html = inject_recommended_reports_ui(
            html_content.replace(
                '<script src="https://cdn.plot.ly/plotly-latest.min.js" '
                'type="text/javascript"></script>',
                '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" '
                'type="text/javascript" defer></script>',
            ).replace(
                'href="/vanna.svg"',
                'href="/assets/smartbusiness-icon.svg"',
            )
        )

        @self.flask_app.route("/", defaults={"path": ""})
        @self.flask_app.route("/<path:path>")
        def smart_index(path: str = ""):
            if self.index_html_path:
                import os

                from flask import send_from_directory

                directory = os.path.dirname(self.index_html_path)
                filename = os.path.basename(self.index_html_path)
                return send_from_directory(directory=directory, path=filename)
            return patched_html

        for route in ("/", "/<path:path>"):
            try:
                _replace_route_view(self.flask_app, route, ["GET"], smart_index)
            except RuntimeError:
                pass

    def _patch_assets_js(self) -> None:
        """Serve Vanna JS/CSS plus the recommended-reports static assets."""

        @self.flask_app.route("/assets/<path:filename>")
        def proxy_assets_patched(filename: str):
            static_dir = Path(__file__).resolve().parent / "static"
            if ".." not in Path(filename).parts and (static_dir / filename).is_file():
                return send_from_directory(static_dir, filename, max_age=0)

            if self.assets_folder:
                return send_from_directory(self.assets_folder, filename)

            from vanna.legacy.flask.assets import css_content

            if ".css" in filename:
                # Vendor rules go in a lower cascade layer so informes.css can
                # override Tailwind utilities without !important.
                return Response(
                    f"@layer vanna {{\n{css_content}\n}}", mimetype="text/css"
                )

            if ".js" in filename:
                return Response(patched_vanna_js_content(), mimetype="text/javascript")

            return "File not found", 404

        _replace_route_view(
            self.flask_app, "/assets/<path:filename>", ["GET"], proxy_assets_patched
        )

    def _patch_manager_report_routes(self) -> None:
        vn = self.vn
        cache = self.cache
        requires_auth = self.requires_auth
        allow_llm = self.allow_llm_to_see_data

        @requires_auth
        def generate_sql(user):
            question = flask.request.args.get("question")
            if question is None:
                return jsonify({"type": "error", "error": "No question provided"})

            cache_id = cache.generate_id(question=question)
            sql = vn.generate_sql(question=question, allow_llm_to_see_data=allow_llm)
            report_result = (
                vn.pop_manager_report_result()
                if hasattr(vn, "pop_manager_report_result")
                else None
            )
            if report_result is not None:
                cache.set(id=cache_id, field="question", value=question)
                cache.set(id=cache_id, field="manager_report", value=report_result)
                return jsonify(manager_report_api_payload(report_result, cache_id))

            cache.set(id=cache_id, field="question", value=question)

            # generate_sql() returns None when the model answers conversationally
            # instead of producing SQL (e.g. "hello world"). Passing None into
            # is_sql_valid() raises inside sqlparse and surfaces to the UI as a 500.
            if not sql or not str(sql).strip():
                return jsonify(
                    {
                        "type": "text",
                        "id": cache_id,
                        "text": (
                            "No pude convertir esa pregunta en una consulta SQL. "
                            "Intenta formularla sobre ventas, productos, clientes "
                            "o inventario."
                        ),
                    }
                )

            cache.set(id=cache_id, field="sql", value=sql)

            if vn.is_sql_valid(sql=sql):
                return jsonify(
                    {
                        "type": "sql",
                        "id": cache_id,
                        "text": sql,
                    }
                )
            return jsonify(
                {
                    "type": "text",
                    "id": cache_id,
                    "text": sql,
                }
            )

        @requires_auth
        def generate_report(user):
            question = flask.request.args.get("question")
            year = flask.request.args.get("year", type=int)
            month = flask.request.args.get("month", type=int)
            fmt = flask.request.args.get("format", "html")
            branch = flask.request.args.get("branch")

            if flask.request.method == "POST":
                body = flask.request.get_json(silent=True) or {}
                question = body.get("question", question)
                year = body.get("year", year)
                month = body.get("month", month)
                fmt = body.get("format", fmt)
                branch = body.get("branch", branch)

            if year is not None:
                year = int(year)
            if month is not None:
                month = int(month)
            fmt = str(fmt or "html").strip().lower()

            cache_id = cache.generate_id(
                question=question, year=year, month=month, format=fmt
            )

            # Explicit year/month/format (catalog clicks) take precedence over NL
            # question parsing so format=pdf is not lost to _parse_report_format.
            if year and month and hasattr(vn, "_build_manager_report"):
                try:
                    from business_analyzer.analysis.manager_report.helpers import (
                        BRANCH_SLUGS,
                    )

                    branch_code = None
                    if branch:
                        branch_key = str(branch).strip().lower().replace("-", "_")
                        branch_code = {
                            slug: code for code, slug in BRANCH_SLUGS.items()
                        }.get(branch_key)
                        if branch_code is None and branch_key.upper() in BRANCH_SLUGS:
                            branch_code = branch_key.upper()
                    result = vn._build_manager_report(
                        year,
                        month,
                        fmt,
                        branch_document_code=branch_code,
                    )
                except Exception as exc:
                    result = {
                        "status": "error",
                        "message": f"Error generando el informe gerencial: {exc}",
                    }
            elif question and hasattr(vn, "route_manager_report_question"):
                result = vn.route_manager_report_question(question)
            else:
                return jsonify(
                    {
                        "type": "error",
                        "error": (
                            "Indica question («informe de mayo 2024») o year y month."
                        ),
                    }
                )

            if result is None:
                return jsonify(
                    {
                        "type": "error",
                        "error": "La pregunta no corresponde a un informe gerencial.",
                    }
                )

            cache.set(id=cache_id, field="manager_report", value=result)
            if question:
                cache.set(id=cache_id, field="question", value=question)
            return jsonify(manager_report_api_payload(result, cache_id))

        @requires_auth
        def generate_kpi_board(user):
            iso_year = flask.request.args.get("iso_year", type=int)
            iso_week = flask.request.args.get("iso_week", type=int)

            if flask.request.method == "POST":
                body = flask.request.get_json(silent=True) or {}
                iso_year = body.get("iso_year", iso_year)
                iso_week = body.get("iso_week", iso_week)

            if iso_year is None or iso_week is None:
                return jsonify(
                    {
                        "type": "error",
                        "error": "Indica iso_year e iso_week para el tablero KPI.",
                    }
                )

            iso_year = int(iso_year)
            iso_week = int(iso_week)
            cache_id = cache.generate_id(iso_year=iso_year, iso_week=iso_week)

            try:
                from business_analyzer.reports.kpi_control_board import (
                    build_kpi_board_result,
                )

                result = build_kpi_board_result(
                    iso_year=iso_year,
                    iso_week=iso_week,
                )
            except ValueError as exc:
                result = {"status": "error", "message": str(exc)}
            except Exception as exc:
                result = {
                    "status": "error",
                    "message": f"Error generando KPI control board: {exc}",
                }

            if result.get("status") == "error":
                return jsonify(kpi_board_api_payload(result, cache_id))

            cache.set(id=cache_id, field="kpi_board", value=result)
            return jsonify(kpi_board_api_payload(result, cache_id))

        @requires_auth
        def generate_rotacion(user):
            as_of_date = flask.request.args.get("as_of_date")
            top_n = flask.request.args.get("top_n", type=int)
            demand_mode = flask.request.args.get("demand_mode")
            fmt = flask.request.args.get("format", "html")

            if flask.request.method == "POST":
                body = flask.request.get_json(silent=True) or {}
                as_of_date = body.get("as_of_date", as_of_date)
                top_n = body.get("top_n", top_n)
                demand_mode = body.get("demand_mode", demand_mode)
                fmt = body.get("format", fmt)

            if not as_of_date:
                return jsonify(
                    {
                        "type": "error",
                        "error": "Indica as_of_date (YYYY-MM-DD) para rotación.",
                    }
                )

            top_n = int(top_n) if top_n is not None else 50
            demand_mode = str(demand_mode or "warehouse").strip().lower()
            fmt = str(fmt or "html").strip().lower()
            cache_id = cache.generate_id(
                as_of_date=as_of_date,
                top_n=top_n,
                demand_mode=demand_mode,
                format=fmt,
            )

            try:
                from business_analyzer.reports.rotacion_existencias import (
                    build_rotacion_result,
                )

                result = build_rotacion_result(
                    as_of_date=str(as_of_date),
                    top_n=top_n,
                    demand_mode=demand_mode,
                    fmt=fmt,
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "generate_rotacion failed as_of=%s fmt=%s", as_of_date, fmt
                )
                result = {
                    "status": "error",
                    "message": (
                        "Error generando rotación de existencias. "
                        "Revise la fecha/formato o los logs del servidor."
                    ),
                }

            if result.get("status") == "error":
                return jsonify(rotacion_api_payload(result, cache_id))

            cache.set(id=cache_id, field="rotacion", value=result)
            return jsonify(rotacion_api_payload(result, cache_id))

        @requires_auth
        def generate_cartera(user):
            as_of_date = flask.request.args.get("as_of_date")
            top_n = flask.request.args.get("top_n", type=int)
            fmt = flask.request.args.get("format", "html")
            dso_days = flask.request.args.get("dso_days", type=int)

            if flask.request.method == "POST":
                body = flask.request.get_json(silent=True) or {}
                as_of_date = body.get("as_of_date", as_of_date)
                top_n = body.get("top_n", top_n)
                fmt = body.get("format", fmt)
                dso_days = body.get("dso_days", dso_days)

            if not as_of_date:
                return jsonify(
                    {
                        "type": "error",
                        "error": "Indica as_of_date (YYYY-MM-DD) para cartera.",
                    }
                )

            top_n = int(top_n) if top_n is not None else 25
            dso_days = int(dso_days) if dso_days is not None else 30
            fmt = str(fmt or "html").strip().lower()
            cache_id = cache.generate_id(
                as_of_date=as_of_date,
                top_n=top_n,
                dso_days=dso_days,
                format=fmt,
                report="cartera",
            )

            try:
                from business_analyzer.reports.cartera_aging import build_cartera_result

                result = build_cartera_result(
                    as_of_date=str(as_of_date),
                    top_n=top_n,
                    dso_days=dso_days,
                    fmt=fmt,
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "generate_cartera failed as_of=%s fmt=%s", as_of_date, fmt
                )
                result = {
                    "status": "error",
                    "message": (
                        "Error generando cartera / aging. "
                        "Revise la fecha/formato o los logs del servidor."
                    ),
                }

            if result.get("status") == "error":
                return jsonify(cartera_api_payload(result, cache_id))

            cache.set(id=cache_id, field="cartera", value=result)
            return jsonify(cartera_api_payload(result, cache_id))

        @requires_auth
        def generate_tsol(user):
            brand = flask.request.args.get("brand", "sika")
            year = flask.request.args.get("year", type=int)
            month = flask.request.args.get("month", type=int)
            ytd = flask.request.args.get("ytd", "false")

            if flask.request.method == "POST":
                body = flask.request.get_json(silent=True) or {}
                brand = body.get("brand", brand)
                year = body.get("year", year)
                month = body.get("month", month)
                ytd = body.get("ytd", ytd)

            ytd_flag = str(ytd).strip().lower() in ("1", "true", "yes", "y")
            brand = str(brand or "sika").strip().lower()
            start = end = None
            if ytd_flag:
                ytd_year = int(year) if year else date.today().year
                start = date(ytd_year, 1, 1)
                end = date.today()
            elif not year or not month:
                return jsonify(
                    {
                        "type": "error",
                        "error": "Indica year y month, o ytd=true, para TSOL.",
                    }
                )

            cache_id = cache.generate_id(
                brand=brand,
                year=year,
                month=month,
                ytd=ytd_flag,
                start=str(start) if start else "",
                end=str(end) if end else "",
                report="tsol",
            )
            try:
                from business_analyzer.reports.tsol_export import build_tsol_result

                result = build_tsol_result(
                    brand=brand,
                    year=None if start else int(year),
                    month=None if start else int(month),
                    start=start,
                    end=end,
                )
            except Exception:
                logging.getLogger(__name__).exception(
                    "generate_tsol failed brand=%s ytd=%s", brand, ytd_flag
                )
                result = {
                    "status": "error",
                    "message": (
                        "Error generando TSOL. Revise marca/periodo o los logs."
                    ),
                }

            if result.get("status") == "error":
                return jsonify(tsol_api_payload(result, cache_id))

            cache.set(id=cache_id, field="tsol", value=result)
            return jsonify(tsol_api_payload(result, cache_id))

        @self.flask_app.route("/api/v0/recommended_reports", methods=["GET"])
        def recommended_reports():
            return jsonify(recommended_reports_payload())

        @self.flask_app.route("/api/v0/health", methods=["GET"])
        def health_check():
            import os
            import shutil

            report_provider = os.getenv("REPORT_AI_PROVIDER") or Config.AI_PROVIDER
            return jsonify(
                {
                    "status": "ok",
                    "sql_provider": Config.AI_PROVIDER,
                    "report_provider": report_provider,
                    "report_fallbacks": os.getenv("REPORT_AI_FALLBACK_PROVIDERS", ""),
                    "commandcode_cli": os.getenv("COMMANDCODE_BIN")
                    or shutil.which("commandcode"),
                    "openrouter_key": bool(os.getenv("OPENROUTER_API_KEY")),
                    "groq_key": bool(os.getenv("GROQ_API_KEY")),
                    "report_cache": os.getenv("REPORT_AI_CACHE", "1") != "0",
                    "output_dir": str(Config.ensure_output_dir()),
                }
            )

        @self.flask_app.route("/reports/<path:filename>")
        def serve_manager_report(filename: str):
            output_dir = Config.ensure_output_dir().resolve()
            safe_name = Path(filename).name
            target = (output_dir / safe_name).resolve()
            if not str(target).startswith(str(output_dir)):
                return "Forbidden", 403
            if not target.is_file():
                return "Not found", 404
            return send_from_directory(output_dir, safe_name)

        _replace_route_view(
            self.flask_app, "/api/v0/generate_sql", ["GET"], generate_sql
        )
        self.flask_app.add_url_rule(
            "/api/v0/generate_report",
            endpoint="smart_generate_report",
            view_func=generate_report,
            methods=["GET", "POST"],
        )
        self.flask_app.add_url_rule(
            "/api/v0/generate_kpi_board",
            endpoint="smart_generate_kpi_board",
            view_func=generate_kpi_board,
            methods=["GET", "POST"],
        )
        self.flask_app.add_url_rule(
            "/api/v0/generate_rotacion",
            endpoint="smart_generate_rotacion",
            view_func=generate_rotacion,
            methods=["GET", "POST"],
        )
        self.flask_app.add_url_rule(
            "/api/v0/generate_cartera",
            endpoint="smart_generate_cartera",
            view_func=generate_cartera,
            methods=["GET", "POST"],
        )
        self.flask_app.add_url_rule(
            "/api/v0/generate_tsol",
            endpoint="smart_generate_tsol",
            view_func=generate_tsol,
            methods=["GET", "POST"],
        )
        self._patch_assets_js()

    def _patch_chart_routes(self) -> None:
        vn = self.vn
        cache = self.cache
        chart_enabled = self.chart
        requires_auth = self.requires_auth
        requires_cache = self.requires_cache

        @requires_auth
        @requires_cache(["sql"])
        def run_sql(user, id: str, sql: str):
            try:
                clear_chart_query_context()
                if hasattr(vn, "_ensure_project_run_sql"):
                    vn._ensure_project_run_sql()
                if not vn.run_sql_is_set:
                    return jsonify(
                        {
                            "type": "error",
                            "error": (
                                "Please connect to a database using vn.connect_to_..."
                                " in order to run SQL queries."
                            ),
                        }
                    )

                df_display = vn.run_sql(sql=sql)
                df_raw = _chart_dataframe(vn, df_display)

                cache.set(id=id, field="df", value=df_display)
                cache.set(id=id, field="df_raw", value=df_raw)
                cache.set(id=id, field="plotly_code", value=None)

                should_chart = chart_enabled and vn.should_generate_chart(
                    df_raw if df_raw is not None and not df_raw.empty else df_display
                )

                return jsonify(
                    {
                        "type": "df",
                        "id": id,
                        "df": df_display.head(Config.MAX_DISPLAY_ROWS).to_json(
                            orient="records", date_format="iso"
                        ),
                        "should_generate_chart": should_chart,
                    }
                )
            except Exception as exc:
                return jsonify({"type": "sql_error", "error": str(exc)})

        @requires_auth
        @requires_cache(
            ["df", "question", "sql"],
            optional_fields=["df_raw"],
        )
        def generate_plotly_figure(
            user,
            id: str,
            df,
            question: str,
            sql: str,
            df_raw: Optional[pd.DataFrame] = None,
        ):
            chart_instructions = flask.request.args.get("chart_instructions")
            clear_chart_query_context()

            chart_df = df_raw
            if chart_df is None or chart_df.empty:
                chart_df = _chart_dataframe(vn, df)

            set_chart_query_context(raw_df=chart_df, question=question)

            try:
                chart_question = question
                if chart_instructions:
                    chart_question = (
                        f"{question}. When generating the chart, use these special "
                        f"instructions: {chart_instructions}"
                    )

                # Deterministic charts only — LLM plotly code plots formatted
                # currency strings on X and row indices (0–30) on Y in the browser.
                code = build_plotly_code(chart_df, question=chart_question) or ""
                cache.set(id=id, field="plotly_code", value=code or None)

                fig = build_smart_figure(
                    chart_df,
                    question=chart_question,
                    dark_mode=False,
                )
                if fig is None:
                    return jsonify(
                        {
                            "type": "error",
                            "error": (
                                "No se pudo generar un gráfico para estos datos. "
                                "Intenta agregar un rango de fechas o más filas."
                            ),
                        }
                    )

                fig_json = fig_to_browser_json(fig)
                cache.set(id=id, field="fig_json", value=fig_json)

                return jsonify(
                    {
                        "type": "plotly_figure",
                        "id": id,
                        "fig": fig_json,
                    }
                )
            except Exception as exc:
                traceback.print_stack()
                traceback.print_exc()
                return jsonify({"type": "error", "error": str(exc)})

        _replace_route_view(self.flask_app, "/api/v0/run_sql", ["GET"], run_sql)
        _replace_route_view(
            self.flask_app,
            "/api/v0/generate_plotly_figure",
            ["GET"],
            generate_plotly_figure,
        )
