-- Add columns your ingest expects
ALTER TABLE adjustments
  ADD COLUMN IF NOT EXISTS adjustment_type TEXT,
  ADD COLUMN IF NOT EXISTS row_hash TEXT;

-- Optional but recommended: make row_hash unique so dedupe works
CREATE UNIQUE INDEX IF NOT EXISTS uq_adjustments_row_hash
ON adjustments(row_hash);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_adjustments_timestamp
ON adjustments(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_adjustments_location
ON adjustments(location_code);