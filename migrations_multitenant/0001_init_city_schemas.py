"""
Migration 0001: Inicialização de Schemas Multi-Tenant por Município

Este script cria a estrutura base para arquitetura multi-tenant:
- Schemas city_<city_id> para cada município
- Tabelas operacionais em cada schema CITY
- Ajustes em public.questions para suportar escopo
- Tabela intermediária school_managers

⚠️ IMPORTANTE:
- Script é IDEMPOTENTE (pode rodar múltiplas vezes)
- NÃO remove dados existentes
- NÃO altera tabelas do schema public (exceto questions)
- Apenas cria estrutura, não migra dados ainda
"""

import os
import sys
import logging
from datetime import datetime
from typing import List, Dict
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Configurar logging com UTF-8 para Windows
log_filename = f'migration_0001_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configurar stdout para UTF-8 no Windows
if sys.platform == 'win32':
    import codecs
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

# Carregar variáveis de ambiente
# Tentar múltiplos caminhos possíveis para .env
possible_env_paths = [
    'app/.env',
    '../app/.env',
    os.path.join(os.path.dirname(__file__), '..', 'app', '.env')
]

for env_path in possible_env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        break

DATABASE_URL = os.getenv('DATABASE_URL')


class MultiTenantMigration:
    """Gerenciador de migração multi-tenant"""
    
    def __init__(self, database_url: str, dry_run: bool = False):
        self.database_url = database_url
        self.dry_run = dry_run
        self.conn = None
        self.cursor = None
        
    def __enter__(self):
        """Context manager - conectar ao banco"""
        self.conn = psycopg2.connect(self.database_url)
        self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        self.cursor = self.conn.cursor()
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Conectado ao banco de dados")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager - fechar conexão"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Conexão fechada")
        
    def execute(self, sql: str, params=None, description: str = ""):
        """Executa SQL com logging e dry-run"""
        if self.dry_run:
            logger.info(f"[DRY RUN] {description}")
            logger.debug(f"[DRY RUN SQL] {sql}")
            return None
        
        try:
            if description:
                logger.info(description)
            self.cursor.execute(sql, params)
            return self.cursor
        except Exception as e:
            logger.error(f"Erro ao executar: {description}")
            logger.error(f"SQL: {sql}")
            logger.error(f"Erro: {e}")
            raise
    
    def get_all_cities(self) -> List[Dict]:
        """Busca todos os municípios cadastrados"""
        logger.info("Buscando municípios cadastrados...")
        self.cursor.execute("SELECT id, name, state FROM public.city ORDER BY name")
        cities = []
        for row in self.cursor.fetchall():
            cities.append({
                'id': row[0],
                'name': row[1],
                'state': row[2]
            })
        logger.info(f"Encontrados {len(cities)} municípios")
        return cities
    
    def create_city_schemas(self):
        """1. Criar schemas city_<city_id> para cada município"""
        logger.info("=" * 80)
        logger.info("ETAPA 1: Criando schemas para municipios")
        logger.info("=" * 80)
        
        cities = self.get_all_cities()
        
        for city in cities:
            schema_name = f"city_{city['id'].replace('-', '_')}"
            
            # Verificar se schema já existe
            self.cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                (schema_name,)
            )
            exists = self.cursor.fetchone()
            
            if exists:
                logger.info(f"  [OK] Schema '{schema_name}' ja existe ({city['name']}/{city['state']})")
                continue
            
            # Criar schema
            sql = f"CREATE SCHEMA IF NOT EXISTS {schema_name}"
            self.execute(
                sql,
                description=f"  => Criando schema '{schema_name}' para {city['name']}/{city['state']}"
            )
            
            # Comentário no schema
            comment_sql = f"""
            COMMENT ON SCHEMA {schema_name} IS 
            'Schema operacional do município: {city["name"]}/{city["state"]} (ID: {city["id"]})'
            """
            self.execute(comment_sql)
            
        logger.info(f"[OK] Schemas criados/verificados para {len(cities)} municipios\n")
    
    def create_city_tables(self, schema: str):
        """2. Criar tabelas operacionais no schema CITY"""
        
        # Usar UUID extension se não existir
        self.execute(
            'CREATE EXTENSION IF NOT EXISTS "uuid-ossp"',
            description=f"  => Habilitando extensao uuid-ossp em {schema}"
        )
        
        # ===================================================================
        # TABELAS OPERACIONAIS - CITY SCHEMA
        # ===================================================================
        
        tables_sql = f"""
        -- ===================================================================
        -- ESTRUTURA ORGANIZACIONAL
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.school (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(100),
            address VARCHAR(200),
            domain VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            city_id VARCHAR REFERENCES public.city(id)
        );
        COMMENT ON TABLE {schema}.school IS 'Escolas do município';
        
        CREATE TABLE IF NOT EXISTS {schema}.school_course (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            education_stage_id UUID REFERENCES public.education_stage(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_school_education_stage UNIQUE(school_id, education_stage_id)
        );
        COMMENT ON TABLE {schema}.school_course IS 'Cursos oferecidos pelas escolas';
        
        CREATE TABLE IF NOT EXISTS {schema}.class (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(100),
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            grade_id UUID REFERENCES public.grade(id)
        );
        COMMENT ON TABLE {schema}.class IS 'Turmas das escolas';
        
        -- ===================================================================
        -- PESSOAS (CONTEXTO OPERACIONAL)
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.student (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(100),
            profile_picture VARCHAR,
            registration VARCHAR(50) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            birth_date DATE,
            user_id VARCHAR REFERENCES public.users(id) UNIQUE,
            grade_id UUID REFERENCES public.grade(id),
            class_id UUID REFERENCES {schema}.class(id),
            school_id VARCHAR(36) REFERENCES {schema}.school(id)
        );
        COMMENT ON TABLE {schema}.student IS 'Alunos das escolas do município';
        
        CREATE TABLE IF NOT EXISTS {schema}.teacher (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            profile_picture VARCHAR,
            registration VARCHAR(50) UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            birth_date DATE,
            user_id VARCHAR REFERENCES public.users(id) UNIQUE
        );
        COMMENT ON TABLE {schema}.teacher IS 'Professores do município';
        
        -- ===================================================================
        -- RELACIONAMENTOS OPERACIONAIS
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.school_teacher (
            id VARCHAR PRIMARY KEY,
            registration VARCHAR,
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            teacher_id VARCHAR REFERENCES {schema}.teacher(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.school_teacher IS 'Vínculo professor-escola';
        
        CREATE TABLE IF NOT EXISTS {schema}.teacher_class (
            id VARCHAR PRIMARY KEY,
            teacher_id VARCHAR REFERENCES {schema}.teacher(id),
            class_id UUID REFERENCES {schema}.class(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.teacher_class IS 'Vínculo professor-turma';
        
        CREATE TABLE IF NOT EXISTS {schema}.class_subject (
            id VARCHAR PRIMARY KEY,
            class_id UUID REFERENCES {schema}.class(id),
            subject_id VARCHAR REFERENCES public.subject(id),
            teacher_id VARCHAR REFERENCES {schema}.teacher(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.class_subject IS 'Disciplinas ministradas em turmas';
        
        -- ===================================================================
        -- ESCOLA-MANAGER (NOVO - SUBSTITUI manager.school_id)
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.school_managers (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            manager_id VARCHAR REFERENCES public.manager(id),
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            role VARCHAR(50),
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_active_manager_school UNIQUE(manager_id, school_id, is_active)
        );
        COMMENT ON TABLE {schema}.school_managers IS 'Vínculo manager-escola (substitui manager.school_id)';
        CREATE INDEX IF NOT EXISTS idx_school_managers_active ON {schema}.school_managers(is_active) WHERE is_active = true;
        
        -- ===================================================================
        -- AVALIAÇÕES
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.test (
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
        COMMENT ON TABLE {schema}.test IS 'Avaliações criadas no município';
        
        CREATE TABLE IF NOT EXISTS {schema}.test_questions (
            id VARCHAR PRIMARY KEY,
            test_id VARCHAR REFERENCES {schema}.test(id),
            question_id VARCHAR REFERENCES public.question(id),
            "order" INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.test_questions IS 'Questões das avaliações';
        
        CREATE TABLE IF NOT EXISTS {schema}.class_test (
            id VARCHAR PRIMARY KEY,
            class_id UUID REFERENCES {schema}.class(id),
            test_id VARCHAR REFERENCES {schema}.test(id),
            status VARCHAR DEFAULT 'agendada',
            application TEXT NOT NULL,
            expiration TEXT NOT NULL,
            timezone VARCHAR(50)
        );
        COMMENT ON TABLE {schema}.class_test IS 'Aplicação de testes em turmas';
        
        CREATE TABLE IF NOT EXISTS {schema}.student_test_olimpics (
            id VARCHAR PRIMARY KEY,
            student_id VARCHAR REFERENCES {schema}.student(id),
            test_id VARCHAR REFERENCES {schema}.test(id),
            status VARCHAR DEFAULT 'agendada',
            application TEXT NOT NULL,
            expiration TEXT NOT NULL,
            timezone VARCHAR(50),
            CONSTRAINT uq_student_test_olimpics_student_test UNIQUE(student_id, test_id)
        );
        COMMENT ON TABLE {schema}.student_test_olimpics IS 'Inscrições de alunos em olimpíadas';
        
        -- ===================================================================
        -- RESPOSTAS E SESSÕES
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.student_answers (
            id VARCHAR PRIMARY KEY,
            student_id VARCHAR REFERENCES {schema}.student(id),
            test_id VARCHAR REFERENCES {schema}.test(id),
            question_id VARCHAR REFERENCES public.question(id),
            answer TEXT NOT NULL,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_correct BOOLEAN,
            manual_score FLOAT,
            feedback TEXT,
            corrected_by VARCHAR REFERENCES public.users(id),
            corrected_at TIMESTAMP
        );
        COMMENT ON TABLE {schema}.student_answers IS 'Respostas dos alunos';
        
        CREATE TABLE IF NOT EXISTS {schema}.test_sessions (
            id VARCHAR PRIMARY KEY,
            student_id VARCHAR REFERENCES {schema}.student(id),
            test_id VARCHAR REFERENCES {schema}.test(id),
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
        COMMENT ON TABLE {schema}.test_sessions IS 'Sessões de prova dos alunos';
        
        CREATE TABLE IF NOT EXISTS {schema}.evaluation_results (
            id VARCHAR PRIMARY KEY,
            test_id VARCHAR REFERENCES {schema}.test(id),
            student_id VARCHAR REFERENCES {schema}.student(id),
            session_id VARCHAR REFERENCES {schema}.test_sessions(id),
            correct_answers INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            score_percentage FLOAT NOT NULL,
            grade FLOAT NOT NULL,
            proficiency FLOAT NOT NULL,
            classification VARCHAR(50) NOT NULL,
            calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.evaluation_results IS 'Resultados de avaliações';
        
        -- ===================================================================
        -- FORMULÁRIOS FÍSICOS
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.physical_test_forms (
            id VARCHAR PRIMARY KEY,
            test_id VARCHAR REFERENCES {schema}.test(id),
            student_id VARCHAR REFERENCES {schema}.student(id),
            class_test_id VARCHAR REFERENCES {schema}.class_test(id),
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
        COMMENT ON TABLE {schema}.physical_test_forms IS 'Formulários físicos gerados';
        
        CREATE TABLE IF NOT EXISTS {schema}.physical_test_answers (
            id VARCHAR PRIMARY KEY,
            physical_form_id VARCHAR REFERENCES {schema}.physical_test_forms(id),
            question_id VARCHAR REFERENCES public.question(id),
            marked_answer VARCHAR,
            correct_answer VARCHAR NOT NULL,
            is_correct BOOLEAN,
            confidence_score FLOAT,
            detection_coordinates JSON,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            corrected_at TIMESTAMP
        );
        COMMENT ON TABLE {schema}.physical_test_answers IS 'Respostas de formulários físicos';
        
        CREATE TABLE IF NOT EXISTS {schema}.form_coordinates (
            id VARCHAR(36) PRIMARY KEY,
            test_id VARCHAR(36) REFERENCES {schema}.test(id),
            form_type VARCHAR(50) NOT NULL DEFAULT 'physical_test',
            qr_code_id VARCHAR(36),
            student_id VARCHAR(36) REFERENCES {schema}.student(id),
            coordinates JSON NOT NULL,
            num_questions INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_test_form_type UNIQUE(test_id, form_type)
        );
        COMMENT ON TABLE {schema}.form_coordinates IS 'Coordenadas de formulários de resposta';
        
        CREATE TABLE IF NOT EXISTS {schema}.answer_sheet_gabaritos (
            id VARCHAR PRIMARY KEY,
            test_id VARCHAR REFERENCES {schema}.test(id),
            class_id UUID REFERENCES {schema}.class(id),
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
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
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
        COMMENT ON TABLE {schema}.answer_sheet_gabaritos IS 'Gabaritos de cartões resposta';
        
        CREATE TABLE IF NOT EXISTS {schema}.answer_sheet_results (
            id VARCHAR PRIMARY KEY,
            gabarito_id VARCHAR REFERENCES {schema}.answer_sheet_gabaritos(id),
            student_id VARCHAR REFERENCES {schema}.student(id),
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
        COMMENT ON TABLE {schema}.answer_sheet_results IS 'Resultados de correção de cartões';
        
        CREATE TABLE IF NOT EXISTS {schema}.batch_correction_jobs (
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
        COMMENT ON TABLE {schema}.batch_correction_jobs IS 'Jobs de correção em lote';
        
        -- ===================================================================
        -- RELATÓRIOS E CACHE
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.report_aggregates (
            id VARCHAR PRIMARY KEY,
            test_id VARCHAR REFERENCES {schema}.test(id) NOT NULL,
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
        COMMENT ON TABLE {schema}.report_aggregates IS 'Cache de relatórios agregados';
        CREATE INDEX IF NOT EXISTS idx_report_aggregates_test ON {schema}.report_aggregates(test_id);
        CREATE INDEX IF NOT EXISTS idx_report_aggregates_scope ON {schema}.report_aggregates(scope_type, scope_id);
        
        -- ===================================================================
        -- JOGOS
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.games (
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
        COMMENT ON TABLE {schema}.games IS 'Jogos criados por professores';
        
        CREATE TABLE IF NOT EXISTS {schema}.game_classes (
            id VARCHAR PRIMARY KEY,
            game_id VARCHAR REFERENCES {schema}.games(id),
            class_id UUID REFERENCES {schema}.class(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.game_classes IS 'Jogos aplicados em turmas';
        
        -- ===================================================================
        -- CALENDÁRIO
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.calendar_events (
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
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            metadata_json JSON
        );
        COMMENT ON TABLE {schema}.calendar_events IS 'Eventos de calendário';
        
        CREATE TABLE IF NOT EXISTS {schema}.calendar_event_targets (
            id VARCHAR PRIMARY KEY,
            event_id VARCHAR REFERENCES {schema}.calendar_events(id),
            target_type VARCHAR NOT NULL,
            target_id VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.calendar_event_targets IS 'Alvos de eventos de calendário';
        
        CREATE TABLE IF NOT EXISTS {schema}.calendar_event_users (
            id VARCHAR PRIMARY KEY,
            event_id VARCHAR REFERENCES {schema}.calendar_events(id),
            user_id VARCHAR REFERENCES public.users(id),
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            class_id UUID REFERENCES {schema}.class(id),
            role_snapshot VARCHAR(32),
            read_at TIMESTAMP WITH TIME ZONE,
            dismissed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.calendar_event_users IS 'Usuários vinculados a eventos';
        
        -- ===================================================================
        -- COMPETIÇÕES (INSTANCIADAS)
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.competitions (
            id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            description TEXT,
            test_id VARCHAR REFERENCES {schema}.test(id),
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
        COMMENT ON TABLE {schema}.competitions IS 'Competições instanciadas no município';
        
        CREATE TABLE IF NOT EXISTS {schema}.competition_enrollments (
            id VARCHAR PRIMARY KEY,
            competition_id VARCHAR REFERENCES {schema}.competitions(id) ON DELETE CASCADE,
            student_id VARCHAR REFERENCES {schema}.student(id) ON DELETE CASCADE,
            enrolled_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR NOT NULL DEFAULT 'inscrito',
            CONSTRAINT uq_competition_enrollments_competition_student UNIQUE(competition_id, student_id)
        );
        COMMENT ON TABLE {schema}.competition_enrollments IS 'Inscrições em competições';
        
        CREATE TABLE IF NOT EXISTS {schema}.competition_results (
            id VARCHAR PRIMARY KEY,
            competition_id VARCHAR REFERENCES {schema}.competitions(id) ON DELETE CASCADE,
            student_id VARCHAR REFERENCES {schema}.student(id) ON DELETE CASCADE,
            session_id VARCHAR REFERENCES {schema}.test_sessions(id) ON DELETE CASCADE,
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
        COMMENT ON TABLE {schema}.competition_results IS 'Resultados de competições';
        
        CREATE TABLE IF NOT EXISTS {schema}.competition_rewards (
            id VARCHAR PRIMARY KEY,
            competition_id VARCHAR REFERENCES {schema}.competitions(id) ON DELETE CASCADE,
            student_id VARCHAR REFERENCES {schema}.student(id) ON DELETE CASCADE,
            participation_paid_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_competition_rewards_competition_student UNIQUE(competition_id, student_id)
        );
        COMMENT ON TABLE {schema}.competition_rewards IS 'Recompensas de competições';
        
        CREATE TABLE IF NOT EXISTS {schema}.competition_ranking_payouts (
            id VARCHAR PRIMARY KEY,
            competition_id VARCHAR REFERENCES {schema}.competitions(id),
            student_id VARCHAR REFERENCES {schema}.student(id),
            position INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            paid_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_competition_ranking_payouts_competition_student UNIQUE(competition_id, student_id)
        );
        COMMENT ON TABLE {schema}.competition_ranking_payouts IS 'Pagamentos de ranking de competições';
        
        -- ===================================================================
        -- FORMULÁRIOS SOCIOECONÔMICOS
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.forms (
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
        COMMENT ON TABLE {schema}.forms IS 'Formulários socioeconômicos';
        
        CREATE TABLE IF NOT EXISTS {schema}.form_questions (
            id VARCHAR PRIMARY KEY,
            form_id VARCHAR REFERENCES {schema}.forms(id) ON DELETE CASCADE,
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
        COMMENT ON TABLE {schema}.form_questions IS 'Questões de formulários socioeconômicos';
        
        CREATE TABLE IF NOT EXISTS {schema}.form_recipients (
            id VARCHAR PRIMARY KEY,
            form_id VARCHAR REFERENCES {schema}.forms(id) ON DELETE CASCADE,
            user_id VARCHAR REFERENCES public.users(id) ON DELETE CASCADE,
            school_id VARCHAR(36) REFERENCES {schema}.school(id) ON DELETE SET NULL,
            status VARCHAR(20) DEFAULT 'pending' NOT NULL,
            sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            CONSTRAINT unique_form_user_recipient UNIQUE(form_id, user_id)
        );
        COMMENT ON TABLE {schema}.form_recipients IS 'Destinatários de formulários';
        
        CREATE TABLE IF NOT EXISTS {schema}.form_responses (
            id VARCHAR PRIMARY KEY,
            form_id VARCHAR REFERENCES {schema}.forms(id) ON DELETE CASCADE,
            user_id VARCHAR REFERENCES public.users(id) ON DELETE CASCADE,
            recipient_id VARCHAR REFERENCES {schema}.form_recipients(id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'in_progress' NOT NULL,
            responses JSON NOT NULL,
            progress NUMERIC(5, 2) DEFAULT 0.00 NOT NULL,
            started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            time_spent INTEGER DEFAULT 0 NOT NULL,
            CONSTRAINT unique_form_user_response UNIQUE(form_id, user_id)
        );
        COMMENT ON TABLE {schema}.form_responses IS 'Respostas de formulários socioeconômicos';
        
        CREATE TABLE IF NOT EXISTS {schema}.form_result_cache (
            id VARCHAR PRIMARY KEY,
            form_id VARCHAR REFERENCES {schema}.forms(id) ON DELETE CASCADE,
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
        COMMENT ON TABLE {schema}.form_result_cache IS 'Cache de resultados de formulários';
        CREATE INDEX IF NOT EXISTS idx_form_result_cache_form_type ON {schema}.form_result_cache(form_id, report_type);
        CREATE INDEX IF NOT EXISTS idx_form_result_cache_dirty ON {schema}.form_result_cache(is_dirty);
        
        -- ===================================================================
        -- PLAY TV (vídeos no schema do município)
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.play_tv_videos (
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
        CREATE INDEX IF NOT EXISTS ix_play_tv_videos_grade_id ON {schema}.play_tv_videos(grade_id);
        CREATE INDEX IF NOT EXISTS ix_play_tv_videos_subject_id ON {schema}.play_tv_videos(subject_id);
        CREATE INDEX IF NOT EXISTS ix_play_tv_videos_created_by ON {schema}.play_tv_videos(created_by);
        COMMENT ON TABLE {schema}.play_tv_videos IS 'Play TV: vídeos do município';
        
        CREATE TABLE IF NOT EXISTS {schema}.play_tv_video_resources (
            id VARCHAR PRIMARY KEY,
            video_id VARCHAR NOT NULL REFERENCES {schema}.play_tv_videos(id) ON DELETE CASCADE,
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
        CREATE INDEX IF NOT EXISTS ix_play_tv_video_resources_video_id ON {schema}.play_tv_video_resources(video_id);
        COMMENT ON TABLE {schema}.play_tv_video_resources IS 'Play TV: recursos (link ou arquivo)';
        
        CREATE TABLE IF NOT EXISTS {schema}.play_tv_video_schools (
            id VARCHAR PRIMARY KEY,
            video_id VARCHAR NOT NULL REFERENCES {schema}.play_tv_videos(id) ON DELETE CASCADE,
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.play_tv_video_schools IS 'Vídeos do Play TV disponibilizados para escolas';
        
        CREATE TABLE IF NOT EXISTS {schema}.play_tv_video_classes (
            id VARCHAR PRIMARY KEY,
            video_id VARCHAR NOT NULL REFERENCES {schema}.play_tv_videos(id) ON DELETE CASCADE,
            class_id UUID REFERENCES {schema}.class(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.play_tv_video_classes IS 'Vídeos do Play TV disponibilizados para turmas';
        
        -- ===================================================================
        -- DISTRIBUIÇÃO DE CONTEÚDO (outros módulos PUBLIC → CITY)
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.plantao_schools (
            id VARCHAR PRIMARY KEY,
            plantao_id VARCHAR REFERENCES public.plantao_online(id),
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.plantao_schools IS 'Plantões online disponibilizados para escolas';
        
        -- ===================================================================
        -- CERTIFICADOS
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.certificate_templates (
            id VARCHAR PRIMARY KEY,
            evaluation_id VARCHAR REFERENCES {schema}.test(id),
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
        COMMENT ON TABLE {schema}.certificate_templates IS 'Templates de certificados';
        
        CREATE TABLE IF NOT EXISTS {schema}.certificates (
            id VARCHAR PRIMARY KEY,
            student_id VARCHAR REFERENCES {schema}.student(id),
            student_name VARCHAR(200) NOT NULL,
            evaluation_id VARCHAR REFERENCES {schema}.test(id),
            evaluation_title VARCHAR(200) NOT NULL,
            grade FLOAT NOT NULL,
            template_id VARCHAR REFERENCES {schema}.certificate_templates(id),
            issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_certificate_student_evaluation UNIQUE(student_id, evaluation_id)
        );
        COMMENT ON TABLE {schema}.certificates IS 'Certificados emitidos';
        
        -- ===================================================================
        -- SISTEMA DE MOEDAS
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.student_coins (
            id VARCHAR PRIMARY KEY,
            student_id VARCHAR REFERENCES {schema}.student(id) NOT NULL UNIQUE,
            balance INTEGER DEFAULT 0 NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.student_coins IS 'Saldo de moedas dos alunos';
        
        CREATE TABLE IF NOT EXISTS {schema}.coin_transactions (
            id VARCHAR PRIMARY KEY,
            student_id VARCHAR REFERENCES {schema}.student(id) NOT NULL,
            amount INTEGER NOT NULL,
            balance_before INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            reason VARCHAR NOT NULL,
            competition_id VARCHAR,
            test_session_id VARCHAR REFERENCES {schema}.test_sessions(id) ON DELETE SET NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.coin_transactions IS 'Transações de moedas dos alunos';
        
        -- ===================================================================
        -- LOG DE SENHAS
        -- ===================================================================
        
        CREATE TABLE IF NOT EXISTS {schema}.student_password_log (
            id VARCHAR PRIMARY KEY,
            student_name VARCHAR(100) NOT NULL,
            email VARCHAR(100),
            password VARCHAR NOT NULL,
            registration VARCHAR(50),
            user_id VARCHAR REFERENCES public.users(id),
            student_id VARCHAR REFERENCES {schema}.student(id),
            class_id UUID REFERENCES {schema}.class(id),
            grade_id UUID REFERENCES public.grade(id),
            school_id VARCHAR(36) REFERENCES {schema}.school(id),
            city_id VARCHAR REFERENCES public.city(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        COMMENT ON TABLE {schema}.student_password_log IS 'Log de senhas de alunos (auditoria)';
        
        """
        
        # Executar criação de tabelas
        self.execute(
            tables_sql,
            description=f"  => Criando tabelas operacionais em {schema}"
        )
        
        logger.info(f"  [OK] Tabelas criadas em {schema}")
    
    def migrate_all_city_tables(self):
        """2. Criar tabelas em todos os schemas CITY"""
        logger.info("=" * 80)
        logger.info("ETAPA 2: Criando tabelas operacionais nos schemas CITY")
        logger.info("=" * 80)
        
        cities = self.get_all_cities()
        
        for city in cities:
            schema_name = f"city_{city['id'].replace('-', '_')}"
            logger.info(f"\n[SCHEMA] {schema_name} ({city['name']}/{city['state']})")
            self.create_city_tables(schema_name)
        
        logger.info(f"\n[OK] Tabelas criadas em {len(cities)} schemas CITY\n")
    
    def adjust_public_questions_schema(self):
        """3. Ajustar public.questions para suportar escopo"""
        logger.info("=" * 80)
        logger.info("ETAPA 3: Ajustando public.questions para suportar escopo")
        logger.info("=" * 80)
        
        # Criar ENUM para scope_type se não existir
        enum_sql = """
        DO $$ BEGIN
            CREATE TYPE question_scope_type AS ENUM ('GLOBAL', 'CITY');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
        self.execute(enum_sql, description="  => Criando ENUM question_scope_type")
        
        # Adicionar colunas de escopo
        columns_sql = """
        ALTER TABLE public.question 
        ADD COLUMN IF NOT EXISTS scope_type question_scope_type DEFAULT 'GLOBAL',
        ADD COLUMN IF NOT EXISTS owner_city_id VARCHAR REFERENCES public.city(id),
        ADD COLUMN IF NOT EXISTS approved_by VARCHAR REFERENCES public.users(id),
        ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP;
        """
        self.execute(
            columns_sql,
            description="  => Adicionando colunas de escopo em public.question"
        )
        
        # Comentários nas colunas
        comment_sql = """
        COMMENT ON COLUMN public.question.scope_type IS 
        'Escopo da questão: GLOBAL (compartilhada) ou CITY (local do município)';
        
        COMMENT ON COLUMN public.question.owner_city_id IS 
        'ID do município dono da questão (NULL para questões globais)';
        
        COMMENT ON COLUMN public.question.approved_by IS 
        'ID do usuário que aprovou a questão para uso global';
        
        COMMENT ON COLUMN public.question.approved_at IS 
        'Data de aprovação da questão para uso global';
        """
        self.execute(comment_sql)
        
        # Popular questões existentes como GLOBAL
        update_sql = """
        UPDATE public.question 
        SET scope_type = 'GLOBAL'
        WHERE scope_type IS NULL;
        """
        self.execute(
            update_sql,
            description="  => Marcando questoes existentes como GLOBAL"
        )
        
        # Criar índices
        index_sql = """
        CREATE INDEX IF NOT EXISTS idx_question_scope ON public.question(scope_type);
        CREATE INDEX IF NOT EXISTS idx_question_owner_city ON public.question(owner_city_id);
        CREATE INDEX IF NOT EXISTS idx_question_created_by ON public.question(created_by);
        """
        self.execute(index_sql, description="  => Criando indices de escopo")
        
        logger.info("  [OK] public.questions ajustado para suportar escopo\n")
    
    def migrate_school_managers_data(self):
        """4. Migrar dados de manager.school_id para school_managers"""
        logger.info("=" * 80)
        logger.info("ETAPA 4: Preparando school_managers (migracao de dados)")
        logger.info("=" * 80)
        
        # Buscar managers com school_id preenchido
        self.cursor.execute("""
            SELECT COUNT(*) 
            FROM public.manager 
            WHERE school_id IS NOT NULL
        """)
        
        managers_count = self.cursor.fetchone()[0]
        logger.info(f"  Encontrados {managers_count} managers com school_id em public.manager")
        
        logger.info("")
        logger.info("  [AVISO] Tabela school_managers criada, mas dados NAO foram migrados")
        logger.info("  [MOTIVO] Escolas ainda nao existem nos schemas CITY")
        logger.info("  [PROXIMA ETAPA] Script 0002 ira:")
        logger.info("    1. Migrar escolas de public.school -> city_<id>.school")
        logger.info("    2. Migrar vinculos para school_managers")
        logger.info("")
        logger.info("  [NOTA] Esta e uma migracao ESTRUTURAL apenas")
        logger.info("  [NOTA] Nenhum dado foi movido ou perdido\n")
    
    def create_public_indexes(self):
        """Criar índices úteis nas tabelas PUBLIC"""
        logger.info("=" * 80)
        logger.info("ETAPA EXTRA: Criando índices de performance em PUBLIC")
        logger.info("=" * 80)
        
        indexes_sql = """
        -- Indices em users
        CREATE INDEX IF NOT EXISTS idx_users_city ON public.users(city_id);
        CREATE INDEX IF NOT EXISTS idx_users_role ON public.users(role);
        CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
        
        -- Indices em manager
        CREATE INDEX IF NOT EXISTS idx_manager_city ON public.manager(city_id);
        CREATE INDEX IF NOT EXISTS idx_manager_user ON public.manager(user_id);
        
        -- Indices em city
        CREATE INDEX IF NOT EXISTS idx_city_state ON public.city(state);
        """
        self.execute(indexes_sql, description="  => Criando indices de performance")
        logger.info("  [OK] Indices criados\n")
    
    def run_migration(self):
        """Executar migração completa"""
        logger.info("\n" + "=" * 80)
        logger.info("INICIANDO MIGRACAO MULTI-TENANT - Script 0001")
        logger.info("=" * 80)
        logger.info(f"Database: {self.database_url.split('@')[1]}")
        logger.info(f"Modo: {'DRY RUN (simulacao)' if self.dry_run else 'EXECUCAO REAL'}")
        logger.info("=" * 80 + "\n")
        
        try:
            # Etapa 1: Criar schemas
            self.create_city_schemas()
            
            # Etapa 2: Criar tabelas CITY
            self.migrate_all_city_tables()
            
            # Etapa 3: Ajustar public.questions
            self.adjust_public_questions_schema()
            
            # Etapa 4: Migrar school_managers
            self.migrate_school_managers_data()
            
            # Extra: Índices
            self.create_public_indexes()
            
            logger.info("\n" + "=" * 80)
            logger.info("MIGRACAO DE ESTRUTURA CONCLUIDA COM SUCESSO!")
            logger.info("=" * 80)
            logger.info("\nO que foi criado:")
            logger.info("  - Schemas city_<id> para cada municipio")
            logger.info("  - 54+ tabelas operacionais em cada schema CITY")
            logger.info("  - Colunas de escopo em public.question")
            logger.info("  - Tabela school_managers (vazia, sera populada no script 0002)")
            logger.info("")
            logger.info("Proximos passos:")
            logger.info("  1. Validar estrutura: python validate_migration.py")
            logger.info("  2. Criar script 0002 para migracao de DADOS")
            logger.info("  3. Migrar: school, student, teacher, test, etc.")
            logger.info("  4. Ajustar application code para schemas dinamicos")
            logger.info("")
            logger.info("IMPORTANTE:")
            logger.info("  - Nenhum dado foi movido ou perdido")
            logger.info("  - Tabelas do public continuam intactas")
            logger.info("  - Sistema atual continua funcionando normalmente")
            logger.info("=" * 80 + "\n")
            
        except Exception as e:
            logger.error("\n" + "=" * 80)
            logger.error("ERRO NA MIGRACAO!")
            logger.error("=" * 80)
            logger.error(f"Erro: {e}")
            logger.error("=" * 80 + "\n")
            raise


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Migração 0001: Inicialização Multi-Tenant'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Executar em modo simulação (não altera banco)'
    )
    parser.add_argument(
        '--database',
        help='URL do banco de dados (sobrescreve .env)',
        default=DATABASE_URL
    )
    
    args = parser.parse_args()
    
    if not args.database:
        logger.error("DATABASE_URL nao configurado!")
        logger.error("Configure no .env ou use --database")
        sys.exit(1)
    
    # Confirmar execução
    if not args.dry_run:
        print("\n" + "=" * 80)
        print("ATENCAO: Esta migracao ira ALTERAR o banco de dados!")
        print("Certifique-se de ter backup antes de continuar.")
        print("=" * 80)
        confirm = input("\nDigite 'CONFIRMO' para continuar: ")
        if confirm != 'CONFIRMO':
            logger.info("Migracao cancelada pelo usuario")
            sys.exit(0)
    
    # Executar migração
    with MultiTenantMigration(args.database, dry_run=args.dry_run) as migration:
        migration.run_migration()


if __name__ == '__main__':
    main()
