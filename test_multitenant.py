"""
Script de Teste: Sistema Multi-Tenant
======================================

Este script testa a resolução automática de schema PostgreSQL
baseada em JWT, headers e subdomínio.

Uso:
    python test_multitenant.py

Requisitos:
    - Servidor Flask rodando
    - Usuários criados no banco
    - Cidades com slugs configurados
"""

import requests
import json
from typing import Dict, Optional

# Configuração
BASE_URL = "http://localhost:5000"
ADMIN_EMAIL = "admin@sistema.com"
ADMIN_PASSWORD = "admin123"
PROFESSOR_EMAIL = "aluno1@afirmeplay.com.br"
PROFESSOR_PASSWORD = "aluno1@innovaplay"


class Colors:
    """Cores ANSI para output colorido"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_test(name: str, status: str, details: str = ""):
    """Imprime resultado de um teste"""
    color = Colors.GREEN if status == "✅ PASS" else Colors.RED
    print(f"{color}{status}{Colors.END} {Colors.BOLD}{name}{Colors.END}")
    if details:
        print(f"  {details}")


def login(email: str, password: str) -> Dict:
    """Faz login e retorna dados do usuário e token"""
    response = requests.post(
        f"{BASE_URL}/login",
        json={"registration": email, "password": password}
    )
    
    if response.status_code == 200:
        data = response.json()
        return {
            "token": data.get("token"),
            "user": data.get("user")
        }
    else:
        raise Exception(f"Login falhou: {response.text}")


def test_user_login():
    """Teste 1: Login de usuário comum"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}TESTE 1: Login de Usuário Comum{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    try:
        data = login(PROFESSOR_EMAIL, PROFESSOR_PASSWORD)
        user = data["user"]
        
        if user.get("tenant_id") and user.get("city_slug"):
            print_test(
                "Login professor com tenant_id",
                "✅ PASS",
                f"tenant_id: {user['tenant_id']}, slug: {user['city_slug']}"
            )
        else:
            print_test(
                "Login professor com tenant_id",
                "❌ FAIL",
                "tenant_id ou city_slug ausente"
            )
            
        return data["token"]
        
    except Exception as e:
        print_test("Login professor", "❌ FAIL", str(e))
        return None


def test_admin_login():
    """Teste 2: Login de admin"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}TESTE 2: Login de Admin{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    try:
        data = login(ADMIN_EMAIL, ADMIN_PASSWORD)
        user = data["user"]
        
        if user.get("tenant_id") is None:
            print_test(
                "Login admin sem tenant_id",
                "✅ PASS",
                f"tenant_id: {user['tenant_id']} (correto para admin)"
            )
        else:
            print_test(
                "Login admin sem tenant_id",
                "❌ FAIL",
                "Admin não deveria ter tenant_id fixo"
            )
            
        return data["token"]
        
    except Exception as e:
        print_test("Login admin", "❌ FAIL", str(e))
        return None


def test_user_access_tenant_route(token: str):
    """Teste 3: Usuário comum acessa rota tenant"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}TESTE 3: Usuário Comum → Rota Tenant{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/school", headers=headers)
        
        if response.status_code == 200:
            schools = response.json()
            print_test(
                "Acesso a /school",
                "✅ PASS",
                f"Retornou {len(schools)} escola(s)"
            )
        else:
            print_test(
                "Acesso a /school",
                "❌ FAIL",
                f"Status {response.status_code}: {response.text}"
            )
            
    except Exception as e:
        print_test("Acesso rota tenant", "❌ FAIL", str(e))


def test_admin_global_route(token: str):
    """Teste 4: Admin acessa rota global sem contexto"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}TESTE 4: Admin → Rota Global (sem contexto){Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/city", headers=headers)
        
        if response.status_code == 200:
            cities = response.json()
            print_test(
                "Acesso a /city",
                "✅ PASS",
                f"Retornou {len(cities)} cidade(s)"
            )
        else:
            print_test(
                "Acesso a /city",
                "❌ FAIL",
                f"Status {response.status_code}: {response.text}"
            )
            
    except Exception as e:
        print_test("Acesso rota global", "❌ FAIL", str(e))


def test_admin_tenant_route_without_context(token: str):
    """Teste 5: Admin acessa rota tenant SEM contexto (deve falhar)"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}TESTE 5: Admin → Rota Tenant SEM Contexto{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.get(f"{BASE_URL}/school", headers=headers)
        
        if response.status_code == 403:
            error = response.json()
            print_test(
                "Bloqueio esperado",
                "✅ PASS",
                f"403 retornado: {error.get('erro')}"
            )
        else:
            print_test(
                "Bloqueio esperado",
                "❌ FAIL",
                f"Deveria retornar 403, retornou {response.status_code}"
            )
            
    except Exception as e:
        print_test("Bloqueio de rota tenant", "❌ FAIL", str(e))


