#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste simples da correção em lote síncrona
"""

import requests
import json
import base64
from PIL import Image
import io
import numpy as np

def create_test_image():
    """Cria uma imagem de teste simples"""
    # Criar imagem RGB 800x600
    img_array = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
    img = Image.fromarray(img_array)
    
    # Converter para base64
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    return f"data:image/jpeg;base64,{img_base64}"

def test_batch_correction():
    """Testa a correção em lote síncrona"""
    
    # URL do backend
    base_url = "http://localhost:5000"
    test_id = "eafb4493-e47a-43e2-98ea-70f75bf6b103"
    
    # Token de autenticação (substitua pelo seu token real)
    token = "seu_token_aqui"
    
    # Preparar dados de teste
    images = [
        {
            "student_id": "ae3b4c91-4f9e-4e0e-bd97-ff1d40b6b22b",
            "student_name": "João Silva",
            "image": create_test_image()
        },
        {
            "student_id": "d0b2cc32-a5c5-4a53-b6de-d27b47a4e9aa",
            "student_name": "Maria Santos", 
            "image": create_test_image()
        }
    ]
    
    # Headers
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Dados da requisição
    data = {
        "images": images
    }
    
    print("🚀 Testando correção em lote síncrona...")
    print(f"📡 URL: {base_url}/physical-tests/test/{test_id}/batch-process-correction")
    print(f"📊 Imagens: {len(images)}")
    
    try:
        # Fazer requisição
        response = requests.post(
            f"{base_url}/physical-tests/test/{test_id}/batch-process-correction",
            headers=headers,
            json=data,
            timeout=60  # 60 segundos de timeout
        )
        
        print(f"📡 Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Sucesso!")
            print(f"📊 Total de imagens: {result['total_images']}")
            print(f"✅ Sucessos: {result['successful_corrections']}")
            print(f"❌ Falhas: {result['failed_corrections']}")
            print(f"📈 Taxa de sucesso: {result['success_rate']}%")
            
            if result['errors']:
                print("⚠️ Erros:")
                for error in result['errors']:
                    print(f"  - {error}")
            
            print("\n📋 Resultados detalhados:")
            for i, res in enumerate(result['results']):
                if res.get('success', False):
                    print(f"  {i+1}. {res['student_name']}: {res['correct_answers']}/{res['total_questions']} acertos ({res['score_percentage']}%)")
                else:
                    print(f"  {i+1}. {res['student_name']}: ERRO - {res.get('error', 'Erro desconhecido')}")
                    
        else:
            print("❌ Erro na requisição:")
            try:
                error_data = response.json()
                print(f"  Erro: {error_data.get('error', 'Erro desconhecido')}")
            except:
                print(f"  Resposta: {response.text}")
                
    except requests.exceptions.Timeout:
        print("⏰ Timeout - A requisição demorou mais de 60 segundos")
    except requests.exceptions.ConnectionError:
        print("🔌 Erro de conexão - Verifique se o backend está rodando")
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")

if __name__ == "__main__":
    print("🧪 Teste da Correção em Lote Síncrona")
    print("=" * 50)
    
    # Verificar se o backend está rodando
    try:
        response = requests.get("http://localhost:5000", timeout=5)
        print("✅ Backend está rodando")
    except:
        print("❌ Backend não está rodando. Execute: python run.py")
        exit(1)
    
    test_batch_correction()
