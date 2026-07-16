"""
Provisiona o schema PostgreSQL city_<id> e as tabelas operacionais ao criar um novo município.
Reutiliza a mesma estrutura da migração 0001_init_city_schemas.

Tabelas mobile (sync + offline pack) vêm de app.services.mobile.ddl.get_mobile_tables_ddl,
para que cada cidade nova já tenha o mesmo conjunto que scripts/create_mobile_tables.py
aplica nas city_* existentes.
"""
import logging
from app import db
from app.utils.tenant_middleware import city_id_to_schema_name
from app.services.mobile.ddl import get_mobile_tables_ddl
from app.afirme_ler.ddl import get_afirme_ler_evaluation_tables_ddl

logger = logging.getLogger(__name__)


def get_play_tv_tables_ddl(schema: str) -> str:
    """
    DDL idempotente das tabelas Play TV no schema city_xxx.
    Usado por provision_city_schema, provision_play_tv_for_city_schema e scripts de manutenção.
    """
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".play_tv_videos (
    id VARCHAR PRIMARY KEY,
    url VARCHAR NOT NULL,
    title VARCHAR(100),
    grade_id UUID NOT NULL REFERENCES public.grade(id),
    subject_id VARCHAR NOT NULL REFERENCES public.subject(id),
    created_by VARCHAR NOT NULL REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    entire_municipality BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS ix_play_tv_videos_grade_id ON "{schema}".play_tv_videos(grade_id);
CREATE INDEX IF NOT EXISTS ix_play_tv_videos_subject_id ON "{schema}".play_tv_videos(subject_id);
CREATE INDEX IF NOT EXISTS ix_play_tv_videos_created_by ON "{schema}".play_tv_videos(created_by);
COMMENT ON TABLE "{schema}".play_tv_videos IS 'Play TV: vídeos do município (schema tenant)';

CREATE TABLE IF NOT EXISTS "{schema}".play_tv_video_resources (
    id VARCHAR PRIMARY KEY,
    video_id VARCHAR NOT NULL REFERENCES "{schema}".play_tv_videos(id) ON DELETE CASCADE,
    resource_type VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    url VARCHAR(2000),
    minio_bucket VARCHAR(100),
    minio_object_name VARCHAR(500),
    original_filename VARCHAR(500),
    content_type VARCHAR(200),
    size_bytes BIGINT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_play_tv_resource_type CHECK (resource_type IN ('link', 'file'))
);
CREATE INDEX IF NOT EXISTS ix_play_tv_video_resources_video_id ON "{schema}".play_tv_video_resources(video_id);
COMMENT ON TABLE "{schema}".play_tv_video_resources IS 'Play TV: links e arquivos anexados ao vídeo';

