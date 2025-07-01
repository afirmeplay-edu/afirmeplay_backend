-- Migração para adicionar campo status à tabela test
-- Execute este script no banco de dados para adicionar o campo status

-- Adicionar coluna status à tabela test
ALTER TABLE test ADD COLUMN status VARCHAR(20) DEFAULT 'agendada';

-- Comentário explicativo
COMMENT ON COLUMN test.status IS 'Status da avaliação: agendada, em_andamento, concluida, cancelada';

-- Atualizar registros existentes para ter status 'agendada' por padrão
UPDATE test SET status = 'agendada' WHERE status IS NULL;

-- Tornar a coluna NOT NULL após atualizar os registros existentes
ALTER TABLE test ALTER COLUMN status SET NOT NULL; 