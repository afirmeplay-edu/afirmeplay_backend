-- ============================================================================
-- Script para adicionar constraint UNIQUE(school_id, name) em todos os schemas city_*
-- Renomeia duplicatas automaticamente antes de adicionar a constraint
-- Versão 2.0 - Com tratamento de erros
-- ============================================================================

DO $$
DECLARE
    schema_rec RECORD;
    table_exists BOOLEAN;
    constraint_exists BOOLEAN;
    renamed_count INTEGER := 0;
    total_schemas INTEGER := 0;
    total_processed INTEGER := 0;
    total_renamed INTEGER := 0;
    total_skipped INTEGER := 0;
    total_errors INTEGER := 0;
    skipped_schemas TEXT := '';
    error_schemas TEXT := '';
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Iniciando processamento de schemas city_*';
    RAISE NOTICE '========================================';
    
    -- Loop em todos os schemas city_*
    FOR schema_rec IN 
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name LIKE 'city_%'
        ORDER BY schema_name
    LOOP
        total_schemas := total_schemas + 1;
        RAISE NOTICE '';
        RAISE NOTICE '📍 Processando schema: %', schema_rec.schema_name;
        RAISE NOTICE '----------------------------------------';
        
        BEGIN
            -- Verificar se a tabela class existe no schema
            EXECUTE format('
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables 
                    WHERE table_schema = %L
                      AND table_name = ''class''
                )', schema_rec.schema_name)
            INTO table_exists;
            
            IF NOT table_exists THEN
                RAISE NOTICE '⚠️  Tabela class não existe - PULANDO';
                total_skipped := total_skipped + 1;
                skipped_schemas := skipped_schemas || schema_rec.schema_name || ', ';
                CONTINUE;
            END IF;
            
            -- 1. Renomear duplicatas neste schema
            renamed_count := 0;
            
            EXECUTE format('
                WITH duplicates AS (
                    SELECT id, school_id, name,
                           ROW_NUMBER() OVER (PARTITION BY school_id, name ORDER BY id) as rn
                    FROM %I.class
                )
                UPDATE %I.class
                SET name = %I.class.name || '' ('' || duplicates.rn || '')''
                FROM duplicates
                WHERE %I.class.id = duplicates.id 
                  AND duplicates.rn > 1',
                schema_rec.schema_name,
                schema_rec.schema_name,
                schema_rec.schema_name,
                schema_rec.schema_name
            );
            
            GET DIAGNOSTICS renamed_count = ROW_COUNT;
            
            IF renamed_count > 0 THEN
                RAISE NOTICE '✅ Renomeadas % turmas duplicadas', renamed_count;
                total_renamed := total_renamed + renamed_count;
            ELSE
                RAISE NOTICE '✅ Nenhuma duplicata encontrada';
            END IF;
            
            -- 2. Verificar se constraint já existe
            EXECUTE format('
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.table_constraints 
                    WHERE table_schema = %L
                      AND table_name = ''class''
                      AND constraint_name = ''unique_class_name_per_school''
                )', schema_rec.schema_name)
            INTO constraint_exists;
            
            -- 3. Adicionar constraint se não existir
            IF constraint_exists THEN
                RAISE NOTICE '✅ Constraint já existe';
            ELSE
                EXECUTE format('
                    ALTER TABLE %I.class 
                    ADD CONSTRAINT unique_class_name_per_school 
                    UNIQUE (school_id, name)',
                    schema_rec.schema_name
                );
                RAISE NOTICE '✅ Constraint adicionada com sucesso';
            END IF;
            
            total_processed := total_processed + 1;
            
        EXCEPTION
            WHEN OTHERS THEN
                -- Capturar erro, logar e continuar
                RAISE WARNING '❌ ERRO ao processar schema %: % (%)', schema_rec.schema_name, SQLERRM, SQLSTATE;
                total_errors := total_errors + 1;
                error_schemas := error_schemas || schema_rec.schema_name || ' (' || SQLERRM || '), ';
        END;
        
    END LOOP;
    
    -- Resumo final
    RAISE NOTICE '';
    RAISE NOTICE '========================================';
    RAISE NOTICE '✨ RESUMO FINAL';
    RAISE NOTICE '========================================';
    RAISE NOTICE '📊 Total de schemas encontrados: %', total_schemas;
    RAISE NOTICE '✅ Schemas processados com sucesso: %', total_processed;
    RAISE NOTICE '⚠️  Schemas pulados (sem tabela class): %', total_skipped;
    RAISE NOTICE '❌ Schemas com erro: %', total_errors;
    RAISE NOTICE '🔧 Total de turmas renomeadas: %', total_renamed;
    
    IF total_skipped > 0 THEN
        RAISE NOTICE '';
        RAISE NOTICE '📋 Schemas pulados:';
        RAISE NOTICE '   %', TRIM(TRAILING ', ' FROM skipped_schemas);
    END IF;
    
    IF total_errors > 0 THEN
        RAISE NOTICE '';
        RAISE NOTICE '⚠️  Schemas com erro:';
        RAISE NOTICE '   %', TRIM(TRAILING ', ' FROM error_schemas);
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE '✨ Processo concluído!';
    
END $$;
