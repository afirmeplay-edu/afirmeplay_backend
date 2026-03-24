"""
Script de Backup - Antes da Migração

Cria backup completo do banco de dados antes de executar migrações.
"""

import os
import sys
import subprocess
from datetime import datetime
from urllib.parse import urlparse
from dotenv import load_dotenv

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


class DatabaseBackup:
    """Gerenciador de backup PostgreSQL"""
    
    def __init__(self, database_url: str):
        # Parse da URL
        parsed = urlparse(database_url)
        self.host = parsed.hostname
        self.port = parsed.port or 5432
        self.database = parsed.path.lstrip('/')
        self.user = parsed.username
        self.password = parsed.password
        
        # Nome do arquivo de backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_file = f"backup_{self.database}_{timestamp}.dump"
        self.backup_sql = f"backup_{self.database}_{timestamp}.sql"
        
    def create_backup_custom_format(self) -> bool:
        """Cria backup no formato custom (recomendado)"""
        print(f"📦 Criando backup (formato custom): {self.backup_file}")
        
        env = os.environ.copy()
        env['PGPASSWORD'] = self.password
        
        cmd = [
            'pg_dump',
            '-h', self.host,
            '-p', str(self.port),
            '-U', self.user,
            '-d', self.database,
            '-F', 'c',  # Custom format
            '-b',  # Include blobs
            '-v',  # Verbose
            '-f', self.backup_file
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                file_size = os.path.getsize(self.backup_file) / (1024 * 1024)
                print(f"✅ Backup criado com sucesso!")
                print(f"   Arquivo: {self.backup_file}")
                print(f"   Tamanho: {file_size:.2f} MB")
                return True
            else:
                print(f"❌ Erro ao criar backup:")
                print(result.stderr)
                return False
                
        except FileNotFoundError:
            print("❌ pg_dump não encontrado!")
            print("Instale PostgreSQL client tools:")
            print("  - Windows: https://www.postgresql.org/download/windows/")
            print("  - Linux: sudo apt-get install postgresql-client")
            print("  - Mac: brew install postgresql")
            return False
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    
    def create_backup_sql_format(self) -> bool:
        """Cria backup no formato SQL (human-readable)"""
        print(f"📦 Criando backup (formato SQL): {self.backup_sql}")
        
        env = os.environ.copy()
        env['PGPASSWORD'] = self.password
        
        cmd = [
            'pg_dump',
            '-h', self.host,
            '-p', str(self.port),
            '-U', self.user,
            '-d', self.database,
            '--no-owner',
            '--no-acl',
            '-f', self.backup_sql
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                file_size = os.path.getsize(self.backup_sql) / (1024 * 1024)
                print(f"✅ Backup SQL criado com sucesso!")
                print(f"   Arquivo: {self.backup_sql}")
                print(f"   Tamanho: {file_size:.2f} MB")
                return True
            else:
                print(f"❌ Erro ao criar backup SQL:")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    
    def create_schema_only_backup(self) -> bool:
        """Cria backup apenas da estrutura (schema)"""
        schema_file = self.backup_sql.replace('.sql', '_schema_only.sql')
        print(f"📦 Criando backup de schema: {schema_file}")
        
        env = os.environ.copy()
        env['PGPASSWORD'] = self.password
        
        cmd = [
            'pg_dump',
            '-h', self.host,
            '-p', str(self.port),
            '-U', self.user,
            '-d', self.database,
            '--schema-only',
            '--no-owner',
            '--no-acl',
            '-f', schema_file
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"✅ Backup de schema criado: {schema_file}")
                return True
            else:
                print(f"⚠️  Erro ao criar backup de schema")
                return False
                
        except Exception as e:
            print(f"⚠️  Erro: {e}")
            return False
    
    def print_restore_instructions(self):
        """Imprime instruções de restore"""
        print("\n" + "=" * 80)
        print("📋 INSTRUÇÕES DE RESTORE")
        print("=" * 80)
        
        print(f"\n🔧 Para restaurar o backup CUSTOM (.dump):")
        print(f"   pg_restore -h {self.host} -p {self.port} -U {self.user} \\")
        print(f"              -d {self.database} -v --clean {self.backup_file}")
        
        print(f"\n🔧 Para restaurar o backup SQL (.sql):")
        print(f"   psql -h {self.host} -p {self.port} -U {self.user} \\")
        print(f"        -d {self.database} < {self.backup_sql}")
        
        print(f"\n⚠️  ATENÇÃO:")
        print(f"   - Certifique-se que o banco está vazio antes de restaurar")
        print(f"   - Use --clean para limpar objetos existentes")
        print(f"   - Faça restore em ambiente de teste primeiro")
        print("=" * 80)


def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backup do banco de dados')
    parser.add_argument(
        '--format',
        choices=['custom', 'sql', 'both'],
        default='both',
        help='Formato do backup (default: both)'
    )
    parser.add_argument(
        '--schema-only',
        action='store_true',
        help='Criar backup apenas do schema (estrutura)'
    )
    
    args = parser.parse_args()
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL não configurado!")
        print("Configure no app/.env")
        sys.exit(1)
    
    print("\n" + "=" * 80)
    print("🔄 BACKUP DO BANCO DE DADOS")
    print("=" * 80)
    
    backup = DatabaseBackup(DATABASE_URL)
    
    print(f"\nDatabase: {backup.database}")
    print(f"Host: {backup.host}:{backup.port}")
    print(f"User: {backup.user}")
    print("=" * 80 + "\n")
    
    success = True
    
    if args.format in ['custom', 'both']:
        if not backup.create_backup_custom_format():
            success = False
    
    if args.format in ['sql', 'both']:
        if not backup.create_backup_sql_format():
            success = False
    
    if args.schema_only:
        backup.create_schema_only_backup()
    
    if success:
        backup.print_restore_instructions()
        print("\n✅ Backup concluído com sucesso!")
        print("\n💡 Próximo passo:")
        print("   python migrations_multitenant/0001_init_city_schemas.py")
    else:
        print("\n❌ Erro ao criar backup!")
        sys.exit(1)


if __name__ == '__main__':
    main()
