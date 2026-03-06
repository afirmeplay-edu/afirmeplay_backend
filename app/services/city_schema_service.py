"""
Provisiona o schema PostgreSQL city_<id> e as tabelas operacionais ao criar um novo município.
Reutiliza a mesma estrutura da migração 0001_init_city_schemas.
"""
import logging
from app import db
from app.utils.tenant_middleware import city_id_to_schema_name

logger = logging.getLogger(__name__)


def provision_city_schema(city_id: str, city_name: str, city_state: str) -> None:
    """
    Cria o schema city_<id> e todas as tabelas operacionais para o município.
    Idempotente: usa CREATE SCHEMA IF NOT EXISTS e CREATE TABLE IF NOT EXISTS.

    Raises:
        Exception: em falha de SQL (ex.: permissão, conexão).
    """
    schema_name = city_id_to_schema_name(city_id)
    # Garantir que o nome do schema é seguro (apenas alfanumérico e underscore)
    if not schema_name.replace("_", "").isalnum() or not schema_name.startswith("city_"):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    raw_conn = db.engine.raw_connection()
    try:
        raw_conn.set_isolation_level(0)  # AUTOCOMMIT para DDL
        cursor = raw_conn.cursor()

        cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        comment = f"Schema operacional do município: {city_name}/{city_state} (ID: {city_id})"
        cursor.execute(f'COMMENT ON SCHEMA "{schema_name}" IS %s', (comment,))

        # DDL das tabelas (igual à migração 0001) – um bloco por vez para compatibilidade
        ddl = _get_city_tables_ddl(schema_name)
        cursor.execute(ddl)

        logger.info("Schema e tabelas criados para cidade %s (%s)", city_id, schema_name)
    except Exception as e:
        logger.exception("Falha ao provisionar schema para cidade %s: %s", city_id, e)
        raise
    finally:
        if raw_conn:
            raw_conn.close()


def _get_city_tables_ddl(schema: str) -> str:
    """Retorna o SQL de criação das tabelas do schema city (mesmo conteúdo da migração 0001)."""
    # Uso de {schema} único; literais JSON como '{{}}' para .format()
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".school (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100),
    address VARCHAR(200),
    domain VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    city_id VARCHAR REFERENCES public.city(id)
);
COMMENT ON TABLE "{schema}".school IS 'Escolas do município';

