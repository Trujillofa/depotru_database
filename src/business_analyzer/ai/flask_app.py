"""
Vanna Flask app with cache-backed raw DataFrames for smart chart generation.

The stock VannaFlaskApp caches only the formatted display DataFrame from run_sql.
Chart generation runs in a separate HTTP request, so thread-local chart context
is lost under Waitress. This subclass stores df_raw in the query cache and always
builds charts from numeric data instead of stale LLM plotly code.
"""

from __future__ import annotations

import traceback
from typing import Optional

import flask
import pandas as pd
from flask import Response, jsonify
from vanna.legacy.flask import VannaFlaskApp
from vanna.legacy.flask.assets import html_content

from business_analyzer.ai.charts import (
    build_plotly_code,
    build_smart_figure,
    clear_chart_query_context,
    fig_to_browser_json,
    set_chart_query_context,
)
from business_analyzer.ai.formatting import coerce_chart_dataframe


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


class SmartVannaFlaskApp(VannaFlaskApp):
    """VannaFlaskApp that caches raw query results for deterministic charts."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._patch_chart_routes()
        self._patch_plotly_cdn()

    def _patch_plotly_cdn(self) -> None:
        """Use a maintained Plotly.js build instead of deprecated plotly-latest."""
        patched_html = html_content.replace(
            "https://cdn.plot.ly/plotly-latest.min.js",
            "https://cdn.plot.ly/plotly-2.35.2.min.js",
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
                        "df": df_display.head(10).to_json(
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
