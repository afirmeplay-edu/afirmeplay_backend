#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste para verificar conectividade Redis e Celery
Testa todas as conexões necessárias para o sistema de relatórios assíncronos
"""

import os
import sys
import time
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('app/.env')

# Cores para output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

def print_success(text):
    print(f"{Colors.GREEN}[OK] {text}{Colors.RESET}")

def print_error(text):
    print(f"{Colors.RED}[ERRO] {text}{Colors.RESET}")

def print_warning(text):
    print(f"{Colors.YELLOW}[AVISO] {text}{Colors.RESET}")

def print_info(text):
    print(f"  {text}")

# ============================================================================
# TESTE 1: Variáveis de Ambiente
# ============================================================================
print_header("TESTE 1: Variáveis de Ambiente")

env_vars = {
    'CELERY_BROKER_URL': os.getenv('CELERY_BROKER_URL'),
    'CELERY_RESULT_BACKEND': os.getenv('CELERY_RESULT_BACKEND'),
    'REDIS_URL': os.getenv('REDIS_URL'),
    'REDIS_PASSWORD': os.getenv('REDIS_PASSWORD'),
}

all_ok = True
for key, value in env_vars.items():
    if value:
        if key == 'REDIS_PASSWORD':
            print_success(f"{key}: {'*' * len(value)} (oculto)")
        else:
            print_success(f"{key}: {value}")
    else:
        print_error(f"{key}: NÃO DEFINIDO")
        all_ok = False

if not all_ok:
    print_error("\nAlgumas variáveis de ambiente não estão definidas!")
    sys.exit(1)

# ============================================================================
# TESTE 2: Conexão Direta ao Redis (redis-py)
# ============================================================================
print_header("TESTE 2: Conexão Direta ao Redis (redis-py)")

try:
    import redis
    
    # Testar conexão sem senha (URL original)
    redis_url_original = env_vars['REDIS_URL']
    print_info(f"Testando conexão com: {redis_url_original}")
    
    try:
        redis_client_original = redis.from_url(redis_url_original, decode_responses=True, socket_connect_timeout=5)
        redis_client_original.ping()
        print_success("Conexão sem senha: OK")
        redis_client_original.close()
    except redis.AuthenticationError:
        print_warning("Conexão sem senha: FALHOU (autenticação necessária)")
    except Exception as e:
        print_warning(f"Conexão sem senha: FALHOU ({type(e).__name__}: {str(e)})")
    
    # Testar conexão com senha
    if env_vars['REDIS_PASSWORD']:
        # Construir URL com senha
        if redis_url_original.startswith('redis://'):
            parts = redis_url_original.replace('redis://', '').split('/')
            host_port = parts[0]
            db = parts[1] if len(parts) > 1 else '0'
            redis_url_with_password = f'redis://:{env_vars["REDIS_PASSWORD"]}@{host_port}/{db}'
        else:
            redis_url_with_password = redis_url_original
        
        print_info(f"Testando conexão com senha: redis://:***@{host_port}/{db}")
        
        try:
            redis_client = redis.from_url(redis_url_with_password, decode_responses=True, socket_connect_timeout=5)
            result = redis_client.ping()
            if result:
                print_success("Conexão com senha: OK")
                
                # Testar operações básicas
                test_key = f"test_connection_{int(time.time())}"
                redis_client.set(test_key, "test_value", ex=10)
                value = redis_client.get(test_key)
                if value == "test_value":
                    print_success("Operações de leitura/escrita: OK")
                redis_client.delete(test_key)
                redis_client.close()
            else:
                print_error("Conexão com senha: PING retornou False")
        except redis.AuthenticationError:
            print_error("Conexão com senha: FALHOU (autenticação inválida)")
        except redis.ConnectionError as e:
            print_error(f"Conexão com senha: FALHOU (erro de conexão: {str(e)})")
        except Exception as e:
            print_error(f"Conexão com senha: FALHOU ({type(e).__name__}: {str(e)})")
    else:
        print_warning("REDIS_PASSWORD não definido, pulando teste com senha")
        
except ImportError:
    print_error("Biblioteca 'redis' não instalada. Execute: pip install redis")
    sys.exit(1)

# ============================================================================
# TESTE 3: Configuração do Celery (Broker e Result Backend)
# ============================================================================
print_header("TESTE 3: Configuração do Celery")

try:
    from app.report_analysis.celery_app import celery_app
    
    # Verificar configurações
    broker_url = celery_app.conf.broker_url
    result_backend = celery_app.conf.result_backend
    
    print_info(f"Broker URL: {broker_url}")
    print_info(f"Result Backend: {result_backend}")
    
    # Verificar URLs originais do .env
    env_broker = os.getenv('CELERY_BROKER_URL')
    env_backend = os.getenv('CELERY_RESULT_BACKEND')
    env_password = os.getenv('REDIS_PASSWORD')
    
    print_info(f"\nURLs do .env (antes da aplicacao da senha):")
    print_info(f"  CELERY_BROKER_URL: {env_broker}")
    print_info(f"  CELERY_RESULT_BACKEND: {env_backend}")
    print_info(f"  REDIS_PASSWORD definido: {'Sim' if env_password else 'Nao'}")
    
    # Verificar se as URLs do Celery têm senha
    expected_broker = f'redis://:{env_password}@{env_broker.replace("redis://", "").split("/")[0]}/{env_broker.split("/")[-1] if "/" in env_broker else "0"}'
    expected_backend = f'redis://:{env_password}@{env_backend.replace("redis://", "").split("/")[0]}/{env_backend.split("/")[-1] if "/" in env_backend else "0"}'
    
    print_info(f"\nURLs esperadas (com senha):")
    print_info(f"  Broker esperado: redis://:***@{env_broker.replace('redis://', '').split('/')[0]}/{env_broker.split('/')[-1] if '/' in env_broker else '0'}")
    print_info(f"  Backend esperado: redis://:***@{env_backend.replace('redis://', '').split('/')[0]}/{env_backend.split('/')[-1] if '/' in env_backend else '0'}")
    
    # Verificar se as URLs têm senha
    has_password_broker = '@' in broker_url and ':' in broker_url.split('@')[0]
    has_password_backend = '@' in result_backend and ':' in result_backend.split('@')[0]
    
    if has_password_broker:
        print_success("Broker URL contém senha")
    else:
        print_warning("Broker URL NÃO contém senha (pode falhar se Redis requer autenticação)")
    
    if has_password_backend:
        print_success("Result Backend URL contém senha")
    else:
        print_warning("Result Backend URL NÃO contém senha (pode falhar se Redis requer autenticação)")
    
    # Testar conexão do broker
    print_info("\nTestando conexão do Broker...")
    try:
        with celery_app.connection() as conn:
            conn.ensure_connection(max_retries=3, timeout=5)
            print_success("Conexão do Broker: OK")
    except Exception as e:
        print_error(f"Conexão do Broker: FALHOU ({type(e).__name__}: {str(e)})")
    
    # Testar conexão do result backend
    print_info("Testando conexão do Result Backend...")
    try:
        backend = celery_app.backend
        # Tentar uma operação simples
        backend.client.ping()
        print_success("Conexão do Result Backend: OK")
    except Exception as e:
        print_error(f"Conexão do Result Backend: FALHOU ({type(e).__name__}: {str(e)})")
        print_info(f"Detalhes do erro: {str(e)}")
        
except ImportError as e:
    print_error(f"Não foi possível importar celery_app: {str(e)}")
    sys.exit(1)
except Exception as e:
    print_error(f"Erro ao testar Celery: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TESTE 4: Enviar Task Simples
# ============================================================================
print_header("TESTE 4: Enviar Task Simples ao Celery")

try:
    from app.report_analysis.celery_app import celery_app
    
    # Criar uma task de teste simples
    @celery_app.task(name='test_connection_task', bind=True)
    def test_task(self):
        return {"status": "success", "message": "Task executada com sucesso"}
    
    print_info("Enviando task de teste...")
    
    try:
        # Enviar task
        result = test_task.delay()
        print_success(f"Task enviada com sucesso! Task ID: {result.id}")
        
        # Tentar obter resultado (com timeout)
        print_info("Aguardando resultado (timeout: 10s)...")
        try:
            task_result = result.get(timeout=10)
            print_success(f"Task executada com sucesso! Resultado: {task_result}")
        except Exception as e:
            print_warning(f"Não foi possível obter resultado da task: {type(e).__name__}: {str(e)}")
            print_info("Isso pode ser normal se o worker não estiver rodando")
            print_info(f"Task ID: {result.id} - Verifique no worker se a task foi processada")
            
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        print_error(f"Erro ao enviar task: {error_type}: {error_msg}")
        
        if "retry" in error_msg.lower() or "reconnect" in error_msg.lower():
            print_warning("\nEste erro geralmente indica:")
            print_info("1. Celery não consegue se conectar ao Redis result backend")
            print_info("2. Verifique se a senha está sendo aplicada corretamente")
            print_info("3. Verifique se o Redis está acessível da máquina atual")
            print_info("4. Verifique se o worker está rodando")
        
except Exception as e:
    print_error(f"Erro ao criar/enviar task de teste: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TESTE 5: Verificar Worker (se disponível)
# ============================================================================
print_header("TESTE 5: Status do Celery Worker")

try:
    from app.report_analysis.celery_app import celery_app
    
    # Tentar inspecionar workers ativos
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        
        if active_workers:
            print_success(f"Workers ativos encontrados: {len(active_workers)}")
            for worker_name, tasks in active_workers.items():
                print_info(f"  - {worker_name}: {len(tasks)} tasks ativas")
        else:
            print_warning("Nenhum worker ativo encontrado")
            print_info("Certifique-se de que o worker está rodando:")
            print_info("  celery -A app.report_analysis.celery_app worker --loglevel=info --pool=solo")
            
    except Exception as e:
        print_warning(f"Não foi possível verificar workers: {type(e).__name__}: {str(e)}")
        print_info("Isso é normal se o worker não estiver rodando ou não estiver acessível")
        
except Exception as e:
    print_warning(f"Erro ao verificar workers: {type(e).__name__}: {str(e)}")

# ============================================================================
# RESUMO FINAL
# ============================================================================
print_header("RESUMO DOS TESTES")

print_info("Verifique os resultados acima para identificar problemas.")
print_info("\nProblemas comuns e soluções:")
print_info("1. Se 'Conexao com senha: FALHOU' -> Verifique REDIS_PASSWORD no .env")
print_info("2. Se 'Result Backend: FALHOU' -> Verifique se a senha esta na URL do Celery")
print_info("3. Se 'Erro ao enviar task' -> Verifique se o worker esta rodando")
print_info("4. Se 'Nenhum worker ativo' -> Inicie o worker com: celery -A app.report_analysis.celery_app worker --loglevel=info --pool=solo")

print("\n" + "="*60 + "\n")

