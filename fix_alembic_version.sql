-- Script para corrigir a tabela alembic_version
-- Execute este script no PostgreSQL

-- 1. Ver estado atual
SELECT * FROM alembic_version;

-- 2. Limpar tabela
DELETE FROM alembic_version;

-- 3. Inserir a head correta (f036b7fbab8e - merge das 3 heads)
INSERT INTO alembic_version (version_num) VALUES ('f036b7fbab8e');

-- 4. Verificar
SELECT * FROM alembic_version;
