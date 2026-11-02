/*
Shipping slice B — depotru-inbox tables
=======================================
Run against SmartBusiness during a maintenance window. Idempotent: every
object is guarded, so re-running after a partial deploy is safe.

The inbox is the only place a Magento order becomes loadable freight:
weight_kg is NOT NULL and CHECK (> 0) because dispatch plans trucks from it —
an order without a weight must be refused upstream, never defaulted to zero.

Policy numbers (threshold, max wait) live in code, not here: they are
candidate values pending sign-off, and a rate change must never require DDL.
*/

IF OBJECT_ID('dbo.depotru_inbox_orders', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.depotru_inbox_orders (
        order_id          BIGINT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_depotru_inbox_orders PRIMARY KEY,
        magento_order_id  NVARCHAR(64)  NOT NULL,
        store_id          INT           NULL,
        customer_id       INT           NULL,
        weight_kg         DECIMAL(12,3) NOT NULL
            CONSTRAINT CK_depotru_inbox_orders_weight CHECK (weight_kg > 0),
        dest_city         NVARCHAR(120) NOT NULL,
        dest_department   NVARCHAR(120) NOT NULL CONSTRAINT DF_inbox_orders_dept DEFAULT '',
        site              VARCHAR(16)   NOT NULL
            CONSTRAINT CK_depotru_inbox_orders_site CHECK (site IN ('neiva', 'florencia')),
        placed_at         DATETIME2(0)  NOT NULL,
        status            VARCHAR(16)   NOT NULL CONSTRAINT DF_inbox_orders_status DEFAULT 'pending'
            CONSTRAINT CK_depotru_inbox_orders_status
                CHECK (status IN ('pending', 'assigned', 'dispatched', 'cancelled')),
        trip_id           NVARCHAR(32)  NULL,
        created_at        DATETIME2(0)  NOT NULL CONSTRAINT DF_inbox_orders_created DEFAULT SYSUTCDATETIME(),
        updated_at        DATETIME2(0)  NOT NULL CONSTRAINT DF_inbox_orders_updated DEFAULT SYSUTCDATETIME()
    );

    -- One row per Magento order: the consumer may replay, the load may not fork.
    CREATE UNIQUE INDEX UX_depotru_inbox_orders_magento
        ON dbo.depotru_inbox_orders (magento_order_id);

    -- Dispatch reads pending rows per site in FIFO order.
    CREATE INDEX IX_depotru_inbox_orders_pending
        ON dbo.depotru_inbox_orders (site, status, placed_at)
        INCLUDE (weight_kg, dest_city, dest_department);
END;
GO

IF OBJECT_ID('dbo.depotru_inbox_vehicles', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.depotru_inbox_vehicles (
        plate        NVARCHAR(20)  NOT NULL
            CONSTRAINT PK_depotru_inbox_vehicles PRIMARY KEY,
        capacity_kg  DECIMAL(12,3) NOT NULL
            CONSTRAINT CK_depotru_inbox_vehicles_capacity CHECK (capacity_kg > 0),
        site         VARCHAR(16)   NOT NULL
            CONSTRAINT CK_depotru_inbox_vehicles_site CHECK (site IN ('neiva', 'florencia')),
        is_active    BIT           NOT NULL CONSTRAINT DF_inbox_vehicles_active DEFAULT 1,
        notes        NVARCHAR(400) NULL,
        updated_at   DATETIME2(0)  NOT NULL CONSTRAINT DF_inbox_vehicles_updated DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID('dbo.depotru_inbox_trips', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.depotru_inbox_trips (
        trip_id          NVARCHAR(32)  NOT NULL
            CONSTRAINT PK_depotru_inbox_trips PRIMARY KEY,
        vehicle_plate    NVARCHAR(20)  NOT NULL,
        site             VARCHAR(16)   NOT NULL
            CONSTRAINT CK_depotru_inbox_trips_site CHECK (site IN ('neiva', 'florencia')),
        total_weight_kg  DECIMAL(12,3) NOT NULL
            CONSTRAINT CK_depotru_inbox_trips_weight CHECK (total_weight_kg > 0),
        reason           VARCHAR(16)   NOT NULL
            CONSTRAINT CK_depotru_inbox_trips_reason
                CHECK (reason IN ('threshold', 'max_wait', 'dedicated')),
        state            VARCHAR(16)   NOT NULL CONSTRAINT DF_inbox_trips_state DEFAULT 'planned'
            CONSTRAINT CK_depotru_inbox_trips_state
                CHECK (state IN ('planned', 'loading', 'dispatched', 'closed', 'cancelled')),
        created_by       NVARCHAR(80)  NOT NULL,
        created_at       DATETIME2(0)  NOT NULL CONSTRAINT DF_inbox_trips_created DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_depotru_inbox_trips_vehicle
            FOREIGN KEY (vehicle_plate) REFERENCES dbo.depotru_inbox_vehicles (plate)
    );

    CREATE INDEX IX_depotru_inbox_trips_site_state
        ON dbo.depotru_inbox_trips (site, state, created_at);
END;
GO

IF OBJECT_ID('dbo.depotru_inbox_trip_orders', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.depotru_inbox_trip_orders (
        trip_id          NVARCHAR(32)  NOT NULL,
        magento_order_id NVARCHAR(64)  NOT NULL,
        weight_kg        DECIMAL(12,3) NOT NULL
            CONSTRAINT CK_depotru_inbox_trip_orders_weight CHECK (weight_kg > 0),
        CONSTRAINT PK_depotru_inbox_trip_orders PRIMARY KEY (trip_id, magento_order_id),
        CONSTRAINT FK_depotru_inbox_trip_orders_trip
            FOREIGN KEY (trip_id) REFERENCES dbo.depotru_inbox_trips (trip_id),
        CONSTRAINT FK_depotru_inbox_trip_orders_order
            FOREIGN KEY (magento_order_id) REFERENCES dbo.depotru_inbox_orders (magento_order_id)
    );
END;
GO
