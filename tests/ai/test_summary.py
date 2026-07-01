"""Tests for deterministic Vanna summaries."""

import pandas as pd

from business_analyzer.ai.base import AIVanna


class TestDeterministicSummary:
    def test_geo_sales_summary_uses_colombian_format(self):
        df = pd.DataFrame(
            {
                "Departamento": ["HUILA", "CAQUETÁ"],
                "Ciudad": ["NEIVA", "SAN VICENTE DEL CAGUÁN"],
                "Ventas_Totales": [25766450550.8084, 1631913520.8136],
                "Ganancia": [3017521952.5855, 175505121.9045],
                "Clientes_Unicos": [9632, 36],
            }
        )
        text = AIVanna._deterministic_summary("Ventas por departamento y ciudad", df)
        assert "$25.766.450.551" in text
        assert "$3.017.521.953" in text
        assert "9.632" in text
        assert "HUILA — NEIVA" in text
        assert "25,786" not in text

    def test_top_customers_summary_uses_cliente_label(self):
        df = pd.DataFrame(
            {
                "Cliente": ["FERRETERIA MAGRETH S A S"],
                "Facturacion_Total": [12_731_981_609.02],
                "Ganancia_Neta": [728_105_320.5],
                "Numero_Compras": [15101],
            }
        )
        text = AIVanna._deterministic_summary(
            "Top 10 clientes con mayor facturación", df
        )
        assert "FERRETERIA MAGRETH" in text
        assert "$12.731.981.609" in text
        assert "$728.105.320" in text
