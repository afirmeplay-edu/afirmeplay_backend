-- Script SQL para criar a tabela evaluation_results
-- Execute este script diretamente no seu banco PostgreSQL

-- Verificar se a tabela ja existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'evaluation_results'
    ) THEN
        -- Criar a tabela
        CREATE TABLE evaluation_results (
            id VARCHAR PRIMARY KEY,
            test_id VARCHAR NOT NULL REFERENCES test(id),
            student_id VARCHAR NOT NULL REFERENCES student(id),
                                session_id VARCHAR NOT NULL REFERENCES test_sessions(id),
            correct_answers INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            score_percentage FLOAT NOT NULL,
            grade FLOAT NOT NULL,
            proficiency FLOAT NOT NULL,
            classification VARCHAR(50) NOT NULL,
            calculated_at TIMESTAMP,
            UNIQUE(test_id, student_id)
        );
        
        -- Criar indices para melhor performance
        CREATE INDEX idx_evaluation_results_test_id ON evaluation_results(test_id);
        CREATE INDEX idx_evaluation_results_student_id ON evaluation_results(student_id);
        CREATE INDEX idx_evaluation_results_session_id ON evaluation_results(session_id);
        CREATE INDEX idx_evaluation_results_calculated_at ON evaluation_results(calculated_at);
        
        RAISE NOTICE 'Tabela evaluation_results criada com sucesso!';
    ELSE
        RAISE NOTICE 'Tabela evaluation_results ja existe!';
    END IF;
END $$; 