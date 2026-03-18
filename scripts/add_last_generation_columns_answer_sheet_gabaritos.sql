-- Adiciona colunas last_generation_classes_count e last_generation_students_count
-- na tabela answer_sheet_gabaritos em todos os schemas city_xxx que possuem a tabela.
-- Idempotente: usa ADD COLUMN IF NOT EXISTS (não falha se a coluna já existir).
--
-- Uso: psql -U seu_usuario -d seu_banco -f scripts/add_last_generation_columns_answer_sheet_gabaritos.sql

DO $$
DECLARE
  r RECORD;
  tbl regclass;
BEGIN
  FOR r IN (
    SELECT n.nspname AS schema_name
    FROM pg_namespace n
    JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = 'answer_sheet_gabaritos'
    WHERE n.nspname LIKE 'city_%'
  )
  LOOP
    EXECUTE format(
      'ALTER TABLE %I.answer_sheet_gabaritos ADD COLUMN IF NOT EXISTS last_generation_classes_count INTEGER NULL',
      r.schema_name
    );
    EXECUTE format(
      'ALTER TABLE %I.answer_sheet_gabaritos ADD COLUMN IF NOT EXISTS last_generation_students_count INTEGER NULL',
      r.schema_name
    );
    RAISE NOTICE 'Schema %: colunas last_generation_* adicionadas/verificadas.', r.schema_name;
  END LOOP;
END $$;
