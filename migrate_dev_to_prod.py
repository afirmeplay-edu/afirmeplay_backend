#!/usr/bin/env python3
"""
Script de Migração: DEV para PROD
Database: afirmeplay
Data: 2026-03-24

Este script sincroniza as tabelas e colunas do banco DEV para o PROD
considerando todos os schemas (public e city_*)

Uso:
    python migrate_dev_to_prod.py           # Execução normal (pede confirmação)
    python migrate_dev_to_prod.py --dry-run # Apenas mostra o que seria feito
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
import argparse
from typing import List, Dict, Set, Tuple

# Configurações dos bancos de dados
DEV_DB = "postgresql://postgres:devpass@147.79.87.213:15432/afirmeplay_dev"
PROD_DB = "postgresql://postgres:devpass@147.79.87.213:15432/afirmeplay_prod"

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(msg: str):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{msg.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")

def print_success(msg: str):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_info(msg: str):
    print(f"{Colors.OKCYAN}ℹ {msg}{Colors.ENDC}")

def print_warning(msg: str):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def print_error(msg: str):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def get_schemas(conn) -> List[str]:
    """Obtém todos os schemas do banco (public e city_*)"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name = 'public' OR schema_name LIKE 'city_%'
            ORDER BY schema_name
        """)
        return [row[0] for row in cur.fetchall()]


def get_tables_in_schema(conn, schema: str) -> Set[str]:
    """Obtém todas as tabelas de um schema"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
        """, (schema,))
        return {row[0] for row in cur.fetchall()}


def get_table_columns(conn, schema: str, table: str) -> Dict[str, Dict]:
    """Obtém todas as colunas de uma tabela com seus metadados"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default,
                udt_name
            FROM information_schema.columns 
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))
        
        columns = {}
        for row in cur.fetchall():
            col_name, data_type, max_length, is_nullable, col_default, udt_name = row
            columns[col_name] = {
                'data_type': data_type,
                'max_length': max_length,
                'is_nullable': is_nullable,
                'default': col_default,
                'udt_name': udt_name
            }
        return columns