CREATE TABLE IF NOT EXISTS "{schema}".play_tv_video_schools (
    id VARCHAR PRIMARY KEY,
    video_id VARCHAR NOT NULL REFERENCES "{schema}".play_tv_videos(id) ON DELETE CASCADE,
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".play_tv_video_schools IS 'Vídeos do Play TV disponibilizados para escolas';

CREATE TABLE IF NOT EXISTS "{schema}".play_tv_video_classes (
    id VARCHAR PRIMARY KEY,
    video_id VARCHAR NOT NULL REFERENCES "{schema}".play_tv_videos(id) ON DELETE CASCADE,
    class_id UUID REFERENCES "{schema}".class(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".play_tv_video_classes IS 'Vídeos do Play TV disponibilizados para turmas';
"""


def get_plantao_online_tables_ddl(schema: str) -> str:
    """
    DDL idempotente das tabelas Plantão Online no schema city_xxx.

    Cria a tabela tenant ``plantao_online`` (antes só existia em ``public``) e a tabela de
    junção ``plantao_schools`` com FK apontando para a versão local de ``plantao_online``.
    Usado por provision_city_schema, provision_plantao_online_for_city_schema e o script
    de migração public→tenant.
    """
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".plantao_online (
    id VARCHAR PRIMARY KEY,
    link TEXT NOT NULL,
    title TEXT,
    grade_id UUID NOT NULL REFERENCES public.grade(id),
    subject_id VARCHAR NOT NULL REFERENCES public.subject(id),
    created_by VARCHAR NOT NULL REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_plantao_online_grade_id ON "{schema}".plantao_online(grade_id);
CREATE INDEX IF NOT EXISTS ix_plantao_online_subject_id ON "{schema}".plantao_online(subject_id);
CREATE INDEX IF NOT EXISTS ix_plantao_online_created_by ON "{schema}".plantao_online(created_by);
COMMENT ON TABLE "{schema}".plantao_online IS 'Plantão Online: plantões do município (schema tenant)';

CREATE TABLE IF NOT EXISTS "{schema}".plantao_schools (
    id VARCHAR PRIMARY KEY,
    plantao_id VARCHAR NOT NULL REFERENCES "{schema}".plantao_online(id) ON DELETE CASCADE,
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_plantao_school UNIQUE(plantao_id, school_id)
);
CREATE INDEX IF NOT EXISTS ix_plantao_schools_plantao_id ON "{schema}".plantao_schools(plantao_id);
CREATE INDEX IF NOT EXISTS ix_plantao_schools_school_id ON "{schema}".plantao_schools(school_id);
COMMENT ON TABLE "{schema}".plantao_schools IS 'Plantões online disponibilizados para escolas';
"""


def get_ideb_meta_tables_ddl(schema: str) -> str:
    """
    DDL idempotente da Calculadora de Metas IDEB no schema city_xxx.

    Nota: a tabela referencia public.city (cross-schema) para identificar o município
    do contexto salvo. Uma linha por (city_id, level).
    """
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".ideb_meta_saves (
    id VARCHAR PRIMARY KEY,
    city_id VARCHAR NOT NULL REFERENCES public.city(id) ON DELETE CASCADE,
    level VARCHAR(100) NOT NULL,
    payload JSON NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ideb_meta_saves_context UNIQUE(city_id, level)
);
CREATE INDEX IF NOT EXISTS idx_ideb_meta_saves_context ON "{schema}".ideb_meta_saves(city_id, level);
COMMENT ON TABLE "{schema}".ideb_meta_saves IS 'Calculadora IDEB: payload salvo por (city_id, level) no schema do município';
"""


def get_monitoring_tables_ddl(schema: str) -> str:
    """DDL idempotente de ações de monitoramento no schema city_xxx."""
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".monitoring_action (
    id VARCHAR NOT NULL PRIMARY KEY,
    source_type VARCHAR(30) NOT NULL,
    source_id VARCHAR NOT NULL,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    class_id UUID REFERENCES "{schema}".class(id),
    grade_id UUID REFERENCES public.grade(id),
    discipline VARCHAR(120),
    coordinator_id VARCHAR REFERENCES public.users(id),
    pedagogical_action TEXT,
    responsible_id VARCHAR REFERENCES public.users(id),
    responsible_name VARCHAR(255),
    deadline DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'pendente',
    completed_at DATE,
    done_by_school BOOLEAN NOT NULL DEFAULT FALSE,
    seen_by_semed BOOLEAN NOT NULL DEFAULT FALSE,
    note TEXT,
    created_by VARCHAR REFERENCES public.users(id),
    updated_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_monitoring_action_source_student
    ON "{schema}".monitoring_action (source_type, source_id, student_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_action_school_status
    ON "{schema}".monitoring_action (school_id, status);

CREATE TABLE IF NOT EXISTS "{schema}".monitoring_action_history (
    id VARCHAR NOT NULL PRIMARY KEY,
    monitoring_action_id VARCHAR NOT NULL
        REFERENCES "{schema}".monitoring_action(id),
    changed_by VARCHAR REFERENCES public.users(id),
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    changed_fields JSON,
    old_values JSON,
    new_values JSON,
    note TEXT
);
CREATE INDEX IF NOT EXISTS idx_monitoring_action_history_action_changed_at
    ON "{schema}".monitoring_action_history (monitoring_action_id, changed_at);
COMMENT ON TABLE "{schema}".monitoring_action IS 'Ações pedagógicas de monitoramento (avaliação/cartão resposta)';
COMMENT ON TABLE "{schema}".monitoring_action_history IS 'Histórico de alterações em monitoring_action';
"""


def get_monitoring_action_column_migrations_ddl(schema: str) -> str:
    """ALTER idempotente para colunas adicionadas após a criação inicial."""
    return f"""
ALTER TABLE "{schema}".monitoring_action
    ADD COLUMN IF NOT EXISTS responsible_name VARCHAR(255);
"""


def ensure_monitoring_action_columns(schema: str) -> None:
    """Garante colunas novas em monitoring_action (idempotente)."""
    import re

    from sqlalchemy import text

    from app import db

    if not schema or not re.match(r"^city_[a-zA-Z0-9_]+$", schema):
        return
    db.session.execute(text(get_monitoring_action_column_migrations_ddl(schema)))
    db.session.commit()


def get_class_shift_column_migrations_ddl(schema: str) -> str:
    """DDL idempotente: coluna shift em class (morning, afternoon, full-time, etc.)."""
    return f"""
DO $mig$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = 'class' AND column_name = 'turno'
    ) AND NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = 'class' AND column_name = 'shift'
    ) THEN
        ALTER TABLE "{schema}".class RENAME COLUMN turno TO shift;
    ELSIF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = 'class' AND column_name = 'shift'
    ) THEN
        ALTER TABLE "{schema}".class ADD COLUMN shift VARCHAR(50);
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = 'class' AND column_name = 'turno'
    ) AND EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = '{schema}' AND table_name = 'class' AND column_name = 'shift'
    ) THEN
        UPDATE "{schema}".class SET shift = turno WHERE shift IS NULL AND turno IS NOT NULL;
        ALTER TABLE "{schema}".class DROP COLUMN turno;
    END IF;
END $mig$;
"""


def ensure_class_shift_column(schema: str) -> None:
    """Garante coluna shift em class no schema do município (idempotente)."""
    import re

    from sqlalchemy import text

    from app import db

    if not schema or not re.match(r"^city_[a-zA-Z0-9_]+$", schema):
        return
    db.session.execute(text(get_class_shift_column_migrations_ddl(schema)))
    db.session.commit()


def get_saved_ata_sala_tables_ddl(schema: str) -> str:
    """DDL idempotente de atas de sala salvas no schema city_xxx."""
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".saved_ata_sala (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL REFERENCES public.users(id),
    created_by_name VARCHAR(255) NOT NULL,
    city_id VARCHAR NOT NULL,
    school_id VARCHAR(36) NOT NULL REFERENCES "{schema}".school(id),
    title VARCHAR(255) NOT NULL,
    modo_lista VARCHAR(30) NOT NULL,
    filters JSON NOT NULL,
    content JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_saved_ata_sala_user_id ON "{schema}".saved_ata_sala(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_ata_sala_school_updated ON "{schema}".saved_ata_sala(school_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_saved_ata_sala_city_updated ON "{schema}".saved_ata_sala(city_id, updated_at);
COMMENT ON TABLE "{schema}".saved_ata_sala IS 'Atas de sala salvas por usuário (visibilidade por escola/município)';
"""


def provision_afirme_ler_for_city_schema(schema_name: str) -> None:
    """Aplica DDL de avaliações Afirme Ler em um schema city_* existente (idempotente)."""
    if not schema_name.replace("_", "").isalnum() or not schema_name.startswith("city_"):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    raw_conn = db.engine.raw_connection()
    try:
        raw_conn.set_isolation_level(0)
        cursor = raw_conn.cursor()
        cursor.execute(get_afirme_ler_evaluation_tables_ddl(schema_name))
        logger.info("Afirme Ler evaluation DDL aplicado em schema %s", schema_name)
    except Exception as e:
        logger.exception("Falha ao aplicar Afirme Ler em %s: %s", schema_name, e)
        raise
    finally:
        raw_conn.close()


def provision_plantao_online_for_city_schema(schema_name: str) -> None:
    """
    Aplica apenas o bloco DDL Plantão Online em um schema city_* já existente (idempotente).
    Não altera public. Para realinhar FKs legadas que referenciam public.plantao_online,
    use migrate_plantao_online_from_public_to_city_schema após copiar os dados necessários.
    """
    if not schema_name.replace("_", "").isalnum() or not schema_name.startswith("city_"):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    raw_conn = db.engine.raw_connection()
    try:
        raw_conn.set_isolation_level(0)
        cursor = raw_conn.cursor()
        cursor.execute(get_plantao_online_tables_ddl(schema_name))
        logger.info("Plantão Online DDL aplicado em schema %s", schema_name)
    except Exception as e:
        logger.exception("Falha ao aplicar Plantão Online em %s: %s", schema_name, e)
        raise
    finally:
        raw_conn.close()


def _plantao_online_table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


def _plantao_online_drop_public_fks(cursor, schema: str, table: str) -> int:
    cursor.execute(
        """
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN pg_class ref ON ref.oid = c.confrelid
        JOIN pg_namespace rn ON rn.oid = ref.relnamespace
        WHERE n.nspname = %s AND rel.relname = %s
          AND c.contype = 'f'
          AND ref.relname = 'plantao_online'
          AND rn.nspname = 'public'
        """,
        (schema, table),
    )
    names = [row[0] for row in cursor.fetchall()]
    for conname in names:
        cursor.execute(
            f'ALTER TABLE "{schema}"."{table}" DROP CONSTRAINT IF EXISTS "{conname}"'
        )
    return len(names)


def _plantao_online_has_fk_to_public(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN pg_class ref ON ref.oid = c.confrelid
        JOIN pg_namespace rn ON rn.oid = ref.relnamespace
        WHERE n.nspname = %s AND rel.relname = %s
          AND c.contype = 'f' AND ref.relname = 'plantao_online'
          AND rn.nspname = 'public'
        LIMIT 1
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


def _backfill_plantao_online_from_public(cursor, schema_name: str) -> int:
    """
    Insere em {schema}.plantao_online as linhas de public.plantao_online cujo id
    aparece em {schema}.plantao_schools e ainda não existe localmente.
    """
    if not _plantao_online_table_exists(cursor, schema_name, "plantao_schools"):
        return 0

    insert_sql = f"""
        INSERT INTO "{schema_name}".plantao_online (
            id, link, title, grade_id, subject_id, created_by, created_at
        )
        SELECT p.id, p.link, p.title, p.grade_id, p.subject_id, p.created_by, p.created_at
        FROM public.plantao_online p
        WHERE p.id IN (
            SELECT plantao_id FROM "{schema_name}".plantao_schools WHERE plantao_id IS NOT NULL
        )
        ON CONFLICT (id) DO NOTHING
    """
    cursor.execute(insert_sql)
    return cursor.rowcount


def migrate_plantao_online_from_public_to_city_schema(schema_name: str) -> dict:
    """
    Copia plantões referenciados de public.plantao_online para city_xxx.plantao_online
    (backfill) e, se a junção plantao_schools ainda tiver FK para public.plantao_online,
    remove essa FK e recria apontando para o schema do tenant.

    Idempotente: pode ser executado várias vezes; linhas já presentes em plantao_online
    local são ignoradas (ON CONFLICT DO NOTHING).
    """
    if not schema_name.replace("_", "").isalnum() or not schema_name.startswith("city_"):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    summary = {
        "schema": schema_name,
        "fks_dropped": 0,
        "plantoes_copied": 0,
        "fks_recreated": 0,
        "skipped": False,
    }

    raw_conn = db.engine.raw_connection()
    try:
        raw_conn.set_isolation_level(0)
        cursor = raw_conn.cursor()

        if not _plantao_online_table_exists(cursor, "public", "plantao_online"):
            summary["skipped"] = True
            summary["note"] = "public.plantao_online inexistente"
            return summary

        if not _plantao_online_table_exists(cursor, schema_name, "plantao_online"):
            summary["skipped"] = True
            summary["note"] = "plantao_online local inexistente (rode provision antes)"
            return summary

        if not _plantao_online_table_exists(cursor, schema_name, "plantao_schools"):
            summary["skipped"] = True
            summary["note"] = "Sem tabela plantao_schools neste schema"
            return summary

        summary["plantoes_copied"] = _backfill_plantao_online_from_public(cursor, schema_name)

        refs_public = _plantao_online_has_fk_to_public(cursor, schema_name, "plantao_schools")

        if not refs_public:
            summary["note"] = (
                "FK já referencia plantao_online local; backfill aplicado se necessário"
            )
            logger.info("Plantão Online migrate %s: %s", schema_name, summary)
            return summary

        dropped = _plantao_online_drop_public_fks(cursor, schema_name, "plantao_schools")
        summary["fks_dropped"] = dropped
        if dropped == 0:
            raise RuntimeError(
                f"Detectada FK para public.plantao_online em {schema_name}.plantao_schools "
                "mas nenhuma constraint foi removida"
            )

        try:
            cursor.execute(
                f"""
                ALTER TABLE "{schema_name}"."plantao_schools"
                ADD CONSTRAINT plantao_schools_plantao_id_fkey
                FOREIGN KEY (plantao_id)
                REFERENCES "{schema_name}".plantao_online(id)
                ON DELETE CASCADE
                """
            )
            summary["fks_recreated"] += 1
        except Exception as ex:
            err = str(ex).lower()
            if "already exists" in err or "duplicate" in err:
                logger.info(
                    "Constraint plantao_schools_plantao_id_fkey já existe em %s",
                    schema_name,
                )
            else:
                raise

        summary["note"] = "FK realinhada para plantao_online do schema tenant"
        logger.info("Plantão Online migrado public→%s: %s", schema_name, summary)
        return summary
    except Exception as e:
        logger.exception("migrate_plantao_online_from_public %s: %s", schema_name, e)
        raise
    finally:
        raw_conn.close()


def get_subjective_evaluation_tables_ddl(schema: str) -> str:
    """
    DDL idempotente das tabelas da avaliação subjetiva no schema city_xxx.

    Avaliação subjetiva é uma entidade própria (subjective_tests), separada de
    test/question: a prova em si é física/impressa e fica fora do sistema — só a
    estrutura é cadastrada (subjective_questions: número, código e habilidade digitada
    livremente, por questão). A correção é sempre manual, célula a célula (aluno x
    questão), com a rubrica SIM/PARCIAL/NAO/BRANCO (subjective_results).
    subjective_presences: presença do aluno na aplicação da avaliação.

    `subjective_tests.shadow_test_id` referencia um registro-espelho em "{schema}".test
    (evaluation_mode='subjective'), criado internamente só para reaproveitar o pipeline
    de evaluation_results/relatórios já existente — não é exposto/editado pelo frontend.
    """
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".subjective_tests (
    id VARCHAR PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description VARCHAR(500),
    test_type VARCHAR(50) DEFAULT 'Diagnóstica',
    subject_id VARCHAR NOT NULL REFERENCES public.subject(id),
    grade_id UUID NOT NULL REFERENCES public.grade(id),
    application_date DATE,
    municipalities JSON,
    schools JSON,
    classes JSON,
    status VARCHAR(20) DEFAULT 'pendente',
    created_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    shadow_test_id VARCHAR REFERENCES "{schema}".test(id)
);
CREATE INDEX IF NOT EXISTS idx_subjective_tests_created_by ON "{schema}".subjective_tests(created_by);
COMMENT ON TABLE "{schema}".subjective_tests IS 'Avaliação subjetiva (cartão-resposta manual): só a estrutura é cadastrada, a prova física fica fora do sistema';

CREATE TABLE IF NOT EXISTS "{schema}".subjective_questions (
    id VARCHAR PRIMARY KEY,
    subjective_test_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_tests(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    code VARCHAR(50),
    skill_description VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_question_test_number UNIQUE(subjective_test_id, number)
);
CREATE INDEX IF NOT EXISTS idx_subjective_questions_test_id ON "{schema}".subjective_questions(subjective_test_id);
COMMENT ON TABLE "{schema}".subjective_questions IS 'Estrutura da questão da avaliação subjetiva: número, código e habilidade digitada livremente';

CREATE TABLE IF NOT EXISTS "{schema}".subjective_results (
    id VARCHAR PRIMARY KEY,
    subjective_test_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_tests(id) ON DELETE CASCADE,
    subjective_question_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_questions(id) ON DELETE CASCADE,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    value VARCHAR(10) NOT NULL,
    corrected_by VARCHAR REFERENCES public.users(id),
    corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_result_test_question_student UNIQUE(subjective_test_id, subjective_question_id, student_id),
    CONSTRAINT ck_subjective_result_value CHECK (value IN ('SIM', 'PARCIAL', 'NAO', 'BRANCO'))
);
CREATE INDEX IF NOT EXISTS idx_subjective_results_test_id ON "{schema}".subjective_results(subjective_test_id);
CREATE INDEX IF NOT EXISTS idx_subjective_results_student_id ON "{schema}".subjective_results(student_id);
COMMENT ON TABLE "{schema}".subjective_results IS 'Rubrica de correção manual (SIM/PARCIAL/NAO/BRANCO) da avaliação subjetiva';

CREATE TABLE IF NOT EXISTS "{schema}".subjective_presences (
    id VARCHAR PRIMARY KEY,
    subjective_test_id VARCHAR NOT NULL REFERENCES "{schema}".subjective_tests(id) ON DELETE CASCADE,
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id),
    present BOOLEAN NOT NULL DEFAULT true,
    updated_by VARCHAR REFERENCES public.users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subjective_presence_test_student UNIQUE(subjective_test_id, student_id)
);
CREATE INDEX IF NOT EXISTS idx_subjective_presences_test_id ON "{schema}".subjective_presences(subjective_test_id);
COMMENT ON TABLE "{schema}".subjective_presences IS 'Presença do aluno na aplicação da avaliação subjetiva';
"""


def provision_subjective_evaluation_for_city_schema(schema_name: str) -> None:
    """Aplica apenas o bloco DDL da avaliação subjetiva em um schema city_* existente (idempotente)."""
    if not schema_name.replace("_", "").isalnum() or not schema_name.startswith("city_"):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    raw_conn = db.engine.raw_connection()
    try:
        raw_conn.set_isolation_level(0)
        cursor = raw_conn.cursor()
        cursor.execute(get_subjective_evaluation_tables_ddl(schema_name))
        logger.info("Avaliação subjetiva DDL aplicado em schema %s", schema_name)
    except Exception as e:
        logger.exception("Falha ao aplicar avaliação subjetiva em %s: %s", schema_name, e)
        raise
    finally:
        raw_conn.close()


def get_calendar_tables_ddl(schema: str) -> str:
    """DDL idempotente para estruturas do Calendar em schemas city_*."""
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".calendar_event_resources (
    id VARCHAR PRIMARY KEY,
    event_id VARCHAR REFERENCES "{schema}".calendar_events(id) ON DELETE CASCADE,
    resource_type VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    url VARCHAR(2000),
    minio_bucket VARCHAR(100),
    minio_object_name VARCHAR(500),
    original_filename VARCHAR(500),
    content_type VARCHAR(200),
    size_bytes BIGINT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_calendar_event_resource_type CHECK (resource_type IN ('link', 'file'))
);
CREATE INDEX IF NOT EXISTS ix_calendar_event_resources_event_id ON "{schema}".calendar_event_resources(event_id);

ALTER TABLE "{schema}".calendar_event_targets
    ADD COLUMN IF NOT EXISTS target_filters JSON;

DO $$
BEGIN
    BEGIN
        ALTER TABLE "{schema}".calendar_event_targets
            ALTER COLUMN target_id DROP NOT NULL;
    EXCEPTION WHEN others THEN
        NULL;
    END;
END $$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = '{schema}'
          AND table_name = 'calendar_event_targets'
          AND column_name = 'target_type'
    ) THEN
        -- Permite ALL sem impor enum para compatibilidade entre ambientes.
        -- Mantemos como VARCHAR e dados validados na aplicação.
        NULL;
    END IF;
END $$;
"""


def provision_calendar_for_city_schema(schema_name: str) -> None:
    """Aplica somente DDL do Calendar em um schema city_* existente (idempotente)."""
    if not schema_name.replace("_", "").isalnum() or not schema_name.startswith("city_"):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    raw_conn = db.engine.raw_connection()
    try:
        raw_conn.set_isolation_level(0)
        cursor = raw_conn.cursor()
        cursor.execute(get_calendar_tables_ddl(schema_name))
        logger.info("Calendar DDL aplicado em schema %s", schema_name)
    except Exception as e:
        logger.exception("Falha ao aplicar Calendar em %s: %s", schema_name, e)
        raise
    finally:
        raw_conn.close()


def provision_play_tv_for_city_schema(schema_name: str) -> None:
    """
    Aplica apenas o bloco DDL Play TV em um schema city_* já existente (idempotente).
    Não altera public. Para realinhar FKs legadas de public.play_tv_videos, use
    migrate_play_tv_fk_from_public_to_schema após copiar os dados necessários.
    """
    if not schema_name.replace("_", "").isalnum() or not schema_name.startswith("city_"):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    raw_conn = db.engine.raw_connection()
    try:
        raw_conn.set_isolation_level(0)
        cursor = raw_conn.cursor()
        cursor.execute(get_play_tv_tables_ddl(schema_name))
        logger.info("Play TV DDL aplicado em schema %s", schema_name)
    except Exception as e:
        logger.exception("Falha ao aplicar Play TV em %s: %s", schema_name, e)
        raise
    finally:
        raw_conn.close()


def _play_tv_table_exists(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


def _play_tv_drop_public_video_fks(cursor, schema: str, table: str) -> int:
    cursor.execute(
        """
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN pg_class ref ON ref.oid = c.confrelid
        JOIN pg_namespace rn ON rn.oid = ref.relnamespace
        WHERE n.nspname = %s AND rel.relname = %s
          AND c.contype = 'f'
          AND ref.relname = 'play_tv_videos'
          AND rn.nspname = 'public'
        """,
        (schema, table),
    )
    names = [row[0] for row in cursor.fetchall()]
    for conname in names:
        cursor.execute(
            f'ALTER TABLE "{schema}"."{table}" DROP CONSTRAINT IF EXISTS "{conname}"'
        )
    return len(names)


def _play_tv_has_fk_to_public_videos(cursor, schema: str, table: str) -> bool:
    cursor.execute(
        """
        SELECT 1 FROM pg_constraint c
        JOIN pg_class rel ON rel.oid = c.conrelid
        JOIN pg_namespace n ON n.oid = rel.relnamespace
        JOIN pg_class ref ON ref.oid = c.confrelid
        JOIN pg_namespace rn ON rn.oid = ref.relnamespace
        WHERE n.nspname = %s AND rel.relname = %s
          AND c.contype = 'f' AND ref.relname = 'play_tv_videos'
          AND rn.nspname = 'public'
        LIMIT 1
        """,
        (schema, table),
    )
    return cursor.fetchone() is not None


def _backfill_play_tv_videos_from_public(cursor, schema_name: str) -> int:
    """
    Insere em {schema}.play_tv_videos as linhas de public.play_tv_videos cujo id aparece
    em junções/recursos do tenant e ainda não existe localmente.
    """
    parts = []
    for tbl in ("play_tv_video_schools", "play_tv_video_classes", "play_tv_video_resources"):
        if _play_tv_table_exists(cursor, schema_name, tbl):
            parts.append(
                f'SELECT video_id FROM "{schema_name}"."{tbl}" WHERE video_id IS NOT NULL'
            )
    if not parts:
        return 0

    vid_union = " UNION ".join(parts)

    cursor.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'play_tv_videos'
          AND column_name = 'entire_municipality'
        """
    )
    has_em = cursor.fetchone() is not None
    em_expr = "COALESCE(v.entire_municipality, false)" if has_em else "false"

    insert_sql = f"""
        INSERT INTO "{schema_name}".play_tv_videos (
            id, url, title, grade_id, subject_id, created_by,
            created_at, updated_at, entire_municipality
        )
        SELECT v.id, v.url, v.title, v.grade_id, v.subject_id, v.created_by,
               v.created_at, v.updated_at, {em_expr}
        FROM public.play_tv_videos v
        WHERE v.id IN ({vid_union})
        ON CONFLICT (id) DO NOTHING
    """
    cursor.execute(insert_sql)
    return cursor.rowcount


def migrate_play_tv_from_public_to_city_schema(schema_name: str) -> dict:
    """
    Copia vídeos referenciados de public.play_tv_videos para city_xxx.play_tv_videos
    (backfill) e, se junções ainda tiverem FK para public.play_tv_videos, remove essas FKs
    e recria apontando para o schema do tenant.

    Idempotente: pode ser executado várias vezes; linhas já presentes em play_tv_videos
    local são ignoradas (ON CONFLICT DO NOTHING).
    """
    if not schema_name.replace("_", "").isalnum() or not schema_name.startswith("city_"):
        raise ValueError(f"Nome de schema inválido: {schema_name}")

    summary = {
        "schema": schema_name,
        "fks_dropped": 0,
        "videos_copied": 0,
        "fks_recreated": 0,
        "skipped": False,
    }

    raw_conn = db.engine.raw_connection()
    try:
        raw_conn.set_isolation_level(0)
        cursor = raw_conn.cursor()

        if not _play_tv_table_exists(cursor, "public", "play_tv_videos"):
            summary["skipped"] = True
            summary["note"] = "public.play_tv_videos inexistente"
            return summary

        if not _play_tv_table_exists(cursor, schema_name, "play_tv_videos"):
            summary["skipped"] = True
            summary["note"] = "play_tv_videos local inexistente (rode provision antes)"
            return summary

        junction_tables = (
            "play_tv_video_schools",
            "play_tv_video_classes",
            "play_tv_video_resources",
        )
        if not any(
            _play_tv_table_exists(cursor, schema_name, t) for t in junction_tables
        ):
            summary["skipped"] = True
            summary["note"] = "Sem tabelas de junção/recursos Play TV neste schema"
            return summary

        try:
            cursor.execute(
                """
                DO $$ BEGIN
                    ALTER TABLE public.play_tv_videos
                    ADD COLUMN entire_municipality BOOLEAN NOT NULL DEFAULT false;
                EXCEPTION
                    WHEN duplicate_column THEN NULL;
                END $$;
                """
            )
        except Exception:
            logger.debug("Coluna entire_municipality em public.play_tv_videos já existe ou erro ignorado")

        summary["videos_copied"] = _backfill_play_tv_videos_from_public(cursor, schema_name)

        refs_public = False
        for tbl in ("play_tv_video_schools", "play_tv_video_classes", "play_tv_video_resources"):
            if _play_tv_table_exists(cursor, schema_name, tbl) and _play_tv_has_fk_to_public_videos(
                cursor, schema_name, tbl
            ):
                refs_public = True
                break

        if not refs_public:
            summary["note"] = (
                "FKs já referenciam play_tv_videos local; backfill de vídeos aplicado se necessário"
            )
            logger.info("Play TV migrate %s: %s", schema_name, summary)
            return summary

        dropped = 0
        for tbl in ("play_tv_video_schools", "play_tv_video_classes", "play_tv_video_resources"):
            if _play_tv_table_exists(cursor, schema_name, tbl):
                dropped += _play_tv_drop_public_video_fks(cursor, schema_name, tbl)
        summary["fks_dropped"] = dropped
        if dropped == 0:
            raise RuntimeError(
                f"Detectada FK para public.play_tv_videos em {schema_name} "
                "mas nenhuma constraint foi removida"
            )

        for tbl in ("play_tv_video_schools", "play_tv_video_classes", "play_tv_video_resources"):
            if not _play_tv_table_exists(cursor, schema_name, tbl):
                continue
            try:
                cursor.execute(
                    f"""
                    ALTER TABLE "{schema_name}"."{tbl}"
                    ADD CONSTRAINT {tbl}_video_id_fkey
                    FOREIGN KEY (video_id)
                    REFERENCES "{schema_name}".play_tv_videos(id)
                    ON DELETE CASCADE
                    """
                )
                summary["fks_recreated"] += 1
            except Exception as ex:
                err = str(ex).lower()
                if "already exists" in err or "duplicate" in err:
                    logger.info("Constraint %s_video_id_fkey já existe em %s", tbl, schema_name)
                else:
                    raise

        summary["note"] = "FKs realinhadas para play_tv_videos do schema tenant"
        logger.info("Play TV migrado public→%s: %s", schema_name, summary)
        return summary
    except Exception as e:
        logger.exception("migrate_play_tv_from_public %s: %s", schema_name, e)
        raise
    finally:
        raw_conn.close()


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
        cursor.execute(get_class_shift_column_migrations_ddl(schema_name))

        mobile_ddl = get_mobile_tables_ddl(schema_name)
        cursor.execute(mobile_ddl)

        logger.info("Schema e tabelas criados para cidade %s (%s)", city_id, schema_name)
    except Exception as e:
        logger.exception("Falha ao provisionar schema para cidade %s: %s", city_id, e)
        raise
    finally:
        if raw_conn:
            raw_conn.close()


def _get_city_tables_ddl(schema: str) -> str:
    """Retorna o SQL de criação das tabelas do schema city (mesmo conteúdo da migração 0001)."""
    play_tv_block = get_play_tv_tables_ddl(schema)
    plantao_online_block = get_plantao_online_tables_ddl(schema)
    ideb_meta_block = get_ideb_meta_tables_ddl(schema)
    monitoring_block = get_monitoring_tables_ddl(schema)
    saved_ata_block = get_saved_ata_sala_tables_ddl(schema)
    afirme_ler_block = get_afirme_ler_evaluation_tables_ddl(schema)
    subjective_evaluation_block = get_subjective_evaluation_tables_ddl(schema)
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
    grade_id UUID REFERENCES public.grade(id),
    shift VARCHAR(50)
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

CREATE TABLE IF NOT EXISTS "{schema}".student_school_enrollment (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4()::text),
    student_id VARCHAR NOT NULL REFERENCES "{schema}".student(id) ON DELETE CASCADE,
    school_id VARCHAR(36) REFERENCES "{schema}".school(id),
    class_id UUID REFERENCES "{schema}".class(id),
    valid_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_student_school_enrollment_valid_range
        CHECK (valid_to IS NULL OR valid_to >= valid_from)
);
COMMENT ON TABLE "{schema}".student_school_enrollment IS 'Histórico de vínculo aluno–escola–turma (matrícula). valid_to IS NULL indica período vigente.';

