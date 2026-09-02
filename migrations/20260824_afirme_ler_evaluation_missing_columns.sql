-- Afirme Ler — colunas que o modelo já usa e os city_* ainda não têm
--
-- reading_evaluation: student_ids, evaluation_kind
-- reading_fluency_session: reading_evaluation_id (próximo insert da aplicação)
--
-- Uso:
--   psql ... -f migrations/20260824_afirme_ler_evaluation_missing_columns.sql

BEGIN;

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname LIKE 'city_%'
        ORDER BY nspname
    LOOP
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = schema_name
              AND table_name = 'reading_evaluation'
        ) THEN
            RAISE NOTICE 'Schema % sem reading_evaluation — pulado.', schema_name;
            CONTINUE;
        END IF;

        EXECUTE format(
            'ALTER TABLE %I.reading_evaluation
             ADD COLUMN IF NOT EXISTS student_ids JSON NOT NULL DEFAULT ''[]''::json',
            schema_name
        );
        EXECUTE format(
            'ALTER TABLE %I.reading_evaluation
             ADD COLUMN IF NOT EXISTS evaluation_kind VARCHAR(20) NOT NULL DEFAULT ''formativa''',
            schema_name
        );
        EXECUTE format(
            'ALTER TABLE %I.reading_evaluation
             DROP CONSTRAINT IF EXISTS chk_reading_evaluation_kind',
            schema_name
        );
        EXECUTE format(
            'ALTER TABLE %I.reading_evaluation
             ADD CONSTRAINT chk_reading_evaluation_kind
             CHECK (evaluation_kind IN (''entrada'', ''formativa'', ''saida''))',
            schema_name
        );
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS ix_reading_evaluation_kind
             ON %I.reading_evaluation(evaluation_kind)',
            schema_name
        );

        IF EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = schema_name
              AND table_name = 'reading_fluency_session'
        ) THEN
            EXECUTE format(
                'ALTER TABLE %I.reading_fluency_session
                 ADD COLUMN IF NOT EXISTS reading_evaluation_id VARCHAR
                 REFERENCES %I.reading_evaluation(id)',
                schema_name, schema_name
            );
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS ix_reading_fluency_session_evaluation
                 ON %I.reading_fluency_session(reading_evaluation_id)',
                schema_name
            );
        END IF;

        RAISE NOTICE 'Atualizado schema %', schema_name;
    END LOOP;
END $$;

COMMIT;

SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'city_9a2f95ed_9f70_4863_a5f1_1b6c6c262b0d'
  AND table_name = 'reading_evaluation'
  AND column_name IN ('student_ids', 'evaluation_kind', 'grade_ids')
ORDER BY column_name;
