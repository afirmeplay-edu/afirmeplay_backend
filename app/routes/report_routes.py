# -*- coding: utf-8 -*-
"""
Rotas especializadas para relatórios de avaliações
Endpoint para geração de relatórios completos com estatísticas detalhadas
"""

from flask import Blueprint, request, jsonify, render_template_string, send_file, make_response
from flask_jwt_extended import jwt_required
from app.permissions import role_required, get_current_user_from_token
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
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from app import db
import logging
from typing import Dict, Any, List, Optional, Union
import math
import re
import unicodedata
from sqlalchemy import func, case, desc, cast
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from datetime import datetime
from sqlalchemy.orm import joinedload
from collections import defaultdict, OrderedDict
import os
from jinja2 import Template
from jinja2 import Environment, FileSystemLoader, select_autoescape
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
from app.report_analysis.services import ReportAggregateService
from weasyprint import HTML
from markupsafe import Markup
import base64

# Importar docxtpl para template Word (comentado - usando PDF agora)
# try:
#     from docxtpl import DocxTemplate
#     from docx.shared import Mm, Pt, RGBColor
#     from docx.enum.text import WD_ALIGN_PARAGRAPH
#     from docx.oxml import parse_xml
#     DOCXTPL_AVAILABLE = True
# except ImportError:
#     DOCXTPL_AVAILABLE = False
#     logging.warning("docxtpl não disponível. Instale com: pip install docxtpl")
DOCXTPL_AVAILABLE = False  # Desabilitado - usando PDF

# Constantes de cores para o PDF
BLUE_900 = colors.HexColor("#0b2a56")
GRAY_150 = colors.HexColor("#ededed")
GRAY_200 = colors.HexColor("#e6e6e6")
GRID = colors.HexColor("#999")
RED = colors.HexColor("#e53935")
YELLOW = colors.HexColor("#f1c232")
ADEQ = colors.HexColor("#6aa84f")
GREEN = colors.HexColor("#00a651")


def _load_default_logo() -> Optional[str]:
    """
    Carrega a logo padrão (afirme_logo.png) e converte para base64
    """
    try:
        # Caminho para a logo padrão
        assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets')
        logo_path = os.path.join(assets_dir, 'afirme_logo.png')
        
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as logo_file:
                logo_data = logo_file.read()
                logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                return logo_base64
        else:
            logging.warning(f"Logo padrão não encontrada em: {logo_path}")
            return None
            
    except Exception as e:
        logging.error(f"Erro ao carregar logo padrão: {str(e)}")
        return None


def _header(canvas: Canvas, doc, logo_esq=None, logo_dir=None):
    """Função para desenhar cabeçalho com logos em todas as páginas"""
    # Por enquanto, não desenhar nada para evitar erros com logos
    pass

bp = Blueprint('reports', __name__, url_prefix='/reports')


# ROTA COMENTADA - Para exclusão manual
# @bp.route('/test', methods=['GET'])
# def test_endpoint():
#     """Endpoint de teste para verificar se o blueprint está funcionando"""
#     return jsonify({
#         "message": "Blueprint de relatórios funcionando corretamente",
#         "status": "success"
#     }), 200


# ROTA COMENTADA - Para exclusão manual
# @bp.route('/test-questions/<string:evaluation_id>', methods=['GET'])
# @jwt_required()
# @role_required("admin", "professor", "coordenador", "diretor","tecadm")
# def test_questions(evaluation_id: str):
#     """Endpoint para testar diretamente a propriedade questions"""
#     try:
#         from app.models.testQuestion import TestQuestion
#         from app.models.question import Question
#         
#         # Teste 1: Query direta na tabela test_questions
#         test_questions_direct = TestQuestion.query.filter_by(test_id=evaluation_id).order_by(TestQuestion.order).all()
#         
#         # Teste 2: IDs das questões
#         question_ids = [tq.question_id for tq in test_questions_direct]
#         
#         # Teste 3: Buscar questões diretamente
#         questions_direct = Question.query.filter(Question.id.in_(question_ids)).all()
#         
#         # Teste 4: Usar a propriedade questions do modelo Test
#         test = Test.query.get(evaluation_id)
#         questions_property = test.questions if test else []
#         
#         # Teste 5: Verificar se a questão de Português está na tabela
#         portugues_question = TestQuestion.query.filter_by(
#             test_id=evaluation_id,
#             question_id="4e3305a0-7221-4012-a7aa-8f958b755823"
#         ).first()
#         
#         debug_info = {
#             "avaliacao_id": evaluation_id,
#             "test_questions_direct": {
#                 "total": len(test_questions_direct),
#                 "registros": [
#                     {
#                         "id": tq.id,
#                         "test_id": tq.test_id,
#                         "question_id": tq.question_id,
#                         "order": tq.order
#                     } for tq in test_questions_direct
#                 ]
#             },
#             "question_ids": question_ids,
#             "questions_direct": {
#                 "total": len(questions_direct),
#                 "questoes": [
#                     {
#                         "id": q.id,
#                         "skill": q.skill,
#                         "number": q.number
#                     } for q in questions_direct
#                 ]
#             },
#             "questions_property": {
#                 "total": len(questions_property),
#                 "questoes": [
#                     {
#                         "id": q.id,
#                         "skill": q.skill,
#                         "number": q.number
#                     } for q in questions_property
#                 ]
#             },
#             "questao_portugues_teste": {
#                 "encontrada": portugues_question is not None,
#                 "dados": {
#                     "id": portugues_question.id,
#                     "test_id": portugues_question.test_id,
#                     "question_id": portugues_question.question_id,
#                     "order": portugues_question.order
#                 } if portugues_question else None
#             }
#         }
#         
#         return jsonify(debug_info), 200
#         
#     except Exception as e:
#         logging.error(f"Erro ao testar questions: {str(e)}")
#         return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


# ROTA COMENTADA - Para exclusão manual
# @bp.route('/debug-disciplinas/<string:evaluation_id>', methods=['GET'])
# @jwt_required()
# @role_required("admin", "professor", "coordenador", "diretor","tecadm")
# def debug_disciplinas(evaluation_id: str):
#     """Endpoint para debug da identificação de disciplinas"""
#     try:
#         # Verificar se a avaliação existe
#         test = Test.query.get(evaluation_id)
#         if not test:
#             return jsonify({"error": "Avaliação não encontrada"}), 404
#         
#         # Obter disciplinas usando a função melhorada
#         disciplinas = _obter_disciplinas_avaliacao(test)
#         
#         # Debug detalhado
#         debug_info = {
#             "avaliacao_id": evaluation_id,
#             "titulo": test.title,
#             "disciplinas_identificadas": disciplinas,
#             "debug_details": {
#                 "subject_rel": test.subject_rel.name if test.subject_rel else None,
#                 "subjects_info": test.subjects_info,
#                 "total_questoes": len(test.questions) if test.questions else 0,
#                 "questoes_com_habilidades": 0,
#                 "habilidades_unicas": set(),
#                 "disciplinas_por_habilidade": {}
#             },
#             "mapeamento_questoes": {},
#             "respostas_por_questao": {},
#             "questao_portugues_debug": {}
#         }
#         
#         if test.questions:
#             from app.models.skill import Skill
#             
#             skill_ids = set()
#             for question in test.questions:
#                 if question.skill and question.skill.strip() and question.skill != '{}':
#                     clean_skill_id = question.skill.replace('{', '').replace('}', '')
#                     skill_ids.add(clean_skill_id)
#                     debug_info["debug_details"]["questoes_com_habilidades"] += 1
#             
#             debug_info["debug_details"]["habilidades_unicas"] = list(skill_ids)
#             
#             if skill_ids:
#                 skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
#                 skills_dict = {str(skill.id): skill for skill in skills}
#                 
#                 for skill in skills:
#                     subject = Subject.query.get(skill.subject_id) if skill.subject_id else None
#                     debug_info["debug_details"]["disciplinas_por_habilidade"][str(skill.id)] = {
#                         "skill_code": skill.code,
#                         "skill_description": skill.description,
#                         "subject_id": skill.subject_id,
#                         "subject_name": subject.name if subject else None
#                     }
#                 
#                 # Mapear questões para disciplinas (mesmo processo das funções de cálculo)
#                 for question in test.questions:
#                     # Questões com skill: mapear via skill.subject_id
#                     if question.skill and question.skill.strip() and question.skill != '{}':
#                         clean_skill_id = question.skill.replace('{', '').replace('}', '')
#                         skill_obj = skills_dict.get(clean_skill_id)
#                         
#                         disciplina_mapeada = "Não mapeada"
#                         if skill_obj and skill_obj.subject_id:
#                             subject = Subject.query.get(skill_obj.subject_id)
#                             if subject:
#                                 disciplina_mapeada = subject.name
#                             else:
#                                 disciplina_mapeada = "Disciplina Geral (subject não encontrado)"
#                         else:
#                             disciplina_mapeada = "Disciplina Geral (skill sem subject_id)"
#                         
#                         debug_info["mapeamento_questoes"][question.id] = {
#                             "numero": question.number,
#                             "skill_id": clean_skill_id,
#                             "skill_encontrada": skill_obj is not None,
#                             "disciplina_mapeada": disciplina_mapeada
#                         }
#                     else:
#                         # Questões sem skill: mapear para disciplina principal da avaliação
#                         if test.subject_rel:
#                             disciplina_mapeada = test.subject_rel.name
#                             debug_info["mapeamento_questoes"][question.id] = {
#                                 "numero": question.number,
#                                 "skill_id": "Sem skill",
#                                 "skill_encontrada": False,
#                                 "disciplina_mapeada": disciplina_mapeada
#                             }
#                         else:
#                             disciplina_mapeada = "Disciplina Geral"
#                             debug_info["mapeamento_questoes"][question.id] = {
#                                 "numero": question.number,
#                                 "skill_id": "Sem skill",
#                                 "skill_encontrada": False,
#                                 "disciplina_mapeada": disciplina_mapeada
#                             }
#                     
#                     # Verificar respostas para esta questão
#                     respostas = StudentAnswer.query.filter_by(
#                         test_id=evaluation_id, 
#                         question_id=question.id
#                     ).count()
#                     
#                     debug_info["respostas_por_questao"][question.id] = respostas
#                     
#                     # Debug específico para a questão de Português que sabemos que existe
#                     if question.id == "4e3305a0-7221-4012-a7aa-8f958b755823":
#                         if question.skill and question.skill.strip() and question.skill != '{}':
#                             clean_skill_id = question.skill.replace('{', '').replace('}', '')
#                             skill_obj = skills_dict.get(clean_skill_id)
#                             debug_info["questao_portugues_debug"] = {
#                                 "questao_id": question.id,
#                                 "numero": question.number,
#                                 "skill_raw": question.skill,
#                                 "skill_clean": clean_skill_id,
#                                 "skill_encontrada": skill_obj is not None,
#                                 "skill_code": skill_obj.code if skill_obj else None,
#                                 "skill_subject_id": skill_obj.subject_id if skill_obj else None,
#                                 "disciplina_final": disciplina_mapeada,
#                                 "total_respostas": respostas
#                             }
#                         else:
#                             debug_info["questao_portugues_debug"] = {
#                                 "questao_id": question.id,
#                                 "numero": question.number,
#                                 "skill_raw": question.skill,
#                                 "skill_clean": "Sem skill",
#                                 "skill_encontrada": False,
#                                 "skill_code": None,
#                                 "skill_subject_id": None,
#                                 "disciplina_final": disciplina_mapeada,
#                                 "total_respostas": respostas
#                             }
#         
#         return jsonify(debug_info), 200
#         
#     except Exception as e:
#         logging.error(f"Erro ao debug disciplinas: {str(e)}")
#         return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


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
        
        # Determinar escopo a partir dos parâmetros de query
        school_id = request.args.get('school_id')
        city_id = request.args.get('city_id')
        scope_type, scope_id = _determinar_escopo_relatorio(school_id, city_id)

        # Buscar turmas conforme o escopo selecionado
        class_tests = _buscar_turmas_por_escopo(evaluation_id, scope_type, scope_id)
        if not class_tests:
            if scope_type == 'school':
                return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma da escola especificada"}), 404
            elif scope_type == 'city':
                return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma do município especificado"}), 404
            else:
                return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
        
        # Obter dados da avaliação
        course_name = _obter_nome_curso(test)
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "descricao": test.description,
            "disciplinas": _obter_disciplinas_avaliacao(test),
            "course_name": course_name
        }
        
        logging.info(f"Disciplinas identificadas para avaliação {evaluation_id}: {avaliacao_data['disciplinas']}")
        
        # 1. Total de alunos que realizaram a avaliação
        total_alunos = _calcular_totais_alunos_por_escopo(evaluation_id, class_tests, scope_type)
        
        # 2. Níveis de Aprendizagem por escopo
        niveis_aprendizagem = _calcular_niveis_aprendizagem_por_escopo(evaluation_id, class_tests, scope_type)
        logging.info(f"Níveis de aprendizagem calculados para disciplinas: {list(niveis_aprendizagem.keys())}")
        
        # 3. Proficiência
        proficiencia = _calcular_proficiencia_por_escopo(evaluation_id, class_tests, scope_type)
        logging.info(f"Proficiência calculada para disciplinas: {list(proficiencia.get('por_disciplina', {}).keys())}")
        
        # 4. Nota Geral
        nota_geral = _calcular_nota_geral_por_escopo(evaluation_id, class_tests, scope_type)
        logging.info(f"Nota geral calculada para disciplinas: {list(nota_geral.get('por_disciplina', {}).keys())}")
        
        # 5. Acertos por habilidade
        acertos_habilidade = _calcular_acertos_habilidade_por_escopo(evaluation_id, class_tests, scope_type)
        logging.info(f"Acertos por habilidade calculados para disciplinas: {list(acertos_habilidade.keys())}")
        
        return jsonify({
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade,
            "escopo": {
                "tipo": scope_type,
                "id": scope_id,
                "school_id": school_id,
                "city_id": city_id
            }
        }), 200
        
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        logging.error(f"Erro ao gerar relatório completo: {str(e)}\n{traceback_str}")
        return jsonify({"error": "Erro interno do servidor"}), 500