def get_table_constraints(conn, schema: str, table: str) -> Dict[str, List]:
    """Obtém constraints (PK, FK, UNIQUE, CHECK) de uma tabela"""
    with conn.cursor() as cur:
        # Primary Keys
        cur.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            WHERE i.indrelid = %s::regclass AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
        """, (f'{schema}.{table}',))
        pk_columns = [row[0] for row in cur.fetchall()]
        
        # Foreign Keys
        cur.execute("""
            SELECT
                tc.constraint_name,
                kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.delete_rule,
                rc.update_rule
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            LEFT JOIN information_schema.referential_constraints AS rc
                ON rc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = %s
                AND tc.table_name = %s
            ORDER BY tc.constraint_name, kcu.ordinal_position
        """, (schema, table))
        foreign_keys = []
        for row in cur.fetchall():
            foreign_keys.append({
                'constraint_name': row[0],
                'column': row[1],
                'ref_schema': row[2],
                'ref_table': row[3],
                'ref_column': row[4],
                'on_delete': row[5],
                'on_update': row[6]
            })
        
        # Unique Constraints (excluindo PKs)
        cur.execute("""
            SELECT
                tc.constraint_name,
                string_agg(kcu.column_name, ',' ORDER BY kcu.ordinal_position) as columns
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'UNIQUE'
                AND tc.table_schema = %s
                AND tc.table_name = %s
            GROUP BY tc.constraint_name
        """, (schema, table))
        unique_constraints = []
        for row in cur.fetchall():
            unique_constraints.append({
                'name': row[0],
                'columns': row[1].split(',') if row[1] else []
            })
        
        # Indexes (não unique e não PK)
        cur.execute("""
            SELECT
                i.relname AS index_name,
                string_agg(a.attname, ',' ORDER BY array_position(ix.indkey, a.attnum)) as columns
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = %s
                AND t.relname = %s
                AND NOT ix.indisunique
                AND NOT ix.indisprimary
            GROUP BY i.relname
        """, (schema, table))
        indexes = []
        for row in cur.fetchall():
            indexes.append({
                'name': row[0],
                'columns': row[1].split(',') if row[1] else []
            })
        
        return {
            'primary_key': pk_columns,
            'foreign_keys': foreign_keys,
            'unique_constraints': unique_constraints,
            'indexes': indexes
        }


def build_create_table_ddl(conn, schema: str, table: str, skip_fks: bool = True) -> Tuple[str, List[str]]:
    """Constrói o DDL completo de uma tabela
    
    Args:
        conn: Conexão com o banco
        schema: Nome do schema
        table: Nome da tabela
        skip_fks: Se True, retorna FKs separadamente para criar depois
    
    Returns:
        Tuple com (ddl_create_table, lista_de_foreign_keys)
    """
    columns = get_table_columns(conn, schema, table)
    constraints = get_table_constraints(conn, schema, table)
    
    if not columns:
        return None, []
    
    # Início do CREATE TABLE
    ddl_parts = [f'CREATE TABLE {schema}.{table} (']
    
    # Colunas
    column_defs = []
    for col_name, col_info in columns.items():
        col_def = build_column_definition(col_name, col_info)
        column_defs.append(f'    {col_def}')
    
    ddl_parts.append(',\n'.join(column_defs))
    
    # Primary Key
    if constraints['primary_key']:
        pk_cols = ', '.join([f'"{col}"' for col in constraints['primary_key']])
        ddl_parts.append(f',\n    PRIMARY KEY ({pk_cols})')
    
    # Unique Constraints
    for uc in constraints['unique_constraints']:
        uc_cols = ', '.join([f'"{col}"' for col in uc['columns']])
        ddl_parts.append(f',\n    CONSTRAINT {uc["name"]} UNIQUE ({uc_cols})')
    
    ddl_parts.append('\n);')
    
    ddl = ''.join(ddl_parts)
    
    # Foreign Keys (retornar separadamente se skip_fks=True)
    fk_statements = []
    if skip_fks:
        for fk in constraints['foreign_keys']:
            on_delete = f' ON DELETE {fk["on_delete"]}' if fk['on_delete'] and fk['on_delete'] != 'NO ACTION' else ''
            on_update = f' ON UPDATE {fk["on_update"]}' if fk['on_update'] and fk['on_update'] != 'NO ACTION' else ''
            
            fk_stmt = f'ALTER TABLE {schema}.{table} ADD CONSTRAINT {fk["constraint_name"]} '
            fk_stmt += f'FOREIGN KEY ("{fk["column"]}") '
            fk_stmt += f'REFERENCES {fk["ref_schema"]}.{fk["ref_table"]}("{fk["ref_column"]}")'
            fk_stmt += on_delete + on_update + ';'
            fk_statements.append(fk_stmt)
    
    # Indexes
    idx_statements = []
    for idx in constraints['indexes']:
        idx_cols = ', '.join([f'"{col}"' for col in idx['columns']])
        idx_stmt = f'CREATE INDEX IF NOT EXISTS {idx["name"]} ON {schema}.{table} ({idx_cols});'
        idx_statements.append(idx_stmt)
    
    # Combinar CREATE TABLE com INDEXES
    full_ddl = ddl
    if idx_statements:
        full_ddl += '\n' + '\n'.join(idx_statements)
    
    return full_ddl, fk_statements


def build_column_definition(col_name: str, col_info: Dict) -> str:
    """Constrói a definição de coluna para ALTER TABLE ADD COLUMN"""
    data_type = col_info['data_type']
    max_length = col_info['max_length']
    is_nullable = col_info['is_nullable']
    col_default = col_info['default']
    udt_name = col_info['udt_name']
    
    # Tratar tipos USER-DEFINED
    if data_type == 'USER-DEFINED':
        col_type = udt_name
    elif data_type == 'character varying' and max_length:
        col_type = f'VARCHAR({max_length})'
    elif data_type == 'character varying':
        col_type = 'VARCHAR'
    elif data_type == 'character' and max_length:
        col_type = f'CHAR({max_length})'
    elif data_type == 'timestamp without time zone':
        col_type = 'TIMESTAMP WITHOUT TIME ZONE'
    elif data_type == 'timestamp with time zone':
        col_type = 'TIMESTAMP WITH TIME ZONE'
    elif data_type == 'double precision':
        col_type = 'DOUBLE PRECISION'
    else:
        col_type = data_type.upper()
    
    # Construir definição
    definition = f'"{col_name}" {col_type}'
    
    # Nullable
    if is_nullable == 'NO':
        definition += ' NOT NULL'
    
    # Default
    if col_default:
        definition += f' DEFAULT {col_default}'
    
    return definition


def migrate_schema(dev_conn, prod_conn, schema: str, dry_run: bool = False):
    """Migra um schema específico do DEV para PROD"""
    print_info(f"Processando schema: {schema}")
    
    # Verificar se o schema existe no PROD
    with prod_conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.schemata 
            WHERE schema_name = %s
        """, (schema,))
        schema_exists = cur.fetchone()[0] > 0
    
    if not schema_exists:
        if dry_run:
            print_warning(f"  [DRY-RUN] Schema {schema} não existe no PROD. Seria criado...")
        else:
            print_warning(f"  Schema {schema} não existe no PROD. Criando...")
            with prod_conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
            prod_conn.commit()
            print_success(f"  Schema {schema} criado")
    
    # Obter tabelas
    dev_tables = get_tables_in_schema(dev_conn, schema)
    prod_tables = get_tables_in_schema(prod_conn, schema)
    
    # Tabelas que existem no DEV mas não no PROD
    missing_tables = dev_tables - prod_tables
    
    # Tabelas que existem em ambos (precisam verificar colunas)
    common_tables = dev_tables & prod_tables
    
    print_info(f"  Tabelas no DEV: {len(dev_tables)}")
    print_info(f"  Tabelas no PROD: {len(prod_tables)}")
    print_info(f"  Tabelas faltando no PROD: {len(missing_tables)}")
    print_info(f"  Tabelas comuns: {len(common_tables)}")
    
    # Criar tabelas faltantes (SEM foreign keys primeiro)
    pending_fks = []  # Armazenar FKs para criar depois
    
    for table in sorted(missing_tables):
        print_info(f"\n  Criando tabela: {schema}.{table}")
        
        if dry_run:
            print_warning(f"    [DRY-RUN] Tabela {schema}.{table} seria criada")
            continue
        
        # Construir DDL via Python (sem FKs)
        try:
            ddl, fk_statements = build_create_table_ddl(dev_conn, schema, table, skip_fks=True)
            
            if ddl:
                with prod_conn.cursor() as cur:
                    # Executar cada statement separadamente
                    for statement in ddl.split(';'):
                        statement = statement.strip()
                        if statement:
                            cur.execute(statement)
                prod_conn.commit()
                print_success(f"    Tabela {schema}.{table} criada com sucesso")
                
                # Guardar FKs para criar depois
                if fk_statements:
                    pending_fks.extend([(schema, table, fk) for fk in fk_statements])
            else:
                print_warning(f"    Não foi possível gerar DDL para {schema}.{table}")
        except Exception as e:
            print_error(f"    Erro ao criar tabela {schema}.{table}: {e}")
            prod_conn.rollback()
    
    # Agora criar as Foreign Keys
    if pending_fks and not dry_run:
        print_info(f"\n  Criando Foreign Keys ({len(pending_fks)} constraints)")
        for schema_name, table_name, fk_stmt in pending_fks:
            try:
                with prod_conn.cursor() as cur:
                    cur.execute(fk_stmt)
                prod_conn.commit()
            except Exception as e:
                print_warning(f"    Erro ao criar FK em {schema_name}.{table_name}: {e}")
                prod_conn.rollback()
    
    # Verificar colunas nas tabelas comuns
    for table in sorted(common_tables):
        dev_columns = get_table_columns(dev_conn, schema, table)
        prod_columns = get_table_columns(prod_conn, schema, table)
        
        missing_columns = set(dev_columns.keys()) - set(prod_columns.keys())
        
        if missing_columns:
            print_info(f"\n  Tabela {schema}.{table} - Adicionando {len(missing_columns)} coluna(s)")
            
            for col in sorted(missing_columns):
                col_def = build_column_definition(col, dev_columns[col])
                
                if dry_run:
                    print_warning(f"    [DRY-RUN] Coluna {col} seria adicionada: {col_def}")
                    continue
                
                try:
                    with prod_conn.cursor() as cur:
                        alter_sql = sql.SQL("ALTER TABLE {}.{} ADD COLUMN IF NOT EXISTS {}").format(
                            sql.Identifier(schema),
                            sql.Identifier(table),
                            sql.SQL(col_def)
                        )
                        cur.execute(alter_sql)
                    prod_conn.commit()
                    print_success(f"    Coluna {col} adicionada")
                except Exception as e:
                    print_error(f"    Erro ao adicionar coluna {col}: {e}")
                    prod_conn.rollback()


