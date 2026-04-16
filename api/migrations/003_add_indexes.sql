-- api/migrations/003_add_indexes.sql

CREATE INDEX IF NOT EXISTS idx_investigations_created_at
ON investigations(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_investigations_source
ON investigations(source);

CREATE INDEX IF NOT EXISTS idx_investigations_dedupe
ON investigations(dedupe_key);

CREATE INDEX IF NOT EXISTS idx_adjustments_sku
ON adjustments(sku_code);

CREATE INDEX IF NOT EXISTS idx_adjustments_zone
ON adjustments(zone);

CREATE INDEX IF NOT EXISTS idx_adjustments_user
ON adjustments(user_ref);