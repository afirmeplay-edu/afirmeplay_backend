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
"""
