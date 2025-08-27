# -*- coding: utf-8 -*-
"""
Rotas especializadas para relatórios de avaliações
Endpoint para geração de relatórios completos com estatísticas detalhadas
"""

from flask import Blueprint, request, jsonify, render_template_string
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.models.question import Question
from app.models.subject import Subject
from app.models.school import School
from app.models.city import City
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.classTest import ClassTest
from app.models.evaluationResult import EvaluationResult
from app import db
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import func, case, desc
from datetime import datetime
from sqlalchemy.orm import joinedload
from collections import defaultdict
import os
from jinja2 import Template
import tempfile
from reportlab.lib.pagesizes import A4
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen.canvas import Canvas
from io import BytesIO
from app.services.ai_analysis_service import AIAnalysisService

# Constantes de cores para o PDF
BLUE_900 = colors.HexColor("#0b2a56")
GRAY_150 = colors.HexColor("#ededed")
GRAY_200 = colors.HexColor("#e6e6e6")
GRID = colors.HexColor("#999")
RED = colors.HexColor("#e53935")
YELLOW = colors.HexColor("#f1c232")
ADEQ = colors.HexColor("#6aa84f")
GREEN = colors.HexColor("#00a651")

def _header(canvas: Canvas, doc, logo_esq=None, logo_dir=None):
    """Função para desenhar cabeçalho com logos em todas as páginas"""
    top_y = doc.height + doc.topMargin + 8*mm
    if logo_esq:
        canvas.drawImage(logo_esq, doc.leftMargin, top_y-18*mm, width=28*mm, height=18*mm, preserveAspectRatio=True, mask='auto')
    if logo_dir:
        x = doc.pagesize[0] - doc.rightMargin - 28*mm
        canvas.drawImage(logo_dir, x, top_y-18*mm, width=28*mm, height=18*mm, preserveAspectRatio=True, mask='auto')

bp = Blueprint('reports', __name__, url_prefix='/reports')


@bp.route('/test', methods=['GET'])
def test_endpoint():
    """Endpoint de teste para verificar se o blueprint está funcionando"""
    return jsonify({
        "message": "Blueprint de relatórios funcionando corretamente",
        "status": "success"
    }), 200


