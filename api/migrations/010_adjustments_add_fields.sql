-- Add the columns your ingest/scoring expects
ALTER TABLE adjustments
ADD COLUMN IF NOT EXISTS adjustment_type TEXT;

ALTER TABLE adjustments
ADD COLUMN IF NOT EXISTS row_hash TEXT;

-- Strongly recommended: prevent duplicates if you use row_hash for dedupe
CREATE UNIQUE INDEX IF NOT EXISTS uq_adjustments_row_hash
ON adjustments(row_hash);

-- Optional but useful for performance
CREATE INDEX IF NOT EXISTS idx_adjustments_ts
ON adjustments(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_adjustments_loc
ON adjustments(location_code);