"""
Script para debug de avaliação via API
"""
import requests
import json

API_URL = "http://localhost:5000"
EVALUATION_ID = "00e2ef94-cc5e-4a53-b06a-38d532e6a6d4"
CITY_ID = "0f93f076-c274-4515-98df-302bbf7e9b15"

TOKEN = input("Cole seu token JWT: ").strip()

print("=" * 80)
print(f"Debug da Avaliação: {EVALUATION_ID}")
print(f"City ID: {CITY_ID}")
print("=" * 80)

headers = {}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"

try:
    response = requests.get(
        f"{API_URL}/evaluation-results/debug/{EVALUATION_ID}?city_id={CITY_ID}",
        headers=headers,
        timeout=30
    )
    
    print(f"\nStatus Code: {response.status_code}\n")
    
    if response.status_code == 200:
        data = response.json()
        
        print(f"📋 Avaliação: {data.get('test_title')}")
        print(f"   Schema: {data.get('schema')}")
        print(f"   Subjects Info: {data.get('test_subjects_info')}")
        print(f"\n👥 Total de Resultados: {data.get('total_results')}")
        print("-" * 80)
        
        for i, result in enumerate(data.get('results', []), 1):
            print(f"\n[{i}] Aluno: {result['student_name']} (ID: {result['student_id']})")
            print(f"    Nota Geral: {result['grade']}")
            print(f"    Proficiência Geral: {result['proficiency']}")
            print(f"    Classificação Geral: {result['classification']}")
            print(f"    Acertos: {result['correct_answers']}/{result['total_questions']}")
            
            if result.get('subject_results'):
                print(f"\n    📊 Resultados por Disciplina:")
                for subject_id, subject_data in result['subject_results'].items():
                    print(f"       - {subject_data.get('subject_name', subject_id)}:")
                    print(f"         Nota: {subject_data.get('grade')}")
                    print(f"         Proficiência: {subject_data.get('proficiency')}")
                    print(f"         Classificação: {subject_data.get('classification')}")
                    print(f"         Acertos: {subject_data.get('correct_answers')}/{subject_data.get('answered_questions')}")
            else:
                print(f"    ⚠️  Sem resultados por disciplina no JSON")
        
        print("\n" + "=" * 80)
        print("✅ Debug concluído!")
        print("=" * 80)
    else:
        print("Erro:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
except Exception as e:
    print(f"\n❌ Erro: {str(e)}")
