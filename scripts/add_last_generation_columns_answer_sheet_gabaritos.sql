-- Adiciona colunas last_generation_classes_count e last_generation_students_count
-- na tabela answer_sheet_gabaritos em TODOS os schemas city_xxx.
-- Executar no PostgreSQL conectado ao banco do projeto.
--
-- Uso: psql -U seu_usuario -d seu_banco -f scripts/add_last_generation_columns_answer_sheet_gabaritos.sql

DO $$
DECLARE
  r RECORD;
BEGIN
  FOR r IN (SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'city_%')
  LOOP
    EXECUTE format('ALTER TABLE %I.answer_sheet_gabaritos ADD COLUMN IF NOT EXISTS last_generation_classes_count INTEGER NULL', r.schema_name);
    EXECUTE format('ALTER TABLE %I.answer_sheet_gabaritos ADD COLUMN IF NOT EXISTS last_generation_students_count INTEGER NULL', r.schema_name);
    RAISE NOTICE 'Schema %: colunas adicionadas.', r.schema_name;
  END LOOP;
END $$;
