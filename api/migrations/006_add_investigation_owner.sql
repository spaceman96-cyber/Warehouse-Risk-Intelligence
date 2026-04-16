-- 006_add_investigation_owner.sql
ALTER TABLE investigations
ADD COLUMN IF NOT EXISTS owner TEXT;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS closed_at TIMESTAMP;
ALTER TABLE investigations ADD COLUMN IF NOT EXISTS notes TEXT;