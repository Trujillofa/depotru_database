/*
Affinity performance: indexes + co-occurrence mart
====================================================
Run against SmartBusiness during a maintenance window.
Excludes test documents per business rules (XY, AS, TS).

Refresh mart nightly:
  PYTHONPATH=src python scripts/analysis/refresh_affinity_mart.py

Enable mart reads in affinity pipeline:
  AFFINITY_USE_MART=1 python -m business_analyzer.analysis.affinity
*/

-- ---------------------------------------------------------------------------
-- Recommended indexes on banco_datos (heap table — high impact for affinity)
-- ---------------------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_banco_datos_ticket_products'
      AND object_id = OBJECT_ID('dbo.banco_datos')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_banco_datos_ticket_products
    ON dbo.banco_datos (DocumentosCodigo, NumeroDocumento)
    INCLUDE (ArticulosCodigo, ArticulosNombre, Fecha, TercerosID);
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_banco_datos_terceros_fecha'
      AND object_id = OBJECT_ID('dbo.banco_datos')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_banco_datos_terceros_fecha
    ON dbo.banco_datos (TercerosID, Fecha)
    INCLUDE (ArticulosCodigo, ArticulosNombre, DocumentosCodigo);
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_banco_datos_fecha_docs'
      AND object_id = OBJECT_ID('dbo.banco_datos')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_banco_datos_fecha_docs
    ON dbo.banco_datos (Fecha, DocumentosCodigo)
    INCLUDE (ArticulosCodigo, TotalSinIva, TercerosNombres);
END;

-- ---------------------------------------------------------------------------
-- Pre-aggregated ticket co-occurrence mart
-- ---------------------------------------------------------------------------
IF OBJECT_ID('dbo.affinity_co_occurrence', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.affinity_co_occurrence (
        sku_a       NVARCHAR(50)  NOT NULL,
        sku_b       NVARCHAR(50)  NOT NULL,
        name_a      NVARCHAR(200) NULL,
        name_b      NVARCHAR(200) NULL,
        co_count    INT           NOT NULL,
        refreshed_at DATETIME2    NOT NULL DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_affinity_co_occurrence PRIMARY KEY (sku_a, sku_b)
    );
END;

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_affinity_co_occurrence_count'
      AND object_id = OBJECT_ID('dbo.affinity_co_occurrence')
)
BEGIN
    CREATE NONCLUSTERED INDEX IX_affinity_co_occurrence_count
    ON dbo.affinity_co_occurrence (co_count DESC)
    INCLUDE (name_a, name_b);
END;
