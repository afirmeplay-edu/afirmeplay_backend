"""
Script para testar estatísticas por disciplina via API
"""
import requests
import json

API_URL = "http://localhost:5000"
EVALUATION_ID = "00e2ef94-cc5e-4a53-b06a-38d532e6a6d4"
CITY_ID = "0f93f076-c274-4515-98df-302bbf7e9b15"

TOKEN = input("Cole seu token JWT: ").strip()

print("=" * 80)
print("Testando Estatísticas da Avaliação")
print("=" * 80)

headers = {}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"

# Testar rota de análise das avaliações
print("\n1️⃣  Testando rota: /evaluation-results/avaliacoes")
print("-" * 80)

try:
    response = requests.get(
        f"{API_URL}/evaluation-results/avaliacoes",
        params={
            "estado": "ALAGOAS",
            "municipio": CITY_ID,
            "avaliacao": EVALUATION_ID,
            "page": 1,
            "per_page": 10
        },
        headers=headers,
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✅ Status: {response.status_code}")
        print(f"\nEstatísticas Gerais:")
        stats = data.get('estatisticas_gerais', {})
        print(f"  Total alunos: {stats.get('total_alunos')}")
        print(f"  Alunos participantes: {stats.get('alunos_participantes')}")
        
        dist = stats.get('distribuicao_classificacao_geral', {})
        print(f"\n  Distribuição Geral:")
        print(f"    Abaixo do Básico: {dist.get('abaixo_do_basico', 0)}")
        print(f"    Básico: {dist.get('basico', 0)}")
        print(f"    Adequado: {dist.get('adequado', 0)}")
        print(f"    Avançado: {dist.get('avancado', 0)}")
        
        print(f"\nResultados por Disciplina:")
        for disciplina in data.get('resultados_por_disciplina', []):
            print(f"\n  📚 {disciplina.get('disciplina')}:")
            print(f"     Total alunos: {disciplina.get('total_alunos')}")
            print(f"     Média nota: {disciplina.get('media_nota')}")
            print(f"     Média proficiência: {disciplina.get('media_proficiencia')}")
            
            dist_disc = disciplina.get('distribuicao_classificacao', {})
            print(f"     Distribuição:")
            print(f"       Abaixo do Básico: {dist_disc.get('abaixo_do_basico', 0)}")
            print(f"       Básico: {dist_disc.get('basico', 0)}")
            print(f"       Adequado: {dist_disc.get('adequado', 0)}")
            print(f"       Avançado: {dist_disc.get('avancado', 0)}")
    else:
        print(f"❌ Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
except Exception as e:
    print(f"❌ Erro: {str(e)}")

# Testar rota de relatórios
print("\n\n2️⃣  Testando rota: /reports/dados-json")
print("-" * 80)

try:
    response = requests.get(
        f"{API_URL}/reports/dados-json/{EVALUATION_ID}",
        params={
            "city_id": CITY_ID
        },
        headers=headers,
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"✅ Status: {response.status_code}")
        
        # Verificar se tem estatísticas por disciplina
        if 'estatisticas_por_disciplina' in data:
            print(f"\nEstatísticas por Disciplina (Reports):")
            for disciplina in data.get('estatisticas_por_disciplina', []):
                print(f"\n  📚 {disciplina.get('disciplina')}:")
                print(f"     Total alunos: {disciplina.get('total_alunos')}")
                print(f"     Média nota: {disciplina.get('media_nota')}")
                
                dist_disc = disciplina.get('distribuicao_classificacao', {})
                print(f"     Distribuição:")
                print(f"       Abaixo do Básico: {dist_disc.get('abaixo_do_basico', 0)}")
                print(f"       Básico: {dist_disc.get('basico', 0)}")
                print(f"       Adequado: {dist_disc.get('adequado', 0)}")
                print(f"       Avançado: {dist_disc.get('avancado', 0)}")
        
        # Verificar estatísticas gerais
        if 'estatisticas_gerais' in data:
            stats = data.get('estatisticas_gerais', {})
            print(f"\n  Estatísticas Gerais (Reports):")
            print(f"    Total alunos: {stats.get('total_alunos')}")
            
            dist = stats.get('distribuicao_classificacao_geral', {})
            print(f"    Distribuição Geral:")
            print(f"      Abaixo do Básico: {dist.get('abaixo_do_basico', 0)}")
            print(f"      Básico: {dist.get('basico', 0)}")
            print(f"      Adequado: {dist.get('adequado', 0)}")
            print(f"      Avançado: {dist.get('avancado', 0)}")
            
    elif response.status_code == 202:
        print(f"⏳ Status: {response.status_code} - Relatório sendo processado")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    else:
        print(f"❌ Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
except Exception as e:
    print(f"❌ Erro: {str(e)}")

print("\n" + "=" * 80)
print("✅ Teste concluído!")
print("=" * 80)
