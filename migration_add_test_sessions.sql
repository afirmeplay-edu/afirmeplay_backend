-- Migração para adicionar tabela de sessões de prova
-- Execução: psql -U postgres -d nome_do_banco -f migration_add_test_sessions.sql

-- Criar tabela test_sessions
CREATE TABLE IF NOT EXISTS test_sessions (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR NOT NULL,
    test_id VARCHAR NOT NULL,
    
    -- Controle de tempo
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP NULL,
    time_limit_minutes INTEGER NULL,
    
    -- Status da sessão
    status VARCHAR(20) DEFAULT 'em_andamento',
    
    -- Resultados
    total_questions INTEGER NULL,
    correct_answers INTEGER NULL,
    score FLOAT NULL,
    grade FLOAT NULL,
    
    -- Metadados
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (student_id) REFERENCES student(id) ON DELETE CASCADE,
    FOREIGN KEY (test_id) REFERENCES test(id) ON DELETE CASCADE
);

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_test_sessions_student_id ON test_sessions(student_id);
CREATE INDEX IF NOT EXISTS idx_test_sessions_test_id ON test_sessions(test_id);
CREATE INDEX IF NOT EXISTS idx_test_sessions_status ON test_sessions(status);
CREATE INDEX IF NOT EXISTS idx_test_sessions_started_at ON test_sessions(started_at);

-- Criar índice único para prevenir múltiplas sessões ativas
CREATE UNIQUE INDEX IF NOT EXISTS idx_test_sessions_unique_active 
ON test_sessions(student_id, test_id) 
WHERE status = 'em_andamento';

-- Criar trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_test_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_test_sessions_updated_at 
    BEFORE UPDATE ON test_sessions 
    FOR EACH ROW 
    EXECUTE FUNCTION update_test_sessions_updated_at();

-- Comentários para documentação
COMMENT ON TABLE test_sessions IS 'Tabela para controlar sessões de prova dos alunos';
COMMENT ON COLUMN test_sessions.status IS 'Status da sessão: em_andamento, finalizada, expirada';
COMMENT ON COLUMN test_sessions.time_limit_minutes IS 'Tempo limite da prova em minutos';
COMMENT ON COLUMN test_sessions.score IS 'Pontuação percentual (0-100)';
COMMENT ON COLUMN test_sessions.grade IS 'Nota final (0-10)';

-- Inserir alguns dados de exemplo (opcional)
-- INSERT INTO test_sessions (id, student_id, test_id, time_limit_minutes, status) 
-- VALUES ('test-session-1', 'student-1', 'test-1', 60, 'finalizada');

COMMIT; 