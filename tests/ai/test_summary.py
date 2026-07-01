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

    def test_vendedor_summary_uses_colombian_format(self):
        df = pd.DataFrame(
            {
                "Vendedor": ["OSCAR IVAN POLANIA GARCIA"],
                "Ventas_Este_Mes": [1164],
                "Total_Vendido": [602_118_006.64],
                "Ganancia_Generada": [68_670_869.72],
            }
        )
        text = AIVanna._deterministic_summary(
            "Vendedores con mejor desempeño este mes", df
        )
        assert "OSCAR IVAN POLANIA GARCIA" in text
        assert "$602.118.007" in text
        assert "$68.670.870" in text
        assert "1.164 transacciones" in text
        assert "60,271" not in text

    def test_document_type_summary_uses_descripcion(self):
        df = pd.DataFrame(
            {
                "Descripcion": ["Factura Almacén"],
                "Numero_Documentos": [168770],
                "Ventas_Total": [47_199_625_900.40],
                "Ganancia_Total": [5_500_000_000.12],
            }
        )
        text = AIVanna._deterministic_summary(
            "Comparación de ventas por tipo de documento", df
        )
        assert "Factura Almacén" in text
        assert "$47.199.625.900" in text
        assert "168.770 documentos" in text