CREATE UNIQUE INDEX IF NOT EXISTS uq_student_school_enrollment_one_active
    ON "{schema}".student_school_enrollment (student_id)
    WHERE valid_to IS NULL;

CREATE INDEX IF NOT EXISTS idx_student_school_enrollment_student_hist
    ON "{schema}".student_school_enrollment (student_id, valid_from DESC);

CREATE INDEX IF NOT EXISTS idx_student_school_enrollment_school
    ON "{schema}".student_school_enrollment (school_id)
    WHERE school_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_student_school_enrollment_class
    ON "{schema}".student_school_enrollment (class_id)
    WHERE class_id IS NOT NULL;

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
    subject_results JSONB,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    school_id_snapshot VARCHAR(36),
    class_id_snapshot UUID,
    grade_id_snapshot UUID,
    enrollment_id_snapshot VARCHAR(36)
);
COMMENT ON TABLE "{schema}".evaluation_results IS 'Resultados de avaliações';
COMMENT ON COLUMN "{schema}".evaluation_results.school_id_snapshot IS 'Escola no momento da participação (imutável após preenchido).';
COMMENT ON COLUMN "{schema}".evaluation_results.class_id_snapshot IS 'Turma no momento da participação (imutável após preenchido).';
COMMENT ON COLUMN "{schema}".evaluation_results.grade_id_snapshot IS 'Série no momento da participação (imutável após preenchido).';
COMMENT ON COLUMN "{schema}".evaluation_results.enrollment_id_snapshot IS 'Matrícula vigente (student_school_enrollment) no momento do resultado.';

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

