-- =====================================================
-- Migração para adicionar campos de reset de senha
-- InnovaPlay Backend
-- 
-- Execute este script no seu banco PostgreSQL para
-- adicionar os campos necessários para a funcionalidade
-- de redefinição de senha.
-- =====================================================

-- Adicionar colunas para reset de senha
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS reset_token VARCHAR(255) UNIQUE,
ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP;

-- Criar índice para melhor performance nas consultas por token
CREATE INDEX IF NOT EXISTS idx_users_reset_token ON users(reset_token);

-- Criar índice para limpeza de tokens expirados
CREATE INDEX IF NOT EXISTS idx_users_reset_token_expires ON users(reset_token_expires);

-- Comentário explicativo
COMMENT ON COLUMN users.reset_token IS 'Token único para redefinição de senha';
COMMENT ON COLUMN users.reset_token_expires IS 'Data e hora de expiração do token de reset'; 