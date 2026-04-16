-- 004_extend_sku_master.sql
ALTER TABLE sku_master ADD COLUMN IF NOT EXISTS abc_class TEXT;
ALTER TABLE sku_master ADD COLUMN IF NOT EXISTS value_band TEXT;
ALTER TABLE sku_master ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();