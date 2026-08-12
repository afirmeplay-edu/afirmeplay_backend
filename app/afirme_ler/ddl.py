# -*- coding: utf-8 -*-
"""DDL idempotente das tabelas de avaliação Afirme Ler em schemas city_xxx."""


def get_afirme_ler_evaluation_tables_ddl(schema: str) -> str:
  return f"""
CREATE TABLE IF NOT EXISTS "{schema}".reading_evaluation (
    id VARCHAR PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    reading_text_id VARCHAR NOT NULL,
    words_word_list_id VARCHAR,
    uncommon_word_list_id VARCHAR,
    grade_id UUID REFERENCES public.grade(id),
    class_ids JSON NOT NULL DEFAULT '[]'::json,
    school_ids JSON,
    assessment_type VARCHAR(20) NOT NULL DEFAULT 'completa',
    status VARCHAR(20) NOT NULL DEFAULT 'rascunho',
    application_start TIMESTAMP,
    application_end TIMESTAMP,
    timezone VARCHAR(50) DEFAULT 'America/Sao_Paulo',
    created_by VARCHAR NOT NULL REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_reading_evaluation_assessment_type
        CHECK (assessment_type IN ('fluencia', 'compreensao', 'completa')),
    CONSTRAINT chk_reading_evaluation_status
        CHECK (status IN ('rascunho', 'agendada', 'em_andamento', 'concluida', 'cancelada'))
);
CREATE INDEX IF NOT EXISTS ix_reading_evaluation_status ON "{schema}".reading_evaluation(status);
CREATE INDEX IF NOT EXISTS ix_reading_evaluation_reading_text_id ON "{schema}".reading_evaluation(reading_text_id);
COMMENT ON TABLE "{schema}".reading_evaluation IS 'Avaliações de leitura (fluência/compreensão) do município';

CREATE TABLE IF NOT EXISTS "{schema}".reading_evaluation_session (
    id VARCHAR PRIMARY KEY,
    reading_evaluation_id VARCHAR NOT NULL
        REFERENCES "{schema}".reading_evaluation(id) ON DELETE CASCADE,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    class_id UUID REFERENCES "{schema}".class(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pendente',
    fluency_data JSON,
    calculated_plcm DOUBLE PRECISION,
    calculated_accuracy DOUBLE PRECISION,
    precision_level VARCHAR(30),
    fluency_level VARCHAR(30),
    ica_score DOUBLE PRECISION,
    ica_breakdown JSON,
    prosody_level INTEGER,
    comprehension_correct_count INTEGER,
    comprehension_total INTEGER,
    comprehension_score DOUBLE PRECISION,
    started_at TIMESTAMP,
    submitted_at TIMESTAMP,
    applied_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_reading_eval_session_status
        CHECK (status IN ('pendente', 'em_andamento', 'finalizada', 'ausente')),
    CONSTRAINT uq_reading_eval_session_student UNIQUE(reading_evaluation_id, student_id)
);
CREATE INDEX IF NOT EXISTS ix_reading_eval_session_evaluation
    ON "{schema}".reading_evaluation_session(reading_evaluation_id);
CREATE INDEX IF NOT EXISTS ix_reading_eval_session_student
    ON "{schema}".reading_evaluation_session(student_id);
COMMENT ON TABLE "{schema}".reading_evaluation_session IS 'Sessão de avaliação de leitura por aluno';

ALTER TABLE "{schema}".reading_evaluation_session
    ADD COLUMN IF NOT EXISTS calculated_plcm DOUBLE PRECISION;
ALTER TABLE "{schema}".reading_evaluation_session
    ADD COLUMN IF NOT EXISTS calculated_accuracy DOUBLE PRECISION;
ALTER TABLE "{schema}".reading_evaluation_session
    ADD COLUMN IF NOT EXISTS precision_level VARCHAR(30);
ALTER TABLE "{schema}".reading_evaluation_session
    ADD COLUMN IF NOT EXISTS fluency_level VARCHAR(30);
ALTER TABLE "{schema}".reading_evaluation_session
    ADD COLUMN IF NOT EXISTS ica_score DOUBLE PRECISION;
ALTER TABLE "{schema}".reading_evaluation_session
    ADD COLUMN IF NOT EXISTS ica_breakdown JSON;
ALTER TABLE "{schema}".reading_evaluation_session
    ADD COLUMN IF NOT EXISTS prosody_level INTEGER;

CREATE TABLE IF NOT EXISTS "{schema}".reading_comprehension_answer (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL
        REFERENCES "{schema}".reading_evaluation_session(id) ON DELETE CASCADE,
    reading_text_question_id VARCHAR NOT NULL,
    selected_option INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_reading_comp_answer UNIQUE(session_id, reading_text_question_id)
);
CREATE INDEX IF NOT EXISTS ix_reading_comp_answer_session
    ON "{schema}".reading_comprehension_answer(session_id);
COMMENT ON TABLE "{schema}".reading_comprehension_answer IS 'Respostas de compreensão na avaliação de leitura';

CREATE TABLE IF NOT EXISTS "{schema}".reading_guided_session (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    class_id UUID REFERENCES "{schema}".class(id),
    reading_text_id VARCHAR NOT NULL,
    words_read INTEGER NOT NULL,
    reading_time_seconds INTEGER NOT NULL,
    errors_count INTEGER NOT NULL DEFAULT 0,
    prosody_level INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'finalizada',
    calculated_plcm DOUBLE PRECISION,
    calculated_accuracy DOUBLE PRECISION,
    comprehension_correct_count INTEGER,
    comprehension_total INTEGER,
    comprehension_score DOUBLE PRECISION,
    audio_bucket VARCHAR(100),
    audio_key TEXT,
    audio_mime_type VARCHAR(100),
    audio_size_bytes INTEGER,
    applied_by VARCHAR REFERENCES public.users(id),
    submitted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_reading_guided_session_status
        CHECK (status IN ('em_andamento', 'finalizada')),
    CONSTRAINT chk_reading_guided_prosody
        CHECK (prosody_level BETWEEN 1 AND 5),
    CONSTRAINT chk_reading_guided_words
        CHECK (words_read >= 0 AND reading_time_seconds >= 0 AND errors_count >= 0)
);
CREATE INDEX IF NOT EXISTS ix_reading_guided_session_student
    ON "{schema}".reading_guided_session(student_id);
CREATE INDEX IF NOT EXISTS ix_reading_guided_session_text
    ON "{schema}".reading_guided_session(reading_text_id);
CREATE INDEX IF NOT EXISTS ix_reading_guided_session_created
    ON "{schema}".reading_guided_session(created_at DESC);
COMMENT ON TABLE "{schema}".reading_guided_session IS 'Sessão de leitura guiada (1 aluno + 1 texto + métricas + áudio)';

CREATE TABLE IF NOT EXISTS "{schema}".reading_guided_comprehension_answer (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL
        REFERENCES "{schema}".reading_guided_session(id) ON DELETE CASCADE,
    reading_text_question_id VARCHAR NOT NULL,
    selected_option INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_reading_guided_comp_answer UNIQUE(session_id, reading_text_question_id)
);
CREATE INDEX IF NOT EXISTS ix_reading_guided_comp_answer_session
    ON "{schema}".reading_guided_comprehension_answer(session_id);
COMMENT ON TABLE "{schema}".reading_guided_comprehension_answer IS 'Respostas de compreensão na leitura guiada';

CREATE TABLE IF NOT EXISTS "{schema}".reading_guided_auto_session (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    class_id UUID REFERENCES "{schema}".class(id),
    reading_text_id VARCHAR,
    words_word_list_id VARCHAR,
    uncommon_word_list_id VARCHAR,
    expected_payload JSON NOT NULL DEFAULT '{{}}'::json,
    part_results JSON,
    ica_breakdown JSON,
    status VARCHAR(30) NOT NULL DEFAULT 'awaiting_audio',
    words_read INTEGER,
    errors_count INTEGER,
    omitted_count INTEGER,
    extra_count INTEGER,
    duration_seconds DOUBLE PRECISION,
    calculated_plcm DOUBLE PRECISION,
    calculated_accuracy DOUBLE PRECISION,
    precision_level VARCHAR(30),
    fluency_level VARCHAR(30),
    comprehension_correct_count INTEGER,
    comprehension_total INTEGER,
    comprehension_score DOUBLE PRECISION,
    ica_score DOUBLE PRECISION,
    transcript_raw TEXT,
    stt_provider VARCHAR(50),
    stt_model VARCHAR(100),
    algorithm_version VARCHAR(20),
    evaluation_version VARCHAR(20),
    error_message TEXT,
    audio_bucket VARCHAR(100),
    audio_key TEXT,
    audio_mime_type VARCHAR(100),
    audio_size_bytes INTEGER,
    part_audios JSON,
    applied_by VARCHAR REFERENCES public.users(id),
    submitted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_reading_guided_auto_status
        CHECK (status IN ('awaiting_audio', 'queued', 'processing', 'completed', 'failed'))
);
CREATE INDEX IF NOT EXISTS ix_reading_guided_auto_session_student
    ON "{schema}".reading_guided_auto_session(student_id);
CREATE INDEX IF NOT EXISTS ix_reading_guided_auto_session_status
    ON "{schema}".reading_guided_auto_session(status);
CREATE INDEX IF NOT EXISTS ix_reading_guided_auto_session_created
    ON "{schema}".reading_guided_auto_session(created_at DESC);
COMMENT ON TABLE "{schema}".reading_guided_auto_session IS 'Leitura guiada automática (STT + métricas oficiais no backend)';

CREATE TABLE IF NOT EXISTS "{schema}".reading_guided_auto_word (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL
        REFERENCES "{schema}".reading_guided_auto_session(id) ON DELETE CASCADE,
    part VARCHAR(20) NOT NULL DEFAULT 'text',
    position INTEGER NOT NULL,
    expected_token VARCHAR(255),
    recognized_token VARCHAR(255),
    similarity DOUBLE PRECISION,
    phonetic_expected VARCHAR(255),
    phonetic_recognized VARCHAR(255),
    match_type VARCHAR(20) NOT NULL,
    start_ms INTEGER,
    end_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_reading_guided_auto_word_session
    ON "{schema}".reading_guided_auto_word(session_id);
COMMENT ON TABLE "{schema}".reading_guided_auto_word IS 'Alinhamento por palavra da leitura guiada automática';

CREATE TABLE IF NOT EXISTS "{schema}".reading_guided_auto_comprehension_answer (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL
        REFERENCES "{schema}".reading_guided_auto_session(id) ON DELETE CASCADE,
    reading_text_question_id VARCHAR NOT NULL,
    selected_option INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_reading_guided_auto_comp_answer UNIQUE(session_id, reading_text_question_id)
);
CREATE INDEX IF NOT EXISTS ix_reading_guided_auto_comp_answer_session
    ON "{schema}".reading_guided_auto_comprehension_answer(session_id);
COMMENT ON TABLE "{schema}".reading_guided_auto_comprehension_answer IS 'Respostas de compreensão na leitura guiada automática';

CREATE TABLE IF NOT EXISTS "{schema}".reading_fluency_session (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    class_id UUID REFERENCES "{schema}".class(id),
    school_id VARCHAR(36),
    reading_text_id VARCHAR NOT NULL,
    words_word_list_id VARCHAR,
    uncommon_word_list_id VARCHAR,
    caderno VARCHAR(8) NOT NULL DEFAULT 'A',
    status VARCHAR(20) NOT NULL DEFAULT 'em_andamento',
    fluency_data JSON,
    part_audios JSON,
    calculated_plcm DOUBLE PRECISION,
    calculated_accuracy DOUBLE PRECISION,
    precision_level VARCHAR(30),
    fluency_level VARCHAR(30),
    ica_score DOUBLE PRECISION,
    ica_breakdown JSON,
    prosody_level INTEGER,
    comprehension_correct_count INTEGER,
    comprehension_total INTEGER,
    comprehension_score DOUBLE PRECISION,
    started_at TIMESTAMP,
    submitted_at TIMESTAMP,
    applied_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_reading_fluency_session_status
        CHECK (status IN ('em_andamento', 'finalizada', 'ausente')),
    CONSTRAINT chk_reading_fluency_prosody
        CHECK (prosody_level IS NULL OR prosody_level BETWEEN 1 AND 5)
);
CREATE INDEX IF NOT EXISTS ix_reading_fluency_session_student
    ON "{schema}".reading_fluency_session(student_id);
CREATE INDEX IF NOT EXISTS ix_reading_fluency_session_status
    ON "{schema}".reading_fluency_session(status);
CREATE INDEX IF NOT EXISTS ix_reading_fluency_session_created
    ON "{schema}".reading_fluency_session(created_at DESC);
COMMENT ON TABLE "{schema}".reading_fluency_session IS 'Sessão ad-hoc de Fluência Leitora (CAEd) sem avaliação pré-aplicada';

CREATE TABLE IF NOT EXISTS "{schema}".reading_fluency_comprehension_answer (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL
        REFERENCES "{schema}".reading_fluency_session(id) ON DELETE CASCADE,
    reading_text_question_id VARCHAR NOT NULL,
    selected_option INTEGER NOT NULL,
    is_correct BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_reading_fluency_comp_answer UNIQUE(session_id, reading_text_question_id)
);
CREATE INDEX IF NOT EXISTS ix_reading_fluency_comp_answer_session
    ON "{schema}".reading_fluency_comprehension_answer(session_id);
COMMENT ON TABLE "{schema}".reading_fluency_comprehension_answer IS 'Respostas de compreensão na sessão ad-hoc de fluência';
"""