@bp.route('/test-questions/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def test_questions(evaluation_id: str):
    """Endpoint para testar diretamente a propriedade questions"""
    try:
        from app.models.testQuestion import TestQuestion
        from app.models.question import Question
        
        # Teste 1: Query direta na tabela test_questions
        test_questions_direct = TestQuestion.query.filter_by(test_id=evaluation_id).order_by(TestQuestion.order).all()
        
        # Teste 2: IDs das questões
        question_ids = [tq.question_id for tq in test_questions_direct]
        
        # Teste 3: Buscar questões diretamente
        questions_direct = Question.query.filter(Question.id.in_(question_ids)).all()
        
        # Teste 4: Usar a propriedade questions do modelo Test
        test = Test.query.get(evaluation_id)
        questions_property = test.questions if test else []
        
        # Teste 5: Verificar se a questão de Português está na tabela
        portugues_question = TestQuestion.query.filter_by(
            test_id=evaluation_id,
            question_id="4e3305a0-7221-4012-a7aa-8f958b755823"
        ).first()
        
        debug_info = {
            "avaliacao_id": evaluation_id,
            "test_questions_direct": {
                "total": len(test_questions_direct),
                "registros": [
                    {
                        "id": tq.id,
                        "test_id": tq.test_id,
                        "question_id": tq.question_id,
                        "order": tq.order
                    } for tq in test_questions_direct
                ]
            },
            "question_ids": question_ids,
            "questions_direct": {
                "total": len(questions_direct),
                "questoes": [
                    {
                        "id": q.id,
                        "skill": q.skill,
                        "number": q.number
                    } for q in questions_direct
                ]
            },
            "questions_property": {
                "total": len(questions_property),
                "questoes": [
                    {
                        "id": q.id,
                        "skill": q.skill,
                        "number": q.number
                    } for q in questions_property
                ]
            },
            "questao_portugues_teste": {
                "encontrada": portugues_question is not None,
                "dados": {
                    "id": portugues_question.id,
                    "test_id": portugues_question.test_id,
                    "question_id": portugues_question.question_id,
                    "order": portugues_question.order
                } if portugues_question else None
            }
        }
        
        return jsonify(debug_info), 200
        
    except Exception as e:
        logging.error(f"Erro ao testar questions: {str(e)}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/debug-disciplinas/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def debug_disciplinas(evaluation_id: str):
    """Endpoint para debug da identificação de disciplinas"""
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Obter disciplinas usando a função melhorada
        disciplinas = _obter_disciplinas_avaliacao(test)
        
        # Debug detalhado
        debug_info = {
            "avaliacao_id": evaluation_id,
            "titulo": test.title,
            "disciplinas_identificadas": disciplinas,
            "debug_details": {
                "subject_rel": test.subject_rel.name if test.subject_rel else None,
                "subjects_info": test.subjects_info,
                "total_questoes": len(test.questions) if test.questions else 0,
                "questoes_com_habilidades": 0,
                "habilidades_unicas": set(),
                "disciplinas_por_habilidade": {}
            },
            "mapeamento_questoes": {},
            "respostas_por_questao": {},
            "questao_portugues_debug": {}
        }
        
        if test.questions:
            from app.models.skill import Skill
            
            skill_ids = set()
            for question in test.questions:
                if question.skill and question.skill.strip() and question.skill != '{}':
                    clean_skill_id = question.skill.replace('{', '').replace('}', '')
                    skill_ids.add(clean_skill_id)
                    debug_info["debug_details"]["questoes_com_habilidades"] += 1
            
            debug_info["debug_details"]["habilidades_unicas"] = list(skill_ids)
            
            if skill_ids:
                skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
                skills_dict = {str(skill.id): skill for skill in skills}
                
                for skill in skills:
                    subject = Subject.query.get(skill.subject_id) if skill.subject_id else None
                    debug_info["debug_details"]["disciplinas_por_habilidade"][str(skill.id)] = {
                        "skill_code": skill.code,
                        "skill_description": skill.description,
                        "subject_id": skill.subject_id,
                        "subject_name": subject.name if subject else None
                    }
                
                # Mapear questões para disciplinas (mesmo processo das funções de cálculo)
                for question in test.questions:
                    # Questões com skill: mapear via skill.subject_id
                    if question.skill and question.skill.strip() and question.skill != '{}':
                        clean_skill_id = question.skill.replace('{', '').replace('}', '')
                        skill_obj = skills_dict.get(clean_skill_id)
                        
                        disciplina_mapeada = "Não mapeada"
                        if skill_obj and skill_obj.subject_id:
                            subject = Subject.query.get(skill_obj.subject_id)
                            if subject:
                                disciplina_mapeada = subject.name
                            else:
                                disciplina_mapeada = "Disciplina Geral (subject não encontrado)"
                        else:
                            disciplina_mapeada = "Disciplina Geral (skill sem subject_id)"
                        
                        debug_info["mapeamento_questoes"][question.id] = {
                            "numero": question.number,
                            "skill_id": clean_skill_id,
                            "skill_encontrada": skill_obj is not None,
                            "disciplina_mapeada": disciplina_mapeada
                        }
                    else:
                        # Questões sem skill: mapear para disciplina principal da avaliação
                        if test.subject_rel:
                            disciplina_mapeada = test.subject_rel.name
                            debug_info["mapeamento_questoes"][question.id] = {
                                "numero": question.number,
                                "skill_id": "Sem skill",
                                "skill_encontrada": False,
                                "disciplina_mapeada": disciplina_mapeada
                            }
                        else:
                            disciplina_mapeada = "Disciplina Geral"
                            debug_info["mapeamento_questoes"][question.id] = {
                                "numero": question.number,
                                "skill_id": "Sem skill",
                                "skill_encontrada": False,
                                "disciplina_mapeada": disciplina_mapeada
                            }
                    
                    # Verificar respostas para esta questão
                    respostas = StudentAnswer.query.filter_by(
                        test_id=evaluation_id, 
                        question_id=question.id
                    ).count()
                    
                    debug_info["respostas_por_questao"][question.id] = respostas
                    
                    # Debug específico para a questão de Português que sabemos que existe
                    if question.id == "4e3305a0-7221-4012-a7aa-8f958b755823":
                        if question.skill and question.skill.strip() and question.skill != '{}':
                            clean_skill_id = question.skill.replace('{', '').replace('}', '')
                            skill_obj = skills_dict.get(clean_skill_id)
                            debug_info["questao_portugues_debug"] = {
                                "questao_id": question.id,
                                "numero": question.number,
                                "skill_raw": question.skill,
                                "skill_clean": clean_skill_id,
                                "skill_encontrada": skill_obj is not None,
                                "skill_code": skill_obj.code if skill_obj else None,
                                "skill_subject_id": skill_obj.subject_id if skill_obj else None,
                                "disciplina_final": disciplina_mapeada,
                                "total_respostas": respostas
                            }
                        else:
                            debug_info["questao_portugues_debug"] = {
                                "questao_id": question.id,
                                "numero": question.number,
                                "skill_raw": question.skill,
                                "skill_clean": "Sem skill",
                                "skill_encontrada": False,
                                "skill_code": None,
                                "skill_subject_id": None,
                                "disciplina_final": disciplina_mapeada,
                                "total_respostas": respostas
                            }
        
        return jsonify(debug_info), 200
        
    except Exception as e:
        logging.error(f"Erro ao debug disciplinas: {str(e)}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/relatorio-completo/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def relatorio_completo(evaluation_id: str):
    """
    Gera relatório completo de uma avaliação com todos os dados solicitados
    
    Args:
        evaluation_id: ID da avaliação
    
    Returns:
        JSON com relatório completo contendo:
        - Total de alunos que realizaram a avaliação
        - Níveis de Aprendizagem por turma
        - Proficiência
        - Nota Geral por turma
        - Acertos por habilidade
    """
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Buscar turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
        
        # Obter dados da avaliação
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "descricao": test.description,
            "disciplinas": _obter_disciplinas_avaliacao(test)
        }
        
        logging.info(f"Disciplinas identificadas para avaliação {evaluation_id}: {avaliacao_data['disciplinas']}")
        
        # 1. Total de alunos que realizaram a avaliação
        total_alunos = _calcular_totais_alunos(evaluation_id, class_tests)
        
        # 2. Níveis de Aprendizagem por turma
        niveis_aprendizagem = _calcular_niveis_aprendizagem(evaluation_id, class_tests)
        logging.info(f"Níveis de aprendizagem calculados para disciplinas: {list(niveis_aprendizagem.keys())}")
        
        # 3. Proficiência
        proficiencia = _calcular_proficiencia(evaluation_id, class_tests)
        logging.info(f"Proficiência calculada para disciplinas: {list(proficiencia.get('por_disciplina', {}).keys())}")
        
        # 4. Nota Geral por turma
        nota_geral = _calcular_nota_geral(evaluation_id, class_tests)
        logging.info(f"Nota geral calculada para disciplinas: {list(nota_geral.get('por_disciplina', {}).keys())}")
        
        # 5. Acertos por habilidade
        acertos_habilidade = _calcular_acertos_habilidade(evaluation_id)
        logging.info(f"Acertos por habilidade calculados para disciplinas: {list(acertos_habilidade.keys())}")
        
        return jsonify({
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório completo: {str(e)}")
        return jsonify({"error": "Erro interno do servidor"}), 500


@bp.route('/relatorio-com-ia/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def relatorio_com_ia(evaluation_id: str):
    """
    Gera relatório completo com análise da IA
    
    Args:
        evaluation_id: ID da avaliação
    
    Returns:
        JSON com relatório completo + análise da IA
    """
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Buscar turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
        
        # Obter dados da avaliação
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "descricao": test.description,
            "disciplinas": _obter_disciplinas_avaliacao(test),
            "questoes_anuladas": []  # Lista de questões anuladas se houver
        }
        
        logging.info(f"Disciplinas identificadas para avaliação {evaluation_id}: {avaliacao_data['disciplinas']}")
        
        # 1. Total de alunos que realizaram a avaliação
        total_alunos = _calcular_totais_alunos(evaluation_id, class_tests)
        
        # 2. Níveis de Aprendizagem por turma
        niveis_aprendizagem = _calcular_niveis_aprendizagem(evaluation_id, class_tests)
        
        # 3. Proficiência
        proficiencia = _calcular_proficiencia(evaluation_id, class_tests)
        
        # 4. Nota Geral por turma
        nota_geral = _calcular_nota_geral(evaluation_id, class_tests)
        
        # 5. Acertos por habilidade
        acertos_habilidade = _calcular_acertos_habilidade(evaluation_id)
        
        # Preparar dados completos para análise da IA
        report_data = {
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade
        }
        
        # 6. Análise da IA
        ai_service = AIAnalysisService()
        ai_analysis = ai_service.analyze_report_data(report_data)
        
        return jsonify({
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade,
            "analise_ia": ai_analysis
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório com IA: {str(e)}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/relatorio-pdf/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def relatorio_pdf(evaluation_id: str):
    """
    Gera relatório PDF de uma avaliação
    
    Args:
        evaluation_id: ID da avaliação
    
    Returns:
        PDF do relatório para download
    """
    try:
        # Usar a mesma lógica da rota relatorio_completo
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Buscar turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
        
        # Obter dados da avaliação (mesma lógica do relatorio_completo)
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "descricao": test.description,
            "disciplinas": _obter_disciplinas_avaliacao(test)
        }
        
        logging.info(f"Disciplinas identificadas para avaliação {evaluation_id}: {avaliacao_data['disciplinas']}")
        
        # 1. Total de alunos que realizaram a avaliação
        total_alunos = _calcular_totais_alunos(evaluation_id, class_tests)
        
        # 2. Níveis de Aprendizagem por turma
        niveis_aprendizagem = _calcular_niveis_aprendizagem(evaluation_id, class_tests)
        logging.info(f"Níveis de aprendizagem calculados para disciplinas: {list(niveis_aprendizagem.keys())}")
        
        # 3. Proficiência
        proficiencia = _calcular_proficiencia(evaluation_id, class_tests)
        logging.info(f"Proficiência calculada para disciplinas: {list(proficiencia.get('por_disciplina', {}).keys())}")
        
        # 4. Nota Geral por turma
        nota_geral = _calcular_nota_geral(evaluation_id, class_tests)
        logging.info(f"Nota geral calculada para disciplinas: {list(nota_geral.get('por_disciplina', {}).keys())}")
        
        # 5. Acertos por habilidade
        acertos_habilidade = _calcular_acertos_habilidade(evaluation_id)
        logging.info(f"Acertos por habilidade calculados para disciplinas: {list(acertos_habilidade.keys())}")
        
        # 6. Análise da IA
        ai_service = AIAnalysisService()
        ai_analysis = ai_service.analyze_report_data({
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade
        })
        
        # Preparar dados para o template (incluindo dados extras e IA)
        template_data = _preparar_dados_template_pdf(
            test, total_alunos, niveis_aprendizagem, 
            proficiencia, nota_geral, acertos_habilidade, ai_analysis
        )
        
        # Ler o template HTML
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'relatorio_avaliacao_novo.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Renderizar o template
        template = Template(template_content)
        html_content = template.render(**template_data)
        
        # Gerar PDF com ReportLab
        try:
            pdf_content = _gerar_pdf_reportlab(template_data)
            
            # Preparar nome do arquivo com o nome da avaliação
            nome_avaliacao = test.title.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            nome_arquivo = f"relatorio_{nome_avaliacao}.pdf"
            
            # Retornar PDF
            from flask import Response
            response = Response(pdf_content, mimetype='application/pdf')
            response.headers['Content-Disposition'] = f'attachment; filename={nome_arquivo}'
            
            return response
            
        except Exception as pdf_error:
            logging.error(f"Erro ao gerar PDF com ReportLab: {str(pdf_error)}")
            
            # Fallback: retornar HTML se PDF falhar
            logging.warning("Falha na geração do PDF, retornando HTML como fallback")
            
            # Preparar nome do arquivo com o nome da avaliação
            nome_avaliacao = test.title.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            nome_arquivo = f"relatorio_{nome_avaliacao}.html"
            
            from flask import Response
            response = Response(html_content, mimetype='text/html')
            response.headers['Content-Disposition'] = f'inline; filename={nome_arquivo}'
            
            return response
        
    except Exception as e:
        logging.error(f"Erro ao gerar relatório PDF: {str(e)}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/test-html/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def test_html_template(evaluation_id: str):
    """Endpoint para testar o template HTML renderizado"""
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Buscar turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
        
        # Obter dados da avaliação usando as funções existentes
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "descricao": test.description,
            "disciplinas": _obter_disciplinas_avaliacao(test)
        }
        
        # 1. Total de alunos que realizaram a avaliação
        total_alunos = _calcular_totais_alunos(evaluation_id, class_tests)
        
        # 2. Níveis de Aprendizagem por turma
        niveis_aprendizagem = _calcular_niveis_aprendizagem(evaluation_id, class_tests)
        
        # 3. Proficiência
        proficiencia = _calcular_proficiencia(evaluation_id, class_tests)
        
        # 4. Nota Geral por turma
        nota_geral = _calcular_nota_geral(evaluation_id, class_tests)
        
        # 5. Acertos por habilidade
        acertos_habilidade = _calcular_acertos_habilidade(evaluation_id)
        
        # Preparar dados para o template
        template_data = _preparar_dados_template(
            test, total_alunos, niveis_aprendizagem, 
            proficiencia, nota_geral, acertos_habilidade
        )
        
        # Ler o template HTML
        template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'relatorio_avaliacao.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Renderizar o template
        template = Template(template_content)
        html_content = template.render(**template_data)
        
        # Retornar HTML para teste
        from flask import Response
        response = Response(html_content, mimetype='text/html')
        return response
        
    except Exception as e:
        logging.error(f"Erro ao testar template HTML: {str(e)}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


def _preparar_dados_template(test: Test, total_alunos: Dict, niveis_aprendizagem: Dict, 
                           proficiencia: Dict, nota_geral: Dict, acertos_habilidade: Dict) -> Dict[str, Any]:
    """Prepara os dados para o template Jinja2"""
    
    # Obter informações da escola e município
    escola_nome = "Escola não identificada"
    municipio_nome = "Município não identificado"
    uf = "AL"
    
    try:
        # Buscar primeira turma para obter escola e município
        if test.class_tests:
            first_class_test = test.class_tests[0]
            first_class = Class.query.get(first_class_test.class_id)
            if first_class and first_class.school:
                escola_nome = first_class.school.name
                if first_class.school.city:
                    municipio_nome = first_class.school.city.name
                    uf = first_class.school.city.state or "AL"
    except Exception as e:
        logging.warning(f"Erro ao obter dados da escola/município: {str(e)}")
    
    # Preparar dados de participação
    participacao = []
    for turma_data in total_alunos.get('por_turma', []):
        participacao.append({
            'serie_turno': turma_data['turma'],
            'matriculados': turma_data['matriculados'],
            'avaliados': turma_data['avaliados'],
            'percentual': turma_data['percentual'],
            'faltosos': turma_data['faltosos']
        })
    
    # Resumo de participação
    total_geral = total_alunos.get('total_geral', {})
    participacao_resumo = f"Total geral: {total_geral.get('avaliados', 0)} alunos avaliados de {total_geral.get('matriculados', 0)} matriculados ({total_geral.get('percentual', 0)}%)"
    
    # Textos padrão
    apresentacao_texto = f"""
    Este relatório apresenta os resultados da <strong>Avaliação Diagnóstica {test.title}</strong> 
    aplicada na rede municipal de ensino de {municipio_nome}, {uf}. 
    A avaliação foi realizada com o objetivo de diagnosticar o nível de aprendizagem dos estudantes 
    e identificar áreas que necessitam de maior atenção pedagógica.
    """
    
    consideracoes = f"""
    A avaliação foi aplicada em {len(test.class_tests) if test.class_tests else 0} turmas, 
    totalizando {total_geral.get('avaliados', 0)} estudantes avaliados. 
    Os resultados apresentados refletem o desempenho dos alunos em diferentes habilidades 
    e competências, organizados por disciplina e nível de aprendizagem.
    """
    
    # Determinar período atual
    from datetime import datetime
    now = datetime.now()
    mes_atual = now.strftime("%B").upper()
    ano_atual = now.year
    periodo = f"{ano_atual}.1"
    
    return {
        'escola': escola_nome,
        'municipio': municipio_nome,
        'uf': uf,
        'periodo': periodo,
        'mes': mes_atual,
        'ano': ano_atual,
        'apresentacao_texto': apresentacao_texto,
        'consideracoes': consideracoes,
        'participacao': participacao,
        'participacao_resumo': participacao_resumo,
        'niveis_aprendizagem': niveis_aprendizagem,
        'proficiencia': proficiencia,
        'nota_geral': nota_geral,
        'acertos_por_habilidade': acertos_habilidade
    }


def _preparar_dados_template_pdf(test: Test, total_alunos: Dict, niveis_aprendizagem: Dict, 
                               proficiencia: Dict, nota_geral: Dict, acertos_habilidade: Dict, 
                               ai_analysis: Dict) -> Dict[str, Any]:
    """Prepara os dados para o template Jinja2 do PDF (com dados extras)"""
    
    # Usar a função base para obter dados comuns
    dados_base = _preparar_dados_template(test, total_alunos, niveis_aprendizagem, 
                                        proficiencia, nota_geral, acertos_habilidade)
    
    # Adicionar dados extras específicos para o PDF
    dados_extras = _obter_dados_extras_pdf(test, total_alunos)
    
    # Adicionar dados específicos do novo template
    dados_template = _preparar_dados_template_novo(test, total_alunos, proficiencia, nota_geral, acertos_habilidade)
    
    # Combinar todos os dados incluindo a IA e níveis de aprendizagem
    dados_completos = {**dados_base, **dados_extras, **dados_template, **ai_analysis}
    
    # Adicionar dados de níveis de aprendizagem se disponíveis
    if 'niveis_aprendizagem' in dados_base:
        dados_completos['niveis_aprendizagem'] = dados_base['niveis_aprendizagem']
    
    return dados_completos


def _obter_dados_extras_pdf(test: Test, total_alunos: Dict) -> Dict[str, Any]:
    """Obtém dados extras necessários para o template do PDF"""
    
    # Obter informações detalhadas da escola
    escola_info = _obter_info_escola_detalhada(test)
    
    # Obter informações do município
    municipio_info = _obter_info_municipio_detalhada(test)
    
    # Obter estatísticas adicionais
    estatisticas_extras = _obter_estatisticas_extras(test, total_alunos)
    
    return {
        'escola_info': escola_info,
        'municipio_info': municipio_info,
        'estatisticas_extras': estatisticas_extras
    }


def _obter_info_escola_detalhada(test: Test) -> Dict[str, Any]:
    """Obtém informações detalhadas da escola"""
    try:
        if test.class_tests:
            first_class_test = test.class_tests[0]
            first_class = Class.query.get(first_class_test.class_id)
            if first_class and first_class.school:
                school = first_class.school
                return {
                    'nome': school.name,
                    'codigo': school.code if hasattr(school, 'code') else 'N/A',
                    'endereco': school.address if hasattr(school, 'address') else 'Endereço não informado',
                    'telefone': school.phone if hasattr(school, 'phone') else 'Telefone não informado',
                    'email': school.email if hasattr(school, 'email') else 'Email não informado'
                }
    except Exception as e:
        logging.warning(f"Erro ao obter informações da escola: {str(e)}")
    
    return {
        'nome': 'Escola não identificada',
        'codigo': 'N/A',
        'endereco': 'Endereço não informado',
        'telefone': 'Telefone não informado',
        'email': 'Email não informado'
    }


def _obter_info_municipio_detalhada(test: Test) -> Dict[str, Any]:
    """Obtém informações detalhadas do município"""
    try:
        if test.class_tests:
            first_class_test = test.class_tests[0]
            first_class = Class.query.get(first_class_test.class_id)
            if first_class and first_class.school and first_class.school.city:
                city = first_class.school.city
                return {
                    'nome': city.name,
                    'estado': city.state or 'AL',
                    'regiao': city.region if hasattr(city, 'region') else 'Região não informada',
                    'populacao': city.population if hasattr(city, 'population') else 'População não informada'
                }
    except Exception as e:
        logging.warning(f"Erro ao obter informações do município: {str(e)}")
    
    return {
        'nome': 'Município não identificado',
        'estado': 'AL',
        'regiao': 'Região não informada',
        'populacao': 'População não informada'
    }


def _obter_estatisticas_extras(test: Test, total_alunos: Dict) -> Dict[str, Any]:
    """Obtém estatísticas extras para o PDF"""
    try:
        total_geral = total_alunos.get('total_geral', {})
        
        # Calcular estatísticas adicionais
        total_turmas = len(test.class_tests) if test.class_tests else 0
        total_escolas = len(set(ct.class_.school_id for ct in test.class_tests if ct.class_ and ct.class_.school_id)) if test.class_tests else 0
        
        # Calcular taxas
        taxa_participacao = total_geral.get('percentual', 0)
        taxa_ausencia = 100 - taxa_participacao if taxa_participacao else 0
        
        return {
            'total_turmas': total_turmas,
            'total_escolas': total_escolas,
            'taxa_participacao': taxa_participacao,
            'taxa_ausencia': taxa_ausencia,
            'data_geracao': datetime.now().strftime("%d/%m/%Y às %H:%M"),
            'periodo_avaliacao': test.created_at.strftime("%B/%Y") if test.created_at else "Período não informado"
        }
    except Exception as e:
        logging.warning(f"Erro ao obter estatísticas extras: {str(e)}")
        return {
            'total_turmas': 0,
            'total_escolas': 0,
            'taxa_participacao': 0,
            'taxa_ausencia': 0,
            'data_geracao': datetime.now().strftime("%d/%m/%Y às %H:%M"),
            'periodo_avaliacao': "Período não informado"
        }


def _preparar_dados_template_novo(test: Test, total_alunos: Dict, proficiencia: Dict, nota_geral: Dict, acertos_habilidade: Dict) -> Dict[str, Any]:
    """Prepara dados específicos para o novo template"""
    try:
        total_geral = total_alunos.get('total_geral', {})
        
        # Dados básicos do sumário
        sumario_data = {
            'sumario_p1': '3',
            'sumario_p2': '3', 
            'sumario_p3': '4',
            'sumario_p4': '4',
            'sumario_p41': '4-5',
            'sumario_p42': '5-6',
            'sumario_p43': '6-7',
            'sumario_p44': '7-8',
            'sumario_p45': '8-9',
            'sumario_p5': '9'
        }
        
        # Dados da apresentação
        apresentacao_data = {
            'simulados_label': '1º Simulado',
            'referencia': '9º de 2025',
            'escola_extenso': 'ESCOLA MUNICIPAL DE EDUCAÇÃO BÁSICA MONSENHOR HILDEBRANDO',
            'total_avaliados': total_geral.get('avaliados', 0),
            'percentual_avaliados': f"{total_geral.get('percentual', 0)}%"
        }
        
        # Dados das considerações gerais
        consideracoes_data = {
            'qtd_questoes_anuladas': 2,
            'serie_alvo': '9º ano',
            'questoes_anuladas': '10 e 11',
            'ordens_avaliacao': '36ª e 37ª'
        }
        
        # Dados da participação
        participacao_data = {
            'total_avaliados': total_geral.get('avaliados', 0),
            'total_matriculados': total_geral.get('matriculados', 0),
            'total_faltosos': total_geral.get('faltosos', 0),
            'percentual_avaliados': f"{total_geral.get('percentual', 0)}%",
            'serie_titulo': '9º ANO'
        }
        
        # Dados de proficiência
        prof_data = _preparar_dados_proficiencia(proficiencia)
        
        # Dados de notas
        notas_data = _preparar_dados_notas(nota_geral)
        
        # Dados de habilidades
        habilidades_data = _preparar_dados_habilidades(acertos_habilidade)
        
        # Dados municipais para comparação
        municipais_data = {
            'municipal_media': '265,00',  # Média municipal de proficiência
            'municipal_nota_media': '5,50'  # Média municipal de notas
        }
        
        return {
            **sumario_data,
            **apresentacao_data,
            **consideracoes_data,
            **participacao_data,
            **prof_data,
            **notas_data,
            **habilidades_data,
            **municipais_data
        }
        
    except Exception as e:
        logging.warning(f"Erro ao preparar dados do novo template: {str(e)}")
        return {}


def _preparar_dados_proficiencia(proficiencia: Dict) -> Dict[str, Any]:
    """Prepara dados de proficiência para o template"""
    try:
        # Valores padrão
        prof_lp_media = '298,86'
        prof_mat_media = '268,29'
        prof_lp_saeb = '272,19'
        prof_mat_saeb = '293,55'
        
        # Tentar extrair dados reais
        if proficiencia and 'por_disciplina' in proficiencia:
            disciplinas = proficiencia['por_disciplina']
            
            # Buscar Língua Portuguesa
            for disciplina, dados in disciplinas.items():
                if 'portuguesa' in disciplina.lower() or 'língua' in disciplina.lower():
                    prof_lp_media = f"{dados.get('media_geral', 298.86):.2f}".replace('.', ',')
                elif 'matemática' in disciplina.lower() or 'matematica' in disciplina.lower():
                    prof_mat_media = f"{dados.get('media_geral', 268.29):.2f}".replace('.', ',')
        
        # Preparar dados de proficiência por turma
        proficiencia_turmas = []
        if proficiencia and 'por_disciplina' in proficiencia:
            disciplinas = proficiencia['por_disciplina']
            
            # Buscar dados por turma
            for disciplina, dados in disciplinas.items():
                if disciplina == 'GERAL' and 'por_turma' in dados:
                    for turma in dados['por_turma']:
                        proficiencia_turmas.append({
                            'serie_turno': turma.get('turma', 'Turma'),
                            'lp': turma.get('proficiencia', 0),
                            'mat': turma.get('proficiencia', 0),  # Mesmo valor para ambas disciplinas
                            'media': turma.get('proficiencia', 0)
                        })
        
        return {
            'prof_lp_media': prof_lp_media,
            'prof_mat_media': prof_mat_media,
            'prof_lp_saeb': prof_lp_saeb,
            'prof_mat_saeb': prof_mat_saeb,
            'proficiencia': proficiencia_turmas
        }
        
    except Exception as e:
        logging.warning(f"Erro ao preparar dados de proficiência: {str(e)}")
        return {
            'prof_lp_media': '298,86',
            'prof_mat_media': '268,29',
            'prof_lp_saeb': '272,19',
            'prof_mat_saeb': '293,55',
            'proficiencia': []
        }


def _preparar_dados_notas(nota_geral: Dict) -> Dict[str, Any]:
    """Prepara dados de notas para o template"""
    try:
        # Valores padrão
        media_geral = '6,31'
        media_lp = '6,77'
        media_mat = '5,85'
        saeb_nota_ref = '6,1'
        label_media_municipal = 'MUNICIPAL'
        
        # Tentar extrair dados reais
        if nota_geral and 'por_disciplina' in nota_geral:
            disciplinas = nota_geral['por_disciplina']
            
            # Buscar Língua Portuguesa e Matemática
            for disciplina, dados in disciplinas.items():
                if 'portuguesa' in disciplina.lower() or 'língua' in disciplina.lower():
                    media_lp = f"{dados.get('media_geral', 6.77):.2f}".replace('.', ',')
                elif 'matemática' in disciplina.lower() or 'matematica' in disciplina.lower():
                    media_mat = f"{dados.get('media_geral', 5.85):.2f}".replace('.', ',')
            
            # Calcular média geral
            medias = []
            for disciplina, dados in disciplinas.items():
                if disciplina != 'GERAL':
                    medias.append(dados.get('media_geral', 0))
            
            if medias:
                media_geral = f"{sum(medias) / len(medias):.2f}".replace('.', ',')
        
        # Preparar dados de notas por turma
        notas_turmas = []
        if nota_geral and 'por_disciplina' in nota_geral:
            disciplinas = nota_geral['por_disciplina']
            
            # Buscar dados por turma
            for disciplina, dados in disciplinas.items():
                if disciplina == 'GERAL' and 'por_turma' in dados:
                    for turma in dados['por_turma']:
                        notas_turmas.append({
                            'serie_turno': turma.get('turma', 'Turma'),
                            'lp': turma.get('nota', 0),
                            'mat': turma.get('nota', 0),  # Mesmo valor para ambas disciplinas
                            'media': turma.get('nota', 0)
                        })
        
        return {
            'media_geral': media_geral,
            'media_lp': media_lp,
            'media_mat': media_mat,
            'saeb_nota_ref': saeb_nota_ref,
            'label_media_municipal': label_media_municipal,
            'notas': notas_turmas
        }
        
    except Exception as e:
        logging.warning(f"Erro ao preparar dados de notas: {str(e)}")
        return {
            'media_geral': '6,31',
            'media_lp': '6,77',
            'media_mat': '5,85',
            'saeb_nota_ref': '6,1',
            'label_media_municipal': 'MUNICIPAL',
            'notas': []
        }


def _preparar_dados_habilidades(acertos_habilidade: Dict) -> Dict[str, Any]:
    """Prepara dados de habilidades para o template"""
    try:
        lp_habilidades = []
        mat_habilidades = []
        lp_dentro_meta = []
        lp_abaixo_meta = []
        mat_dentro_meta = []
        mat_abaixo_meta = []
        
        if acertos_habilidade:
            # Processar Língua Portuguesa
            for disciplina, dados in acertos_habilidade.items():
                if 'portuguesa' in disciplina.lower() or 'língua' in disciplina.lower():
                    if 'habilidades' in dados:
                        for habilidade in dados['habilidades']:
                            lp_habilidades.append({
                                'questao': habilidade.get('questoes', [{}])[0].get('numero', 'N/A') if habilidade.get('questoes') else 'N/A',
                                'codigo': habilidade.get('codigo', 'N/A'),
                                'percentual': habilidade.get('percentual', 0)
                            })
                            
                            # Separar por meta
                            percentual_val = habilidade.get('percentual', 0)
                            try:
                                percentual_val = float(percentual_val)
                            except (ValueError, TypeError):
                                logging.warning(f"Could not convert percentual '{percentual_val}' to float. Defaulting to 0.0.")
                                percentual_val = 0.0
                            
                            if percentual_val >= 70:
                                lp_dentro_meta.append(f"<strong>{habilidade.get('codigo', 'N/A')}</strong> - {habilidade.get('percentual', 0):.1f}%")
                            else:
                                lp_abaixo_meta.append(f"<strong>{habilidade.get('codigo', 'N/A')}</strong> - {habilidade.get('percentual', 0):.1f}%")
                
                elif 'matemática' in disciplina.lower() or 'matematica' in disciplina.lower():
                    if 'habilidades' in dados:
                        for habilidade in dados['habilidades']:
                            mat_habilidades.append({
                                'questao': habilidade.get('questoes', [{}])[0].get('numero', 'N/A') if habilidade.get('questoes') else 'N/A',
                                'codigo': habilidade.get('codigo', 'N/A'),
                                'percentual': habilidade.get('percentual', 0)
                            })
                            
                            # Separar por meta
                            percentual_val = habilidade.get('percentual', 0)
                            try:
                                percentual_val = float(percentual_val)
                            except (ValueError, TypeError):
                                logging.warning(f"Could not convert percentual '{percentual_val}' to float. Defaulting to 0.0.")
                                percentual_val = 0.0
                            
                            if percentual_val >= 70:
                                mat_dentro_meta.append(f"<strong>{habilidade.get('codigo', 'N/A')}</strong> - {habilidade.get('percentual', 0):.1f}%")
                            else:
                                mat_abaixo_meta.append(f"<strong>{habilidade.get('codigo', 'N/A')}</strong> - {habilidade.get('percentual', 0):.1f}%")
        
        return {
            'lp_habilidades': lp_habilidades,
            'mat_habilidades': mat_habilidades,
            'lp_dentro_meta': lp_dentro_meta,
            'lp_abaixo_meta': lp_abaixo_meta,
            'mat_dentro_meta': mat_dentro_meta,
            'mat_abaixo_meta': mat_abaixo_meta
        }
        
    except Exception as e:
        logging.warning(f"Erro ao preparar dados de habilidades: {str(e)}")
        return {
            'lp_habilidades': [],
            'mat_habilidades': [],
            'lp_dentro_meta': [],
            'lp_abaixo_meta': [],
            'mat_dentro_meta': [],
            'mat_abaixo_meta': []
        }


def _obter_disciplinas_avaliacao(test: Test) -> List[str]:
    """Obtém as disciplinas da avaliação"""
    disciplinas = []
    
    logging.info(f"Identificando disciplinas para avaliação {test.id}")
    
    # Se a avaliação tem uma disciplina específica
    if test.subject_rel:
        disciplinas.append(test.subject_rel.name)
        logging.info(f"Disciplina encontrada via subject_rel: {test.subject_rel.name}")
    
    # Se tem informações de disciplinas no JSON
    if test.subjects_info and isinstance(test.subjects_info, dict):
        disciplinas.extend(test.subjects_info.keys())
        logging.info(f"Disciplinas encontradas via subjects_info: {list(test.subjects_info.keys())}")
    
    # Buscar disciplinas através das habilidades das questões
    if test.questions:
        from app.models.skill import Skill
        
        skill_ids = set()
        for question in test.questions:
            if question.skill and question.skill.strip() and question.skill != '{}':
                clean_skill_id = question.skill.replace('{', '').replace('}', '')
                skill_ids.add(clean_skill_id)
        
        logging.info(f"Skill IDs encontrados nas questões: {skill_ids}")
        
        if skill_ids:
            skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
            logging.info(f"Habilidades encontradas na tabela Skill: {len(skills)}")
            
            for skill in skills:
                if skill.subject_id:
                    subject = Subject.query.get(skill.subject_id)
                    if subject and subject.name not in disciplinas:
                        disciplinas.append(subject.name)
                        logging.info(f"Disciplina encontrada via habilidade {skill.code}: {subject.name}")
                else:
                    logging.warning(f"Habilidade {skill.code} não tem subject_id")
    
    # Se não encontrou disciplinas, usar padrão
    if not disciplinas:
        disciplinas = ["Disciplina Geral"]
        logging.warning("Nenhuma disciplina encontrada, usando padrão: Disciplina Geral")
    
    disciplinas_finais = list(set(disciplinas))  # Remove duplicatas
    logging.info(f"Disciplinas finais identificadas: {disciplinas_finais}")
    
    return disciplinas_finais


def _calcular_totais_alunos(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula totais de alunos por turma e geral"""
    class_ids = [ct.class_id for ct in class_tests]
    
    # Buscar todos os alunos das turmas onde a avaliação foi aplicada
    students = Student.query.options(
        joinedload(Student.class_).joinedload(Class.grade)
    ).filter(Student.class_id.in_(class_ids)).all()
    
    # Buscar resultados da avaliação (alunos que realizaram)
    evaluation_results = EvaluationResult.query.filter_by(test_id=evaluation_id).all()
    results_by_student = {er.student_id: er for er in evaluation_results}
    
    # Agrupar alunos por turma
    students_by_class = defaultdict(list)
    for student in students:
        students_by_class[student.class_id].append(student)
    
    # Calcular estatísticas por turma
    por_turma = []
    total_matriculados = 0
    total_avaliados = 0
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_students = students_by_class[class_id]
        
        # Matriculados = Alunos da turma onde a avaliação foi aplicada
        matriculados = len(class_students)
        # Avaliados = Alunos que realmente realizaram a avaliação (têm resultado)
        avaliados = sum(1 for s in class_students if s.id in results_by_student)
        percentual = (avaliados / matriculados * 100) if matriculados > 0 else 0
        # Faltosos = Matriculados que não realizaram
        faltosos = matriculados - avaliados
        
        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_students and class_students[0].class_:
            turma_nome = class_students[0].class_.name
        
        por_turma.append({
            "turma": turma_nome,
            "matriculados": matriculados,
            "avaliados": avaliados,
            "percentual": round(percentual, 1),
            "faltosos": faltosos
        })
        
        total_matriculados += matriculados
        total_avaliados += avaliados
    
    # Calcular totais gerais
    total_percentual = (total_avaliados / total_matriculados * 100) if total_matriculados > 0 else 0
    total_faltosos = total_matriculados - total_avaliados
    
    return {
        "por_turma": por_turma,
        "total_geral": {
            "matriculados": total_matriculados,
            "avaliados": total_avaliados,
            "percentual": round(total_percentual, 1),
            "faltosos": total_faltosos
        }
    }


def _calcular_niveis_aprendizagem(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula níveis de aprendizagem por turma e disciplina"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação para identificar disciplinas
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    logging.info(f"Calculando níveis de aprendizagem para avaliação {evaluation_id}")
    logging.info(f"Total de questões: {len(test.questions)}")
    
    # Buscar todas as habilidades para mapear ID -> disciplina
    skills_dict = {}
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    logging.info(f"Skill IDs encontrados: {skill_ids}")
    
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
        logging.info(f"Habilidades encontradas na tabela Skill: {len(skills_dict)}")
        
        for skill in skills:
            logging.info(f"Skill: {skill.id} -> {skill.code} -> subject_id: {skill.subject_id}")
    
    # Mapear questões para disciplinas
    question_disciplines = {}
    disciplinas_identificadas = set()
    
    for question in test.questions:
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                    disciplinas_identificadas.add(subject.name)
                    logging.info(f"Questão {question.id} mapeada para disciplina via skill: {subject.name}")
                else:
                    question_disciplines[question.id] = "Disciplina Geral"
                    disciplinas_identificadas.add("Disciplina Geral")
                    logging.warning(f"Subject não encontrado para skill {skill_obj.id}")
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
                if skill_obj:
                    logging.warning(f"Skill {skill_obj.id} não tem subject_id")
                else:
                    logging.warning(f"Skill não encontrado para ID: {clean_skill_id}")
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
                disciplinas_identificadas.add(test.subject_rel.name)
                logging.info(f"Questão {question.id} sem skill mapeada para disciplina principal: {test.subject_rel.name}")
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
                logging.warning(f"Questão {question.id} sem skill e avaliação sem disciplina principal")
        

    
    logging.info(f"Disciplinas identificadas nas questões: {disciplinas_identificadas}")
    logging.info(f"Questões mapeadas para disciplinas: {len(question_disciplines)}")
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    logging.info(f"Total de respostas de alunos: {len(student_answers)}")
    
    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)
    
    logging.info(f"Alunos com respostas por disciplina: {len(student_discipline_results)}")
    
    # Buscar resultados da avaliação para obter classificações
    evaluation_results = EvaluationResult.query.options(
        joinedload(EvaluationResult.student).joinedload(Student.class_)
    ).filter_by(test_id=evaluation_id).all()
    
    logging.info(f"Total de resultados de avaliação: {len(evaluation_results)}")
    
    # Agrupar por turma e disciplina
    class_ids = [ct.class_id for ct in class_tests]
    results_by_class = defaultdict(list)
    for result in evaluation_results:
        if result.student and result.student.class_id in class_ids:
            results_by_class[result.student.class_id].append(result)
    
    logging.info(f"Turmas com resultados: {list(results_by_class.keys())}")
    
    # Calcular por turma e disciplina
    disciplinas_resultado = defaultdict(lambda: {
        "por_turma": [],
        "geral": {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0, "total": 0}
    })
    
    # Dados gerais que englobam todas as disciplinas
    dados_gerais_por_turma = defaultdict(lambda: {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0, "total": 0})
    dados_gerais_total = {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0, "total": 0}
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_results = results_by_class[class_id]
        
        if not class_results:
            continue
        
        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        
        logging.info(f"Processando turma: {turma_nome}")
        
        # Para cada disciplina, calcular níveis de aprendizagem
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        logging.info(f"Disciplinas encontradas na turma {turma_nome}: {disciplinas_turma}")
        
        for disciplina in disciplinas_turma:
            # Contar classificações para esta disciplina e turma
            classificacoes = {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0}
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Se o aluno respondeu questões desta disciplina, usar sua classificação
                    classificacao = result.classification
                    if classificacao in classificacoes:
                        classificacoes[classificacao] += 1
                        disciplinas_resultado[disciplina]["geral"][classificacao] += 1
            
            total_turma = sum(classificacoes.values())
            disciplinas_resultado[disciplina]["geral"]["total"] += total_turma
            
            disciplinas_resultado[disciplina]["por_turma"].append({
                "turma": turma_nome,
                "abaixo_do_basico": classificacoes["Abaixo do Básico"],
                "basico": classificacoes["Básico"],
                "adequado": classificacoes["Adequado"],
                "avancado": classificacoes["Avançado"],
                "total": total_turma
            })
        
        # Calcular dados gerais para esta turma (todas as disciplinas)
        for result in class_results:
            classificacao = result.classification
            if classificacao in dados_gerais_por_turma[turma_nome]:
                dados_gerais_por_turma[turma_nome][classificacao] += 1
                dados_gerais_por_turma[turma_nome]["total"] += 1
                dados_gerais_total[classificacao] += 1
                dados_gerais_total["total"] += 1
    
    # Organizar resultado final
    resultado_final = {}
    for disciplina, dados in disciplinas_resultado.items():
        resultado_final[disciplina] = {
            "por_turma": dados["por_turma"],
            "geral": {
                "abaixo_do_basico": dados["geral"]["Abaixo do Básico"],
                "basico": dados["geral"]["Básico"],
                "adequado": dados["geral"]["Adequado"],
                "avancado": dados["geral"]["Avançado"],
                "total": dados["geral"]["total"]
            }
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    dados_gerais_por_turma_lista = []
    for turma, dados in dados_gerais_por_turma.items():
        dados_gerais_por_turma_lista.append({
            "turma": turma,
            "abaixo_do_basico": dados["Abaixo do Básico"],
            "basico": dados["Básico"],
            "adequado": dados["Adequado"],
            "avancado": dados["Avançado"],
            "total": dados["total"]
        })
    
    resultado_final["GERAL"] = {
        "por_turma": dados_gerais_por_turma_lista,
        "geral": {
            "abaixo_do_basico": dados_gerais_total["Abaixo do Básico"],
            "basico": dados_gerais_total["Básico"],
            "adequado": dados_gerais_total["Adequado"],
            "avancado": dados_gerais_total["Avançado"],
            "total": dados_gerais_total["total"]
        }
    }
    
    logging.info(f"Resultado final com disciplinas: {list(resultado_final.keys())}")
    
    return resultado_final


def _calcular_proficiencia(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula proficiência por turma e disciplina"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação para identificar disciplinas
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    # Buscar todas as habilidades para mapear ID -> disciplina
    skills_dict = {}
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
    
    # Mapear questões para disciplinas
    question_disciplines = {}
    for question in test.questions:
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                else:
                    question_disciplines[question.id] = "Disciplina Geral"
            else:
                question_disciplines[question.id] = "Disciplina Geral"
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
            else:
                question_disciplines[question.id] = "Disciplina Geral"
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    
    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)
    
    # Buscar resultados da avaliação para obter proficiências
    evaluation_results = EvaluationResult.query.options(
        joinedload(EvaluationResult.student).joinedload(Student.class_)
    ).filter_by(test_id=evaluation_id).all()
    
    # Agrupar por turma e disciplina
    class_ids = [ct.class_id for ct in class_tests]
    results_by_class = defaultdict(list)
    for result in evaluation_results:
        if result.student and result.student.class_id in class_ids:
            results_by_class[result.student.class_id].append(result)
    
    # Calcular por turma e disciplina
    disciplinas_proficiencia = defaultdict(lambda: {
        "por_turma": [],
        "total_proficiencia": 0,
        "total_alunos": 0
    })
    
    # Dados gerais que englobam todas as disciplinas
    dados_gerais_por_turma = defaultdict(list)
    dados_gerais_total_proficiencia = 0
    dados_gerais_total_alunos = 0
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_results = results_by_class[class_id]
        
        if not class_results:
            continue
        
        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        
        # Para cada disciplina, calcular proficiência
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        for disciplina in disciplinas_turma:
            # Calcular proficiência para esta disciplina e turma
            proficiencias_disciplina = []
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Se o aluno respondeu questões desta disciplina, usar sua proficiência
                    if result.proficiency is not None:
                        proficiencias_disciplina.append(result.proficiency)
            
            if proficiencias_disciplina:
                media_proficiencia = sum(proficiencias_disciplina) / len(proficiencias_disciplina)
                disciplinas_proficiencia[disciplina]["total_proficiencia"] += sum(proficiencias_disciplina)
                disciplinas_proficiencia[disciplina]["total_alunos"] += len(proficiencias_disciplina)
                
                disciplinas_proficiencia[disciplina]["por_turma"].append({
                    "turma": turma_nome,
                    "proficiencia": round(media_proficiencia, 2)
                })
        
        # Calcular dados gerais para esta turma (todas as disciplinas)
        proficiencias_gerais_turma = []
        for result in class_results:
            if result.proficiency is not None:
                proficiencias_gerais_turma.append(result.proficiency)
        
        if proficiencias_gerais_turma:
            media_proficiencia_geral_turma = sum(proficiencias_gerais_turma) / len(proficiencias_gerais_turma)
            dados_gerais_por_turma[turma_nome].append({
                "turma": turma_nome,
                "proficiencia": round(media_proficiencia_geral_turma, 2)
            })
            dados_gerais_total_proficiencia += sum(proficiencias_gerais_turma)
            dados_gerais_total_alunos += len(proficiencias_gerais_turma)
    
    # Organizar resultado final
    resultado_final = {}
    for disciplina, dados in disciplinas_proficiencia.items():
        media_geral_disciplina = dados["total_proficiencia"] / dados["total_alunos"] if dados["total_alunos"] > 0 else 0
        
        resultado_final[disciplina] = {
            "por_turma": sorted(dados["por_turma"], key=lambda x: x["turma"]),
            "media_geral": round(media_geral_disciplina, 2)
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    media_geral_total = dados_gerais_total_proficiencia / dados_gerais_total_alunos if dados_gerais_total_alunos > 0 else 0
    
    resultado_final["GERAL"] = {
        "por_turma": sorted([dados for dados_list in dados_gerais_por_turma.values() for dados in dados_list], key=lambda x: x["turma"]),
        "media_geral": round(media_geral_total, 2)
    }
    
    # Calcular média municipal por disciplina
    media_municipal_por_disciplina = _calcular_media_municipal_por_disciplina(evaluation_id, question_disciplines)
    
    return {
        "por_disciplina": resultado_final,
        "media_municipal_por_disciplina": media_municipal_por_disciplina
    }


def _calcular_nota_geral(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula nota geral por turma e disciplina"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação para identificar disciplinas
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    # Buscar todas as habilidades para mapear ID -> disciplina
    skills_dict = {}
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
    
    # Mapear questões para disciplinas
    question_disciplines = {}
    for question in test.questions:
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                else:
                    question_disciplines[question.id] = "Disciplina Geral"
            else:
                question_disciplines[question.id] = "Disciplina Geral"
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
            else:
                question_disciplines[question.id] = "Disciplina Geral"
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    
    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)
    
    # Buscar resultados da avaliação para obter notas
    evaluation_results = EvaluationResult.query.options(
        joinedload(EvaluationResult.student).joinedload(Student.class_)
    ).filter_by(test_id=evaluation_id).all()
    
    # Agrupar por turma e disciplina
    class_ids = [ct.class_id for ct in class_tests]
    results_by_class = defaultdict(list)
    for result in evaluation_results:
        if result.student and result.student.class_id in class_ids:
            results_by_class[result.student.class_id].append(result)
    
    # Calcular por turma e disciplina
    disciplinas_notas = defaultdict(lambda: {
        "por_turma": [],
        "total_notas": 0,
        "total_alunos": 0
    })
    
    # Dados gerais que englobam todas as disciplinas
    dados_gerais_por_turma = defaultdict(list)
    dados_gerais_total_notas = 0
    dados_gerais_total_alunos = 0
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_results = results_by_class[class_id]
        
        if not class_results:
            continue
        
        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        
        # Para cada disciplina, calcular nota
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        for disciplina in disciplinas_turma:
            # Calcular nota para esta disciplina e turma
            notas_disciplina = []
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Se o aluno respondeu questões desta disciplina, usar sua nota
                    if result.grade is not None:
                        notas_disciplina.append(result.grade)
            
            if notas_disciplina:
                media_nota = sum(notas_disciplina) / len(notas_disciplina)
                disciplinas_notas[disciplina]["total_notas"] += sum(notas_disciplina)
                disciplinas_notas[disciplina]["total_alunos"] += len(notas_disciplina)
                
                disciplinas_notas[disciplina]["por_turma"].append({
                    "turma": turma_nome,
                    "nota": round(media_nota, 2)
                })
        
        # Calcular dados gerais para esta turma (todas as disciplinas)
        notas_gerais_turma = []
        for result in class_results:
            if result.grade is not None:
                notas_gerais_turma.append(result.grade)
        
        if notas_gerais_turma:
            media_nota_geral_turma = sum(notas_gerais_turma) / len(notas_gerais_turma)
            dados_gerais_por_turma[turma_nome].append({
                "turma": turma_nome,
                "nota": round(media_nota_geral_turma, 2)
            })
            dados_gerais_total_notas += sum(notas_gerais_turma)
            dados_gerais_total_alunos += len(notas_gerais_turma)
    
    # Organizar resultado final
    resultado_final = {}
    for disciplina, dados in disciplinas_notas.items():
        media_geral_disciplina = dados["total_notas"] / dados["total_alunos"] if dados["total_alunos"] > 0 else 0
        
        resultado_final[disciplina] = {
            "por_turma": sorted(dados["por_turma"], key=lambda x: x["turma"]),
            "media_geral": round(media_geral_disciplina, 2)
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    media_geral_total = dados_gerais_total_notas / dados_gerais_total_alunos if dados_gerais_total_alunos > 0 else 0
    
    resultado_final["GERAL"] = {
        "por_turma": sorted([dados for dados_list in dados_gerais_por_turma.values() for dados in dados_list], key=lambda x: x["turma"]),
        "media_geral": round(media_geral_total, 2)
    }
    
    # Calcular média municipal por disciplina
    media_municipal_por_disciplina = _calcular_media_municipal_nota_por_disciplina(evaluation_id, question_disciplines)
    
    return {
        "por_disciplina": resultado_final,
        "media_municipal_por_disciplina": media_municipal_por_disciplina
    }


def _calcular_acertos_habilidade(evaluation_id: str) -> Dict[str, Any]:
    """Calcula acertos por habilidade e ranking organizados por disciplina"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    
    # Agrupar respostas por questão
    answers_by_question = defaultdict(list)
    for answer in student_answers:
        answers_by_question[answer.question_id].append(answer)
    
    # Buscar todas as habilidades para mapear ID -> código
    skills_dict = {}
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            # Remover chaves {} do UUID se existirem
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
        
        # Debug detalhado
        logging.info(f"Skill IDs encontrados: {skill_ids}")
        logging.info(f"Habilidades encontradas na tabela: {len(skills_dict)}")
        for skill in skills:
            logging.info(f"Skill encontrada: {skill.id} -> {skill.code}")
        
        # Verificar quais IDs não foram encontrados
        not_found = skill_ids - set(skills_dict.keys())
        if not_found:
            logging.warning(f"Skill IDs não encontrados: {not_found}")
    
    # Calcular acertos por habilidade e disciplina
    disciplinas_habilidades = defaultdict(lambda: defaultdict(lambda: {"total": 0, "acertos": 0, "questoes": []}))
    
    # Dados gerais que englobam todas as disciplinas
    habilidades_gerais = defaultdict(lambda: {"total": 0, "acertos": 0, "questoes": []})
    
    for question in test.questions:
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            # Remover chaves {} do UUID se existirem
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            # Se não encontrou a habilidade na tabela Skill, usar o ID como código
            if not skill_obj:
                skill_code = clean_skill_id
                disciplina = "Disciplina Geral"
                logging.warning(f"Habilidade não encontrada na tabela Skill: {clean_skill_id}")
            else:
                skill_code = skill_obj.code
                # Obter disciplina da habilidade
                if skill_obj.subject_id:
                    # Buscar a disciplina pelo subject_id
                    subject = Subject.query.get(skill_obj.subject_id)
                    if subject:
                        disciplina = subject.name
                    else:
                        disciplina = "Disciplina Geral"
                else:
                    disciplina = "Disciplina Geral"
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                disciplina = test.subject_rel.name
                skill_code = f"Questão {question.number or 'N/A'}"
                logging.info(f"Questão {question.id} sem skill mapeada para disciplina principal: {test.subject_rel.name}")
            else:
                disciplina = "Disciplina Geral"
                skill_code = f"Questão {question.number or 'N/A'}"
                logging.warning(f"Questão {question.id} sem skill e avaliação sem disciplina principal")
        
        answers = answers_by_question.get(question.id, [])
        
        total_respostas = len(answers)
        acertos = 0
        
        for answer in answers:
            # Verificar se a resposta está correta
            if question.question_type == 'multipleChoice':
                # Para múltipla escolha, verificar se a resposta está nas alternativas corretas
                if question.alternatives:
                    correct_alternatives = [alt for alt in question.alternatives if alt.get('isCorrect', False)]
                    if any(answer.answer == alt.get('text', '') for alt in correct_alternatives):
                        acertos += 1
            else:
                # Para outros tipos, comparar com correct_answer
                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                    acertos += 1
        
        disciplinas_habilidades[disciplina][skill_code]["total"] += total_respostas
        disciplinas_habilidades[disciplina][skill_code]["acertos"] += acertos
        disciplinas_habilidades[disciplina][skill_code]["questoes"].append({
            "numero": question.number or 1,
            "acertos": acertos,
            "total": total_respostas
        })
        
        # Adicionar aos dados gerais
        habilidades_gerais[skill_code]["total"] += total_respostas
        habilidades_gerais[skill_code]["acertos"] += acertos
        habilidades_gerais[skill_code]["questoes"].append({
            "numero": question.number or 1,
            "acertos": acertos,
            "total": total_respostas
        })
    
    # Organizar resultado por disciplina
    resultado_por_disciplina = {}
    
    for disciplina, habilidades in disciplinas_habilidades.items():
        # Calcular percentuais e ranking para esta disciplina
        habilidades_ranking = []
        for skill_code, dados in habilidades.items():
            if dados["total"] > 0:
                percentual = (dados["acertos"] / dados["total"]) * 100
                habilidades_ranking.append({
                    "codigo": skill_code,
                    "descricao": f"Habilidade {skill_code}",
                    "acertos": dados["acertos"],
                    "total": dados["total"],
                    "percentual": round(percentual, 1),
                    "questoes": dados["questoes"]
                })
        
        # Ordenar por percentual (maior para menor)
        habilidades_ranking.sort(key=lambda x: x["percentual"], reverse=True)
        
        # Adicionar ranking
        for i, habilidade in enumerate(habilidades_ranking, 1):
            habilidade["ranking"] = i
        
        resultado_por_disciplina[disciplina] = {
            "habilidades": habilidades_ranking
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    habilidades_gerais_ranking = []
    for skill_code, dados in habilidades_gerais.items():
        if dados["total"] > 0:
            percentual = (dados["acertos"] / dados["total"]) * 100
            habilidades_gerais_ranking.append({
                "codigo": skill_code,
                "descricao": f"Habilidade {skill_code}",
                "acertos": dados["acertos"],
                "total": dados["total"],
                "percentual": round(percentual, 1),
                "questoes": dados["questoes"]
            })
    
    # Ordenar por percentual (maior para menor)
    habilidades_gerais_ranking.sort(key=lambda x: x["percentual"], reverse=True)
    
    # Adicionar ranking
    for i, habilidade in enumerate(habilidades_gerais_ranking, 1):
        habilidade["ranking"] = i
    
    resultado_por_disciplina["GERAL"] = {
        "habilidades": habilidades_gerais_ranking
    }
    
    return resultado_por_disciplina


def _calcular_media_municipal(evaluation_id: str) -> float:
    """Calcula média de proficiência municipal"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return 0.0
        
        # Buscar turmas da avaliação
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return 0.0
        
        # Obter município da primeira turma
        first_class = Class.query.get(class_tests[0].class_id)
        if not first_class or not first_class.school:
            return 0.0
        
        city_id = first_class.school.city_id
        
        # Buscar todos os resultados do município para esta avaliação
        municipal_results = db.session.query(EvaluationResult).join(
            Student, EvaluationResult.student_id == Student.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            School.city_id == city_id,
            EvaluationResult.test_id == evaluation_id
        ).all()
        
        if not municipal_results:
            return 0.0
        
        media_municipal = sum(r.proficiency for r in municipal_results) / len(municipal_results)
        return media_municipal
        
    except Exception as e:
        logging.error(f"Erro ao calcular média municipal: {str(e)}")
        return 0.0


def _calcular_media_municipal_nota(evaluation_id: str) -> float:
    """Calcula média de nota municipal"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return 0.0
        
        # Buscar turmas da avaliação
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return 0.0
        
        # Obter município da primeira turma
        first_class = Class.query.get(class_tests[0].class_id)
        if not first_class or not first_class.school:
            return 0.0
        
        city_id = first_class.school.city_id
        
        # Buscar todos os resultados do município para esta avaliação
        municipal_results = db.session.query(EvaluationResult).join(
            Student, EvaluationResult.student_id == Student.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            School.city_id == city_id,
            EvaluationResult.test_id == evaluation_id
        ).all()
        
        if not municipal_results:
            return 0.0
        
        media_municipal = sum(r.grade for r in municipal_results) / len(municipal_results)
        return media_municipal
        
    except Exception as e:
        logging.error(f"Erro ao calcular média municipal de nota: {str(e)}")
        return 0.0


def _calcular_media_municipal_por_disciplina(evaluation_id: str, question_disciplines: Dict[str, str]) -> Dict[str, float]:
    """Calcula média de proficiência municipal por disciplina"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return {}
        
        # Buscar turmas da avaliação
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return {}
        
        # Obter município da primeira turma
        first_class = Class.query.get(class_tests[0].class_id)
        if not first_class or not first_class.school:
            return {}
        
        city_id = first_class.school.city_id
        
        # Buscar todos os resultados do município para esta avaliação
        municipal_results = db.session.query(EvaluationResult).join(
            Student, EvaluationResult.student_id == Student.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            School.city_id == city_id,
            EvaluationResult.test_id == evaluation_id
        ).all()
        
        if not municipal_results:
            return {}
        
        # Buscar respostas dos alunos do município
        student_ids = [r.student_id for r in municipal_results]
        municipal_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == evaluation_id,
            StudentAnswer.student_id.in_(student_ids)
        ).all()
        
        # Agrupar respostas por aluno e disciplina
        student_discipline_results = defaultdict(lambda: defaultdict(list))
        
        for answer in municipal_answers:
            if answer.question_id in question_disciplines:
                disciplina = question_disciplines[answer.question_id]
                student_discipline_results[answer.student_id][disciplina].append(answer)
        
        # Calcular média por disciplina
        disciplinas_proficiencia = defaultdict(list)
        
        for result in municipal_results:
            student_id = result.student_id
            if student_id in student_discipline_results and result.proficiency is not None:
                for disciplina in student_discipline_results[student_id].keys():
                    disciplinas_proficiencia[disciplina].append(result.proficiency)
        
        # Calcular média para cada disciplina
        medias_por_disciplina = {}
        for disciplina, proficiencias in disciplinas_proficiencia.items():
            if proficiencias:
                media = sum(proficiencias) / len(proficiencias)
                medias_por_disciplina[disciplina] = round(media, 2)
        
        return medias_por_disciplina
        
    except Exception as e:
        logging.error(f"Erro ao calcular média municipal por disciplina: {str(e)}")
        return {}


def _calcular_media_municipal_nota_por_disciplina(evaluation_id: str, question_disciplines: Dict[str, str]) -> Dict[str, float]:
    """Calcula média de nota municipal por disciplina"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return {}
        
        # Buscar turmas da avaliação
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        if not class_tests:
            return {}
        
        # Obter município da primeira turma
        first_class = Class.query.get(class_tests[0].class_id)
        if not first_class or not first_class.school:
            return {}
        
        city_id = first_class.school.city_id
        
        # Buscar todos os resultados do município para esta avaliação
        municipal_results = db.session.query(EvaluationResult).join(
            Student, EvaluationResult.student_id == Student.id
        ).join(
            Class, Student.class_id == Class.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            School.city_id == city_id,
            EvaluationResult.test_id == evaluation_id
        ).all()
        
        if not municipal_results:
            return {}
        
        # Buscar respostas dos alunos do município
        student_ids = [r.student_id for r in municipal_results]
        municipal_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == evaluation_id,
            StudentAnswer.student_id.in_(student_ids)
        ).all()
        
        # Agrupar respostas por aluno e disciplina
        student_discipline_results = defaultdict(lambda: defaultdict(list))
        
        for answer in municipal_answers:
            if answer.question_id in question_disciplines:
                disciplina = question_disciplines[answer.question_id]
                student_discipline_results[answer.student_id][disciplina].append(answer)
        
        # Calcular média por disciplina
        disciplinas_notas = defaultdict(list)
        
        for result in municipal_results:
            student_id = result.student_id
            if student_id in student_discipline_results and result.grade is not None:
                for disciplina in student_discipline_results[student_id].keys():
                    disciplinas_notas[disciplina].append(result.grade)
        
        # Calcular média para cada disciplina
        medias_por_disciplina = {}
        for disciplina, notas in disciplinas_notas.items():
            if notas:
                media = sum(notas) / len(notas)
                medias_por_disciplina[disciplina] = round(media, 2)
        
        return medias_por_disciplina
        
    except Exception as e:
        logging.error(f"Erro ao calcular média municipal de nota por disciplina: {str(e)}")
        return {}


def _gerar_pdf_reportlab(template_data: Dict[str, Any]) -> bytes:
    """Gera PDF usando ReportLab replicando fielmente o template HTML"""
    
    buffer = BytesIO()

    # Margens do modelo (~14–18mm)
    LEFT = RIGHT = 14*mm
    TOP = 16*mm
    BOTTOM = 18*mm

    doc = BaseDocTemplate(
        buffer, pagesize=A4,
        leftMargin=LEFT, rightMargin=RIGHT, topMargin=TOP, bottomMargin=BOTTOM
    )
    frame = Frame(LEFT, BOTTOM, doc.width, doc.height, id='normal')
    doc.addPageTemplates([
        PageTemplate(id='pagina', frames=[frame],
                     onPage=lambda c,d: _header(c,d, template_data.get("logo_esquerda"), template_data.get("logo_direita")))
    ])

    # ======== ESTILOS ========
    styles = getSampleStyleSheet()
    title = ParagraphStyle('TitleItal',
        parent=styles['Heading1'], fontName='Helvetica-BoldOblique',
        fontSize=22, alignment=TA_CENTER, spaceAfter=12)
    
    subtitle = ParagraphStyle('Sub',
        parent=styles['Heading2'], fontName='Helvetica-Bold',
        fontSize=16, alignment=TA_CENTER, spaceBefore=30, spaceAfter=6)
    mutedCenter = ParagraphStyle('MutedC',
        parent=styles['Normal'], fontSize=12, textColor=colors.HexColor('#111'),
        alignment=TA_CENTER, spaceAfter=2)
    hSection = ParagraphStyle('HSection',
        parent=styles['Heading2'], fontSize=13.5, spaceBefore=6, spaceAfter=6,
        fontName='Helvetica-Bold')
    hBlock = ParagraphStyle('HBlock',
        parent=styles['Normal'], fontSize=12, fontName='Helvetica-Bold',
        spaceBefore=8, spaceAfter=4)
    normal = ParagraphStyle('Normal12', parent=styles['Normal'], fontSize=12, leading=16)
    bold = ParagraphStyle('Bold12', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=16)
    small = ParagraphStyle('Small', parent=styles['Normal'], fontSize=11, leading=14)
    
    story = []
    
    # ================== CAPA ==================
    story.append(Spacer(1, 90))
    story.append(Paragraph(f"<b><i>RELATÓRIO DA AVALIAÇÃO DIAGNÓSTICA {template_data.get('periodo','2025.1')}</i></b>", title))
    story.append(Paragraph("DA REDE MUNICIPAL DE ENSINO", mutedCenter))
    story.append(Paragraph(f"{template_data.get('municipio','CAMPO ALEGRE')} / {template_data.get('uf','AL')}", mutedCenter))
    story.append(Spacer(1, 45))
    story.append(Paragraph(template_data.get('escola','E. M. E. B. MONSENHOR HILDEBRANDO'), subtitle))
    story.append(Spacer(1, 120))
    story.append(Paragraph(f"{template_data.get('mes','MAIO')} / {template_data.get('ano','2025')}", mutedCenter))
    story.append(PageBreak())
    
    # ================== SUMÁRIO ==================
    story.append(Paragraph("SUMÁRIO", hSection))
    def linha_sumario(txt, pagina):
        # alinha número da página à direita como no modelo
        return Paragraph(f"{txt} <font size='12'>{pagina}</font>", normal)
    story += [
        linha_sumario("1. APRESENTAÇÃO", template_data.get('sumario_p1','3')),
        linha_sumario("2. CONSIDERAÇÕES GERAIS", template_data.get('sumario_p2','3')),
        linha_sumario("3. PARTICIPAÇÃO DA REDE NO PROCESSO DE AVALIAÇÃO DIAGNÓSTICA", template_data.get('sumario_p3','4')),
        linha_sumario("4. RENDIMENTO POR SÉRIE, POR TURMA E POR ESCOLA", template_data.get('sumario_p4','4')),
        linha_sumario("4.1 PROFICIÊNCIA POR UNIDADE DE ENSINO/ TURMA - 9º ANO", template_data.get('sumario_p41','4-5')),
        linha_sumario("4.2 NOTA POR UNIDADE DE ENSINO/ TURMA - 9º ANO", template_data.get('sumario_p42','5')),
        linha_sumario("4.3 ACERTOS POR HABILIDADE POR UNIDADE DE ENSINO/ TURMA - 9º ANO", template_data.get('sumario_p43','6')),
        linha_sumario("4.4 ACERTOS POR HABILIDADE POR UNIDADE DE ENSINO/ TURMA - 9º ANO", template_data.get('sumario_p44','7')),
    ]
    story.append(PageBreak())
    
    # ================== 1. APRESENTAÇÃO ==================
    story.append(Paragraph("1. APRESENTAÇÃO", hSection))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Este relatório apresenta os resultados do <b>{template_data.get('simulados_label','1º Simulado')}</b> "
        f"da Rede Municipal de Ensino de <b>{template_data.get('municipio','Campo Alegre')} – {template_data.get('uf','AL')}</b> "
        f"referente ao <b>{template_data.get('referencia','9º de 2025')}</b> da <b>{template_data.get('escola_extenso','ESCOLA MUNICIPAL DE EDUCAÇÃO BÁSICA MONSENHOR HILDEBRANDO')}</b>. "
        f"Foram avaliados <b>{template_data.get('total_avaliados',222)}</b> alunos, o que corresponde a <b>{template_data.get('percentual_avaliados','89%')}</b> do total de estudantes dessas séries.",
        normal
    ))
    story.append(Paragraph("<b>Para a análise, utilizamos:</b>", normal))
    for li in ["Frequência absoluta (número de alunos)", "Frequência relativa (percentual)", "Média aritmética simples"]:
        story.append(Paragraph(f"&bull; {li}", normal))
    story.append(Paragraph(
        "As competências avaliadas foram <b>Língua Portuguesa</b> e <b>Matemática</b>... "
        "Gráficos nominais por aluno e rendimento de cada turma estão disponíveis na <b>Plataforma InnovPlay</b>.",
        normal
    ))
    story.append(Paragraph(
        "A escala de cores das médias variou do <b>vermelho (0)</b> ao <b>verde (10)</b>... "
        "índice de erro superior a <b>40%</b> em destaque vermelho.", normal))
    story.append(PageBreak())
    
    # ================== 2. CONSIDERAÇÕES GERAIS ==================
    story.append(Paragraph("2. CONSIDERAÇÕES GERAIS", hSection))
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("""
    Antes de olharmos os resultados é importante nos atentarmos que cada escola tem suas especificidades, assim como cada turma. 
    Existem resultados que só serão explicados considerando estas especificidades.
    """, normal))
    
    story.append(Paragraph("""
    As turmas são únicas e, portanto, a observação das necessidades de cada turma deve ser analisada através do sistema.
    """, normal))
    
    story.append(Paragraph("""
    Foram constatadas algumas inconsistências em algumas questões. Para conhecimento:
    """, normal))
    
    # Nota destacada
    note_text = f"""
    A necessidade de anulação de <b>{template_data.get('qtd_questoes_anuladas', 2)}</b> questões de <b>Matemática</b> direcionadas ao <b>{template_data.get('serie_alvo', '9º ano')}</b>. 
    As questões (<b>nº {template_data.get('questoes_anuladas', '10 e 11')}</b> do material da SEMED), referentes a <b>{template_data.get('ordens_avaliacao', '36ª e 37ª')}</b> na avaliação InnovPlay foram enviadas com possíveis erros pela equipe responsável pela elaboração da SEMED, 
    por este motivo havendo a necessidade de anular.
    """
    story.append(Paragraph(note_text, normal))
    
    story.append(PageBreak())
    
    # ================== 3. PARTICIPAÇÃO ==================
    story.append(Paragraph("3. PARTICIPAÇÃO DA REDE NO PROCESSO DE AVALIAÇÃO DIAGNÓSTICA", hSection))
    
    # Cabeçalho cinza simples
    story.append(Paragraph(f"<b>TOTAL DE ALUNOS QUE REALIZARAM A AVALIAÇÃO DIAGNÓSTICA {template_data.get('periodo','2025.1')}</b>", hBlock))
    
    # Tabela de participação simplificada
    if template_data.get("participacao"):
        participacao_data = [["SÉRIE/TURNO","MATRICULADOS","AVALIADOS","PERCENTUAL","FALTOSOS"]]
        
        for r in template_data.get("participacao", []):
            participacao_data.append([
                r.get("serie_turno", ""),
                str(r.get("matriculados", 0)),
                str(r.get("avaliados", 0)),
                f"{r.get('percentual', 0)}%",
                str(r.get("faltosos", 0))
            ])
        
        # Adicionar linha total
        participacao_data.append([
            template_data.get("total_label","9º GERAL"),
            str(template_data.get("total_matriculados",0)),
            str(template_data.get("total_avaliados",0)),
            template_data.get("percentual_avaliados","0%"),
            str(template_data.get("total_faltosos",0))
        ])
        
        # Criar tabela
        colw = [doc.width*0.35, doc.width*0.16, doc.width*0.16, doc.width*0.16, doc.width*0.17]
        t = Table(participacao_data, colWidths=colw, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0), BLUE_900), ('TEXTCOLOR',(0,0),(-1,0), colors.white),
            ('ALIGN',(1,1),(-1,-1),'RIGHT'), ('ALIGN',(0,1),(0,-1),'LEFT'),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('GRID',(0,0),(-1,-1), 0.7, GRID), ('FONTSIZE',(0,0),(-1,-1),11),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('BACKGROUND', (0,len(participacao_data)-1), (-1,len(participacao_data)-1), GRAY_150),
            ('FONTNAME',(0,len(participacao_data)-1),(-1,len(participacao_data)-1),'Helvetica-Bold'),
        ]))
        
        story.append(KeepTogether(t))
        story.append(Spacer(1,6))
    
    # Texto de participação
    story.append(Paragraph(template_data.get("participacao_texto_padrao",
        "A escola avaliou alunos do 9º ano... planejamento de reposição diagnóstica."), normal))
    
    # ===== 4. RENDIMENTO =====
    story.append(Paragraph("4. RENDIMENTO POR SÉRIE, POR TURMA E POR ESCOLA", hSection))
    
    # ===== NÍVEIS LP/MAT/MÉDIA (colunas coloridas) =====
    def tabela_niveis(titulo, rows, totais=None):
        story.append(Spacer(1,6))
        story.append(Paragraph(titulo, hBlock))
        hdr = ["SÉRIE/TURNO","ABAIXO DO BÁSICO","BÁSICO","ADEQUADO","AVANÇADO"]
        data = [hdr] + rows + ([totais] if totais else [])
        t = Table(data, colWidths=[doc.width*0.34, doc.width*0.165, doc.width*0.165, doc.width*0.165, doc.width*0.165], repeatRows=1)
        t.setStyle(TableStyle([
            ('GRID',(0,0),(-1,-1),0.7, GRID), ('FONTSIZE',(0,0),(-1,-1),11),
            ('BACKGROUND',(0,0),(0,0), BLUE_900), ('TEXTCOLOR',(0,0),(0,0), colors.white),
            ('BACKGROUND',(1,0),(1,0), RED), ('BACKGROUND',(2,0),(2,0), YELLOW),
            ('BACKGROUND',(3,0),(3,0), ADEQ), ('BACKGROUND',(4,0),(4,0), GREEN),
            ('TEXTCOLOR',(1,0),(-1,0), colors.white),
            ('ALIGN',(1,1),(-1,-1),'RIGHT'), ('ALIGN',(0,1),(0,-1),'LEFT'),
        ]))
        if totais:
            t.setStyle(TableStyle([('BACKGROUND', (0,len(rows)+1), (-1,len(rows)+1), GRAY_150),
                                   ('FONTNAME',(0,len(rows)+1),(-1,len(rows)+1),'Helvetica-Bold')]), append=True)
        story.append(KeepTogether(t))

    tabela_niveis("LÍNGUA PORTUGUESA", template_data.get("lp_niveis", []),
                  template_data.get("lp_totais"))
    story.append(Paragraph("<b>Língua Portuguesa (total de 222 alunos avaliados):</b>", bold))
    for li in template_data.get("lp_resumo_lista", [
        "Abaixo do Básico: 20 alunos (9,0%)","Básico: 27 alunos (12,2%)",
        "Adequado: 45 alunos (20,3%)","Avançado: 130 alunos (58,6%)"
    ]):
        story.append(Paragraph(f"&bull; {li}", normal))

    tabela_niveis("MATEMÁTICA", template_data.get("mat_niveis", []),
                  template_data.get("mat_totais"))
    # idem resumos…
    # tabela_niveis("MÉDIA GERAL", ...)

    story.append(PageBreak())

    # ===== PROFICIÊNCIA (com "badge" municipal) =====
    story.append(Paragraph("PROFICIÊNCIA POR TURMA/GERAL – AVALIAÇÃO DIAGNÓSTICA " + template_data.get("periodo","2025.1"), hBlock))
    prof_hdr = ["SÉRIE/TURNO","LÍNGUA PORTUGUESA","MATEMÁTICA","MÉDIA","MUNICIPAL"]
    prof_rows = [prof_hdr]
    for p in template_data.get("proficiencia", []):
        prof_rows.append([p["serie_turno"], p["lp"], p["mat"], p.get("media",""), p.get("municipal","")])
    prof = Table(prof_rows, colWidths=[doc.width*0.30, doc.width*0.17, doc.width*0.17, doc.width*0.17, doc.width*0.19], repeatRows=1)
    prof.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0), GRAY_150), ('GRID',(0,0),(-1,-1),0.7, GRID),
        ('ALIGN',(1,1),(-2,-1),'RIGHT'), ('ALIGN',(-1,1),(-1,-1),'CENTER'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
    ]))
    story.append(prof)
    story.append(Spacer(1,6))
    story.append(Paragraph(template_data.get("proficiencia_texto_padrao",
        "A proficiência média da escola nesta avaliação diagnóstica foi de 298,86 em LP e 268,29 em Matemática..."), normal))

    # ===== NOTA =====
    story.append(Spacer(1,8))
    story.append(Paragraph("NOTA POR TURMA/GERAL – AVALIAÇÃO DIAGNÓSTICA " + template_data.get("periodo","2025.1"), hBlock))
    # ... montar tabela e texto idênticos

    story.append(PageBreak())
    
    # ===== ACERTOS POR HABILIDADE (duas linhas de 13 colunas) =====
    story.append(Paragraph("ACERTOS POR HABILIDADE TURMA/GERAL – AVALIAÇÃO DIAGNÓSTICA " + template_data.get("periodo","2025.1"), hBlock))
    story.append(Paragraph("LÍNGUA PORTUGUESA", hBlock))
    def grid_13(rotulos, pct):
        # Verificar se os dados existem e têm o tamanho correto
        if not rotulos or not pct or len(rotulos) != 13 or len(pct) != 13:
            # Retornar tabela vazia se os dados não estiverem corretos
            empty_data = [['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10', 'H11', 'H12', 'H13'],
                         ['0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%', '0%']]
            t = Table(empty_data, colWidths=[doc.width/13.0]*13)
            t.setStyle(TableStyle([
                ('GRID',(0,0),(-1,-1),0.7, GRID),
                ('BACKGROUND',(0,0),(-1,0), BLUE_900), ('TEXTCOLOR',(0,0),(-1,0), colors.white),
                ('ALIGN',(0,0),(-1,-1),'CENTER'), ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ]))
            return t
        
        data = [rotulos, pct]
        colw = [doc.width/13.0]*13
        t = Table(data, colWidths=colw)
        st = TableStyle([
            ('GRID',(0,0),(-1,-1),0.7, GRID),
            ('BACKGROUND',(0,0),(-1,0), BLUE_900), ('TEXTCOLOR',(0,0),(-1,0), colors.white),
            ('ALIGN',(0,0),(-1,-1),'CENTER'), ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ])
        # cores por faixa
        for i, val in enumerate(pct):
            try:
                v = float(str(val).replace('%','').replace(',','.'))
            except: 
                v = 0
            color = colors.white
            if v < 60: color = colors.HexColor("#ffd1d1")
            elif v < 70: color = colors.HexColor("#ffe9b3")
            elif v < 80: color = colors.HexColor("#d6f5d6")
            else: color = colors.HexColor("#b9eabb")
            st.add('BACKGROUND',(i,1),(i,1), color)
            st.add('FONTNAME',(i,1),(i,1),'Helvetica-Bold')
        t.setStyle(st)
        return t

    story.append(grid_13(template_data.get("lp_rotulos_1_13", []), template_data.get("lp_pct_1_13", [])))
    story.append(Spacer(1,6))
    story.append(grid_13(template_data.get("lp_rotulos_14_26", []), template_data.get("lp_pct_14_26", [])))
    # … listas "dentro da meta/abaixo da meta" como Paragraph + bullets

    # ===== FINALIZA =====
    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content


@bp.errorhandler(Exception)
def handle_error(error):
    """Handler de erros para o blueprint"""
    logging.error(f"Erro no blueprint de relatórios: {str(error)}")
    return jsonify({"error": "Erro interno do servidor"}), 500
