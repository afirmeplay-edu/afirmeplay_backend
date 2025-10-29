#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste para geração de PDFs de relatórios

Este script gera dois PDFs:
1. Relatório Municipal (sem school_id)
2. Relatório por Escola (com school_id)

Uso: python test_pdf_generation.py
"""

import sys
import os

# Adicionar o diretório raiz ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.routes.report_routes import (
    _determinar_escopo_relatorio,
    _buscar_turmas_por_escopo,
    _obter_nome_curso,
    _obter_disciplinas_avaliacao,
    _calcular_totais_alunos_por_escopo,
    _calcular_niveis_aprendizagem_por_escopo,
    _calcular_proficiencia_por_escopo,
    _calcular_nota_geral_por_escopo,
    _calcular_acertos_habilidade_por_escopo
)
from app.services.ai_analysis_service import AIAnalysisService
from app.utils.pdf_template_generator import gerar_pdf_com_template_dinamico
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.studentClass import Class
from app.models.school import School

# IDs de teste
CITY_ID = "4f5078e3-58a5-48e6-bca9-e3f85d35f87e"
# Usar uma das escolas encontradas nas turmas da avaliação:
# b177ca2b-cac0-40e4-85b3-c6a4ba2c6fdd (ESCOLA MUNICIPAL RUI PALMEIRA)
# e1f269f5-001e-4526-9f9d-4628e835a0ae (ESCOLA MUNICIPAL PROFESSORA ANA NERI MALHEIRO DE OLIVEIRA)
SCHOOL_ID = "b177ca2b-cac0-40e4-85b3-c6a4ba2c6fdd"  # ESCOLA MUNICIPAL RUI PALMEIRA
TEST_ID = "ec3535d2-3812-4567-a237-e3c5c007b284"

def gerar_pdf_direto(test_id: str, scope_type: str, scope_id: str = None, filename: str = None):
    """Gera PDF diretamente sem passar pelos decorators"""
    try:
        # Buscar avaliação
        test = Test.query.get(test_id)
        if not test:
            print(f"✗ Avaliação {test_id} não encontrada")
            return False
        
        # Debug: verificar todas as turmas da avaliação
        all_class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        print(f"  Total de turmas na avaliação: {len(all_class_tests)}")
        
        # Debug: verificar escola_id das turmas
        escolas_encontradas = set()
        for ct in all_class_tests:
            class_obj = Class.query.get(ct.class_id)
            if class_obj:
                school_obj = School.query.get(class_obj.school_id)
                print(f"    Turma {ct.class_id}: escola={class_obj.school_id} ({school_obj.name if school_obj else 'N/A'})")
                escolas_encontradas.add(class_obj.school_id)
        
        print(f"  Escolas encontradas: {list(escolas_encontradas)}")
        
        # Se scope_id for None e scope_type for 'school', usar a primeira escola encontrada
        if scope_type == 'school' and scope_id is None and escolas_encontradas:
            scope_id = list(escolas_encontradas)[0]
            school_obj = School.query.get(scope_id)
            print(f"  Usando primeira escola: {scope_id} ({school_obj.name if school_obj else 'N/A'})")
        
        # Buscar turmas baseado no escopo
        class_tests = _buscar_turmas_por_escopo(test_id, scope_type, scope_id)
        if not class_tests:
            print(f"✗ Nenhuma turma encontrada para o escopo especificado")
            print(f"  Scope type: {scope_type}")
            print(f"  Scope ID: {scope_id}")
            return False
        
        # Obter dados da avaliação
        course_name = _obter_nome_curso(test)
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "descricao": test.description,
            "disciplinas": _obter_disciplinas_avaliacao(test),
            "course_name": course_name
        }
        
        print(f"✓ Avaliação encontrada: {test.title}")
        print(f"✓ Turmas encontradas: {len(class_tests)}")
        
        # Calcular todos os dados
        print("  Calculando totais de alunos...")
        total_alunos = _calcular_totais_alunos_por_escopo(test_id, class_tests, scope_type)
        
        print("  Calculando níveis de aprendizagem...")
        niveis_aprendizagem = _calcular_niveis_aprendizagem_por_escopo(test_id, class_tests, scope_type)
        
        print("  Calculando proficiência...")
        proficiencia = _calcular_proficiencia_por_escopo(test_id, class_tests, scope_type)
        
        print("  Calculando notas...")
        nota_geral = _calcular_nota_geral_por_escopo(test_id, class_tests, scope_type)
        
        print("  Calculando acertos por habilidade...")
        acertos_habilidade = _calcular_acertos_habilidade_por_escopo(test_id, class_tests, scope_type)
        
        # Gerar análise da IA
        print("  Gerando análise da IA...")
        ai_service = AIAnalysisService()
        ai_analysis = ai_service.analyze_report_data({
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade,
            "scope_type": scope_type,
            "scope_id": scope_id
        })
        
        # Gerar PDF
        print("  Gerando PDF...")
        pdf_content = gerar_pdf_com_template_dinamico(
            test, total_alunos, niveis_aprendizagem, 
            proficiencia, nota_geral, acertos_habilidade, ai_analysis, avaliacao_data, scope_type
        )
        
        # Salvar arquivo
        if not filename:
            filename = f"relatorio_{scope_type}_{test_id[:8]}.pdf"
        
        with open(filename, 'wb') as f:
            f.write(pdf_content)
        
        print(f"✓ PDF gerado com sucesso: {filename}")
        print(f"  Tamanho: {len(pdf_content)} bytes")
        
        return True
        
    except Exception as e:
        print(f"✗ Erro ao gerar PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def gerar_relatorio_municipal():
    """Gera relatório municipal (sem school_id)"""
    print("=" * 60)
    print("GERANDO RELATÓRIO MUNICIPAL")
    print("=" * 60)
    print(f"Test ID: {TEST_ID}")
    print(f"City ID: {CITY_ID}")
    print("School ID: Não especificado (relatório municipal)")
    print()
    
    return gerar_pdf_direto(TEST_ID, 'city', CITY_ID, f"relatorio_municipal_{TEST_ID[:8]}.pdf")

def gerar_relatorio_escola():
    """Gera relatório por escola (com school_id)"""
    print("\n" + "=" * 60)
    print("GERANDO RELATÓRIO POR ESCOLA")
    print("=" * 60)
    print(f"Test ID: {TEST_ID}")
    print(f"City ID: {CITY_ID}")
    print(f"School ID: {SCHOOL_ID}")
    print()
    
    return gerar_pdf_direto(TEST_ID, 'school', SCHOOL_ID, f"relatorio_escola_{TEST_ID[:8]}.pdf")

def main():
    """Função principal"""
    print("\n" + "=" * 60)
    print("SCRIPT DE TESTE - GERAÇÃO DE PDFs DE RELATÓRIOS")
    print("=" * 60)
    print()
    
    # Criar e inicializar aplicação
    app = create_app()
    
    # Verificar se os IDs são válidos
    print("Verificando configurações...")
    print(f"Test ID: {TEST_ID}")
    print(f"City ID: {CITY_ID}")
    print(f"School ID: {SCHOOL_ID}")
    print()
    
    # Executar dentro do contexto da aplicação
    with app.app_context():
        # Gerar relatórios
        resultado_municipal = gerar_relatorio_municipal()
        resultado_escola = gerar_relatorio_escola()
    
    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO")
    print("=" * 60)
    print(f"Relatório Municipal: {'✓ Sucesso' if resultado_municipal else '✗ Falhou'}")
    print(f"Relatório por Escola: {'✓ Sucesso' if resultado_escola else '✗ Falhou'}")
    print()
    
    if resultado_municipal and resultado_escola:
        print("✓ Ambos os PDFs foram gerados com sucesso!")
        print("\nArquivos gerados:")
        print(f"  - relatorio_municipal_{TEST_ID[:8]}.pdf")
        print(f"  - relatorio_escola_{TEST_ID[:8]}.pdf")
    else:
        print("✗ Alguns PDFs falharam na geração. Verifique os erros acima.")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
