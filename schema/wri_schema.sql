-- ============================================================
-- Warehouse Risk Intelligence (WRI) — MVP v0.1
-- PostgreSQL Schema
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- CORE ENTITIES
-- ============================================================

CREATE TABLE orgs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    region      TEXT,                          -- e.g. SG, MY, AU
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE sites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    country     TEXT,
    timezone    TEXT DEFAULT 'Asia/Singapore',
    wms_name    TEXT,                          -- e.g. SAP EWM, Manhattan
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE clients (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE site_clients (
    site_id     UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    client_id   UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    PRIMARY KEY (site_id, client_id)
);

-- ============================================================
-- DIMENSIONS
-- ============================================================

CREATE TABLE sku_master (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    client_id       UUID REFERENCES clients(id),
    sku             TEXT NOT NULL,
    description     TEXT,
    uom             TEXT,
    category        TEXT,
    abc_class       TEXT,                      -- A / B / C
    unit_cost       NUMERIC(12,4),
    value_band      TEXT,                      -- low / med / high
    avg_monthly_movement INT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (site_id, client_id, sku)
);

CREATE TABLE locations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    client_id       UUID REFERENCES clients(id),
    location_code   TEXT NOT NULL,
    zone            TEXT,
    area            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (site_id, client_id, location_code)
);

CREATE TABLE users_dim (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id     UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    user_ref    TEXT NOT NULL,                 -- WMS username / employee ID
    role        TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (site_id, user_ref)
);

-- ============================================================
-- DATA INGESTION TRACKING
-- ============================================================

CREATE TABLE data_imports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID NOT NULL REFERENCES sites(id),
    client_id       UUID REFERENCES clients(id),
    import_type     TEXT NOT NULL CHECK (import_type IN (
                        'adjustments','cycle_counts','sku_master',
                        'locations','inventory_snapshot'
                    )),
    source_filename TEXT,
    source_hash     TEXT,                      -- SHA256 for dedup
    rows_total      INT DEFAULT 0,
    rows_loaded     INT DEFAULT 0,
    status          TEXT DEFAULT 'pending' CHECK (status IN (
                        'pending','loaded','failed'
                    )),
    error_message   TEXT,
    imported_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- OPERATIONAL FACTS
-- ============================================================

CREATE TABLE inventory_adjustments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id             UUID NOT NULL REFERENCES sites(id),
    client_id           UUID REFERENCES clients(id),
    event_ts            TIMESTAMPTZ NOT NULL,
    sku                 TEXT NOT NULL,
    location_code       TEXT,
    qty_delta           NUMERIC NOT NULL,      -- negative = loss, positive = found
    adjustment_type     TEXT,                  -- CycleCount / Damage / Returns / Unknown
    reason_code         TEXT,
    doc_ref             TEXT,
    user_ref            TEXT,
    shift               TEXT,                  -- Morning / Afternoon / Night
    remarks             TEXT,
    system_qty_before   NUMERIC,
    physical_qty_found  NUMERIC,
    source_import_id    UUID REFERENCES data_imports(id),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Core query indexes
CREATE INDEX idx_adj_site_ts         ON inventory_adjustments (site_id, client_id, event_ts);
CREATE INDEX idx_adj_site_sku_ts     ON inventory_adjustments (site_id, client_id, sku, event_ts);
CREATE INDEX idx_adj_site_loc_ts     ON inventory_adjustments (site_id, client_id, location_code, event_ts);
CREATE INDEX idx_adj_site_user_ts    ON inventory_adjustments (site_id, client_id, user_ref, event_ts);

CREATE TABLE cycle_counts (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id             UUID NOT NULL REFERENCES sites(id),
    client_id           UUID REFERENCES clients(id),
    count_ts            TIMESTAMPTZ NOT NULL,
    sku                 TEXT NOT NULL,
    location_code       TEXT,
    system_qty          NUMERIC,
    counted_qty         NUMERIC NOT NULL,
    variance_qty        NUMERIC GENERATED ALWAYS AS (counted_qty - system_qty) STORED,
    counter_ref         TEXT,
    source_import_id    UUID REFERENCES data_imports(id),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- RISK OUTPUTS
-- ============================================================

CREATE TABLE risk_scores_daily (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID NOT NULL REFERENCES sites(id),
    client_id       UUID REFERENCES clients(id),
    score_date      DATE NOT NULL,
    entity_type     TEXT NOT NULL CHECK (entity_type IN ('sku','zone','location','user')),
    entity_key      TEXT NOT NULL,             -- sku code / zone / location / user_ref
    risk_score      INT CHECK (risk_score BETWEEN 0 AND 100),
    signals         JSONB,                     -- {"freq_7d":12,"drift":1.6,"value_band":"high"}
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (site_id, client_id, score_date, entity_type, entity_key)
);

CREATE INDEX idx_risk_site_date ON risk_scores_daily (site_id, score_date, entity_type);

CREATE TABLE cycle_count_recommendations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID NOT NULL REFERENCES sites(id),
    client_id       UUID REFERENCES clients(id),
    rec_date        DATE NOT NULL,
    sku             TEXT NOT NULL,
    location_code   TEXT,
    priority        INT,                       -- 1 = highest priority
    reason          TEXT,
    signals         JSONB,
    status          TEXT DEFAULT 'proposed' CHECK (status IN (
                        'proposed','accepted','done','skipped'
                    )),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INVESTIGATION WORKFLOW
-- ============================================================

CREATE TABLE investigations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id         UUID NOT NULL REFERENCES sites(id),
    client_id       UUID REFERENCES clients(id),
    title           TEXT NOT NULL,
    status          TEXT DEFAULT 'open' CHECK (status IN (
                        'open','in_progress','blocked','closed'
                    )),
    severity        TEXT DEFAULT 'med' CHECK (severity IN ('low','med','high')),
    owner           TEXT,
    opened_at       TIMESTAMPTZ DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    root_cause_tag  TEXT CHECK (root_cause_tag IN (
                        'mis-pick','receiving','theft','system','unknown'
                    )),
    summary         TEXT
);

CREATE TABLE investigation_links (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id    UUID NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    link_type           TEXT NOT NULL CHECK (link_type IN (
                            'sku','zone','location','user',
                            'adjustment_event','cycle_count'
                        )),
    link_key            TEXT NOT NULL,
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- END OF SCHEMA
-- ============================================================
