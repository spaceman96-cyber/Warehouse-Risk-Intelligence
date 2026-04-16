-- api/migrations/008_extend_adjustments_location.sql

ALTER TABLE adjustments
  ADD COLUMN IF NOT EXISTS location_code TEXT;