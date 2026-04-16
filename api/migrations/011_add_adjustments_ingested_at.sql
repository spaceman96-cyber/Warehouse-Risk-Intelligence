ALTER TABLE adjustments
ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_adjustments_ingested_at
ON adjustments(ingested_at DESC);