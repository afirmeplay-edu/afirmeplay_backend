-- Script SQL para adicionar o campo actual_start_time na tabela test_sessions
-- Execute este script no seu banco de dados PostgreSQL

-- Adicionar o campo actual_start_time
ALTER TABLE test_sessions 
ADD COLUMN actual_start_time TIMESTAMP;

-- Tornar o campo started_at nullable (caso ainda não seja)
ALTER TABLE test_sessions 
ALTER COLUMN started_at DROP NOT NULL;

-- Comentário explicativo
COMMENT ON COLUMN test_sessions.actual_start_time IS 'Momento real que o aluno iniciou a sessão de teste';

-- Verificar se a alteração foi aplicada
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'test_sessions' 
AND column_name = 'actual_start_time'; 