-- ============================================================================
-- Script de Migração: DEV para PROD
-- Database: afirmeplay
-- Data: 2026-03-24
-- 
-- Este script sincroniza as tabelas e colunas do banco DEV para o PROD
-- ============================================================================

BEGIN;

-- ============================================================================
-- PARTE 1: CRIAÇÃO DE NOVAS TABELAS
-- ============================================================================

-- Tabela: answer_sheet_generation_jobs
CREATE TABLE IF NOT EXISTS answer_sheet_generation_jobs (
    job_id VARCHAR(36) NOT NULL PRIMARY KEY,
    city_id VARCHAR(36) NOT NULL,
    gabarito_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(36) NOT NULL,
    task_ids JSONB,
    total INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    successful INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'processing',
    progress_current INTEGER NOT NULL DEFAULT 0,
    progress_percentage INTEGER NOT NULL DEFAULT 0,
    scope_type VARCHAR(50),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    total_students_generated INTEGER,
    classes_generated INTEGER
);

CREATE INDEX IF NOT EXISTS ix_answer_sheet_generation_jobs_city_id ON answer_sheet_generation_jobs(city_id);
CREATE INDEX IF NOT EXISTS ix_answer_sheet_generation_jobs_gabarito_id ON answer_sheet_generation_jobs(gabarito_id);

-- Tabela: competitions
CREATE TABLE IF NOT EXISTS competitions (
    id VARCHAR NOT NULL PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    test_id VARCHAR,
    subject_id VARCHAR NOT NULL,
    level INTEGER NOT NULL,
    scope VARCHAR NOT NULL DEFAULT 'individual',
    scope_filter JSON,
    enrollment_start TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    enrollment_end TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    application TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    expiration TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    timezone VARCHAR NOT NULL DEFAULT 'America/Sao_Paulo',
    question_mode VARCHAR NOT NULL DEFAULT 'auto_random',
    question_rules JSON,
    reward_config JSON NOT NULL,
    ranking_criteria VARCHAR NOT NULL DEFAULT 'nota',
    ranking_tiebreaker VARCHAR NOT NULL DEFAULT 'tempo_entrega',
    ranking_visibility VARCHAR NOT NULL DEFAULT 'final',
    max_participants INTEGER,
    recurrence VARCHAR NOT NULL DEFAULT 'manual',
    template_id VARCHAR,
    status VARCHAR NOT NULL DEFAULT 'rascunho',
    created_by VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    edition_number INTEGER,
    edition_series VARCHAR
);

CREATE INDEX IF NOT EXISTS ix_competitions_created_by ON competitions(created_by);
CREATE INDEX IF NOT EXISTS ix_competitions_grade_id ON competitions(level);
CREATE INDEX IF NOT EXISTS ix_competitions_status ON competitions(status);
CREATE INDEX IF NOT EXISTS ix_competitions_subject ON competitions(subject_id);

-- Tabela: competition_enrollments
CREATE TABLE IF NOT EXISTS competition_enrollments (
    id VARCHAR NOT NULL PRIMARY KEY,
    competition_id VARCHAR NOT NULL,
    student_id VARCHAR NOT NULL,
    enrolled_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR NOT NULL DEFAULT 'inscrito',
    CONSTRAINT uq_competition_enrollments_competition_student UNIQUE (competition_id, student_id)
);

-- Tabela: competition_results
CREATE TABLE IF NOT EXISTS competition_results (
    id VARCHAR NOT NULL PRIMARY KEY,
    competition_id VARCHAR NOT NULL,
    student_id VARCHAR NOT NULL,
    session_id VARCHAR NOT NULL,
    correct_answers INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    score_percentage DOUBLE PRECISION NOT NULL,
    grade DOUBLE PRECISION NOT NULL,
    proficiency DOUBLE PRECISION,
    classification VARCHAR,
    posicao INTEGER NOT NULL,
    moedas_ganhas INTEGER NOT NULL DEFAULT 0,
    tempo_gasto INTEGER,
    acertos INTEGER NOT NULL,
    erros INTEGER NOT NULL,
    em_branco INTEGER NOT NULL,
    calculated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    CONSTRAINT uq_competition_results_competition_student UNIQUE (competition_id, student_id)
);

