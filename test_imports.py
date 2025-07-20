#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script simples para testar se os imports estão funcionando
"""
import sys
import os

def test_imports():
    """Testa se os imports estão funcionando"""
    print("🧪 Testando imports...")
    
    try:
        # Testar import do modelo
        print("📦 Testando import do modelo EvaluationResult...")
        from app.models.evaluationResult import EvaluationResult
        print("✅ EvaluationResult importado com sucesso!")
        
        # Testar import do serviço
        print("📦 Testando import do serviço EvaluationResultService...")
        from app.services.evaluation_result_service import EvaluationResultService
        print("✅ EvaluationResultService importado com sucesso!")
        
        # Testar import das rotas
        print("📦 Testando import das rotas...")
        from app.routes.evaluation_results_routes import bp as evaluation_bp
        print("✅ Rotas de avaliação importadas com sucesso!")
        
        print("\n✅ Todos os imports funcionando corretamente!")
        return True
        
    except ImportError as e:
        print(f"❌ Erro de import: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1) 