-- ============================================================================
-- SCRIPT DE ATUALIZAÇÃO DE HABILIDADES DE PORTUGUÊS
-- ============================================================================
--
-- Gerado automaticamente em: 2026-02-18 09:32:47
-- Total de habilidades: 249
--
-- COMPORTAMENTO:
-- - Se a habilidade existir (busca por code): atualiza APENAS description
-- - Se não existir: cria nova habilidade
-- - Tabela: public.skills
--
-- EXECUÇÃO (PowerShell):
--   Get-Content update_portuguese_skills_multitenant_FULL.sql | docker exec -i CONTAINER_ID psql -U postgres -d DATABASE_NAME
--
-- EXEMPLO:
--   Get-Content update_portuguese_skills_multitenant_FULL.sql | docker exec -i bc34754e13fb psql -U postgres -d afirmeplay_dev
--
-- ============================================================================

DO $$
DECLARE
    v_code text;
    v_description text;
    v_subject_id uuid;
    v_grade_id uuid;
    v_count_updated integer := 0;
    v_count_created integer := 0;
    v_count_errors integer := 0;
    v_exists boolean;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '🚀 ATUALIZAÇÃO DE HABILIDADES DE PORTUGUÊS';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '';

    RAISE NOTICE '📂 Total de habilidades: 249';
    RAISE NOTICE '';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '📦 PROCESSANDO HABILIDADES';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '';

    -- [1/249] CEEF01LP01
    BEGIN
        v_code := 'CEEF01LP01';
        v_description := 'Identificar as múltiplas linguagens que fazem parte do cotidiano da criança.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [1/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [1/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [1/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [2/249] EF15LP01
    BEGIN
        v_code := 'EF15LP01';
        v_description := 'Identificar a função social de textos que circulam em campos da vida social dos quais participa cotidianamente (a casa, a rua, a comunidade, a escola) e nas mídias impressa, de massa e digital, reconhecendo para que foram produzidos, onde circulam, quem os produziu e a quem se destinam.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [2/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [2/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [2/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [3/249] EF15LP02
    BEGIN
        v_code := 'EF15LP02';
        v_description := 'Estabelecer expectativas em relação ao texto que vai ler (pressuposições antecipadoras dos sentidos, da forma e da função social do texto), apoiando-se em seus conhecimentos prévios sobre as condições de produção e recepção desse texto, o gênero, o suporte e o universo temático, bem como sobre saliências textuais, recursos gráficos, imagens, dados da própria obra (índice, prefácio etc.), confirmando antecipações e inferências realizadas antes e durante a leitura de textos, checando a adequação das hipóteses realizadas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [3/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [3/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [3/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [4/249] EF15LP03
    BEGIN
        v_code := 'EF15LP03';
        v_description := 'Localizar informações explícitas em textos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [4/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [4/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [4/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [5/249] EF15LP04
    BEGIN
        v_code := 'EF15LP04';
        v_description := 'Identificar o efeito de sentido produzido pelo uso de recursos expressivos gráfico-visuais em textos multissemióticos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [5/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [5/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [5/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [6/249] EF15LP05
    BEGIN
        v_code := 'EF15LP05';
        v_description := 'Planejar, com a ajuda do professor, o texto que será produzido, considerando a situação comunicativa, os interlocutores (quem escreve/para quem escreve); a finalidade ou o propósito (escrever para quê); a circulação (onde o texto vai circular); o suporte (qual é o portador do texto); a linguagem, organização e forma do texto e seu tema, pesquisando em meios impressos ou digitais, sempre que for preciso, informações necessárias à produção do texto, organizando em tópicos os dados e as fontes pesquisadas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [6/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [6/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [6/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [7/249] EF15LP06
    BEGIN
        v_code := 'EF15LP06';
        v_description := 'Reler e revisar o texto produzido com a ajuda do professor e a colaboração dos colegas, para corrigi-lo e aprimorá- lo, fazendo cortes, acréscimos, reformulações, correções de ortografia e pontuação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [7/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [7/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [7/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [8/249] EF15LP07
    BEGIN
        v_code := 'EF15LP07';
        v_description := 'Editar a versão final do texto, em colaboração com os colegas e com a ajuda do professor, ilustrando, quando for o caso, em suporte adequado, manual ou digital.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [8/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [8/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [8/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [9/249] EF15LP08
    BEGIN
        v_code := 'EF15LP08';
        v_description := 'Utilizar software, inclusive programas de edição de texto, para editar e publicar os textos produzidos, explorando os recursos multissemióticos disponíveis.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [9/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [9/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [9/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [10/249] EF15LP09
    BEGIN
        v_code := 'EF15LP09';
        v_description := 'Expressar-se em situações de intercâmbio oral com clareza, preocupando-se em ser compreendido pelo interlocutor e usando a palavra com tom de voz audível, boa articulação e ritmo adequado.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [10/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [10/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [10/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [11/249] EF15LP10
    BEGIN
        v_code := 'EF15LP10';
        v_description := 'Escutar, com atenção, falas de professores e colegas, formulando perguntas pertinentes ao tema e solicitando esclarecimentos sempre que necessário.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [11/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [11/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [11/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [12/249] EF15LP11
    BEGIN
        v_code := 'EF15LP11';
        v_description := 'Reconhecer características da conversação espontânea presencial, respeitando os turnos de fala, selecionando e utilizando, durante a conversação, formas de tratamento adequadas, de acordo com a situação e a posição do interlocutor.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [12/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [12/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [12/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [13/249] EF15LP12
    BEGIN
        v_code := 'EF15LP12';
        v_description := 'Atribuir significado a aspectos não linguísticos (paralinguísticos) observados na fala, como direção do olhar, riso, gestos, movimentos da cabeça (de concordância ou discordância), expressão corporal, tom de voz.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [13/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [13/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [13/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [14/249] EF15LP13
    BEGIN
        v_code := 'EF15LP13';
        v_description := 'Identificar finalidades da interação oral em diferentes contextos comunicativos (solicitar informações, apresentar opiniões, informar, relatar experiências etc.).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [14/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [14/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [14/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [15/249] EF15LP14
    BEGIN
        v_code := 'EF15LP14';
        v_description := 'Construir o sentido de histórias em quadrinhos e tirinhas, relacionando imagens e palavras e interpretando recursos gráficos (tipos de balões, de letras, onomatopeias).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [15/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [15/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [15/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [16/249] EF15LP15
    BEGIN
        v_code := 'EF15LP15';
        v_description := 'Reconhecer que os textos literários fazem parte do mundo do imaginário e apresentam uma dimensão lúdica, de encantamento, valorizando- os, em sua diversidade cultural, como patrimônio artístico da humanidade.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [16/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [16/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [16/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [17/249] EF15LP16
    BEGIN
        v_code := 'EF15LP16';
        v_description := 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor e, mais tarde, de maneira autônoma, textos narrativos de maior porte como contos (populares, de fadas, acumulativos, de assombração etc.) e crônicas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [17/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [17/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [17/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [18/249] EF15LP17
    BEGIN
        v_code := 'EF15LP17';
        v_description := 'Apreciar poemas visuais e concretos, observando efeitos de sentido criados pelo formato do texto na página, distribuição e diagramação das letras, pelas ilustrações e por outros efeitos visuais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [18/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [18/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [18/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [19/249] EF15LP18
    BEGIN
        v_code := 'EF15LP18';
        v_description := 'Relacionar texto com ilustrações e outros recursos gráficos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [19/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [19/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [19/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [20/249] EF15LP19
    BEGIN
        v_code := 'EF15LP19';
        v_description := 'Recontar oralmente, com e sem apoio de imagem, textos literários lidos pelo professor.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [20/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [20/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [20/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [21/249] EF12LP01
    BEGIN
        v_code := 'EF12LP01';
        v_description := 'Ler palavras novas com precisão na decodificação, no caso de palavras de uso frequente, ler globalmente, por memorização.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [21/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [21/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [21/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [22/249] EF12LP02
    BEGIN
        v_code := 'EF12LP02';
        v_description := 'Buscar, selecionar e ler, com a mediação do professor (leitura compartilhada), textos que circulam em meios impressos ou digitais, de acordo com as necessidades e interesses.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [22/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [22/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [22/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [23/249] EF12LP03
    BEGIN
        v_code := 'EF12LP03';
        v_description := 'Copiar textos breves, mantendo suas características e voltando para o texto sempre que tiver dúvidas sobre sua distribuição gráfica, espaçamento entre as palavras, escrita das palavras e pontuação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [23/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [23/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [23/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [24/249] EF12LP04
    BEGIN
        v_code := 'EF12LP04';
        v_description := 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor ou já com certa autonomia, listas, agendas, calendários, avisos, convites, receitas, instruções de montagem (digitais ou impressos), dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto do texto e relacionando sua forma de organização à sua finalidade.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [24/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [24/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [24/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [25/249] EF12LP05
    BEGIN
        v_code := 'EF12LP05';
        v_description := 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, (re)contagens de histórias, poemas e outros textos versificados (letras de canção, quadrinhas, cordel), poemas visuais, tiras e histórias em quadrinhos, dentre outros gêneros do campo artístico- literário, considerando a situação comunicativa e a finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [25/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [25/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [25/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [26/249] EF12LP06
    BEGIN
        v_code := 'EF12LP06';
        v_description := 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, recados, avisos, convites, receitas, instruções de montagem, dentre outros gêneros do campo da vida cotidiana, que possam ser repassados oralmente por meio de ferramentas digitais, em áudio ou vídeo, considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [26/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [26/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [26/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [27/249] EF12LP07
    BEGIN
        v_code := 'EF12LP07';
        v_description := 'Identificar e (re)produzir, em cantiga, quadras, quadrinhas, parlendas, trava-línguas e canções, rimas, aliterações, assonâncias, o ritmo de fala relacionado ao ritmo e à melodia das músicas e seus efeitos de sentido.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [27/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [27/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [27/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [28/249] EF12LP08
    BEGIN
        v_code := 'EF12LP08';
        v_description := 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, fotolegendas em notícias, manchetes e lides em notícias, álbum de fotos digital noticioso e notícias curtas para público infantil, dentre outros gêneros do campo jornalístico, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [28/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [28/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [28/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [29/249] EF12LP09
    BEGIN
        v_code := 'EF12LP09';
        v_description := 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, slogans, anúncios publicitários e textos de campanhas de conscientização destinados ao público infantil, dentre outros gêneros do campo publicitário, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [29/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [29/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [29/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [30/249] EF12LP10
    BEGIN
        v_code := 'EF12LP10';
        v_description := 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, cartazes, avisos, folhetos, regras e regulamentos que organizam a vida na comunidade escolar, dentre outros gêneros do campo da atuação cidadã, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [30/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [30/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [30/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [31/249] EF12LP11
    BEGIN
        v_code := 'EF12LP11';
        v_description := 'Escrever, em colaboração com os colegas e com a ajuda do professor, fotolegendas em notícias, manchetes e lides em notícias, álbum de fotos digital noticioso e notícias curtas para público infantil, digitais ou impressos, dentre outros gêneros do campo jornalístico, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [31/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [31/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [31/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [32/249] EF12LP12
    BEGIN
        v_code := 'EF12LP12';
        v_description := 'Escrever, em colaboração com os colegas e com a ajuda do professor, slogans, anúncios publicitários e textos de campanhas de conscientização destinados ao público infantil, dentre outros gêneros do campo publicitário, considerando a situação comunicativa e o tema/ assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [32/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [32/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [32/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [33/249] EF12LP13
    BEGIN
        v_code := 'EF12LP13';
        v_description := 'Planejar, em colaboração com os colegas e com a ajuda do professor, slogans e peça de campanha de conscientização destinada ao público infantil que possam ser repassados oralmente por meio de ferramentas digitais, em áudio ou vídeo, considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [33/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [33/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [33/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [34/249] EF12LP14
    BEGIN
        v_code := 'EF12LP14';
        v_description := 'Identificar e reproduzir, em fotolegendas de notícias, álbum de fotos digital noticioso, cartas de leitor (revista infantil), digitais ou impressos, a formatação e diagramação específica de cada um desses gêneros, inclusive em suas versões orais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [34/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [34/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [34/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [35/249] EF12LP15
    BEGIN
        v_code := 'EF12LP15';
        v_description := 'Identificar a forma de composição de slogans publicitários.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [35/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [35/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [35/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [36/249] EF12LP16
    BEGIN
        v_code := 'EF12LP16';
        v_description := 'Identificar e reproduzir, em anúncios publicitários e textos de campanhas de conscientização destinados ao público infantil (orais e escritos, digitais ou impressos), a formatação e diagramação específica de cada um desses gêneros, inclusive o uso de imagens.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [36/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [36/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [36/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [37/249] EF12LP17
    BEGIN
        v_code := 'EF12LP17';
        v_description := 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, enunciados de tarefas escolares, diagramas, curiosidades, pequenos relatos de experimentos, entrevistas, verbetes de enciclopédia infantil, entre outros gêneros do campo investigativo, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [37/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [37/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [37/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [38/249] EF12LP18
    BEGIN
        v_code := 'EF12LP18';
        v_description := 'Apreciar poemas e outros textos versificados, observando rimas, sonoridades, jogos de palavras, reconhecendo seu pertencimento ao mundo imaginário e sua dimensão de encantamento, jogo e fruição.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [38/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [38/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [38/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [39/249] EF12LP19
    BEGIN
        v_code := 'EF12LP19';
        v_description := 'Reconhecer, em textos versificados, rimas, sonoridades, jogos de palavras, palavras, expressões, comparações, relacionando-as com sensações e associações.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [39/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [39/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [39/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [40/249] EF35LP01
    BEGIN
        v_code := 'EF35LP01';
        v_description := 'Ler e compreender, silenciosamente e, em seguida, em voz alta, com autonomia e fluência, textos curtos com nível de textualidade adequado.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [40/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [40/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [40/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [41/249] EF35LP02
    BEGIN
        v_code := 'EF35LP02';
        v_description := 'Selecionar livros da biblioteca e/ou do cantinho de leitura da sala de aula e/ou disponíveis em meios digitais para leitura individual, justificando a escolha e compartilhando com os colegas sua opinião, após a leitura.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [41/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [41/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [41/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [42/249] EF35LP03
    BEGIN
        v_code := 'EF35LP03';
        v_description := 'Identificar a ideia central do texto, demonstrando compreensão global.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [42/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [42/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [42/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [43/249] EF35LP04
    BEGIN
        v_code := 'EF35LP04';
        v_description := 'Inferir informações implícitas nos textos lidos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [43/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [43/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [43/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [44/249] EF35LP05
    BEGIN
        v_code := 'EF35LP05';
        v_description := 'Inferir o sentido de palavras ou expressões desconhecidas em textos, com base no contexto da frase ou do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [44/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [44/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [44/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [45/249] EF35LP06
    BEGIN
        v_code := 'EF35LP06';
        v_description := 'Recuperar relações entre partes de um texto, identificando substituições lexicais (de substantivos por sinônimos) ou pronominais (uso de pronomes anafóricos – pessoais, possessivos, demonstrativos) que contribuem para a continuidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [45/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [45/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [45/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [46/249] EF35LP07
    BEGIN
        v_code := 'EF35LP07';
        v_description := 'Utilizar, ao produzir um texto, conhecimentos linguísticos e gramaticais, tais como ortografia, regras básicas de concordância nominal e verbal, pontuação (ponto final, ponto de exclamação, ponto de interrogação, vírgulas em enumerações) e pontuação do discurso direto, quando for o caso.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [46/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [46/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [46/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [47/249] EF35LP08
    BEGIN
        v_code := 'EF35LP08';
        v_description := 'Utilizar, ao produzir um texto, recursos de referenciação (por substituição lexical ou por pronomes pessoais, possessivos e demonstrativos), vocabulário apropriado ao gênero, recursos de coesão pronominal (pronomes anafóricos) e articuladores de relações de sentido (tempo, causa, oposição, conclusão, comparação), com nível suficiente de informatividade.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [47/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [47/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [47/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [48/249] EF35LP09
    BEGIN
        v_code := 'EF35LP09';
        v_description := 'Organizar o texto em unidades de sentido, dividindo-o em parágrafos segundo as normas gráficas e de acordo com as características do gênero textual.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [48/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [48/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [48/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [49/249] EF35LP10
    BEGIN
        v_code := 'EF35LP10';
        v_description := 'Identificar gêneros do discurso oral, utilizados em diferentes situações e contextos comunicativos, e suas características linguístico- expressivas e composicionais (conversação espontânea, conversação telefônica, entrevistas pessoais, entrevistas no rádio ou na TV, debate, noticiário de rádio e TV, narração de jogos esportivos no rádio e TV, aula, debate etc.).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [49/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [49/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [49/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [50/249] EF35LP11
    BEGIN
        v_code := 'EF35LP11';
        v_description := 'Ouvir gravações, canções, textos falados em diferentes variedades linguísticas, identificando características regionais, urbanas e rurais da fala e respeitando as diversas variedades linguísticas como características do uso da língua por diferentes grupos regionais ou diferentes culturas locais, rejeitando preconceitos linguísticos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [50/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [50/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [50/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [51/249] EF35LP12
    BEGIN
        v_code := 'EF35LP12';
        v_description := 'Recorrer ao dicionário para esclarecer dúvida sobre a escrita de palavras, especialmente no caso de palavras com relações irregulares fonema-grafema.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [51/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [51/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [51/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [52/249] EF35LP13
    BEGIN
        v_code := 'EF35LP13';
        v_description := 'Memorizar a grafia de palavras de uso frequente nas quais as relações fonema-grafema são irregulares e com h inicial que não representa fonema.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [52/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [52/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [52/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [53/249] EF35LP14
    BEGIN
        v_code := 'EF35LP14';
        v_description := 'Identificar em textos e usar na produção textual pronomes pessoais, possessivos e demonstrativos, como recurso coesivo anafórico.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [53/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [53/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [53/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [54/249] EF35LP15
    BEGIN
        v_code := 'EF35LP15';
        v_description := 'Opinar e defender ponto de vista sobre tema polêmico relacionado a situações vivenciadas na escola e/ou na comunidade, utilizando registro formal e estrutura adequada à argumentação, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [54/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [54/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [54/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [55/249] EF35LP16
    BEGIN
        v_code := 'EF35LP16';
        v_description := 'Identificar e reproduzir, em notícias, manchetes, lides e corpo de notícias simples para público infantil e cartas de reclamação (revista infantil), digitais ou impressos, a formatação e diagramação específica de cada um desses gêneros, inclusive em suas versões orais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [55/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [55/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [55/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [56/249] EF35LP17
    BEGIN
        v_code := 'EF35LP17';
        v_description := 'Buscar e selecionar, com o apoio do professor, informações de interesse sobre fenômenos sociais e naturais, em textos que circulam em meios impressos ou digitais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [56/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [56/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [56/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [57/249] EF35LP18
    BEGIN
        v_code := 'EF35LP18';
        v_description := 'Escutar, com atenção, apresentações de trabalhos realizadas por colegas, formulando perguntas pertinentes ao tema e solicitando esclarecimentos sempre que necessário.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [57/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [57/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [57/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [58/249] EF35LP19
    BEGIN
        v_code := 'EF35LP19';
        v_description := 'Recuperar as ideias principais em situações formais de escuta de exposições, apresentações e palestras.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [58/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [58/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [58/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [59/249] EF35LP20
    BEGIN
        v_code := 'EF35LP20';
        v_description := 'Expor trabalhos ou pesquisas escolares, em sala de aula, com apoio de recursos multissemióticos (imagens, diagrama, tabelas etc.), orientando-se por roteiro escrito, planejando o tempo de fala e adequando a linguagem à situação comunicativa.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [59/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [59/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [59/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [60/249] EF35LP21
    BEGIN
        v_code := 'EF35LP21';
        v_description := 'Ler e compreender, de forma autônoma, textos literários de diferentes gêneros e extensões, inclusive aqueles sem ilustrações, estabelecendo preferências por gêneros, temas, autores.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [60/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [60/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [60/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [61/249] EF35LP22
    BEGIN
        v_code := 'EF35LP22';
        v_description := 'Perceber diálogos em textos narrativos, observando o efeito de sentido de verbos de enunciação e, se for o caso, o uso de variedades linguísticas no discurso direto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [61/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [61/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [61/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [62/249] EF35LP23
    BEGIN
        v_code := 'EF35LP23';
        v_description := 'Apreciar poemas e outros textos versificados, observando rimas, aliterações e diferentes modos de divisão dos versos, estrofes e refrões e seu efeito de sentido.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [62/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [62/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [62/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [63/249] EF35LP24
    BEGIN
        v_code := 'EF35LP24';
        v_description := 'Identificar funções do texto dramático (escrito para ser encenado) e sua organização por meio de diálogos entre personagens e marcadores das falas das personagens e das cenas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [63/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [63/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [63/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [64/249] EF35LP25
    BEGIN
        v_code := 'EF35LP25';
        v_description := 'Criar narrativas ficcionais, com certa autonomia, utilizando detalhes descritivos, sequências de eventos e imagens apropriadas para sustentar o sentido do texto, e marcadores de tempo, espaço e de fala de personagens.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [64/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [64/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [64/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [65/249] EF35LP26
    BEGIN
        v_code := 'EF35LP26';
        v_description := 'Ler e compreender, com certa autonomia, narrativas ficcionais que apresentem cenários e personagens, observando os elementos da estrutura narrativa: enredo, tempo, espaço, personagens, narrador e a construção do discurso indireto e discurso direto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [65/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [65/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [65/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [66/249] EF35LP27
    BEGIN
        v_code := 'EF35LP27';
        v_description := 'Ler e compreender, com certa autonomia, textos em versos, explorando rimas, sons e jogos de palavras, imagens poéticas (sentidos figurados) e recursos visuais e sonoros.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [66/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [66/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [66/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [67/249] EF35LP28
    BEGIN
        v_code := 'EF35LP28';
        v_description := 'Declamar poemas, com entonação, postura e interpretação adequadas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [67/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [67/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [67/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [68/249] EF35LP29
    BEGIN
        v_code := 'EF35LP29';
        v_description := 'Identificar, em narrativas, cenário, personagem central, conflito gerador, resolução e o ponto de vista com base no qual histórias são narradas, diferenciando narrativas em primeira e terceira pessoas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [68/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [68/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [68/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [69/249] EF35LP30
    BEGIN
        v_code := 'EF35LP30';
        v_description := 'Diferenciar discurso indireto e discurso direto, determinando o efeito de sentido de verbos de enunciação e explicando o uso de variedades linguísticas no discurso direto, quando for o caso.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [69/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [69/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [69/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [70/249] EF35LP31
    BEGIN
        v_code := 'EF35LP31';
        v_description := 'Identificar, em textos versificados, efeitos de sentido decorrentes do uso de recursos rítmicos e sonoros e de metáforas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := NULL;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [70/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [70/249] Criada: % (grade=NULL)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [70/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [71/249] EF01LP01
    BEGIN
        v_code := 'EF01LP01';
        v_description := 'Reconhecer que textos são lidos e escritos da esquerda para a direita e de cima para baixo da página.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [71/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [71/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [71/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [72/249] EF01LP02
    BEGIN
        v_code := 'EF01LP02';
        v_description := 'Escrever, espontaneamente ou por ditado, palavras e frases de forma alfabética – usando letras/grafemas que representem fonemas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [72/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [72/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [72/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [73/249] EF01LP03
    BEGIN
        v_code := 'EF01LP03';
        v_description := 'Observar escritas convencionais, comparando-as às suas produções escritas, percebendo semelhanças e diferenças.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [73/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [73/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [73/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [74/249] EF01LP04
    BEGIN
        v_code := 'EF01LP04';
        v_description := 'Distinguir as letras do alfabeto de outros sinais gráficos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [74/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [74/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [74/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [75/249] EF01LP05
    BEGIN
        v_code := 'EF01LP05';
        v_description := 'Reconhecer o sistema de escrita alfabética como representação dos sons da fala.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [75/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [75/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [75/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [76/249] EF01LP06
    BEGIN
        v_code := 'EF01LP06';
        v_description := 'Segmentar oralmente palavras em sílabas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [76/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [76/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [76/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [77/249] EF01LP07
    BEGIN
        v_code := 'EF01LP07';
        v_description := 'Identificar fonemas e sua representação por letras.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [77/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [77/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [77/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [78/249] EF01LP08
    BEGIN
        v_code := 'EF01LP08';
        v_description := 'Relacionar elementos sonoros (sílabas, fonemas, partes de palavras) com sua representação escrita.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [78/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [78/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [78/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [79/249] EF01LP09
    BEGIN
        v_code := 'EF01LP09';
        v_description := 'Comparar palavras, identificando semelhanças e diferenças entre sons de sílabas iniciais, mediais e finais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [79/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [79/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [79/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [80/249] EF01LP10
    BEGIN
        v_code := 'EF01LP10';
        v_description := 'Nomear as letras do alfabeto e recitá-lo na ordem das letras.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [80/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [80/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [80/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [81/249] EF01LP11
    BEGIN
        v_code := 'EF01LP11';
        v_description := 'Conhecer, diferenciar e relacionar letras em formato imprensa e cursiva, maiúsculas e minúsculas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [81/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [81/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [81/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [82/249] EF01LP12
    BEGIN
        v_code := 'EF01LP12';
        v_description := 'Reconhecer a separação das palavras, na escrita, por espaços em branco.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [82/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [82/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [82/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [83/249] EF01LP13
    BEGIN
        v_code := 'EF01LP13';
        v_description := 'Comparar palavras, identificando semelhanças e diferenças entre sons de sílabas iniciais, mediais e finais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [83/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [83/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [83/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [84/249] EF01LP14
    BEGIN
        v_code := 'EF01LP14';
        v_description := 'Identificar outros sinais no texto além das letras, como pontos finais, de interrogação e exclamação, número e seus efeitos na entonação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [84/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [84/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [84/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [85/249] EF01LP15
    BEGIN
        v_code := 'EF01LP15';
        v_description := 'Agrupar palavras pelo critério de aproximação de significado (sinonímia) e separar palavras pelo critério de oposição de significado (antonímia).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [85/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [85/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [85/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [86/249] EF01LP16
    BEGIN
        v_code := 'EF01LP16';
        v_description := 'Ler e compreender, em colaboração com os colegas e com a ajuda do professor, quadras, quadrinhas, parlendas, trava-línguas, dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto do texto e relacionando sua forma de organização à sua finalidade.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [86/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [86/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [86/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [87/249] EF01LP17
    BEGIN
        v_code := 'EF01LP17';
        v_description := 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, listas, agendas, calendários, avisos, convites, receitas, instruções de montagem e legendas para álbuns, fotos ou ilustrações (digitais ou impressos), dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto/ finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [87/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [87/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [87/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [88/249] EF01LP18
    BEGIN
        v_code := 'EF01LP18';
        v_description := 'Registrar, em colaboração com os colegas e com a ajuda do professor, cantigas, quadras, quadrinhas, parlendas, trava-línguas, dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [88/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [88/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [88/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [89/249] EF01LP19
    BEGIN
        v_code := 'EF01LP19';
        v_description := 'Recitar parlendas, quadras, quadrinhas, trava-línguas, com entonação adequada e observando as rimas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [89/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [89/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [89/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [90/249] EF01LP20
    BEGIN
        v_code := 'EF01LP20';
        v_description := 'Identificar e reproduzir, em listas, agendas, calendários, regras, avisos, convites, receitas, instruções de montagem e legendas para álbuns, fotos ou ilustrações (digitais ou impressos), a formatação e diagramação específica de cada um desses gêneros.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [90/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [90/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [90/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [91/249] EF01LP21
    BEGIN
        v_code := 'EF01LP21';
        v_description := 'Escrever, em colaboração com os colegas e com a ajuda do professor, listas de regras e regulamentos que organizam a vida na comunidade escolar, dentre outros gêneros do campo da atuação cidadã, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [91/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [91/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [91/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [92/249] EF01LP22
    BEGIN
        v_code := 'EF01LP22';
        v_description := 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, diagramas, entrevistas, curiosidades, dentre outros gêneros do campo investigativo, digitais ou impressos, considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [92/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [92/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [92/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [93/249] EF01LP23
    BEGIN
        v_code := 'EF01LP23';
        v_description := 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, entrevistas, curiosidades, dentre outros gêneros do campo investigativo, que possam ser repassados oralmente por meio de ferramentas digitais, em áudio ou vídeo, considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [93/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [93/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [93/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [94/249] EF01LP24
    BEGIN
        v_code := 'EF01LP24';
        v_description := 'Identificar e reproduzir, em enunciados de tarefas escolares, diagramas, entrevistas, curiosidades, digitais ou impressos, a formatação e diagramação específica de cada um desses gêneros, inclusive em suas versões orais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [94/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [94/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [94/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [95/249] EF01LP25
    BEGIN
        v_code := 'EF01LP25';
        v_description := 'Produzir, tendo o professor como escriba, recontagens de histórias lidas pelo professor, histórias imaginadas ou baseadas em livros de imagens, observando a forma de composição de textos narrativos (personagens, enredo, tempo e espaço).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [95/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [95/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [95/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [96/249] EF01LP26
    BEGIN
        v_code := 'EF01LP26';
        v_description := 'Identificar elementos de uma narrativa lida ou escutada, incluindo personagens, enredo, tempo e espaço.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [96/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [96/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [96/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [97/249] D1
    BEGIN
        v_code := 'D1';
        v_description := 'Localizar informações explícitas em um texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [97/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [97/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [97/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [98/249] D3
    BEGIN
        v_code := 'D3';
        v_description := 'Inferir o sentido de uma palavra ou expressão.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [98/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [98/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [98/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [99/249] D4
    BEGIN
        v_code := 'D4';
        v_description := 'Inferir uma informação implícita em um texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [99/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [99/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [99/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [100/249] D6
    BEGIN
        v_code := 'D6';
        v_description := 'Identificar o tema de um texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [100/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [100/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [100/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [101/249] D11
    BEGIN
        v_code := 'D11';
        v_description := 'Distinguir um fato da opinião relativa a esse fato.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [101/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [101/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [101/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [102/249] D5
    BEGIN
        v_code := 'D5';
        v_description := 'Interpretar texto com auxílio de material gráfico diverso (propagandas, quadrinhos, foto, etc.).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [102/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [102/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [102/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [103/249] D9
    BEGIN
        v_code := 'D9';
        v_description := 'Identificar a finalidade de textos de diferentes gêneros.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [103/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [103/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [103/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [104/249] D15
    BEGIN
        v_code := 'D15';
        v_description := 'Reconhecer diferentes formas de tratar uma informação na comparação de textos que tratam do mesmo tema, em função das condições em que ele foi produzido e daquelas em que será recebido.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [104/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [104/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [104/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [105/249] D2
    BEGIN
        v_code := 'D2';
        v_description := 'Estabelecer relações entre partes de um texto, identificando repetições ou substituições que contribuem para a continuidade de um texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [105/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [105/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [105/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [106/249] D7
    BEGIN
        v_code := 'D7';
        v_description := 'Identificar o conflito gerador do enredo e os elementos que constroem a narrativa.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [106/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [106/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [106/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [107/249] D8
    BEGIN
        v_code := 'D8';
        v_description := 'Estabelecer relação causa /consequência entre partes e elementos do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [107/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [107/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [107/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [108/249] D12
    BEGIN
        v_code := 'D12';
        v_description := 'Estabelecer relações lógico-discursivas presentes no texto, marcadas por conjunções, advérbios, etc.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [108/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [108/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [108/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [109/249] D13
    BEGIN
        v_code := 'D13';
        v_description := 'Identificar efeitos de ironia ou humor em textos variados.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [109/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [109/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [109/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [110/249] D14
    BEGIN
        v_code := 'D14';
        v_description := 'Identificar o efeito de sentido decorrente do uso da pontuação e de outras notações.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [110/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [110/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [110/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [111/249] D10
    BEGIN
        v_code := 'D10';
        v_description := 'Identificar as marcas linguísticas que evidenciam o locutor e o interlocutor de um texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '391ed6e8-fc45-46f8-8e4c-065005d2329f'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [111/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [111/249] Criada: % (grade=391ed6e8...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [111/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [112/249] EF02LP01
    BEGIN
        v_code := 'EF02LP01';
        v_description := 'Utilizar, ao produzir o texto, grafia correta de palavras conhecidas ou com estruturas silábicas já dominadas, letras maiúsculas em início de frases e em substantivos próprios, segmentação entre as palavras, ponto final, ponto de interrogação e ponto de exclamação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [112/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [112/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [112/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [113/249] EF02LP02
    BEGIN
        v_code := 'EF02LP02';
        v_description := 'Segmentar palavras em sílabas e remover e substituir sílabas iniciais, mediais ou finais para criar novas palavras.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [113/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [113/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [113/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [114/249] EF02LP03
    BEGIN
        v_code := 'EF02LP03';
        v_description := 'Ler e escrever palavras com correspondências regulares diretas entre letras e fonemas (f, v, t, d, p, b) e correspondências regulares contextuais (c e q; e e o, em posição átona em final de palavra).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [114/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [114/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [114/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [115/249] EF02LP04
    BEGIN
        v_code := 'EF02LP04';
        v_description := 'Ler e escrever corretamente palavras com sílabas CV, V, CVC, CCV, identificando que existem vogais em todas as sílabas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [115/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [115/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [115/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [116/249] EF02LP05
    BEGIN
        v_code := 'EF02LP05';
        v_description := 'Ler e escrever corretamente palavras com marcas de nasalidade (til, m, n).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [116/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [116/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [116/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [117/249] EF02LP06
    BEGIN
        v_code := 'EF02LP06';
        v_description := 'Perceber o princípio acrofônico que opera nos nomes das letras do alfabeto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [117/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [117/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [117/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [118/249] EF02LP07
    BEGIN
        v_code := 'EF02LP07';
        v_description := 'Escrever palavras, frases, textos curtos nas formas imprensa e cursiva.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [118/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [118/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [118/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [119/249] EF02LP08
    BEGIN
        v_code := 'EF02LP08';
        v_description := 'Segmentar corretamente as palavras ao escrever frases e textos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [119/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [119/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [119/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [120/249] EF02LP09
    BEGIN
        v_code := 'EF02LP09';
        v_description := 'Usar adequadamente ponto final, ponto de interrogação e ponto de exclamação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [120/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [120/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [120/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [121/249] EF02LP10
    BEGIN
        v_code := 'EF02LP10';
        v_description := 'Identificar sinônimos de palavras de texto lido, determinando a diferença de sentido entre eles, e formar antônimos de palavras encontradas em texto lido pelo acréscimo do prefixo de negação in-/im-.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [121/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [121/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [121/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [122/249] EF02LP11
    BEGIN
        v_code := 'EF02LP11';
        v_description := 'Formar o aumentativo e o diminutivo de palavras com os sufixos -ão e -inho/-zinho.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [122/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [122/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [122/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [123/249] EF02LP12
    BEGIN
        v_code := 'EF02LP12';
        v_description := 'Ler e compreender com certa autonomia cantigas, letras de canção, dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto do texto e relacionando sua forma de organização à sua finalidade.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [123/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [123/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [123/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [124/249] EF02LP13
    BEGIN
        v_code := 'EF02LP13';
        v_description := 'Planejar e produzir bilhetes e cartas, em meio impresso e/ou digital, dentre outros gêneros do campo da vida cotidiana, considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [124/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [124/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [124/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [125/249] EF02LP14
    BEGIN
        v_code := 'EF02LP14';
        v_description := 'Planejar e produzir pequenos relatos de observação de processos, de fatos, de experiências pessoais, mantendo as características do gênero, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [125/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [125/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [125/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [126/249] EF02LP15
    BEGIN
        v_code := 'EF02LP15';
        v_description := 'Cantar cantigas e canções, obedecendo ao ritmo e à melodia.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [126/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [126/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [126/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [127/249] EF02LP16
    BEGIN
        v_code := 'EF02LP16';
        v_description := 'Identificar e reproduzir, em bilhetes, recados, avisos, cartas, e- mails, receitas (modo de fazer), relatos (digitais ou impressos), a formatação e diagramação específica de cada um desses gêneros.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [127/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [127/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [127/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [128/249] EF02LP17
    BEGIN
        v_code := 'EF02LP17';
        v_description := 'Identificar e reproduzir, em relatos de experiências pessoais, a sequência dos fatos, utilizando expressões que marquem a passagem do tempo ("antes", "depois", "ontem", "hoje", "amanhã", "outro dia", "antigamente", "há muito tempo" etc.), e o nível de informatividade necessário.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [128/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [128/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [128/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [129/249] EF02LP18
    BEGIN
        v_code := 'EF02LP18';
        v_description := 'Planejar e produzir cartazes e folhetos para divulgar eventos da escola ou da comunidade, utilizando linguagem persuasiva e elementos textuais e visuais (tamanho da letra, leiaute, imagens) adequados ao gênero, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [129/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [129/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [129/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [130/249] EF02LP19
    BEGIN
        v_code := 'EF02LP19';
        v_description := 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, notícias curtas para público infantil, para compor jornal falado que possa ser repassado oralmente ou em meio digital, em áudio ou vídeo, dentre outros gêneros do campo jornalístico, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [130/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [130/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [130/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [131/249] EF02LP20
    BEGIN
        v_code := 'EF02LP20';
        v_description := 'Reconhecer a função de textos utilizados para apresentar informações coletadas em atividades de pesquisa (enquetes, pequenas entrevistas, registros de experimentações).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [131/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [131/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [131/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [132/249] EF02LP21
    BEGIN
        v_code := 'EF02LP21';
        v_description := 'Explorar, com a mediação do professor, textos informativos de diferentes ambientes digitais de pesquisa, conhecendo suas possibilidades.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [132/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [132/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [132/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [133/249] EF02LP22
    BEGIN
        v_code := 'EF02LP22';
        v_description := 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, pequenos relatos de experimentos, entrevistas, verbetes de enciclopédia infantil, dentre outros gêneros do campo investigativo, digitais ou impressos, considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [133/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [133/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [133/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [134/249] EF02LP23
    BEGIN
        v_code := 'EF02LP23';
        v_description := 'Planejar e produzir, com certa autonomia, pequenos registros de observação de resultados de pesquisa, coerentes com um tema investigado.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [134/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [134/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [134/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [135/249] EF02LP24
    BEGIN
        v_code := 'EF02LP24';
        v_description := 'Planejar e produzir, em colaboração com os colegas e com a ajuda do professor, relatos de experimentos, registros de observação, entrevistas, dentre outros gêneros do campo investigativo, que possam ser repassados oralmente por meio de ferramentas digitais, em áudio ou vídeo, considerando a situação comunicativa e o tema/assunto/ finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [135/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [135/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [135/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [136/249] EF02LP25
    BEGIN
        v_code := 'EF02LP25';
        v_description := 'Identificar e reproduzir, em relatos de experimentos, entrevistas, verbetes de enciclopédia infantil, digitais ou impressos, a formatação e diagramação específica de cada um desses gêneros, inclusive em suas versões orais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [136/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [136/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [136/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [137/249] EF02LP26
    BEGIN
        v_code := 'EF02LP26';
        v_description := 'Ler e compreender, com certa autonomia, textos literários, de gêneros variados, desenvolvendo o gosto pela leitura.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [137/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [137/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [137/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [138/249] EF02LP27
    BEGIN
        v_code := 'EF02LP27';
        v_description := 'Reescrever textos narrativos literários lidos pelo professor.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [138/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [138/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [138/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [139/249] EF02LP28
    BEGIN
        v_code := 'EF02LP28';
        v_description := 'Reconhecer o conflito gerador de uma narrativa ficcional e sua resolução, além de palavras, expressões e frases que caracterizam personagens e ambientes.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [139/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [139/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [139/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [140/249] EF02LP29
    BEGIN
        v_code := 'EF02LP29';
        v_description := 'Observar, em poemas visuais, o formato do texto na página, as ilustrações e outros efeitos visuais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := '74821122-e632-4301-b6f5-42b92b802a55'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [140/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [140/249] Criada: % (grade=74821122...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [140/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [141/249] EF03LP01
    BEGIN
        v_code := 'EF03LP01';
        v_description := 'Ler e escrever palavras com correspondências regulares contextuais entre grafemas e fonemas – c/qu; g/gu; r/rr; s/ss; o (e não u) e e (e não i) em sílaba átona em final de palavra – e com marcas de nasalidade (til, m, n).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [141/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [141/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [141/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [142/249] EF03LP02
    BEGIN
        v_code := 'EF03LP02';
        v_description := 'Ler e escrever corretamente palavras com sílabas CV, V, CVC, CCV, VC, VV, CVV, identificando que existem vogais em todas as sílabas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [142/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [142/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [142/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [143/249] EF03LP03
    BEGIN
        v_code := 'EF03LP03';
        v_description := 'Ler e escrever corretamente palavras com os dígrafos lh, nh, ch.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [143/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [143/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [143/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [144/249] EF03LP04
    BEGIN
        v_code := 'EF03LP04';
        v_description := 'Usar acento gráfico (agudo ou circunflexo) em monossílabos tônicos terminados em a, e, o e em palavras oxítonas terminadas em a, e, o, seguidas ou não de s.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [144/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [144/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [144/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [145/249] EF03LP05
    BEGIN
        v_code := 'EF03LP05';
        v_description := 'Identificar o número de sílabas de palavras, classificando-as em monossílabas, dissílabas, trissílabas e polissílabas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [145/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [145/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [145/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [146/249] EF03LP06
    BEGIN
        v_code := 'EF03LP06';
        v_description := 'Identificar a sílaba tônica em palavras, classificando-as em oxítonas, paroxítonas e proparoxítonas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [146/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [146/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [146/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [147/249] EF03LP07
    BEGIN
        v_code := 'EF03LP07';
        v_description := 'Identificar a função na leitura e usar na escrita ponto final, ponto de interrogação, ponto de exclamação e, em diálogos (discurso direto), dois- pontos e travessão.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [147/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [147/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [147/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [148/249] EF03LP08
    BEGIN
        v_code := 'EF03LP08';
        v_description := 'Identificar e diferenciar, em textos, substantivos e verbos e suas funções na oração: agente, ação, objeto da ação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [148/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [148/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [148/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [149/249] EF03LP09
    BEGIN
        v_code := 'EF03LP09';
        v_description := 'Identificar, em textos, adjetivos e sua função de atribuição de propriedades aos substantivos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [149/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [149/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [149/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [150/249] EF03LP10
    BEGIN
        v_code := 'EF03LP10';
        v_description := 'Reconhecer prefixos e sufixos produtivos na formação de palavras derivadas de substantivos, de adjetivos e de verbos, utilizando-os para compreender palavras e para formar novas palavras.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [150/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [150/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [150/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [151/249] EF03LP11
    BEGIN
        v_code := 'EF03LP11';
        v_description := 'Ler e compreender, com autonomia, textos injuntivos instrucionais (receitas, instruções de montagem etc.), com a estrutura própria desses textos (verbos imperativos, indicação de passos a ser seguidos) e mesclando palavras, imagens e recursos gráfico- visuais, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [151/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [151/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [151/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [152/249] EF03LP12
    BEGIN
        v_code := 'EF03LP12';
        v_description := 'Ler e compreender, com autonomia, cartas pessoais e diários, com expressão de sentimentos e opiniões, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero carta e considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [152/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [152/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [152/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [153/249] EF03LP13
    BEGIN
        v_code := 'EF03LP13';
        v_description := 'Planejar e produzir cartas pessoais e diários, com expressão de sentimentos e opiniões, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções dos gêneros carta e diário e considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [153/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [153/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [153/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [154/249] EF03LP14
    BEGIN
        v_code := 'EF03LP14';
        v_description := 'Planejar e produzir textos injuntivos instrucionais, com a estrutura própria desses textos (verbos imperativos, indicação de passos a ser seguidos) e mesclando palavras, imagens e recursos gráfico-visuais, considerando a situação comunicativa e o tema/ assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [154/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [154/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [154/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [155/249] EF03LP15
    BEGIN
        v_code := 'EF03LP15';
        v_description := 'Assistir, em vídeo digital, a programas de culinária infantil e, a partir deles, planejar e produzir receitas em áudio ou vídeo.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [155/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [155/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [155/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [156/249] EF03LP16
    BEGIN
        v_code := 'EF03LP16';
        v_description := 'Identificar e reproduzir, em textos injuntivos instrucionais (receitas, instruções de montagem, digitais ou impressos), a formatação própria desses textos (verbos imperativos, indicação de passos a ser seguidos) e a diagramação específica dos textos desses gêneros (lista de ingredientes ou materiais e instruções de execução – \"modo de fazer\").';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [156/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [156/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [156/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [157/249] EF03LP17
    BEGIN
        v_code := 'EF03LP17';
        v_description := 'Identificar e reproduzir, em gêneros epistolares e diários, a formatação própria desses textos (relatos de acontecimentos, expressão de vivências, emoções, opiniões ou críticas) e a diagramação específica dos textos desses gêneros (data, saudação, corpo do texto, despedida, assinatura).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [157/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [157/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [157/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [158/249] EF03LP18
    BEGIN
        v_code := 'EF03LP18';
        v_description := 'Ler e compreender, com autonomia, cartas dirigidas a veículos da mídia impressa ou digital (cartas de leitor e de reclamação a jornais, revistas) e notícias, dentre outros gêneros do campo jornalístico, de acordo com as convenções do gênero carta e considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [158/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [158/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [158/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [159/249] EF03LP19
    BEGIN
        v_code := 'EF03LP19';
        v_description := 'Identificar e discutir o propósito do uso de recursos de persuasão (cores, imagens, escolha de palavras, jogo de palavras, tamanho de letras) em textos publicitários e de propaganda, como elementos de convencimento.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [159/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [159/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [159/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [160/249] EF03LP20
    BEGIN
        v_code := 'EF03LP20';
        v_description := 'Produzir cartas dirigidas a veículos da mídia impressa ou digital (cartas do leitor ou de reclamação a jornais ou revistas), dentre outros gêneros do campo político- cidadão, com opiniões e críticas, de acordo com as convenções do gênero carta e considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [160/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [160/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [160/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [161/249] EF03LP21
    BEGIN
        v_code := 'EF03LP21';
        v_description := 'Produzir anúncios publicitários, textos de campanhas de conscientização destinados ao público infantil, observando os recursos de persuasão utilizados nos textos publicitários e de propaganda (cores, imagens, slogan, escolha de palavras, jogo de palavras, tamanho e tipo de letras, diagramação).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [161/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [161/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [161/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [162/249] EF03LP22
    BEGIN
        v_code := 'EF03LP22';
        v_description := 'Planejar e produzir, em colaboração com os colegas, telejornal para público infantil com algumas notícias e textos de campanhas que possam ser repassados oralmente ou em meio digital, em áudio ou vídeo, considerando a situação comunicativa, a organização específica da fala nesses gêneros e o tema/assunto/ finalidade dos textos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [162/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [162/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [162/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [163/249] EF03LP23
    BEGIN
        v_code := 'EF03LP23';
        v_description := 'Analisar o uso de adjetivos em cartas dirigidas a veículos da mídia impressa ou digital (cartas do leitor ou de reclamação a jornais ou revistas), digitais ou impressas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [163/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [163/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [163/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [164/249] EF03LP24
    BEGIN
        v_code := 'EF03LP24';
        v_description := 'Ler/ouvir e compreender, com autonomia, relatos de observações e de pesquisas em fontes de informações, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [164/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [164/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [164/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [165/249] EF03LP25
    BEGIN
        v_code := 'EF03LP25';
        v_description := 'Planejar e produzir textos para apresentar resultados de observações e de pesquisas em fontes de informações, incluindo, quando pertinente, imagens, diagramas e gráficos ou tabelas simples, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [165/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [165/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [165/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [166/249] EF03LP26
    BEGIN
        v_code := 'EF03LP26';
        v_description := 'Identificar e reproduzir, em relatórios de observação e pesquisa, a formatação e diagramação específica desses gêneros (passos ou listas de itens, tabelas, ilustrações, gráficos, resumo dos resultados), inclusive em suas versões orais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [166/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [166/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [166/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [167/249] EF03LP27
    BEGIN
        v_code := 'EF03LP27';
        v_description := 'Recitar cordel e cantar repentes e emboladas, observando as rimas e obedecendo ao ritmo e à melodia.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'ea1ed64b-c9f5-4156-93b2-497ecf9e0d84'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [167/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [167/249] Criada: % (grade=ea1ed64b...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [167/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [168/249] EF04LP01
    BEGIN
        v_code := 'EF04LP01';
        v_description := 'Grafar palavras utilizando regras de correspondência fonema--grafema regulares diretas e contextuais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [168/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [168/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [168/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [169/249] EF04LP02
    BEGIN
        v_code := 'EF04LP02';
        v_description := 'Leitura e escrita, corretamente, palavras com sílabas VV e CVV em casos nos quais a combinação VV (ditongo) é reduzida na língua oral (ai, ei, ou).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [169/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [169/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [169/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [170/249] EF04LP03
    BEGIN
        v_code := 'EF04LP03';
        v_description := 'Localizar palavras no dicionário para esclarecer significados, reconhecendo o significado mais plausível para o contexto que deu origem à consulta.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [170/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [170/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [170/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [171/249] EF04LP04
    BEGIN
        v_code := 'EF04LP04';
        v_description := 'Usar acento gráfico (agudo ou circunflexo) em paroxítonas terminadas em -i(s), -l, -r, - ão(s).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [171/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [171/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [171/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [172/249] EF04LP05
    BEGIN
        v_code := 'EF04LP05';
        v_description := 'Identificar a função na leitura e usar, adequadamente, na escrita ponto final, de interrogação, de exclamação, dois- pontos e travessão em diálogos (discurso direto), vírgula em enumerações e em separação de vocativo e de aposto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [172/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [172/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [172/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [173/249] EF04LP06
    BEGIN
        v_code := 'EF04LP06';
        v_description := 'Identificar em textos e usar na produção textual a concordância entre substantivo ou pronome pessoal e verbo (concordância verbal).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [173/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [173/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [173/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [174/249] EF04LP07
    BEGIN
        v_code := 'EF04LP07';
        v_description := 'Identificar em textos e usar na produção textual a concordância entre artigo, substantivo e adjetivo (concordância no grupo nominal).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [174/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [174/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [174/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [175/249] EF04LP08
    BEGIN
        v_code := 'EF04LP08';
        v_description := 'Reconhecer e grafar, corretamente, palavras derivadas com os sufixos -agem, -oso, -eza, - izar/-isar (regulares morfológicas).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [175/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [175/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [175/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [176/249] EF04LP09
    BEGIN
        v_code := 'EF04LP09';
        v_description := 'Ler e compreender, com autonomia, boletos, faturas e carnês, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero (campos, itens elencados, medidas de consumo, código de barras) e considerando a situação comunicativa e a finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [176/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [176/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [176/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [177/249] EF04LP10
    BEGIN
        v_code := 'EF04LP10';
        v_description := 'Ler e compreender, com autonomia, cartas pessoais de reclamação, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero carta e considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [177/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [177/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [177/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [178/249] EF04LP11
    BEGIN
        v_code := 'EF04LP11';
        v_description := 'Planejar e produzir, com autonomia, cartas pessoais de reclamação, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero carta e com a estrutura própria desses textos (problema, opinião, argumentos), considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [178/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [178/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [178/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [179/249] EF04LP12
    BEGIN
        v_code := 'EF04LP12';
        v_description := 'Assistir, em vídeo digital, a programa infantil com instruções de montagem, de jogos e brincadeiras e, a partir dele, planejar e produzir tutoriais em áudio ou vídeo.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [179/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [179/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [179/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [180/249] EF04LP13
    BEGIN
        v_code := 'EF04LP13';
        v_description := 'Identificar e reproduzir, em textos injuntivos instrucionais (instruções de jogos digitais ou impressos), a formatação própria desses textos (verbos imperativos, indicação de passos a ser seguidos) e formato específico dos textos orais ou escritos desses gêneros (lista/ apresentação de materiais e instruções/passos de jogo).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [180/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [180/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [180/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [181/249] EF04LP14
    BEGIN
        v_code := 'EF04LP14';
        v_description := 'Identificar, em notícias, fatos, participantes, local e momento/tempo da ocorrência do fato noticiado.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [181/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [181/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [181/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [182/249] EF04LP15
    BEGIN
        v_code := 'EF04LP15';
        v_description := 'Distinguir fatos de opiniões/sugestões em textos (informativos, jornalísticos, publicitários etc.).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [182/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [182/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [182/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [183/249] EF04LP16
    BEGIN
        v_code := 'EF04LP16';
        v_description := 'Produzir notícias sobre fatos ocorridos no universo escolar, digitais ou impressas, para o jornal da escola, noticiando os fatos e seus atores e comentando decorrências, de acordo com as convenções do gênero notícia e considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [183/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [183/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [183/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [184/249] EF04LP17
    BEGIN
        v_code := 'EF04LP17';
        v_description := 'Produzir jornais radiofônicos ou televisivos e entrevistas veiculadas em rádio, TV e na internet, orientando-se por roteiro ou texto e demonstrando conhecimento dos gêneros jornal falado/televisivo e entrevista.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [184/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [184/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [184/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [185/249] EF04LP18
    BEGIN
        v_code := 'EF04LP18';
        v_description := 'Analisar o padrão entonacional e a expressão facial e corporal de âncoras de jornais radiofônicos ou televisivos e de entrevistadores/entrevistados.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [185/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [185/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [185/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [186/249] EF04LP19
    BEGIN
        v_code := 'EF04LP19';
        v_description := 'Ler e compreender textos expositivos de divulgação científica para crianças, considerando a situação comunicativa e o tema/ assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [186/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [186/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [186/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [187/249] EF04LP20
    BEGIN
        v_code := 'EF04LP20';
        v_description := 'Reconhecer a função de gráficos, diagramas e tabelas em textos, como forma de apresentação de dados e informações.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [187/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [187/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [187/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [188/249] EF04LP21
    BEGIN
        v_code := 'EF04LP21';
        v_description := 'Planejar e produzir textos sobre temas de interesse, com base em resultados de observações e pesquisas em fontes de informações impressas ou eletrônicas, incluindo, quando pertinente, imagens e gráficos ou tabelas simples, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [188/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [188/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [188/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [189/249] EF04LP22
    BEGIN
        v_code := 'EF04LP22';
        v_description := 'Planejar e produzir, com certa autonomia, verbetes de enciclopédia infantil, digitais ou impressos, considerando a situação comunicativa e o tema/ assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [189/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [189/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [189/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [190/249] EF04LP23
    BEGIN
        v_code := 'EF04LP23';
        v_description := 'Identificar e reproduzir, em verbetes de enciclopédia infantil, digitais ou impressos, a formatação e diagramação específica desse gênero (título do verbete, definição, detalhamento, curiosidades), considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [190/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [190/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [190/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [191/249] EF04LP24
    BEGIN
        v_code := 'EF04LP24';
        v_description := 'Identificar e reproduzir, em seu formato, tabelas, diagramas e gráficos em relatórios de observação e pesquisa, como forma de apresentação de dados e informações.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [191/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [191/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [191/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [192/249] EF04LP25
    BEGIN
        v_code := 'EF04LP25';
        v_description := 'Planejar e produzir, com certa autonomia, verbetes de dicionário, digitais ou impressos, considerando a situação comunicativa e o tema/assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [192/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [192/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [192/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [193/249] EF04LP26
    BEGIN
        v_code := 'EF04LP26';
        v_description := 'Observar, em poemas concretos, o formato, a distribuição e a diagramação das letras do texto na página.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [193/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [193/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [193/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [194/249] EF04LP27
    BEGIN
        v_code := 'EF04LP27';
        v_description := 'Identificar, em textos dramáticos, marcadores das falas das personagens e de cena.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'b8cdea4d-22fe-4647-a9f3-c575eb82c514'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [194/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [194/249] Criada: % (grade=b8cdea4d...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [194/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [195/249] EF05LP01
    BEGIN
        v_code := 'EF05LP01';
        v_description := 'Grafar palavras utilizando regras de correspondência fonema-grafema regulares, contextuais e morfológicas e palavras de uso frequente com correspondências irregulares.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [195/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [195/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [195/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [196/249] EF05LP02
    BEGIN
        v_code := 'EF05LP02';
        v_description := 'Identificar o caráter polissêmico das palavras (uma mesma palavra com diferentes significados, de acordo com o contexto de uso), comparando o significado de determinados termos utilizados nas áreas científicas com esses mesmos termos utilizados na linguagem usual.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [196/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [196/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [196/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [197/249] EF05LP03
    BEGIN
        v_code := 'EF05LP03';
        v_description := 'Acentuar corretamente palavras oxítonas, paroxítonas e proparoxítonas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [197/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [197/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [197/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [198/249] EF05LP04
    BEGIN
        v_code := 'EF05LP04';
        v_description := 'Diferenciar, na leitura de textos, vírgula, ponto e vírgula, dois-pontos e reconhecer, na leitura de textos, o efeito de sentido que decorre do uso de reticências, aspas, parênteses.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [198/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [198/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [198/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [199/249] EF05LP05
    BEGIN
        v_code := 'EF05LP05';
        v_description := 'Identificar a expressão de presente, passado e futuro em tempos verbais do modo indicativo.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [199/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [199/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [199/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [200/249] EF05LP06
    BEGIN
        v_code := 'EF05LP06';
        v_description := 'Flexionar, adequadamente, na escrita e na oralidade, os verbos em concordância com pronomes pessoais/nomes sujeitos da oração.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [200/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [200/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [200/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [201/249] EF05LP07
    BEGIN
        v_code := 'EF05LP07';
        v_description := 'Identificar, em textos, o uso de conjunções e a relação que estabelecem entre partes do texto: adição, oposição, tempo, causa, condição, finalidade.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [201/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [201/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [201/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [202/249] EF05LP08
    BEGIN
        v_code := 'EF05LP08';
        v_description := 'Diferenciar palavras primitivas, derivadas e compostas, e derivadas por adição de prefixo e de sufixo.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [202/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [202/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [202/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [203/249] EF05LP09
    BEGIN
        v_code := 'EF05LP09';
        v_description := 'Ler e compreender, com autonomia, textos instrucionais de regras de jogo, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero e considerando a situação comunicativa e a finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [203/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [203/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [203/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [204/249] EF05LP10
    BEGIN
        v_code := 'EF05LP10';
        v_description := 'Ler e compreender, com autonomia, anedotas, piadas e cartuns, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero e considerando a situação comunicativa e a finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [204/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [204/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [204/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [205/249] EF05LP11
    BEGIN
        v_code := 'EF05LP11';
        v_description := 'Registrar, com autonomia, anedotas, piadas e cartuns, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero e considerando a situação comunicativa e a finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [205/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [205/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [205/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [206/249] EF05LP12
    BEGIN
        v_code := 'EF05LP12';
        v_description := 'Planejar e produzir, com autonomia, textos instrucionais de regras de jogo, dentre outros gêneros do campo da vida cotidiana, de acordo com as convenções do gênero e considerando a situação comunicativa e a finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [206/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [206/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [206/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [207/249] EF05LP13
    BEGIN
        v_code := 'EF05LP13';
        v_description := 'Assistir, em vídeo digital, a postagem de vlog infantil de críticas de brinquedos e livros de literatura infantil e, a partir dele, planejar e produzir resenhas digitais em áudio ou vídeo.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [207/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [207/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [207/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [208/249] EF05LP14
    BEGIN
        v_code := 'EF05LP14';
        v_description := 'Identificar e reproduzir, em textos de resenha crítica de brinquedos ou livros de literatura infantil, a formatação própria desses textos (apresentação e avaliação do produto).';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [208/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [208/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [208/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [209/249] EF05LP15
    BEGIN
        v_code := 'EF05LP15';
        v_description := 'Ler/assistir e compreender, com autonomia, notícias, reportagens, vídeos em vlogs argumentativos, dentre outros gêneros do campo político-cidadão, de acordo com as convenções dos gêneros e considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [209/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [209/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [209/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [210/249] EF05LP16
    BEGIN
        v_code := 'EF05LP16';
        v_description := 'Comparar informações sobre um mesmo fato veiculadas em diferentes mídias e concluir sobre qual é mais confiável e por quê.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [210/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [210/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [210/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [211/249] EF05LP17
    BEGIN
        v_code := 'EF05LP17';
        v_description := 'Produzir roteiro para edição de uma reportagem digital sobre temas de interesse da turma, a partir de buscas de informações, imagens, áudios e vídeos na internet, de acordo com as convenções do gênero e considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [211/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [211/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [211/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [212/249] EF05LP18
    BEGIN
        v_code := 'EF05LP18';
        v_description := 'Roteirizar, produzir e editar vídeo para vlogs argumentativos sobre produtos de mídia para público infantil (filmes, desenhos animados, HQs, games etc.), com base em conhecimentos sobre os mesmos, de acordo com as convenções do gênero e considerando a situação comunicativa e o tema/ assunto/finalidade do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [212/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [212/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [212/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [213/249] EF05LP19
    BEGIN
        v_code := 'EF05LP19';
        v_description := 'Argumentar oralmente sobre acontecimentos de interesse social, com base em conhecimentos sobre fatos divulgados em TV, rádio, mídia impressa e digital, respeitando pontos de vista diferentes.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [213/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [213/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [213/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [214/249] EF05LP20
    BEGIN
        v_code := 'EF05LP20';
        v_description := 'Analisar a validade e força de argumentos em argumentações sobre produtos de mídia para público infantil (filmes, desenhos animados, HQs, games etc.), com base em conhecimentos sobre os mesmos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [214/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [214/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [214/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [215/249] EF05LP21
    BEGIN
        v_code := 'EF05LP21';
        v_description := 'Analisar o padrão entonacional, a expressão facial e corporal e as escolhas de variedade e registro linguísticos de vloggers de vlogs opinativos ou argumentativos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [215/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [215/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [215/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [216/249] EF05LP22
    BEGIN
        v_code := 'EF05LP22';
        v_description := 'Ler e compreender verbetes de dicionário, identificando a estrutura, as informações gramaticais (significado de abreviaturas) e as informações semânticas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [216/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [216/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [216/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [217/249] EF05LP23
    BEGIN
        v_code := 'EF05LP23';
        v_description := 'Comparar informações apresentadas em gráficos ou tabelas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [217/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [217/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [217/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [218/249] EF05LP24
    BEGIN
        v_code := 'EF05LP24';
        v_description := 'Planejar e produzir texto sobre tema de interesse, organizando resultados de pesquisa em fontes de informação impressas ou digitais, incluindo imagens e gráficos ou tabelas, considerando a situação comunicativa e o tema/assunto do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [218/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [218/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [218/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [219/249] EF05LP25
    BEGIN
        v_code := 'EF05LP25';
        v_description := 'Representar cenas de textos dramáticos, reproduzindo as falas das personagens, de acordo com as rubricas de interpretação e movimento indicadas pelo autor.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [219/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [219/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [219/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [220/249] EF05LP26
    BEGIN
        v_code := 'EF05LP26';
        v_description := 'Utilizar, ao produzir o texto, conhecimentos linguísticos e gramaticais: regras sintáticas de concordância nominal e verbal, convenções de escrita de citações, pontuação (ponto final, dois-pontos, vírgulas em enumerações) e regras ortográficas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [220/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [220/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [220/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [221/249] EF05LP27
    BEGIN
        v_code := 'EF05LP27';
        v_description := 'Utilizar, ao produzir o texto, recursos de coesão pronominal (pronomes anafóricos) e articuladores de relações de sentido (tempo, causa, oposição, conclusão, comparação), com nível adequado de informatividade.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [221/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [221/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [221/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [222/249] EF05LP28
    BEGIN
        v_code := 'EF05LP28';
        v_description := 'Observar, em ciberpoemas e minicontos infantis em mídia digital, os recursos multissemióticos presentes nesses textos digitais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [222/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [222/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [222/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [223/249] 5L1.1
    BEGIN
        v_code := '5L1.1';
        v_description := 'Identificar a ideia central do texto.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [223/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [223/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [223/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [224/249] 5L1.2
    BEGIN
        v_code := '5L1.2';
        v_description := 'Localizar informação explícita.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [224/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [224/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [224/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [225/249] 5L1.3
    BEGIN
        v_code := '5L1.3';
        v_description := 'Reconhecer diferentes gêneros textuais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [225/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [225/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [225/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [226/249] 5L1.4
    BEGIN
        v_code := '5L1.4';
        v_description := 'Identificar elementos constitutivos de textos narrativos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [226/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [226/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [226/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [227/249] 5L1.5
    BEGIN
        v_code := '5L1.5';
        v_description := 'Reconhecer diferentes modos de organização composicional de textos em versos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [227/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [227/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [227/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [228/249] 5L1.6
    BEGIN
        v_code := '5L1.6';
        v_description := 'Identificar as marcas de organização de textos dramáticos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [228/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [228/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [228/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [229/249] 5L2.1
    BEGIN
        v_code := '5L2.1';
        v_description := 'Analisar elementos constitutivos de gêneros textuais diversos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [229/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [229/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [229/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [230/249] 5L2.2
    BEGIN
        v_code := '5L2.2';
        v_description := 'Analisar relações de causa e consequência.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [230/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [230/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [230/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [231/249] 5L2.3
    BEGIN
        v_code := '5L2.3';
        v_description := 'Analisar o uso de recursos de persuasão em textos verbais e/ ou multimodais.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [231/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [231/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [231/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [232/249] 5L2.4
    BEGIN
        v_code := '5L2.4';
        v_description := 'Distinguir fatos de opiniões em textos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [232/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [232/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [232/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [233/249] 5L2.5
    BEGIN
        v_code := '5L2.5';
        v_description := 'Analisar informações apresentadas em gráficos, infográficos ou tabelas.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [233/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [233/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [233/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [234/249] 5L2.6
    BEGIN
        v_code := '5L2.6';
        v_description := 'Inferir informações implícitas em textos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [234/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [234/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [234/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [235/249] 5L2.7
    BEGIN
        v_code := '5L2.7';
        v_description := 'Inferir o sentido de palavras ou expressões em textos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [235/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [235/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [235/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [236/249] 5L2.8
    BEGIN
        v_code := '5L2.8';
        v_description := 'Analisar os efeitos de sentido de recursos multissemióticos em textos que circulam em diferentes suportes.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [236/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [236/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [236/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [237/249] 5L2.9
    BEGIN
        v_code := '5L2.9';
        v_description := 'Analisar a construção de sentidos de textos em versos com base em seus elementos constitutivos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [237/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [237/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [237/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [238/249] 5L3.1
    BEGIN
        v_code := '5L3.1';
        v_description := 'Avaliar a fidedignidade de informações sobre um mesmo fato veiculadas em diferentes mídias.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [238/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [238/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [238/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [239/249] 5A1.1
    BEGIN
        v_code := '5A1.1';
        v_description := 'Reconhecer os usos da pontuação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [239/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [239/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [239/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [240/249] 5A1.2
    BEGIN
        v_code := '5A1.2';
        v_description := 'Reconhecer em textos o significado de palavras derivadas a partir de seus afixos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [240/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [240/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [240/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [241/249] 5A1.3
    BEGIN
        v_code := '5A1.3';
        v_description := 'Identificar as variedades linguísticas em textos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [241/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [241/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [241/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [242/249] 5A1.4
    BEGIN
        v_code := '5A1.4';
        v_description := 'Identificar os mecanismos de progressão textual.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [242/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [242/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [242/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [243/249] 5A1.5
    BEGIN
        v_code := '5A1.5';
        v_description := 'Identificar os mecanismos de referenciação lexical e pronominal.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [243/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [243/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [243/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [244/249] 5A2.1
    BEGIN
        v_code := '5A2.1';
        v_description := 'Analisar os efeitos de sentido decorrentes do uso da pontuação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [244/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [244/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [244/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [245/249] 5A2.2
    BEGIN
        v_code := '5A2.2';
        v_description := 'Analisar os efeitos de sentido de verbos de enunciação.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [245/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [245/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [245/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [246/249] 5A2.3
    BEGIN
        v_code := '5A2.3';
        v_description := 'Analisar os efeitos de sentido decorrentes do uso dos adjetivos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [246/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [246/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [246/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [247/249] 5A2.4
    BEGIN
        v_code := '5A2.4';
        v_description := 'Analisar os efeitos de sentido decorrentes do uso dos advérbios.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [247/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [247/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [247/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [248/249] 5A3.1
    BEGIN
        v_code := '5A3.1';
        v_description := 'Julgar a eficácia de argumentos em textos.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [248/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [248/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [248/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- [249/249] 5P4.1
    BEGIN
        v_code := '5P4.1';
        v_description := 'Pruduzir texto em língua portuguesa, de acordo com o gênero textual e o tema demandados.';
        v_subject_id := '4d29b4f1-7bd7-42c0-84d5-111dc7025b90'::uuid;
        v_grade_id := 'f5688bb2-9624-487f-ab1f-40b191c96b76'::uuid;

        -- Verificar se existe
        SELECT EXISTS(SELECT 1 FROM public.skills WHERE code = v_code) INTO v_exists;

        IF v_exists THEN
            -- ATUALIZAR description apenas
            UPDATE public.skills
            SET description = v_description
            WHERE code = v_code;

            v_count_updated := v_count_updated + 1;
            RAISE NOTICE '   ✏️  [249/249] Atualizada: %', v_code;
        ELSE
            -- INSERIR nova habilidade
            INSERT INTO public.skills (code, description, subject_id, grade_id)
            VALUES (v_code, v_description, v_subject_id, v_grade_id);

            v_count_created := v_count_created + 1;
            RAISE NOTICE '   ➕ [249/249] Criada: % (grade=f5688bb2...)', v_code;
        END IF;

    EXCEPTION WHEN OTHERS THEN
        v_count_errors := v_count_errors + 1;
        RAISE WARNING '   ❌ [249/249] Erro ao processar %: %', v_code, SQLERRM;
    END;

    -- Relatório final
    RAISE NOTICE '';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '📊 RELATÓRIO FINAL';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '';
    RAISE NOTICE '  📝 Total de habilidades: 249';
    RAISE NOTICE '  ✏️  Habilidades atualizadas: %', v_count_updated;
    RAISE NOTICE '  ➕ Habilidades criadas: %', v_count_created;
    RAISE NOTICE '  ❌ Erros: %', v_count_errors;
    RAISE NOTICE '';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '✅ SCRIPT CONCLUÍDO COM SUCESSO!';
    RAISE NOTICE '======================================================================';
    RAISE NOTICE '';

END $$;
