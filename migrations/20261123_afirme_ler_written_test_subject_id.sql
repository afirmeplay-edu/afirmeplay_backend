-- Afirme Ler — subject_id em reading_written_test (todos os schemas city_*)
--
-- Resolve Português em public.subject PELO NOME (não fixa UUID).
-- Backfill por avaliação:
--   1) todas as questões com o mesmo subject_id → usa esse id;
--   2) sem questões → Português pelo nome;
--   3) subjects distintos → NOTICE com a prova e fallback Português.
-- Depois: subject_id NOT NULL + índice.
--
-- Uso (psql / cliente SQL):
--   \i migrations/20261123_afirme_ler_written_test_subject_id.sql
--
-- Preferível: python migrations_multitenant/add_written_test_subject_id.py --execute

DO $$
DECLARE
  portugues_id VARCHAR;
  portugues_name TEXT;
  schema_name TEXT;
  null_count INTEGER;
  rec RECORD;
  distinct_count INTEGER;
  chosen_id VARCHAR;
BEGIN
  SELECT s.id, s.name
    INTO portugues_id, portugues_name
  FROM public.subject s
  WHERE lower(translate(s.name,
        'ÁÀÂÃÄáàâãäÉÈÊËéèêëÍÌÎÏíìîïÓÒÔÕÖóòôõöÚÙÛÜúùûüÇç',
        'AAAAAaaaaaEEEEeeeeIIIIiiiiOOOOOoooooUUUUuuuuCc'))
        LIKE '%portugu%'
     OR lower(trim(s.name)) IN ('lp', 'lingua portuguesa', 'língua portuguesa')
  ORDER BY length(s.name), s.name, s.id
  LIMIT 1;

  IF portugues_id IS NULL THEN
    RAISE EXCEPTION
      'Não foi possível encontrar a disciplina Português em public.subject pelo nome. Cadastre-a antes de rodar esta migration.';
  END IF;

  RAISE NOTICE 'Português resolvido: % (%)', portugues_name, portugues_id;

  FOR schema_name IN
    SELECT nspname
    FROM pg_namespace
    WHERE nspname LIKE 'city_%'
      AND EXISTS (
        SELECT 1
        FROM information_schema.tables t
        WHERE t.table_schema = nspname
          AND t.table_name = 'reading_written_test'
      )
    ORDER BY nspname
  LOOP
    EXECUTE format(
      'ALTER TABLE %I.reading_written_test ADD COLUMN IF NOT EXISTS subject_id VARCHAR',
      schema_name
    );

    FOR rec IN EXECUTE format(
      'SELECT wt.id AS test_id, wt.title AS title,
              array_agg(DISTINCT q.subject_id ORDER BY q.subject_id)
                FILTER (WHERE q.subject_id IS NOT NULL) AS subject_ids
         FROM %I.reading_written_test wt
         LEFT JOIN %I.reading_written_test_question wtq
           ON wtq.written_test_id = wt.id
         LEFT JOIN public.question q ON q.id = wtq.question_id
         GROUP BY wt.id, wt.title
         ORDER BY wt.created_at, wt.id',
      schema_name, schema_name
    ) LOOP
      distinct_count := COALESCE(array_length(rec.subject_ids, 1), 0);
      IF distinct_count = 1 THEN
        chosen_id := rec.subject_ids[1];
      ELSIF distinct_count = 0 THEN
        chosen_id := portugues_id;
      ELSE
        RAISE NOTICE
          'MIXED %.% title=% subjects=% → fallback Português (%)',
          schema_name, rec.test_id, rec.title, rec.subject_ids, portugues_id;
        chosen_id := portugues_id;
      END IF;

      EXECUTE format(
        'UPDATE %I.reading_written_test SET subject_id = $1 WHERE id = $2',
        schema_name
      ) USING chosen_id, rec.test_id;
    END LOOP;

    EXECUTE format(
      'UPDATE %I.reading_written_test SET subject_id = $1 WHERE subject_id IS NULL',
      schema_name
    ) USING portugues_id;

    EXECUTE format(
      'SELECT COUNT(*) FROM %I.reading_written_test WHERE subject_id IS NULL',
      schema_name
    ) INTO null_count;
    IF null_count > 0 THEN
      RAISE EXCEPTION '%: ainda há % avaliações sem subject_id após o backfill.', schema_name, null_count;
    END IF;

    EXECUTE format(
      'ALTER TABLE %I.reading_written_test ALTER COLUMN subject_id SET NOT NULL',
      schema_name
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS ix_reading_written_test_subject ON %I.reading_written_test(subject_id)',
      schema_name
    );
    RAISE NOTICE 'OK %', schema_name;
  END LOOP;
END $$;
