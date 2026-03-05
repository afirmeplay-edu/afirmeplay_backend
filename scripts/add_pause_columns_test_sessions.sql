-- Adiciona colunas de pausa do timer em test_sessions (todos os schemas).
-- Execute com: psql -d SUA_BASE -f scripts/add_pause_columns_test_sessions.sql
-- Ou rode no cliente SQL de sua preferência.

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN
    SELECT DISTINCT table_schema
    FROM information_schema.tables
    WHERE table_name = 'test_sessions'
  LOOP
    EXECUTE format(
      'ALTER TABLE %I.test_sessions ADD COLUMN IF NOT EXISTS paused_at TIMESTAMP NULL'
    , r.table_schema);
    EXECUTE format(
      'ALTER TABLE %I.test_sessions ADD COLUMN IF NOT EXISTS total_paused_seconds INTEGER NOT NULL DEFAULT 0'
    , r.table_schema);
    RAISE NOTICE 'Schema %: colunas adicionadas.', r.table_schema;
  END LOOP;
END $$;