-- Tabela: competition_rewards
CREATE TABLE IF NOT EXISTS competition_rewards (
    id VARCHAR NOT NULL PRIMARY KEY,
    competition_id VARCHAR NOT NULL,
    student_id VARCHAR NOT NULL,
    participation_paid_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_competition_rewards_competition_student UNIQUE (competition_id, student_id)
);

-- Tabela: competition_ranking_payouts
CREATE TABLE IF NOT EXISTS competition_ranking_payouts (
    id VARCHAR NOT NULL PRIMARY KEY,
    competition_id VARCHAR NOT NULL,
    student_id VARCHAR NOT NULL,
    position INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    paid_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_competition_ranking_payouts_competition_student UNIQUE (competition_id, student_id)
);

-- Tabela: ideb_meta_saves
CREATE TABLE IF NOT EXISTS ideb_meta_saves (
    id VARCHAR NOT NULL PRIMARY KEY,
    city_id VARCHAR NOT NULL,
    level VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ideb_meta_saves_context UNIQUE (city_id, level),
    CONSTRAINT ideb_meta_saves_city_id_fkey FOREIGN KEY (city_id) REFERENCES city(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ideb_meta_saves_context ON ideb_meta_saves(city_id, level);

-- Tabela: skill_grade
CREATE TABLE IF NOT EXISTS skill_grade (
    skill_id UUID NOT NULL,
    grade_id UUID NOT NULL,
    PRIMARY KEY (skill_id, grade_id),
    CONSTRAINT skill_grade_skill_id_fkey FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    CONSTRAINT skill_grade_grade_id_fkey FOREIGN KEY (grade_id) REFERENCES grade(id) ON DELETE CASCADE
);

-- Tabela: store_items
CREATE TABLE IF NOT EXISTS store_items (
    id VARCHAR NOT NULL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    category VARCHAR(64) NOT NULL,
    reward_type VARCHAR(64) NOT NULL,
    reward_data TEXT,
    is_physical BOOLEAN NOT NULL DEFAULT false,
    scope_type VARCHAR(32) NOT NULL DEFAULT 'system',
    scope_filter JSON,
    is_active BOOLEAN NOT NULL DEFAULT true,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabela: student_purchases
CREATE TABLE IF NOT EXISTS student_purchases (
    id VARCHAR NOT NULL PRIMARY KEY,
    student_id VARCHAR NOT NULL,
    store_item_id VARCHAR NOT NULL,
    purchase_price INTEGER NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    purchased_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    delivered_at TIMESTAMP WITHOUT TIME ZONE,
    delivery_address TEXT,
    tracking_code VARCHAR(255),
    notes TEXT,
    CONSTRAINT student_purchases_store_item_id_fkey FOREIGN KEY (store_item_id) REFERENCES store_items(id) ON DELETE CASCADE
);

-- Tabela: test
CREATE TABLE IF NOT EXISTS test (
    id VARCHAR NOT NULL PRIMARY KEY,
    title VARCHAR(100),
    description VARCHAR(500),
    intructions VARCHAR(500),
    type VARCHAR,
    max_score DOUBLE PRECISION,
    time_limit TIMESTAMP WITHOUT TIME ZONE,
    end_time TIMESTAMP WITHOUT TIME ZONE,
    duration INTEGER,
    evaluation_mode VARCHAR(20) DEFAULT 'virtual',
    created_by VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    subject VARCHAR,
    grade_id UUID,
    municipalities JSON,
    schools JSON,
    classes JSON,
    course VARCHAR(100),
    model VARCHAR(50),
    subjects_info JSON,
    status VARCHAR(20) DEFAULT 'pendente',
    grade_calculation_type VARCHAR(20) DEFAULT 'complex'
);

CREATE INDEX IF NOT EXISTS ix_test_created_by ON test(created_by);
CREATE INDEX IF NOT EXISTS ix_test_subject ON test(subject);

-- Tabela: test_questions
CREATE TABLE IF NOT EXISTS test_questions (
    id VARCHAR NOT NULL PRIMARY KEY,
    test_id VARCHAR NOT NULL,
    question_id VARCHAR NOT NULL,
    "order" INTEGER,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_test_questions_test_question UNIQUE (test_id, question_id),
    CONSTRAINT test_questions_test_id_fkey FOREIGN KEY (test_id) REFERENCES test(id),
    CONSTRAINT test_questions_question_id_fkey FOREIGN KEY (question_id) REFERENCES question(id)
);

-- Tabela: test_sessions
CREATE TABLE IF NOT EXISTS test_sessions (
    id VARCHAR NOT NULL PRIMARY KEY,
    student_id VARCHAR NOT NULL,
    test_id VARCHAR NOT NULL,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    actual_start_time TIMESTAMP WITHOUT TIME ZONE,
    submitted_at TIMESTAMP WITHOUT TIME ZONE,
    time_limit_minutes INTEGER,
    status VARCHAR(20) DEFAULT 'em_andamento',
    total_questions INTEGER,
    correct_answers INTEGER,
    score DOUBLE PRECISION,
    grade DOUBLE PRECISION,
    manual_score NUMERIC,
    feedback TEXT,
    corrected_by VARCHAR,
    corrected_at TIMESTAMP WITHOUT TIME ZONE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE
);

-- ============================================================================
-- PARTE 2: ADIÇÃO DE NOVAS COLUNAS EM TABELAS EXISTENTES
-- ============================================================================

-- Tabela: user_settings - Adicionar novas colunas
DO $$
BEGIN
    -- sidebar_theme_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' 
        AND column_name = 'sidebar_theme_id'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN sidebar_theme_id VARCHAR(128);
    END IF;

    -- frame_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' 
        AND column_name = 'frame_id'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN frame_id VARCHAR(128);
    END IF;

    -- stamp_id
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' 
        AND column_name = 'stamp_id'
    ) THEN
        ALTER TABLE user_settings ADD COLUMN stamp_id VARCHAR(128);
    END IF;
END $$;

-- ============================================================================
-- VERIFICAÇÕES E RESUMO
-- ============================================================================

-- Contar novas tabelas criadas
SELECT 'Tabelas verificadas' as status;

SELECT 
    'answer_sheet_generation_jobs' as tabela,
    CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'answer_sheet_generation_jobs') 
        THEN 'Existe' ELSE 'Não existe' END as status
UNION ALL
SELECT 'competitions', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'competitions') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'competition_enrollments', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'competition_enrollments') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'competition_results', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'competition_results') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'competition_rewards', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'competition_rewards') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'competition_ranking_payouts', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'competition_ranking_payouts') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'ideb_meta_saves', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'ideb_meta_saves') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'skill_grade', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'skill_grade') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'store_items', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'store_items') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'student_purchases', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'student_purchases') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'test', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'test') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'test_questions', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'test_questions') 
    THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 'test_sessions', CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'test_sessions') 
    THEN 'Existe' ELSE 'Não existe' END;

