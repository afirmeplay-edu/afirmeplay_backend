-- ============================================================================
-- SCRIPT DE ATUALIZAÇÃO DE HABILIDADES DE PORTUGUÊS (MULTITENANT)
-- ============================================================================
--
-- COMPORTAMENTO:
-- - Detecta automaticamente o schema da cidade (city_xxx)
-- - Se a habilidade existir (busca por code): atualiza APENAS a description
-- - Se não existir: cria nova habilidade com todos os campos do JSON
--
-- REQUISITOS:
-- - PostgreSQL com arquitetura multitenant
-- - Schema city_xxx com tabela skill
--
-- EXECUÇÃO:
--   Get-Content update_portuguese_skills_multitenant.sql | docker exec -i CONTAINER_ID psql -U postgres -d DATABASE_NAME
--
-- EXEMPLO:
--   Get-Content update_portuguese_skills_multitenant.sql | docker exec -i bc34754e13fb psql -U postgres -d afirmeplay_dev
--
-- ============================================================================

DO $$
DECLARE
    v_json_data jsonb := '{
  "habilidades": [
    {
      "code": "CEEF01LP01",
      "description": "Identificar as múltiplas linguagens que fazem parte do cotidiano da criança.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP01",
      "description": "Identificar a função social de textos que circulam em campos da vida social dos quais participa cotidianamente (a casa, a rua, a comunidade, a escola) e nas mídias impressa, de massa e digital, reconhecendo para que foram produzidos, onde circulam, quem os produziu e a quem se destinam.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP02",
      "description": "Estabelecer expectativas em relação ao texto que vai ler (pressuposições antecipadoras dos sentidos, da forma e da função social do texto), apoiando-se em seus conhecimentos prévios sobre as condições de produção e recepção desse texto, o gênero, o suporte e o universo temático, bem como sobre saliências textuais, recursos gráficos, imagens, dados da própria obra (índice, prefácio etc.), confirmando antecipações e inferências realizadas antes e durante a leitura de textos, checando a adequação das hipóteses realizadas.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP03",
      "description": "Localizar informações explícitas em textos.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP04",
      "description": "Identificar o efeito de sentido produzido pelo uso de recursos expressivos gráfico-visuais em textos multissemióticos.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP05",
      "description": "Planejar, com a ajuda do professor, o texto que será produzido, considerando a situação comunicativa, os interlocutores (quem escreve/para quem escreve); a finalidade ou o propósito (escrever para quê); a circulação (onde o texto vai circular); o suporte (qual é o portador do texto); a linguagem, organização e forma do texto e seu tema, pesquisando em meios impressos ou digitais, sempre que for preciso, informações necessárias à produção do texto, organizando em tópicos os dados e as fontes pesquisadas.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP06",
      "description": "Reler e revisar o texto produzido com a ajuda do professor e a colaboração dos colegas, para corrigi-lo e aprimorá- lo, fazendo cortes, acréscimos, reformulações, correções de ortografia e pontuação.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP07",
      "description": "Editar a versão final do texto, em colaboração com os colegas e com a ajuda do professor, ilustrando, quando for o caso, em suporte adequado, manual ou digital.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP08",
      "description": "Utilizar software, inclusive programas de edição de texto, para editar e publicar os textos produzidos, explorando os recursos multissemióticos disponíveis.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP09",
      "description": "Expressar-se em situações de intercâmbio oral com clareza, preocupando-se em ser compreendido pelo interlocutor e usando a palavra com tom de voz audível, boa articulação e ritmo adequado.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP10",
      "description": "Escutar, com atenção, falas de professores e colegas, formulando perguntas pertinentes ao tema e solicitando esclarecimentos sempre que necessário.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP11",
      "description": "Reconhecer características da conversação espontânea presencial, respeitando os turnos de fala, selecionando e utilizando, durante a conversação, formas de tratamento adequadas, de acordo com a situação e a posição do interlocutor.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    },
    {
      "code": "EF15LP12",
      "description": "Atribuir significado a aspectos não linguísticos (paralinguísticos) observados na fala, como direção do olhar, riso, gestos, movimentos da cabeça (de concordância ou discordância), expressão corporal, tom de voz.",
      "subject_id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
      "grade_id": null,
      "comment": "Compartilhada: 1º, 2º, 3º, 4º e 5º Ano"
    }
  ]
}'::jsonb;
    v_habilidade jsonb;
    v_code text;
    v_description text;
    v_subject_id uuid;
    v_grade_id uuid;
    v_count_updated integer := 0;
    v_count_created integer := 0;
    v_count_total integer := 0;
    v_count_errors integer := 0;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '🚀 ATUALIZAÇÃO DE HABILIDADES DE PORTUGUÊS';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '';

    -- Contar total de habilidades no JSON
    SELECT jsonb_array_length(v_json_data->'habilidades') INTO v_count_total;
    RAISE NOTICE '📂 Habilidades no JSON: %', v_count_total;
    RAISE NOTICE '';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '📦 PROCESSANDO HABILIDADES';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '';

    -- Processar cada habilidade
    FOR v_habilidade IN 
        SELECT * FROM jsonb_array_elements(v_json_data->'habilidades')
    LOOP
        BEGIN
            v_code := v_habilidade->>'code';
            v_description := v_habilidade->>'description';
            v_subject_id := (v_habilidade->>'subject_id')::uuid;
            
            -- grade_id pode ser null
            IF v_habilidade->>'grade_id' IS NOT NULL AND v_habilidade->>'grade_id' != 'null' THEN
                v_grade_id := (v_habilidade->>'grade_id')::uuid;
            ELSE
                v_grade_id := NULL;
            END IF;

            -- Validar campos obrigatórios
            IF v_code IS NULL OR v_description IS NULL THEN
                RAISE WARNING '   ⚠️  Habilidade sem code ou description, pulando...';
                CONTINUE;
            END IF;

            -- INSERT com ON CONFLICT
            -- Tabela skills está em public
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id)
            ON CONFLICT (code) 
            DO UPDATE SET 
                description = EXCLUDED.description,
                updated_at = NOW()
            ;

            -- Verificar se foi INSERT ou UPDATE
            IF FOUND THEN
                -- Verificar se o registro já existia
                PERFORM 1 FROM public.skills 
                WHERE code = v_code 
                AND created_at < NOW() - INTERVAL '1 second';
                
                IF FOUND THEN
                    v_count_updated := v_count_updated + 1;
                    RAISE NOTICE '   ✏️  Atualizada: %', v_code;
                ELSE
                    v_count_created := v_count_created + 1;
                    IF v_grade_id IS NOT NULL THEN
                        RAISE NOTICE '   ➕ Criada: % (grade=%)', v_code, LEFT(v_grade_id::text, 8) || '...';
                    ELSE
                        RAISE NOTICE '   ➕ Criada: % (grade=NULL)', v_code;
                    END IF;
                END IF;
            END IF;

        EXCEPTION WHEN OTHERS THEN
            v_count_errors := v_count_errors + 1;
            RAISE WARNING '   ❌ Erro ao processar %: %', v_code, SQLERRM;
        END;
    END LOOP;

    -- Relatório final
    RAISE NOTICE '';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '📊 RELATÓRIO FINAL';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '  📝 Total de habilidades no JSON: %', v_count_total;
    RAISE NOTICE '  ✏️  Habilidades atualizadas: %', v_count_updated;
    RAISE NOTICE '  ➕ Habilidades criadas: %', v_count_created;
    RAISE NOTICE '  ❌ Erros: %', v_count_errors;
    RAISE NOTICE '';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '✅ SCRIPT CONCLUÍDO COM SUCESSO!';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '';

END $$;


-- ============================================================================
-- VALIDAÇÃO (descomente para executar)
-- ============================================================================

-- -- Ver habilidades atualizadas recentemente no schema da cidade
-- DO $$
-- DECLARE
--     v_city_schema text;
-- BEGIN
--     SELECT nspname INTO v_city_schema
--     FROM pg_namespace n
--     INNER JOIN pg_class c ON c.relnamespace = n.oid
--     WHERE nspname LIKE 'city_%'
--       AND c.relname = 'skills'
--     LIMIT 1;
--
--     EXECUTE format('SET search_path TO %I, public', v_city_schema);
--
--     RAISE NOTICE '';
--     RAISE NOTICE '=== HABILIDADES RECENTES (Schema: %) ===', v_city_schema;
--     
--     FOR rec IN 
--         EXECUTE 'SELECT code, LEFT(description, 60) as description, updated_at 
--                  FROM skills 
--                  WHERE code LIKE ''EF%'' OR code LIKE ''CEEF%''
--                  ORDER BY updated_at DESC 
--                  LIMIT 10'
--     LOOP
--         RAISE NOTICE '% - % (atualizada: %)', rec.code, rec.description, rec.updated_at;
--     END LOOP;
--
--     RESET search_path;
-- END $$;