CREATE TABLE IF NOT EXISTS "{schema}".physical_test_zip (
    test_id VARCHAR PRIMARY KEY REFERENCES "{schema}".test(id),
    minio_url VARCHAR(500),
    minio_object_name VARCHAR(200),
    minio_bucket VARCHAR(100),
    zip_generated_at TIMESTAMP
);
COMMENT ON TABLE "{schema}".physical_test_zip IS 'URL do ZIP de provas físicas (download all) por prova';

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
    last_generation_classes_count INTEGER,
    last_generation_students_count INTEGER,
    batch_id VARCHAR(36),
    last_generation_job_id VARCHAR(36)
);
COMMENT ON TABLE "{schema}".answer_sheet_gabaritos IS 'Gabaritos de cartões resposta';

CREATE TABLE IF NOT EXISTS "{schema}".answer_sheet_generations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gabarito_id VARCHAR NOT NULL REFERENCES "{schema}".answer_sheet_gabaritos(id) ON DELETE CASCADE,
    job_id VARCHAR(36) NOT NULL,
    scope_type VARCHAR(50),
    scope_snapshot JSONB,
    minio_url VARCHAR(500),
    minio_object_name VARCHAR(500),
    minio_bucket VARCHAR(100),
    zip_generated_at TIMESTAMP,
    total_classes INTEGER,
    total_students INTEGER,
    status VARCHAR(30) NOT NULL DEFAULT 'completed',
    created_by VARCHAR REFERENCES public.users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".answer_sheet_generations IS 'Histórico de gerações de ZIP por gabarito (escopos distintos)';
