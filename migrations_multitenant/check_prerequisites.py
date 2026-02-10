"""
Verificador de Pré-requisitos para Migração

Verifica se o ambiente está pronto para executar a migração multi-tenant.
"""

import os
import sys
import subprocess
from urllib.parse import urlparse
from dotenv import load_dotenv

# Cores
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def check_python_version():
    """Verifica versão do Python"""
    print(f"\n{Colors.BLUE}🐍 Python Version{Colors.RESET}")
    version = sys.version_info
    
    if version.major >= 3 and version.minor >= 7:
        print(f"  {Colors.GREEN}✓{Colors.RESET} Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"  {Colors.RED}✗{Colors.RESET} Python {version.major}.{version.minor}.{version.micro}")
        print(f"  {Colors.RED}  Requer Python 3.7+{Colors.RESET}")
        return False


def check_dependencies():
    """Verifica dependências Python instaladas"""
    print(f"\n{Colors.BLUE}📦 Python Dependencies{Colors.RESET}")
    
    required = ['psycopg2', 'dotenv']
    all_ok = True
    
    for package in required:
        try:
            __import__(package)
            print(f"  {Colors.GREEN}✓{Colors.RESET} {package}")
        except ImportError:
            print(f"  {Colors.RED}✗{Colors.RESET} {package} não instalado")
            all_ok = False
    
    if not all_ok:
        print(f"\n  {Colors.YELLOW}💡 Para instalar:{Colors.RESET}")
        print(f"     pip install psycopg2-binary python-dotenv")
    
    return all_ok


def check_env_file():
    """Verifica se .env existe e tem DATABASE_URL"""
    print(f"\n{Colors.BLUE}⚙️  Environment Configuration{Colors.RESET}")
    
    # Tentar múltiplos caminhos possíveis
    possible_paths = [
        'app/.env',
        '../app/.env',
        '../../app/.env',
        os.path.join(os.path.dirname(__file__), '..', 'app', '.env')
    ]
    
    env_path = None
    for path in possible_paths:
        if os.path.exists(path):
            env_path = path
            break
    
    if not env_path:
        print(f"  {Colors.RED}✗{Colors.RESET} app/.env não encontrado")
        print(f"  {Colors.YELLOW}💡 Tentou:{Colors.RESET}")
        for path in possible_paths[:3]:
            print(f"     - {path}")
        print(f"\n  {Colors.YELLOW}📝 Execute o script a partir da raiz do projeto:{Colors.RESET}")
        print(f"     cd C:\\Users\\Artur Calderon\\Documents\\Programming\\innovaplay_backend")
        print(f"     python migrations_multitenant\\check_prerequisites.py")
        return False
    
    print(f"  {Colors.GREEN}✓{Colors.RESET} {env_path} existe")
    
    load_dotenv(env_path)
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print(f"  {Colors.RED}✗{Colors.RESET} DATABASE_URL não configurado")
        return False
    
    print(f"  {Colors.GREEN}✓{Colors.RESET} DATABASE_URL configurado")
    
    # Parse URL
    try:
        parsed = urlparse(database_url)
        print(f"     Host: {parsed.hostname}:{parsed.port or 5432}")
        print(f"     Database: {parsed.path.lstrip('/')}")
        print(f"     User: {parsed.username}")
        return True
    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.RESET} DATABASE_URL inválido: {e}")
        return False


def check_database_connection():
    """Verifica conexão com banco de dados"""
    print(f"\n{Colors.BLUE}🔌 Database Connection{Colors.RESET}")
    
    # Carregar .env do caminho correto
    possible_paths = [
        'app/.env',
        '../app/.env',
        os.path.join(os.path.dirname(__file__), '..', 'app', '.env')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            load_dotenv(path)
            break
    
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print(f"  {Colors.RED}✗{Colors.RESET} DATABASE_URL não configurado")
        return False
    
    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Testar query simples
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        
        # Verificar se é PostgreSQL
        if 'PostgreSQL' in version:
            pg_version = version.split()[1]
            print(f"  {Colors.GREEN}✓{Colors.RESET} Conectado ao PostgreSQL {pg_version}")
        else:
            print(f"  {Colors.YELLOW}⚠{Colors.RESET}  Banco não é PostgreSQL")
        
        # Verificar permissões
        cursor.execute("SELECT current_user")
        user = cursor.fetchone()[0]
        print(f"  {Colors.GREEN}✓{Colors.RESET} Usuário: {user}")
        
        # Verificar se pode criar schemas
        try:
            cursor.execute("SELECT has_database_privilege(current_user, current_database(), 'CREATE')")
            can_create = cursor.fetchone()[0]
            
            if can_create:
                print(f"  {Colors.GREEN}✓{Colors.RESET} Permissão CREATE: OK")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} Sem permissão CREATE")
                cursor.close()
                conn.close()
                return False
        except:
            print(f"  {Colors.YELLOW}⚠{Colors.RESET}  Não foi possível verificar permissões")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.RESET} Erro de conexão: {e}")
        return False


