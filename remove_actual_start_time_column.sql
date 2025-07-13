
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'test_sessions' 
        AND column_name = 'actual_start_time'
    ) THEN
        ALTER TABLE test_sessions DROP COLUMN actual_start_time;
        RAISE NOTICE 'Coluna actual_start_time removida com sucesso';
    ELSE
        RAISE NOTICE 'Coluna actual_start_time não existe, nada a fazer';
    END IF;
END $$;

-- Verificar se há dados que precisam ser migrados
-- Se houver sessões com actual_start_time mas sem started_at, migrar os dados
UPDATE test_sessions 
SET started_at = actual_start_time 
WHERE started_at IS NULL 
AND actual_start_time IS NOT NULL;

-- Comentar sobre a mudança
COMMENT ON TABLE test_sessions IS 'Tabela de sessões de teste - Frontend responsável pelo cronômetro'; 