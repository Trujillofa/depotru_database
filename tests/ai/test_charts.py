"""Tests for smart chart generation."""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.charts import build_plotly_code, build_smart_figure
from business_analyzer.ai.formatting import format_number


@pytest.fixture
def enhanced_vanna(monkeypatch):
    """Real EnhancedAIVanna() with lightweight parent inits (no DB/API)."""
    from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
    from vanna.legacy.openai import OpenAI_Chat

    from business_analyzer.ai import base
    from vanna_grok import EnhancedAIVanna

    monkeypatch.setattr(
        ChromaDB_VectorStore, "__init__", lambda self, config=None: None
    )
    monkeypatch.setattr(
        OpenAI_Chat, "__init__", lambda self, client=None, config=None: None
    )
    monkeypatch.setattr(
        base,
        "create_ai_client",
        lambda provider=None: (object(), {"model": "test"}, "openai"),
    )

    vn = EnhancedAIVanna()
    return vn


CLIENT_PROFIT_DF = pd.DataFrame(
    {
        "Cliente": [
            "ONG FUNDACION GESTION SOCIAL DE COLOMBIA",
            "FEDERACION NACIONAL DE CAFETEROS DE COLOMBIA",
            "COMERCIALIZADORA INTERNACIONAL C.I PISCICOLA NEW YORK S.A.",
            "FERRETERIA MAGRETH S A S",
            "CONSTRUCTORA SANTA LUCIA SAS",
            "FERRETERIA LA GRAN REBAJA DE CAMPOALEGRE S.A.S",
            "GIL ANTONIO VARGAS  MERCHAN",
            "RUBY LILIANA CABRERA CABRERA",
            "MANUEL OSWALDO PACHECO PRADILLA",
            "MUNDO COLOR FERRETERIA Y PINTURAS S.A.S",
        ],
        "Ganancia_Total": [
            794_510_097,
            781_206_614,
            762_740_096,
            728_105_320,
            411_805_555,
            387_575_447,
            360_890_901,
            314_888_739,
            295_766_731,
            270_457_974,
        ],
        "Facturacion": [
            7_680_276_777,
            3_836_699_510,
            4_609_024_304,
            13_044_407_165,
            4_163_628_959,
            4_457_368_593,
            4_247_296_793,
            2_899_674_751,
            2_861_421_387,
            2_758_422_270,
        ],
        "Margen_Promedio": [15.2, 29.2, 22.7, 7.0, 13.5, 13.2, 12.3, 15.6, 18.7, 14.6],
        "Numero_Compras": [3218, 968, 4738, 15101, 3021, 4606, 1697, 10600, 1853, 6596],
    }
)