def main():
    # Parser de argumentos
    parser = argparse.ArgumentParser(
        description='Migração de tabelas e colunas do DEV para PROD',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python migrate_dev_to_prod.py              # Execução normal (pede confirmação)
  python migrate_dev_to_prod.py --dry-run    # Apenas mostra o que seria feito
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Apenas mostra o que seria feito, sem executar nenhuma mudança'
    )
    
    args = parser.parse_args()
    dry_run = args.dry_run
    
    if dry_run:
        print_header("MIGRAÇÃO DEV → PROD (MODO DRY-RUN)")
        print_warning("MODO DRY-RUN ATIVADO: Nenhuma mudança será feita no banco!")
    else:
        print_header("MIGRAÇÃO DEV → PROD")
    
    print_info(f"DEV:  {DEV_DB}")
    print_info(f"PROD: {PROD_DB}")
    
    # Confirmar execução (apenas se não for dry-run)
    if not dry_run:
        print_warning("\nATENÇÃO: Este script irá modificar o banco de produção!")
        response = input("Deseja continuar? (sim/não): ").strip().lower()
        
        if response not in ['sim', 's', 'yes', 'y']:
            print_info("Operação cancelada pelo usuário.")
            sys.exit(0)
    
    print_header("CONECTANDO AOS BANCOS")
    
    try:
        # Conectar aos bancos
        print_info("Conectando ao DEV...")
        dev_conn = psycopg2.connect(DEV_DB)
        dev_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print_success("Conectado ao DEV")
        
        print_info("Conectando ao PROD...")
        prod_conn = psycopg2.connect(PROD_DB)
        prod_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print_success("Conectado ao PROD")
        
        # Obter schemas
        print_header("OBTENDO SCHEMAS")
        dev_schemas = get_schemas(dev_conn)
        prod_schemas = get_schemas(prod_conn)
        
        print_info(f"Schemas no DEV: {len(dev_schemas)}")
        print_info(f"Schemas no PROD: {len(prod_schemas)}")
        
        missing_schemas = set(dev_schemas) - set(prod_schemas)
        if missing_schemas:
            print_warning(f"Schemas faltando no PROD: {', '.join(sorted(missing_schemas))}")
        
        # Migrar cada schema
        print_header("MIGRANDO SCHEMAS")
        
        for schema in dev_schemas:
            migrate_schema(dev_conn, prod_conn, schema, dry_run)
        
        # Fechar conexões
        dev_conn.close()
        prod_conn.close()
        
        if dry_run:
            print_header("DRY-RUN CONCLUÍDO!")
            print_info("Nenhuma mudança foi feita no banco de produção.")
            print_info("Execute sem --dry-run para aplicar as mudanças.")
        else:
            print_header("MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            print_success("Todas as tabelas e colunas foram sincronizadas.")
        
    except psycopg2.Error as e:
        print_error(f"Erro de banco de dados: {e}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Erro inesperado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
