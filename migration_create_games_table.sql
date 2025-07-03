-- Migração para criar a tabela games
-- Data: 2024

CREATE TABLE IF NOT EXISTS games (
    id VARCHAR PRIMARY KEY,
    url VARCHAR(500) NOT NULL,
    title VARCHAR(200) NOT NULL,
    "iframeHtml" TEXT NOT NULL,
    thumbnail VARCHAR(500),
    author VARCHAR(200),
    provider VARCHAR(50) NOT NULL DEFAULT 'wordwall',
    subject VARCHAR(100) NOT NULL,
    "userId" VARCHAR NOT NULL,
    "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY ("userId") REFERENCES users(id) ON DELETE CASCADE
);

-- Criar índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_games_user_id ON games("userId");
CREATE INDEX IF NOT EXISTS idx_games_subject ON games(subject);
CREATE INDEX IF NOT EXISTS idx_games_provider ON games(provider);
CREATE INDEX IF NOT EXISTS idx_games_created_at ON games("createdAt"); 