class TestSmartCharts:
    def test_sika_center_monthly_bar_chart(self):
        df = pd.DataFrame(
            {
                "Año": [2026] * 6,
                "Mes": [1, 2, 3, 4, 5, 6],
                "Nombre_Mes": [
                    "Enero",
                    "Febrero",
                    "Marzo",
                    "Abril",
                    "Mayo",
                    "Junio",
                ],
                "Ventas_Totales": [
                    200,
                    10_301_805,
                    67_201_662,
                    46_578_881,
                    62_649_251,
                    69_947_226,
                ],
                "Ganancia": [
                    88,
                    1_495_360,
                    10_024_608,
                    7_592_778,
                    10_314_864,
                    12_021_344,
                ],
                "Numero_Transacciones": [1, 63, 423, 302, 341, 359],
            }
        )
        fig = build_smart_figure(
            df, question="Ventas del Sika Center este año", dark_mode=False
        )
        assert fig is not None
        assert fig.data[0].type == "bar"
        assert fig.data[0].orientation != "h"
        assert "Junio 2026" in list(fig.data[0].x)

    def test_sika_product_ranking_horizontal_bar(self):
        df = pd.DataFrame(
            {
                "Producto": [f"Producto SIKA {i}" for i in range(1, 11)],
                "Ventas": [
                    5_000_000_000 - i * 100_000_000 for i in range(10)
                ],
                "Cantidad_Vendida": list(range(1000, 900, -10)),
                "Ganancia": [500_000_000 - i * 10_000_000 for i in range(10)],
            }
        )
        fig = build_smart_figure(
            df, question="Productos de SIKA más vendidos", dark_mode=False
        )
        assert fig is not None
        assert len(fig.data) == 1
        assert fig.data[0].type == "bar"
        assert fig.data[0].orientation == "h"

    def test_credito_vs_contado_single_metric_bar(self):
        df = pd.DataFrame(
            {
                "Tipo_Venta": ["Credito", "Contado"],
                "Numero_Ventas": [65317, 129266],
                "Ventas_Total": [26_972_371_085.04, 24_318_696_028.85],
                "Promedio_Dias_Credito": [28.262335, 0.0],
                "Ganancia": [3_085_086_290.82, 2_917_145_121.65],
            }
        )
        fig = build_smart_figure(
            df, question="Ventas a crédito vs contado", dark_mode=False
        )
        assert fig is not None
        assert len(fig.data) == 1
        assert fig.data[0].type == "bar"
        assert list(fig.data[0].x) == ["Credito", "Contado"]

    def test_last_30_days_chart_uses_ventas_diarias(self):
        df = pd.DataFrame(
            {
                "Fecha": pd.to_datetime(["2026-06-28", "2026-06-29", "2026-06-30"]),
                "Ventas_Diarias": [5_000_000, 4_200_000, 6_100_000],
                "Numero_Transacciones": [25, 22, 31],
            }
        )
        fig = build_smart_figure(
            df, question="Ventas de los últimos 30 días", dark_mode=False
        )
        assert fig is not None
        assert fig.data[0].type == "bar"
        assert fig.data[0].y is not None

    def test_build_plotly_code_returns_bar_for_time_series(self):
        df = pd.DataFrame(
            {
                "Nombre_Mes": ["Enero", "Febrero"],
                "Ventas_Totales": [100, 200],
            }
        )
        code = build_plotly_code(df, question="Ventas mensuales")
        assert code is not None
        assert "px.bar" in code
        assert "orientation='h'" not in code

    def test_empty_or_single_row_returns_none(self):
        assert build_smart_figure(pd.DataFrame()) is None
        assert build_smart_figure(pd.DataFrame({"x": [1]})) is None

    def test_category_single_metric_vertical_bar(self):
        df = pd.DataFrame(
            {
                "Categoria": ["Herramientas", "Pinturas", "Electricidad"],
                "Ventas_Totales": [1_000_000, 2_000_000, 1_500_000],
            }
        )
        fig = build_smart_figure(df, question="Ventas por categoría")
        assert fig is not None
        assert fig.data[0].type == "bar"
        assert len(fig.data) == 1

    def test_client_profit_mixed_scale_uses_horizontal_single_metric(self):
        fig = build_smart_figure(
            CLIENT_PROFIT_DF,
            question="Clientes más rentables por ganancia",
            dark_mode=False,
        )
        assert fig is not None
        assert len(fig.data) == 1
        assert fig.data[0].type == "bar"
        assert fig.data[0].orientation == "h"
        labels = list(fig.data[0].y)
        assert any("ONG FUNDACION" in str(label) for label in labels)
        assert max(fig.data[0].x) > 700_000_000

    def test_vendedor_performance_chart_uses_total_vendido(self):
        df = pd.DataFrame(
            {
                "Vendedor": [
                    "OSCAR IVAN POLANIA GARCIA",
                    "DANIEL ENRIQUE CAICEDO",
                    "FELIPE RAMIREZ",
                ],
                "Ventas_Este_Mes": [1164, 871, 1827],
                "Total_Vendido": [602_118_006, 525_781_825, 458_738_635],
                "Ganancia_Generada": [68_670_869, 67_352_457, 52_050_755],
            }
        )
        fig = build_smart_figure(
            df,
            question="Vendedores con mejor desempeño este mes",
            dark_mode=False,
        )
        assert fig is not None
        assert fig.data[0].orientation == "h"
        assert max(fig.data[0].x) > 500_000_000
        assert fig.layout.xaxis.showticklabels is False

    def test_document_type_chart_uses_ventas_total(self):
        df = pd.DataFrame(
            {
                "Descripcion": [
                    "Factura Almacén",
                    "Factura Calle 5",
                    "Factura Florencia (Sika Center)",
                ],
                "Numero_Documentos": [168770, 20515, 1546],
                "Ventas_Total": [47_199_625_900, 4_859_592_471, 266_908_988],
                "Ganancia_Total": [5_000_000_000, 500_000_000, 50_000_000],
            }
        )
        fig = build_smart_figure(
            df,
            question="Comparación de ventas por tipo de documento",
            dark_mode=False,
        )
        assert fig is not None
        assert fig.data[0].orientation == "h"
        assert max(fig.data[0].x) > 40_000_000_000

    def test_daily_average_chart_uses_year_month_period_label(self):
        df = pd.DataFrame(
            {
                "Año": [2026, 2026, 2025],
                "Mes": [6, 5, 12],
                "Nombre_Mes": ["June", "May", "December"],
                "Promedio_Ventas_Diarias": [
                    338_678_637,
                    328_806_929,
                    368_241_396,
                ],
                "Promedio_Transacciones_Diarias": [1376, 1259, 1354],
            }
        )
        fig = build_smart_figure(
            df,
            question="Promedio de ventas diarias por mes",
            dark_mode=False,
        )
        assert fig is not None
        labels = list(fig.data[0].x)
        assert any("202" in str(label) for label in labels)

    def test_client_ranking_hides_confusing_x_axis_ticks(self):
        df = pd.DataFrame(
            {
                "Cliente": ["FERRETERIA MAGRETH S A S", "ONG FUNDACION GESTION SOCIAL"],
                "Facturacion_Total": [12_731_981_609, 7_680_276_777],
                "Numero_Compras": [15101, 3218],
            }
        )
        fig = build_smart_figure(
            df,
            question="Top 10 clientes con mayor facturación",
            dark_mode=False,
        )
        assert fig is not None
        assert fig.layout.xaxis.showticklabels is False

    def test_client_profit_no_grouped_three_trace_chart(self):
        fig = build_smart_figure(
            CLIENT_PROFIT_DF,
            question="Clientes más rentables por ganancia",
        )
        assert fig is not None
        assert len(fig.data) != 3

    def test_client_profit_plotly_code_matches_horizontal(self):
        code = build_plotly_code(
            CLIENT_PROFIT_DF, question="Clientes más rentables por ganancia"
        )
        assert code is not None
        assert "orientation='h'" in code
        assert "Ganancia_Total" in code
        assert "melt" not in code

    def test_mixed_scale_without_ranking_returns_dual_axis(self):
        df = pd.DataFrame(
            {
                "Item": ["Alpha", "Beta", "Gamma"],
                "Revenue": [1_000_000, 2_000_000, 3_000_000],
                "Margen_Pct": [10.0, 20.0, 30.0],
            }
        )
        fig = build_smart_figure(df, question="Comparación general")
        assert fig is not None
        assert len(fig.data) == 2
        assert fig.data[0].type == "bar"
        assert fig.data[1].type == "scatter"
        assert fig.layout.xaxis2.title.text == "Margen_Pct"

    def test_dual_axis_plotly_code_emits_go_figure(self):
        df = pd.DataFrame(
            {
                "Item": ["Alpha", "Beta"],
                "Revenue": [1_000_000, 2_000_000],
                "Margen_Pct": [10.0, 20.0],
            }
        )
        code = build_plotly_code(df, question="Comparación general")
        assert code is not None
        assert "go.Figure" in code
        assert "xaxis2" in code

    def test_plotly_code_matches_figure_strategy(self):
        code = build_plotly_code(
            CLIENT_PROFIT_DF, question="Clientes más rentables por ganancia"
        )
        fig = build_smart_figure(
            CLIENT_PROFIT_DF, question="Clientes más rentables por ganancia"
        )
        assert code is not None
        assert fig is not None
        assert "orientation='h'" in code
        assert "update_traces" in code
        assert fig.data[0].orientation == "h"
        assert "melt" not in code

    def test_enhanced_ai_vanna_generate_plotly_code_uses_charts_before_super(
        self,
        enhanced_vanna,
        monkeypatch,
    ):
        from business_analyzer.ai.base import AIVanna

        super_called = {"value": False}

        def _fake_super_generate(*_args, **_kwargs):
            super_called["value"] = True
            return "llm-fallback"

        monkeypatch.setattr(AIVanna, "generate_plotly_code", _fake_super_generate)

        enhanced_vanna._last_result_df = CLIENT_PROFIT_DF.copy()
        enhanced_vanna._last_question = "Clientes más rentables por ganancia"

        code = enhanced_vanna.generate_plotly_code(
            question="Clientes más rentables por ganancia"
        )

        assert enhanced_vanna.provider
        assert "orientation='h'" in code
        assert "update_traces" in code
        assert super_called["value"] is False

    def test_enhanced_ai_vanna_get_plotly_figure_uses_passed_df(self, enhanced_vanna):
        enhanced_vanna._last_question = "Clientes más rentables por ganancia"

        fig = enhanced_vanna.get_plotly_figure("", CLIENT_PROFIT_DF, dark_mode=False)

        assert enhanced_vanna.provider
        assert fig.data[0].orientation == "h"
        assert len(fig.data) == 1

    def test_enhanced_ai_vanna_get_plotly_figure_falls_back_to_super_when_not_chartable(
        self,
        enhanced_vanna,
        monkeypatch,
    ):
        from business_analyzer.ai.base import AIVanna

        sentinel = {"called": False, "figure": None}

        def _fake_super_get(*_args, **_kwargs):
            sentinel["called"] = True
            sentinel["figure"] = "super-figure"
            return sentinel["figure"]

        monkeypatch.setattr(AIVanna, "get_plotly_figure", _fake_super_get)

        fig = enhanced_vanna.get_plotly_figure(
            "", pd.DataFrame({"x": [1]}), dark_mode=False
        )

        assert enhanced_vanna.provider
        assert sentinel["called"]
        assert fig == "super-figure"

    def test_geo_query_uses_departamento_ciudad_composite_label(self):
        df = pd.DataFrame(
            {
                "Departamento": ["HUILA", "HUILA", "CAQUETÁ"],
                "Ciudad": ["NEIVA", "PALERMO", "SAN VICENTE DEL CAGUÁN"],
                "Ventas_Totales": [25766450550.81, 1588071736.42, 1631913520.81],
            }
        )
        fig = build_smart_figure(df, question="Ventas por departamento y ciudad")
        assert fig is not None
        labels = list(fig.data[0].y)
        assert any("NEIVA" in label for label in labels)
        assert any("PALERMO" in label for label in labels)
        assert labels.count("HUILA") <= 1

    def test_top_products_chart_uses_colombian_bar_labels(self):
        df = pd.DataFrame(
            {
                "Producto": ["CEMENTO CEMEX", "BARRA 1/2"],
                "Unidades_Vendidas": [149835, 57220],
                "Facturacion_Total": [4993131, 1487777],
            }
        )
        fig = build_smart_figure(
            df, question="Top 10 productos más vendidos por facturación este año"
        )
        assert fig is not None
        assert fig.data[0].orientation == "h"
        bar_text = "".join(str(t) for t in fig.data[0].text)
        assert "$" in bar_text
        assert "4.993.131" in bar_text or "4993131" in bar_text.replace(".", "")


class TestFormattingExtensions:
    def test_ventas_totales_currency(self):
        assert format_number(67201661.98, "Ventas_Totales") == "$67.201.662"

    def test_facturacion_total_currency(self):
        assert format_number(4993131, "Facturacion_Total") == "$4.993.131"

    def test_unidades_vendidas_integer(self):
        assert format_number(149835, "Unidades_Vendidas") == "149.835"

    def test_numero_transacciones_integer(self):
        assert format_number(423, "Numero_Transacciones") == "423"
