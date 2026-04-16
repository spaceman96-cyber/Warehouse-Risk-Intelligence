-- api/migrations/001_init.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS investigations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT,
    status TEXT DEFAULT 'open',
    severity TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS adjustments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sku_code TEXT,
    zone TEXT,
    user_ref TEXT,
    qty_delta NUMERIC,
    timestamp TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sku_master (
    sku_code TEXT PRIMARY KEY,
    sku_name TEXT,
    category TEXT,
    unit_cost NUMERIC
);

CREATE TABLE IF NOT EXISTS ingest_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);