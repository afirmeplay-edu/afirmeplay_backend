"""
Script de Validação - Migração 0001

Verifica se a migração multi-tenant foi executada corretamente:
- Schemas city_<id> criados
- Tabelas operacionais criadas em cada schema
- Colunas de escopo em public.question
- Dados migrados para school_managers
"""

import os
import sys
import psycopg2
from dotenv import load_dotenv
from typing import List, Dict, Tuple

# Cores para terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

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


class MigrationValidator:
    """Validador de migração multi-tenant"""
    
    # Tabelas esperadas em cada schema CITY
    EXPECTED_CITY_TABLES = [
        'school', 'school_course', 'class', 'student', 'teacher',
        'school_teacher', 'teacher_class', 'class_subject',
        'school_managers',  # ⭐ NOVA TABELA
        'test', 'test_questions', 'class_test', 'student_test_olimpics',
        'student_answers', 'test_sessions', 'evaluation_results',
        'physical_test_forms', 'physical_test_answers', 'form_coordinates',
        'answer_sheet_gabaritos', 'answer_sheet_results', 'batch_correction_jobs',
        'report_aggregates', 'games', 'game_classes',
        'calendar_events', 'calendar_event_targets', 'calendar_event_users',
        'competitions', 'competition_enrollments', 'competition_results',
        'competition_rewards', 'competition_ranking_payouts',
        'forms', 'form_questions', 'form_recipients', 'form_responses', 'form_result_cache',
        'play_tv_video_schools', 'play_tv_video_classes', 'plantao_schools',
        'certificate_templates', 'certificates',
        'student_coins', 'coin_transactions',
        'student_password_log'
    ]
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.conn = None
        self.cursor = None
        self.errors = []
        self.warnings = []
        self.successes = []
        
    def __enter__(self):
        self.conn = psycopg2.connect(self.database_url)
        self.cursor = self.conn.cursor()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
    
    def get_all_cities(self) -> List[Dict]:
        """Busca todos os municípios"""
        self.cursor.execute("SELECT id, name, state FROM public.city ORDER BY name")
        return [{'id': row[0], 'name': row[1], 'state': row[2]} for row in self.cursor.fetchall()]
    
    def check_schemas(self) -> bool:
        """Verifica se schemas city_<id> foram criados"""
        print(f"\n{Colors.BLUE}{Colors.BOLD}[1] Verificando schemas CITY...{Colors.RESET}")
        
        cities = self.get_all_cities()
        all_ok = True
        
        for city in cities:
            schema_name = f"city_{city['id'].replace('-', '_')}"
            
            self.cursor.execute(
                "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                (schema_name,)
            )
            exists = self.cursor.fetchone()
            
            if exists:
                print(f"  {Colors.GREEN}✓{Colors.RESET} Schema '{schema_name}' existe ({city['name']}/{city['state']})")
                self.successes.append(f"Schema {schema_name} criado")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} Schema '{schema_name}' NÃO EXISTE ({city['name']}/{city['state']})")
                self.errors.append(f"Schema {schema_name} não encontrado")
                all_ok = False
        
        return all_ok
    
    def check_city_tables(self) -> bool:
        """Verifica se tabelas foram criadas nos schemas CITY"""
        print(f"\n{Colors.BLUE}{Colors.BOLD}[2] Verificando tabelas nos schemas CITY...{Colors.RESET}")
        
        cities = self.get_all_cities()
        all_ok = True
        total_missing = 0
        
        for city in cities:
            schema_name = f"city_{city['id'].replace('-', '_')}"
            
            # Buscar tabelas existentes no schema
            self.cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s
            """, (schema_name,))
            
            existing_tables = {row[0] for row in self.cursor.fetchall()}
            expected_tables = set(self.EXPECTED_CITY_TABLES)
            missing_tables = expected_tables - existing_tables
            extra_tables = existing_tables - expected_tables
            
            if not missing_tables:
                print(f"  {Colors.GREEN}✓{Colors.RESET} {schema_name}: {len(existing_tables)} tabelas OK")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} {schema_name}: faltando {len(missing_tables)} tabelas")
                for table in sorted(missing_tables):
                    print(f"    {Colors.RED}  - {table}{Colors.RESET}")
                    self.errors.append(f"{schema_name}.{table} não criada")
                all_ok = False
                total_missing += len(missing_tables)
            
            if extra_tables:
                print(f"  {Colors.YELLOW}[!]{Colors.RESET} {schema_name}: {len(extra_tables)} tabelas extras (nao esperadas)")
                for table in sorted(extra_tables):
                    print(f"    {Colors.YELLOW}  + {table}{Colors.RESET}")
                    self.warnings.append(f"{schema_name}.{table} não esperada")
        
        if all_ok:
            self.successes.append(f"Todas as tabelas CITY criadas ({len(self.EXPECTED_CITY_TABLES)} por schema)")
        
        return all_ok
    
    def check_questions_schema_changes(self) -> bool:
        """Verifica se public.question foi ajustado para escopo"""
        print(f"\n{Colors.BLUE}{Colors.BOLD}[3] Verificando ajustes em public.question...{Colors.RESET}")
        
        expected_columns = ['scope_type', 'owner_city_id', 'approved_by', 'approved_at']
        all_ok = True
        
        # Buscar colunas existentes
        self.cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'question'
        """)
        existing_columns = {row[0] for row in self.cursor.fetchall()}
        
        for col in expected_columns:
            if col in existing_columns:
                print(f"  {Colors.GREEN}✓{Colors.RESET} Coluna 'question.{col}' existe")
                self.successes.append(f"Coluna question.{col} criada")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} Coluna 'question.{col}' NÃO EXISTE")
                self.errors.append(f"Coluna question.{col} não encontrada")
                all_ok = False
        
        # Verificar ENUM scope_type
        self.cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_type 
                WHERE typname = 'question_scope_type'
            )
        """)
        enum_exists = self.cursor.fetchone()[0]
        
        if enum_exists:
            print(f"  {Colors.GREEN}✓{Colors.RESET} ENUM 'question_scope_type' existe")
            self.successes.append("ENUM question_scope_type criado")
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} ENUM 'question_scope_type' NÃO EXISTE")
            self.errors.append("ENUM question_scope_type não encontrado")
            all_ok = False
        
        # Verificar questões marcadas como GLOBAL
        if all_ok:
            self.cursor.execute("SELECT COUNT(*) FROM public.question WHERE scope_type = 'GLOBAL'")
            global_count = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM public.question")
            total_count = self.cursor.fetchone()[0]
            
            print(f"  {Colors.GREEN}✓{Colors.RESET} {global_count}/{total_count} questoes marcadas como GLOBAL")
            if global_count < total_count:
                print(f"  {Colors.YELLOW}[!]{Colors.RESET} {total_count - global_count} questoes sem escopo definido")
                self.warnings.append(f"{total_count - global_count} questões sem escopo")
        
        return all_ok
    
    def check_school_managers_migration(self) -> bool:
        """Verifica se school_managers foi criado (dados serao migrados no script 0002)"""
        print(f"\n{Colors.BLUE}{Colors.BOLD}[4] Verificando school_managers...{Colors.RESET}")
        
        # Contar managers com school_id em public
        self.cursor.execute("""
            SELECT COUNT(*) FROM public.manager WHERE school_id IS NOT NULL
        """)
        managers_with_school = self.cursor.fetchone()[0]
        
        print(f"  📊 Managers com school_id em public.manager: {managers_with_school}")
        print(f"  {Colors.YELLOW}ℹ{Colors.RESET}  Script 0001 apenas cria estrutura (nao migra dados)")
        
        # Verificar se tabela school_managers existe em cada schema
        cities = self.get_all_cities()
        tables_created = 0
        all_ok = True
        
        for city in cities:
            schema_name = f"city_{city['id'].replace('-', '_')}"
            
            try:
                # Verificar se tabela existe
                self.cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = %s 
                        AND table_name = 'school_managers'
                    )
                """, (schema_name,))
                
                exists = self.cursor.fetchone()[0]
                
                if exists:
                    tables_created += 1
                else:
                    print(f"  {Colors.RED}✗{Colors.RESET} Tabela {schema_name}.school_managers NAO existe")
                    self.errors.append(f"Tabela {schema_name}.school_managers ausente")
                    all_ok = False
                    
            except Exception as e:
                print(f"  {Colors.RED}✗{Colors.RESET} Erro ao verificar {schema_name}.school_managers: {e}")
                self.errors.append(f"Erro em {schema_name}.school_managers")
                all_ok = False
        
        if tables_created == len(cities):
            print(f"  {Colors.GREEN}✓{Colors.RESET} Tabela school_managers criada em {tables_created} schemas")
            print(f"  {Colors.YELLOW}ℹ{Colors.RESET}  Dados serao migrados no script 0002 (apos migrar schools)")
            self.successes.append(f"Tabela school_managers criada em {tables_created} schemas")
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} Tabela criada em apenas {tables_created}/{len(cities)} schemas")
        
        return all_ok
    
    def check_foreign_keys(self) -> bool:
        """Verifica integridade de Foreign Keys cross-schema"""
        print(f"\n{Colors.BLUE}{Colors.BOLD}[5] Verificando Foreign Keys cross-schema...{Colors.RESET}")
        
        cities = self.get_all_cities()
        all_ok = True
        
        # Testar algumas FKs importantes
        test_cases = [
            ('student', 'grade_id', 'public.grade'),
            ('school', 'city_id', 'public.city'),
            ('test_questions', 'question_id', 'public.question'),
            ('school_managers', 'manager_id', 'public.manager'),
        ]
        
        for city in cities[:1]:  # Testar apenas no primeiro schema para performance
            schema_name = f"city_{city['id'].replace('-', '_')}"
            
            for table, column, ref_table in test_cases:
                try:
                    # Verificar se FK existe
                    self.cursor.execute(f"""
                        SELECT COUNT(*) 
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.key_column_usage kcu 
                          ON tc.constraint_name = kcu.constraint_name
                        WHERE tc.table_schema = %s 
                          AND tc.table_name = %s
                          AND kcu.column_name = %s
                          AND tc.constraint_type = 'FOREIGN KEY'
                    """, (schema_name, table, column))
                    
                    fk_count = self.cursor.fetchone()[0]
                    
                    if fk_count > 0:
                        print(f"  {Colors.GREEN}✓{Colors.RESET} FK {schema_name}.{table}.{column} → {ref_table}")
                    else:
                        print(f"  {Colors.YELLOW}[!]{Colors.RESET} FK {schema_name}.{table}.{column} nao encontrada")
                        self.warnings.append(f"FK {table}.{column} ausente")
                        
                except Exception as e:
                    print(f"  {Colors.RED}✗{Colors.RESET} Erro verificando {table}.{column}: {e}")
                    all_ok = False
        
        return all_ok
    
    def check_indexes(self) -> bool:
        """Verifica índices criados"""
        print(f"\n{Colors.BLUE}{Colors.BOLD}[6] Verificando indices...{Colors.RESET}")
        
        expected_indexes = [
            ('public', 'users', 'idx_users_city'),
            ('public', 'users', 'idx_users_role'),
            ('public', 'manager', 'idx_manager_city'),
            ('public', 'question', 'idx_question_scope'),
        ]
        
        all_ok = True
        
        for schema, table, index_name in expected_indexes:
            self.cursor.execute("""
                SELECT COUNT(*) 
                FROM pg_indexes 
                WHERE schemaname = %s 
                  AND tablename = %s 
                  AND indexname = %s
            """, (schema, table, index_name))
            
            exists = self.cursor.fetchone()[0] > 0
            
            if exists:
                print(f"  {Colors.GREEN}✓{Colors.RESET} Índice '{index_name}' em {schema}.{table}")
            else:
                print(f"  {Colors.YELLOW}[!]{Colors.RESET} Indice '{index_name}' nao encontrado em {schema}.{table}")
                self.warnings.append(f"Índice {index_name} ausente")
        
        return all_ok
    
    def print_summary(self):
        """Imprime resumo da validação"""
        print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
        print(f"{Colors.BOLD}RESUMO DA VALIDACAO{Colors.RESET}")
        print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
        
        print(f"\n{Colors.GREEN}[OK] Sucessos: {len(self.successes)}{Colors.RESET}")
        for msg in self.successes[:5]:  # Mostrar apenas os 5 primeiros
            print(f"  • {msg}")
        if len(self.successes) > 5:
            print(f"  ... e mais {len(self.successes) - 5}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}[!] Avisos: {len(self.warnings)}{Colors.RESET}")
            for msg in self.warnings[:10]:
                print(f"  • {msg}")
            if len(self.warnings) > 10:
                print(f"  ... e mais {len(self.warnings) - 10}")
        
        if self.errors:
            print(f"\n{Colors.RED}[X] Erros: {len(self.errors)}{Colors.RESET}")
            for msg in self.errors:
                print(f"  • {msg}")
        
        print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
        
        if not self.errors and not self.warnings:
            print(f"{Colors.GREEN}{Colors.BOLD}[OK] MIGRACAO VALIDADA COM SUCESSO!{Colors.RESET}")
            print(f"{Colors.GREEN}Todos os componentes foram criados corretamente.{Colors.RESET}")
            return True
        elif not self.errors:
            print(f"{Colors.YELLOW}{Colors.BOLD}[!] MIGRACAO OK COM AVISOS{Colors.RESET}")
            print(f"{Colors.YELLOW}Alguns componentes opcionais estao ausentes.{Colors.RESET}")
            return True
        else:
            print(f"{Colors.RED}{Colors.BOLD}[X] MIGRACAO COM ERROS!{Colors.RESET}")
            print(f"{Colors.RED}Componentes criticos estao faltando.{Colors.RESET}")
            return False
    
    def run_validation(self) -> bool:
        """Executa validação completa"""
        print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
        print(f"{Colors.BOLD}VALIDACAO DE MIGRACAO MULTI-TENANT{Colors.RESET}")
        print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
        print(f"Database: {self.database_url.split('@')[1]}")
        print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
        
        checks = [
            self.check_schemas,
            self.check_city_tables,
            self.check_questions_schema_changes,
            self.check_school_managers_migration,
            self.check_foreign_keys,
            self.check_indexes,
        ]
        
        for check in checks:
            try:
                check()
            except Exception as e:
                print(f"\n{Colors.RED}[X] Erro ao executar {check.__name__}: {e}{Colors.RESET}")
                self.errors.append(f"Erro em {check.__name__}: {e}")
        
        return self.print_summary()


def main():
    """Função principal"""
    if not DATABASE_URL:
        print(f"{Colors.RED}[X] DATABASE_URL nao configurado!{Colors.RESET}")
        print("Configure no app/.env")
        sys.exit(1)
    
    try:
        with MigrationValidator(DATABASE_URL) as validator:
            success = validator.run_validation()
            sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n{Colors.RED}[X] Erro fatal: {e}{Colors.RESET}")
        sys.exit(1)


if __name__ == '__main__':
    main()
