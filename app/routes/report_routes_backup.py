# -*- coding: utf-8 -*-
"""
Rotas especializadas para relatórios de avaliações
Endpoint para geração de relatórios completos com estatísticas detalhadas
"""

from flask import Blueprint, request, jsonify, render_template_string, send_file
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
from app.services.evaluation_result_service import EvaluationResultService

# Reportlab para geração de PDF

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
    Gera relatório PDF de uma avaliação usando reportlab
    
    Args:
        evaluation_id: ID da avaliação
    
    Returns:
        Arquivo PDF do relatório para download
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
        
        # Gerar relatório PDF usando reportlab
        try:
            pdf_content = _gerar_pdf_com_reportlab(
                test, total_alunos, niveis_aprendizagem, 
                proficiencia, nota_geral, acertos_habilidade, ai_analysis, avaliacao_data
            )
            
            # Preparar nome do arquivo com o nome da avaliação
            nome_avaliacao = test.title.replace(' ', '_').replace('/', '_').replace('\\', '_').replace(':', '_').replace('?', '_').replace('*', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
            nome_arquivo = f"relatorio_{nome_avaliacao}.pdf"
            
            # Retornar arquivo PDF
            from flask import Response
            response = Response(pdf_content, mimetype='application/pdf')
            response.headers['Content-Disposition'] = f'attachment; filename={nome_arquivo}'
            
            return response
            
        except Exception as pdf_error:
            logging.error(f"Erro ao gerar PDF: {str(pdf_error)}")
            
            # Fallback: retornar erro se PDF falhar
            return jsonify({"error": "Erro ao gerar relatório PDF", "details": str(pdf_error)}), 500
        
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


def _gerar_pdf_com_reportlab(test: Test, total_alunos: Dict, niveis_aprendizagem: Dict, 
                             proficiencia: Dict, nota_geral: Dict, acertos_habilidade: Dict, 
                             ai_analysis: Dict, avaliacao_data: Dict) -> bytes:
    """Gera arquivo PDF usando reportlab"""
    
    try:
        # Criar buffer para o PDF
        buffer = BytesIO()
        
        # Criar documento PDF
        doc = BaseDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=30*mm,
            bottomMargin=20*mm
        )
        
        # Obter informações da escola e município
        escola_nome = "Escola não identificada"
        municipio_nome = "Município não identificado"
        uf = "AL"
        
        try:
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
        
        # Determinar período atual
        from datetime import datetime
        now = datetime.now()
        mes_atual = now.strftime("%B").upper()
        ano_atual = now.year
        
        # Preparar elementos do PDF
        elements = []
        
        # Título principal
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=BLUE_900,
            alignment=TA_CENTER,
            spaceAfter=20
        )
        
        elements.append(Paragraph("RELATÓRIO DE AVALIAÇÃO EDUCACIONAL", title_style))
        elements.append(Spacer(1, 12))
        
        # Informações básicas
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=6
        )
        
        elements.append(Paragraph(f"<b>Escola:</b> {escola_nome}", info_style))
        elements.append(Paragraph(f"<b>Município:</b> {municipio_nome} - {uf}", info_style))
        elements.append(Paragraph(f"<b>Avaliação:</b> {test.title}", info_style))
        elements.append(Paragraph(f"<b>Período:</b> {ano_atual}.1", info_style))
        elements.append(Spacer(1, 20))
        
        # Tabela de Participação
        elements.append(Paragraph("<b>PARTICIPAÇÃO POR TURMA</b>", title_style))
        elements.append(Spacer(1, 10))
        
        participacao_data = _preparar_dados_participacao(total_alunos)
        if participacao_data.get("participacao_por_turma"):
            headers = ["SÉRIE/TURNO", "MATRICULADOS", "AVALIADOS", "PERCENTUAL", "FALTOSOS"]
            data = []
            
            for p in participacao_data["participacao_por_turma"]:
                data.append([
                    p.get("turma", ""),
                    str(p.get("matriculados", 0)),
                    str(p.get("avaliados", 0)),
                    f"{p.get('percentual', 0)}%",
                    str(p.get("faltosos", 0))
                ])
            
            # Adicionar linha total
            data.append([
                "TOTAL GERAL",
                str(participacao_data.get("total_matriculados", 0)),
                str(participacao_data.get("total_avaliados", 0)),
                f"{participacao_data.get('percentual_avaliados', 0)}%",
                str(participacao_data.get("total_faltosos", 0))
            ])
            
            participacao_table = Table([headers] + data, colWidths=[80, 60, 60, 60, 60])
            participacao_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BLUE_900),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, -1), (-1, -1), GRAY_200),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            
            elements.append(participacao_table)
            elements.append(Spacer(1, 20))
        
        # Níveis de Aprendizagem
        elements.append(Paragraph("<b>NÍVEIS DE APRENDIZAGEM POR TURMA</b>", title_style))
        elements.append(Spacer(1, 10))
        
        # Adicionar tabelas de níveis por disciplina
        for disciplina, dados in niveis_aprendizagem.items():
            if disciplina != 'GERAL' and dados.get('por_turma'):
                elements.append(Paragraph(f"<b>{disciplina.upper()}</b>", styles['Heading2']))
                
                headers = ["TURMA", "ABAIXO DO BÁSICO", "BÁSICO", "ADEQUADO", "AVANÇADO", "TOTAL"]
                data = []
                
                for turma_data in dados['por_turma']:
                    data.append([
                        turma_data.get("turma", ""),
                        str(turma_data.get("abaixo_do_basico", 0)),
                        str(turma_data.get("basico", 0)),
                        str(turma_data.get("adequado", 0)),
                        str(turma_data.get("avancado", 0)),
                        str(turma_data.get("total", 0))
                    ])
                
                niveis_table = Table([headers] + data, colWidths=[80, 60, 60, 60, 60, 60])
                niveis_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), BLUE_900),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                
                elements.append(niveis_table)
                elements.append(Spacer(1, 15))
        
        # Tabela GERAL de níveis
        if 'GERAL' in niveis_aprendizagem and niveis_aprendizagem['GERAL'].get('por_turma'):
            elements.append(Paragraph("<b>GERAL</b>", styles['Heading2']))
            
            headers = ["TURMA", "ABAIXO DO BÁSICO", "BÁSICO", "ADEQUADO", "AVANÇADO", "TOTAL"]
            data = []
            
            for turma_data in niveis_aprendizagem['GERAL']['por_turma']:
                data.append([
                    turma_data.get("turma", ""),
                    str(turma_data.get("abaixo_do_basico", 0)),
                    str(turma_data.get("basico", 0)),
                    str(turma_data.get("adequado", 0)),
                    str(turma_data.get("avancado", 0)),
                    str(turma_data.get("total", 0))
                ])
            
            geral_table = Table([headers] + data, colWidths=[80, 60, 60, 60, 60, 60])
            geral_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BLUE_900),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(geral_table)
            elements.append(Spacer(1, 20))
        
        # Proficiência
        elements.append(Paragraph("<b>PROFICIÊNCIA POR TURMA</b>", title_style))
        elements.append(Spacer(1, 10))
        
        if 'GERAL' in proficiencia.get('por_disciplina', {}) and proficiencia['por_disciplina']['GERAL'].get('por_turma'):
            headers = ["TURMA", "PROFICIÊNCIA"]
            data = []
            
            for turma_data in proficiencia['por_disciplina']['GERAL']['por_turma']:
                data.append([
                    turma_data.get("turma", ""),
                    f"{turma_data.get('proficiencia', 0):.2f}"
                ])
            
            proficiencia_table = Table([headers] + data, colWidths=[120, 80])
            proficiencia_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BLUE_900),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(proficiencia_table)
            elements.append(Spacer(1, 20))
        
        # Análise da IA
        if ai_analysis:
            elements.append(Paragraph("<b>ANÁLISE E RECOMENDAÇÕES</b>", title_style))
            elements.append(Spacer(1, 10))
            
            analise_text = ai_analysis.get('analysis', 'Análise não disponível.')
            elements.append(Paragraph(analise_text, styles['Normal']))
            elements.append(Spacer(1, 20))
        
        # Construir PDF
        doc.build(elements)
        
        # Obter conteúdo do buffer
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return pdf_content
        
    except Exception as e:
        logging.error(f"Erro ao gerar PDF: {str(e)}")
        raise


