"""
Script para investigar filtros e escopos
"""
import requests
import json

API_URL = "http://localhost:5000"
EVALUATION_ID = "00e2ef94-cc5e-4a53-b06a-38d532e6a6d4"
CITY_ID = "0f93f076-c274-4515-98df-302bbf7e9b15"

TOKEN = input("Cole seu token JWT: ").strip()

print("=" * 80)
print("Investigando Filtros e Escopos")
print("=" * 80)

headers = {}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"

# 1. Buscar opções de filtros
print("\n1️⃣  Buscando opções de filtros disponíveis...")
print("-" * 80)

try:
    response = requests.get(
        f"{API_URL}/evaluation-results/opcoes-filtros",
        params={
            "estado": "ALAGOAS",
            "municipio": CITY_ID
        },
        headers=headers,
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✅ Status: {response.status_code}")
        print(f"\nAvaliações disponíveis: {len(data.get('avaliacoes', []))}")
        
        for aval in data.get('avaliacoes', []):
            print(f"  - {aval.get('nome')} (ID: {aval.get('id')})")
            if aval.get('id') == EVALUATION_ID:
                print(f"    ✅ Esta é a avaliação que estamos investigando!")
        
        print(f"\nEscolas disponíveis: {len(data.get('escolas', []))}")
        for escola in data.get('escolas', []):
            print(f"  - {escola.get('nome')} (ID: {escola.get('id')})")
        
    else:
        print(f"❌ Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
except Exception as e:
    print(f"❌ Erro: {str(e)}")

# 2. Buscar com escola específica
print("\n\n2️⃣  Buscando opções com avaliação específica...")
print("-" * 80)

try:
    response = requests.get(
        f"{API_URL}/evaluation-results/opcoes-filtros",
        params={
            "estado": "ALAGOAS",
            "municipio": CITY_ID,
            "avaliacao": EVALUATION_ID
        },
        headers=headers,
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✅ Status: {response.status_code}")
        print(f"\nEscolas onde a avaliação foi aplicada: {len(data.get('escolas', []))}")
        
        escolas = data.get('escolas', [])
        for escola in escolas:
            print(f"  - {escola.get('nome')} (ID: {escola.get('id')})")
        
        if escolas:
            primeira_escola = escolas[0]
            escola_id = primeira_escola.get('id')
            
            print(f"\n3️⃣  Testando com escola específica: {primeira_escola.get('nome')}")
            print("-" * 80)
            
            # Testar com escola específica
            response2 = requests.get(
                f"{API_URL}/evaluation-results/avaliacoes",
                params={
                    "estado": "ALAGOAS",
                    "municipio": CITY_ID,
                    "avaliacao": EVALUATION_ID,
                    "escola": escola_id,
                    "page": 1,
                    "per_page": 10
                },
                headers=headers,
                timeout=30
            )
            
            if response2.status_code == 200:
                data2 = response2.json()
                
                print(f"✅ Status: {response2.status_code}")
                
                stats = data2.get('estatisticas_gerais', {})
                print(f"\nEstatísticas Gerais:")
                print(f"  Total alunos: {stats.get('total_alunos')}")
                print(f"  Alunos participantes: {stats.get('alunos_participantes')}")
                
                dist = stats.get('distribuicao_classificacao_geral', {})
                print(f"\n  Distribuição Geral:")
                print(f"    Abaixo do Básico: {dist.get('abaixo_do_basico', 0)}")
                print(f"    Básico: {dist.get('basico', 0)}")
                print(f"    Adequado: {dist.get('adequado', 0)}")
                print(f"    Avançado: {dist.get('avancado', 0)}")
                
                print(f"\n  Resultados por Disciplina:")
                for disciplina in data2.get('resultados_por_disciplina', []):
                    print(f"\n    📚 {disciplina.get('disciplina')}:")
                    print(f"       Total alunos: {disciplina.get('total_alunos')}")
                    
                    dist_disc = disciplina.get('distribuicao_classificacao', {})
                    print(f"       Distribuição:")
                    print(f"         Abaixo do Básico: {dist_disc.get('abaixo_do_basico', 0)}")
                    print(f"         Básico: {dist_disc.get('basico', 0)}")
                    print(f"         Adequado: {dist_disc.get('adequado', 0)}")
                    print(f"         Avançado: {dist_disc.get('avancado', 0)}")
            else:
                print(f"❌ Status: {response2.status_code}")
                print(json.dumps(response2.json(), indent=2, ensure_ascii=False))
        else:
            print("⚠️  Nenhuma escola encontrada onde a avaliação foi aplicada")
        
    else:
        print(f"❌ Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
except Exception as e:
    print(f"❌ Erro: {str(e)}")

print("\n" + "=" * 80)
print("✅ Investigação concluída!")
print("=" * 80)