CREATE TABLE IF NOT EXISTS "{schema}".school_course (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    education_stage_id UUID REFERENCES public.education_stage(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_school_education_stage UNIQUE(school_id, education_stage_id)
);
COMMENT ON TABLE "{schema}".school_course IS 'Cursos oferecidos pelas escolas';

CREATE TABLE IF NOT EXISTS "{schema}".class (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    grade_id UUID REFERENCES public.grade(id)
);
COMMENT ON TABLE "{schema}".class IS 'Turmas das escolas';

CREATE TABLE IF NOT EXISTS "{schema}".student (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(100),
    profile_picture VARCHAR,
    registration VARCHAR(50) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    birth_date DATE,
    user_id VARCHAR REFERENCES public.users(id) UNIQUE,
    grade_id UUID REFERENCES public.grade(id),
    class_id UUID REFERENCES "{schema}".class(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id)
);
COMMENT ON TABLE "{schema}".student IS 'Alunos das escolas do município';

CREATE TABLE IF NOT EXISTS "{schema}".teacher (
    id VARCHAR PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    profile_picture VARCHAR,
    registration VARCHAR(50) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    birth_date DATE,
    user_id VARCHAR REFERENCES public.users(id) UNIQUE
);
COMMENT ON TABLE "{schema}".teacher IS 'Professores do município';

CREATE TABLE IF NOT EXISTS "{schema}".school_teacher (
    id VARCHAR PRIMARY KEY,
    registration VARCHAR,
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    teacher_id VARCHAR REFERENCES "{schema}".teacher(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".school_teacher IS 'Vínculo professor-escola';

CREATE TABLE IF NOT EXISTS "{schema}".teacher_class (
    id VARCHAR PRIMARY KEY,
    teacher_id VARCHAR REFERENCES "{schema}".teacher(id),
    class_id UUID REFERENCES "{schema}".class(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".teacher_class IS 'Vínculo professor-turma';

CREATE TABLE IF NOT EXISTS "{schema}".class_subject (
    id VARCHAR PRIMARY KEY,
    class_id UUID REFERENCES "{schema}".class(id),
    subject_id VARCHAR REFERENCES public.subject(id),
    teacher_id VARCHAR REFERENCES "{schema}".teacher(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".class_subject IS 'Disciplinas ministradas em turmas';

CREATE TABLE IF NOT EXISTS "{schema}".school_managers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    manager_id VARCHAR REFERENCES public.manager(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    role VARCHAR(50),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_active_manager_school UNIQUE(manager_id, school_id, is_active)
);
COMMENT ON TABLE "{schema}".school_managers IS 'Vínculo manager-escola (substitui manager.school_id)';
CREATE INDEX IF NOT EXISTS idx_school_managers_active ON "{schema}".school_managers(is_active) WHERE is_active = true;

CREATE TABLE IF NOT EXISTS "{schema}".test (
    id VARCHAR PRIMARY KEY,
    title VARCHAR(100),
    description VARCHAR(500),
    intructions VARCHAR(500),
    type VARCHAR,
    max_score FLOAT,
    time_limit TIMESTAMP,
    end_time TIMESTAMP,
    duration INTEGER,
    evaluation_mode VARCHAR(20) DEFAULT 'virtual',
    created_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    subject VARCHAR REFERENCES public.subject(id),
    grade_id UUID REFERENCES public.grade(id),
    municipalities JSON,
    schools JSON,
    classes JSON,
    course VARCHAR(100),
    model VARCHAR(50),
    subjects_info JSON,
    status VARCHAR(20) DEFAULT 'pendente',
    grade_calculation_type VARCHAR(20) DEFAULT 'complex'
);
COMMENT ON TABLE "{schema}".test IS 'Avaliações criadas no município';

CREATE TABLE IF NOT EXISTS "{schema}".test_questions (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR REFERENCES "{schema}".test(id),
    question_id VARCHAR REFERENCES public.question(id),
    "order" INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".test_questions IS 'Questões das avaliações';

CREATE TABLE IF NOT EXISTS "{schema}".class_test (
    id VARCHAR PRIMARY KEY,
    class_id UUID REFERENCES "{schema}".class(id),
    test_id VARCHAR REFERENCES "{schema}".test(id),
    status VARCHAR DEFAULT 'agendada',
    application TEXT NOT NULL,
    expiration TEXT NOT NULL,
    timezone VARCHAR(50)
);
COMMENT ON TABLE "{schema}".class_test IS 'Aplicação de testes em turmas';

CREATE TABLE IF NOT EXISTS "{schema}".student_test_olimpics (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR REFERENCES "{schema}".student(id),
    test_id VARCHAR REFERENCES "{schema}".test(id),
    status VARCHAR DEFAULT 'agendada',
    application TEXT NOT NULL,
    expiration TEXT NOT NULL,
    timezone VARCHAR(50),
    CONSTRAINT uq_student_test_olimpics_student_test UNIQUE(student_id, test_id)
);
COMMENT ON TABLE "{schema}".student_test_olimpics IS 'Inscrições de alunos em olimpíadas';

CREATE TABLE IF NOT EXISTS "{schema}".student_answers (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR REFERENCES "{schema}".student(id),
    test_id VARCHAR REFERENCES "{schema}".test(id),
    question_id VARCHAR REFERENCES public.question(id),
    answer TEXT NOT NULL,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_correct BOOLEAN,
    manual_score FLOAT,
    feedback TEXT,
    corrected_by VARCHAR REFERENCES public.users(id),
    corrected_at TIMESTAMP
);
COMMENT ON TABLE "{schema}".student_answers IS 'Respostas dos alunos';

CREATE TABLE IF NOT EXISTS "{schema}".test_sessions (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR REFERENCES "{schema}".student(id),
    test_id VARCHAR REFERENCES "{schema}".test(id),
    started_at TIMESTAMP,
    actual_start_time TIMESTAMP,
    submitted_at TIMESTAMP,
    time_limit_minutes INTEGER,
    status VARCHAR(20) DEFAULT 'em_andamento',
    total_questions INTEGER,
    correct_answers INTEGER,
    score FLOAT,
    grade FLOAT,
    manual_score NUMERIC(5, 2),
    feedback TEXT,
    corrected_by VARCHAR REFERENCES public.users(id),
    corrected_at TIMESTAMP,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".test_sessions IS 'Sessões de prova dos alunos';

CREATE TABLE IF NOT EXISTS "{schema}".evaluation_results (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR REFERENCES "{schema}".test(id),
    student_id VARCHAR REFERENCES "{schema}".student(id),
    session_id VARCHAR REFERENCES "{schema}".test_sessions(id),
    correct_answers INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    score_percentage FLOAT NOT NULL,
    grade FLOAT NOT NULL,
    proficiency FLOAT NOT NULL,
    classification VARCHAR(50) NOT NULL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".evaluation_results IS 'Resultados de avaliações';

CREATE TABLE IF NOT EXISTS "{schema}".physical_test_forms (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR REFERENCES "{schema}".test(id),
    student_id VARCHAR REFERENCES "{schema}".student(id),
    class_test_id VARCHAR REFERENCES "{schema}".class_test(id),
    form_pdf_data BYTEA,
    answer_sheet_data BYTEA,
    correction_image_data BYTEA,
    form_pdf_url VARCHAR,
    answer_sheet_url VARCHAR,
    correction_image_url VARCHAR,
    qr_code_data VARCHAR NOT NULL,
    qr_code_coordinates JSON,
    status VARCHAR DEFAULT 'gerado',
    is_corrected BOOLEAN DEFAULT false,
    form_type VARCHAR DEFAULT 'institutional',
    num_questions INTEGER,
    use_blocks BOOLEAN DEFAULT false,
    blocks_config JSON,
    correct_answers JSON,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    corrected_at TIMESTAMP,
    processed_at TIMESTAMP,
    answer_sheet_sent_at TIMESTAMP
);
COMMENT ON TABLE "{schema}".physical_test_forms IS 'Formulários físicos gerados';

CREATE TABLE IF NOT EXISTS "{schema}".physical_test_answers (
    id VARCHAR PRIMARY KEY,
    physical_form_id VARCHAR REFERENCES "{schema}".physical_test_forms(id),
    question_id VARCHAR REFERENCES public.question(id),
    marked_answer VARCHAR,
    correct_answer VARCHAR NOT NULL,
    is_correct BOOLEAN,
    confidence_score FLOAT,
    detection_coordinates JSON,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    corrected_at TIMESTAMP
);
COMMENT ON TABLE "{schema}".physical_test_answers IS 'Respostas de formulários físicos';

CREATE TABLE IF NOT EXISTS "{schema}".form_coordinates (
    id VARCHAR(36) PRIMARY KEY,
    test_id VARCHAR(36) REFERENCES "{schema}".test(id),
    form_type VARCHAR(50) NOT NULL DEFAULT 'physical_test',
    qr_code_id VARCHAR(36),
    student_id VARCHAR(36) REFERENCES "{schema}".student(id),
    coordinates JSON NOT NULL,
    num_questions INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_test_form_type UNIQUE(test_id, form_type)
);
COMMENT ON TABLE "{schema}".form_coordinates IS 'Coordenadas de formulários de resposta';

CREATE TABLE IF NOT EXISTS "{schema}".answer_sheet_gabaritos (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR REFERENCES "{schema}".test(id),
    class_id UUID REFERENCES "{schema}".class(id),
    grade_id UUID REFERENCES public.grade(id),
    num_questions INTEGER NOT NULL,
    use_blocks BOOLEAN DEFAULT false,
    blocks_config JSON,
    scope_type VARCHAR(50) DEFAULT 'class',
    correct_answers JSON NOT NULL,
    coordinates JSON,
    template_block_1 BYTEA,
    template_block_2 BYTEA,
    template_block_3 BYTEA,
    template_block_4 BYTEA,
    template_generated_at TIMESTAMP,
    template_dpi INTEGER,
    title VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR REFERENCES public.users(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    school_name VARCHAR(200),
    municipality VARCHAR(200),
    state VARCHAR(100),
    grade_name VARCHAR(100),
    institution VARCHAR(200),
    minio_url VARCHAR(500),
    minio_object_name VARCHAR(200),
    minio_bucket VARCHAR(100),
    zip_generated_at TIMESTAMP,
    batch_id VARCHAR(36)
);
COMMENT ON TABLE "{schema}".answer_sheet_gabaritos IS 'Gabaritos de cartões resposta';

CREATE TABLE IF NOT EXISTS "{schema}".answer_sheet_results (
    id VARCHAR PRIMARY KEY,
    gabarito_id VARCHAR REFERENCES "{schema}".answer_sheet_gabaritos(id),
    student_id VARCHAR REFERENCES "{schema}".student(id),
    detected_answers JSON NOT NULL,
    correct_answers INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    incorrect_answers INTEGER NOT NULL,
    unanswered_questions INTEGER NOT NULL,
    answered_questions INTEGER NOT NULL,
    score_percentage FLOAT NOT NULL,
    grade FLOAT NOT NULL,
    proficiency FLOAT,
    classification VARCHAR(50),
    corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    detection_method VARCHAR(20) DEFAULT 'geometric'
);
COMMENT ON TABLE "{schema}".answer_sheet_results IS 'Resultados de correção de cartões';

CREATE TABLE IF NOT EXISTS "{schema}".batch_correction_jobs (
    id VARCHAR(36) PRIMARY KEY,
    test_id VARCHAR(36) NOT NULL,
    created_by VARCHAR(36) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_images INTEGER NOT NULL DEFAULT 0,
    processed_images INTEGER NOT NULL DEFAULT 0,
    successful_corrections INTEGER NOT NULL DEFAULT 0,
    failed_corrections INTEGER NOT NULL DEFAULT 0,
    current_student_id VARCHAR(36),
    current_student_name VARCHAR(255),
    progress_percentage FLOAT NOT NULL DEFAULT 0.0,
    images_data TEXT,
    gabarito_data TEXT,
    results TEXT,
    errors TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    estimated_completion TIMESTAMP
);
COMMENT ON TABLE "{schema}".batch_correction_jobs IS 'Jobs de correção em lote';

CREATE TABLE IF NOT EXISTS "{schema}".report_aggregates (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR REFERENCES "{schema}".test(id) NOT NULL,
    scope_type VARCHAR(32) NOT NULL,
    scope_id VARCHAR,
    payload JSON NOT NULL DEFAULT '{{}}',
    student_count INTEGER NOT NULL DEFAULT 0,
    ai_analysis JSON DEFAULT '{{}}',
    ai_analysis_generated_at TIMESTAMP,
    ai_analysis_is_dirty BOOLEAN NOT NULL DEFAULT false,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_dirty BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT uq_report_aggregate_scope UNIQUE(test_id, scope_type, scope_id)
);
COMMENT ON TABLE "{schema}".report_aggregates IS 'Cache de relatórios agregados';
CREATE INDEX IF NOT EXISTS idx_report_aggregates_test ON "{schema}".report_aggregates(test_id);
CREATE INDEX IF NOT EXISTS idx_report_aggregates_scope ON "{schema}".report_aggregates(scope_type, scope_id);

CREATE TABLE IF NOT EXISTS "{schema}".games (
    id VARCHAR PRIMARY KEY,
    url VARCHAR(500) NOT NULL,
    title VARCHAR(200) NOT NULL,
    "iframeHtml" TEXT NOT NULL,
    thumbnail VARCHAR(500),
    author VARCHAR(200),
    provider VARCHAR(50) NOT NULL DEFAULT 'wordwall',
    subject VARCHAR(100) NOT NULL,
    "userId" VARCHAR REFERENCES public.users(id) NOT NULL,
    "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".games IS 'Jogos criados por professores';

CREATE TABLE IF NOT EXISTS "{schema}".game_classes (
    id VARCHAR PRIMARY KEY,
    game_id VARCHAR REFERENCES "{schema}".games(id),
    class_id UUID REFERENCES "{schema}".class(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".game_classes IS 'Jogos aplicados em turmas';

CREATE TABLE IF NOT EXISTS "{schema}".calendar_events (
    id VARCHAR PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    location VARCHAR(200),
    start_at TIMESTAMP WITH TIME ZONE NOT NULL,
    end_at TIMESTAMP WITH TIME ZONE,
    all_day BOOLEAN NOT NULL DEFAULT false,
    timezone VARCHAR(64),
    recurrence_rule VARCHAR(255),
    is_published BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id VARCHAR REFERENCES public.users(id) NOT NULL,
    created_by_role VARCHAR(32) NOT NULL,
    visibility_scope VARCHAR NOT NULL,
    municipality_id VARCHAR REFERENCES public.city(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    metadata_json JSON
);
COMMENT ON TABLE "{schema}".calendar_events IS 'Eventos de calendário';

CREATE TABLE IF NOT EXISTS "{schema}".calendar_event_targets (
    id VARCHAR PRIMARY KEY,
    event_id VARCHAR REFERENCES "{schema}".calendar_events(id),
    target_type VARCHAR NOT NULL,
    target_id VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".calendar_event_targets IS 'Alvos de eventos de calendário';

CREATE TABLE IF NOT EXISTS "{schema}".calendar_event_users (
    id VARCHAR PRIMARY KEY,
    event_id VARCHAR REFERENCES "{schema}".calendar_events(id),
    user_id VARCHAR REFERENCES public.users(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    class_id UUID REFERENCES "{schema}".class(id),
    role_snapshot VARCHAR(32),
    read_at TIMESTAMP WITH TIME ZONE,
    dismissed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".calendar_event_users IS 'Usuários vinculados a eventos';

CREATE TABLE IF NOT EXISTS "{schema}".competitions (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    test_id VARCHAR REFERENCES "{schema}".test(id),
    subject_id VARCHAR REFERENCES public.subject(id) NOT NULL,
    level INTEGER NOT NULL,
    scope VARCHAR DEFAULT 'individual',
    scope_filter JSON,
    enrollment_start TIMESTAMP NOT NULL,
    enrollment_end TIMESTAMP NOT NULL,
    application TIMESTAMP NOT NULL,
    expiration TIMESTAMP NOT NULL,
    timezone VARCHAR DEFAULT 'America/Sao_Paulo',
    question_mode VARCHAR DEFAULT 'auto_random',
    question_rules JSON,
    reward_config JSON NOT NULL,
    ranking_criteria VARCHAR DEFAULT 'nota',
    ranking_tiebreaker VARCHAR DEFAULT 'tempo_entrega',
    ranking_visibility VARCHAR DEFAULT 'final',
    max_participants INTEGER,
    recurrence VARCHAR DEFAULT 'manual',
    template_id VARCHAR,
    status VARCHAR DEFAULT 'rascunho',
    created_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".competitions IS 'Competições instanciadas no município';

CREATE TABLE IF NOT EXISTS "{schema}".competition_enrollments (
    id VARCHAR PRIMARY KEY,
    competition_id VARCHAR REFERENCES "{schema}".competitions(id) ON DELETE CASCADE,
    student_id VARCHAR REFERENCES "{schema}".student(id) ON DELETE CASCADE,
    enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR NOT NULL DEFAULT 'inscrito',
    CONSTRAINT uq_competition_enrollments_competition_student UNIQUE(competition_id, student_id)
);
COMMENT ON TABLE "{schema}".competition_enrollments IS 'Inscrições em competições';

CREATE TABLE IF NOT EXISTS "{schema}".competition_results (
    id VARCHAR PRIMARY KEY,
    competition_id VARCHAR REFERENCES "{schema}".competitions(id) ON DELETE CASCADE,
    student_id VARCHAR REFERENCES "{schema}".student(id) ON DELETE CASCADE,
    session_id VARCHAR REFERENCES "{schema}".test_sessions(id) ON DELETE CASCADE,
    correct_answers INTEGER NOT NULL,
    total_questions INTEGER NOT NULL,
    score_percentage FLOAT NOT NULL,
    grade FLOAT NOT NULL,
    proficiency FLOAT,
    classification VARCHAR,
    posicao INTEGER NOT NULL,
    moedas_ganhas INTEGER NOT NULL DEFAULT 0,
    tempo_gasto INTEGER,
    acertos INTEGER NOT NULL,
    erros INTEGER NOT NULL,
    em_branco INTEGER NOT NULL,
    calculated_at TIMESTAMP NOT NULL,
    CONSTRAINT uq_competition_results_competition_student UNIQUE(competition_id, student_id)
);
COMMENT ON TABLE "{schema}".competition_results IS 'Resultados de competições';

CREATE TABLE IF NOT EXISTS "{schema}".competition_rewards (
    id VARCHAR PRIMARY KEY,
    competition_id VARCHAR REFERENCES "{schema}".competitions(id) ON DELETE CASCADE,
    student_id VARCHAR REFERENCES "{schema}".student(id) ON DELETE CASCADE,
    participation_paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_competition_rewards_competition_student UNIQUE(competition_id, student_id)
);
COMMENT ON TABLE "{schema}".competition_rewards IS 'Recompensas de competições';

CREATE TABLE IF NOT EXISTS "{schema}".competition_ranking_payouts (
    id VARCHAR PRIMARY KEY,
    competition_id VARCHAR REFERENCES "{schema}".competitions(id),
    student_id VARCHAR REFERENCES "{schema}".student(id),
    position INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    paid_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_competition_ranking_payouts_competition_student UNIQUE(competition_id, student_id)
);
COMMENT ON TABLE "{schema}".competition_ranking_payouts IS 'Pagamentos de ranking de competições';

CREATE TABLE IF NOT EXISTS "{schema}".forms (
    id VARCHAR PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    form_type VARCHAR(50) NOT NULL,
    instructions TEXT,
    target_groups JSON NOT NULL DEFAULT '[]',
    selected_schools JSON,
    selected_grades JSON,
    selected_classes JSON,
    selected_tecadmin_users JSON,
    filters JSON,
    is_active BOOLEAN DEFAULT true NOT NULL,
    deadline TIMESTAMP,
    created_by VARCHAR REFERENCES public.users(id) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".forms IS 'Formulários socioeconômicos';

CREATE TABLE IF NOT EXISTS "{schema}".form_questions (
    id VARCHAR PRIMARY KEY,
    form_id VARCHAR REFERENCES "{schema}".forms(id) ON DELETE CASCADE,
    question_id VARCHAR(50) NOT NULL,
    text TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    options JSON,
    sub_questions JSON,
    min_value INTEGER,
    max_value INTEGER,
    option_id VARCHAR(50),
    option_text VARCHAR(255),
    required BOOLEAN DEFAULT false NOT NULL,
    question_order INTEGER NOT NULL,
    depends_on JSON
);
COMMENT ON TABLE "{schema}".form_questions IS 'Questões de formulários socioeconômicos';

CREATE TABLE IF NOT EXISTS "{schema}".form_recipients (
    id VARCHAR PRIMARY KEY,
    form_id VARCHAR REFERENCES "{schema}".forms(id) ON DELETE CASCADE,
    user_id VARCHAR REFERENCES public.users(id) ON DELETE CASCADE,
    school_id VARCHAR(36) REFERENCES "{schema}".school(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    CONSTRAINT unique_form_user_recipient UNIQUE(form_id, user_id)
);
COMMENT ON TABLE "{schema}".form_recipients IS 'Destinatários de formulários';

CREATE TABLE IF NOT EXISTS "{schema}".form_responses (
    id VARCHAR PRIMARY KEY,
    form_id VARCHAR REFERENCES "{schema}".forms(id) ON DELETE CASCADE,
    user_id VARCHAR REFERENCES public.users(id) ON DELETE CASCADE,
    recipient_id VARCHAR REFERENCES "{schema}".form_recipients(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'in_progress' NOT NULL,
    responses JSON NOT NULL,
    progress NUMERIC(5, 2) DEFAULT 0.00 NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    time_spent INTEGER DEFAULT 0 NOT NULL,
    CONSTRAINT unique_form_user_response UNIQUE(form_id, user_id)
);
COMMENT ON TABLE "{schema}".form_responses IS 'Respostas de formulários socioeconômicos';

CREATE TABLE IF NOT EXISTS "{schema}".form_result_cache (
    id VARCHAR PRIMARY KEY,
    form_id VARCHAR REFERENCES "{schema}".forms(id) ON DELETE CASCADE,
    report_type VARCHAR(50) NOT NULL,
    filters_hash VARCHAR(64) NOT NULL,
    filters JSON NOT NULL,
    result JSON,
    student_count INTEGER DEFAULT 0 NOT NULL,
    is_dirty BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    CONSTRAINT uq_form_report_filters UNIQUE(form_id, report_type, filters_hash)
);
COMMENT ON TABLE "{schema}".form_result_cache IS 'Cache de resultados de formulários';
CREATE INDEX IF NOT EXISTS idx_form_result_cache_form_type ON "{schema}".form_result_cache(form_id, report_type);
CREATE INDEX IF NOT EXISTS idx_form_result_cache_dirty ON "{schema}".form_result_cache(is_dirty);

CREATE TABLE IF NOT EXISTS "{schema}".play_tv_video_schools (
    id VARCHAR PRIMARY KEY,
    video_id VARCHAR REFERENCES public.play_tv_videos(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".play_tv_video_schools IS 'Vídeos do Play TV disponibilizados para escolas';

CREATE TABLE IF NOT EXISTS "{schema}".play_tv_video_classes (
    id VARCHAR PRIMARY KEY,
    video_id VARCHAR REFERENCES public.play_tv_videos(id),
    class_id UUID REFERENCES "{schema}".class(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".play_tv_video_classes IS 'Vídeos do Play TV disponibilizados para turmas';

CREATE TABLE IF NOT EXISTS "{schema}".plantao_schools (
    id VARCHAR PRIMARY KEY,
    plantao_id VARCHAR REFERENCES public.plantao_online(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".plantao_schools IS 'Plantões online disponibilizados para escolas';

CREATE TABLE IF NOT EXISTS "{schema}".certificate_templates (
    id VARCHAR PRIMARY KEY,
    evaluation_id VARCHAR REFERENCES "{schema}".test(id),
    title VARCHAR(255),
    text_content TEXT NOT NULL,
    background_color VARCHAR(7) NOT NULL,
    text_color VARCHAR(7) NOT NULL,
    accent_color VARCHAR(7) NOT NULL,
    logo_url VARCHAR(500),
    signature_url VARCHAR(500),
    custom_date VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_certificate_template_evaluation UNIQUE(evaluation_id)
);
COMMENT ON TABLE "{schema}".certificate_templates IS 'Templates de certificados';

CREATE TABLE IF NOT EXISTS "{schema}".certificates (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR REFERENCES "{schema}".student(id),
    student_name VARCHAR(200) NOT NULL,
    evaluation_id VARCHAR REFERENCES "{schema}".test(id),
    evaluation_title VARCHAR(200) NOT NULL,
    grade FLOAT NOT NULL,
    template_id VARCHAR REFERENCES "{schema}".certificate_templates(id),
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_certificate_student_evaluation UNIQUE(student_id, evaluation_id)
);
COMMENT ON TABLE "{schema}".certificates IS 'Certificados emitidos';

CREATE TABLE IF NOT EXISTS "{schema}".student_coins (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR REFERENCES "{schema}".student(id) NOT NULL UNIQUE,
    balance INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".student_coins IS 'Saldo de moedas dos alunos';

CREATE TABLE IF NOT EXISTS "{schema}".coin_transactions (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR REFERENCES "{schema}".student(id) NOT NULL,
    amount INTEGER NOT NULL,
    balance_before INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    reason VARCHAR NOT NULL,
    competition_id VARCHAR,
    test_session_id VARCHAR REFERENCES "{schema}".test_sessions(id) ON DELETE SET NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".coin_transactions IS 'Transações de moedas dos alunos';

-- Compras da loja: por tenant (student_id do schema). Catálogo store_items fica em public.
CREATE TABLE IF NOT EXISTS "{schema}".student_purchases (
    id VARCHAR PRIMARY KEY,
    student_id VARCHAR REFERENCES "{schema}".student(id) ON DELETE CASCADE NOT NULL,
    store_item_id VARCHAR REFERENCES public.store_items(id) ON DELETE CASCADE NOT NULL,
    price_paid INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".student_purchases IS 'Compras da loja por aluno';
CREATE INDEX IF NOT EXISTS idx_student_purchases_student_id ON "{schema}".student_purchases(student_id);
CREATE INDEX IF NOT EXISTS idx_student_purchases_store_item_id ON "{schema}".student_purchases(store_item_id);
CREATE INDEX IF NOT EXISTS idx_student_purchases_created_at ON "{schema}".student_purchases(created_at);

CREATE TABLE IF NOT EXISTS "{schema}".student_password_log (
    id VARCHAR PRIMARY KEY,
    student_name VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    password VARCHAR NOT NULL,
    registration VARCHAR(50),
    user_id VARCHAR REFERENCES public.users(id),
    student_id VARCHAR REFERENCES "{schema}".student(id),
    class_id UUID REFERENCES "{schema}".class(id),
    grade_id UUID REFERENCES public.grade(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    city_id VARCHAR REFERENCES public.city(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".student_password_log IS 'Log de senhas de alunos (auditoria)';
"""
