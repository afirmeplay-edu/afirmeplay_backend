#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para testar a análise de IA do sistema de relatórios.

Uso:
    python test_ai_analysis.py [evaluation_id] [scope_type] [scope_id]

Exemplos:
    python test_ai_analysis.py
    python test_ai_analysis.py <test_id>
    python test_ai_analysis.py <test_id> overall
    python test_ai_analysis.py <test_id> school <school_id>
"""

import sys
import os
from dotenv import load_dotenv

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Carregar variáveis de ambiente
load_dotenv('app/.env')

from app import create_app, db
from app.models.reportAggregate import ReportAggregate
from app.models.test import Test
from app.services.ai_analysis_service import AIAnalysisService
from app.services.report_aggregate_service import ReportAggregateService
from app.routes.report_routes import _montar_resposta_relatorio, _montar_resposta_relatorio_por_turmas
from app.openai_config.openai_config import (
    ABACUS_API_KEY,
    ABACUS_API_URL,
    ABACUS_MODEL
)
import requests
import logging
import json
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_abacus_connection():
    """Testa se a conexão com Abacus AI está funcionando"""
    print("\n" + "="*80)
    print("TESTE 1: Conexão com Abacus AI (REST API)")
    print("="*80)
    
    try:
        # Preparar requisição REST
        headers = {
            "Authorization": f"Bearer {ABACUS_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": ABACUS_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": "Responda apenas: OK"
                }
            ],
            "max_tokens": 10
        }
        
        print(f"✓ Testando conexão com modelo: {ABACUS_MODEL}")
        print(f"✓ URL: {ABACUS_API_URL}")
        
        # Testar uma chamada simples
        print("\nTestando chamada simples ao Abacus AI...")
        response = requests.post(
            ABACUS_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            print(f"✓ Resposta recebida: {content[:50]}")
            return True
        else:
            print(f"❌ Resposta não contém 'choices': {result}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro na requisição HTTP: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status code: {e.response.status_code}")
            try:
                print(f"   Erro: {e.response.json()}")
            except:
                print(f"   Text: {e.response.text[:200]}")
        return False
    except Exception as e:
        print(f"❌ Erro ao testar Abacus AI: {str(e)}")
        print(f"   Tipo do erro: {type(e).__name__}")
        return False


def check_cache_status(test_id: str, scope_type: str = "overall", scope_id: str = None):
    """Verifica o status do cache no banco de dados"""
    print("\n" + "="*80)
    print("TESTE 2: Status do Cache no Banco de Dados")
    print("="*80)
    
    try:
        aggregate = ReportAggregateService.get(test_id, scope_type, scope_id)
        
        if not aggregate:
            print(f"❌ Nenhum cache encontrado para:")
            print(f"   test_id: {test_id}")
            print(f"   scope_type: {scope_type}")
            print(f"   scope_id: {scope_id}")
            return None
        
        print(f"✓ Cache encontrado:")
        print(f"   ID: {aggregate.id}")
        print(f"   test_id: {aggregate.test_id}")
        print(f"   scope_type: {aggregate.scope_type}")
        print(f"   scope_id: {aggregate.scope_id}")
        print(f"   is_dirty: {aggregate.is_dirty}")
        print(f"   ai_analysis_is_dirty: {aggregate.ai_analysis_is_dirty}")
        print(f"   Tem payload: {bool(aggregate.payload)}")
        print(f"   Tem ai_analysis: {bool(aggregate.ai_analysis)}")
        print(f"   ai_analysis_generated_at: {aggregate.ai_analysis_generated_at}")
        print(f"   updated_at: {aggregate.updated_at}")
        
        if aggregate.ai_analysis:
            print(f"\n   Análise de IA (primeiros 200 chars):")
            ai_str = json.dumps(aggregate.ai_analysis, ensure_ascii=False, indent=2)
            print(f"   {ai_str[:200]}...")
        
        return aggregate
        
    except Exception as e:
        print(f"❌ Erro ao verificar cache: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_ai_service_initialization():
    """Testa se o serviço de IA inicializa corretamente"""
    print("\n" + "="*80)
    print("TESTE 3: Inicialização do Serviço de IA")
    print("="*80)
    
    try:
        ai_service = AIAnalysisService()
        print(f"✓ Serviço inicializado")
        print(f"   Modelo: {ABACUS_MODEL}")
        print(f"   API URL: {ABACUS_API_URL}")
        return ai_service
    except Exception as e:
        print(f"❌ Erro ao inicializar serviço: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_ai_analysis_generation(test_id: str, scope_type: str = "overall", scope_id: str = None):
    """Testa a geração de análise de IA"""
    print("\n" + "="*80)
    print("TESTE 4: Geração de Análise de IA")
    print("="*80)
    
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(test_id)
        if not test:
            print(f"❌ Avaliação não encontrada: {test_id}")
            return None
        
        print(f"✓ Avaliação encontrada: {test.title}")
        
        # Buscar dados do relatório
        print("\nBuscando dados do relatório...")
        if scope_type == "teacher" and scope_id:
            from app.permissions.utils import get_teacher, get_teacher_classes
            from app.models.classTest import ClassTest
            
            teacher = get_teacher(scope_id)
            if not teacher:
                print(f"❌ Professor não encontrado: {scope_id}")
                return None
            
            teacher_class_ids = get_teacher_classes(teacher.user_id)
            if not teacher_class_ids:
                print(f"❌ Professor não vinculado a nenhuma turma")
                return None
            
            class_tests = ClassTest.query.filter(
                ClassTest.test_id == test_id,
                ClassTest.class_id.in_(teacher_class_ids)
            ).all()
            
            if not class_tests:
                print(f"❌ Avaliação não aplicada em turmas do professor")
                return None
            
            report_data = _montar_resposta_relatorio_por_turmas(test_id, class_tests, include_ai=False)
        else:
            school_id = scope_id if scope_type == "school" else None
            city_id = scope_id if scope_type == "city" else None
            report_data = _montar_resposta_relatorio(test_id, school_id, city_id, include_ai=False)
        
        print(f"✓ Dados do relatório obtidos")
        print(f"   Total de alunos: {report_data.get('total_alunos', {}).get('total_geral', {}).get('avaliados', 0)}")
        
        # Preparar dados para análise
        report_data['scope_type'] = scope_type
        report_data['scope_id'] = scope_id
        
        # Inicializar serviço de IA
        print("\nInicializando serviço de IA...")
        ai_service = AIAnalysisService()
        
        print(f"✓ Serviço de IA inicializado (Abacus AI - REST API)")
        
        # Gerar análise
        print("\nGerando análise de IA (isso pode levar alguns segundos)...")
        ai_analysis = ai_service.analyze_report_data(report_data)
        
        print(f"✓ Análise gerada com sucesso!")
        print(f"\n   Estrutura da análise:")
        for key in ai_analysis.keys():
            if isinstance(ai_analysis[key], dict):
                print(f"   - {key}: dict com {len(ai_analysis[key])} itens")
            elif isinstance(ai_analysis[key], str):
                print(f"   - {key}: string ({len(ai_analysis[key])} chars)")
            else:
                print(f"   - {key}: {type(ai_analysis[key]).__name__}")
        
        # Mostrar preview
        print(f"\n   Preview da análise:")
        if 'participacao' in ai_analysis:
            print(f"   Participação: {ai_analysis['participacao'][:150]}...")
        if 'notas' in ai_analysis:
            print(f"   Notas: {ai_analysis['notas'][:150]}...")
        if 'proficiencia' in ai_analysis:
            for disc, analise in list(ai_analysis['proficiencia'].items())[:2]:
                print(f"   Proficiência {disc}: {analise[:100]}...")
        
        return ai_analysis
        
    except Exception as e:
        print(f"❌ Erro ao gerar análise: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def test_save_ai_analysis(test_id: str, scope_type: str = "overall", scope_id: str = None):
    """Testa o salvamento da análise de IA"""
    print("\n" + "="*80)
    print("TESTE 5: Salvamento da Análise de IA")
    print("="*80)
    
    try:
        # Gerar análise
        ai_analysis = test_ai_analysis_generation(test_id, scope_type, scope_id)
        
        if not ai_analysis:
            print("❌ Não foi possível gerar análise")
            return False
        
        # Salvar análise
        print("\nSalvando análise no banco de dados...")
        aggregate = ReportAggregateService.save_ai_analysis(
            test_id=test_id,
            scope_type=scope_type,
            scope_id=scope_id,
            ai_analysis=ai_analysis,
            commit=True
        )
        
        print(f"✓ Análise salva com sucesso!")
        print(f"   Aggregate ID: {aggregate.id}")
        print(f"   ai_analysis_is_dirty: {aggregate.ai_analysis_is_dirty}")
        print(f"   ai_analysis_generated_at: {aggregate.ai_analysis_generated_at}")
        
        # Verificar se foi salvo corretamente
        saved_aggregate = ReportAggregateService.get(test_id, scope_type, scope_id)
        if saved_aggregate and saved_aggregate.ai_analysis:
            print(f"✓ Análise confirmada no banco de dados")
            return True
        else:
            print(f"❌ Análise não encontrada após salvar")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao salvar análise: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_ensure_ai_analysis(test_id: str, scope_type: str = "overall", scope_id: str = None):
    """Testa o método ensure_ai_analysis completo"""
    print("\n" + "="*80)
    print("TESTE 6: Fluxo Completo ensure_ai_analysis")
    print("="*80)
    
    try:
        # Marcar como dirty primeiro
        print("Marcando análise como dirty...")
        ReportAggregateService.mark_ai_dirty(test_id, scope_type, scope_id, commit=True)
        
        # Verificar status
        aggregate = ReportAggregateService.get(test_id, scope_type, scope_id)
        if aggregate:
            print(f"✓ Status após marcar dirty: ai_analysis_is_dirty={aggregate.ai_analysis_is_dirty}")
        else:
            print("⚠ Nenhum aggregate encontrado (será criado)")
        
        # Criar callback de geração
        def build_ai_analysis():
            if scope_type == "teacher" and scope_id:
                from app.permissions.utils import get_teacher, get_teacher_classes
                from app.models.classTest import ClassTest
                
                teacher = get_teacher(scope_id)
                teacher_class_ids = get_teacher_classes(teacher.user_id)
                class_tests = ClassTest.query.filter(
                    ClassTest.test_id == test_id,
                    ClassTest.class_id.in_(teacher_class_ids)
                ).all()
                
                report_data = _montar_resposta_relatorio_por_turmas(test_id, class_tests, include_ai=False)
            else:
                school_id = scope_id if scope_type == "school" else None
                city_id = scope_id if scope_type == "city" else None
                report_data = _montar_resposta_relatorio(test_id, school_id, city_id, include_ai=False)
            
            report_data['scope_type'] = scope_type
            report_data['scope_id'] = scope_id
            
            ai_service = AIAnalysisService()
            return ai_service.analyze_report_data(report_data)
        
        # Chamar ensure_ai_analysis
        print("\nChamando ensure_ai_analysis...")
        result = ReportAggregateService.ensure_ai_analysis(
            test_id=test_id,
            scope_type=scope_type,
            scope_id=scope_id,
            build_ai_callback=build_ai_analysis,
            commit=True
        )
        
        print(f"✓ ensure_ai_analysis retornou resultado")
        print(f"   Tipo: {type(result)}")
        print(f"   Chaves: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        
        # Verificar no banco
        final_aggregate = ReportAggregateService.get(test_id, scope_type, scope_id)
        if final_aggregate:
            print(f"\n✓ Status final no banco:")
            print(f"   ai_analysis_is_dirty: {final_aggregate.ai_analysis_is_dirty}")
            print(f"   Tem ai_analysis: {bool(final_aggregate.ai_analysis)}")
            print(f"   ai_analysis_generated_at: {final_aggregate.ai_analysis_generated_at}")
            
            if final_aggregate.ai_analysis_is_dirty:
                print("⚠ ATENÇÃO: Análise ainda está marcada como dirty!")
            if not final_aggregate.ai_analysis:
                print("⚠ ATENÇÃO: Análise não foi salva!")
        
        return result
        
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Função principal"""
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print("SCRIPT DE TESTE - ANÁLISE DE IA")
        print("="*80)
        print(f"Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Obter parâmetros
        test_id = sys.argv[1] if len(sys.argv) > 1 else None
        scope_type = sys.argv[2] if len(sys.argv) > 2 else "overall"
        scope_id = sys.argv[3] if len(sys.argv) > 3 else None
        
        if not test_id:
            print("\n⚠ Nenhum test_id fornecido. Executando apenas testes básicos...")
            test_abacus_connection()
            test_ai_service_initialization()
            print("\n" + "="*80)
            print("Para testar com uma avaliação específica:")
            print("  python test_ai_analysis.py <test_id> [scope_type] [scope_id]")
            print("="*80)
            return
        
        # Executar todos os testes
        test_abacus_connection()
        test_ai_service_initialization()
        check_cache_status(test_id, scope_type, scope_id)
        test_ai_analysis_generation(test_id, scope_type, scope_id)
        test_save_ai_analysis(test_id, scope_type, scope_id)
        test_ensure_ai_analysis(test_id, scope_type, scope_id)
        
        # Verificação final
        print("\n" + "="*80)
        print("VERIFICAÇÃO FINAL")
        print("="*80)
        final_aggregate = check_cache_status(test_id, scope_type, scope_id)
        
        if final_aggregate:
            if final_aggregate.ai_analysis_is_dirty:
                print("\n❌ PROBLEMA: Análise ainda está marcada como dirty!")
            elif not final_aggregate.ai_analysis:
                print("\n❌ PROBLEMA: Análise não foi salva!")
            else:
                print("\n✓ SUCESSO: Análise está salva e não está dirty!")
        else:
            print("\n⚠ Nenhum aggregate encontrado")
        
        print("\n" + "="*80)
        print("TESTES CONCLUÍDOS")
        print("="*80)


if __name__ == "__main__":
    main()