CREATE INDEX IF NOT EXISTS idx_as_gen_gabarito ON "{schema}".answer_sheet_generations(gabarito_id);
CREATE INDEX IF NOT EXISTS idx_as_gen_job ON "{schema}".answer_sheet_generations(job_id);

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
    proficiency_by_subject JSON,
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

CREATE TABLE IF NOT EXISTS "{schema}".answer_sheet_report_aggregates (
    id VARCHAR PRIMARY KEY,
    gabarito_id VARCHAR NOT NULL REFERENCES "{schema}".answer_sheet_gabaritos(id) ON DELETE CASCADE,
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
    CONSTRAINT uq_answer_sheet_report_aggregate_scope UNIQUE(gabarito_id, scope_type, scope_id)
);
COMMENT ON TABLE "{schema}".answer_sheet_report_aggregates IS 'Cache de relatórios agregados para cartão-resposta';
CREATE INDEX IF NOT EXISTS idx_as_report_agg_gabarito ON "{schema}".answer_sheet_report_aggregates(gabarito_id);
CREATE INDEX IF NOT EXISTS idx_as_report_agg_scope ON "{schema}".answer_sheet_report_aggregates(scope_type, scope_id);

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
    target_id VARCHAR,
    target_filters JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE "{schema}".calendar_event_targets IS 'Alvos de eventos de calendário';

CREATE TABLE IF NOT EXISTS "{schema}".calendar_event_resources (
    id VARCHAR PRIMARY KEY,
    event_id VARCHAR REFERENCES "{schema}".calendar_events(id) ON DELETE CASCADE,
    resource_type VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    url VARCHAR(2000),
    minio_bucket VARCHAR(100),
    minio_object_name VARCHAR(500),
    original_filename VARCHAR(500),
    content_type VARCHAR(200),
    size_bytes BIGINT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_calendar_event_resource_type CHECK (resource_type IN ('link', 'file'))
);
CREATE INDEX IF NOT EXISTS ix_calendar_event_resources_event_id ON "{schema}".calendar_event_resources(event_id);
COMMENT ON TABLE "{schema}".calendar_event_resources IS 'Links e arquivos anexados a eventos do calendário';

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
    edition_number INTEGER,
    edition_series VARCHAR,
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
""" + play_tv_block + plantao_online_block + ideb_meta_block + monitoring_block + saved_ata_block + afirme_ler_block + subjective_evaluation_block + f"""
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
