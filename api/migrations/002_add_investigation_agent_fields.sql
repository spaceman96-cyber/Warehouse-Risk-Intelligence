-- api/migrations/002_add_investigation_agent_fields.sql

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS confidence INT;

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS source TEXT;

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS dedupe_key TEXT UNIQUE;

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS evidence JSONB;

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS checklist JSONB;

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS hypothesis TEXT;

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS sku_code TEXT;

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS zone TEXT;

ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS user_ref TEXT;