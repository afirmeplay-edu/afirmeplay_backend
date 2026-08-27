-- Afirme Ler — aplicar no banco (psql)
--
-- 1) public.reading_word_list: PALAVRAS → PALAVRAS_CONHECIDAS
--    (substitui a migration Alembic 20260820_afirme_ler_known_words, que foi removida)
-- 2) city_*: reading_evaluation.grade_ids (várias séries) + backfill a partir de grade_id
--
-- Uso:
--   psql -h HOST -p PORTA -U postgres -d afirmeplay_dev -f migrations/20260824_afirme_ler_word_lists_and_grade_ids.sql
--
-- Idempotente: pode rodar de novo.

BEGIN;

-- ============================================================
-- 1. Listas de palavras (schema public)
-- ============================================================
ALTER TABLE public.reading_word_list
    DROP CONSTRAINT IF EXISTS ck_reading_word_list_kind;

UPDATE public.reading_word_list
SET kind = 'PALAVRAS_CONHECIDAS'
WHERE kind = 'PALAVRAS';

ALTER TABLE public.reading_word_list
    ALTER COLUMN kind SET DEFAULT 'PALAVRAS_CONHECIDAS';

ALTER TABLE public.reading_word_list
    ADD CONSTRAINT ck_reading_word_list_kind
    CHECK (kind IN ('PALAVRAS_CONHECIDAS', 'POUCO_COMUNS'));

-- ============================================================
-- 2. Avaliações: várias séries em cada schema city_*
-- ============================================================
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
             ADD COLUMN IF NOT EXISTS grade_ids JSON NOT NULL DEFAULT ''[]''::json',
            schema_name
        );
        EXECUTE format(
            'UPDATE %I.reading_evaluation
             SET grade_ids = json_build_array(grade_id::text)
             WHERE grade_id IS NOT NULL
               AND (grade_ids IS NULL OR COALESCE(json_array_length(grade_ids), 0) = 0)',
            schema_name
        );
        RAISE NOTICE 'grade_ids atualizado em %', schema_name;
    END LOOP;
END $$;

COMMIT;

-- Conferência: kinds das listas
SELECT kind, COUNT(*) AS n
FROM public.reading_word_list
GROUP BY kind
ORDER BY kind;

-- Conferência: grade_ids por município (só schemas que têm a tabela)
DO $$
DECLARE
    schema_name TEXT;
    total_n INTEGER;
    filled_n INTEGER;
BEGIN
    FOR schema_name IN
        SELECT nspname FROM pg_namespace WHERE nspname LIKE 'city_%' ORDER BY nspname
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = schema_name AND table_name = 'reading_evaluation'
        ) THEN
            EXECUTE format(
                'SELECT COUNT(*), COUNT(*) FILTER (WHERE COALESCE(json_array_length(grade_ids), 0) > 0)
                 FROM %I.reading_evaluation',
                schema_name
            ) INTO total_n, filled_n;
            RAISE NOTICE '%: % avaliações, % com grade_ids', schema_name, total_n, filled_n;
        END IF;
    END LOOP;
END $$;
