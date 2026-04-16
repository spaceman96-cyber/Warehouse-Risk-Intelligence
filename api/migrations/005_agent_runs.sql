-- 005_agent_runs.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS agent_runs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  agent_name TEXT NOT NULL,
  score_date DATE,
  auto_open BOOLEAN DEFAULT FALSE,
  max_to_open INT,
  opened INT DEFAULT 0,
  skipped INT DEFAULT 0,
  created_ids JSONB DEFAULT '[]'::jsonb,
  status TEXT DEFAULT 'success',
  error TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at
ON agent_runs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_name
ON agent_runs(agent_name);