def test_admin_with_city_header(token: str, city_slug: str):
    """Teste 6: Admin acessa rota tenant COM header X-City-Slug"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}TESTE 6: Admin → Rota Tenant COM X-City-Slug{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-City-Slug": city_slug
    }
    
    try:
        response = requests.get(f"{BASE_URL}/school", headers=headers)
        
        if response.status_code == 200:
            schools = response.json()
            print_test(
                f"Acesso com X-City-Slug: {city_slug}",
                "✅ PASS",
                f"Retornou {len(schools)} escola(s) de {city_slug}"
            )
        elif response.status_code == 404:
            print_test(
                f"Slug '{city_slug}' não encontrado",
                "⚠️ SKIP",
                "Ajuste CITY_SLUG_TEST no script"
            )
        else:
            print_test(
                f"Acesso com X-City-Slug",
                "❌ FAIL",
                f"Status {response.status_code}: {response.text}"
            )
            
    except Exception as e:
        print_test("Acesso com header", "❌ FAIL", str(e))


def test_user_header_ignored(token: str, city_slug: str):
    """Teste 7: Usuário comum tenta usar header (deve ser ignorado)"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}TESTE 7: Usuário Comum com Header (Segurança){Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    # Primeiro, obter escolas sem header
    headers1 = {"Authorization": f"Bearer {token}"}
    response1 = requests.get(f"{BASE_URL}/school", headers=headers1)
    
    # Depois, tentar com header de outra cidade
    headers2 = {
        "Authorization": f"Bearer {token}",
        "X-City-Slug": city_slug
    }
    response2 = requests.get(f"{BASE_URL}/school", headers=headers2)
    
    if response1.status_code == 200 and response2.status_code == 200:
        schools1 = response1.json()
        schools2 = response2.json()
        
        # Devem retornar as MESMAS escolas (header ignorado)
        if schools1 == schools2:
            print_test(
                "Header ignorado para usuário comum",
                "✅ PASS",
                "Retornou mesmos dados (header foi ignorado)"
            )
        else:
            print_test(
                "Header ignorado",
                "❌ FAIL",
                "Dados diferentes - header NÃO foi ignorado (falha de segurança!)"
            )
    else:
        print_test(
            "Header ignorado",
            "⚠️ SKIP",
            "Não foi possível testar (erro nas requisições)"
        )


def test_invalid_slug(token: str):
    """Teste 8: Admin com slug inválido"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}TESTE 8: Admin com Slug Inválido{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-City-Slug": "cidade-que-nao-existe-123"
    }
    
    try:
        response = requests.get(f"{BASE_URL}/school", headers=headers)
        
        if response.status_code == 404:
            error = response.json()
            print_test(
                "Erro 404 para slug inválido",
                "✅ PASS",
                f"Mensagem: {error.get('erro')}"
            )
        else:
            print_test(
                "Erro 404 esperado",
                "❌ FAIL",
                f"Status {response.status_code} retornado (esperava 404)"
            )
            
    except Exception as e:
        print_test("Validação de slug", "❌ FAIL", str(e))


def run_all_tests():
    """Executa todos os testes"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}  TESTES DO SISTEMA MULTI-TENANT{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}")
    
    # Obter slug de cidade para testes (ajustar conforme seu banco)
    CITY_SLUG_TEST = "jiparana"  # ← AJUSTAR CONFORME SEU BANCO
    
    # Teste 1: Login usuário comum
    user_token = test_user_login()
    
    # Teste 2: Login admin
    admin_token = test_admin_login()
    
    if user_token:
        # Teste 3: Usuário acessa rota tenant
        test_user_access_tenant_route(user_token)
        
        # Teste 7: Usuário tenta usar header (ignorado)
        test_user_header_ignored(user_token, CITY_SLUG_TEST)
    
    if admin_token:
        # Teste 4: Admin acessa rota global
        test_admin_global_route(admin_token)
        
        # Teste 5: Admin tenta rota tenant sem contexto
        test_admin_tenant_route_without_context(admin_token)
        
        # Teste 6: Admin com header válido
        test_admin_with_city_header(admin_token, CITY_SLUG_TEST)
        
        # Teste 8: Admin com slug inválido
        test_invalid_slug(admin_token)
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}  FIM DOS TESTES{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")


if __name__ == "__main__":
    try:
        run_all_tests()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Testes interrompidos pelo usuário{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.RED}Erro ao executar testes: {e}{Colors.END}")
