import requests
import json

# URL base do servidor
BASE_URL = "http://localhost:5000"

def get_auth_token():
    """Obtém um token JWT válido"""
    login_data = {
        "email": "admin@example.com",  # Substitua por um email válido
        "password": "admin123"         # Substitua por uma senha válida
    }
    
    try:
        response = requests.post(f"{BASE_URL}/login", json=login_data)
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token')
        else:
            print(f"Erro no login: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Erro ao fazer login: {e}")
        return None

def test_avaliacoes_route(token):
    """Testa a rota de avaliações com os parâmetros problemáticos"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    params = {
        "estado": "ALAGOAS",
        "municipio": "618f56d1-2167-439e-bf0b-d3d2be54271c"
    }
    
    try:
        response = requests.get(
            f"{BASE_URL}/evaluation-results/opcoes-filtros/avaliacoes",
            headers=headers,
            params=params
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Sucesso! Avaliações encontradas: {data.get('total', 0)}")
            return True
        else:
            print(f"❌ Erro na requisição")
            return False
            
    except Exception as e:
        print(f"Erro ao testar rota: {e}")
        return False

def main():
    print("🔐 Obtendo token de autenticação...")
    token = get_auth_token()
    
    if not token:
        print("❌ Não foi possível obter o token de autenticação")
        return
    
    print(f"✅ Token obtido: {token[:50]}...")
    
    print("\n🧪 Testando rota de avaliações...")
    success = test_avaliacoes_route(token)
    
    if success:
        print("\n🎉 Teste concluído com sucesso!")
    else:
        print("\n💥 Teste falhou!")

if __name__ == "__main__":
    main() 