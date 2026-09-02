-- Afirme Ler — série nas listas de palavras
--
-- Adiciona public.reading_word_list.grade_id.
-- Listas já existentes ficam com grade_id NULL e NÃO aparecem no combo
-- quando o front envia ?gradeId= (até você atribuir a série via PATCH).
--
-- Uso:
--   psql -h HOST -p PORTA -U postgres -d afirmeplay_dev -f migrations/20260824_afirme_ler_word_list_grade_id.sql
--
-- Idempotente.

BEGIN;

ALTER TABLE public.reading_word_list
    ADD COLUMN IF NOT EXISTS grade_id UUID REFERENCES public.grade(id);

CREATE INDEX IF NOT EXISTS ix_reading_word_list_grade_id
    ON public.reading_word_list(grade_id);

COMMIT;

SELECT
    COUNT(*) AS total,
    COUNT(grade_id) AS com_serie,
    COUNT(*) FILTER (WHERE grade_id IS NULL) AS sem_serie
FROM public.reading_word_list;
