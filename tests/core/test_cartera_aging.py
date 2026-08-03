"""Unit tests for cartera / AR aging (no live DB)."""

from business_analyzer.core.cartera_aging import (
    SNAPSHOT_SELECT_COLUMNS,
    aggregate_clients,
    bucket_breakdown,
    build_dso_sales_sql,
    build_report_from_rows,
    build_snapshot_sql,
    compute_dso,
    compute_summary,
    over_limit_clients,
    top_concentration,
    top_overdue,
)


def _sample_rows():
    return [
        {
            "cliente_uid": 1,
            "cliente_nit": "9001",
            "cliente_razon_social": "Cliente Alfa",
            "cliente_ciudad": "Cali",
            "cliente_departamento": "Valle",
            "vendedor_nombre": "Ana",
            "corriente": 100_000,
            "vencido": 50_000,
            "vencido_30": 50_000,
            "vencido_60": 0,
            "vencido_90": 0,
            "vencido_120": 0,
            "vencido_360": 0,
            "vencido_superior": 0,
            "total": 150_000,
            "dias_vencidos": 20,
            "cliente_cupo": 200_000,
            "fecha_carga": "2026-07-28 19:00:00",
        },
        {
            "cliente_uid": 1,
            "cliente_nit": "9001",
            "cliente_razon_social": "Cliente Alfa",
            "cliente_ciudad": "Cali",
            "cliente_departamento": "Valle",
            "vendedor_nombre": "Ana",
            "corriente": 0,
            "vencido": 80_000,
            "vencido_30": 0,
            "vencido_60": 0,
            "vencido_90": 80_000,
            "vencido_120": 0,
            "vencido_360": 0,
            "vencido_superior": 0,
            "total": 80_000,
            "dias_vencidos": 95,
            "cliente_cupo": 200_000,
            "fecha_carga": "2026-07-28 19:00:00",
        },
        {
            "cliente_uid": 2,
            "cliente_nit": "9002",
            "cliente_razon_social": "Cliente Beta",
            "cliente_ciudad": "Bogotá",
            "cliente_departamento": "Cundinamarca",
            "vendedor_nombre": "Luis",
            "corriente": 500_000,
            "vencido": 0,
            "vencido_30": 0,
            "vencido_60": 0,
            "vencido_90": 0,
            "vencido_120": 0,
            "vencido_360": 0,
            "vencido_superior": 0,
            "total": 500_000,
            "dias_vencidos": 0,
            "cliente_cupo": 300_000,
            "fecha_carga": "2026-07-28 19:00:00",
        },
        {
            "cliente_uid": 3,
            "cliente_nit": "9003",
            "cliente_razon_social": "Cliente Gamma",
            "cliente_ciudad": "Medellín",
            "cliente_departamento": "Antioquia",
            "vendedor_nombre": "Ana",
            "corriente": 0,
            "vencido": 1_000_000,
            "vencido_30": 0,
            "vencido_60": 0,
            "vencido_90": 0,
            "vencido_120": 200_000,
            "vencido_360": 800_000,
            "vencido_superior": 0,
            "total": 1_000_000,
            "dias_vencidos": 200,
            "cliente_cupo": 2_000_000,
            "fecha_carga": "2026-07-28 19:00:00",
        },
    ]


def test_snapshot_sql_uses_max_fecha_carga_and_limited_columns():
    sql = build_snapshot_sql().upper()
    assert "BANCO_CARTERA" in sql
    assert "MAX(FECHA_CARGA)" in sql
    for col in SNAPSHOT_SELECT_COLUMNS:
        assert col.upper() in sql
    # No document-level noise columns in SELECT
    assert "DOCUMENTO_NUMERO" not in sql
    assert "DEBITOS" not in sql


def test_snapshot_sql_as_of_filter():
    sql = build_snapshot_sql(as_of_date="2026-07-28")
    assert "CAST(fecha_carga AS DATE)" in sql
    assert "2026-07-28" in sql


def test_dso_sales_sql_excludes_test_docs():
    sql = build_dso_sales_sql(as_of_date="2026-07-28", dso_days=30).upper()
    assert "BANCO_DATOS" in sql
    assert "DOCUMENTOSCODIGO NOT IN" in sql
    for code in ("XY", "AS", "TS"):
        assert f"'{code}'" in sql
    assert "TOTALSINIVA" in sql


def test_aggregate_clients_sums_and_over_limit():
    clients = aggregate_clients(_sample_rows())
    assert len(clients) == 3
    alfa = next(c for c in clients if c["cliente_uid"] == 1)
    assert alfa["total"] == 230_000
    assert alfa["vencido"] == 130_000
    assert alfa["dias_vencidos"] == 95
    assert alfa["documentos"] == 2
    # total 230k > cupo 200k
    assert alfa["sobre_cupo"] is True
    beta = next(c for c in clients if c["cliente_uid"] == 2)
    assert beta["sobre_cupo"] is True  # 500k > 300k cupo
    gamma = next(c for c in clients if c["cliente_uid"] == 3)
    assert gamma["sobre_cupo"] is False
    assert gamma["vencido_90_plus"] == 1_000_000


def test_summary_and_buckets_q9_aligned():
    clients = aggregate_clients(_sample_rows())
    summary = compute_summary(
        clients, document_row_count=4, dso_dias=40.0, ventas_netas=1e6
    )
    assert summary["Cartera_Total"] == 1_730_000
    assert summary["Cartera_Vencida"] == 1_130_000
    assert abs(summary["Cartera_Vencida_Pct"] - (1_130_000 * 100 / 1_730_000)) < 0.01
    assert summary["Cartera_Vencida_90_Plus"] == 1_080_000  # 80k + 1M
    assert summary["Clientes_Sobre_Cupo"] == 2
    assert summary["DSO_Dias"] == 40.0
    buckets = bucket_breakdown(summary)
    assert len(buckets) == 7
    assert sum(b["amount"] for b in buckets) == (
        summary["Bucket_Corriente"]
        + summary["Bucket_Vencido_30"]
        + summary["Bucket_Vencido_60"]
        + summary["Bucket_Vencido_90"]
        + summary["Bucket_Vencido_120"]
        + summary["Bucket_Vencido_360"]
        + summary["Bucket_Vencido_Superior"]
    )


def test_top_overdue_concentration_over_limit():
    clients = aggregate_clients(_sample_rows())
    od = top_overdue(clients, top_n=5)
    assert od[0]["cliente_razon_social"] == "Cliente Gamma"
    conc = top_concentration(clients, top_n=10)
    assert conc[0]["cliente_razon_social"] == "Cliente Gamma"
    assert conc[0]["share_acum"] > 0.5
    ol = over_limit_clients(clients)
    assert len(ol) == 2


def test_compute_dso():
    # cartera 1_000_000, ventas 500_000 over 30 days → DSO = 60
    assert abs(compute_dso(1_000_000, 500_000, 30) - 60.0) < 0.01
    assert compute_dso(1_000_000, 0, 30) == 0.0


def test_build_report_from_rows_structure():
    report = build_report_from_rows(
        _sample_rows(),
        as_of_date="2026-07-28",
        top_n=10,
        dso_days=30,
        ventas_netas=2_000_000,
        include_dso=True,
    )
    assert report["as_of_date"] == "2026-07-28"
    assert report["source"] == "banco_cartera"
    assert "XY" in report["excluded_document_codes"]
    assert report["summary"]["Cartera_Total"] == 1_730_000
    assert report["summary"]["DSO_Dias"] is not None
    assert report["top_overdue"]
    assert report["buckets"]
    assert report["client_count"] == 3
