"""Unit tests for inventory turnover (Rotación de Existencias)."""

from business_analyzer.core.inventory_turnover import (
    BAND_MUERTO,
    BAND_QUIEBRE,
    BAND_SALUDABLE,
    BAND_SOBRESTOCK,
    DEMAND_MODE_COMPANY,
    DEMAND_MODE_WAREHOUSE,
    abc_by_commercial_velocity,
    action_capital_atrapado,
    action_quiebre,
    annualized_turns,
    build_commercial_demand_by_warehouse_cte,
    build_commercial_demand_cte,
    build_commercial_stock_cte,
    build_turnover_detail_sql,
    classify_turnover_band,
    commercial_cover_days,
    enrich_detail_rows,
    suggested_transfers,
    turnover_summary_from_rows,
)
from business_analyzer.core.inventory_warehouse_policy import is_turnover_sku_denied


def test_classify_quiebre_negative_or_zero_stock_with_demand():
    assert classify_turnover_band(-10, 100, None) == BAND_QUIEBRE
    assert classify_turnover_band(0, 100, 0.0) == BAND_QUIEBRE


def test_classify_quiebre_low_cover():
    assert classify_turnover_band(50, 100, 3.0) == BAND_QUIEBRE


def test_classify_muerto_stock_no_sales():
    assert classify_turnover_band(100, 0, None) == BAND_MUERTO


def test_classify_overstock():
    assert classify_turnover_band(500, 30, 200.0) == BAND_SOBRESTOCK


def test_classify_saludable():
    assert classify_turnover_band(100, 50, 60.0) == BAND_SALUDABLE


def test_commercial_cover_and_turns():
    assert commercial_cover_days(90, 3) == 30.0
    assert commercial_cover_days(90, 0) is None
    turns = annualized_turns(90, 30, 90)
    assert turns is not None
    assert abs(turns - 12.1666) < 0.01


def test_demand_sql_excludes_canonical_sales_docs_not_inventory_only():
    sql = build_commercial_demand_cte(as_of_date="2026-07-28").upper()
    assert "DOCUMENTOSCODIGO NOT IN" in sql
    for code in ("XY", "AS", "TS", "YX", "ISC"):
        assert f"'{code}'" in sql
    assert "BANCO_DATOS" in sql


def test_stock_sql_commercial_warehouses_and_physical_salidas():
    sql = build_commercial_stock_cte().upper()
    assert "ALMACENCODIGO IN" in sql
    assert "'ALM'" in sql
    assert "'DIS'" in sql
    assert "'CON'" not in sql
    assert "'B.ROT'" not in sql
    assert "SALDOACTUAL" in sql
    assert "SALIDASENE" in sql
    assert "AS STOCK" in sql
    assert "008050" in sql  # service SKU denylist


def test_stock_sql_does_not_filter_negative_saldo():
    sql = build_commercial_stock_cte()
    assert "SaldoActual" in sql
    assert "SaldoActual AS DECIMAL(18, 4)) >= 0" not in sql
    assert "CAST(d.SaldoActual AS DECIMAL(18, 4)) >= 0" not in sql


def test_detail_sql_joins_demand_left_warehouse_default():
    sql = build_turnover_detail_sql("2026-07-28", top_n=25).upper()
    compact = sql.replace(" ", "")
    assert "LEFT JOIN DEMANDA_COMERCIAL" in sql
    assert "DC.ALMACENCODIGO = SC.ALMACENCODIGO" in sql
    assert "INVVENTASDETALLE" in compact
    assert "TOP (25)" in sql
    assert "DIAS_COBERTURA_COMERCIAL" in sql
    assert "SALIDA_FISICA_YTD" in sql


def test_detail_sql_company_mode_joins_sku_only():
    sql = build_turnover_detail_sql(
        "2026-07-28", demand_mode=DEMAND_MODE_COMPANY, top_n=10
    ).upper()
    assert "BANCO_DATOS" in sql
    assert "DC.ARTICULOSCODIGO = SC.ARTICULOSCODIGO" in sql
    assert "DC.ALMACENCODIGO = SC.ALMACENCODIGO" not in sql


def test_warehouse_demand_cte_excludes_sales_docs_and_filters_bodegas():
    sql = build_commercial_demand_by_warehouse_cte(as_of_date="2026-07-28").upper()
    assert "INVVENTAS" in sql
    assert "INVVENTASDETALLE" in sql
    assert "ADMDOCUMENTOS" in sql
    assert "DOCUMENTOSCODIGO NOT IN" in sql
    for code in ("XY", "AS", "TS", "YX", "ISC"):
        assert f"'{code}'" in sql
    assert "ALMACENCODIGO IN" in sql
    assert "'ALM'" in sql
    assert "'CON'" not in sql