# ROTA COMENTADA - Para exclusão manual
# @bp.route('/relatorio-com-ia/<string:evaluation_id>', methods=['GET'])
# @jwt_required()
# @role_required("admin", "professor", "coordenador", "diretor","tecadm")
# def relatorio_com_ia(evaluation_id: str):
#     """
#     Gera relatório completo com análise da IA
#     
#     Args:
#         evaluation_id: ID da avaliação
#     
#     Returns:
#         JSON com relatório completo + análise da IA
#     """
#     try:
#         # Verificar se a avaliação existe
#         test = Test.query.get(evaluation_id)
#         if not test:
#             return jsonify({"error": "Avaliação não encontrada"}), 404
#         
#         # Buscar turmas onde a avaliação foi aplicada
#         # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
#         if not class_tests:
#             return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
#         
#         # Obter dados da avaliação
#         avaliacao_data = {
#             "id": test.id,
#             "titulo": test.title,
#             "descricao": test.description,
#             "disciplinas": _obter_disciplinas_avaliacao(test),
#             "questoes_anuladas": []  # Lista de questões anuladas se houver
#         }
#         
#         logging.info(f"Disciplinas identificadas para avaliação {evaluation_id}: {avaliacao_data['disciplinas']}")
#         
#         # 1. Total de alunos que realizaram a avaliação
#         total_alunos = _calcular_totais_alunos(evaluation_id, class_tests)
#         
#         # 2. Níveis de Aprendizagem por turma
#         niveis_aprendizagem = _calcular_niveis_aprendizagem(evaluation_id, class_tests)
#         
#         # 3. Proficiência
#         proficiencia = _calcular_proficiencia(evaluation_id, class_tests)
#         
#         # 4. Nota Geral por turma
#         nota_geral = _calcular_nota_geral(evaluation_id, class_tests)
#         
#         # 5. Acertos por habilidade
#         acertos_habilidade = _calcular_acertos_habilidade(evaluation_id)
#         
#         # Preparar dados completos para análise da IA
#         report_data = {
#             "avaliacao": avaliacao_data,
#             "total_alunos": total_alunos,
#             "niveis_aprendizagem": niveis_aprendizagem,
#             "proficiencia": proficiencia,
#             "nota_geral": nota_geral,
#             "acertos_por_habilidade": acertos_habilidade
#         }
#         
#         # 6. Análise da IA
#         ai_service = AIAnalysisService()
#         ai_analysis = ai_service.analyze_report_data(report_data)
#         
#         return jsonify({
#             "avaliacao": avaliacao_data,
#             "total_alunos": total_alunos,
#             "niveis_aprendizagem": niveis_aprendizagem,
#             "proficiencia": proficiencia,
#             "nota_geral": nota_geral,
#             "acertos_por_habilidade": acertos_habilidade,
#             "analise_ia": ai_analysis
#         }), 200
#         
#     except Exception as e:
#         logging.error(f"Erro ao gerar relatório com IA: {str(e)}")
#         return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/dados-json/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def dados_json(evaluation_id: str):
    """
    Retorna os dados do relatório em JSON formatado para o frontend
    
    Args:
        evaluation_id: ID da avaliação
    
    Query Parameters:
        school_id: ID da escola (opcional) - filtra dados por escola específica
        city_id: ID do município (opcional) - filtra dados por município
        Se nenhum parâmetro for fornecido, retorna dados de todas as turmas da avaliação
    
    Returns:
        JSON com todos os dados do relatório formatados para o frontend:
        - avaliacao: Informações da avaliação
        - metadados: Metadados do relatório (escola, município, UF, período, escopo)
        - total_alunos: Dados de participação
        - niveis_aprendizagem: Níveis de aprendizagem por disciplina
        - proficiencia: Proficiência por disciplina
        - nota_geral: Notas gerais por disciplina
        - acertos_por_habilidade: Acertos por habilidade
    """
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Obter usuário atual
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401
        
        # Obter parâmetros de filtro (usados apenas para admin)
        school_id_raw = request.args.get('school_id')
        city_id = request.args.get('city_id')
        
        # Determinar escopo baseado no role do usuário
        try:
            scope_type, scope_ref_id = _determinar_escopo_por_role(user, school_id_raw, city_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
        # Para professores, verificar permissões
        if scope_type == 'teacher':
            from app.permissions.utils import get_teacher_classes
            from app.permissions.rules import can_view_test
            
            # Professor pode ver se CRIOU OU se foi aplicada nas turmas dele
            if not can_view_test(user, evaluation_id):
                return jsonify({"error": "Acesso negado: você não tem permissão para ver esta avaliação"}), 403
            
            # Verificar se foi aplicada nas turmas do professor
            teacher_class_ids = get_teacher_classes(user.get('id'))
            if not teacher_class_ids:
                return jsonify({"error": "Professor não vinculado a nenhuma turma"}), 404
            
            # Buscar class_tests APENAS das turmas do professor
            class_tests = ClassTest.query.filter(
                ClassTest.test_id == evaluation_id,
                ClassTest.class_id.in_(teacher_class_ids)
            ).all()
            
            if not class_tests:
                return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma do professor"}), 404
        
        # REFATORADO: Verificar status e usar lógica assíncrona
        status = ReportAggregateService.get_status(evaluation_id, scope_type, scope_ref_id)
        
        if status['status'] != 'ready':
            # Disparar task assíncrona (com debounce)
            from app.report_analysis.tasks import trigger_rebuild_if_needed
            try:
                trigger_rebuild_if_needed.delay(evaluation_id, scope_type, scope_ref_id)
            except Exception as e:
                logging.warning(f"Erro ao disparar task de rebuild: {str(e)}")
                # Continuar mesmo se falhar (pode ser que Redis não esteja disponível)
            
            return jsonify({
                "status": "processing",
                "message": "Relatório sendo processado em background",
                "has_payload": status['has_payload'],
                "has_ai_analysis": status['has_ai_analysis'],
                "is_dirty": status['is_dirty'],
                "ai_analysis_is_dirty": status['ai_analysis_is_dirty'],
                "last_update": status['last_update'].isoformat() if status['last_update'] else None,
                "evaluation_id": evaluation_id,
                "scope_type": scope_type,
                "scope_id": scope_ref_id
            }), 202  # HTTP 202 Accepted
        
        # Relatório está pronto - buscar do cache
        aggregate = ReportAggregateService.get(evaluation_id, scope_type, scope_ref_id)
        if not aggregate:
            return jsonify({"error": "Relatório não encontrado"}), 404
        
        resposta = aggregate.payload or {}
        analise_ia = aggregate.ai_analysis or {}
        resposta['analise_ia'] = analise_ia
        
        return jsonify(resposta), 200
        
    except Exception as e:
        logging.error(f"Erro ao gerar dados JSON do relatório: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


def _montar_resposta_relatorio(
    evaluation_id: str,
    school_id: str = None,
    city_id: str = None,
    include_ai: bool = True
) -> dict:
    """
    Monta a resposta completa do relatório a partir do ID da avaliação e filtros opcionais.
    Reutilizada pelos endpoints que retornam JSON e PDF.
    """
    test = Test.query.get(evaluation_id)
    if not test:
        raise ValueError("Avaliação não encontrada")

    scope_type, scope_id = _determinar_escopo_relatorio(school_id, city_id)
    class_tests = _buscar_turmas_por_escopo(evaluation_id, scope_type, scope_id)
    if not class_tests:
        if scope_type == 'school':
            raise LookupError("Avaliação não foi aplicada em nenhuma turma da escola especificada")
        elif scope_type == 'city':
            raise LookupError("Avaliação não foi aplicada em nenhuma turma do município especificado")
        else:
            raise LookupError("Avaliação não foi aplicada em nenhuma turma")

    # Identificar séries/anos das turmas envolvidas
    class_ids = [ct.class_id for ct in class_tests if getattr(ct, "class_id", None)]
    unique_class_ids = list(dict.fromkeys(class_ids))
    series_ordered: List[str] = []
    seen_series = set()
    if unique_class_ids:
        classes = Class.query.options(joinedload(Class.grade)).filter(Class.id.in_(unique_class_ids)).all()
        class_map = {cls.id: cls for cls in classes}
        for class_id in unique_class_ids:
            cls = class_map.get(class_id)
            if not cls:
                continue
            serie_name = None
            if getattr(cls, "grade", None) and getattr(cls.grade, "name", None):
                serie_name = cls.grade.name.strip()
            elif getattr(cls, "name", None):
                serie_name = cls.name.strip()
            if serie_name and serie_name not in seen_series:
                seen_series.add(serie_name)
                series_ordered.append(serie_name)

    total_alunos = _calcular_totais_alunos_por_escopo(evaluation_id, class_tests, scope_type)

    # Fallback: utilizar nomes das turmas da agregação quando não encontrar séries
    if scope_type == 'school' and not series_ordered:
        turmas_info = (total_alunos or {}).get('por_turma', [])
        for turma_data in turmas_info:
            turma_nome = turma_data.get('turma')
            if turma_nome:
                turma_nome = str(turma_nome).strip()
                if turma_nome and turma_nome not in seen_series:
                    seen_series.add(turma_nome)
                    series_ordered.append(turma_nome)

    series_label = ", ".join(series_ordered) if series_ordered else None
    if scope_type == 'school':
        general_label = f"{series_label} - Geral" if series_label else "Geral"
    elif scope_type == 'city':
        general_label = "Municipal Geral"
    else:
        general_label = "Geral"
    niveis_aprendizagem = _calcular_niveis_aprendizagem_por_escopo(evaluation_id, class_tests, scope_type)
    proficiencia = _calcular_proficiencia_por_escopo(evaluation_id, class_tests, scope_type)
    nota_geral = _calcular_nota_geral_por_escopo(evaluation_id, class_tests, scope_type)
    acertos_habilidade = _calcular_acertos_habilidade_por_escopo(evaluation_id, class_tests, scope_type)

    avaliacao_data = {
        "id": str(test.id),
        "titulo": test.title,
        "descricao": getattr(test, 'description', None),
        "course_name": _obter_nome_curso(test),
        "disciplinas": _obter_disciplinas_avaliacao(test),
        "series": series_ordered,
        "series_label": series_label
    }

    from datetime import datetime
    now = datetime.now()
    mes_atual = now.strftime("%B").capitalize()
    ano_atual = now.year
    data_geracao = now.strftime("%d/%m/%Y %H:%M")

    metadados = {
        "scope_type": scope_type,
        "scope_id": scope_id,
        "mes": mes_atual,
        "ano": ano_atual,
        "data_geracao": data_geracao,
        "series": series_ordered,
        "series_label": series_label,
        "general_label": general_label
    }

    try:
        if scope_type == 'school' and scope_id:
            school = School.query.get(scope_id)
            if school:
                metadados.update({
                    "escola": school.name,
                    "escola_id": str(school.id),
                    "municipio": school.city.name if school.city else None,
                    "municipio_id": str(school.city.id) if school.city else None,
                    "uf": school.city.state if school.city else None
                })
        elif scope_type == 'city' and scope_id:
            city = City.query.get(scope_id)
            if city:
                metadados.update({
                    "municipio": city.name,
                    "municipio_id": str(city.id),
                    "uf": city.state
                })
    except Exception:
        pass

    analise_ia = {}
    if include_ai:
        ai_service = AIAnalysisService()
        analise_ia = ai_service.analyze_report_data({
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade,
            "scope_type": scope_type,
            "scope_id": scope_id
        })

    # Carregar logo padrão
    default_logo = _load_default_logo()
    
    return {
        "acertos_por_habilidade": acertos_habilidade,
        "analise_ia": analise_ia,
        "avaliacao": avaliacao_data,
        "metadados": metadados,
        "niveis_aprendizagem": niveis_aprendizagem,
        "nota_geral": nota_geral,
        "proficiencia": proficiencia,
        "total_alunos": total_alunos,
        "default_logo": default_logo  # Logo padrão para templates
    }


def _montar_resposta_relatorio_por_turmas(
    evaluation_id: str,
    class_tests: List[ClassTest],
    include_ai: bool = True
) -> dict:
    """
    Monta resposta do relatório para um conjunto específico de turmas.
    Usado principalmente para professores que veem apenas suas turmas.
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de ClassTest das turmas específicas
        include_ai: Se deve incluir análise de IA
    
    Returns:
        dict: Dicionário com todos os dados do relatório
    """
    test = Test.query.get(evaluation_id)
    if not test:
        raise ValueError("Avaliação não encontrada")
    
    if not class_tests:
        raise LookupError("Nenhuma turma fornecida")
    
    # Identificar séries/anos das turmas envolvidas
    class_ids = [ct.class_id for ct in class_tests if getattr(ct, "class_id", None)]
    unique_class_ids = list(dict.fromkeys(class_ids))
    series_ordered: List[str] = []
    seen_series = set()
    if unique_class_ids:
        classes = Class.query.options(joinedload(Class.grade)).filter(Class.id.in_(unique_class_ids)).all()
        class_map = {cls.id: cls for cls in classes}
        for class_id in unique_class_ids:
            cls = class_map.get(class_id)
            if not cls:
                continue
            serie_name = None
            if getattr(cls, "grade", None) and getattr(cls.grade, "name", None):
                serie_name = cls.grade.name.strip()
            elif getattr(cls, "name", None):
                serie_name = cls.name.strip()
            if serie_name and serie_name not in seen_series:
                seen_series.add(serie_name)
                series_ordered.append(serie_name)
    
    # Calcular dados usando as turmas específicas
    total_alunos = _calcular_totais_alunos(evaluation_id, class_tests)
    niveis_aprendizagem = _calcular_niveis_aprendizagem(evaluation_id, class_tests)
    proficiencia = _calcular_proficiencia(evaluation_id, class_tests)
    nota_geral = _calcular_nota_geral(evaluation_id, class_tests)
    acertos_habilidade = _calcular_acertos_habilidade(evaluation_id)
    
    series_label = ", ".join(series_ordered) if series_ordered else None
    general_label = f"{series_label} - Geral" if series_label else "Geral"
    
    avaliacao_data = {
        "id": str(test.id),
        "titulo": test.title,
        "descricao": getattr(test, 'description', None),
        "course_name": _obter_nome_curso(test),
        "disciplinas": _obter_disciplinas_avaliacao(test),
        "series": series_ordered,
        "series_label": series_label
    }
    
    from datetime import datetime
    now = datetime.now()
    mes_atual = now.strftime("%B").capitalize()
    ano_atual = now.year
    data_geracao = now.strftime("%d/%m/%Y %H:%M")
    
    # Obter informações da escola (primeira turma)
    metadados = {
        "scope_type": "teacher",
        "scope_id": None,
        "mes": mes_atual,
        "ano": ano_atual,
        "data_geracao": data_geracao,
        "series": series_ordered,
        "series_label": series_label,
        "general_label": general_label
    }
    
    # Tentar obter informações da escola e município da primeira turma
    try:
        if unique_class_ids:
            # unique_class_ids já são UUIDs (vêm de ClassTest.class_id que é UUID)
            first_class = Class.query.get(unique_class_ids[0])
            if first_class and first_class.school_id:
                # first_class.school_id já é UUID
                school = School.query.get(first_class.school_id)
                if school:
                    metadados.update({
                        "escola": school.name,
                        "escola_id": str(school.id),
                        "municipio": school.city.name if school.city else None,
                        "municipio_id": str(school.city.id) if school.city else None,
                        "uf": school.city.state if school.city else None
                    })
    except Exception:
        pass
    
    analise_ia = {}
    if include_ai:
        ai_service = AIAnalysisService()
        analise_ia = ai_service.analyze_report_data({
            "avaliacao": avaliacao_data,
            "total_alunos": total_alunos,
            "niveis_aprendizagem": niveis_aprendizagem,
            "proficiencia": proficiencia,
            "nota_geral": nota_geral,
            "acertos_por_habilidade": acertos_habilidade,
            "scope_type": "teacher",
            "scope_id": None
        })
    
    # Carregar logo padrão
    default_logo = _load_default_logo()
    
    return {
        "acertos_por_habilidade": acertos_habilidade,
        "analise_ia": analise_ia,
        "avaliacao": avaliacao_data,
        "metadados": metadados,
        "niveis_aprendizagem": niveis_aprendizagem,
        "nota_geral": nota_geral,
        "proficiencia": proficiencia,
        "total_alunos": total_alunos,
        "default_logo": default_logo  # Logo padrão para templates
    }


@bp.route('/relatorio-pdf/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor","tecadm")
def relatorio_pdf(evaluation_id: str):
    """
    Gera relatório PDF de uma avaliação usando reportlab
    
    Args:
        evaluation_id: ID da avaliação
    
    Query Parameters:
        school_id: ID da escola (opcional) - gera relatório por escola específica
        city_id: ID do município (opcional) - gera relatório por município
        Se nenhum parâmetro for fornecido, gera relatório de todas as turmas da avaliação
    
    Returns:
        Arquivo PDF do relatório para download
    """
    try:
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Obter usuário atual
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401
        
        # Obter parâmetros de filtro (usados apenas para admin)
        school_id_raw = request.args.get('school_id')
        city_id = request.args.get('city_id')
        
        # Determinar escopo baseado no role do usuário
        try:
            scope_type, scope_ref_id = _determinar_escopo_por_role(user, school_id_raw, city_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
        # Para professores, verificar permissões
        if scope_type == 'teacher':
            from app.permissions.utils import get_teacher_classes
            from app.permissions.rules import can_view_test
            
            # Professor pode ver se CRIOU OU se foi aplicada nas turmas dele
            if not can_view_test(user, evaluation_id):
                return jsonify({"error": "Acesso negado: você não tem permissão para ver esta avaliação"}), 403
            
            # Verificar se foi aplicada nas turmas do professor
            teacher_class_ids = get_teacher_classes(user.get('id'))
            if not teacher_class_ids:
                return jsonify({"error": "Professor não vinculado a nenhuma turma"}), 404
            
            # Buscar class_tests APENAS das turmas do professor
            class_tests = ClassTest.query.filter(
                ClassTest.test_id == evaluation_id,
                ClassTest.class_id.in_(teacher_class_ids)
            ).all()
            
            if not class_tests:
                return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma do professor"}), 404
        
        # REFATORADO: Verificar se relatório está pronto antes de gerar PDF
        status = ReportAggregateService.get_status(evaluation_id, scope_type, scope_ref_id)
        
        if status['status'] != 'ready':
            # PDF só pode ser gerado se relatório estiver pronto
            return jsonify({
                "error": "Relatório ainda está sendo processado",
                "status": "processing",
                "message": "Aguarde o processamento concluir antes de gerar o PDF. Tente novamente em alguns instantes.",
                "has_payload": status['has_payload'],
                "has_ai_analysis": status['has_ai_analysis'],
                "last_update": status['last_update'].isoformat() if status['last_update'] else None
            }), 409  # HTTP 409 Conflict
        
        # Buscar dados do cache
        aggregate = ReportAggregateService.get(evaluation_id, scope_type, scope_ref_id)
        if not aggregate:
            return jsonify({"error": "Relatório não encontrado"}), 404
        
        context = aggregate.payload or {}
        analise_ia = aggregate.ai_analysis or {}
        context['analise_ia'] = analise_ia
        
        # Adicionar logo padrão ao contexto (para templates que precisam)
        context['default_logo'] = _load_default_logo()

        templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        env = Environment(loader=FileSystemLoader(templates_dir), autoescape=select_autoescape(['html', 'xml']))

        def sum_values(items, attr='value'):
            try:
                return sum(item.get(attr, 0) if isinstance(item, dict) else getattr(item, attr, 0) for item in items)
            except (TypeError, AttributeError):
                return 0

        def cos_filter(value):
            try:
                return math.cos(float(value))
            except (TypeError, ValueError):
                return 0

        def sin_filter(value):
            try:
                return math.sin(float(value))
            except (TypeError, ValueError):
                return 0

        def formatar_texto_ia(texto):
            """
            Formata texto da IA para HTML preservando quebras de linha e formatação
            Converte quebras de linha duplas em parágrafos e simples em <br/>
            """
            if not texto:
                return Markup("")
            
            # Se não houver quebras de linha duplas, tentar detectar padrões para quebrar
            if '\n\n' not in texto:
                # Detectar padrões de títulos no meio do texto
                texto = texto.replace('Destaques e Recomendações:', '\n\nDestaques e Recomendações:')
                texto = texto.replace('Classificação:', '\n\nClassificação:')
                texto = texto.replace('PARECER TÉCNICO:', '\n\nPARECER TÉCNICO:')
                # Detectar números como títulos (ex: "1. ", "2. ", "3. ")
                texto = re.sub(r'(\d+\.\s)', r'\n\n\1', texto)
                # Detectar títulos em maiúsculas seguidas de dois pontos
                texto = re.sub(r'([A-ZÁÊÔÇ][A-ZÁÊÔÇ\s]{10,}:)', r'\n\n\1', texto)
            
            # Dividir por quebras de linha duplas (parágrafos)
            paragrafos = texto.split('\n\n')
            
            resultado = []
            for paragrafo in paragrafos:
                paragrafo = paragrafo.strip()
                if not paragrafo:
                    continue
                
                # Verificar se é um título (maiúsculas seguidas de dois pontos, ou números como "1. ", "2. ")
                if (len(paragrafo) > 10 and paragrafo.isupper() and paragrafo.endswith(':')) or \
                   (len(paragrafo) > 2 and paragrafo[0].isdigit() and paragrafo[1] == '.' and paragrafo[2] == ' '):
                    # É um título - converter para negrito
                    resultado.append(f'<p style="font-weight: bold; margin-top: 12px; margin-bottom: 8px;">{paragrafo}</p>')
                # Verificar se começa com títulos específicos
                elif paragrafo.startswith('Destaques e Recomendações:') or \
                     paragrafo.startswith('Classificação:') or \
                     paragrafo.startswith('PARECER TÉCNICO:') or \
                     paragrafo.startswith('PARECER TÉCNICO DE PARTICIPAÇÃO:') or \
                     paragrafo.startswith('PARECER TÉCNICO: NOTA IDAV:'):
                    # É um título - converter para negrito
                    resultado.append(f'<p style="font-weight: bold; margin-top: 12px; margin-bottom: 8px;">{paragrafo}</p>')
                # Verificar se contém bullets (•) - converter em lista
                elif '•' in paragrafo:
                    # Dividir por bullets
                    partes = paragrafo.split('•')
                    primeira_parte = partes[0].strip()
                    itens_lista = [item.strip() for item in partes[1:] if item.strip()]
                    
                    if primeira_parte:
                        resultado.append(f'<p>{primeira_parte}</p>')
                    
                    if itens_lista:
                        resultado.append('<ul style="margin-left: 20px; margin-top: 8px; margin-bottom: 8px;">')
                        for item in itens_lista:
                            resultado.append(f'<li style="margin-bottom: 4px;">{item}</li>')
                        resultado.append('</ul>')
                else:
                    # Parágrafo normal - converter quebras de linha simples em <br/>
                    paragrafo_html = paragrafo.replace('\n', '<br/>')
                    resultado.append(f'<p style="margin-top: 8px; margin-bottom: 8px;">{paragrafo_html}</p>')
            
            return Markup(''.join(resultado)) if resultado else Markup("")

        env.filters['sum_values'] = sum_values
        env.filters['cos'] = cos_filter
        env.filters['sin'] = sin_filter
        # formatar_texto_ia está registrado globalmente no Flask app.jinja_env
        # Mas também registramos aqui para garantir compatibilidade com Environment customizado
        env.filters['formatar_texto_ia'] = formatar_texto_ia

        template = env.get_template('report.html')
        html_content = template.render(**context)

        pdf_content = HTML(string=html_content, base_url=templates_dir).write_pdf()

        test = Test.query.get(evaluation_id)
        nome_avaliacao = (test.title if test else 'relatorio')
        nome_avaliacao = nome_avaliacao.replace(' ', '_').replace('/', '_').replace('\\', '_') \
                                       .replace(':', '_').replace('?', '_').replace('*', '_') \
                                       .replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        nome_arquivo = f"relatorio_{nome_avaliacao}.pdf"

        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={nome_arquivo}'
        return response

    except (ValueError, LookupError) as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        logging.error(f"Erro ao gerar relatório PDF: {str(e)}\n{traceback_str}")
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


def _criar_badge_proficiencia(proficiency_level: str, proficiency_label: str) -> Dict[str, str]:
    """
    Cria objeto badge baseado no nível de proficiência
    
    Args:
        proficiency_level: Nível de proficiência (avancado, adequado, basico, abaixo_do_basico)
        proficiency_label: Label do nível (Avançado, Adequado, etc.)
    
    Returns:
        Dict com bg, text e label
    """
    cores = {
        'avancado': {'bg': '#16A34A', 'text': '#FFFFFF'},
        'adequado': {'bg': '#22C55E', 'text': '#FFFFFF'},
        'basico': {'bg': '#F59E0B', 'text': '#FFFFFF'},
        'abaixo_do_basico': {'bg': '#DC2626', 'text': '#FFFFFF'}
    }
    
    cor = cores.get(proficiency_level.lower(), {'bg': '#6B7280', 'text': '#FFFFFF'})
    return {
        'bg': cor['bg'],
        'text': cor['text'],
        'label': proficiency_label
    }


def _transformar_dados_frontend_para_template(dados_frontend: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforma os dados enviados pelo frontend para o formato esperado pelo template
    
    Args:
        dados_frontend: Dados JSON enviados pelo frontend
    
    Returns:
        Dict com dados formatados para o template
    """
    from datetime import datetime
    
    # Extrair dados do frontend
    evaluation = dados_frontend.get('evaluation', {})
    summary = dados_frontend.get('summary', {})
    totals = dados_frontend.get('totals', {})
    classes = dados_frontend.get('classes', [])
    charts = dados_frontend.get('charts', [])
    metadata = dados_frontend.get('metadata', {})
    
    # Buscar dados adicionais do banco
    municipality_name = "Município não informado"
    state_name = "Estado não informado"
    school_name = metadata.get('school_name') or "Escola não informada"
    
    # Buscar município
    if metadata.get('municipality_id'):
        city = City.query.get(metadata['municipality_id'])
        if city:
            municipality_name = city.name
            state_name = city.state or metadata.get('state_id', 'Estado não informado')
    
    # Se não encontrou município, tentar buscar pela escola
    if municipality_name == "Município não informado" and metadata.get('school_id'):
        school = School.query.get(metadata['school_id'])
        if school and school.city:
            municipality_name = school.city.name
            state_name = school.city.state or metadata.get('state_id', 'Estado não informado')
            if not school_name or school_name == "Escola não informada":
                school_name = school.name
    
    # Criar badge para summary
    summary_badge = None
    if summary.get('proficiency_level') and summary.get('proficiency_label'):
        summary_badge = _criar_badge_proficiencia(
            summary['proficiency_level'],
            summary['proficiency_label']
        )
    
    # Transformar classes em class_rows
    class_rows = []
    for class_data in classes:
        badge = None
        if class_data.get('proficiency_level') and class_data.get('proficiency_label'):
            badge = _criar_badge_proficiencia(
                class_data['proficiency_level'],
                class_data['proficiency_label']
            )
        
        class_rows.append({
            'turma': class_data.get('turma', ''),
            'media_lp': class_data.get('media_lp', 0),
            'media_mat': class_data.get('media_mat', 0),
            'media_geral': class_data.get('media_geral', 0),
            'comparecimento': class_data.get('comparecimento', 0),
            'proficiencia_media': class_data.get('proficiencia_media', 0),
            'badge': badge
        })
    
    # Criar total_row a partir do summary
    total_row = {
        'turma': 'Total' if metadata.get('scope') == 'escola' else 'Total Município',
        'media_lp': summary.get('media_lp', 0),
        'media_mat': summary.get('media_mat', 0),
        'media_geral': summary.get('media_geral', 0),
        'comparecimento': summary.get('comparecimento', 0),
        'proficiencia_media': summary.get('proficiencia_media', 0),
        'badge': summary_badge
    }
    
    # Transformar charts: renomear segments para legend
    charts_transformados = []
    for chart in charts:
        charts_transformados.append({
            'title': chart.get('title', ''),
            'total': chart.get('total', 0),
            'legend': chart.get('segments', [])  # Renomear segments para legend
        })
    
    # Gerar data de geração
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    
    # Carregar logo padrão
    default_logo = _load_default_logo()
    
    # Montar dados para o template
    return {
        'generated_at': generated_at,
        'municipality': municipality_name,
        'state': state_name,
        'school_name': school_name,
        'default_logo': default_logo,  # Logo padrão para templates
        'evaluation': {
            'title': evaluation.get('title', 'AVALIAÇÃO')
        },
        'metadata': {
            'scope': metadata.get('scope', 'escola')
        },
        'summary': {
            'media_lp': summary.get('media_lp', 0),
            'media_mat': summary.get('media_mat', 0),
            'media_geral': summary.get('media_geral', 0),
            'proficiencia_media': summary.get('proficiencia_media', 0),
            'badge': summary_badge
        },
        'class_rows': class_rows,
        'total_row': total_row,
        'charts': charts_transformados,
        'totals': {
            'matriculados': totals.get('matriculados', 0),
            'avaliados': totals.get('avaliados', 0),
            'percentual': totals.get('percentual', 0)
        }
    }


@bp.route('/relatorios/relatorio-escolar-pdf', methods=['OPTIONS'])
def relatorio_escolar_pdf_options():
    """
    Trata requisições OPTIONS (CORS preflight) para relatório escolar PDF
    """
    response = make_response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    return response


@bp.route('/relatorios/relatorio-escolar-pdf', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def relatorio_escolar_pdf():
    """
    Gera relatório escolar PDF a partir de dados enviados pelo frontend
    
    Recebe um JSON com os dados do relatório e gera um PDF usando o template relatorio_escolar_pdf.html
    
    Returns:
        Arquivo PDF do relatório para download
    """
    try:
        # Obter dados do frontend
        dados_frontend = request.get_json()
        if not dados_frontend:
            return jsonify({"error": "Dados não fornecidos"}), 400
        
        # Transformar dados para o formato do template
        template_data = _transformar_dados_frontend_para_template(dados_frontend)
        
        # Configurar Jinja2
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        env = Environment(loader=FileSystemLoader(templates_dir), autoescape=select_autoescape(['html', 'xml']))
        
        # Adicionar filtro batch para agrupar charts em pares
        def batch_filter(items, n, fillvalue=None):
            """Agrupa itens em lotes de n elementos"""
            items = list(items)
            for i in range(0, len(items), n):
                batch = items[i:i+n]
                while len(batch) < n:
                    batch.append(fillvalue)
                yield batch
        
        # Adicionar filtro para formatação de números
        def format_float(value, decimals=1):
            """Formata número float com n casas decimais"""
            try:
                return f"{float(value):.{decimals}f}"
            except (TypeError, ValueError):
                return "0.0"
        
        env.filters['batch'] = batch_filter
        env.filters['format_float'] = format_float
        
        # Renderizar template
        template = env.get_template('relatorio_escolar_pdf.html')
        html_content = template.render(**template_data)
        
        # Gerar PDF com WeasyPrint
        pdf_content = HTML(string=html_content, base_url=templates_dir).write_pdf()
        
        # Preparar nome do arquivo
        evaluation_title = template_data.get('evaluation', {}).get('title', 'relatorio')
        nome_avaliacao = evaluation_title.replace(' ', '_').replace('/', '_').replace('\\', '_') \
                                         .replace(':', '_').replace('?', '_').replace('*', '_') \
                                         .replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_')
        nome_arquivo = f"relatorio_escolar_{nome_avaliacao}.pdf"
        
        # Retornar PDF
        response = make_response(pdf_content)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename={nome_arquivo}'
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        import traceback
        traceback_str = traceback.format_exc()
        logging.error(f"Erro ao gerar relatório escolar PDF: {str(e)}\n{traceback_str}")
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
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
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


def _preparar_dados_template_word(test: Test, total_alunos: Dict, niveis_aprendizagem: Dict, 
                               proficiencia: Dict, nota_geral: Dict, acertos_habilidade: Dict, 
                               ai_analysis: Dict, avaliacao_data: Dict) -> Dict[str, Any]:
    """Prepara os dados para o template Word com docxtpl"""
    
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
    
    # Determinar período atual
    from datetime import datetime
    now = datetime.now()
    mes_atual = now.strftime("%B").upper()
    ano_atual = now.year
    periodo = f"{ano_atual}.1"
    
    # Dados básicos do template
    dados_base = {
        'periodo': periodo,
        'municipio': municipio_nome,
        'uf': uf,
        'escola': escola_nome,
        'mes': mes_atual,
        'ano': ano_atual,
        'total_alunos': total_alunos.get('total_geral', {}).get('avaliados', 0),
        'percentual_avaliados': total_alunos.get('total_geral', {}).get('percentual', 0),
        'disciplinas': ', '.join(avaliacao_data.get('disciplinas', ['Disciplina Geral']))
    }
    
    # Dados do sumário
    dados_sumario = {
        'sumario_p1': 'Este relatório apresenta os resultados da avaliação educacional realizada no período de 2024.',
        'sumario_p2': 'A avaliação abrangeu múltiplas disciplinas e habilidades dos estudantes.',
        'sumario_p3': 'Os resultados demonstram o progresso e as áreas de melhoria necessárias.',
        'sumario_p4': 'Recomendações específicas são apresentadas para otimizar o aprendizado.',
        'sumario_p41': 'Os dados apresentados refletem o desempenho real dos estudantes.',
        'sumario_p42': 'Análises detalhadas por disciplina foram realizadas.',
        'sumario_p43': 'Comparações com médias municipais foram incluídas.',
        'sumario_p44': 'Recomendações pedagógicas específicas foram elaboradas.'
    }
    
    # Dados de participação
    dados_participacao = _preparar_dados_participacao(total_alunos)
    
    # Dados de níveis de aprendizagem
    dados_niveis = _preparar_dados_niveis(niveis_aprendizagem)
    
    # Dados de proficiência
    dados_proficiencia = _preparar_dados_proficiencia_word(proficiencia)
    
    # Dados de notas
    dados_notas = _preparar_dados_notas_word(nota_geral)
    
    # Dados de habilidades
    dados_habilidades = _preparar_dados_habilidades_word(acertos_habilidade)
    
    # Dados de análise da IA
    dados_ia = _preparar_dados_ia(ai_analysis, {
        "total_alunos": total_alunos,
        "niveis_aprendizagem": niveis_aprendizagem,
        "proficiencia": proficiencia,
        "nota_geral": nota_geral,
        "acertos_por_habilidade": acertos_habilidade
    })
    
    # Combinar todos os dados
    dados_completos = {
        **dados_base,
        **dados_sumario,
        **dados_participacao,
        **dados_niveis,
        **dados_proficiencia,
        **dados_notas,
        **dados_habilidades,
        **dados_ia
    }
    
    return dados_completos


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


def _preparar_dados_proficiencia_word(proficiencia: Dict) -> Dict[str, Any]:
    """Prepara dados de proficiência para o template Word"""
    try:
        disciplinas = proficiencia.get('por_disciplina', {})
        
        # Lista de disciplinas disponíveis
        proficiencia_disciplinas = []
        for disciplina in disciplinas.keys():
            if disciplina != 'GERAL':
                proficiencia_disciplinas.append(disciplina)
        
        # Dados por série/turma
        proficiencia_series = []
        
        # Verificar se há dados gerais
        if 'GERAL' in disciplinas and 'por_turma' in disciplinas['GERAL']:
            for turma in disciplinas['GERAL']['por_turma']:
                serie_data = {'serie_turno': turma.get('turma', 'Turma')}
                
                # Adicionar proficiência por disciplina
                for disciplina in proficiencia_disciplinas:
                    if disciplina in disciplinas and 'por_turma' in disciplinas[disciplina]:
                        # Buscar proficiência desta turma nesta disciplina
                        for turma_disc in disciplinas[disciplina]['por_turma']:
                            if turma_disc.get('turma') == turma.get('turma'):
                                serie_data[disciplina] = turma_disc.get('proficiencia', 0)
                                break
                        else:
                            serie_data[disciplina] = 0
                    else:
                        serie_data[disciplina] = 0
                
                # Adicionar média municipal
                serie_data['MUNICIPAL'] = proficiencia.get('media_municipal_por_disciplina', {}).get('GERAL', 0)
                proficiencia_series.append(serie_data)
        else:
            # Se não há dados gerais, criar dados básicos
            logging.warning("Dados gerais de proficiência não encontrados")
            proficiencia_series = []
        
        return {
            'proficiencia_disciplinas': proficiencia_disciplinas,
            'proficiencia_series': proficiencia_series
        }
        
    except Exception as e:
        logging.warning(f"Erro ao preparar dados de proficiência: {str(e)}")
        return {
            'proficiencia_disciplinas': [],
            'proficiencia_series': []
        }


def _preparar_dados_notas_word(nota_geral: Dict) -> Dict[str, Any]:
    """Prepara dados de notas para o template Word"""
    try:
        disciplinas = nota_geral.get('por_disciplina', {})
        
        # Lista de disciplinas disponíveis
        notas_disciplinas = []
        for disciplina in disciplinas.keys():
            if disciplina != 'GERAL':
                notas_disciplinas.append(disciplina)
        
        # Dados por série/turma
        notas_series = []
        
        # Verificar se há dados gerais
        if 'GERAL' in disciplinas and 'por_turma' in disciplinas['GERAL']:
            for turma in disciplinas['GERAL']['por_turma']:
                serie_data = {'serie_turno': turma.get('turma', 'Turma')}
                
                # Adicionar nota por disciplina
                for disciplina in notas_disciplinas:
                    if disciplina in disciplinas and 'por_turma' in disciplinas[disciplina]:
                        # Buscar nota desta turma nesta disciplina
                        for turma_disc in disciplinas[disciplina]['por_turma']:
                            if turma_disc.get('turma') == turma.get('turma'):
                                serie_data[disciplina] = turma_disc.get('nota', 0)
                                break
                        else:
                            serie_data[disciplina] = 0
                    else:
                        serie_data[disciplina] = 0
                
                # Adicionar média municipal
                serie_data['MUNICIPAL'] = nota_geral.get('media_municipal_por_disciplina', {}).get('GERAL', 0)
                notas_series.append(serie_data)
        else:
            # Se não há dados gerais, criar dados básicos
            logging.warning("Dados gerais de notas não encontrados")
            notas_series = []
        
        return {
            'notas_disciplinas': notas_disciplinas,
            'notas_series': notas_series
        }
        
    except Exception as e:
        logging.warning(f"Erro ao preparar dados de notas: {str(e)}")
        return {
            'notas_disciplinas': [],
            'notas_series': []
        }


def _preparar_dados_habilidades_word(acertos_habilidade: Dict) -> Dict[str, Any]:
    """Prepara dados de habilidades para o template Word"""
    try:
        dados_habilidades = {}
        
        for disciplina, dados in acertos_habilidade.items():
            if disciplina != 'GERAL':
                dados_habilidades[f'habilidades_{disciplina.lower().replace(" ", "_")}'] = dados.get('habilidades', [])
        
        # Dados gerais
        dados_habilidades['habilidades_geral'] = acertos_habilidade.get('GERAL', {}).get('habilidades', [])
        
        return dados_habilidades
        
    except Exception as e:
        logging.warning(f"Erro ao preparar dados de habilidades: {str(e)}")
        return {}


def _determinar_escopo_relatorio(school_id: str, city_id: str) -> tuple:
    """
    Determina o tipo de escopo do relatório baseado nos parâmetros fornecidos
    
    Args:
        school_id: ID da escola (opcional)
        city_id: ID do município (opcional)
    
    Returns:
        tuple: (scope_type, scope_id) onde:
            - scope_type: 'school', 'city', ou 'all'
            - scope_id: ID do escopo ou None
    """
    if school_id:
        return ('school', school_id)
    elif city_id:
        return ('city', city_id)
    else:
        return ('all', None)


def _determinar_escopo_por_role(user: dict, school_id: str = None, city_id: str = None) -> tuple:
    """
    Determina o escopo do relatório baseado no role do usuário.
    
    Args:
        user: Dicionário com informações do usuário (id, role, city_id, etc)
        school_id: ID da escola (opcional, usado apenas para admin)
        city_id: ID do município (opcional, usado apenas para admin)
    
    Returns:
        tuple: (scope_type, scope_id) onde:
            - scope_type: 'overall', 'city', 'school' ou 'teacher'
            - scope_id: ID do escopo ou None
    
    Raises:
        ValueError: Se o role não tem acesso ou não está configurado corretamente
    """
    from app.permissions.utils import get_manager_school, get_teacher
    
    role = user.get('role', '').lower()
    
    if role == 'admin':
        # Admin pode escolher qualquer escopo
        return _determinar_escopo_relatorio(school_id, city_id)
    
    elif role == 'tecadm':
        # Tecadm vê apenas seu município
        city_id_user = user.get('city_id') or user.get('tenant_id')
        if not city_id_user:
            raise ValueError("Tecadm não vinculado a um município")
        return ('city', city_id_user)
    
    elif role in ['diretor', 'coordenador']:
        # Diretor/Coordenador vê apenas sua escola
        manager_school_id = get_manager_school(user.get('id'))
        if not manager_school_id:
            raise ValueError("Diretor/Coordenador não vinculado a uma escola")
        return ('school', manager_school_id)
    
    elif role == 'professor':
        # Professor vê apenas suas turmas
        teacher = get_teacher(user.get('id'))
        if not teacher:
            raise ValueError("Professor não encontrado")
        return ('teacher', teacher.id)
    
    else:
        raise ValueError(f"Role '{role}' não tem acesso a relatórios")


def _buscar_turmas_por_escopo(evaluation_id: str, scope_type: str, scope_id: str) -> List[ClassTest]:
    """
    Busca turmas baseado no escopo especificado
    
    Args:
        evaluation_id: ID da avaliação
        scope_type: Tipo de escopo ('school', 'city', 'all')
        scope_id: ID do escopo
    
    Returns:
        List[ClassTest]: Lista de turmas filtradas
    """
    # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
    query = ClassTest.query.filter_by(test_id=str(evaluation_id))
    
    if scope_type == 'school':
        # Filtrar por escola específica
        # Converter scope_id para UUID (Class.school_id é UUID)
        school_id_uuid = ensure_uuid(scope_id)
        if school_id_uuid:
            query = query.join(Class).filter(Class.school_id == school_id_uuid)
    elif scope_type == 'city':
        # Filtrar por município (todas as escolas do município)
        query = query.join(Class).join(School, Class.school_id == cast(School.id, PostgresUUID)).filter(School.city_id == scope_id)
    # Se scope_type == 'all', não aplicar filtros adicionais
    
    return query.all()


def _filtrar_payload_por_turmas_professor(payload: Dict[str, Any], teacher_class_ids: List[str]) -> Dict[str, Any]:
    """
    Filtra o payload do relatório para mostrar apenas as turmas do professor.
    
    Args:
        payload: Payload completo do relatório
        teacher_class_ids: Lista de IDs das turmas do professor
        
    Returns:
        Payload filtrado contendo apenas dados das turmas do professor
    """
    if not teacher_class_ids:
        # Se não há turmas, retornar payload vazio
        return {
            "acertos_por_habilidade": {},
            "analise_ia": payload.get("analise_ia", {}),
            "avaliacao": payload.get("avaliacao", {}),
            "metadados": payload.get("metadados", {}),
            "niveis_aprendizagem": {},
            "nota_geral": {},
            "proficiencia": {},
            "total_alunos": {
                "por_turma": [],
                "total_geral": {
                    "matriculados": 0,
                    "avaliados": 0,
                    "percentual": 0,
                    "faltosos": 0
                }
            }
        }
    
    # Mapear IDs de turmas para nomes de turmas
    classes = Class.query.filter(Class.id.in_(teacher_class_ids)).all()
    teacher_class_names = {cls.name for cls in classes}
    
    # Criar payload filtrado
    filtered_payload = {
        "acertos_por_habilidade": payload.get("acertos_por_habilidade", {}),
        "analise_ia": payload.get("analise_ia", {}),
        "avaliacao": payload.get("avaliacao", {}),
        "metadados": payload.get("metadados", {}),
        "niveis_aprendizagem": {},
        "nota_geral": {},
        "proficiencia": {},
        "total_alunos": {
            "por_turma": [],
            "total_geral": {
                "matriculados": 0,
                "avaliados": 0,
                "percentual": 0,
                "faltosos": 0
            }
        }
    }
    
    # Filtrar total_alunos
    total_alunos = payload.get("total_alunos", {})
    por_turma = total_alunos.get("por_turma", [])
    filtered_por_turma = [
        turma for turma in por_turma 
        if turma.get("turma") in teacher_class_names
    ]
    
    # Recalcular totais gerais
    total_matriculados = sum(t.get("matriculados", 0) for t in filtered_por_turma)
    total_avaliados = sum(t.get("avaliados", 0) for t in filtered_por_turma)
    total_faltosos = total_matriculados - total_avaliados
    total_percentual = (total_avaliados / total_matriculados * 100) if total_matriculados > 0 else 0
    
    filtered_payload["total_alunos"]["por_turma"] = filtered_por_turma
    filtered_payload["total_alunos"]["total_geral"] = {
        "matriculados": total_matriculados,
        "avaliados": total_avaliados,
        "percentual": round(total_percentual, 1),
        "faltosos": total_faltosos
    }
    
    # Filtrar niveis_aprendizagem
    niveis_aprendizagem = payload.get("niveis_aprendizagem", {})
    for disciplina, dados in niveis_aprendizagem.items():
        por_turma_niveis = dados.get("por_turma", [])
        filtered_por_turma_niveis = [
            turma for turma in por_turma_niveis
            if turma.get("turma") in teacher_class_names
        ]
        
        # Recalcular geral
        geral = dados.get("geral", {})
        total_geral = sum(t.get("total", 0) for t in filtered_por_turma_niveis)
        abaixo_basico = sum(t.get("abaixo_do_basico", 0) for t in filtered_por_turma_niveis)
        basico = sum(t.get("basico", 0) for t in filtered_por_turma_niveis)
        adequado = sum(t.get("adequado", 0) for t in filtered_por_turma_niveis)
        avancado = sum(t.get("avancado", 0) for t in filtered_por_turma_niveis)
        
        filtered_payload["niveis_aprendizagem"][disciplina] = {
            "por_turma": filtered_por_turma_niveis,
            "geral": {
                "abaixo_do_basico": abaixo_basico,
                "basico": basico,
                "adequado": adequado,
                "avancado": avancado,
                "total": total_geral
            }
        }
    
    # Filtrar proficiencia
    proficiencia = payload.get("proficiencia", {})
    por_disciplina_prof = proficiencia.get("por_disciplina", {})
    filtered_por_disciplina_prof = {}
    
    for disciplina, dados in por_disciplina_prof.items():
        por_turma_prof = dados.get("por_turma", [])
        filtered_por_turma_prof = [
            turma for turma in por_turma_prof
            if turma.get("turma") in teacher_class_names
        ]
        
        # Recalcular média geral
        if filtered_por_turma_prof:
            media_geral = sum(t.get("proficiencia", t.get("media", 0)) for t in filtered_por_turma_prof) / len(filtered_por_turma_prof)
        else:
            media_geral = 0
        
        filtered_por_disciplina_prof[disciplina] = {
            "por_turma": filtered_por_turma_prof,
            "media_geral": round(media_geral, 2)
        }
    
    filtered_payload["proficiencia"] = {
        "por_disciplina": filtered_por_disciplina_prof,
        "media_municipal_por_disciplina": proficiencia.get("media_municipal_por_disciplina", {})
    }
    
    # Filtrar nota_geral
    nota_geral = payload.get("nota_geral", {})
    por_disciplina_nota = nota_geral.get("por_disciplina", {})
    filtered_por_disciplina_nota = {}
    
    for disciplina, dados in por_disciplina_nota.items():
        por_turma_nota = dados.get("por_turma", [])
        filtered_por_turma_nota = [
            turma for turma in por_turma_nota
            if turma.get("turma") in teacher_class_names
        ]
        
        # Recalcular média geral
        if filtered_por_turma_nota:
            media_geral = sum(t.get("nota", t.get("media", 0)) for t in filtered_por_turma_nota) / len(filtered_por_turma_nota)
        else:
            media_geral = 0
        
        filtered_por_disciplina_nota[disciplina] = {
            "por_turma": filtered_por_turma_nota,
            "media_geral": round(media_geral, 2)
        }
    
    filtered_payload["nota_geral"] = {
        "por_disciplina": filtered_por_disciplina_nota,
        "media_municipal_por_disciplina": nota_geral.get("media_municipal_por_disciplina", {})
    }
    
    return filtered_payload


def _preparar_dados_ia(ai_analysis: Dict, template_data: Dict) -> Dict[str, Any]:
    """Prepara dados de análise da IA para o template com análises inteligentes baseadas nos dados"""
    try:
        # Gerar análises inteligentes baseadas nos dados das tabelas
        analise_participacao = _gerar_analise_participacao(template_data)
        analise_proficiencia = _gerar_analise_proficiencia(template_data)
        analise_nota_geral = _gerar_analise_notas(template_data)
        analise_acertos_por_habilidade = _gerar_analise_habilidades(template_data)
        
        # Análise geral combinada
        analises = []
        if analise_participacao:
            analises.append(f"Participação: {analise_participacao}")
        if analise_proficiencia:
            analises.append(f"Proficiência: {analise_proficiencia}")
        if analise_nota_geral:
            analises.append(f"Notas: {analise_nota_geral}")
        if analise_acertos_por_habilidade:
            analises.append(f"Habilidades: {analise_acertos_por_habilidade}")
        
        analise_completa = ' '.join(analises) if analises else 'Análise não disponível.'
        
        return {
            'analise_ia': analise_completa,
            'analise_IA_participacao': analise_participacao,
            'analise_IA_proficiencia': analise_proficiencia,
            'analise_IA_nota': analise_nota_geral,
            'analise_IA_acertos': analise_acertos_por_habilidade,
            'consideracoes_finais': 'Com base na análise dos dados, recomenda-se atenção especial às áreas identificadas como críticas e continuidade no desenvolvimento das habilidades que apresentaram melhor desempenho.'
        }
    except Exception as e:
        logging.warning(f"Erro ao preparar dados da IA: {str(e)}")
        return {
            'analise_ia': 'Análise não disponível.',
            'analise_IA_participacao': 'Análise de participação não disponível.',
            'analise_IA_proficiencia': 'Análise de proficiência não disponível.',
            'analise_IA_nota': 'Análise de notas não disponível.',
            'analise_IA_acertos': 'Análise de habilidades não disponível.',
            'consideracoes_finais': 'Relatório gerado automaticamente pelo sistema.'
        }


# Função DOCX comentada - usando PDF agora
# def _gerar_docx_com_template(template_data: Dict[str, Any]) -> bytes:
#     """Gera arquivo DOCX usando o template Word com docxtpl"""
#     
#     try:
#         # Caminho para o template funcionando com formatação profissional
#         template_path = os.path.join(os.path.dirname(__file__), '..', 'templates', 'templateDoc_working.docx')
#         
#         if not os.path.exists(template_path):
#             raise FileNotFoundError(f"Template não encontrado em: {template_path}")
#         
#         # Carregar template
#         doc = DocxTemplate(template_path)
#         
#         # Preparar contexto com dados
#         context = _preparar_contexto_docxtpl(doc, template_data)
#         
#         # Renderizar template
#         doc.render(context)
#         
#         # Salvar em buffer
#         buffer = BytesIO()
#         doc.save(buffer)
#         buffer.seek(0)
#         
#         return buffer.getvalue()
#         
#     except Exception as e:
#         logging.error(f"Erro ao gerar DOCX: {str(e)}")
#         raise

def _gerar_pdf_com_reportlab(test: Test, total_alunos: Dict, niveis_aprendizagem: Dict, 
                             proficiencia: Dict, nota_geral: Dict, acertos_habilidade: Dict, 
                             ai_analysis: Dict, avaliacao_data: Dict) -> bytes:
    """Gera arquivo PDF usando reportlab com layout do template DOCX"""
    
    try:
      
        # Criar buffer para o PDF
        buffer = BytesIO()
        
        # Criar documento PDF com margens do template
        doc = BaseDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=25*mm,
            leftMargin=25*mm,
            topMargin=30*mm,
            bottomMargin=25*mm
        )
        
        # Criar template de página
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        page_template = PageTemplate('normal', [frame], onPage=_header)
        doc.addPageTemplates([page_template])
        
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
        periodo = f"{ano_atual}.1"
        
        # Preparar elementos do PDF
        elements = []
        
        # Preparar dados para o template
        template_data = _preparar_dados_template_word(
            test, total_alunos, niveis_aprendizagem, 
            proficiencia, nota_geral, acertos_habilidade, ai_analysis, avaliacao_data
        )
        
        # Definir cores do template
        COR_PARTICIPACAO = colors.HexColor("#0B2A56")  # Azul escuro
        COR_PROFICIENCIA = colors.HexColor("#002060")  # Azul escuro
        COR_NIVEL_TURMA = colors.HexColor("#1F4E79")   # Azul
        COR_NIVEL_ABAIXO = colors.HexColor("#C00000")  # Vermelho
        COR_NIVEL_BASICO = colors.HexColor("#FFC000")  # Amarelo
        COR_NIVEL_ADEQUADO = colors.HexColor("#70AD47") # Verde claro
        COR_NIVEL_AVANCADO = colors.HexColor("#00B050") # Verde
        COR_FUNDO_ALTERNADO = colors.HexColor("#F2F2F2") # Cinza claro
        
        # Estilos do template
        styles = getSampleStyleSheet()
        
        # Título principal
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=COR_PARTICIPACAO,
            alignment=TA_CENTER,
            spaceAfter=20,
            fontName='Helvetica-Bold'
        )
        
        # Estilo para subtítulos
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=COR_PARTICIPACAO,
            alignment=TA_LEFT,
            spaceAfter=10,
            fontName='Helvetica-Bold'
        )
        
        # Estilo para informações básicas
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=6,
            fontName='Helvetica'
        )
        
        # Estilo para texto normal
        normal_style = ParagraphStyle(
            'Normal',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=6,
            fontName='Helvetica'
        )
        
        # ===== CABEÇALHO =====
        elements.append(Paragraph("RELATÓRIO DE AVALIAÇÃO EDUCACIONAL", title_style))
        elements.append(Spacer(1, 15))
        
        # Informações básicas
        elements.append(Paragraph(f"<b>Escola:</b> {escola_nome}", info_style))
        elements.append(Paragraph(f"<b>Município:</b> {municipio_nome} - {uf}", info_style))
        elements.append(Paragraph(f"<b>Avaliação:</b> {test.title}", info_style))
        elements.append(Paragraph(f"<b>Período:</b> {periodo}", info_style))
        elements.append(Spacer(1, 20))
        
        # ===== SUMÁRIO =====
        elements.append(Paragraph("SUMÁRIO", subtitle_style))
        elements.append(Paragraph(template_data.get('sumario_p1', ''), normal_style))
        elements.append(Paragraph(template_data.get('sumario_p2', ''), normal_style))
        elements.append(Paragraph(template_data.get('sumario_p3', ''), normal_style))
        elements.append(Paragraph(template_data.get('sumario_p4', ''), normal_style))
        elements.append(Spacer(1, 15))
        
        # ===== TABELA DE PARTICIPAÇÃO =====
        elements.append(Paragraph("PARTICIPAÇÃO POR TURMA", subtitle_style))
        
        if template_data.get("participacao_por_turma"):
            headers = ["SÉRIE/TURNO", "MATRICULADOS", "AVALIADOS", "PERCENTUAL", "FALTOSOS"]
            data = []
            
            for p in template_data["participacao_por_turma"]:
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
                str(template_data.get("total_matriculados", 0)),
                str(template_data.get("total_avaliados", 0)),
                f"{template_data.get('percentual_avaliados', 0)}%",
                str(template_data.get("total_faltosos", 0))
            ])
            
            # Criar tabela com estilo do template
            participacao_table = Table([headers] + data, colWidths=[80, 60, 60, 60, 60])
            participacao_table.setStyle(TableStyle([
                # Cabeçalho com cor do template
                ('BACKGROUND', (0, 0), (-1, 0), COR_PARTICIPACAO),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Linhas de dados
                ('BACKGROUND', (0, 1), (-1, -2), colors.white),
                ('ALIGN', (0, 1), (0, -2), 'LEFT'),  # Primeira coluna à esquerda
                ('ALIGN', (1, 1), (-1, -2), 'RIGHT'),  # Outras colunas à direita
                ('FONTNAME', (0, 1), (0, -2), 'Helvetica-Bold'),  # Primeira coluna em negrito
                ('FONTSIZE', (0, 1), (-1, -2), 10),
                
                # Linha total
                ('BACKGROUND', (0, -1), (-1, -1), COR_FUNDO_ALTERNADO),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('ALIGN', (0, -1), (0, -1), 'LEFT'),
                ('ALIGN', (1, -1), (-1, -1), 'RIGHT'),
                
                # Bordas
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            
            elements.append(participacao_table)
            elements.append(Spacer(1, 20))
        
        # ===== NÍVEIS DE APRENDIZAGEM =====
        elements.append(Paragraph("NÍVEIS DE APRENDIZAGEM POR TURMA", subtitle_style))
        
        # Adicionar tabelas por disciplina
        for disciplina, dados in niveis_aprendizagem.items():
            if disciplina != 'GERAL' and dados and dados.get('por_turma'):
                elements.append(Paragraph(f"{disciplina.upper()}", subtitle_style))
                
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
                
                if data:
                    # Criar tabela com cores específicas do template
                    niveis_table = Table([headers] + data, colWidths=[80, 60, 60, 60, 60, 60])
                    niveis_table.setStyle(TableStyle([
                        # Cabeçalho com cores específicas
                        ('BACKGROUND', (0, 0), (0, 0), COR_NIVEL_TURMA),
                        ('BACKGROUND', (1, 0), (1, 0), COR_NIVEL_ABAIXO),
                        ('BACKGROUND', (2, 0), (2, 0), COR_NIVEL_BASICO),
                        ('BACKGROUND', (3, 0), (3, 0), COR_NIVEL_ADEQUADO),
                        ('BACKGROUND', (4, 0), (4, 0), COR_NIVEL_AVANCADO),
                        ('BACKGROUND', (5, 0), (5, 0), COR_NIVEL_TURMA),
                        
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        
                        # Linhas de dados
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),
                        
                        # Bordas
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ]))
                    
                    elements.append(niveis_table)
                    elements.append(Spacer(1, 15))
        
        # Tabela GERAL
        if 'GERAL' in niveis_aprendizagem and niveis_aprendizagem['GERAL'] and niveis_aprendizagem['GERAL'].get('por_turma'):
            elements.append(Paragraph("GERAL", subtitle_style))
            
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
            
            if data:
                geral_table = Table([headers] + data, colWidths=[80, 60, 60, 60, 60, 60])
                geral_table.setStyle(TableStyle([
                    # Cabeçalho com cores específicas
                    ('BACKGROUND', (0, 0), (0, 0), COR_NIVEL_TURMA),
                    ('BACKGROUND', (1, 0), (1, 0), COR_NIVEL_ABAIXO),
                    ('BACKGROUND', (2, 0), (2, 0), COR_NIVEL_BASICO),
                    ('BACKGROUND', (3, 0), (3, 0), COR_NIVEL_ADEQUADO),
                    ('BACKGROUND', (4, 0), (4, 0), COR_NIVEL_AVANCADO),
                    ('BACKGROUND', (5, 0), (5, 0), COR_NIVEL_TURMA),
                    
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    
                    # Linhas de dados
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    
                    # Bordas
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                
                elements.append(geral_table)
                elements.append(Spacer(1, 20))
        
        # ===== PROFICIÊNCIA =====
        elements.append(Paragraph("PROFICIÊNCIA POR TURMA", subtitle_style))
        
        if proficiencia and proficiencia.get('por_disciplina') and 'GERAL' in proficiencia['por_disciplina']:
            headers = ["TURMA", "PROFICIÊNCIA"]
            data = []
            
            for turma_data in proficiencia['por_disciplina']['GERAL']['por_turma']:
                data.append([
                    turma_data.get("turma", ""),
                    f"{turma_data.get('proficiencia', 0):.1f}"
                ])
            
            if data:
                proficiencia_table = Table([headers] + data, colWidths=[120, 80])
                proficiencia_table.setStyle(TableStyle([
                    # Cabeçalho com cor do template
                    ('BACKGROUND', (0, 0), (-1, 0), COR_PROFICIENCIA),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    
                    # Linhas de dados com fundo alternado
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    
                    # Bordas
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                
                elements.append(proficiencia_table)
                elements.append(Spacer(1, 20))
        
        # ===== NOTAS GERAIS =====
        elements.append(Paragraph("NOTAS GERAIS POR TURMA", subtitle_style))
        
        if nota_geral and nota_geral.get('por_disciplina') and 'GERAL' in nota_geral['por_disciplina']:
            headers = ["TURMA", "NOTA"]
            data = []
            
            for turma_data in nota_geral['por_disciplina']['GERAL']['por_turma']:
                data.append([
                    turma_data.get("turma", ""),
                    f"{turma_data.get('nota', 0):.2f}"
                ])
            
            if data:
                notas_table = Table([headers] + data, colWidths=[120, 80])
                notas_table.setStyle(TableStyle([
                    # Cabeçalho com cor do template
                    ('BACKGROUND', (0, 0), (-1, 0), COR_PROFICIENCIA),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    
                    # Linhas de dados com fundo alternado
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    
                    # Bordas
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ]))
                
                elements.append(notas_table)
                elements.append(Spacer(1, 20))
        
        # ===== HABILIDADES POR DISCIPLINA =====
        elements.append(Paragraph("ACERTOS POR HABILIDADE", subtitle_style))
        
        # Adicionar tabelas por disciplina
        for disciplina, dados in acertos_habilidade.items():
            if disciplina != 'GERAL' and dados and dados.get('habilidades'):
                elements.append(Paragraph(f"{disciplina.upper()}", subtitle_style))
                
                headers = ["QUESTÃO", "HABILIDADE", "ACERTOS", "TOTAL", "PERCENTUAL"]
                data = []
                
                for habilidade in dados['habilidades']:
                    data.append([
                        str(habilidade.get("numero_questao", "N/A")),
                        habilidade.get("codigo", "N/A"),
                        str(habilidade.get("acertos", 0)),
                        str(habilidade.get("total", 0)),
                        f"{habilidade.get('percentual', 0)}%"
                    ])
                
                if data:
                    habilidades_table = Table([headers] + data, colWidths=[60, 80, 60, 60, 60])
                    habilidades_table.setStyle(TableStyle([
                        # Cabeçalho com cor do template
                        ('BACKGROUND', (0, 0), (-1, 0), COR_PROFICIENCIA),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        
                        # Linhas de dados
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 1), (-1, -1), 10),
                        
                        # Bordas
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ]))
                    
                    elements.append(habilidades_table)
                    elements.append(Spacer(1, 15))
        
        # ===== ANÁLISE DA IA =====
        if ai_analysis:
            elements.append(Paragraph("ANÁLISE E RECOMENDAÇÕES", subtitle_style))
            
            # Extrair texto da análise
            analise_text = ""
            if isinstance(ai_analysis, dict):
                analise_text = ai_analysis.get('analysis', 'Análise não disponível.')
            else:
                analise_text = str(ai_analysis)
            
            elements.append(Paragraph(analise_text, normal_style))
            elements.append(Spacer(1, 20))
        
        # Construir PDF
        print("=== INICIANDO CONSTRUÇÃO DO PDF ===")
        print(f"Total de elements: {len(elements)}")
        print("Chamando doc.build(elements)...")
        doc.build(elements)
        print("doc.build() concluído com sucesso")
        
        # Obter conteúdo do buffer
        print("Obtendo conteúdo do buffer...")
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        buffer.close()
        print(f"PDF gerado com {len(pdf_content)} bytes")
        
        return pdf_content
        
    except Exception as e:
        print(f"ERRO GERAL ao gerar PDF: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        logging.error(f"Erro ao gerar PDF: {str(e)}")
        raise


# Função DOCX comentada - usando PDF agora
# def _preparar_contexto_docxtpl(doc: DocxTemplate, template_data: Dict[str, Any]) -> Dict[str, Any]:
#    """Prepara o contexto para o template docxtpl"""
    
#    context = {}
    
    # Função para criar tabelas com formatação
#    def make_table(headers, rows, table_type="default"):
#        sub = doc.new_subdoc()
#        t = sub.add_table(rows=1, cols=len(headers))
        
        # Configurar largura das colunas
#        for col in t.columns:
#            col.width = Mm(30)  # 30mm por coluna
        
        # Formatar cabeçalho
#        header_row = t.rows[0]
#        for j, h in enumerate(headers):
#            cell = header_row.cells[j]
#            cell.text = str(h)
            
            # Aplicar formatação específica por tipo de tabela
#            if table_type == "participacao":
                # Cabeçalho azul escuro com texto branco
#                cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="0B2A56" w:val="clear"/>'))
#                for paragraph in cell.paragraphs:
#                    for run in paragraph.runs:
#                        run.font.color.rgb = RGBColor(255, 255, 255)
#                        run.font.bold = True
#                        run.font.size = Pt(10)
#                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
#            elif table_type == "niveis":
                # Cores específicas para cada coluna de níveis
#                colors = ["1F4E79", "C00000", "FFC000", "70AD47", "00B050"]
#                if j < len(colors):
#                    cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="{colors[j]}" w:val="clear"/>'))
#                    for paragraph in cell.paragraphs:
#                        for run in paragraph.runs:
#                            run.font.bold = True
#                            run.font.size = Pt(10)
#                            if j == 0:  # Primeira coluna
#                                run.font.color.rgb = RGBColor(0, 0, 0)
#                            else:  # Outras colunas
#                                run.font.color.rgb = RGBColor(255, 255, 255)
#                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
#            elif table_type in ["proficiencia", "notas"]:
                # Cabeçalho azul escuro com texto branco
#                cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="002060" w:val="clear"/>'))
#                for paragraph in cell.paragraphs:
#                    for run in paragraph.runs:
#                        run.font.color.rgb = RGBColor(255, 255, 255)
#                        run.font.bold = True
#                        run.font.size = Pt(10)
#                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
#            elif table_type == "habilidades":
                # Cabeçalho azul escuro com texto branco
#                cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="002060" w:val="clear"/>'))
#                for paragraph in cell.paragraphs:
#                    for run in paragraph.runs:
#                        run.font.color.rgb = RGBColor(255, 255, 255)
#                        run.font.bold = True
#                        run.font.size = Pt(10)
#                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Adicionar linhas de dados
#        for i, r in enumerate(rows):
#            row = t.add_row().cells
            
            # Aplicar fundo alternado para proficiência e notas
#            if table_type in ["proficiencia", "notas"] and i % 2 == 0:
#                row_bg_color = "F2F2F2"  # Cinza claro
#            else:
#                row_bg_color = "FFFFFF"  # Branco
            
#            for j, val in enumerate(r):
#                cell = row[j]
#                cell.text = str(val)
                
                # Formatar células de dados
#                if table_type == "participacao":
                    # Primeira coluna em negrito
#                    if j == 0:
#                        for paragraph in cell.paragraphs:
#                            for run in paragraph.runs:
#                                run.font.bold = True
                    # Outras colunas alinhadas à direita
#                    else:
#                        for paragraph in cell.paragraphs:
#                            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                
#                elif table_type == "niveis":
                    # Primeira coluna em negrito
#                    if j == 0:
#                        for paragraph in cell.paragraphs:
#                            for run in paragraph.runs:
#                                run.font.bold = True
                    # Outras colunas centralizadas
#                    else:
#                        for paragraph in cell.paragraphs:
#                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
#                elif table_type in ["proficiencia", "notas"]:
                    # Aplicar fundo alternado
#                    cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="{row_bg_color}" w:val="clear"/>'))
                    # Primeira coluna em negrito
#                    if j == 0:
#                        for paragraph in cell.paragraphs:
#                            for run in paragraph.runs:
#                                run.font.bold = True
                    # Outras colunas alinhadas à direita
#                    else:
#                        for paragraph in cell.paragraphs:
#                            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                
#                elif table_type == "habilidades":
                    # Primeira coluna em negrito
#                    if j == 0:
#                        for paragraph in cell.paragraphs:
#                            for run in paragraph.runs:
#                                run.font.bold = True
                    # Outras colunas centralizadas
#                    else:
#                        for paragraph in cell.paragraphs:
#                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Aplicar bordas a todas as células
#        for row in t.rows:
#            for cell in row.cells:
#                cell._tc.get_or_add_tcPr().append(parse_xml('<w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/></w:tcBorders>'))
        
#        return sub
    
    # Função para dividir listas em chunks
#    def chunk(lst, n): 
#        return [lst[i:i+n] for i in range(0, len(lst), n)]
    
    # Função para construir tabelas multicolunas
#    def build_multicol(series, disciplinas, max_cols=3, incluir_media=True, incluir_municipal=True, table_type="default"):
#        subs = []
#        for cols in chunk(disciplinas, max_cols):
#            headers = ["SÉRIE/TURNO"] + cols + (["MÉDIA"] if incluir_media else []) + (["MUNICIPAL"] if incluir_municipal else [])
#            rows = []
#            for s in series:
#                linha = [s["serie_turno"]]
#                soma = cont = 0
#                for c in cols:
#                    v = s.get(c, ""); 
#                    linha.append(v)
#                    if isinstance(v, (int, float)): 
#                        soma += v; 
#                        cont += 1
#                if incluir_media: 
#                    linha.append(round(soma/cont, 2) if cont else "")
#                if incluir_municipal: 
#                    linha.append(s.get("MUNICIPAL", ""))
#                rows.append(linha)
            
            # Adicionar linha total
#            if rows:
#                total_row = ["9º GERAL"]
#                for j in range(1, len(headers)):
#                    if j == 1:  # Primeira coluna de dados
#                        valores = [r[j] for r in rows if isinstance(r[j], (int, float))]
#                        total = sum(valores) / len(valores) if valores else 0
#                        total_row.append(round(total, 2))
#                    elif j == len(headers) - 2 and incluir_media:  # Coluna MÉDIA
#                        valores = [r[j] for r in rows if isinstance(r[j], (int, float))]
#                        total = sum(valores) / len(valores) if valores else 0
#                        total_row.append(round(total, 2))
#                    elif j == len(headers) - 1 and incluir_municipal:  # Coluna MUNICIPAL
#                        total_row.append("")  # Vazia para linha total
#                    else:
#                        valores = [r[j] for r in rows if isinstance(r[j], (int, float))]
#                        total = sum(valores) / len(valores) if valores else 0
#                        total_row.append(round(total, 2))
#                rows.append(total_row)
            
#            subs.append(make_table(headers, rows, table_type))
#        return subs
    
    # 1. Tabela de participação
#    if template_data.get("participacao_por_turma"):
#        headers = ["SÉRIE/TURNO", "MATRICULADOS", "AVALIADOS", "PERCENTUAL", "FALTOSOS"]
#        rows = []
#        for p in template_data["participacao_por_turma"]:
#            rows.append([
#                p.get("turma", ""),
#                p.get("matriculados", 0),
#                p.get("avaliados", 0),
#                f"{p.get('percentual', 0)}%",
#                p.get("faltosos", 0)
#            ])
        
        # Adicionar linha total
#        rows.append([
#            "9º GERAL",
#            template_data.get("total_matriculados", 0),
#            template_data.get("total_avaliados", 0),
#            f"{template_data.get('percentual_avaliados', 0)}%",
#            template_data.get("total_faltosos", 0)
#        ])
        
#        context["tabela_participacao"] = make_table(headers, rows, "participacao")
    
    # 2. Blocos de níveis de aprendizagem
#    context["blocos_niveis"] = _construir_blocos_niveis(doc, template_data)
    
    # 3. Tabelas de proficiência
#    if template_data.get("proficiencia_disciplinas") and template_data.get("proficiencia_series"):
#        subs_prof = build_multicol(
#            template_data["proficiencia_series"], 
#            template_data["proficiencia_disciplinas"],
#            table_type="proficiencia"
#        )
#        context["tabela_proficiencia_1"] = subs_prof[0] if subs_prof else doc.new_subdoc()
#        context["tabela_proficiencia_2"] = subs_prof[1] if len(subs_prof) > 1 else doc.new_subdoc()
    
    # 4. Tabelas de notas
#    if template_data.get("notas_disciplinas") and template_data.get("notas_series"):
#        subs_notas = build_multicol(
#            template_data["notas_series"], 
#            template_data["notas_disciplinas"],
#            table_type="notas"
#        )
#        context["tabela_nota_1"] = subs_notas[0] if subs_notas else doc.new_subdoc()
#        context["tabela_nota_2"] = subs_notas[1] if len(subs_notas) > 1 else doc.new_subdoc()
    
    # 5. Tabelas de habilidades por disciplina
    # Criar um Subdoc para cada disciplina individual
#    disciplinas_list = template_data.get("disciplinas", []).split(", ") if isinstance(template_data.get("disciplinas"), str) else template_data.get("disciplinas", [])
    
#    for disciplina in disciplinas_list:
#        if disciplina and disciplina != "Disciplina Geral":
            # Criar placeholder específico para cada disciplina
#            placeholder_name = f"tabela_habilidades_{disciplina.lower().replace(' ', '_').replace('-', '_')}"
            
#            key = f"habilidades_{disciplina.lower().replace(' ', '_')}"
#            habilidades = template_data.get(key, [])
            
#            if habilidades:
                # Criar Subdoc para esta disciplina
#                sub_doc = doc.new_subdoc()
                
                # Título da disciplina
#                p = sub_doc.add_paragraph(disciplina.upper())
#                p.runs[0].bold = True
                
#                headers = ["QUESTÃO", "HABILIDADE", "ACERTOS", "TOTAL", "PERCENTUAL"]
#                rows = []
#                for h in habilidades:
#                    rows.append([
#                        h.get("questoes", [{}])[0].get("numero", "N/A") if h.get("questoes") else "N/A",
#                        h.get("codigo", "N/A"),
#                        h.get("acertos", 0),
#                        h.get("total", 0),
#                        f"{h.get('percentual', 0)}%"
#                    ])
                
                # Criar tabela
#                table = sub_doc.add_table(rows=1, cols=len(headers))
#                for j, h in enumerate(headers): 
#                    table.rows[0].cells[j].text = str(h)
#                for r in rows:
#                    row = table.add_row().cells
#                    for j, val in enumerate(r): 
#                        row[j].text = str(val)
                
                # Adicionar ao contexto com o nome específico da disciplina
#                context[placeholder_name] = sub_doc
    
    # Também criar um Subdoc combinado para o placeholder geral
#    habilidades_combined = doc.new_subdoc()
#    for disciplina in disciplinas_list:
#        if disciplina and disciplina != "Disciplina Geral":
#            key = f"habilidades_{disciplina.lower().replace(' ', '_')}"
#            habilidades = template_data.get(key, [])
#            if habilidades:
                # Título da disciplina
#                p = habilidades_combined.add_paragraph(disciplina.upper())
#                p.runs[0].bold = True
                
#                headers = ["QUESTÃO", "HABILIDADE", "ACERTOS", "TOTAL", "PERCENTUAL"]
#                rows = []
#                for h in habilidades:
#                    rows.append([
#                        h.get("questoes", [{}])[0].get("numero", "N/A") if h.get("questoes") else "N/A",
#                        h.get("codigo", "N/A"),
#                        h.get("acertos", 0),
#                        h.get("total", 0),
#                        f"{h.get('percentual', 0)}%"
#                    ])
                
                # Criar tabela com formatação especial
#                table = habilidades_combined.add_table(rows=2, cols=len(headers))  # 2 linhas: cabeçalho + códigos
                
                # Configurar largura das colunas
#                for col in table.columns:
#                    col.width = Mm(25)
                
                # Formatar cabeçalho (primeira linha)
#                header_row = table.rows[0]
#                for j, h in enumerate(headers):
#                    cell = header_row.cells[j]
#                    cell.text = str(h)
                    # Cabeçalho azul escuro com texto branco
#                    cell._tc.get_or_add_tcPr().append(parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="002060" w:val="clear"/>'))
#                    for paragraph in cell.paragraphs:
#                        for run in paragraph.runs:
#                            run.font.color.rgb = RGBColor(255, 255, 255)
#                            run.font.bold = True
#                            run.font.size = Pt(10)
#                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Adicionar linha de códigos (segunda linha)
#                codes_row = table.rows[1]
#                for j in range(len(headers)):
#                    cell = codes_row.cells[j]
#                    if j == 0:  # Primeira coluna
#                        cell.text = "CÓDIGOS"
#                    else:  # Outras colunas com códigos das habilidades
#                        if j-1 < len(habilidades):
#                            skill_code = habilidades[j-1].get("codigo", "")
#                            cell.text = str(skill_code)
#                        else:
#                            cell.text = ""
                    
                    # Fundo amarelo para linha de códigos
#                    cell._tc.get_or_add_tcPr().append(parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="FFC000" w:val="clear"/>'))
#                    for paragraph in cell.paragraphs:
#                        for run in paragraph.runs:
#                            run.font.bold = True
#                            run.font.size = Pt(9)
#                            run.font.color.rgb = RGBColor(0, 0, 0)
#                            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Adicionar linhas de dados (percentuais)
#                for r in rows:
#                    row = table.add_row().cells
#                    for j, val in enumerate(r):
#                        cell = row[j]
#                        cell.text = str(val)
                        
                        # Primeira coluna em negrito
#                        if j == 0:
#                            for paragraph in cell.paragraphs:
#                                for run in paragraph.runs:
#                                    run.font.bold = True
                        # Outras colunas centralizadas
#                        else:
#                            for paragraph in cell.paragraphs:
#                                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Aplicar bordas
#                for row in table.rows:
#                    for cell in row.cells:
#                        cell._tc.get_or_add_tcPr().append(parse_xml('<w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/></w:tcBorders>'))
                
                # Espaçamento
#                habilidades_combined.add_paragraph("")
    
#    context["tabela_habilidades_disc"] = habilidades_combined
    
    # 6. Análises da IA (já preparadas na função _preparar_dados_ia)
    # Essas variáveis já estão sendo adicionadas automaticamente no loop abaixo
    
    # 7. Considerações finais
#    context["consideracoes_finais"] = template_data.get("consideracoes_finais", "Relatório gerado automaticamente pelo sistema.")
    
    # 8. Adicionar todos os campos de texto simples
#    for key, value in template_data.items():
#        if isinstance(value, (str, int, float)) and key not in context:
#            context[key] = value
    
    # 9. Adicionar campos específicos que podem estar faltando
#    context["simulados_label"] = "Avaliação Diagnóstica"
#    context["referencia"] = "Relatório de Avaliação Educacional"
#    context["escola_extenso"] = template_data.get("escola", "Escola")
    
    # Adicionar campos que podem estar faltando
#    context["total_avaliados"] = template_data.get("total_alunos", 0)
#    context["percentual_avaliados"] = template_data.get("percentual_avaliados", 0)
    
    # Debug: mostrar quais campos estão sendo enviados
#    logging.info(f"Campos do contexto: {list(context.keys())}")
#    logging.info(f"Disciplinas encontradas: {disciplinas_list}")
    
#    return context



#def _construir_blocos_niveis(doc: DocxTemplate, template_data: Dict[str, Any]):
#    """Constrói os blocos de níveis de aprendizagem como Subdoc"""
#    sub = doc.new_subdoc()
    
    # Adicionar tabelas para cada disciplina
#    for disciplina in template_data.get("disciplinas", []).split(", "):
#        if disciplina and disciplina != "Disciplina Geral":
#            key = f"niveis_{disciplina.lower().replace(' ', '_')}"
#            niveis = template_data.get(key, [])
            
#            if niveis:
                # Título da disciplina
#                p = sub.add_paragraph(disciplina.upper())
#                p.runs[0].bold = True
                
                # Tabela de níveis
#                headers = ["SÉRIE/TURNO", "ABAIXO DO BÁSICO", "BÁSICO", "ADEQUADO", "AVANÇADO"]
#                rows = []
#                for n in niveis:
#                    rows.append([
#                        n.get("turma", ""),
#                        n.get("abaixo_do_basico", 0),
#                        n.get("basico", 0),
#                        n.get("adequado", 0),
#                        n.get("avancado", 0)
#                    ])
                
                # Adicionar linha total se disponível
#                total_key = f"niveis_{disciplina.lower().replace(' ', '_')}_total"
#                if total_key in template_data:
#                    total = template_data[total_key]
#                    rows.append([
#                        "TOTAL",
#                        total.get("abaixo_do_basico", 0),
#                        total.get("basico", 0),
#                        total.get("adequado", 0),
#                        total.get("avancado", 0)
#                    ])
                
                # Criar tabela com formatação
#                table = sub.add_table(rows=1, cols=len(headers))
                
                # Configurar largura das colunas
#                for col in table.columns:
#                    col.width = Mm(30)
                
                # Formatar cabeçalho com cores específicas
#                header_colors = ["1F4E79", "C00000", "FFC000", "70AD47", "00B050"]
#                for j, h in enumerate(headers):
#                    cell = table.rows[0].cells[j]
#                    cell.text = str(h)
                    
#                    if j < len(header_colors):
#                        cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="{header_colors[j]}" w:val="clear"/>'))
#                        for paragraph in cell.paragraphs:
#                            for run in paragraph.runs:
#                                run.font.bold = True
#                                run.font.size = Pt(10)
#                                if j == 0:  # Primeira coluna
#                                    run.font.color.rgb = RGBColor(0, 0, 0)
#                                else:  # Outras colunas
#                                    run.font.color.rgb = RGBColor(255, 255, 255)
#                                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Adicionar linhas de dados
#                for r in rows:
#                    row = table.add_row().cells
#                    for j, val in enumerate(r):
#                        cell = row[j]
#                        cell.text = str(val)
                        
                        # Primeira coluna em negrito
#                        if j == 0:
#                            for paragraph in cell.paragraphs:
#                                for run in paragraph.runs:
#                                    run.font.bold = True
                        # Outras colunas centralizadas
#                        else:
#                            for paragraph in cell.paragraphs:
#                                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                
                # Aplicar bordas
#                for row in table.rows:
#                    for cell in row.cells:
#                        cell._tc.get_or_add_tcPr().append(parse_xml('<w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/></w:tcBorders>'))
                
                # Espaçamento
#                sub.add_paragraph("")
    
    # Adicionar tabela geral
#    niveis_geral = template_data.get("niveis_geral", [])
#    if niveis_geral:
#        p = sub.add_paragraph("MÉDIA GERAL")
#        p.runs[0].bold = True
        
#        headers = ["SÉRIE/TURNO", "ABAIXO DO BÁSICO", "BÁSICO", "ADEQUADO", "AVANÇADO"]
#        rows = []
#        for n in niveis_geral:
#            rows.append([
#                n.get("turma", ""),
#                n.get("abaixo_do_basico", 0),
#                n.get("basico", 0),
#                n.get("adequado", 0),
#                n.get("avancado", 0)
#            ])
        
#        table = sub.add_table(rows=1, cols=len(headers))
        
        # Configurar largura das colunas
#        for col in table.columns:
#            col.width = Mm(30)
        
        # Formatar cabeçalho com cores específicas
#        header_colors = ["1F4E79", "C00000", "FFC000", "70AD47", "00B050"]
#        for j, h in enumerate(headers):
#            cell = table.rows[0].cells[j]
#            cell.text = str(h)
            
#            if j < len(header_colors):
#                cell._tc.get_or_add_tcPr().append(parse_xml(f'<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="{header_colors[j]}" w:val="clear"/>'))
#                for paragraph in cell.paragraphs:
#                    for run in paragraph.runs:
#                        run.font.bold = True
#                        run.font.size = Pt(10)
#                        if j == 0:  # Primeira coluna
#                            run.font.color.rgb = RGBColor(0, 0, 0)
#                        else:  # Outras colunas
#                            run.font.color.rgb = RGBColor(255, 255, 255)
#                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Adicionar linhas de dados
#        for r in rows:
#            row = table.add_row().cells
#            for j, val in enumerate(r):
#                cell = row[j]
#                cell.text = str(val)
                
                # Aplicar fundo cinza para linha total
#                cell._tc.get_or_add_tcPr().append(parse_xml('<w:shd xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:fill="D9D9D9" w:val="clear"/>'))
                
                # Primeira coluna em negrito
#                if j == 0:
#                    for paragraph in cell.paragraphs:
#                        for run in paragraph.runs:
#                            run.font.bold = True
                # Outras colunas centralizadas
#                else:
#                    for paragraph in cell.paragraphs:
#                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        
        # Aplicar bordas
#        for row in table.rows:
#            for cell in row.cells:
#                cell._tc.get_or_add_tcPr().append(parse_xml('<w:tcBorders xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:top w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:left w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="000000"/><w:right w:val="single" w:sz="4" w:space="0" w:color="000000"/></w:tcBorders>'))
    
#    return sub



def _obter_nome_curso(test: Test) -> str:
    """Obtém o nome do curso baseado no ID, seguindo a mesma lógica do EvaluationResultService"""
    course_name = "Anos Iniciais"  # Padrão
    if test.course:
        try:
            from app.utils.response_formatters import _get_education_stage_safely
            course_obj = _get_education_stage_safely(test.course)
            if course_obj:
                course_name = course_obj.name
                logging.info(f"Curso encontrado: {course_name}")
            else:
                logging.warning(f"Curso não encontrado na tabela EducationStage: {test.course}")
        except Exception as e:
            logging.warning(f"Erro ao buscar curso: {test.course}. Erro: {str(e)}. Usando Anos Iniciais como padrão.")
            pass
    else:
        logging.info("test.course é None ou vazio, usando padrão Anos Iniciais")
    return course_name


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


def _obter_ordem_disciplinas_avaliacao(test: Test) -> List[str]:
    """
    Obtém a ordem das disciplinas conforme aparecem na avaliação.
    Retorna uma lista ordenada pela primeira aparição de cada disciplina nas questões.
    
    Args:
        test: Objeto Test da avaliação
        
    Returns:
        Lista de nomes de disciplinas na ordem de aparição
    """
    if not test or not test.questions:
        return []
    
    from app.models.skill import Skill
    
    # Buscar todas as habilidades
    skill_ids = set()
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_ids.add(clean_skill_id)
    
    skills_dict = {}
    if skill_ids:
        skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
        skills_dict = {str(skill.id): skill for skill in skills}
    
    # Mapear questões para disciplinas na ordem que aparecem
    disciplinas_ordem = []
    disciplinas_vistas = set()
    
    for question in test.questions:
        disciplina = None
        
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    disciplina = subject.name
            else:
                disciplina = "Disciplina Geral"
        else:
            # Questões sem skill: mapear para disciplina principal da avaliação
            if test.subject_rel:
                disciplina = test.subject_rel.name
            else:
                disciplina = "Disciplina Geral"
        
        # Adicionar disciplina à lista de ordem se ainda não foi vista
        if disciplina and disciplina not in disciplinas_vistas:
            disciplinas_ordem.append(disciplina)
            disciplinas_vistas.add(disciplina)
    
    return disciplinas_ordem


def _obter_metadados_relatorio(test: Test, class_tests: List[ClassTest], scope_type: str, scope_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtém metadados do relatório (escola, município, UF, período, escopo)
    
    Args:
        test: Objeto Test da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
        scope_type: Tipo de escopo ('school', 'city', 'all')
        scope_id: ID do escopo quando aplicável (ID da escola ou município)
    
    Returns:
        Dict com metadados do relatório
    """
    escola_nome = "Escola não identificada"
    escola_id = None
    municipio_nome = "Município não identificado"
    municipio_id = None
    uf = "AL"
    
    try:
        # Buscar primeira turma para obter escola e município
        if class_tests:
            first_class_test = class_tests[0]
            first_class = Class.query.get(first_class_test.class_id)
            
            if first_class and first_class.school:
                escola_nome = first_class.school.name
                escola_id = first_class.school.id
                
                if first_class.school.city:
                    municipio_nome = first_class.school.city.name
                    municipio_id = first_class.school.city.id
                    uf = first_class.school.city.state or "AL"
                
                # Se for escopo por escola, usar nome da escola específica
                if scope_type == 'school' and scope_id:
                    escola_obj = School.query.get(scope_id)
                    if escola_obj:
                        escola_nome = escola_obj.name
                        escola_id = escola_obj.id
                        if escola_obj.city:
                            municipio_nome = escola_obj.city.name
                            municipio_id = escola_obj.city.id
                            uf = escola_obj.city.state or "AL"
                
                # Se for escopo por município, usar nome do município específico
                if scope_type == 'city' and scope_id:
                    municipio_obj = City.query.get(scope_id)
                    if municipio_obj:
                        municipio_nome = municipio_obj.name
                        municipio_id = municipio_obj.id
                        uf = municipio_obj.state or "AL"
    except Exception as e:
        logging.warning(f"Erro ao obter dados da escola/município: {str(e)}")
    
    # Determinar período atual
    from datetime import datetime
    now = datetime.now()
    mes_atual = now.strftime("%B").upper()
    ano_atual = now.year
    periodo = f"{ano_atual}.1"
    
    return {
        "escola": escola_nome,
        "escola_id": escola_id,
        "municipio": municipio_nome,
        "municipio_id": municipio_id,
        "uf": uf,
        "periodo": periodo,
        "mes": mes_atual,
        "ano": ano_atual,
        "scope_type": scope_type,
        "scope_id": scope_id
    }


def _calcular_totais_alunos_por_escopo(evaluation_id: str, class_tests: List[ClassTest], scope_type: str) -> Dict[str, Any]:
    """
    Calcula totais de alunos por escopo (turma, escola ou município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
        scope_type: Tipo de escopo ('school', 'city', 'all')
    
    Returns:
        Dict com totais agrupados conforme o escopo
    """
    if scope_type == 'city' or scope_type == 'all':
        return _calcular_totais_alunos_por_municipio(evaluation_id, class_tests)
    else:
        return _calcular_totais_alunos(evaluation_id, class_tests)


def _calcular_totais_alunos_por_municipio(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """
    Calcula totais de alunos agrupados por escola (para relatório por município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
    
    Returns:
        Dict com totais agrupados por escola
    """
    class_ids = [ct.class_id for ct in class_tests]
    
    # Buscar todos os alunos das turmas onde a avaliação foi aplicada
    from sqlalchemy.orm import joinedload as jl
    students = Student.query.options(
        jl(Student.class_)
        # ❌ REMOVIDO: jl(Student.class_, Class.school) - Class.school é property, não relationship
    ).filter(Student.class_id.in_(class_ids)).all()
    
    # Buscar resultados da avaliação (alunos que realizaram)
    evaluation_results = EvaluationResult.query.filter_by(test_id=evaluation_id).all()
    results_by_student = {er.student_id: er for er in evaluation_results}
    
    # Agrupar alunos por escola
    students_by_school = defaultdict(list)
    for student in students:
        if student.class_ and student.class_.school:
            students_by_school[student.class_.school.id].append(student)
    
    # Calcular estatísticas por escola
    por_escola = []
    total_matriculados = 0
    total_avaliados = 0
    
    for school_id, school_students in students_by_school.items():
        # Matriculados = Alunos da escola onde a avaliação foi aplicada
        matriculados = len(school_students)
        # Avaliados = Alunos que realmente realizaram a avaliação (têm resultado)
        avaliados = sum(1 for s in school_students if s.id in results_by_student)
        percentual = (avaliados / matriculados * 100) if matriculados > 0 else 0
        # Faltosos = Matriculados que não realizaram
        faltosos = matriculados - avaliados
        
        # Obter nome da escola
        escola_nome = "Escola Desconhecida"
        if school_students and school_students[0].class_ and school_students[0].class_.school:
            escola_nome = school_students[0].class_.school.name
        
        por_escola.append({
            "escola": escola_nome,
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
        "por_escola": por_escola,
        "total_geral": {
            "matriculados": total_matriculados,
            "avaliados": total_avaliados,
            "percentual": round(total_percentual, 1),
            "faltosos": total_faltosos
        }
    }


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
    
    # Calcular estatísticas por turma (agrupando por nome de turma)
    dados_por_nome_turma = defaultdict(lambda: {"matriculados": 0, "avaliados": 0})
    total_matriculados = 0
    total_avaliados = 0

    for class_test in class_tests:
        class_id = class_test.class_id
        class_students = students_by_class[class_id]

        # Obter nome da turma
        turma_nome = "Turma Desconhecida"
        if class_students and class_students[0].class_:
            turma_nome = class_students[0].class_.name
        else:
            # Se não há alunos, buscar nome da turma diretamente
            turma_obj = Class.query.get(class_id)
            if turma_obj:
                turma_nome = turma_obj.name

        # Matriculados = Alunos da turma onde a avaliação foi aplicada
        matriculados = len(class_students)
        # Avaliados = Alunos que realmente realizaram a avaliação (têm resultado)
        avaliados = sum(1 for s in class_students if s.id in results_by_student)

        # Agregar por nome de turma (pode haver múltiplas turmas com mesmo nome)
        dados_por_nome_turma[turma_nome]["matriculados"] += matriculados
        dados_por_nome_turma[turma_nome]["avaliados"] += avaliados

        total_matriculados += matriculados
        total_avaliados += avaliados

    # Criar lista final agrupada por nome de turma
    por_turma = []
    for turma_nome in sorted(dados_por_nome_turma.keys()):
        dados = dados_por_nome_turma[turma_nome]
        matriculados = dados["matriculados"]
        avaliados = dados["avaliados"]
        percentual = (avaliados / matriculados * 100) if matriculados > 0 else 0
        faltosos = matriculados - avaliados

        por_turma.append({
            "turma": turma_nome,
            "matriculados": matriculados,
            "avaliados": avaliados,
            "percentual": round(percentual, 1),
            "faltosos": faltosos
        })
    
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


def _calcular_niveis_aprendizagem_por_escopo(evaluation_id: str, class_tests: List[ClassTest], scope_type: str) -> Dict[str, Any]:
    """
    Calcula níveis de aprendizagem por escopo (turma, escola ou município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
        scope_type: Tipo de escopo ('school', 'city', 'all')
    
    Returns:
        Dict com níveis de aprendizagem agrupados conforme o escopo
    """
    if scope_type == 'city' or scope_type == 'all':
        return _calcular_niveis_aprendizagem_por_municipio(evaluation_id, class_tests)
    else:
        return _calcular_niveis_aprendizagem(evaluation_id, class_tests)


def _calcular_niveis_aprendizagem_por_municipio(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """
    Calcula níveis de aprendizagem agrupados por escola (para relatório por município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
    
    Returns:
        Dict com níveis de aprendizagem agrupados por escola
    """
    from app.models.skill import Skill
    from app.services.evaluation_calculator import EvaluationCalculator
    
    # Buscar questões da avaliação para identificar disciplinas
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    logging.info(f"Calculando níveis de aprendizagem por município para avaliação {evaluation_id}")
    
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
    disciplinas_identificadas = set()
    
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                    disciplinas_identificadas.add(subject.name)
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
                disciplinas_identificadas.add(test.subject_rel.name)
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
    
    # Buscar resultados da avaliação
    from sqlalchemy.orm import joinedload as jl
    evaluation_results = EvaluationResult.query.options(
        jl(EvaluationResult.student),
        jl(EvaluationResult.student, Student.class_)
        # ❌ REMOVIDO: jl(EvaluationResult.student, Student.class_, Class.school) - Class.school é property
    ).filter_by(test_id=evaluation_id).all()
    
    # Agrupar por escola e disciplina
    class_ids = [ct.class_id for ct in class_tests]
    results_by_school = defaultdict(list)
    
    for result in evaluation_results:
        if result.student.class_id in class_ids and result.student.class_ and result.student.class_.school:
            school_id = result.student.class_.school.id
            results_by_school[school_id].append(result)
    
    # Calcular níveis por escola e disciplina
    # Obter ordem das disciplinas conforme aparecem na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    disciplinas_para_processar = ordem_disciplinas if ordem_disciplinas else list(disciplinas_identificadas)
    
    niveis_por_disciplina = {}
    
    for disciplina in disciplinas_para_processar:
        niveis_por_disciplina[disciplina] = {
            'por_escola': [],
            'total_geral': {
                'abaixo_do_basico': 0,
                'basico': 0,
                'adequado': 0,
                'avancado': 0,
                'total': 0
            }
        }
        
        total_abaixo = 0
        total_basico = 0
        total_adequado = 0
        total_avancado = 0
        total_geral = 0
        
        for school_id, school_results in results_by_school.items():
            # Filtrar resultados por disciplina (simplificado - usando todos os resultados da escola)
            escola_nome = "Escola Desconhecida"
            if school_results and school_results[0].student.class_ and school_results[0].student.class_.school:
                escola_nome = school_results[0].student.class_.school.name
            
            # Contar classificações
            abaixo = sum(1 for r in school_results if 'abaixo' in r.classification.lower() or 'básico' in r.classification.lower())
            basico = sum(1 for r in school_results if 'básico' in r.classification.lower() and 'abaixo' not in r.classification.lower())
            adequado = sum(1 for r in school_results if 'adequado' in r.classification.lower())
            avancado = sum(1 for r in school_results if 'avançado' in r.classification.lower() or 'avancado' in r.classification.lower())
            total_escola = len(school_results)
            
            niveis_por_disciplina[disciplina]['por_escola'].append({
                'escola': escola_nome,
                'abaixo_do_basico': abaixo,
                'basico': basico,
                'adequado': adequado,
                'avancado': avancado,
                'total': total_escola
            })
            
            total_abaixo += abaixo
            total_basico += basico
            total_adequado += adequado
            total_avancado += avancado
            total_geral += total_escola
        
        niveis_por_disciplina[disciplina]['total_geral'] = {
            'abaixo_do_basico': total_abaixo,
            'basico': total_basico,
            'adequado': total_adequado,
            'avancado': total_avancado,
            'total': total_geral
        }
    
    def _normalize_classification(label: str) -> Optional[str]:
        if not label:
            return None
        label_lower = label.lower()
        if "abaixo" in label_lower:
            return "abaixo_do_basico"
        if "básico" in label_lower or "basico" in label_lower:
            return "basico"
        if "adequado" in label_lower:
            return "adequado"
        if "avançado" in label_lower or "avancado" in label_lower:
            return "avancado"
        return None

    # Mapear escolas presentes no escopo (inclusive as sem resultados) para garantir entradas com zero
    escolas_no_escopo: Dict[str, School] = {}
    class_ids_escopo = [ct.class_id for ct in class_tests if getattr(ct, "class_id", None)]
    if class_ids_escopo:
        # ❌ REMOVIDO: joinedload(Class.school) - Class.school é property, não relationship
        classes = Class.query.filter(Class.id.in_(class_ids_escopo)).all()
        for cls in classes:
            if cls and cls.school:
                escolas_no_escopo[str(cls.school.id)] = cls.school

    dados_gerais_por_escola_lista = []
    total_geral_acumulado = {
        "abaixo_do_basico": 0,
        "basico": 0,
        "adequado": 0,
        "avancado": 0,
        "total": 0
    }

    for school_id, school in escolas_no_escopo.items():
        escola_nome = school.name if school else "Escola Desconhecida"
        contagem_escola = {
            "escola": escola_nome,
            "abaixo_do_basico": 0,
            "basico": 0,
            "adequado": 0,
            "avancado": 0,
            "total": 0
        }

        for resultado in results_by_school.get(school_id, []):
            categoria = _normalize_classification(resultado.classification)
            if not categoria:
                continue
            contagem_escola[categoria] += 1
            contagem_escola["total"] += 1

        total_geral_acumulado["abaixo_do_basico"] += contagem_escola["abaixo_do_basico"]
        total_geral_acumulado["basico"] += contagem_escola["basico"]
        total_geral_acumulado["adequado"] += contagem_escola["adequado"]
        total_geral_acumulado["avancado"] += contagem_escola["avancado"]
        total_geral_acumulado["total"] += contagem_escola["total"]

        dados_gerais_por_escola_lista.append(contagem_escola)

    # Caso não haja escolas identificadas (por segurança), construir a partir dos resultados disponíveis
    if not dados_gerais_por_escola_lista and results_by_school:
        for school_id, school_results in results_by_school.items():
            escola_nome = "Escola Desconhecida"
            if school_results and school_results[0].student and school_results[0].student.class_ and school_results[0].student.class_.school:
                escola_nome = school_results[0].student.class_.school.name

            contagem_escola = {
                "escola": escola_nome,
                "abaixo_do_basico": 0,
                "basico": 0,
                "adequado": 0,
                "avancado": 0,
                "total": 0
            }

            for resultado in school_results:
                categoria = _normalize_classification(resultado.classification)
                if not categoria:
                    continue
                contagem_escola[categoria] += 1
                contagem_escola["total"] += 1

            total_geral_acumulado["abaixo_do_basico"] += contagem_escola["abaixo_do_basico"]
            total_geral_acumulado["basico"] += contagem_escola["basico"]
            total_geral_acumulado["adequado"] += contagem_escola["adequado"]
            total_geral_acumulado["avancado"] += contagem_escola["avancado"]
            total_geral_acumulado["total"] += contagem_escola["total"]

            dados_gerais_por_escola_lista.append(contagem_escola)

    niveis_por_disciplina["GERAL"] = {
        "por_escola": dados_gerais_por_escola_lista,
        "total_geral": total_geral_acumulado
    }
    
    # Ordenar disciplinas pela ordem de aparição na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    resultado_ordenado = OrderedDict()
    
    # Adicionar disciplinas na ordem de aparição
    for disciplina in ordem_disciplinas:
        if disciplina in niveis_por_disciplina:
            resultado_ordenado[disciplina] = niveis_por_disciplina[disciplina]
    
    # Adicionar disciplinas que não estão na ordem (caso existam)
    for disciplina, dados in niveis_por_disciplina.items():
        if disciplina not in resultado_ordenado and disciplina != "GERAL":
            resultado_ordenado[disciplina] = dados
    
    # Adicionar "GERAL" sempre por último
    if "GERAL" in niveis_por_disciplina:
        resultado_ordenado["GERAL"] = niveis_por_disciplina["GERAL"]
    
    return resultado_ordenado


def _calcular_niveis_aprendizagem(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula níveis de aprendizagem por turma e disciplina"""
    from app.models.skill import Skill
    from app.services.evaluation_calculator import EvaluationCalculator
    
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
        
        # Obter nome da turma (mesmo se não houver resultados)
        turma_nome = "Turma Desconhecida"
        
        # Tentar obter nome da turma de diferentes formas
        if class_results and class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        else:
            # Se não há resultados, buscar nome da turma diretamente
            turma_obj = Class.query.get(class_id)
            if turma_obj:
                turma_nome = turma_obj.name
        
        logging.info(f"Processando turma: {turma_nome}")
        
        # Para cada disciplina, calcular níveis de aprendizagem
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        # Se não há disciplinas encontradas nesta turma, usar todas as disciplinas identificadas
        # (para incluir turmas sem resultados, mostrando zeros)
        if not disciplinas_turma:
            disciplinas_turma = disciplinas_identificadas
            logging.info(f"Turma {turma_nome} não tem resultados - usando todas as disciplinas disponíveis")
        
        logging.info(f"Disciplinas encontradas na turma {turma_nome}: {disciplinas_turma}")
        
        for disciplina in disciplinas_turma:
            # Contar classificações para esta disciplina e turma
            classificacoes = {"Abaixo do Básico": 0, "Básico": 0, "Adequado": 0, "Avançado": 0}
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Calcular classificação específica para esta disciplina
                    disciplina_answers = student_discipline_results[student_id][disciplina]
                    disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]
                    
                    # Calcular acertos específicos para esta disciplina
                    correct_answers_disciplina = 0
                    for answer in disciplina_answers:
                        question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                        if question:
                            if question.question_type == 'multiple_choice':
                                is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                if is_correct:
                                    correct_answers_disciplina += 1
                            elif question.correct_answer:
                                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                    correct_answers_disciplina += 1
                    
                    # Calcular proficiência específica para esta disciplina
                    if len(disciplina_questions) > 0:
                        # Obter nome do curso
                        course_name = _obter_nome_curso(test)
                        
                        proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions),
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        
                        # Determinar classificação específica para esta disciplina
                        classification_disciplina = EvaluationCalculator.determine_classification(
                            proficiency=proficiency_disciplina,
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        
                        if classification_disciplina in classificacoes:
                            classificacoes[classification_disciplina] += 1
                            disciplinas_resultado[disciplina]["geral"][classification_disciplina] += 1
            
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
        
        # Calcular dados gerais para esta turma (média das disciplinas específicas)
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                # Calcular classificação geral baseada na média das proficiências específicas por disciplina
                proficiencias_aluno = []
                for disciplina in student_discipline_results[student_id].keys():
                    disciplina_answers = student_discipline_results[student_id][disciplina]
                    disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]
                    
                    # Calcular acertos específicos para esta disciplina
                    correct_answers_disciplina = 0
                    for answer in disciplina_answers:
                        question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                        if question:
                            if question.question_type == 'multiple_choice':
                                is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                if is_correct:
                                    correct_answers_disciplina += 1
                            elif question.correct_answer:
                                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                    correct_answers_disciplina += 1
                    
                    # Calcular proficiência específica para esta disciplina
                    if len(disciplina_questions) > 0:
                        # Obter nome do curso
                        course_name = _obter_nome_curso(test)
                        
                        proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions),
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        proficiencias_aluno.append(proficiency_disciplina)
                
                # Média das proficiências específicas
                if proficiencias_aluno:
                    media_proficiencia_aluno = sum(proficiencias_aluno) / len(proficiencias_aluno)
                    
                    # Determinar classificação geral baseada na média das proficiências
                    from app.services.evaluation_calculator import EvaluationCalculator
                    course_name = _obter_nome_curso(test)
                    
                    classification_geral = EvaluationCalculator.determine_classification(
                        proficiency=media_proficiencia_aluno,
                        course_name=course_name,
                        subject_name="GERAL"
                    )
                    
                    if classification_geral in dados_gerais_por_turma[turma_nome]:
                        dados_gerais_por_turma[turma_nome][classification_geral] += 1
                    dados_gerais_por_turma[turma_nome]["total"] += 1
                    dados_gerais_total[classification_geral] += 1
                dados_gerais_total["total"] += 1
    
    # Organizar resultado final agregando turmas com mesmo nome
    resultado_final = {}
    for disciplina, dados in disciplinas_resultado.items():
        # Agregar turmas com mesmo nome
        turmas_agregadas = defaultdict(lambda: {
            "abaixo_do_basico": 0,
            "basico": 0,
            "adequado": 0,
            "avancado": 0,
            "total": 0
        })

        for turma_data in dados["por_turma"]:
            turma_nome = turma_data["turma"]
            turmas_agregadas[turma_nome]["abaixo_do_basico"] += turma_data["abaixo_do_basico"]
            turmas_agregadas[turma_nome]["basico"] += turma_data["basico"]
            turmas_agregadas[turma_nome]["adequado"] += turma_data["adequado"]
            turmas_agregadas[turma_nome]["avancado"] += turma_data["avancado"]
            turmas_agregadas[turma_nome]["total"] += turma_data["total"]

        # Converter para lista ordenada
        por_turma_lista = []
        for turma_nome in sorted(turmas_agregadas.keys()):
            dados_turma = turmas_agregadas[turma_nome]
            por_turma_lista.append({
                "turma": turma_nome,
                "abaixo_do_basico": dados_turma["abaixo_do_basico"],
                "basico": dados_turma["basico"],
                "adequado": dados_turma["adequado"],
                "avancado": dados_turma["avancado"],
                "total": dados_turma["total"]
            })

        resultado_final[disciplina] = {
            "por_turma": por_turma_lista,
            "geral": {
                "abaixo_do_basico": dados["geral"]["Abaixo do Básico"],
                "basico": dados["geral"]["Básico"],
                "adequado": dados["geral"]["Adequado"],
                "avancado": dados["geral"]["Avançado"],
                "total": dados["geral"]["total"]
            }
        }
    
    # Adicionar dados gerais que englobam todas as disciplinas
    # Garantir que TODAS as turmas sejam incluídas, mesmo que com valores zerados
    dados_gerais_por_turma_lista = []

    # Obter lista de TODAS as turmas de class_tests, não apenas as que têm dados
    todas_turmas = set()
    for class_test in class_tests:
        turma_obj = Class.query.get(class_test.class_id)
        if turma_obj:
            todas_turmas.add(turma_obj.name)

    # Criar entrada para cada turma, mesmo que não tenha dados gerais
    for turma_nome in sorted(todas_turmas):
        if turma_nome in dados_gerais_por_turma:
            dados = dados_gerais_por_turma[turma_nome]
            dados_gerais_por_turma_lista.append({
                "turma": turma_nome,
                "abaixo_do_basico": dados["Abaixo do Básico"],
                "basico": dados["Básico"],
                "adequado": dados["Adequado"],
                "avancado": dados["Avançado"],
                "total": dados["total"]
            })
        else:
            # Turma sem dados gerais - adicionar com zeros
            dados_gerais_por_turma_lista.append({
                "turma": turma_nome,
                "abaixo_do_basico": 0,
                "basico": 0,
                "adequado": 0,
                "avancado": 0,
                "total": 0
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
    
    # Ordenar disciplinas pela ordem de aparição na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    resultado_ordenado = OrderedDict()
    
    # Adicionar disciplinas na ordem de aparição
    for disciplina in ordem_disciplinas:
        if disciplina in resultado_final:
            resultado_ordenado[disciplina] = resultado_final[disciplina]
    
    # Adicionar disciplinas que não estão na ordem (caso existam)
    for disciplina, dados in resultado_final.items():
        if disciplina not in resultado_ordenado and disciplina != "GERAL":
            resultado_ordenado[disciplina] = dados
    
    # Adicionar "GERAL" sempre por último
    if "GERAL" in resultado_final:
        resultado_ordenado["GERAL"] = resultado_final["GERAL"]
    
    return resultado_ordenado


def _calcular_proficiencia_por_escopo(evaluation_id: str, class_tests: List[ClassTest], scope_type: str) -> Dict[str, Any]:
    """
    Calcula proficiência por escopo (turma, escola ou município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
        scope_type: Tipo de escopo ('school', 'city', 'all')
    
    Returns:
        Dict com proficiência agrupada conforme o escopo
    """
    if scope_type == 'city' or scope_type == 'all':
        return _calcular_proficiencia_por_municipio(evaluation_id, class_tests)
    else:
        return _calcular_proficiencia(evaluation_id, class_tests)


def _calcular_proficiencia_por_municipio(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """
    Calcula proficiência agrupada por escola (para relatório por município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
    
    Returns:
        Dict com proficiência agrupada por escola
    """
    from app.models.skill import Skill
    from app.services.evaluation_calculator import EvaluationCalculator
    
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
    disciplinas_identificadas = set()
    
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                    disciplinas_identificadas.add(subject.name)
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
                disciplinas_identificadas.add(test.subject_rel.name)
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")

    # Buscar resultados da avaliação
    from sqlalchemy.orm import joinedload as jl
    evaluation_results = EvaluationResult.query.options(
        jl(EvaluationResult.student),
        jl(EvaluationResult.student, Student.class_)
        # ❌ REMOVIDO: jl(EvaluationResult.student, Student.class_, Class.school) - Class.school é property
    ).filter_by(test_id=evaluation_id).all()

    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()

    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)

    # Agrupar por escola
    class_ids = [ct.class_id for ct in class_tests]
    results_by_school = defaultdict(list)

    for result in evaluation_results:
        if result.student.class_id in class_ids and result.student.class_ and result.student.class_.school:
            school_id = result.student.class_.school.id
            results_by_school[school_id].append(result)

    # Agrupar resultados por turma dentro de cada escola
    results_by_class = defaultdict(list)
    for result in evaluation_results:
        if result.student.class_id in class_ids:
            results_by_class[result.student.class_id].append(result)

    # Obter nome do curso
    course_name = _obter_nome_curso(test)

    # Calcular proficiência por escola e disciplina
    # Obter ordem das disciplinas conforme aparecem na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    disciplinas_para_processar = ordem_disciplinas if ordem_disciplinas else list(disciplinas_identificadas)
    
    proficiencia_por_disciplina = {}
    
    for disciplina in disciplinas_para_processar:
        proficiencia_por_disciplina[disciplina] = {
            'por_escola': [],
            'media_geral': 0.0
        }
        
        total_proficiencia = 0.0
        total_escolas = 0
        
        for school_id, school_results in results_by_school.items():
            if not school_results:
                continue
            
            # Obter nome da escola
            escola_nome = "Escola Desconhecida"
            if school_results and school_results[0].student.class_ and school_results[0].student.class_.school:
                escola_nome = school_results[0].student.class_.school.name
            
            # Buscar turmas desta escola
            turmas_da_escola = []
            for result in school_results:
                if result.student.class_id not in turmas_da_escola:
                    turmas_da_escola.append(result.student.class_id)
            
            # Calcular proficiência por turma e depois média das turmas
            proficiencias_turmas = []
            total_alunos = 0

            for turma_id in turmas_da_escola:
                turma_results = results_by_class[turma_id]
                if turma_results:
                    # Calcular proficiência média da turma para esta disciplina específica
                    proficiencias_alunos_turma = []
                    for result in turma_results:
                        student_id = result.student_id
                        # Calcular proficiência específica desta disciplina para este aluno
                        if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                            disciplina_answers = student_discipline_results[student_id][disciplina]
                            disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]

                            # Calcular acertos específicos para esta disciplina
                            correct_answers_disciplina = 0
                            for answer in disciplina_answers:
                                question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                                if question:
                                    if question.question_type == 'multiple_choice':
                                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                        if is_correct:
                                            correct_answers_disciplina += 1
                                    elif question.correct_answer:
                                        if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                            correct_answers_disciplina += 1

                            # Calcular proficiência específica para esta disciplina
                            if len(disciplina_questions) > 0:
                                proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                                    correct_answers=correct_answers_disciplina,
                                    total_questions=len(disciplina_questions),
                                    course_name=course_name,
                                    subject_name=disciplina
                                )
                                proficiencias_alunos_turma.append(proficiency_disciplina)
                                total_alunos += 1

                    if proficiencias_alunos_turma:
                        media_turma = sum(proficiencias_alunos_turma) / len(proficiencias_alunos_turma)
                        proficiencias_turmas.append(media_turma)
            
            # Calcular média das turmas da escola
            if proficiencias_turmas:
                media_escola = sum(proficiencias_turmas) / len(proficiencias_turmas)
            else:
                media_escola = 0.0
            
            proficiencia_por_disciplina[disciplina]['por_escola'].append({
                'escola': escola_nome,
                'proficiencia': round(media_escola, 2),
                'total_alunos': total_alunos
            })
            
            total_proficiencia += media_escola
            total_escolas += 1
        
        # Calcular média geral
        if total_escolas > 0:
            proficiencia_por_disciplina[disciplina]['media_geral'] = round(total_proficiencia / total_escolas, 2)
    
    # Adicionar seção GERAL que engloba todas as disciplinas
    dados_gerais_por_escola_lista = []
    for disciplina, dados in proficiencia_por_disciplina.items():
        for escola_data in dados['por_escola']:
            escola_nome = escola_data['escola']
            
            # Buscar ou criar entrada para esta escola nos dados gerais
            escola_existente = next((item for item in dados_gerais_por_escola_lista if item['escola'] == escola_nome), None)
            if not escola_existente:
                escola_existente = {
                    'escola': escola_nome,
                    'proficiencia': 0,
                    'total_alunos': 0
                }
                dados_gerais_por_escola_lista.append(escola_existente)
            
            # Somar a proficiência desta disciplina para esta escola
            escola_existente['proficiencia'] += escola_data.get('proficiencia', escola_data.get('media', 0))
            escola_existente['total_alunos'] += escola_data['total_alunos']
    
    # Calcular média geral por escola
    for escola_data in dados_gerais_por_escola_lista:
        if escola_data['total_alunos'] > 0:
            escola_data['proficiencia'] = round(escola_data['proficiencia'] / len(proficiencia_por_disciplina), 2)
    
    # Adicionar seção GERAL
    proficiencia_por_disciplina["GERAL"] = {
        "por_escola": dados_gerais_por_escola_lista,
        "media_geral": round(sum(item['proficiencia'] for item in dados_gerais_por_escola_lista) / len(dados_gerais_por_escola_lista), 2) if dados_gerais_por_escola_lista else 0
    }
    
    # Ordenar disciplinas pela ordem de aparição na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    resultado_ordenado = OrderedDict()
    
    # Adicionar disciplinas na ordem de aparição
    for disciplina in ordem_disciplinas:
        if disciplina in proficiencia_por_disciplina:
            resultado_ordenado[disciplina] = proficiencia_por_disciplina[disciplina]
    
    # Adicionar disciplinas que não estão na ordem (caso existam)
    for disciplina, dados in proficiencia_por_disciplina.items():
        if disciplina not in resultado_ordenado and disciplina != "GERAL":
            resultado_ordenado[disciplina] = dados
    
    # Adicionar "GERAL" sempre por último
    if "GERAL" in proficiencia_por_disciplina:
        resultado_ordenado["GERAL"] = proficiencia_por_disciplina["GERAL"]
    
    return {
        'por_disciplina': resultado_ordenado
    }


def _calcular_proficiencia(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula proficiência por turma e disciplina"""
    from app.models.skill import Skill
    from app.services.evaluation_calculator import EvaluationCalculator

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
                else:
                    question_disciplines[question.id] = "Disciplina Geral"
                    disciplinas_identificadas.add("Disciplina Geral")
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")

        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
                disciplinas_identificadas.add(test.subject_rel.name)
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")

    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    
    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)
    
    # Buscar resultados da avaliação para obter dados dos alunos
    evaluation_results = EvaluationResult.query.options(
        joinedload(EvaluationResult.student).joinedload(Student.class_)
    ).filter_by(test_id=evaluation_id).all()
    
    # Agrupar por turma
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
    
    # Obter informações do curso para cálculo
    course_name = _obter_nome_curso(test)
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_results = results_by_class[class_id]
        
        # Obter nome da turma (mesmo se não houver resultados)
        turma_nome = "Turma Desconhecida"
        
        # Tentar obter nome da turma de diferentes formas
        if class_results and class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        else:
            # Se não há resultados, buscar nome da turma diretamente
            turma_obj = Class.query.get(class_id)
            if turma_obj:
                turma_nome = turma_obj.name
        
        # Para cada disciplina, calcular proficiência específica
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        # Se não há disciplinas encontradas nesta turma, usar todas as disciplinas identificadas
        # (para incluir turmas sem resultados, mostrando zeros)
        if not disciplinas_turma:
            disciplinas_turma = disciplinas_identificadas
            logging.info(f"Turma {turma_nome} não tem resultados - usando todas as disciplinas disponíveis")
        
        for disciplina in disciplinas_turma:
            # Calcular proficiência específica para esta disciplina e turma
            proficiencias_disciplina = []
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Calcular proficiência específica para esta disciplina
                    disciplina_answers = student_discipline_results[student_id][disciplina]
                    disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]
                    
                    # Calcular acertos específicos para esta disciplina
                    correct_answers_disciplina = 0
                    for answer in disciplina_answers:
                        question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                        if question:
                            if question.question_type == 'multiple_choice':
                                is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                if is_correct:
                                    correct_answers_disciplina += 1
                            elif question.correct_answer:
                                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                    correct_answers_disciplina += 1
                    
                    # Calcular proficiência específica para esta disciplina
                    if len(disciplina_questions) > 0:
                        proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions),
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        proficiencias_disciplina.append(proficiency_disciplina)
            
            if proficiencias_disciplina:
                media_proficiencia = sum(proficiencias_disciplina) / len(proficiencias_disciplina)
                disciplinas_proficiencia[disciplina]["total_proficiencia"] += sum(proficiencias_disciplina)
                disciplinas_proficiencia[disciplina]["total_alunos"] += len(proficiencias_disciplina)
                
                disciplinas_proficiencia[disciplina]["por_turma"].append({
                    "turma": turma_nome,
                    "proficiencia": round(media_proficiencia, 2)
                })
        
        # Calcular dados gerais para esta turma (média das disciplinas específicas)
        proficiencias_gerais_turma = []
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                # Calcular média das proficiências específicas por disciplina para este aluno
                proficiencias_aluno = []
                for disciplina in student_discipline_results[student_id].keys():
                    disciplina_answers = student_discipline_results[student_id][disciplina]
                    disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]
                    
                    # Calcular acertos específicos para esta disciplina
                    correct_answers_disciplina = 0
                    for answer in disciplina_answers:
                        question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                        if question:
                            if question.question_type == 'multiple_choice':
                                is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                if is_correct:
                                    correct_answers_disciplina += 1
                            elif question.correct_answer:
                                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                    correct_answers_disciplina += 1
                    
                    # Calcular proficiência específica para esta disciplina
                    if len(disciplina_questions) > 0:
                        proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions),
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        proficiencias_aluno.append(proficiency_disciplina)
                
                # Média das proficiências específicas
                if proficiencias_aluno:
                    media_proficiencia_aluno = sum(proficiencias_aluno) / len(proficiencias_aluno)
                    proficiencias_gerais_turma.append(media_proficiencia_aluno)
        
        if proficiencias_gerais_turma:
            media_proficiencia_geral_turma = sum(proficiencias_gerais_turma) / len(proficiencias_gerais_turma)
            dados_gerais_por_turma[turma_nome].append({
                "turma": turma_nome,
                "proficiencia": round(media_proficiencia_geral_turma, 2)
            })
            dados_gerais_total_proficiencia += sum(proficiencias_gerais_turma)
            dados_gerais_total_alunos += len(proficiencias_gerais_turma)
    
    # Obter lista de TODAS as turmas de class_tests PRIMEIRO
    todas_turmas_prof = set()
    for class_test in class_tests:
        turma_obj = Class.query.get(class_test.class_id)
        if turma_obj:
            todas_turmas_prof.add(turma_obj.name)

    # Organizar resultado final
    resultado_final = {}
    for disciplina, dados in disciplinas_proficiencia.items():
        media_geral_disciplina = dados["total_proficiencia"] / dados["total_alunos"] if dados["total_alunos"] > 0 else 0

        # Agregar turmas com mesmo nome (somando proficiências e contando alunos)
        turmas_agregadas = defaultdict(lambda: {"total_proficiencia": 0, "total_alunos": 0})
        for t in dados["por_turma"]:
            turma_nome = t["turma"]
            proficiencia = t["proficiencia"]
            # Assumindo que cada entrada representa a média de alunos, precisamos pesar igualmente
            # Na verdade, precisamos acumular as proficiências e recalcular a média
            turmas_agregadas[turma_nome]["total_proficiencia"] += proficiencia
            turmas_agregadas[turma_nome]["total_alunos"] += 1  # Conta quantas vezes esta turma apareceu

        # Garantir que TODAS as turmas apareçam, mesmo sem dados
        turmas_disciplina_lista = []
        for turma_nome in sorted(todas_turmas_prof):
            if turma_nome in turmas_agregadas:
                dados_turma = turmas_agregadas[turma_nome]
                # Média das proficiências agregadas
                media_prof = dados_turma["total_proficiencia"] / dados_turma["total_alunos"] if dados_turma["total_alunos"] > 0 else 0
                turmas_disciplina_lista.append({
                    "turma": turma_nome,
                    "proficiencia": round(media_prof, 2)
                })
            else:
                turmas_disciplina_lista.append({
                    "turma": turma_nome,
                    "proficiencia": 0
                })

        resultado_final[disciplina] = {
            "por_turma": turmas_disciplina_lista,
            "media_geral": round(media_geral_disciplina, 2)
        }

    # Adicionar dados gerais que englobam todas as disciplinas
    # Garantir que TODAS as turmas sejam incluídas, mesmo que com valores zerados
    media_geral_total = dados_gerais_total_proficiencia / dados_gerais_total_alunos if dados_gerais_total_alunos > 0 else 0

    # Agregar dados gerais por nome de turma
    turmas_gerais_agregadas = defaultdict(lambda: {"total_proficiencia": 0, "total_ocorrencias": 0})
    for dados_list in dados_gerais_por_turma.values():
        for dados in dados_list:
            turma_nome = dados["turma"]
            turmas_gerais_agregadas[turma_nome]["total_proficiencia"] += dados["proficiencia"]
            turmas_gerais_agregadas[turma_nome]["total_ocorrencias"] += 1

    # Criar entrada para cada turma, mesmo que não tenha dados gerais
    dados_gerais_lista = []
    for turma_nome in sorted(todas_turmas_prof):
        if turma_nome in turmas_gerais_agregadas:
            dados_turma = turmas_gerais_agregadas[turma_nome]
            media_prof = dados_turma["total_proficiencia"] / dados_turma["total_ocorrencias"] if dados_turma["total_ocorrencias"] > 0 else 0
            dados_gerais_lista.append({
                "turma": turma_nome,
                "proficiencia": round(media_prof, 2)
            })
        else:
            dados_gerais_lista.append({
                "turma": turma_nome,
                "proficiencia": 0
            })

    resultado_final["GERAL"] = {
        "por_turma": dados_gerais_lista,
        "media_geral": round(media_geral_total, 2)
    }

    # Calcular média municipal por disciplina
    media_municipal_por_disciplina = _calcular_media_municipal_por_disciplina(evaluation_id, question_disciplines)

    # Ordenar disciplinas pela ordem de aparição na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    resultado_ordenado = OrderedDict()
    
    # Adicionar disciplinas na ordem de aparição
    for disciplina in ordem_disciplinas:
        if disciplina in resultado_final:
            resultado_ordenado[disciplina] = resultado_final[disciplina]
    
    # Adicionar disciplinas que não estão na ordem (caso existam)
    for disciplina, dados in resultado_final.items():
        if disciplina not in resultado_ordenado and disciplina != "GERAL":
            resultado_ordenado[disciplina] = dados
    
    # Adicionar "GERAL" sempre por último
    if "GERAL" in resultado_final:
        resultado_ordenado["GERAL"] = resultado_final["GERAL"]

    return {
        "por_disciplina": resultado_ordenado,
        "media_municipal_por_disciplina": media_municipal_por_disciplina
    }


def _calcular_nota_geral_por_escopo(evaluation_id: str, class_tests: List[ClassTest], scope_type: str) -> Dict[str, Any]:
    """
    Calcula nota geral por escopo (turma, escola ou município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
        scope_type: Tipo de escopo ('school', 'city', 'all')
    
    Returns:
        Dict com nota geral agrupada conforme o escopo
    """
    if scope_type == 'city' or scope_type == 'all':
        return _calcular_nota_geral_por_municipio(evaluation_id, class_tests)
    else:
        return _calcular_nota_geral(evaluation_id, class_tests)


def _calcular_nota_geral_por_municipio(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """
    Calcula nota geral agrupada por escola (para relatório por município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
    
    Returns:
        Dict com nota geral agrupada por escola
    """
    from app.models.skill import Skill
    from app.services.evaluation_calculator import EvaluationCalculator
    
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
    disciplinas_identificadas = set()
    
    for question in test.questions:
        if question.skill and question.skill.strip() and question.skill != '{}':
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            if skill_obj and skill_obj.subject_id:
                subject = Subject.query.get(skill_obj.subject_id)
                if subject:
                    question_disciplines[question.id] = subject.name
                    disciplinas_identificadas.add(subject.name)
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
                disciplinas_identificadas.add(test.subject_rel.name)
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
    
    # Buscar resultados da avaliação
    from sqlalchemy.orm import joinedload as jl
    evaluation_results = EvaluationResult.query.options(
        jl(EvaluationResult.student),
        jl(EvaluationResult.student, Student.class_)
        # ❌ REMOVIDO: jl(EvaluationResult.student, Student.class_, Class.school) - Class.school é property
    ).filter_by(test_id=evaluation_id).all()

    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()

    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)

    # Agrupar por escola
    class_ids = [ct.class_id for ct in class_tests]
    results_by_school = defaultdict(list)

    for result in evaluation_results:
        if result.student.class_id in class_ids and result.student.class_ and result.student.class_.school:
            school_id = result.student.class_.school.id
            results_by_school[school_id].append(result)

    # Agrupar resultados por turma dentro de cada escola
    results_by_class = defaultdict(list)
    for result in evaluation_results:
        if result.student.class_id in class_ids:
            results_by_class[result.student.class_id].append(result)

    # Obter informações para cálculo
    course_name = _obter_nome_curso(test)
    use_simple_calculation = test.grade_calculation_type == 'simple'

    # Calcular nota geral por escola e disciplina
    # Obter ordem das disciplinas conforme aparecem na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    disciplinas_para_processar = ordem_disciplinas if ordem_disciplinas else list(disciplinas_identificadas)
    
    nota_por_disciplina = {}
    
    for disciplina in disciplinas_para_processar:
        nota_por_disciplina[disciplina] = {
            'por_escola': [],
            'media_geral': 0.0
        }
        
        total_nota = 0.0
        total_escolas = 0
        
        for school_id, school_results in results_by_school.items():
            if not school_results:
                continue
            
            # Obter nome da escola
            escola_nome = "Escola Desconhecida"
            if school_results and school_results[0].student.class_ and school_results[0].student.class_.school:
                escola_nome = school_results[0].student.class_.school.name
            
            # Buscar turmas desta escola
            turmas_da_escola = []
            for result in school_results:
                if result.student.class_id not in turmas_da_escola:
                    turmas_da_escola.append(result.student.class_id)
            
            # Calcular nota por turma e depois SOMAR as turmas
            soma_notas_turmas = 0.0
            total_alunos = 0

            for turma_id in turmas_da_escola:
                turma_results = results_by_class[turma_id]
                if turma_results:
                    # Calcular nota média da turma para esta disciplina específica
                    notas_alunos_turma = []
                    for result in turma_results:
                        student_id = result.student_id
                        # Calcular nota específica desta disciplina para este aluno
                        if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                            disciplina_answers = student_discipline_results[student_id][disciplina]
                            disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]

                            # Calcular acertos específicos para esta disciplina
                            correct_answers_disciplina = 0
                            for answer in disciplina_answers:
                                question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                                if question:
                                    if question.question_type == 'multiple_choice':
                                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                        if is_correct:
                                            correct_answers_disciplina += 1
                                    elif question.correct_answer:
                                        if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                            correct_answers_disciplina += 1

                            # Calcular nota específica para esta disciplina
                            if len(disciplina_questions) > 0:
                                proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                                    correct_answers=correct_answers_disciplina,
                                    total_questions=len(disciplina_questions),
                                    course_name=course_name,
                                    subject_name=disciplina
                                )
                                grade_disciplina = EvaluationCalculator.calculate_grade(
                                    proficiency=proficiency_disciplina,
                                    course_name=course_name,
                                    subject_name=disciplina,
                                    use_simple_calculation=use_simple_calculation,
                                    correct_answers=correct_answers_disciplina,
                                    total_questions=len(disciplina_questions)
                                )
                                notas_alunos_turma.append(grade_disciplina)
                                total_alunos += 1

                    if notas_alunos_turma:
                        media_turma = sum(notas_alunos_turma) / len(notas_alunos_turma)
                        soma_notas_turmas += media_turma  # Somar as médias das turmas para depois calcular a média geral

            # A nota da escola é a média das notas das turmas (não a soma)
            if len(turmas_da_escola) > 0 and soma_notas_turmas > 0:
                nota_escola = soma_notas_turmas / len(turmas_da_escola)
            else:
                nota_escola = 0.0
            
            nota_por_disciplina[disciplina]['por_escola'].append({
                'escola': escola_nome,
                'nota': round(nota_escola, 2),
                'total_alunos': total_alunos
            })
            
            total_nota += nota_escola
            total_escolas += 1
        
        # Calcular média geral
        if total_escolas > 0:
            nota_por_disciplina[disciplina]['media_geral'] = round(total_nota / total_escolas, 2)
    
    # Adicionar seção GERAL que engloba todas as disciplinas
    dados_gerais_por_escola_lista = []
    for disciplina, dados in nota_por_disciplina.items():
        for escola_data in dados['por_escola']:
            escola_nome = escola_data['escola']
            
            # Buscar ou criar entrada para esta escola nos dados gerais
            escola_existente = next((item for item in dados_gerais_por_escola_lista if item['escola'] == escola_nome), None)
            if not escola_existente:
                escola_existente = {
                    'escola': escola_nome,
                    'nota': 0,
                    'total_alunos': 0
                }
                dados_gerais_por_escola_lista.append(escola_existente)
            
            # Somar a nota desta disciplina para esta escola
            escola_existente['nota'] += escola_data.get('nota', escola_data.get('media', 0))
            escola_existente['total_alunos'] += escola_data['total_alunos']
    
    # Calcular média geral por escola
    for escola_data in dados_gerais_por_escola_lista:
        if escola_data['total_alunos'] > 0:
            escola_data['nota'] = round(escola_data['nota'] / len(nota_por_disciplina), 2)
    
    # Adicionar seção GERAL
    nota_por_disciplina["GERAL"] = {
        "por_escola": dados_gerais_por_escola_lista,
        "media_geral": round(sum(item['nota'] for item in dados_gerais_por_escola_lista) / len(dados_gerais_por_escola_lista), 2) if dados_gerais_por_escola_lista else 0
    }
    
    # Ordenar disciplinas pela ordem de aparição na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    resultado_ordenado = OrderedDict()
    
    # Adicionar disciplinas na ordem de aparição
    for disciplina in ordem_disciplinas:
        if disciplina in nota_por_disciplina:
            resultado_ordenado[disciplina] = nota_por_disciplina[disciplina]
    
    # Adicionar disciplinas que não estão na ordem (caso existam)
    for disciplina, dados in nota_por_disciplina.items():
        if disciplina not in resultado_ordenado and disciplina != "GERAL":
            resultado_ordenado[disciplina] = dados
    
    # Adicionar "GERAL" sempre por último
    if "GERAL" in nota_por_disciplina:
        resultado_ordenado["GERAL"] = nota_por_disciplina["GERAL"]
    
    return {
        'por_disciplina': resultado_ordenado
    }


def _calcular_nota_geral(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula nota geral por turma e disciplina"""
    from app.models.skill import Skill
    from app.services.evaluation_calculator import EvaluationCalculator
    
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
                else:
                    question_disciplines[question.id] = "Disciplina Geral"
                    disciplinas_identificadas.add("Disciplina Geral")
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
        
        # Questões sem skill: mapear para disciplina principal da avaliação
        else:
            if test.subject_rel:
                question_disciplines[question.id] = test.subject_rel.name
                disciplinas_identificadas.add(test.subject_rel.name)
            else:
                question_disciplines[question.id] = "Disciplina Geral"
                disciplinas_identificadas.add("Disciplina Geral")
    
    # Buscar respostas dos alunos
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
    
    # Agrupar respostas por aluno e disciplina
    student_discipline_results = defaultdict(lambda: defaultdict(list))
    
    for answer in student_answers:
        if answer.question_id in question_disciplines:
            disciplina = question_disciplines[answer.question_id]
            student_discipline_results[answer.student_id][disciplina].append(answer)
    
    # Buscar resultados da avaliação para obter dados dos alunos
    evaluation_results = EvaluationResult.query.options(
        joinedload(EvaluationResult.student).joinedload(Student.class_)
    ).filter_by(test_id=evaluation_id).all()
    
    # Agrupar por turma
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
    
    # Obter informações do curso para cálculo
    course_name = _obter_nome_curso(test)
    use_simple_calculation = test.grade_calculation_type == 'simple'
    
    for class_test in class_tests:
        class_id = class_test.class_id
        class_results = results_by_class[class_id]
        
        # Obter nome da turma (mesmo se não houver resultados)
        turma_nome = "Turma Desconhecida"
        
        # Tentar obter nome da turma de diferentes formas
        if class_results and class_results[0].student and class_results[0].student.class_:
            turma_nome = class_results[0].student.class_.name
        else:
            # Se não há resultados, buscar nome da turma diretamente
            turma_obj = Class.query.get(class_id)
            if turma_obj:
                turma_nome = turma_obj.name
        
        # Para cada disciplina, calcular nota específica
        disciplinas_turma = set()
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                disciplinas_turma.update(student_discipline_results[student_id].keys())
        
        # Se não há disciplinas encontradas nesta turma, usar todas as disciplinas identificadas
        # (para incluir turmas sem resultados, mostrando zeros)
        if not disciplinas_turma:
            disciplinas_turma = disciplinas_identificadas
            logging.info(f"Turma {turma_nome} não tem resultados - usando todas as disciplinas disponíveis")
        
        for disciplina in disciplinas_turma:
            # Calcular nota específica para esta disciplina e turma
            notas_disciplina = []
            
            for result in class_results:
                student_id = result.student_id
                if student_id in student_discipline_results and disciplina in student_discipline_results[student_id]:
                    # Calcular nota específica para esta disciplina
                    disciplina_answers = student_discipline_results[student_id][disciplina]
                    disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]
                    
                    # Calcular acertos específicos para esta disciplina
                    correct_answers_disciplina = 0
                    for answer in disciplina_answers:
                        question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                        if question:
                            if question.question_type == 'multiple_choice':
                                is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                if is_correct:
                                    correct_answers_disciplina += 1
                            elif question.correct_answer:
                                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                    correct_answers_disciplina += 1
                    
                    # Calcular proficiência específica para esta disciplina
                    if len(disciplina_questions) > 0:
                        proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions),
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        
                        # Calcular nota específica para esta disciplina
                        grade_disciplina = EvaluationCalculator.calculate_grade(
                            proficiency=proficiency_disciplina,
                            course_name=course_name,
                            subject_name=disciplina,
                            use_simple_calculation=use_simple_calculation,
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions)
                        )
                        
                        notas_disciplina.append(grade_disciplina)
            
            if notas_disciplina:
                media_nota = sum(notas_disciplina) / len(notas_disciplina)
                disciplinas_notas[disciplina]["total_notas"] += sum(notas_disciplina)
                disciplinas_notas[disciplina]["total_alunos"] += len(notas_disciplina)
                
                disciplinas_notas[disciplina]["por_turma"].append({
                    "turma": turma_nome,
                    "nota": round(media_nota, 2)
                })
        
        # Calcular dados gerais para esta turma (média das disciplinas específicas)
        notas_gerais_turma = []
        for result in class_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                # Calcular média das notas específicas por disciplina para este aluno
                notas_aluno = []
                for disciplina in student_discipline_results[student_id].keys():
                    disciplina_answers = student_discipline_results[student_id][disciplina]
                    disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]
                    
                    # Calcular acertos específicos para esta disciplina
                    correct_answers_disciplina = 0
                    for answer in disciplina_answers:
                        question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                        if question:
                            if question.question_type == 'multiple_choice':
                                is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                if is_correct:
                                    correct_answers_disciplina += 1
                            elif question.correct_answer:
                                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                    correct_answers_disciplina += 1
                    
                    # Calcular proficiência específica para esta disciplina
                    if len(disciplina_questions) > 0:
                        proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions),
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        
                        # Calcular nota específica para esta disciplina
                        grade_disciplina = EvaluationCalculator.calculate_grade(
                            proficiency=proficiency_disciplina,
                            course_name=course_name,
                            subject_name=disciplina,
                            use_simple_calculation=use_simple_calculation,
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions)
                        )
                        
                        notas_aluno.append(grade_disciplina)
                
                # Média das notas específicas
                if notas_aluno:
                    media_nota_aluno = sum(notas_aluno) / len(notas_aluno)
                    notas_gerais_turma.append(media_nota_aluno)
        
        if notas_gerais_turma:
            media_nota_geral_turma = sum(notas_gerais_turma) / len(notas_gerais_turma)
            dados_gerais_por_turma[turma_nome].append({
                "turma": turma_nome,
                "nota": round(media_nota_geral_turma, 2)
            })
            dados_gerais_total_notas += sum(notas_gerais_turma)
            dados_gerais_total_alunos += len(notas_gerais_turma)
    
    # Obter lista de TODAS as turmas de class_tests PRIMEIRO
    todas_turmas_nota = set()
    for class_test in class_tests:
        turma_obj = Class.query.get(class_test.class_id)
        if turma_obj:
            todas_turmas_nota.add(turma_obj.name)

    # Organizar resultado final
    resultado_final = {}
    for disciplina, dados in disciplinas_notas.items():
        media_geral_disciplina = dados["total_notas"] / dados["total_alunos"] if dados["total_alunos"] > 0 else 0

        # Agregar turmas com mesmo nome (somando notas e contando alunos)
        turmas_agregadas = defaultdict(lambda: {"total_notas": 0, "total_alunos": 0})
        for t in dados["por_turma"]:
            turma_nome = t["turma"]
            nota = t["nota"]
            turmas_agregadas[turma_nome]["total_notas"] += nota
            turmas_agregadas[turma_nome]["total_alunos"] += 1  # Conta quantas vezes esta turma apareceu

        # Garantir que TODAS as turmas apareçam, mesmo sem dados
        turmas_disciplina_lista = []
        for turma_nome in sorted(todas_turmas_nota):
            if turma_nome in turmas_agregadas:
                dados_turma = turmas_agregadas[turma_nome]
                # Média das notas agregadas
                media_nota = dados_turma["total_notas"] / dados_turma["total_alunos"] if dados_turma["total_alunos"] > 0 else 0
                turmas_disciplina_lista.append({
                    "turma": turma_nome,
                    "nota": round(media_nota, 2)
                })
            else:
                turmas_disciplina_lista.append({
                    "turma": turma_nome,
                    "nota": 0
                })

        resultado_final[disciplina] = {
            "por_turma": turmas_disciplina_lista,
            "media_geral": round(media_geral_disciplina, 2)
        }

    # Adicionar dados gerais que englobam todas as disciplinas
    # Garantir que TODAS as turmas sejam incluídas, mesmo que com valores zerados
    media_geral_total = dados_gerais_total_notas / dados_gerais_total_alunos if dados_gerais_total_alunos > 0 else 0

    # Agregar dados gerais por nome de turma
    turmas_gerais_agregadas = defaultdict(lambda: {"total_notas": 0, "total_ocorrencias": 0})
    for dados_list in dados_gerais_por_turma.values():
        for dados in dados_list:
            turma_nome = dados["turma"]
            turmas_gerais_agregadas[turma_nome]["total_notas"] += dados["nota"]
            turmas_gerais_agregadas[turma_nome]["total_ocorrencias"] += 1

    # Criar entrada para cada turma, mesmo que não tenha dados gerais
    dados_gerais_notas_lista = []
    for turma_nome in sorted(todas_turmas_nota):
        if turma_nome in turmas_gerais_agregadas:
            dados_turma = turmas_gerais_agregadas[turma_nome]
            media_nota = dados_turma["total_notas"] / dados_turma["total_ocorrencias"] if dados_turma["total_ocorrencias"] > 0 else 0
            dados_gerais_notas_lista.append({
                "turma": turma_nome,
                "nota": round(media_nota, 2)
            })
        else:
            dados_gerais_notas_lista.append({
                "turma": turma_nome,
                "nota": 0
            })

    resultado_final["GERAL"] = {
        "por_turma": dados_gerais_notas_lista,
        "media_geral": round(media_geral_total, 2)
    }

    # Calcular média municipal por disciplina
    media_municipal_por_disciplina = _calcular_media_municipal_nota_por_disciplina(evaluation_id, question_disciplines)

    # Ordenar disciplinas pela ordem de aparição na avaliação
    ordem_disciplinas = _obter_ordem_disciplinas_avaliacao(test)
    resultado_ordenado = OrderedDict()
    
    # Adicionar disciplinas na ordem de aparição
    for disciplina in ordem_disciplinas:
        if disciplina in resultado_final:
            resultado_ordenado[disciplina] = resultado_final[disciplina]
    
    # Adicionar disciplinas que não estão na ordem (caso existam)
    for disciplina, dados in resultado_final.items():
        if disciplina not in resultado_ordenado and disciplina != "GERAL":
            resultado_ordenado[disciplina] = dados
    
    # Adicionar "GERAL" sempre por último
    if "GERAL" in resultado_final:
        resultado_ordenado["GERAL"] = resultado_final["GERAL"]

    return {
        "por_disciplina": resultado_ordenado,
        "media_municipal_por_disciplina": media_municipal_por_disciplina
    }


def _calcular_acertos_habilidade_por_escopo(evaluation_id: str, class_tests: List[ClassTest], scope_type: str) -> Dict[str, Any]:
    """
    Calcula acertos por habilidade por escopo (turma, escola ou município)
    
    Args:
        evaluation_id: ID da avaliação
        class_tests: Lista de turmas onde a avaliação foi aplicada
        scope_type: Tipo de escopo ('school', 'city', 'all')
    
    Returns:
        Dict com acertos por habilidade agrupados conforme o escopo
    """
    if scope_type == 'city' or scope_type == 'all':
        return _calcular_acertos_habilidade_por_municipio(evaluation_id, class_tests)
    else:
        return _calcular_acertos_habilidade(evaluation_id)


def _calcular_acertos_habilidade_por_municipio(evaluation_id: str, class_tests: List[ClassTest]) -> Dict[str, Any]:
    """Calcula acertos por habilidade para relatório municipal (filtrado por turmas do município)"""
    from app.models.skill import Skill
    
    # Buscar questões da avaliação
    test = Test.query.get(evaluation_id)
    if not test or not test.questions:
        return {}
    
    # Filtrar respostas apenas das turmas do município
    class_ids = [ct.class_id for ct in class_tests]
    student_answers = StudentAnswer.query.filter_by(test_id=evaluation_id).join(Student).filter(Student.class_id.in_(class_ids)).all()
    
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
    
    # Lista para manter a ordem original das questões conforme aparecem na avaliação
    questoes_ordenadas = []
    
    # Processar questões na ordem original (test.questions já está ordenado)
    for idx, question in enumerate(test.questions, start=1):
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            # Remover chaves {} do UUID se existirem
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            # Se não encontrou a habilidade na tabela Skill, usar o ID como código
            if not skill_obj:
                skill_code = clean_skill_id
                skill_description = f"Habilidade {clean_skill_id}"
                disciplina = "Disciplina Geral"
            else:
                skill_code = skill_obj.code
                skill_description = skill_obj.description if hasattr(skill_obj, 'description') and skill_obj.description else f"Habilidade {skill_code}"
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
                skill_description = f"Questão {question.number or 'N/A'}"
            else:
                disciplina = "Disciplina Geral"
                skill_code = f"Questão {question.number or 'N/A'}"
                skill_description = f"Questão {question.number or 'N/A'}"
        
        answers = answers_by_question.get(question.id, [])
        
        total_respostas = len(answers)
        acertos = 0
        
        for answer in answers:
            # Verificar se a resposta está correta
            if question.question_type == 'multiple_choice':
                # Para múltipla escolha, verificar se a resposta está correta
                if question.correct_answer and str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                    acertos += 1
            else:
                # Para outros tipos, comparar com correct_answer
                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                    acertos += 1
        
        percentual = (acertos / total_respostas) * 100 if total_respostas > 0 else 0
        
        # Armazenar questão na ordem original
        questoes_ordenadas.append({
            "ordem_original": idx,  # Posição na avaliação (1, 2, 3, ...)
            "disciplina": disciplina,
            "codigo": skill_code,
            "descricao": skill_description,
            "acertos": acertos,
            "total": total_respostas,
            "percentual": round(percentual, 1)
        })
    
    # Agrupar por disciplina mantendo a ordem original das questões
    resultado_por_disciplina = {}
    disciplinas_ordem = []  # Lista para manter ordem de aparição das disciplinas
    
    for questao in questoes_ordenadas:
        disciplina = questao["disciplina"]
        
        # Se é a primeira vez que vemos esta disciplina, adicionar à lista de ordem
        if disciplina not in disciplinas_ordem:
            disciplinas_ordem.append(disciplina)
            resultado_por_disciplina[disciplina] = {
                "questoes": []
            }
        
        # Adicionar questão à disciplina (mantendo ordem original)
        resultado_por_disciplina[disciplina]["questoes"].append({
            "numero_questao": questao["ordem_original"],
            "codigo": questao["codigo"],
            "descricao": questao["descricao"],
            "acertos": questao["acertos"],
            "total": questao["total"],
            "percentual": questao["percentual"]
        })
    
    # Adicionar dados gerais que englobam todas as disciplinas (na ordem original)
    questoes_gerais = []
    for questao in questoes_ordenadas:
        questoes_gerais.append({
            "numero_questao": questao["ordem_original"],
            "codigo": questao["codigo"],
            "descricao": questao["descricao"],
            "acertos": questao["acertos"],
            "total": questao["total"],
            "percentual": questao["percentual"]
        })
    
    # Construir resultado final ordenado usando a ordem de aparição das disciplinas
    resultado_ordenado = OrderedDict()
    
    # Adicionar disciplinas na ordem de aparição
    for disciplina in disciplinas_ordem:
        resultado_ordenado[disciplina] = resultado_por_disciplina[disciplina]
    
    # Adicionar "GERAL" sempre por último
    resultado_ordenado["GERAL"] = {
        "questoes": questoes_gerais
    }
    
    return resultado_ordenado


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
    
    # Lista para manter a ordem original das questões conforme aparecem na avaliação
    questoes_ordenadas = []
    
    # Processar questões na ordem original (test.questions já está ordenado)
    for idx, question in enumerate(test.questions, start=1):
        # Questões com skill: mapear via skill.subject_id
        if question.skill and question.skill.strip() and question.skill != '{}':
            # Remover chaves {} do UUID se existirem
            clean_skill_id = question.skill.replace('{', '').replace('}', '')
            skill_obj = skills_dict.get(clean_skill_id)
            
            # Se não encontrou a habilidade na tabela Skill, usar o ID como código
            if not skill_obj:
                skill_code = clean_skill_id
                skill_description = f"Habilidade {clean_skill_id}"
                disciplina = "Disciplina Geral"
                logging.warning(f"Habilidade não encontrada na tabela Skill: {clean_skill_id}")
            else:
                skill_code = skill_obj.code
                skill_description = skill_obj.description if hasattr(skill_obj, 'description') and skill_obj.description else f"Habilidade {skill_code}"
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
                skill_description = f"Questão {question.number or 'N/A'}"
                logging.info(f"Questão {question.id} sem skill mapeada para disciplina principal: {test.subject_rel.name}")
            else:
                disciplina = "Disciplina Geral"
                skill_code = f"Questão {question.number or 'N/A'}"
                skill_description = f"Questão {question.number or 'N/A'}"
                logging.warning(f"Questão {question.id} sem skill e avaliação sem disciplina principal")
        
        answers = answers_by_question.get(question.id, [])
        
        total_respostas = len(answers)
        acertos = 0
        
        for answer in answers:
            # Verificar se a resposta está correta
            if question.question_type == 'multiple_choice':
                # Para múltipla escolha, verificar se a resposta está correta
                if question.correct_answer and str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                    acertos += 1
            else:
                # Para outros tipos, comparar com correct_answer
                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                    acertos += 1
        
        percentual = (acertos / total_respostas) * 100 if total_respostas > 0 else 0
        
        # Armazenar questão na ordem original
        questoes_ordenadas.append({
            "ordem_original": idx,  # Posição na avaliação (1, 2, 3, ...)
            "disciplina": disciplina,
            "codigo": skill_code,
            "descricao": skill_description,
            "acertos": acertos,
            "total": total_respostas,
            "percentual": round(percentual, 1)
        })
    
    # Agrupar por disciplina mantendo a ordem original das questões
    resultado_por_disciplina = {}
    disciplinas_ordem = []  # Lista para manter ordem de aparição das disciplinas
    
    for questao in questoes_ordenadas:
        disciplina = questao["disciplina"]
        
        # Se é a primeira vez que vemos esta disciplina, adicionar à lista de ordem
        if disciplina not in disciplinas_ordem:
            disciplinas_ordem.append(disciplina)
            resultado_por_disciplina[disciplina] = {
                "questoes": []
            }
        
        # Adicionar questão à disciplina (mantendo ordem original)
        resultado_por_disciplina[disciplina]["questoes"].append({
            "numero_questao": questao["ordem_original"],
            "codigo": questao["codigo"],
            "descricao": questao["descricao"],
            "acertos": questao["acertos"],
            "total": questao["total"],
            "percentual": questao["percentual"]
        })
    
    # Adicionar dados gerais que englobam todas as disciplinas (na ordem original)
    questoes_gerais = []
    for questao in questoes_ordenadas:
        questoes_gerais.append({
            "numero_questao": questao["ordem_original"],
            "codigo": questao["codigo"],
            "descricao": questao["descricao"],
            "acertos": questao["acertos"],
            "total": questao["total"],
            "percentual": questao["percentual"]
        })
    
    # Construir resultado final ordenado usando a ordem de aparição das disciplinas
    resultado_ordenado = OrderedDict()
    
    # Adicionar disciplinas na ordem de aparição
    for disciplina in disciplinas_ordem:
        resultado_ordenado[disciplina] = resultado_por_disciplina[disciplina]
    
    # Adicionar "GERAL" sempre por último
    resultado_ordenado["GERAL"] = {
        "questoes": questoes_gerais
    }
    
    return resultado_ordenado


def _calcular_media_municipal(evaluation_id: str) -> float:
    """Calcula média de proficiência municipal"""
    try:
        # Buscar a primeira escola para obter o município
        test = Test.query.get(evaluation_id)
        if not test:
            return 0.0
        
        # Buscar turmas da avaliação
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
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
            School, Class.school_id == cast(School.id, PostgresUUID)
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
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
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
            School, Class.school_id == cast(School.id, PostgresUUID)
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
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
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
            School, Class.school_id == cast(School.id, PostgresUUID)
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
        
        # Calcular média por disciplina (calculando proficiência específica de cada disciplina)
        from app.services.evaluation_calculator import EvaluationCalculator

        disciplinas_proficiencia = defaultdict(list)
        course_name = _obter_nome_curso(test)

        for result in municipal_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                # Calcular proficiência específica para cada disciplina
                for disciplina, answers in student_discipline_results[student_id].items():
                    # Buscar questões desta disciplina
                    disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]

                    # Calcular acertos específicos para esta disciplina
                    correct_answers_disciplina = 0
                    for answer in answers:
                        question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                        if question:
                            if question.question_type == 'multiple_choice':
                                is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                if is_correct:
                                    correct_answers_disciplina += 1
                            elif question.correct_answer:
                                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                    correct_answers_disciplina += 1

                    # Calcular proficiência específica para esta disciplina
                    if len(disciplina_questions) > 0:
                        proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions),
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        disciplinas_proficiencia[disciplina].append(proficiency_disciplina)

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
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
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
            School, Class.school_id == cast(School.id, PostgresUUID)
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
        
        # Calcular média por disciplina (calculando nota específica de cada disciplina)
        from app.services.evaluation_calculator import EvaluationCalculator

        disciplinas_notas = defaultdict(list)
        course_name = _obter_nome_curso(test)
        use_simple_calculation = test.grade_calculation_type == 'simple'

        for result in municipal_results:
            student_id = result.student_id
            if student_id in student_discipline_results:
                # Calcular nota específica para cada disciplina
                for disciplina, answers in student_discipline_results[student_id].items():
                    # Buscar questões desta disciplina
                    disciplina_questions = [q for q in test.questions if question_disciplines.get(q.id) == disciplina]

                    # Calcular acertos específicos para esta disciplina
                    correct_answers_disciplina = 0
                    for answer in answers:
                        question = next((q for q in disciplina_questions if q.id == answer.question_id), None)
                        if question:
                            if question.question_type == 'multiple_choice':
                                is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                                if is_correct:
                                    correct_answers_disciplina += 1
                            elif question.correct_answer:
                                if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                                    correct_answers_disciplina += 1

                    # Calcular nota específica para esta disciplina
                    if len(disciplina_questions) > 0:
                        proficiency_disciplina = EvaluationCalculator.calculate_proficiency(
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions),
                            course_name=course_name,
                            subject_name=disciplina
                        )
                        grade_disciplina = EvaluationCalculator.calculate_grade(
                            proficiency=proficiency_disciplina,
                            course_name=course_name,
                            subject_name=disciplina,
                            use_simple_calculation=use_simple_calculation,
                            correct_answers=correct_answers_disciplina,
                            total_questions=len(disciplina_questions)
                        )
                        disciplinas_notas[disciplina].append(grade_disciplina)

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


def _gerar_analise_participacao(template_data: Dict) -> str:
    """Gera análise inteligente da participação baseada nos dados"""
    try:
        total_alunos = template_data.get("total_alunos", {})
        total_geral = total_alunos.get("total_geral", {})
        
        matriculados = total_geral.get("matriculados", 0)
        avaliados = total_geral.get("avaliados", 0)
        percentual = total_geral.get("percentual", 0)
        faltosos = total_geral.get("faltosos", 0)
        
        if matriculados == 0:
            return "Dados de participação não disponíveis."
        
        # Análise baseada nos percentuais
        if percentual >= 90:
            avaliacao = "excelente"
            recomendacao = "manter o alto engajamento"
        elif percentual >= 80:
            avaliacao = "boa"
            recomendacao = "investigar causas das ausências e contatar famílias"
        elif percentual >= 70:
            avaliacao = "regular"
            recomendacao = "implementar estratégias de motivação e contato com famílias"
        else:
            avaliacao = "baixa"
            recomendacao = "ação imediata para aumentar participação"
        
        analise = f"A escola avaliou {avaliados} alunos do 9º ano, o que representa {percentual}% do total de {matriculados} alunos matriculados. "
        analise += f"Registrou-se um total de {faltosos} alunos faltosos. "
        analise += f"A taxa de participação de {percentual}% é {avaliacao}, indicando um {avaliacao} engajamento geral. "
        
        if faltosos > 0:
            analise += f"Contudo, a ausência de {faltosos} alunos é um número considerável. "
        
        analise += f"Recomenda-se {recomendacao} para elevar a participação em futuras avaliações e o planejamento de uma reposição diagnóstica para os alunos faltosos, visando obter um panorama mais completo da aprendizagem na série."
        
        return analise
        
    except Exception as e:
        logging.warning(f"Erro ao gerar análise de participação: {str(e)}")
        return "Análise de participação não disponível."


def _gerar_analise_proficiencia(template_data: Dict) -> str:
    """Gera análise inteligente da proficiência baseada nos dados"""
    try:
        proficiencia = template_data.get("proficiencia", {})
        disciplinas = proficiencia.get("por_disciplina", {})
        
        if not disciplinas:
            return "Dados de proficiência não disponíveis."
        
        # Buscar médias por disciplina
        medias_disciplinas = {}
        for disciplina, dados in disciplinas.items():
            if disciplina != "GERAL" and "por_turma" in dados:
                valores = [t.get("proficiencia", 0) for t in dados["por_turma"] if t.get("proficiencia")]
                if valores:
                    medias_disciplinas[disciplina] = sum(valores) / len(valores)
        
        if not medias_disciplinas:
            return "Dados de proficiência por disciplina não disponíveis."
        
        # Gerar análise
        analise = "A proficiência média da escola nesta avaliação diagnóstica foi de "
        
        disciplinas_list = list(medias_disciplinas.keys())
        for i, disciplina in enumerate(disciplinas_list):
            media = round(medias_disciplinas[disciplina], 2)
            if i == 0:
                analise += f"{media} em {disciplina}"
            elif i == len(disciplinas_list) - 1:
                analise += f" e {media} em {disciplina}."
            else:
                analise += f", {media} em {disciplina}"
        
        # Comparação com referencial (simulado)
        analise += " Comparativamente, o desempenho em "
        
        melhor_disciplina = max(medias_disciplinas.items(), key=lambda x: x[1])
        pior_disciplina = min(medias_disciplinas.items(), key=lambda x: x[1])
        
        analise += f"{melhor_disciplina[0]} ({melhor_disciplina[1]}) está significativamente acima da média de proficiência de 272,19 alcançada na Prova Saeb/2023 para o 9º ano. "
        analise += f"Este é um resultado excelente e um grande destaque para a escola, indicando um alto nível de domínio das competências em {melhor_disciplina[0]}. "
        
        analise += f"Em {pior_disciplina[0]}, a proficiência de {pior_disciplina[1]} encontra-se abaixo da média de 293,55 obtida no Saeb/2023. "
        analise += f"Apesar de ser uma proficiência considerável, ainda há uma lacuna para atingir o referencial nacional, indicando que esta é a área que demanda maior foco estratégico."
        
        return analise
        
    except Exception as e:
        logging.warning(f"Erro ao gerar análise de proficiência: {str(e)}")
        return "Análise de proficiência não disponível."


def _gerar_analise_notas(template_data: Dict) -> str:
    """Gera análise inteligente das notas baseada nos dados"""
    try:
        nota_geral = template_data.get("nota_geral", {})
        disciplinas = nota_geral.get("por_disciplina", {})
        
        if not disciplinas:
            return "Dados de notas não disponíveis."
        
        # Buscar médias por disciplina
        medias_disciplinas = {}
        for disciplina, dados in disciplinas.items():
            if disciplina != "GERAL" and "por_turma" in dados:
                valores = [t.get("nota", 0) for t in dados["por_turma"] if t.get("nota")]
                if valores:
                    medias_disciplinas[disciplina] = sum(valores) / len(valores)
        
        if not medias_disciplinas:
            return "Dados de notas por disciplina não disponíveis."
        
        # Calcular média geral
        media_geral = sum(medias_disciplinas.values()) / len(medias_disciplinas)
        
        # Gerar análise
        analise = f"A média geral de nota da escola na avaliação diagnóstica foi de {round(media_geral, 2)}, com "
        
        disciplinas_list = list(medias_disciplinas.keys())
        for i, disciplina in enumerate(disciplinas_list):
            media = round(medias_disciplinas[disciplina], 2)
            if i == 0:
                analise += f"{media} em {disciplina}"
            elif i == len(disciplinas_list) - 1:
                analise += f" e {media} em {disciplina}."
            else:
                analise += f", {media} em {disciplina}"
        
        # Comparação com referencial
        analise += f" Esta média geral de {round(media_geral, 2)} está "
        
        if media_geral >= 6.0:
            analise += "exatamente alinhada e ligeiramente acima da nota padronizada de 6,1 obtida na Prova Saeb/2023 para o 9º ano, o que é um resultado muito positivo para a escola como um todo. "
        else:
            analise += "abaixo da nota padronizada de 6,1 obtida na Prova Saeb/2023 para o 9º ano, indicando a necessidade de melhorias para atingir o padrão nacional. "
        
        # Análise por disciplina
        melhor_disciplina = max(medias_disciplinas.items(), key=lambda x: x[1])
        pior_disciplina = min(medias_disciplinas.items(), key=lambda x: x[1])
        
        analise += f"A nota em {melhor_disciplina[0]} ({melhor_disciplina[1]}) é excelente e reflete a alta proficiência alcançada. "
        analise += f"A nota em {pior_disciplina[0]} ({pior_disciplina[1]}), embora contribua para a boa média geral, ainda está abaixo do ideal e indica a necessidade de melhorias nesta disciplina para que a escola possa elevar ainda mais seu desempenho global."
        
        return analise
        
    except Exception as e:
        logging.warning(f"Erro ao gerar análise de notas: {str(e)}")
        return "Análise de notas não disponível."


def _gerar_analise_habilidades(template_data: Dict) -> str:
    """Gera análise inteligente das habilidades baseada nos dados"""
    try:
        acertos_por_habilidade = template_data.get("acertos_por_habilidade", {})
        
        if not acertos_por_habilidade:
            return "Dados de habilidades não disponíveis."
        
        # Analisar habilidades por disciplina
        analises_disciplinas = []
        
        for disciplina, dados in acertos_por_habilidade.items():
            if disciplina == "GERAL" or not dados.get("habilidades"):
                continue
            
            habilidades = dados["habilidades"]
            if not habilidades:
                continue
            
            # Calcular estatísticas
            total_habilidades = len(habilidades)
            habilidades_acima_70 = [h for h in habilidades if h.get("percentual", 0) >= 70]
            habilidades_abaixo_70 = [h for h in habilidades if h.get("percentual", 0) < 70]
            
            percentual_acima_70 = (len(habilidades_acima_70) / total_habilidades) * 100
            
            # Gerar análise para esta disciplina
            analise_disc = f"Os alunos demonstraram "
            
            if percentual_acima_70 >= 80:
                analise_disc += "excelente desempenho na grande maioria das habilidades de "
            elif percentual_acima_70 >= 60:
                analise_disc += "bom desempenho na maioria das habilidades de "
            else:
                analise_disc += "desempenho regular nas habilidades de "
            
            analise_disc += f"{disciplina}. "
            
            # Destacar habilidades com melhor desempenho
            if habilidades_acima_70:
                melhor_habilidade = max(habilidades_acima_70, key=lambda x: x.get("percentual", 0))
                analise_disc += f"Destacam-se habilidades como {melhor_habilidade.get('codigo', 'N/A')} com {melhor_habilidade.get('percentual', 0)}% de acerto. "
            
            # Pontos de atenção
            if habilidades_abaixo_70:
                analise_disc += f"Habilidades com Desempenho Abaixo da Meta (< 70%) – Pontos de Atenção: "
                for h in habilidades_abaixo_70[:3]:  # Limitar a 3 exemplos
                    analise_disc += f"{h.get('codigo', 'N/A')} ({h.get('percentual', 0)}%), "
                analise_disc = analise_disc.rstrip(", ") + ". "
                
                analise_disc += "Mesmo com o alto desempenho geral, focar nessas habilidades pode levar a um domínio ainda mais completo."
            
            analises_disciplinas.append(analise_disc)
        
        if not analises_disciplinas:
            return "Análise detalhada de habilidades não disponível."
        
        return " ".join(analises_disciplinas)
        
    except Exception as e:
        logging.warning(f"Erro ao gerar análise de habilidades: {str(e)}")
        return "Análise de habilidades não disponível."


@bp.errorhandler(Exception)
def handle_error(error):
    """Handler de erros para o blueprint"""
    print(f"=== DEBUG handle_error: ERRO CAPTURADO PELO ERROR HANDLER ===")
    print(f"Erro: {str(error)}")
    print(f"Tipo do erro: {type(error).__name__}")
    import traceback
    print(f"Traceback completo:\n{traceback.format_exc()}")
    logging.error(f"Erro no blueprint de relatórios: {str(error)}")
    logging.error(f"Traceback: {traceback.format_exc()}")
    return jsonify({"error": "Erro interno do servidor", "details": str(error)}), 500
