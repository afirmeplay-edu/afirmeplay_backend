-- Migração: Corrigir test.type = null para testes vinculados a competições
-- Execute este script MANUALMENTE no banco de dados (psql ou pg admin)
-- 
-- O que ele faz:
--   1. Em public.test: atualiza type='COMPETICAO' e model='COMPETICAO' onde o test
--      está vinculado a uma competição em public.competitions mas type é null.
--   2. Para cada schema city_xxx: mesma correção nos testes vinculados à competitions daquele schema.
--
-- Execute via:  psql -U <usuario> -d <banco> -f fix_competition_test_type.sql

-- ============================================================
-- 1. Corrigir em public.test (competições em public.competitions)
-- ============================================================
UPDATE public.test t
SET
    type  = 'COMPETICAO',
    model = COALESCE(t.model, 'COMPETICAO')
WHERE t.id IN (
    SELECT test_id
    FROM public.competitions
    WHERE test_id IS NOT NULL
)
AND (t.type IS NULL OR t.type != 'COMPETICAO');

-- ============================================================
-- 2. Corrigir em cada schema city_xxx (competições em city schemas)
-- ============================================================
-- Execute o bloco abaixo substituindo city_<uuid> pelo schema correto,
-- ou rode o DO $$ ... $$ dinâmico abaixo que itera todos os schemas.

DO $$
DECLARE
    schema_name TEXT;
BEGIN
    FOR schema_name IN
        SELECT n.nspname
        FROM pg_namespace n
        JOIN pg_class c ON c.relnamespace = n.oid AND c.relname = 'competitions'
        WHERE n.nspname LIKE 'city_%'
    LOOP
        BEGIN
            EXECUTE format(
                'UPDATE %I.test t
                 SET type  = ''COMPETICAO'',
                     model = COALESCE(t.model, ''COMPETICAO'')
                 WHERE t.id IN (
                     SELECT test_id FROM %I.competitions WHERE test_id IS NOT NULL
                 )
                 AND (t.type IS NULL OR t.type != ''COMPETICAO'')',
                schema_name, schema_name
            );
            RAISE NOTICE 'Atualizado schema: %', schema_name;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'Erro no schema %: %', schema_name, SQLERRM;
        END;
    END LOOP;
END $$;

-- Verificar resultado:
SELECT id, type, model, title FROM public.test
WHERE id IN (SELECT test_id FROM public.competitions WHERE test_id IS NOT NULL)
ORDER BY created_at DESC
LIMIT 20;
