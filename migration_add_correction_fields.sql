-- Migração para adicionar campos de correção
-- Arquivo: migration_add_correction_fields.sql
-- Data: 2024

-- Adicionar campos de correção na tabela student_answers
ALTER TABLE student_answers 
ADD COLUMN IF NOT EXISTS manual_score FLOAT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS feedback TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS corrected_by VARCHAR DEFAULT NULL,
ADD COLUMN IF NOT EXISTS corrected_at TIMESTAMP DEFAULT NULL;

-- Adicionar foreign key para corrected_by se a tabela users existir
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
        -- Verificar se a constraint já existe
        IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                      WHERE constraint_name = 'fk_student_answers_corrected_by') THEN
            ALTER TABLE student_answers 
            ADD CONSTRAINT fk_student_answers_corrected_by 
            FOREIGN KEY (corrected_by) REFERENCES users(id);
        END IF;
    END IF;
END $$;

-- Adicionar campos de correção na tabela test_sessions
ALTER TABLE test_sessions 
ADD COLUMN IF NOT EXISTS feedback TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS corrected_by VARCHAR DEFAULT NULL,
ADD COLUMN IF NOT EXISTS corrected_at TIMESTAMP DEFAULT NULL;

-- Adicionar foreign key para corrected_by se a tabela users existir
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'users') THEN
        -- Verificar se a constraint já existe
        IF NOT EXISTS (SELECT 1 FROM information_schema.table_constraints 
                      WHERE constraint_name = 'fk_test_sessions_corrected_by') THEN
            ALTER TABLE test_sessions 
            ADD CONSTRAINT fk_test_sessions_corrected_by 
            FOREIGN KEY (corrected_by) REFERENCES users(id);
        END IF;
    END IF;
END $$;

-- Atualizar possíveis status da coluna status em test_sessions
DO $$
BEGIN
    -- Verificar se existe um tipo ENUM para status
    IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'session_status_enum') THEN
        -- Se existir um ENUM, pode ser necessário adicionar novos valores
        -- ALTER TYPE session_status_enum ADD VALUE IF NOT EXISTS 'corrigida';
        -- ALTER TYPE session_status_enum ADD VALUE IF NOT EXISTS 'revisada';
        NULL; -- Placeholder, ajustar conforme necessário
    END IF;
END $$;

-- Criar índices para melhorar performance das consultas de correção
CREATE INDEX IF NOT EXISTS idx_student_answers_corrected_by ON student_answers(corrected_by);
CREATE INDEX IF NOT EXISTS idx_student_answers_corrected_at ON student_answers(corrected_at);
CREATE INDEX IF NOT EXISTS idx_test_sessions_corrected_by ON test_sessions(corrected_by);
CREATE INDEX IF NOT EXISTS idx_test_sessions_corrected_at ON test_sessions(corrected_at);
CREATE INDEX IF NOT EXISTS idx_test_sessions_status ON test_sessions(status);

-- Comentários nas colunas para documentação
COMMENT ON COLUMN student_answers.manual_score IS 'Pontuação manual atribuída pelo professor para questões dissertativas';
COMMENT ON COLUMN student_answers.feedback IS 'Feedback específico do professor para a resposta do aluno';
COMMENT ON COLUMN student_answers.corrected_by IS 'ID do usuário (professor/admin) que corrigiu a resposta';
COMMENT ON COLUMN student_answers.corrected_at IS 'Data e hora da correção da resposta';

COMMENT ON COLUMN test_sessions.feedback IS 'Feedback geral do professor sobre a avaliação do aluno';
COMMENT ON COLUMN test_sessions.corrected_by IS 'ID do usuário (professor/admin) que finalizou a correção';
COMMENT ON COLUMN test_sessions.corrected_at IS 'Data e hora da finalização da correção';

-- Criar uma view para facilitar consultas de avaliações para correção
CREATE OR REPLACE VIEW evaluations_for_correction AS
SELECT 
    ts.id as session_id,
    ts.student_id,
    s.name as student_name,
    ts.test_id,
    t.title as test_title,
    sub.name as subject_name,
    g.name as grade_name,
    ts.submitted_at,
    ts.duration_minutes,
    ts.status,
    ts.total_questions,
    ts.correct_answers,
    ts.score,
    ts.feedback,
    ts.corrected_by,
    ts.corrected_at,
    COUNT(sa.id) as answered_questions,
    COUNT(CASE WHEN sa.manual_score IS NOT NULL THEN 1 END) as manually_scored_questions
FROM test_sessions ts
LEFT JOIN student s ON ts.student_id = s.id
LEFT JOIN test t ON ts.test_id = t.id
LEFT JOIN subject sub ON t.subject = sub.id
LEFT JOIN grade g ON t.grade_id = g.id
LEFT JOIN student_answers sa ON ts.student_id = sa.student_id AND ts.test_id = sa.test_id
WHERE ts.status IN ('finalizada', 'corrigida', 'revisada')
GROUP BY ts.id, s.name, t.title, sub.name, g.name
ORDER BY ts.submitted_at DESC;

COMMENT ON VIEW evaluations_for_correction IS 'View que consolida informações de avaliações que precisam de correção ou já foram corrigidas';

-- Mensagem de sucesso
DO $$
BEGIN
    RAISE NOTICE 'Migração de campos de correção aplicada com sucesso!';
    RAISE NOTICE 'Novos campos adicionados:';
    RAISE NOTICE '- student_answers: manual_score, feedback, corrected_by, corrected_at';
    RAISE NOTICE '- test_sessions: feedback, corrected_by, corrected_at';
    RAISE NOTICE 'View criada: evaluations_for_correction';
END $$; 