def test_enrich_and_summary_and_actions():
    raw = [
        {
            "SKU": "A",
            "Producto": "Fast",
            "AlmacenCodigo": "ALM",
            "AlmacenNombre": "001",
            "Stock": 0,
            "Venta_Comercial_Nd": 100,
            "Venta_Diaria_Comercial": 100 / 90,
            "Dias_Cobertura_Comercial": 0,
            "Salida_Fisica_Ytd": 10,
        },
        {
            "SKU": "B",
            "Producto": "Dead",
            "AlmacenCodigo": "DIS",
            "AlmacenNombre": "DIS",
            "Stock": 500,
            "Venta_Comercial_Nd": 0,
            "Venta_Diaria_Comercial": 0,
            "Dias_Cobertura_Comercial": None,
            "Salida_Fisica_Ytd": 0,
        },
        {
            "SKU": "C",
            "Producto": "Ok",
            "AlmacenCodigo": "SUR",
            "AlmacenNombre": "SUR",
            "Stock": 90,
            "Venta_Comercial_Nd": 90,
            "Venta_Diaria_Comercial": 1.0,
            "Dias_Cobertura_Comercial": 90,
            "Salida_Fisica_Ytd": 50,
        },
    ]
    enriched = enrich_detail_rows(raw)
    bands = {r["SKU"]: r["Bandera"] for r in enriched}
    assert bands["A"] == BAND_QUIEBRE
    assert bands["B"] == BAND_MUERTO
    assert bands["C"] == BAND_SALUDABLE

    summary = turnover_summary_from_rows(enriched)
    assert summary["QUIEBRE"] == 1
    assert summary["MUERTO"] == 1
    assert summary["SALUDABLE"] == 1
    assert summary["Stock_Unidades_Muerto"] == 500

    q = action_quiebre(enriched, top_n=10)
    assert len(q) == 1 and q[0]["SKU"] == "A"
    cap = action_capital_atrapado(enriched, top_n=10)
    assert len(cap) == 1 and cap[0]["SKU"] == "B"

    abc = abc_by_commercial_velocity(enriched, demand_mode=DEMAND_MODE_WAREHOUSE)
    assert abc[0]["ABC"] == "A"
    assert any(x["SKU"] == "A" for x in abc)

    # Warehouse mode sums demand across rows for same SKU
    multi = enrich_detail_rows(
        [
            {
                "SKU": "X",
                "Producto": "X",
                "AlmacenCodigo": "ALM",
                "Stock": 1,
                "Venta_Comercial_Nd": 10,
                "Venta_Diaria_Comercial": 1,
                "Dias_Cobertura_Comercial": 1,
            },
            {
                "SKU": "X",
                "Producto": "X",
                "AlmacenCodigo": "DIS",
                "Stock": 2,
                "Venta_Comercial_Nd": 5,
                "Venta_Diaria_Comercial": 0.5,
                "Dias_Cobertura_Comercial": 4,
            },
        ]
    )
    abc_wh = abc_by_commercial_velocity(multi, demand_mode=DEMAND_MODE_WAREHOUSE)
    assert abc_wh[0]["Venta_Comercial_Nd"] == 15.0
    abc_co = abc_by_commercial_velocity(multi, demand_mode=DEMAND_MODE_COMPANY)
    assert abc_co[0]["Venta_Comercial_Nd"] == 10.0


def test_service_sku_denied_from_actions():
    assert is_turnover_sku_denied("0080500001")
    rows = enrich_detail_rows(
        [
            {
                "SKU": "0080500001",
                "Producto": "TRANSPORTE",
                "AlmacenCodigo": "ALM",
                "Stock": 100000,
                "Venta_Comercial_Nd": 10,
                "Venta_Diaria_Comercial": 0.1,
                "Dias_Cobertura_Comercial": 1000000,
            },
            {
                "SKU": "GOOD1",
                "Producto": "OK",
                "AlmacenCodigo": "ALM",
                "Stock": 0,
                "Venta_Comercial_Nd": 100,
                "Venta_Diaria_Comercial": 1,
                "Dias_Cobertura_Comercial": 0,
            },
            {
                "SKU": "GOOD1",
                "Producto": "OK",
                "AlmacenCodigo": "DIS",
                "Stock": 500,
                "Venta_Comercial_Nd": 5,
                "Venta_Diaria_Comercial": 0.05,
                "Dias_Cobertura_Comercial": 10000,
            },
        ]
    )
    # force bands for transfer pair
    for r in rows:
        if r["SKU"] == "GOOD1" and r["AlmacenCodigo"] == "ALM":
            r["Bandera"] = BAND_QUIEBRE
        if r["SKU"] == "GOOD1" and r["AlmacenCodigo"] == "DIS":
            r["Bandera"] = BAND_SOBRESTOCK
        if r["SKU"] == "0080500001":
            r["Bandera"] = BAND_SOBRESTOCK

    cap = action_capital_atrapado(rows, top_n=10)
    assert all(r["SKU"] != "0080500001" for r in cap)

    q = action_quiebre(rows, top_n=10, one_row_per_sku=True)
    assert len(q) == 1 and q[0]["SKU"] == "GOOD1" and q[0]["AlmacenCodigo"] == "ALM"

    xfers = suggested_transfers(rows, top_n=10, min_surplus=10)
    assert xfers
    assert xfers[0]["Desde"] == "DIS"
    assert xfers[0]["Hacia"] == "ALM"
    assert xfers[0]["SKU"] == "GOOD1"
