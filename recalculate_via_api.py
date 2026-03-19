"""
Script para recalcular resultado via API
"""
import requests
import json

# Configurações
API_URL = "http://localhost:5000"
RESULT_ID = "bdda37a4-738f-4b5e-9a80-29352f21595f"

# Você precisa fornecer um token JWT válido
# Pegue do navegador ou faça login primeiro
TOKEN = input("Cole seu token JWT (ou pressione Enter para tentar sem autenticação): ").strip()
CITY_ID = input("Digite o city_id (UUID da cidade): ").strip()

if not CITY_ID:
    print("❌ city_id é obrigatório!")
    exit(1)

print("=" * 80)
print(f"Recalculando resultado: {RESULT_ID}")
print(f"City ID: {CITY_ID}")
print("=" * 80)

headers = {
    "Content-Type": "application/json"
}
if TOKEN:
    headers["Authorization"] = f"Bearer {TOKEN}"

body = {
    "city_id": CITY_ID
}

try:
    response = requests.post(
        f"{API_URL}/evaluation-results/result/{RESULT_ID}/recalculate",
        headers=headers,
        json=body,
        timeout=30
    )
    
    print(f"\nStatus Code: {response.status_code}")
    print("\nResposta:")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    
    if response.status_code == 200:
        print("\n" + "=" * 80)
        print("🎉 Resultado recalculado com sucesso!")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("❌ Erro ao recalcular")
        print("=" * 80)
        
except requests.exceptions.ConnectionError:
    print("\n❌ Erro: Não foi possível conectar ao servidor")
    print("   Certifique-se de que o servidor está rodando em http://localhost:5000")
except Exception as e:
    print(f"\n❌ Erro: {str(e)}")
