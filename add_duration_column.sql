-- Script SQL para adicionar o campo duration na tabela test
-- Execute este script no seu banco de dados PostgreSQL

-- Adicionar o campo duration
ALTER TABLE test 
ADD COLUMN duration INTEGER;

-- Comentário explicativo
COMMENT ON COLUMN test.duration IS 'Duração da avaliação em minutos';

-- Verificar se a alteração foi aplicada
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'test' 
AND column_name = 'duration'; 