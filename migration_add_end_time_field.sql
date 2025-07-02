-- Migração para adicionar campo end_time à tabela test
-- Data: 2024
-- Descrição: Adiciona campo para data/hora de término da avaliação

-- Adicionar a coluna end_time do tipo TIMESTAMP
ALTER TABLE test ADD COLUMN end_time TIMESTAMP;

-- Adicionar comentário à coluna
COMMENT ON COLUMN test.end_time IS 'Data e hora de término da disponibilidade da avaliação';

-- Opcional: Adicionar índice para melhorar performance em consultas por data de término
CREATE INDEX idx_test_end_time ON test(end_time);

-- Opcional: Adicionar constraint para garantir que end_time seja posterior a time_limit quando ambos existem
-- ALTER TABLE test ADD CONSTRAINT chk_test_end_time_after_start 
-- CHECK (end_time IS NULL OR time_limit IS NULL OR end_time > time_limit);