-- Verificar novas colunas em user_settings
SELECT 
    'user_settings.sidebar_theme_id' as coluna,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' AND column_name = 'sidebar_theme_id'
    ) THEN 'Existe' ELSE 'Não existe' END as status
UNION ALL
SELECT 
    'user_settings.frame_id',
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' AND column_name = 'frame_id'
    ) THEN 'Existe' ELSE 'Não existe' END
UNION ALL
SELECT 
    'user_settings.stamp_id',
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'user_settings' AND column_name = 'stamp_id'
    ) THEN 'Existe' ELSE 'Não existe' END;

COMMIT;

-- ============================================================================
-- RESUMO DA MIGRAÇÃO
-- ============================================================================
-- 
-- NOVAS TABELAS CRIADAS (13):
-- 1. answer_sheet_generation_jobs
-- 2. competitions
-- 3. competition_enrollments
-- 4. competition_results
-- 5. competition_rewards
-- 6. competition_ranking_payouts
-- 7. ideb_meta_saves
-- 8. skill_grade
-- 9. store_items
-- 10. student_purchases
-- 11. test
-- 12. test_questions
-- 13. test_sessions
--
-- TABELAS MODIFICADAS (1):
-- 1. user_settings - Adicionadas 3 colunas:
--    - sidebar_theme_id
--    - frame_id
--    - stamp_id
--
-- ============================================================================