def check_pg_dump():
    """Verifica se pg_dump está disponível"""
    print(f"\n{Colors.BLUE}🛠️  PostgreSQL Tools{Colors.RESET}")
    
    try:
        result = subprocess.run(
            ['pg_dump', '--version'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"  {Colors.GREEN}✓{Colors.RESET} {version}")
            return True
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} pg_dump não funciona")
            return False
            
    except FileNotFoundError:
        print(f"  {Colors.RED}✗{Colors.RESET} pg_dump não encontrado")
        print(f"\n  {Colors.YELLOW}💡 Para instalar:{Colors.RESET}")
        print(f"     Windows: https://www.postgresql.org/download/windows/")
        print(f"     Linux: sudo apt-get install postgresql-client")
        print(f"     Mac: brew install postgresql")
        return False


def check_cities_in_database():
    """Verifica se há municípios cadastrados"""
    print(f"\n{Colors.BLUE}🏙️  Cities in Database{Colors.RESET}")
    
    # Carregar .env do caminho correto
    possible_paths = [
        'app/.env',
        '../app/.env',
        os.path.join(os.path.dirname(__file__), '..', 'app', '.env')
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            load_dotenv(path)
            break
    
    database_url = os.getenv('DATABASE_URL')
    
    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM public.city")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"  {Colors.GREEN}✓{Colors.RESET} {count} município(s) cadastrado(s)")
            
            # Mostrar alguns exemplos
            cursor.execute("SELECT name, state FROM public.city ORDER BY name LIMIT 5")
            cities = cursor.fetchall()
            
            for city, state in cities:
                print(f"     • {city}/{state}")
            
            if count > 5:
                print(f"     ... e mais {count - 5}")
        else:
            print(f"  {Colors.YELLOW}⚠{Colors.RESET}  Nenhum município cadastrado")
            print(f"     Schemas CITY não serão criados")
        
        cursor.close()
        conn.close()
        return count > 0
        
    except Exception as e:
        print(f"  {Colors.RED}✗{Colors.RESET} Erro ao verificar: {e}")
        return False


def check_disk_space():
    """Verifica espaço em disco"""
    print(f"\n{Colors.BLUE}💾 Disk Space{Colors.RESET}")
    
    try:
        import shutil
        stat = shutil.disk_usage('.')
        
        free_gb = stat.free / (1024**3)
        total_gb = stat.total / (1024**3)
        used_percent = (stat.used / stat.total) * 100
        
        print(f"  Livre: {free_gb:.2f} GB / {total_gb:.2f} GB ({100-used_percent:.1f}% livre)")
        
        if free_gb < 1:
            print(f"  {Colors.RED}✗{Colors.RESET} Pouco espaço em disco!")
            return False
        elif free_gb < 5:
            print(f"  {Colors.YELLOW}⚠{Colors.RESET}  Espaço limitado")
            return True
        else:
            print(f"  {Colors.GREEN}✓{Colors.RESET} Espaço suficiente")
            return True
            
    except Exception as e:
        print(f"  {Colors.YELLOW}⚠{Colors.RESET}  Não foi possível verificar: {e}")
        return True


def print_summary(checks):
    """Imprime resumo das verificações"""
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}📊 RESUMO{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    
    passed = sum(1 for result in checks.values() if result)
    total = len(checks)
    
    for check_name, result in checks.items():
        status = f"{Colors.GREEN}✓{Colors.RESET}" if result else f"{Colors.RED}✗{Colors.RESET}"
        print(f"  {status} {check_name}")
    
    print(f"\n{Colors.BOLD}Resultado: {passed}/{total} verificações passaram{Colors.RESET}")
    
    if passed == total:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ TUDO OK! Pronto para executar migração.{Colors.RESET}")
        print(f"\n{Colors.BOLD}Próximos passos:{Colors.RESET}")
        print(f"  1. python migrations_multitenant/backup_database.py")
        print(f"  2. python migrations_multitenant/0001_init_city_schemas.py --dry-run")
        print(f"  3. python migrations_multitenant/0001_init_city_schemas.py")
        print(f"  4. python migrations_multitenant/validate_migration.py")
        return True
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}❌ PROBLEMAS ENCONTRADOS!{Colors.RESET}")
        print(f"{Colors.RED}Resolva os problemas antes de executar a migração.{Colors.RESET}")
        return False


def main():
    """Função principal"""
    print(f"\n{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}🔍 VERIFICAÇÃO DE PRÉ-REQUISITOS - MIGRAÇÃO MULTI-TENANT{Colors.RESET}")
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}")
    
    checks = {
        'Python Version': check_python_version(),
        'Dependencies': check_dependencies(),
        'Environment File': check_env_file(),
        'Database Connection': check_database_connection(),
        'PostgreSQL Tools': check_pg_dump(),
        'Cities in Database': check_cities_in_database(),
        'Disk Space': check_disk_space(),
    }
    
    success = print_summary(checks)
    print(f"{Colors.BOLD}{'=' * 80}{Colors.RESET}\n")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