def _preparar_dados_participacao(total_alunos: Dict) -> Dict[str, Any]:
    """Prepara dados de participação para o template"""
    try:
        total_geral = total_alunos.get('total_geral', {})
        
        return {
            'total_matriculados': total_geral.get('matriculados', 0),
            'total_avaliados': total_geral.get('avaliados', 0),
            'total_faltosos': total_geral.get('faltosos', 0),
            'percentual_avaliados': total_geral.get('percentual', 0),
            'participacao_por_turma': total_alunos.get('por_turma', []),
            'total_alunos': total_geral.get('avaliados', 0)
        }
    except Exception as e:
        logging.warning(f"Erro ao preparar dados de participação: {str(e)}")
        return {}


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


def _preparar_dados_niveis(niveis_aprendizagem: Dict) -> Dict[str, Any]:
    """Prepara dados de níveis de aprendizagem para o template"""
    try:
        dados_niveis = {}
        
        for disciplina, dados in niveis_aprendizagem.items():
            if disciplina != 'GERAL':
                dados_niveis[f'niveis_{disciplina.lower().replace(" ", "_")}'] = dados.get('por_turma', [])
        
        # Dados gerais
        dados_niveis['niveis_geral'] = niveis_aprendizagem.get('GERAL', {}).get('por_turma', [])
        
        return dados_niveis
        
    except Exception as e:
        logging.warning(f"Erro ao preparar dados de níveis: {str(e)}")
        return {}


@bp.errorhandler(Exception)
def handle_error(error):
    """Handler de erros para o blueprint"""
    logging.error(f"Erro no blueprint de relatórios: {str(error)}")
    return jsonify({"error": "Erro interno do servidor"}), 500
