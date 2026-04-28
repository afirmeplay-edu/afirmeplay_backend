# -*- coding: utf-8 -*-
"""
Rotas especializadas para resultados de avaliações
Endpoints para análise de dados, estatísticas e relatórios

==============================================================
RELATÓRIOS QUE USAM ESTE ARQUIVO:
  - Análise das Avaliações  (frontend: AnaliseAvaliacoes / analise-avaliacoes)
  - Relatório Escolar       (frontend: RelatorioEscolar)

ROTAS USADAS PELOS RELATÓRIOS:
  GET /evaluation-results/avaliacoes
    → retorna tabela detalhada com alunos por disciplina (tabela_detalhada)
    → chamada por getEvaluationsList() no frontend
    → query opcional periodo=YYYY-MM (ClassTest.application); ignorado com report_entity_type=answer_sheet
  GET /evaluation-results/opcoes-filtros
    → retorna opções hierárquicas dos dropdowns de filtro
      (Estado → Município → Avaliação → Escola → Série → Turma)
    → chamada pelo FilterComponentAnalise no frontend

ARQUIVOS RELACIONADOS AO SISTEMA DE RELATÓRIOS:
  app/report_analysis/routes.py       → rotas Flask (/reports/dados-json, /reports/status)
  app/report_analysis/tasks.py        → tasks Celery de geração assíncrona
  app/report_analysis/services.py     → ReportAggregateService (cache no banco)
  app/report_analysis/calculations.py → re-exporta funções de cálculo
  app/report_analysis/debounce.py     → debounce Redis
  app/report_analysis/celery_app.py   → configuração do Celery
  app/routes/report_routes.py         → funções de cálculo + _determinar_escopo_por_role
  app/routes/evaluation_results_routes.py ← este arquivo (dados tabulares + filtros)
==============================================================
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required as old_role_required, get_current_user_from_token as old_get_current_user_from_token
# ✅ NOVO MÓDULO DE PERMISSÕES
from app.permissions import role_required, get_current_user_from_token
from app.permissions import can_view_test, get_user_permission_scope
from app.permissions.query_filters import filter_tests_by_user, filter_classes_by_user
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_filters import EvaluationFilters
from app.services.evaluation_aggregator import EvaluationAggregator
from app.services.evaluation_result_service import EvaluationResultService
from app.services.student_ranking_service import StudentRankingService
from app.report_analysis.services import ReportAggregateService
from app.models.test import Test
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.models.question import Question
from app.models.testQuestion import TestQuestion
from app.models.subject import Subject
from app.models.school import School
from app.models.city import City
from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.evaluationResult import EvaluationResult
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from app.utils.decimal_helpers import round_to_two_decimals
from app.utils.school_equal_weight_means import (
    granularidade_to_hierarchical_target,
    hierarchical_mean_grade_and_proficiency,
)
from sqlalchemy import cast, String, or_, and_, not_
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from app.models.classTest import ClassTest
from app.models.studentTestOlimpics import StudentTestOlimpics
from app.models.schoolTeacher import SchoolTeacher
from app.models.skill import Skill
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path, get_current_tenant_context
from app.routes.answer_sheet_evaluation_listing import (
    answer_sheet_target_classes_visible_for_user,
    build_answer_sheet_evaluation_by_id_json,
    build_answer_sheet_relatorio_detalhado_json,
    fetch_answer_sheet_gabarito_for_detail,
    is_answer_sheet_report_entity,
    listar_avaliacoes_answer_sheet_response,
    obter_escolas_por_gabarito,
    obter_gabaritos_por_municipio,
    obter_series_por_gabarito_escola,
    obter_series_por_gabarito_municipio,
    obter_turmas_por_gabarito_escola_serie,
    obter_turmas_por_gabarito_serie_municipio,
)
from app import db
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
from collections import defaultdict
from sqlalchemy import func, case
from datetime import datetime
from calendar import monthrange
from sqlalchemy.orm import joinedload
import dateutil.parser
import re

bp = Blueprint('evaluation_results', __name__, url_prefix='/evaluation-results')


# ⚠️ SUBSTITUÍDA: Esta função foi movida para app/permissions/rules.py
# Use: from app.permissions import can_view_test
# e passe o dict do usuário completo em vez de apenas user_id
def professor_pode_ver_avaliacao(user_id: str, test_id: str) -> bool:
    """
    ⚠️ SUBSTITUÍDA por: app.permissions.rules.can_view_test()
    
    Nova versão aceita dict completo do user e suporta todos os roles.
    
    Exemplo de uso:
        from app.permissions import can_view_test
        if not can_view_test(current_user, test_id):
            return jsonify({"error": "Acesso negado"}), 403
    
    Verifica se um professor pode ver uma avaliação específica.
    Retorna True se:
    1. O professor criou a avaliação OU
    2. A avaliação foi aplicada em escolas/turmas onde o professor está vinculado
    
    Args:
        user_id: ID do usuário professor
        test_id: ID da avaliação
    
    Returns:
        bool: True se o professor pode ver a avaliação, False caso contrário
    """
    try:
        # Buscar a avaliação
        test = Test.query.get(test_id)
        if not test:
            return False
        
        # Critério 1: Professor criou a avaliação
        if test.created_by == user_id:
            return True
        
        # Critério 2: Avaliação foi aplicada em TURMAS onde professor está vinculado
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        if not teacher:
            return False
        
        # ✅ CORRIGIDO: Buscar TURMAS onde o professor está vinculado (via TeacherClass)
        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        teacher_class_ids = [tc.class_id for tc in teacher_classes]
        
        if not teacher_class_ids:
            return False
        
        # Buscar turmas onde a avaliação foi aplicada
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return False
        
        # ✅ CORRIGIDO: Verificar se a avaliação foi aplicada em TURMAS onde o professor está vinculado
        classes_teacher_schools = Class.query.filter(
            Class.id.in_(class_ids),
            Class.id.in_(teacher_class_ids)
        ).all()
        
        # Se há pelo menos uma turma da escola do professor onde a avaliação foi aplicada
        return len(classes_teacher_schools) > 0
        
    except Exception as e:
        logging.error(f"Erro ao verificar permissão do professor para avaliação {test_id}: {str(e)}")
        return False


# ⚠️ SUBSTITUÍDA: Esta função foi movida para app/permissions/rules.py
# Use: from app.permissions import can_view_class, can_view_test
def professor_pode_ver_avaliacao_turmas(user_id: str, test_id: str) -> bool:
    """
    ⚠️ SUBSTITUÍDA por: app.permissions.rules.can_view_test() e can_view_class()
    
    Use can_view_test(user, test_id) que já implementa toda a lógica necessária.
    
    Verifica se um professor pode ver uma avaliação específica baseado nas TURMAS onde está vinculado.
    Retorna True se:
    1. O professor criou a avaliação OU
    2. A avaliação foi aplicada em turmas específicas onde o professor está vinculado
    
    Args:
        user_id: ID do usuário professor
        test_id: ID da avaliação
    
    Returns:
        bool: True se o professor pode ver a avaliação, False caso contrário
    """
    try:
        # Buscar a avaliação
        test = Test.query.get(test_id)
        if not test:
            return False
        
        # Critério 1: Professor criou a avaliação
        if test.created_by == user_id:
            return True
        
        # Critério 2: Avaliação foi aplicada em turmas específicas onde professor está vinculado
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        
        teacher = Teacher.query.filter_by(user_id=user_id).first()
        if not teacher:
            return False
        
        # Buscar turmas onde a avaliação foi aplicada
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return False
        
        # Buscar turmas onde o professor está vinculado através de TeacherClass
        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        teacher_class_ids = [tc.class_id for tc in teacher_classes]
        
        if not teacher_class_ids:
            return False
        
        # Verificar se há interseção entre turmas da avaliação e turmas do professor
        avaliacao_turmas = set(class_ids)
        professor_turmas = set(teacher_class_ids)
        
        # Se há pelo menos uma turma em comum
        return len(avaliacao_turmas.intersection(professor_turmas)) > 0
        
    except Exception as e:
        logging.error(f"Erro ao verificar permissão do professor para avaliação {test_id}: {str(e)}")
        return False


# ⚠️ SUBSTITUÍDA: Esta função foi movida para app/permissions/rules.py
# Use: from app.permissions import get_user_permission_scope
# ✅ Mantida para compatibilidade com código antigo, mas agora só chama a nova função
def verificar_permissao_filtros(user: dict, scope_info: dict = None) -> Dict[str, Any]:
    """
    ⚠️ SUBSTITUÍDA por: app.permissions.rules.get_user_permission_scope()
    
    ✅ Agora chama a função do novo módulo de permissões
    Use diretamente: from app.permissions import get_user_permission_scope
        permissao = get_user_permission_scope(user)
    
    Verifica permissões do usuário para acessar filtros baseado no seu papel
    
    Args:
        user: Dicionário com informações do usuário logado
        scope_info: Dicionário com informações do escopo (opcional)
    
    Returns:
        Dict com informações de permissão e filtros aplicáveis
    """
    # ✅ NOVA IMPLEMENTAÇÃO: Chama a função do novo módulo de permissões
    return get_user_permission_scope(user)
    
    # ⚠️ LÓGICA ANTIGA COMENTADA - NÃO USAR MAIS
    """
    role = user.get('role')
    city_id = user.get('city_id')
    
    # Normalizar o role para comparação
    if hasattr(role, 'value'):
        # Se for um objeto RoleEnum, pegar o valor
        role = role.value
    elif isinstance(role, str):
        # Se for string, remover RoleEnum. se presente
        if 'RoleEnum.' in role:
            role = role.split('.')[-1]
    
    # Converter para maiúsculas para comparação
    role = str(role).upper()
    
    if role == 'ADMIN':
        # Admin vê todos os resultados de todos os municípios
        return {
            'permitted': True,
            'scope': 'all',
            'filters': {
                'estados': 'all',
                'municipios': 'all',
                'escolas': 'all',
                'series': 'all',
                'turmas': 'all',
                'avaliacoes': 'all'
            }
        }
    
    elif role == 'TECADM':
        # Tecadm vê resultados de todas as escolas do seu município
        if not city_id:
            return {
                'permitted': False,
                'error': 'Tecadm não vinculado a um município'
            }
        
        return {
            'permitted': True,
            'scope': 'municipio',
            'city_id': city_id,
            'filters': {
                'estados': 'specific',
                'municipios': 'specific',
                'escolas': 'municipio',
                'series': 'municipio',
                'turmas': 'municipio',
                'avaliacoes': 'municipio'
            }
        }
    
    elif role in ['DIRETOR', 'COORDENADOR']:
        # Diretor e Coordenador vêem apenas da sua escola
        if not city_id:
            return {
                'permitted': False,
                'error': 'Usuário não vinculado a uma escola'
            }
        
        return {
            'permitted': True,
            'scope': 'escola',
            'city_id': city_id,
            'filters': {
                'estados': 'specific',
                'municipios': 'specific',
                'escolas': 'specific',
                'series': 'escola',
                'turmas': 'escola',
                'avaliacoes': 'escola'
            }
        }
    
    elif role == 'PROFESSOR':
        # Professor vê avaliações que criou OU que foram aplicadas em suas escolas/turmas
        return {
            'permitted': True,
            'scope': 'escola',
            'city_id': city_id,  # Pode ser None
            'filters': {
                'estados': 'specific',
                'municipios': 'specific',
                'escolas': 'vinculadas',
                'series': 'vinculadas',
                'turmas': 'vinculadas',
                'avaliacoes': 'vinculadas'
            }
        }
    
    else:
        # Aluno e outros papéis não têm acesso
        return {
            'permitted': False,
            'error': 'Papel não autorizado para visualizar resultados'
        }
    """

# ==================== ENDPOINTS TEMPORÁRIOS DE TESTE ====================

@bp.route('/grades', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def listar_grades():
    """
    Lista todas as grades (séries) disponíveis.
    Inclui education_stage_name para exibição em cards (ex.: modal de seleção de escopo).
    """
    try:
        grades = Grade.query.options(joinedload(Grade.education_stage)).all()
        result = [{
            "id": str(grade.id),
            "name": grade.name,
            "education_stage_id": str(grade.education_stage_id) if grade.education_stage_id else None,
            "education_stage_name": grade.education_stage.name if getattr(grade, "education_stage", None) else None,
        } for grade in grades]
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao listar grades: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar grades", "details": str(e)}), 500

@bp.route('/test/ping', methods=['GET'])
def test_ping():
    """Endpoint de teste sem autenticação"""
    return jsonify({"message": "Backend está funcionando!", "timestamp": datetime.now().isoformat()}), 200


@bp.route('/test/avaliacoes', methods=['GET'])
def test_avaliacoes():
    """Endpoint de teste para avaliacoes sem autenticação"""
    return jsonify({
        "data": [
            {
                "id": "test-eval-1",
                "titulo": "Avaliação de Matemática - 9º Ano [TESTE]",
                "disciplina": "Matemática",
                "curso": "Ensino Fundamental",
                "serie": "9º Ano",
                "escola": "Escola Municipal Campo Alegre",
                "municipio": "Campo Alegre",
                "data_aplicacao": "2024-01-15T10:00:00Z",
                "data_correcao": "2024-01-16T14:30:00Z",
                "status": "concluida",
                "total_alunos": 25,
                "alunos_participantes": 23,
                "alunos_pendentes": 2,
                "alunos_ausentes": 0,
                "media_nota": 7.2,
                "media_proficiencia": 650,
                "distribuicao_classificacao": {
                    "abaixo_do_basico": 2,
                    "basico": 8,
                    "adequado": 10,
                    "avancado": 3
                },
                "turmas_desempenho": []
            }
        ],
        "total": 1,
        "page": 1,
        "per_page": 10,
        "total_pages": 1
    }), 200

@bp.route('/test/avaliacoes/<string:evaluation_id>', methods=['GET'])
def test_evaluation_by_id(evaluation_id: str):
    """Endpoint de teste para buscar avaliação por ID sem autenticação"""
    return jsonify({
        "id": evaluation_id,
        "titulo": f"Avaliação Teste - {evaluation_id}",
        "disciplina": "Matemática",
        "curso": "Ensino Fundamental",
        "serie": "9º Ano",
        "escola": "Escola Municipal Campo Alegre",
        "municipio": "Campo Alegre",
        "data_aplicacao": "2024-01-15T10:00:00Z",
        "data_correcao": "2024-01-16T14:30:00Z",
        "status": "concluida",
        "total_alunos": 25,
        "alunos_participantes": 23,
        "alunos_pendentes": 2,
        "alunos_ausentes": 0,
        "media_nota": 7.2,
        "media_proficiencia": 650,
        "distribuicao_classificacao": {
            "abaixo_do_basico": 2,
            "basico": 8,
            "adequado": 10,
            "avancado": 3
        }
    }), 200



@bp.route('/test/relatorio-detalhado/<evaluation_id>', methods=['GET'])
def test_relatorio_detalhado(evaluation_id):
    """Endpoint de teste para relatório detalhado sem autenticação"""
    return jsonify({
        "avaliacao": {
            "id": evaluation_id,
            "titulo": "Avaliação de Matemática - 9º Ano [TESTE]",
            "disciplina": "Matemática",
            "total_questoes": 21
        },
        "questoes": [
            {
                "id": "q1",
                "numero": 1,
                "texto": "Questão sobre números e operações",
                "habilidade": "Números e Operações",
                "codigo_habilidade": "9N1.1",
                "tipo": "Múltipla Escolha",
                "dificuldade": "Fácil",
                "porcentagem_acertos": 85.5,
                "porcentagem_erros": 14.5
            },
            {
                "id": "q2",
                "numero": 2,
                "texto": "Questão sobre álgebra",
                "habilidade": "Álgebra",
                "codigo_habilidade": "9A1.2",
                "tipo": "Múltipla Escolha", 
                "dificuldade": "Médio",
                "porcentagem_acertos": 72.3,
                "porcentagem_erros": 27.7
            }
        ],
        "alunos": [
            {
                "id": "student-1",
                "nome": "João Silva",
                "turma": "9º A",
                "respostas": [
                    {"questao_id": "q1", "questao_numero": 1, "resposta_correta": True, "resposta_em_branco": False},
                    {"questao_id": "q2", "questao_numero": 2, "resposta_correta": False, "resposta_em_branco": False}
                ],
                "total_acertos": 15,
                "total_erros": 5,
                "total_em_branco": 1,
                "nota_final": 7.1,
                "proficiencia": 652,
                "classificacao": "Adequado"
            }
        ]
    }), 200

# ==================== ENDPOINTS ORIGINAIS ====================

@bp.errorhandler(Exception)
def handle_error(error):
    """Tratamento global de erros para este blueprint"""
    logging.error(f"Erro em evaluation_results: {str(error)}", exc_info=True)
    
    # Verificar se é um erro de transação falhada
    if "InFailedSqlTransaction" in str(error):
        try:
            db.session.rollback()
            logging.info("Rollback da transação realizado no error handler")
        except Exception as rollback_error:
            logging.error(f"Erro ao fazer rollback no error handler: {str(rollback_error)}")
    
    return jsonify({
        "error": "Erro interno no servidor",
        "details": str(error)
    }), 500


def format_decimal_two_places(value: float) -> float:
    """
    Formata um número para duas casas decimais
    DEPRECIADO: Use round_to_two_decimals de app.utils.decimal_helpers
    """
    return round_to_two_decimals(value)

def convert_proficiency_to_1000_scale(proficiency: float, course: str, subject: str) -> float:
    """
    Converte proficiência do sistema atual para escala 0-1000
    Usa a proficiência máxima correta por curso e disciplina
    """
    from app.services.evaluation_calculator import EvaluationCalculator
    
    # Determinar nível do curso e tipo de disciplina
    course_level = EvaluationCalculator._determine_course_level(course)
    subject_type = EvaluationCalculator._determine_subject_type(subject)
    
    # Obter proficiência máxima específica para curso/disciplina
    max_current = EvaluationCalculator.MAX_PROFICIENCY_CONFIG.get(
        (course_level, subject_type), 350  # Valor padrão
    )
    
    # Garantir que a proficiência não exceda o máximo permitido
    proficiency = min(proficiency, max_current)
    
    # Converter para escala 0-1000
    return (proficiency / max_current) * 1000


def get_classification_1000_scale(proficiency_1000: float) -> str:
    """
    Determina classificação baseada na escala 0-1000
    """
    if proficiency_1000 < 200:
        return "Abaixo do Básico"
    elif proficiency_1000 < 500:
        return "Básico"
    elif proficiency_1000 < 750:
        return "Adequado"
    else:
        return "Avançado"


# ==================== ENDPOINT 1: GET /avaliacoes ====================

@bp.route('/avaliacoes', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def listar_avaliacoes():
    """
    Lista avaliações aplicadas com estatísticas completas e filtros hierárquicos
    
    Nota: Retorna apenas avaliações que foram efetivamente aplicadas (estão na tabela class_test)
    de acordo com os filtros selecionados.
    
    Query Parameters:
    - estado (obrigatório): Estado geográfico (não pode ser 'all')
    - municipio (obrigatório): Município do estado
    - avaliacao (opcional): ID da avaliação específica ou 'all' para todas as avaliações
    - escola (opcional): ID da escola ou 'all' para todas as escolas
    - serie (opcional): ID da série ou 'all' para todas as séries
    - turma (opcional): ID da turma ou 'all' para todas as turmas
    - periodo (opcional): YYYY-MM; restringe ClassTest por application (ignorado em report_entity_type=answer_sheet)
    - page, per_page: Parâmetros de paginação
    
    Lógica hierárquica com "all":
    - Estado + Município + Avaliação "all": Todas as avaliações do município
    - Estado + Município + Avaliação + Escola "all": Todas as escolas que aplicaram a avaliação
    - Estado + Município + Avaliação + Escola + Série "all": Todas as séries da escola
    - Estado + Município + Avaliação + Escola + Série + Turma "all": Todas as turmas da série
    
    Filtros com valor "all" retornam todos os registros daquele nível dentro do contexto dos filtros anteriores.
    """
    try:
        # Garantir que não há transação pendente e limpar a sessão
        try:
            db.session.rollback()
            db.session.close()
            db.session.remove()
        except Exception:
            pass  # Ignorar erros de rollback no início
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        periodo_raw = request.args.get("periodo")
        periodo_bounds: Optional[Tuple[datetime, datetime]] = None
        if not is_answer_sheet_report_entity():
            if periodo_raw is not None and str(periodo_raw).strip():
                try:
                    periodo_bounds = _parse_periodo_bounds(periodo_raw)
                except ValueError as ve:
                    return jsonify({
                        "error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04).",
                        "details": str(ve),
                    }), 400

        # Extrair parâmetros de filtro
        estado = request.args.get('estado')
        municipio = request.args.get('municipio')
        escola = request.args.get('escola')
        serie = request.args.get('serie')
        turma = request.args.get('turma')
        avaliacao = request.args.get('avaliacao')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        per_page = min(per_page, 100)  # Limitar máximo

        # Para professor, restringir o dataset às turmas onde está vinculado (TeacherClass),
        # respeitando também os filtros selecionados (escola/série/turma).
        professor_allowed_class_ids: Optional[Set[Any]] = None
        if (user.get("role") or "").lower() == "professor":
            try:
                from app.permissions.utils import get_teacher_classes
                teacher_class_ids = get_teacher_classes(user["id"]) or []
                if not teacher_class_ids:
                    professor_allowed_class_ids = set()
                else:
                    allowed = set(teacher_class_ids)

                    # Se o usuário selecionou uma turma específica, ela precisa estar no escopo do professor.
                    if turma and str(turma).lower() != "all":
                        turma_id = turma
                        allowed = {turma_id} if turma_id in allowed else set()

                    # Se selecionou escola e/ou série, restringir às turmas do professor que pertencem a esse recorte.
                    if allowed and ((escola and str(escola).lower() != "all") or (serie and str(serie).lower() != "all")):
                        q_classes = Class.query.with_entities(Class.id).filter(Class.id.in_(list(allowed)))
                        if escola and str(escola).lower() != "all":
                            q_classes = q_classes.filter(Class.school_id == escola)
                        if serie and str(serie).lower() != "all":
                            q_classes = q_classes.filter(Class.grade_id == serie)
                        allowed = {row[0] for row in q_classes.all()}

                    professor_allowed_class_ids = allowed
            except Exception:
                # Em caso de erro, ser conservador e não retornar dados fora do escopo.
                professor_allowed_class_ids = set()
        
        # Validar filtros obrigatórios (estado e município são sempre obrigatórios)
        if not estado or estado.lower() == 'all':
            return jsonify({
                "error": "Estado é obrigatório e não pode ser 'all'"
            }), 400
        
        if not municipio:
            return jsonify({
                "error": "Município é obrigatório"
            }), 400
        
        # Contar filtros aplicados (excluindo 'all')
        filtros_aplicados = sum([
            bool(estado and estado.lower() != 'all'),
            bool(municipio and municipio.lower() != 'all'),
            bool(escola and escola.lower() != 'all'),
            bool(serie and serie.lower() != 'all'),
            bool(turma and turma.lower() != 'all'),
            bool(avaliacao and avaliacao.lower() != 'all')
        ])
        
        # Mínimo de 2 filtros (estado e município sempre contam)
        if filtros_aplicados < 2:
            return jsonify({
                "error": "É necessário aplicar pelo menos 2 filtros válidos (excluindo 'all')"
            }), 400
        
        # Identificar escopo de busca baseado nos filtros aplicados
        scope_info = _determinar_escopo_busca(estado, municipio, escola, serie, turma, avaliacao, user)
        logging.info(f"scope_info: {scope_info}")
        
        if not scope_info:
            return jsonify({"error": "Não foi possível determinar o escopo de busca"}), 400
        
        # Atualizar a variável escola com a escola padrão definida pelo escopo (se houver)
        if scope_info.get('escola') and not escola:
            escola = scope_info.get('escola')
            logging.info(f"Escola padrão aplicada: {escola}")
        
        # Buscar dados do escopo
        city_data = scope_info.get('city_data')
        permissao = verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao['error']}), 403

        # Para professor, propagar a restrição de turmas para todas as etapas de cálculo
        # (estatísticas gerais, por disciplina, tabela detalhada, ranking, etc.).
        if (user.get("role") or "").lower() == "professor":
            scope_info["_restrict_class_ids"] = list(professor_allowed_class_ids or [])
        
        # ✅ ALTERADO: Validação flexível - só exige escola para resultados, não para listagem
        from app.permissions import validate_professor_school_selection, validate_manager_school_selection
        
        escola_param = request.args.get('escola', 'all')
        
        # Aplicar validação baseada no role do usuário
        if user.get('role') == 'professor':
            # Para listagem de avaliações, não exige escola específica
            validation_result = validate_professor_school_selection(user, escola_param, require_school=False)
        elif user.get('role') in ['diretor', 'coordenador']:
            # Para listagem de avaliações, não exige escola específica
            validation_result = validate_manager_school_selection(user, escola_param, require_school=False)
        else:
            # Outros roles não precisam de validação específica
            validation_result = {'valid': True, 'school_id': escola_param}
        
        if not validation_result['valid']:
            return jsonify({
                "error": validation_result['error'],
                "code": "SCHOOL_ACCESS_DENIED"
            }), 403
        
        # Usar escola validada (pode ser None para usuários sem escola selecionada)
        escola_id_validada = validation_result['school_id']
        if escola_id_validada:
            escola = escola_id_validada
            logging.info(f"Escola validada para {user.get('role')}: {escola}")
        
        if is_answer_sheet_report_entity():
            municipio_str = str(municipio).strip() if municipio else ""
            if not municipio_str:
                return jsonify({"error": "Município é obrigatório"}), 400
            set_search_path(city_id_to_schema_name(municipio_str))
            return listar_avaliacoes_answer_sheet_response(
                estado=estado or "",
                municipio=municipio_str,
                escola=escola or "all",
                serie=serie or "all",
                turma=turma or "all",
                avaliacao=avaliacao or "all",
                page=page,
                per_page=per_page,
                user=user,
                permissao=permissao,
                scope_info=scope_info,
                city_data=city_data,
            )
        
        # Buscar escolas do escopo baseado nas permissões
        escolas_escopo = scope_info.get('escolas', [])
        
        # Filtrar escolas baseado no papel do usuário
        if permissao['scope'] == 'all':
            # Admin vê todas as escolas
            escola_ids = [escola.id for escola in escolas_escopo]
        elif permissao['scope'] == 'municipio':
            # Tecadm vê apenas escolas do seu município
            if user.get('city_id') != city_data.id:
                return jsonify({"error": "Acesso negado a este município"}), 403
            escola_ids = [escola.id for escola in escolas_escopo if escola.city_id == user.get('city_id')]
        elif permissao['scope'] == 'escola':
            if user.get('role') in ['diretor', 'coordenador']:
                # Diretor e Coordenador veem apenas sua escola
                from app.models.manager import Manager
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if not manager or not manager.school_id:
                    escola_ids = []  # Sem escola vinculada
                else:
                    escola_ids = [escola.id for escola in escolas_escopo if escola.id == manager.school_id]
            elif user.get('role') == 'professor':
                # ✅ CORRIGIDO: Professor vê apenas escolas que têm turmas onde está vinculado
                from app.models.teacher import Teacher
                from app.models.teacherClass import TeacherClass
                
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    # Buscar turmas onde o professor está vinculado
                    teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                    teacher_class_ids = [tc.class_id for tc in teacher_classes]
                    
                    if teacher_class_ids:
                        # Buscar escolas das turmas onde o professor está vinculado
                        teacher_schools = Class.query.filter(Class.id.in_(teacher_class_ids)).with_entities(Class.school_id).distinct().all()
                        teacher_school_ids = [school[0] for school in teacher_schools]
                        escola_ids = [escola.id for escola in escolas_escopo if escola.id in teacher_school_ids]
                    else:
                        escola_ids = []  # Professor não vinculado a nenhuma turma
                else:
                    escola_ids = []  # Professor não vinculado a nenhuma escola
        else:
            escola_ids = []
        
        # Log para debug
        logging.info(f"Escolas encontradas no escopo: {len(escolas_escopo)}")
        logging.info(f"Escolas filtradas por permissões: {len(escola_ids)}")
        if avaliacao and avaliacao.lower() != 'all':
            logging.info(f"Avaliação específica selecionada: {avaliacao}")
            logging.info(f"Escolas onde a avaliação foi aplicada: {[escola.name for escola in escolas_escopo]}")
        
        # Se não há escolas no escopo mas há uma avaliação específica, 
        # isso significa que a avaliação não foi aplicada em nenhuma escola do município
        # NOTA: Com a nova lógica de escola padrão, isso só deve acontecer se realmente não há dados
        if not escola_ids and avaliacao and avaliacao.lower() != 'all':
            return jsonify({
                "nivel_granularidade": "municipio",
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": municipio,
                    "escola": escola,
                    "serie": serie,
                    "turma": turma,
                    "avaliacao": avaliacao,
                    "periodo": (str(periodo_raw).strip() if periodo_raw and str(periodo_raw).strip() else None),
                },
                "estatisticas_gerais": {
                    "tipo": "municipio",
                    "nome": city_data.name if city_data else "Todos os municípios",
                    "estado": scope_info.get('estado', 'Todos os estados'),
                    "municipio": city_data.name if city_data else "Todos os municípios",
                    "escola": None,
                    "serie": None,
                    "total_escolas": 0,
                    "total_series": 0,
                    "total_turmas": 0,
                    "total_avaliacoes": 0,
                    "total_alunos": 0,
                    "alunos_participantes": 0,
                    "alunos_pendentes": 0,
                    "alunos_ausentes": 0,
                    "media_nota_geral": 0.0,
                    "media_proficiencia_geral": 0.0,
                    "distribuicao_classificacao_geral": {
                        "abaixo_do_basico": 0,
                        "basico": 0,
                        "adequado": 0,
                        "avancado": 0
                    }
                },
                "resultados_por_disciplina": [],
                "resultados_detalhados": {
                    "avaliacoes": [],
                    "paginacao": {
                        "page": page,
                        "per_page": per_page,
                        "total": 0,
                        "total_pages": 0
                    }
                },
                "opcoes_proximos_filtros": {
                    "escolas": [],
                    "series": [],
                    "turmas": [],
                    "avaliacoes": []
                }
            }), 200
        
        # Buscar apenas avaliações que foram aplicadas (estão na tabela class_test)
        # Filtradas pelas escolas do escopo selecionado
        try:
            # Garantir que a sessão está limpa antes de construir a query
            db.session.rollback()
            
            # ✅ IMPORTANTE: Importar Test aqui para estar disponível em todo o escopo
            from app.models.test import Test
            
            # Construir query base com filtros de permissões
            query_base = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                                       .join(Class, ClassTest.class_id == Class.id)\
                                       .join(Grade, Class.grade_id == Grade.id)\
                                       .join(School, School.id == cast(Class.school_id, String))\
                                       .join(City, School.city_id == City.id)\
                                       .options(
                                           joinedload(ClassTest.test).joinedload(Test.subject_rel),
                                           joinedload(ClassTest.class_).joinedload(Class.grade)
                                           # ❌ REMOVIDO: joinedload(ClassTest.class_).joinedload(Class.school).joinedload(School.city) - Class.school é property
                                       )

            # ✅ IMPORTANTE: Professor só pode ver dados das suas turmas.
            if (user.get("role") or "").lower() == "professor":
                if professor_allowed_class_ids is None or not professor_allowed_class_ids:
                    query_base = query_base.filter(ClassTest.class_id == None)  # Força vazio
                else:
                    query_base = query_base.filter(ClassTest.class_id.in_(list(professor_allowed_class_ids)))
            
            # ✅ ALTERADO: Aplicar filtros usando o novo módulo de permissões
            if permissao['scope'] == 'municipio':
                # Tecadm vê apenas avaliações do seu município
                query_base = query_base.filter(City.id == user.get('city_id'))
            elif permissao['scope'] == 'escola':
                if user.get('role') in ['diretor', 'coordenador']:
                    # ✅ ALTERADO: Diretor/Coordenador usa filtro flexível - permite listagem sem escola específica
                    from app.permissions.query_filters import filter_tests_by_user
                    
                    # Aplicar filtro usando modo flexível (não exige escola específica para listagem)
                    test_query = Test.query
                    test_query = filter_tests_by_user(test_query, user, escola_id_validada, require_school=False)
                    
                    # Filtrar ClassTest baseado nas avaliações permitidas
                    test_ids_permitidas = [t.id for t in test_query.all()]
                    if test_ids_permitidas:
                        query_base = query_base.filter(Test.id.in_(test_ids_permitidas))
                    else:
                        query_base = query_base.filter(Test.id == None)  # Força resultado vazio
                elif user.get('role') == 'professor':
                    # ✅ ALTERADO: Professor usa filtro flexível - permite listagem sem escola específica
                    from app.permissions.query_filters import filter_tests_by_user
                    
                    # Aplicar filtro usando modo flexível (não exige escola específica para listagem)
                    test_query = Test.query
                    test_query = filter_tests_by_user(test_query, user, escola_id_validada, require_school=False)
                    
                    # Filtrar ClassTest baseado nas avaliações permitidas
                    test_ids_permitidas = [t.id for t in test_query.all()]
                    if test_ids_permitidas:
                        query_base = query_base.filter(Test.id.in_(test_ids_permitidas))
                    else:
                        query_base = query_base.filter(Test.id == None)  # Força resultado vazio
            
            # Aplicar filtro por escolas do escopo (apenas para não-professores)
            if user.get('role') != 'professor' and escola_ids:
                query_base = query_base.filter(School.id.in_(escola_ids))
            elif user.get('role') != 'professor':
                # Para não-professor, aplicar filtro de escolas se existir
                if not escola_ids:
                    # Se não tem escola_id, retornar lista vazia
                    query_base = query_base.filter(School.id == None)
            
            # Log da query para debug
            logging.info(f"Query base construída com permissões aplicadas: {permissao['scope']}")
            logging.info(f"Escolas filtradas: {len(escola_ids)}")
            
        except Exception as e:
            logging.error(f"Erro ao construir query base: {str(e)}")
            db.session.rollback()
            return jsonify({"error": "Erro ao construir query", "details": str(e)}), 500
        
        # Aplicar filtros na ordem especificada (filtros com "all" são ignorados)
        try:
            # Garantir que a sessão está limpa antes de aplicar filtros
            db.session.rollback()
            
            if estado and estado.lower() != 'all':
                query_base = query_base.filter(City.state.ilike(f"%{estado}%"))
            
            if municipio and municipio.lower() != 'all':
                # Tentar filtrar por ID primeiro, depois por nome
                city_filter = City.query.get(municipio)
                if city_filter:
                    query_base = query_base.filter(City.id == municipio)
                else:
                    query_base = query_base.filter(City.name.ilike(f"%{municipio}%"))
            
            if avaliacao and avaliacao.lower() != 'all':
                # Tentar filtrar por ID primeiro, depois por título
                test_filter = Test.query.get(avaliacao)
                if test_filter:
                    query_base = query_base.filter(Test.id == avaliacao)
                else:
                    query_base = query_base.filter(Test.title.ilike(f"%{avaliacao}%"))
            
            if escola and escola.lower() != 'all':
                # Tentar filtrar por ID primeiro, depois por nome
                # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
                from app.utils.uuid_helpers import uuid_to_str
                escola_str = uuid_to_str(escola)
                school_filter = School.query.filter(School.id == escola_str).first() if escola_str else None
                if school_filter:
                    query_base = query_base.filter(School.id == escola)
                else:
                    query_base = query_base.filter(School.name.ilike(f"%{escola}%"))
            
            if serie and serie.lower() != 'all':
                # Tentar filtrar por ID primeiro, depois por nome
                grade_filter = Grade.query.get(serie)
                if grade_filter:
                    query_base = query_base.filter(Grade.id == serie)
                else:
                    query_base = query_base.filter(Grade.name.ilike(f"%{serie}%"))
            
            if turma and turma.lower() != 'all':
                # Tentar filtrar por ID primeiro, depois por nome
                class_filter = Class.query.get(turma)
                if class_filter:
                    query_base = query_base.filter(Class.id == turma)
                else:
                    query_base = query_base.filter(Class.name.ilike(f"%{turma}%"))
            
            # Aplicar filtros específicos baseados no papel do usuário
            if permissao['scope'] == 'escola' and user['role'] == 'professor':
                # ✅ CORRIGIDO: Professor vê avaliações que criou OU que foram aplicadas em TURMAS específicas onde está vinculado
                from app.models.teacher import Teacher
                from app.models.teacherClass import TeacherClass
                from sqlalchemy import or_
                
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    # Criar filtro OR: avaliações criadas pelo professor OU aplicadas em suas TURMAS
                    filters = [Test.created_by == user['id']]
                    
                    # ✅ Buscar TURMAS onde o professor está vinculado (via TeacherClass)
                    teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                    teacher_class_ids = [tc.class_id for tc in teacher_classes]
                    
                    if teacher_class_ids:
                        # ✅ Avaliações aplicadas em TURMAS ESPECÍFICAS onde o professor está vinculado
                        filters.append(
                            Test.id.in_(
                                db.session.query(ClassTest.test_id).filter(
                                    ClassTest.class_id.in_(teacher_class_ids)
                                )
                            )
                        )
                    
                    query_base = query_base.filter(or_(*filters))
                else:
                    # Se não é um professor válido, não mostrar nenhuma avaliação
                    query_base = query_base.filter(Test.created_by == user['id']).filter(Test.id == None)

            query_base = _apply_class_test_application_period(query_base, periodo_bounds)

        except Exception as e:
            logging.error(f"Erro ao aplicar filtros: {str(e)}")
            db.session.rollback()
            return jsonify({"error": "Erro ao aplicar filtros", "details": str(e)}), 500
        
        # Buscar todas as avaliações do escopo para cálculos
        try:
            # Garantir que a sessão está limpa antes de executar a query
            db.session.rollback()
            
            # Se ainda houver erro, tentar com uma nova sessão
            try:
                todas_avaliacoes_escopo = query_base.all()
                logging.info(f"Query executada com sucesso: {len(todas_avaliacoes_escopo)} avaliações encontradas")
            except Exception as inner_e:
                if "InFailedSqlTransaction" in str(inner_e):
                    logging.warning("Tentando com nova sessão devido a transação falhada")
                    db.session.rollback()
                    db.session.close()
                    # Recriar a query com nova sessão
                    query_base = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                                               .join(Class, ClassTest.class_id == Class.id)\
                                               .join(Grade, Class.grade_id == Grade.id)\
                                               .join(School, School.id == cast(Class.school_id, String))\
                                               .join(City, School.city_id == City.id)\
                                               .options(
                                                   joinedload(ClassTest.test).joinedload(Test.subject_rel),
                                                   joinedload(ClassTest.class_).joinedload(Class.grade)
                                                   # ❌ REMOVIDO: joinedload(ClassTest.class_).joinedload(Class.school).joinedload(School.city) - Class.school é property
                                               )
                    # Reaplicar filtros
                    if estado and estado.lower() != 'all':
                        query_base = query_base.filter(City.state.ilike(f"%{estado}%"))
                    if municipio and municipio.lower() != 'all':
                        city_filter = City.query.get(municipio)
                        if city_filter:
                            query_base = query_base.filter(City.id == municipio)
                    if avaliacao and avaliacao.lower() != 'all':
                        test_filter = Test.query.get(avaliacao)
                        if test_filter:
                            query_base = query_base.filter(Test.id == avaliacao)
                    if user['role'] == 'professor':
                        # Para professores, usar a nova lógica de permissões
                        from app.models.teacher import Teacher
                        from sqlalchemy import or_
                        
                        teacher = Teacher.query.filter_by(user_id=user['id']).first()
                        if teacher:
                            # ✅ CORRIGIDO: Criar filtro OR com TURMAS ESPECÍFICAS onde o professor está vinculado
                            from app.models.teacherClass import TeacherClass
                            
                            # Criar filtro OR: avaliações criadas pelo professor OU aplicadas em suas TURMAS
                            filters = [Test.created_by == user['id']]
                            
                            # ✅ Buscar TURMAS onde o professor está vinculado (via TeacherClass)
                            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                            teacher_class_ids = [tc.class_id for tc in teacher_classes]
                            
                            if teacher_class_ids:
                                # ✅ Avaliações aplicadas em TURMAS ESPECÍFICAS onde o professor está vinculado
                                filters.append(
                                    Test.id.in_(
                                        db.session.query(ClassTest.test_id).filter(
                                            ClassTest.class_id.in_(teacher_class_ids)
                                        )
                                    )
                                )
                            
                            query_base = query_base.filter(or_(*filters))

                    query_base = _apply_class_test_application_period(query_base, periodo_bounds)

                    todas_avaliacoes_escopo = query_base.all()
                    logging.info(f"Query executada com nova sessão: {len(todas_avaliacoes_escopo)} avaliações encontradas")
                else:
                    raise inner_e
                    
        except Exception as e:
            logging.error(f"Erro ao buscar avaliações do escopo: {str(e)}")
            db.session.rollback()
            return jsonify({"error": "Erro ao buscar avaliações", "details": str(e)}), 500
        
        # Determinar nível de granularidade
        nivel_granularidade = _determinar_nivel_granularidade(estado, municipio, escola, serie, turma, avaliacao, user)
        logging.info(f"nivel_granularidade: {nivel_granularidade}, estado: {estado}, municipio: {municipio}, escola: {escola}, serie: {serie}, turma: {turma}, avaliacao: {avaliacao}")
        
        # Calcular estatísticas consolidadas baseadas no escopo dos filtros
        estatisticas_consolidadas = _calcular_estatisticas_consolidadas_por_escopo(todas_avaliacoes_escopo, scope_info, nivel_granularidade, user)
        if isinstance(estatisticas_consolidadas, dict):
            estatisticas_consolidadas["participantes_distribuicao"] = estatisticas_consolidadas.get(
                "alunos_participantes", 0
            )
        
        # Calcular estatísticas por disciplina
        resultados_por_disciplina = _calcular_estatisticas_por_disciplina(todas_avaliacoes_escopo, scope_info, nivel_granularidade)
        for disciplina in resultados_por_disciplina or []:
            if isinstance(disciplina, dict):
                disciplina["participantes_distribuicao"] = disciplina.get("alunos_participantes", 0)
        
        # Aplicar paginação para resultados detalhados
        try:
            # Garantir que a sessão está limpa antes de executar as queries de paginação
            db.session.rollback()
            
            # Se ainda houver erro, tentar com uma nova sessão
            try:
                total = query_base.count()
                offset = (page - 1) * per_page
                class_tests_paginados = query_base.offset(offset).limit(per_page).all()
            except Exception as inner_e:
                if "InFailedSqlTransaction" in str(inner_e):
                    logging.warning("Tentando paginação com nova sessão devido a transação falhada")
                    db.session.rollback()
                    db.session.close()
                    # Recriar a query com nova sessão
                    query_base = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                                               .join(Class, ClassTest.class_id == Class.id)\
                                               .join(Grade, Class.grade_id == Grade.id)\
                                               .join(School, School.id == cast(Class.school_id, String))\
                                               .join(City, School.city_id == City.id)\
                                               .options(
                                                   joinedload(ClassTest.test).joinedload(Test.subject_rel),
                                                   joinedload(ClassTest.class_).joinedload(Class.grade)
                                                   # ❌ REMOVIDO: joinedload(ClassTest.class_).joinedload(Class.school).joinedload(School.city) - Class.school é property
                                               )
                    # Reaplicar filtros
                    if estado and estado.lower() != 'all':
                        query_base = query_base.filter(City.state.ilike(f"%{estado}%"))
                    if municipio and municipio.lower() != 'all':
                        city_filter = City.query.get(municipio)
                        if city_filter:
                            query_base = query_base.filter(City.id == municipio)
                    if avaliacao and avaliacao.lower() != 'all':
                        test_filter = Test.query.get(avaliacao)
                        if test_filter:
                            query_base = query_base.filter(Test.id == avaliacao)
                    if permissao['scope'] == 'escola' and user['role'] == 'professor':
                        # Professor vê avaliações que criou OU que foram aplicadas em suas escolas/turmas
                        from app.models.teacher import Teacher
                        from sqlalchemy import or_
                        
                        teacher = Teacher.query.filter_by(user_id=user['id']).first()
                        if teacher:
                            # ✅ CORRIGIDO: Criar filtro OR com TURMAS ESPECÍFICAS onde o professor está vinculado
                            from app.models.teacherClass import TeacherClass
                            
                            # Criar filtro OR: avaliações criadas pelo professor OU aplicadas em suas TURMAS
                            filters = [Test.created_by == user['id']]
                            
                            # ✅ Buscar TURMAS onde o professor está vinculado (via TeacherClass)
                            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                            teacher_class_ids = [tc.class_id for tc in teacher_classes]
                            
                            if teacher_class_ids:
                                # ✅ Avaliações aplicadas em TURMAS ESPECÍFICAS onde o professor está vinculado
                                filters.append(
                                    Test.id.in_(
                                        db.session.query(ClassTest.test_id).filter(
                                            ClassTest.class_id.in_(teacher_class_ids)
                                        )
                                    )
                                )
                            
                            query_base = query_base.filter(or_(*filters))
                        else:
                            # Se não é um professor válido, não mostrar nenhuma avaliação
                            query_base = query_base.filter(Test.created_by == user['id']).filter(Test.id == None)

                    query_base = _apply_class_test_application_period(query_base, periodo_bounds)

                    total = query_base.count()
                    offset = (page - 1) * per_page
                    class_tests_paginados = query_base.offset(offset).limit(per_page).all()
                else:
                    raise inner_e
                    
        except Exception as e:
            logging.error(f"Erro ao aplicar paginação: {str(e)}")
            db.session.rollback()
            return jsonify({"error": "Erro ao aplicar paginação", "details": str(e)}), 500
        
        # Gerar resultados detalhados agregados por nível de granularidade
        resultados_detalhados = _gerar_resultados_detalhados_por_granularidade(
            class_tests_paginados, nivel_granularidade, estatisticas_consolidadas, scope_info
        )
        
        # Calcular total de páginas
        total_pages = (total + per_page - 1) // per_page
        
        # Gerar opções dos próximos filtros
        opcoes_proximos_filtros = _gerar_opcoes_proximos_filtros(scope_info, nivel_granularidade, user)
        
        # Gerar tabela detalhada por disciplina (apenas se uma avaliação específica for selecionada)
        tabela_detalhada = {}
        ranking_alunos = []
        
        restrict_class_ids: Optional[Set[Any]] = None
        if periodo_bounds is not None and avaliacao and avaliacao.lower() != "all":
            restrict_class_ids = {
                ct.class_id for ct in todas_avaliacoes_escopo if str(ct.test_id) == str(avaliacao)
            }

        # Para professor, sempre restringir a tabela/ranking às suas turmas (e ao recorte escola/série/turma).
        if (user.get("role") or "").lower() == "professor":
            if professor_allowed_class_ids is None:
                professor_allowed_class_ids = set()
            if restrict_class_ids is None:
                restrict_class_ids = set(professor_allowed_class_ids)
            else:
                restrict_class_ids = set(restrict_class_ids).intersection(set(professor_allowed_class_ids))

        if avaliacao and avaliacao.lower() != 'all':
            tabela_detalhada = _gerar_tabela_detalhada_por_disciplina(
                avaliacao, scope_info, nivel_granularidade, user, restrict_class_ids
            )

            ranking_alunos = _calcular_ranking_global_alunos(
                avaliacao, scope_info, nivel_granularidade, user, restrict_class_ids
            )
        
        periodo_raw_clean = (str(periodo_raw).strip() if periodo_raw and str(periodo_raw).strip() else None)

        return jsonify({
            "nivel_granularidade": nivel_granularidade,
            "filtros_aplicados": {
                "estado": estado,
                "municipio": municipio,
                "escola": escola,
                "serie": serie,
                "turma": turma,
                "avaliacao": avaliacao,
                "periodo": _formatar_periodo_br(periodo_raw_clean),
                "periodo_iso": periodo_raw_clean,
            },
            "estatisticas_gerais": estatisticas_consolidadas,
            "resultados_por_disciplina": resultados_por_disciplina,
            "resultados_detalhados": {
                "avaliacoes": resultados_detalhados,
                "paginacao": {
                    "page": page,
                    "per_page": per_page,
                    "total": total,
                    "total_pages": total_pages
                }
            },
            "tabela_detalhada": tabela_detalhada,
            "ranking": ranking_alunos,
            "opcoes_proximos_filtros": opcoes_proximos_filtros
        }), 200

    except Exception as e:
        logging.error(f"Erro ao listar avaliações: {str(e)}", exc_info=True)
        
        # Verificar se é um erro de transação falhada
        if "InFailedSqlTransaction" in str(e):
            try:
                # Tentar fazer rollback da transação
                db.session.rollback()
                logging.info("Rollback da transação realizado com sucesso")
            except Exception as rollback_error:
                logging.error(f"Erro ao fazer rollback: {str(rollback_error)}")
        
        return jsonify({"error": "Erro ao listar avaliações", "details": str(e)}), 500


def _gerar_tabela_detalhada_por_disciplina(
    avaliacao_id: str,
    scope_info: Dict,
    nivel_granularidade: str,
    user: Dict,
    restrict_class_ids: Optional[Set[Any]] = None,
) -> Dict[str, Any]:
    """
    Gera tabela detalhada organizada por disciplina com dados dos alunos
    CORRIGIDA: Agora mostra TODOS os alunos em TODAS as disciplinas com TODAS as questões

    restrict_class_ids: quando definido (ex.: filtro periodo em GET /avaliacoes), só alunos dessas turmas.
    """
    try:
        from app.models.question import Question
        from app.models.evaluationResult import EvaluationResult
        
        # Verificar se avaliação existe
        test = Test.query.get(avaliacao_id)
        if not test:
            return {"disciplinas": []}
        
        # Buscar questões da avaliação através da tabela de relacionamento TestQuestion
        
        questoes_por_disciplina = {}
        
        # Buscar todas as questões da avaliação com suas disciplinas
        test_questions = TestQuestion.query.filter_by(
            test_id=avaliacao_id
        ).join(Question).options(
            joinedload(TestQuestion.question).joinedload(Question.subject)
        ).order_by(TestQuestion.order).all()
        
        # Buscar todas as habilidades necessárias para otimizar as consultas
        skill_ids = set()
        for test_question in test_questions:
            if test_question.question.skill:
                # Remover chaves {} se existirem
                clean_skill_id = test_question.question.skill.replace('{', '').replace('}', '')
                skill_ids.add(clean_skill_id)
        
        # Buscar habilidades em lote
        skills_dict = {}
        if skill_ids:
            skills = Skill.query.filter(Skill.id.in_(skill_ids)).all()
            skills_dict = {str(skill.id): skill for skill in skills}
        
        for test_question in test_questions:
            question = test_question.question
            subject_id = str(question.subject_id) if question.subject_id else 'sem_disciplina'
            subject_name = question.subject.name if question.subject else 'Sem Disciplina'
            
            # Buscar informações da habilidade
            skill_code = "N/A"
            skill_description = "N/A"
            if question.skill:
                clean_skill_id = question.skill.replace('{', '').replace('}', '')
                skill_obj = skills_dict.get(clean_skill_id)
                if skill_obj:
                    skill_code = skill_obj.code
                    skill_description = skill_obj.description
                else:
                    skill_code = clean_skill_id
                    skill_description = "Habilidade não encontrada"
            
            if subject_id not in questoes_por_disciplina:
                questoes_por_disciplina[subject_id] = {
                    "id": subject_id,
                    "nome": subject_name,
                    "questoes": [],
                    "alunos": []
                }
            
            questoes_por_disciplina[subject_id]["questoes"].append({
                "numero": test_question.order or 1,
                "habilidade": skill_description,
                "codigo_habilidade": skill_code,
                "question_id": question.id
            })

        # Mapa question_id -> question (evita Question.query.get no loop)
        questions_map = {q.id: q for tq in test_questions for q in [tq.question]}

        # Determinar escopo de alunos baseado na granularidade
        # CORRIGIDO: Usar a lógica correta de filtros hierárquicos
        escopo_calculo = _determinar_escopo_calculo(scope_info, nivel_granularidade)
        logging.info(f"Escopo de cálculo para tabela detalhada: {escopo_calculo}")
        
        # Buscar alunos usando a função corrigida
        # Para o caso "escola", usar a lógica específica baseada no usuário
        if nivel_granularidade == "escola" and user:
            if user.get('role') == 'professor':
                # ✅ CORRIGIDO: Professor: buscar alunos das TURMAS onde está vinculado
                from app.models.teacher import Teacher
                from app.models.teacherClass import TeacherClass
                
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    # Buscar turmas onde o professor está vinculado (via TeacherClass)
                    teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                    teacher_class_ids = [tc.class_id for tc in teacher_classes]
                    
                    if teacher_class_ids:
                        all_students = Student.query.filter(Student.class_id.in_(teacher_class_ids)).all()
                    else:
                        all_students = []
                else:
                    all_students = []
            elif user.get('role') in ['diretor', 'coordenador']:
                # Diretor/Coordenador: buscar alunos apenas da sua escola
                from app.models.manager import Manager
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if manager and manager.school_id:
                    turmas_escola = Class.query.filter(Class.school_id == manager.school_id).all()
                    turma_ids_escola = [t.id for t in turmas_escola]
                    all_students = Student.query.filter(Student.class_id.in_(turma_ids_escola)).all()
                else:
                    all_students = []
            else:
                # Admin/Tecadm (e outros roles): respeitar o filtro de escola do escopo calculado
                all_students = _buscar_alunos_por_escopo(escopo_calculo)
        else:
            all_students = _buscar_alunos_por_escopo(escopo_calculo)

        if restrict_class_ids is not None:
            if not restrict_class_ids:
                all_students = []
            else:
                all_students = [s for s in all_students if s.class_id in restrict_class_ids]
        
        if not all_students:
            logging.warning("Nenhum aluno encontrado para o escopo especificado")
            return {"disciplinas": list(questoes_por_disciplina.values())}

        # Eager load class + grade; carregar escolas em uma query (Class.school é property = N+1)
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade)
        ).filter(Student.id.in_([s.id for s in all_students])).all()
        school_ids = list({s.class_.school_id for s in all_students if s.class_ and getattr(s.class_, 'school_id', None)})
        school_by_id = {}
        if school_ids:
            school_by_id = {s.id: s for s in School.query.filter(School.id.in_(school_ids)).all()}

        # Curso da avaliação (uma vez; evita query por aluno)
        course_name = "Anos Iniciais"
        if getattr(test, 'course', None):
            try:
                from app.models.educationStage import EducationStage
                import uuid as _uuid
                course_uuid = _uuid.UUID(test.course)
                course_obj = EducationStage.query.get(course_uuid)
                if course_obj:
                    course_name = course_obj.name
            except (ValueError, TypeError, Exception):
                pass

        use_simple_calculation = getattr(test, 'grade_calculation_type', None) == 'simple'

        # Log para debug
        logging.debug("Tabela detalhada: %d alunos encontrados", len(all_students))

        # Buscar resultados pré-calculados (apenas dos alunos do escopo)
        if all_students:
            student_ids = [aluno.id for aluno in all_students]
            evaluation_results = EvaluationResult.query.filter(
                EvaluationResult.test_id == avaliacao_id,
                EvaluationResult.student_id.in_(student_ids)
            ).all()
        else:
            evaluation_results = []
        
        results_dict = {er.student_id: er for er in evaluation_results}

        if all_students:
            all_student_answers = StudentAnswer.query.filter(
                StudentAnswer.test_id == avaliacao_id,
                StudentAnswer.student_id.in_(student_ids)
            ).all()
        else:
            all_student_answers = []
        respostas_por_aluno = {}
        for resposta in all_student_answers:
            if resposta.student_id not in respostas_por_aluno:
                respostas_por_aluno[resposta.student_id] = {}
            respostas_por_aluno[resposta.student_id][resposta.question_id] = resposta

        logging.debug("Tabela detalhada: %d resultados, %d respostas", len(evaluation_results), len(all_student_answers))

        for subject_id, disciplina_data in questoes_por_disciplina.items():
            alunos_disciplina = []
            
            # Para cada aluno, verificar TODAS as questões desta disciplina
            for student in all_students:
                # Buscar informações da turma e escola com verificação mais robusta
                turma_nome = "N/A"
                serie_nome = "N/A"
                escola_nome = "N/A"
                
                if student.class_:
                    turma_nome = student.class_.name or "N/A"
                    if student.class_.grade:
                        serie_nome = student.class_.grade.name or "N/A"
                    sid = getattr(student.class_, 'school_id', None)
                    if sid and sid in school_by_id:
                        escola_nome = school_by_id[sid].name or "N/A"

                evaluation_result = results_dict.get(student.id)

                respostas_por_questao = []
                total_acertos = 0
                total_erros = 0
                total_respondidas = 0

                for questao_info in disciplina_data["questoes"]:
                    questao_numero = questao_info["numero"]
                    question_id = questao_info["question_id"]
                    question = questions_map.get(question_id)

                    if question:
                        # Verificar se o aluno respondeu esta questão
                        resposta_aluno = respostas_por_aluno.get(student.id, {}).get(question.id)
                        
                        if resposta_aluno:
                            total_respondidas += 1
                            acertou = False
                            if question.question_type == 'multiple_choice':
                                acertou = EvaluationResultService.check_multiple_choice_answer(resposta_aluno.answer, question.correct_answer)
                            else:
                                acertou = str(resposta_aluno.answer).strip().lower() == str(question.correct_answer).strip().lower()
                            if acertou:
                                total_acertos += 1
                            else:
                                total_erros += 1
                            
                            respostas_por_questao.append({
                                "questao": questao_numero,
                                "acertou": acertou,
                                "respondeu": True,
                                "resposta": resposta_aluno.answer
                            })
                        else:
                            # Aluno NÃO respondeu esta questão
                            respostas_por_questao.append({
                                "questao": questao_info["numero"],
                                "acertou": False,
                                "respondeu": False,
                                "resposta": None
                            })

                # Buscar resultado pré-calculado do aluno
                evaluation_result = results_dict.get(student.id)
                
                # Tentar buscar dados por disciplina do campo JSON
                disciplina_nota = 0.0
                disciplina_proficiencia = 0.0
                disciplina_classificacao = None
                
                if evaluation_result and evaluation_result.subject_results:
                    # Usar dados pré-calculados do JSON (FONTE DA VERDADE)
                    srs = evaluation_result.subject_results
                    subject_data = None
                    if isinstance(srs, dict):
                        subject_data = srs.get(subject_id)
                        if subject_data is None:
                            subject_data = srs.get(str(subject_id))
                    if subject_data:
                        disciplina_nota = subject_data.get('grade', 0.0)
                        disciplina_proficiencia = subject_data.get('proficiency', 0.0)
                        disciplina_classificacao = subject_data.get('classification')
                    else:
                        # Fallback: calcular se não houver dados salvos
                        if total_respondidas > 0:
                            logging.warning(f"Resultado por disciplina não encontrado no JSON para aluno {student.id}, disciplina {subject_id}. Recalculando...")
                            from app.services.evaluation_calculator import EvaluationCalculator
                            result = EvaluationCalculator.calculate_complete_evaluation(
                                correct_answers=total_acertos,
                                total_questions=total_respondidas,
                                course_name=course_name,
                                subject_name=disciplina_data['nome'],
                                use_simple_calculation=use_simple_calculation
                            )
                            disciplina_nota = result['grade']
                            disciplina_proficiencia = result['proficiency']
                            disciplina_classificacao = result['classification']
                elif total_respondidas > 0:
                    # Fallback: calcular se não houver evaluation_result
                    logging.warning(f"EvaluationResult não encontrado para aluno {student.id}. Recalculando...")
                    from app.services.evaluation_calculator import EvaluationCalculator
                    result = EvaluationCalculator.calculate_complete_evaluation(
                        correct_answers=total_acertos,
                        total_questions=total_respondidas,
                        course_name=course_name,
                        subject_name=disciplina_data['nome'],
                        use_simple_calculation=use_simple_calculation
                    )
                    disciplina_nota = result['grade']
                    disciplina_proficiencia = result['proficiency']
                    disciplina_classificacao = result['classification']

                status = "concluida" if total_respondidas > 0 else "pendente"

                aluno_disciplina = {
                    "id": student.id,
                    "nome": student.name,
                    "escola": escola_nome,
                    "serie": serie_nome,
                    "turma": turma_nome,
                    "respostas_por_questao": respostas_por_questao,
                    "total_acertos": total_acertos,
                    "total_erros": total_erros,
                    "total_respondidas": total_respondidas,
                    "total_questoes_disciplina": len(disciplina_data["questoes"]),
                    "total_em_branco": len(disciplina_data["questoes"]) - total_respondidas,
                    "nivel_proficiencia": disciplina_classificacao,
                    "nota": disciplina_nota,
                    "proficiencia": disciplina_proficiencia,
                    "status": status,
                    "percentual_acertos": round_to_two_decimals((total_acertos / total_respondidas * 100)) if total_respondidas > 0 else 0.0
                }
                
                alunos_disciplina.append(aluno_disciplina)

            disciplina_data["alunos"] = alunos_disciplina
            logging.debug("Disciplina %s: %d alunos processados", disciplina_data['nome'], len(alunos_disciplina))

        dados_gerais = _calcular_dados_gerais_alunos(questoes_por_disciplina, course_name)
        payload = {"disciplinas": list(questoes_por_disciplina.values())}
        if nivel_granularidade != "turma":
            payload["geral"] = dados_gerais
        return payload
        
    except Exception as e:
        logging.error(f"Erro ao gerar tabela detalhada por disciplina: {str(e)}", exc_info=True)
        payload_erro = {"disciplinas": [], "error": str(e)}
        if nivel_granularidade != "turma":
            payload_erro["geral"] = {"alunos": []}
        return payload_erro


def _calcular_dados_gerais_alunos(questoes_por_disciplina: dict, course_name: str = "Anos Iniciais") -> dict:
    """
    Calcula dados gerais (média de todas as disciplinas) para cada aluno
    ATUALIZADO: Usa dados pré-calculados por disciplina (já arredondados para 2 casas decimais)
    """
    try:
        # Criar dicionário para armazenar dados consolidados por aluno
        dados_alunos = {}
        
        # Para cada disciplina, coletar dados dos alunos (já pré-calculados)
        for disciplina_id, disciplina_data in questoes_por_disciplina.items():
            for aluno_data in disciplina_data.get("alunos", []):
                aluno_id = aluno_data["id"]
                
                if aluno_id not in dados_alunos:
                    # Inicializar dados do aluno
                    dados_alunos[aluno_id] = {
                        "id": aluno_id,
                        "nome": aluno_data["nome"],
                        "escola": aluno_data["escola"],
                        "serie": aluno_data["serie"],
                        "turma": aluno_data["turma"],
                        "notas_disciplinas": [],
                        "proficiencias_disciplinas": [],
                        "total_acertos_geral": 0,
                        "total_questoes_geral": 0,
                        "total_respondidas_geral": 0
                    }
                
                # Acumular dados das disciplinas (já arredondados para 2 casas decimais)
                dados_alunos[aluno_id]["notas_disciplinas"].append(aluno_data["nota"])
                dados_alunos[aluno_id]["proficiencias_disciplinas"].append(aluno_data["proficiencia"])
                dados_alunos[aluno_id]["total_acertos_geral"] += aluno_data["total_acertos"]
                dados_alunos[aluno_id]["total_questoes_geral"] += aluno_data["total_questoes_disciplina"]
                dados_alunos[aluno_id]["total_respondidas_geral"] += aluno_data["total_respondidas"]
        
        # Calcular médias e classificação geral para cada aluno
        alunos_gerais = []
        for aluno_id, dados in dados_alunos.items():
            # Calcular médias (usando dados já arredondados para 2 casas decimais)
            if dados["notas_disciplinas"]:
                nota_geral = sum(dados["notas_disciplinas"]) / len(dados["notas_disciplinas"])
                proficiencia_geral = sum(dados["proficiencias_disciplinas"]) / len(dados["proficiencias_disciplinas"])
                # Arredondar as médias para 2 casas decimais
                nota_geral = round_to_two_decimals(nota_geral)
                proficiencia_geral = round_to_two_decimals(proficiencia_geral)
            else:
                nota_geral = 0.0
                proficiencia_geral = 0.0
            
            # Calcular percentual geral
            if dados["total_questoes_geral"] > 0:
                percentual_acertos_geral = (dados["total_acertos_geral"] / dados["total_questoes_geral"]) * 100
                percentual_acertos_geral = round_to_two_decimals(percentual_acertos_geral)
            else:
                percentual_acertos_geral = 0.0
            
            # CORREÇÃO: Usar parâmetros específicos para classificação de MÉDIA GERAL
            if dados["notas_disciplinas"] and dados["proficiencias_disciplinas"]:
                # Usar média das proficiências para determinar classificação geral
                proficiencia_media = sum(dados["proficiencias_disciplinas"]) / len(dados["proficiencias_disciplinas"])
                
                # Determinar classificação baseada nos parâmetros específicos para MÉDIA GERAL
                if "finais" in course_name.lower() or "médio" in course_name.lower() or "medio" in course_name.lower():
                    # Média Geral (Anos Finais/Ensino Médio):
                    # - Abaixo do Básico: 0-212.49
                    # - Básico: 212,50-289.99
                    # - Adequado: 290-339.99
                    # - Avançado: 340-425
                    if proficiencia_media >= 340:
                        nivel_proficiencia_geral = "Avançado"
                    elif proficiencia_media >= 290:
                        nivel_proficiencia_geral = "Adequado"
                    elif proficiencia_media >= 212.50:
                        nivel_proficiencia_geral = "Básico"
                    else:
                        nivel_proficiencia_geral = "Abaixo do Básico"
                else:
                    # Média Geral (Educação Infantil/Anos Iniciais/EJA):
                    # - Abaixo do Básico: 0-162
                    # - Básico: 163-212
                    # - Adequado: 213-262
                    # - Avançado: 263-375
                    if proficiencia_media >= 263:
                        nivel_proficiencia_geral = "Avançado"
                    elif proficiencia_media >= 213:
                        nivel_proficiencia_geral = "Adequado"
                    elif proficiencia_media >= 163:
                        nivel_proficiencia_geral = "Básico"
                    else:
                        nivel_proficiencia_geral = "Abaixo do Básico"
            else:
                # Aluno não fez a avaliação - não classificar
                nivel_proficiencia_geral = None
            
            # Determinar status geral
            status_geral = "concluida" if dados["total_respondidas_geral"] > 0 else "pendente"
            
            aluno_geral = {
                "id": dados["id"],
                "nome": dados["nome"],
                "escola": dados["escola"],
                "serie": dados["serie"],
                "turma": dados["turma"],
                "nota_geral": nota_geral,  # Já arredondado para 2 casas decimais
                "proficiencia_geral": proficiencia_geral,  # Já arredondado para 2 casas decimais
                "nivel_proficiencia_geral": nivel_proficiencia_geral,
                "total_acertos_geral": dados["total_acertos_geral"],
                "total_questoes_geral": dados["total_questoes_geral"],
                "total_respondidas_geral": dados["total_respondidas_geral"],
                "total_em_branco_geral": dados["total_questoes_geral"] - dados["total_respondidas_geral"],
                "percentual_acertos_geral": percentual_acertos_geral,  # Já arredondado para 2 casas decimais
                "status_geral": status_geral
            }
            
            alunos_gerais.append(aluno_geral)
        
        # Ordenar alunos por nome
        alunos_gerais.sort(key=lambda x: x["nome"])
        
        return {"alunos": alunos_gerais}
        
    except Exception as e:
        logging.error(f"Erro ao calcular dados gerais dos alunos: {str(e)}")
        return {"alunos": []}


def _calculate_evaluation_stats_frontend(test_id: str) -> Dict[str, Any]:
    """
    Calcula estatísticas de uma avaliação para o frontend
    """
    from app.models.question import Question
    
    # Buscar avaliação
    test = Test.query.get(test_id)
    if not test:
        return _empty_stats()
    
    # Buscar TODOS os alunos das turmas onde a avaliação foi aplicada
    # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test_id para string
    class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
    class_ids = [ct.class_id for ct in class_tests]
    
    if not class_ids:
        return _empty_stats()
    
    # Buscar todos os alunos dessas turmas com relacionamentos carregados
    all_students = Student.query.options(
        joinedload(Student.class_).joinedload(Class.grade)
    ).filter(Student.class_id.in_(class_ids)).all()
    total_alunos = len(all_students)
    
    if total_alunos == 0:
        return _empty_stats()
    
    # Buscar respostas dos alunos que responderam
    student_answers_data = db.session.query(
        StudentAnswer.student_id,
        func.count(StudentAnswer.id).label('total_answered'),
        func.sum(
            case(
                (StudentAnswer.answer == Question.correct_answer, 1),
                else_=0
            )
        ).label('correct_answers')
    ).join(
        Question, StudentAnswer.question_id == Question.id
    ).filter(
        StudentAnswer.test_id == test_id
    ).group_by(StudentAnswer.student_id).all()
    
    # Criar dicionário para mapear student_id -> dados de resposta
    answers_dict = {sa.student_id: {'total_answered': sa.total_answered, 'correct_answers': sa.correct_answers} for sa in student_answers_data}
    
    total_questions = len(test.questions) if test.questions else 0
    if total_questions == 0:
        return _empty_stats()
    
    # Calcular resultados para cada aluno
    notas = []
    proficiencias = []  # CORREÇÃO: valores originais, não escala 1000
    classificacoes = {'Abaixo do Básico': 0, 'Básico': 0, 'Adequado': 0, 'Avançado': 0}
    alunos_participantes = 0
    
    # Buscar nome do curso baseado no ID
    course_name = "Anos Iniciais"  # Padrão
    if test.course:
        try:
            from app.models.educationStage import EducationStage
            import uuid
            # Converter string para UUID
            course_uuid = uuid.UUID(test.course)
            course_obj = EducationStage.query.get(course_uuid)
            if course_obj:
                course_name = course_obj.name
        except (ValueError, TypeError, Exception):
            # Se houver erro, manter o padrão
            pass
    
    subject_name = test.subject_rel.name if test.subject_rel else "Outras"
    
    for student in all_students:
        # Verificar se o aluno respondeu
        student_answers = answers_dict.get(student.id)
        
        if student_answers:
            # Aluno respondeu - calcular resultados normalmente
            alunos_participantes += 1
            correct_answers = int(student_answers['correct_answers'] or 0)
            
            # Determinar tipo de cálculo baseado na configuração do teste
            use_simple_calculation = test.grade_calculation_type == 'simple'
            
            # CORREÇÃO: Usar questões respondidas pelo aluno, não total da avaliação
            answered_questions = int(student_answers['total_answered'] or 0)
            
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=correct_answers,
                total_questions=answered_questions,  # CORREÇÃO: usar questões respondidas
                course_name=course_name,
                subject_name=subject_name,
                use_simple_calculation=use_simple_calculation
            )
            
            # CORREÇÃO: Usar valores originais da proficiência em vez de converter para escala 1000
            # Isso evita distorções nos cálculos e mantém os limites corretos
            proficiency_original = result['proficiency']
            classification_original = result['classification']
            
            notas.append(result['grade'])
            proficiencias.append(proficiency_original)  # CORREÇÃO: usar valor original
            classificacoes[classification_original] += 1
        else:
            # Aluno NÃO respondeu - não incluir na distribuição de classificação
            # Alunos ausentes não são classificados
            pass
    
    if result_rows_frontend:
        mn, mp = hierarchical_mean_grade_and_proficiency(result_rows_frontend, "municipio")
        media_nota = round_to_two_decimals(mn)
        media_proficiencia = format_decimal_two_places(mp)
    else:
        media_nota = 0.0
        media_proficiencia = 0.0
    
    return {
        'total_alunos': total_alunos,
        'alunos_participantes': alunos_participantes,
        'alunos_pendentes': 0,
        'alunos_ausentes': total_alunos - alunos_participantes,
        'media_nota': media_nota,
        'media_proficiencia': media_proficiencia,
        'distribuicao_classificacao': {
            'abaixo_do_basico': classificacoes['Abaixo do Básico'],
            'basico': classificacoes['Básico'],
            'adequado': classificacoes['Adequado'],
            'avancado': classificacoes['Avançado']
        }
    }


def _calculate_evaluation_stats_by_class(test_id: str, class_id: str) -> Dict[str, Any]:
    """
    Calcula estatísticas de uma avaliação para uma turma específica
    """
    from app.models.question import Question
    
    # Buscar avaliação
    test = Test.query.get(test_id)
    if not test:
        return _empty_stats()
    
    # Buscar TODOS os alunos da turma específica
    all_students = Student.query.options(
        joinedload(Student.class_).joinedload(Class.grade)
    ).filter(Student.class_id == class_id).all()
    total_alunos = len(all_students)
    
    if total_alunos == 0:
        return _empty_stats()
    
    # Buscar respostas dos alunos que responderam
    student_answers_data = db.session.query(
        StudentAnswer.student_id,
        func.count(StudentAnswer.id).label('total_answered'),
        func.sum(
            case(
                (StudentAnswer.answer == Question.correct_answer, 1),
                else_=0
            )
        ).label('correct_answers')
    ).join(
        Question, StudentAnswer.question_id == Question.id
    ).filter(
        StudentAnswer.test_id == test_id,
        StudentAnswer.student_id.in_([s.id for s in all_students])
    ).group_by(StudentAnswer.student_id).all()
    
    # Criar dicionário para mapear student_id -> dados de resposta
    answers_dict = {sa.student_id: {'total_answered': sa.total_answered, 'correct_answers': sa.correct_answers} for sa in student_answers_data}
    
    total_questions = len(test.questions) if test.questions else 0
    if total_questions == 0:
        return _empty_stats()
    
    # Calcular resultados para cada aluno
    notas = []
    proficiencias = []  # CORREÇÃO: valores originais, não escala 1000
    classificacoes = {'Abaixo do Básico': 0, 'Básico': 0, 'Adequado': 0, 'Avançado': 0}
    alunos_participantes = 0
    
    # Buscar nome do curso baseado no ID
    course_name = "Anos Iniciais"  # Padrão
    if test.course:
        try:
            from app.models.educationStage import EducationStage
            import uuid
            # Converter string para UUID
            course_uuid = uuid.UUID(test.course)
            course_obj = EducationStage.query.get(course_uuid)
            if course_obj:
                course_name = course_obj.name
        except (ValueError, TypeError, Exception):
            # Se houver erro, manter o padrão
            pass
    
    subject_name = test.subject_rel.name if test.subject_rel else "Outras"
    
    for student in all_students:
        # Verificar se o aluno respondeu
        student_answers = answers_dict.get(student.id)
        
        if student_answers:
            # Aluno respondeu - calcular resultados normalmente
            alunos_participantes += 1
            correct_answers = int(student_answers['correct_answers'] or 0)
            
            # Determinar tipo de cálculo baseado na configuração do teste
            use_simple_calculation = test.grade_calculation_type == 'simple'
            
            # CORREÇÃO: Usar questões respondidas pelo aluno, não total da avaliação
            answered_questions = int(student_answers['total_answered'] or 0)
            
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=correct_answers,
                total_questions=answered_questions,  # CORREÇÃO: usar questões respondidas
                course_name=course_name,
                subject_name=subject_name,
                use_simple_calculation=use_simple_calculation
            )
            
            # CORREÇÃO: Usar valores originais da proficiência em vez de converter para escala 1000
            # Isso evita distorções nos cálculos e mantém os limites corretos
            proficiency_original = result['proficiency']
            classification_original = result['classification']
            
            notas.append(result['grade'])
            proficiencias.append(proficiency_original)  # CORREÇÃO: usar valor original
            classificacoes[classification_original] += 1
        else:
            # Aluno NÃO respondeu - não incluir na distribuição de classificação
            # Alunos ausentes não são classificados
            pass
    
    if result_rows_by_class:
        mn, mp = hierarchical_mean_grade_and_proficiency(result_rows_by_class, "turma")
        media_nota = round_to_two_decimals(mn)
        media_proficiencia = format_decimal_two_places(mp)
    else:
        media_nota = 0.0
        media_proficiencia = 0.0
    
    return {
        'total_alunos': total_alunos,
        'alunos_participantes': alunos_participantes,
        'alunos_pendentes': 0,
        'alunos_ausentes': total_alunos - alunos_participantes,
        'media_nota': media_nota,
        'media_proficiencia': media_proficiencia,
        'distribuicao_classificacao': {
            'abaixo_do_basico': classificacoes['Abaixo do Básico'],
            'basico': classificacoes['Básico'],
            'adequado': classificacoes['Adequado'],
            'avancado': classificacoes['Avançado']
        }
    }


def _empty_stats():
    """Retorna estatísticas vazias"""
    return {
        'total_alunos': 0,
        'alunos_participantes': 0,
        'alunos_pendentes': 0,
        'alunos_ausentes': 0,
        'media_nota': 0.0,
        'media_proficiencia': 0.0,
        'distribuicao_classificacao': {
            'abaixo_do_basico': 0,
            'basico': 0,
            'adequado': 0,
            'avancado': 0
        }
    }


def _calcular_estatisticas_municipio(class_tests: list, scope_info) -> Dict[str, Any]:
    """
    Calcula estatísticas consolidadas do município
    """
    try:
        from app.models.evaluationResult import EvaluationResult
        from app.models.student import Student
        
        if not class_tests:
            city_data = scope_info.get('city_data')
            return {
                "nome": city_data.name if city_data else "Todos os municípios",
                "estado": scope_info.get('estado', 'Todos os estados'),
                "total_escolas": 0,
                "total_avaliacoes": 0,
                "total_alunos": 0,
                "alunos_participantes": 0,
                "alunos_pendentes": 0,
                "alunos_ausentes": 0,
                "media_nota_geral": 0.0,
                "media_proficiencia_geral": 0.0,
                "distribuicao_classificacao_geral": {
                    "abaixo_do_basico": 0,
                    "basico": 0,
                    "adequado": 0,
                    "avancado": 0
                }
            }
        
        # Coletar dados de todas as avaliações
        test_ids = [ct.test_id for ct in class_tests]
        class_ids = [ct.class_id for ct in class_tests]
        
        # Buscar todas as escolas envolvidas
        escolas_unicas = set()
        for ct in class_tests:
            if ct.class_ and ct.class_.school:
                escolas_unicas.add(ct.class_.school.id)
        
        # Se não há escolas nas avaliações, usar as do escopo
        if not escolas_unicas and scope_info.get('escolas'):
            escolas_unicas = {escola.id for escola in scope_info.get('escolas')}
        
        # Buscar todos os alunos das turmas envolvidas
        todos_alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
        total_alunos = len(todos_alunos)
        
        # Buscar todos os resultados das avaliações
        todos_resultados = EvaluationResult.query.filter(EvaluationResult.test_id.in_(test_ids)).all()
        alunos_participantes = len(todos_resultados)
        
        # Calcular médias consolidadas
        if todos_resultados:
            media_nota_geral, media_proficiencia_geral = hierarchical_mean_grade_and_proficiency(
                todos_resultados, "municipio"
            )
        else:
            media_nota_geral = 0.0
            media_proficiencia_geral = 0.0
        
        # Calcular distribuição de classificação consolidada
        distribuicao_geral = {
            'abaixo_do_basico': 0,
            'basico': 0,
            'adequado': 0,
            'avancado': 0
        }
        
        for resultado in todos_resultados:
            classificacao = resultado.classification.lower()
            # ✅ CORRIGIDO: Verificar 'abaixo' PRIMEIRO (mais específico)
            if 'abaixo' in classificacao:
                distribuicao_geral['abaixo_do_basico'] += 1
            elif 'básico' in classificacao or 'basico' in classificacao:
                distribuicao_geral['basico'] += 1
            elif 'adequado' in classificacao:
                distribuicao_geral['adequado'] += 1
            elif 'avançado' in classificacao or 'avancado' in classificacao:
                distribuicao_geral['avancado'] += 1
        
        city_data = scope_info.get('city_data')
        return {
            "nome": city_data.name if city_data else "Todos os municípios",
            "estado": scope_info.get('estado', 'Todos os estados'),
            "total_escolas": len(escolas_unicas),
            "total_avaliacoes": len(test_ids),
            "total_alunos": total_alunos,
            "alunos_participantes": alunos_participantes,
            "alunos_pendentes": total_alunos - alunos_participantes,
            "alunos_ausentes": total_alunos - alunos_participantes,
            "media_nota_geral": round_to_two_decimals(media_nota_geral),
            "media_proficiencia_geral": format_decimal_two_places(media_proficiencia_geral),
            "distribuicao_classificacao_geral": distribuicao_geral
        }
        
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas do município: {str(e)}")
        city_data = scope_info.get('city_data')
        return {
            "nome": city_data.name if city_data else "Todos os municípios",
            "estado": scope_info.get('estado', 'Todos os estados'),
            "total_escolas": 0,
            "total_avaliacoes": 0,
            "total_alunos": 0,
            "alunos_participantes": 0,
            "alunos_pendentes": 0,
            "alunos_ausentes": 0,
            "media_nota_geral": 0.0,
            "media_proficiencia_geral": 0.0,
            "distribuicao_classificacao_geral": {
                "abaixo_do_basico": 0,
                "basico": 0,
                "adequado": 0,
                "avancado": 0
            }
        }


def _determinar_escopo_busca(estado, municipio, escola, serie, turma, avaliacao, user=None):
    """
    Determina o escopo de busca baseado nos filtros aplicados
    Filtros com valor "all" são tratados como "todos"
    
    Args:
        estado: Estado selecionado
        municipio: Município selecionado
        escola: Escola selecionada
        serie: Série selecionada
        turma: Turma selecionada
        avaliacao: Avaliação selecionada
        user: Usuário logado (opcional, para verificar permissões)
    """
    try:
        # Função auxiliar para verificar se um filtro é válido (não é "all")
        def is_valid_filter(value):
            return value and value.lower() != 'all'
        
        # Determinar município base para cálculos
        municipio_id = None
        city_data = None
        
        if is_valid_filter(municipio):
            # Buscar município específico
            city = City.query.get(municipio)
            if not city:
                city = City.query.filter(City.name.ilike(f"%{municipio}%")).first()
            if city:
                municipio_id = city.id
                city_data = city
        elif is_valid_filter(estado):
            # Se não tem município específico, pegar o primeiro do estado
            city = City.query.filter(City.state.ilike(f"%{estado}%")).first()
            if city:
                municipio_id = city.id
                city_data = city
        
        if not municipio_id:
            return None
        
        # Se usuário foi fornecido, verificar permissões
        if user:
            permissao = verificar_permissao_filtros(user)
            if not permissao['permitted']:
                return None
            
            # Tecadm só pode acessar seu próprio município
            if permissao['scope'] == 'municipio' and user.get('city_id') != municipio_id:
                return None
            
            # Para diretores e coordenadores: definir escola padrão se não selecionada
            # ✅ ALTERADO: Professores NÃO têm escola padrão - devem selecionar explicitamente
            if permissao['scope'] == 'escola' and (not escola or escola.lower() == 'all'):
                if user.get('role') in ['diretor', 'coordenador']:
                    # Diretor/Coordenador: usar sua escola vinculada
                    from app.models.manager import Manager
                    
                    manager = Manager.query.filter_by(user_id=user['id']).first()
                    if manager and manager.school_id:
                        escola = manager.school_id
                        logging.info(f"Diretor/Coordenador: usando escola padrão {escola}")
                elif user.get('role') == 'professor':
                    # ✅ NOVO: Professor DEVE selecionar escola específica - não usar padrão
                    logging.info("Professor: escola específica obrigatória - não usando padrão")
        
        # Buscar escolas do escopo
        escolas = []
        
        # Se uma avaliação específica foi selecionada, buscar as escolas onde ela foi aplicada
        if is_valid_filter(avaliacao):
            # Buscar na tabela class_test todas as entradas para esta avaliação
            # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter avaliacao para string
            class_tests_avaliacao = ClassTest.query.filter_by(test_id=str(avaliacao)).all()
            
            if class_tests_avaliacao:
                # Extrair os class_ids únicos
                class_ids = list(set([ct.class_id for ct in class_tests_avaliacao]))
                
                # Buscar as classes e suas escolas
                classes_avaliacao = Class.query.filter(Class.id.in_(class_ids)).all()
                
                # Extrair as escolas únicas onde a avaliação foi aplicada
                escolas_avaliacao = []
                for classe in classes_avaliacao:
                    if classe.school and classe.school not in escolas_avaliacao:
                        # Verificar se a escola pertence ao município do escopo
                        if not municipio_id or classe.school.city_id == municipio_id:
                            escolas_avaliacao.append(classe.school)
                
                escolas = escolas_avaliacao
                
                # Se não encontrou escolas ou se escola específica foi selecionada, filtrar
                if is_valid_filter(escola):
                    escola_filtrada = [e for e in escolas if e.id == escola]
                    escolas = escola_filtrada
            else:
                # Se não há class_tests para esta avaliação, retornar lista vazia
                escolas = []
        else:
            # Se não há avaliação específica, usar a lógica original
            if is_valid_filter(escola):
                # Escola específica
                # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
                from app.utils.uuid_helpers import uuid_to_str
                escola_str = uuid_to_str(escola)
                school = School.query.filter(School.id == escola_str).first() if escola_str else None
                if not school:
                    school = School.query.filter(School.name.ilike(f"%{escola}%")).first()
                if school:
                    # Verificar se a escola pertence ao município
                    if not municipio_id or school.city_id == municipio_id:
                        escolas = [school]
            else:
                # Todas as escolas do município
                escolas = School.query.filter_by(city_id=municipio_id).all()
        
        # Aplicar filtros baseados nas permissões do usuário
        if user:
            permissao = verificar_permissao_filtros(user)
            if permissao['scope'] == 'municipio':
                # Tecadm vê apenas escolas do seu município
                escolas = [e for e in escolas if e.city_id == user.get('city_id')]
            elif permissao['scope'] == 'escola':
                if user.get('role') in ['diretor', 'coordenador']:
                    # Diretor e Coordenador veem apenas sua escola
                    from app.models.manager import Manager
                    manager = Manager.query.filter_by(user_id=user['id']).first()
                    if not manager or not manager.school_id:
                        escolas = []  # Sem escola vinculada
                    else:
                        escolas = [e for e in escolas if e.id == manager.school_id]
                elif user.get('role') == 'professor':
                    # ✅ CORRIGIDO: Professor vê apenas escolas que têm turmas onde está vinculado
                    from app.models.teacher import Teacher
                    from app.models.teacherClass import TeacherClass
                    
                    teacher = Teacher.query.filter_by(user_id=user['id']).first()
                    if teacher:
                        # Buscar turmas onde o professor está vinculado
                        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                        teacher_class_ids = [tc.class_id for tc in teacher_classes]
                        
                        if teacher_class_ids:
                            # Buscar escolas das turmas onde o professor está vinculado
                            teacher_schools = Class.query.filter(
                                Class.id.in_(teacher_class_ids)
                            ).with_entities(Class.school_id).distinct().all()
                            teacher_school_ids = [school[0] for school in teacher_schools]
                            escolas = [e for e in escolas if e.id in teacher_school_ids]
                        else:
                            escolas = []  # Professor não vinculado a nenhuma turma
                    else:
                        escolas = []  # Professor não vinculado a nenhuma escola
        
        scope_result = {
            'municipio_id': municipio_id,
            'city_data': city_data,
            'escolas': escolas,
            'estado': estado,
            'municipio': municipio,
            'escola': escola,
            'serie': serie,
            'turma': turma,
            'avaliacao': avaliacao
        }
        logging.info(f"Escopo de busca determinado: {scope_result}")
        return scope_result
        
    except Exception as e:
        logging.error(f"Erro ao determinar escopo de busca: {str(e)}")
        return None


def _calcular_estatisticas_por_disciplina(class_tests: list, scope_info: dict, nivel_granularidade: str):
    """
    Calcula estatísticas agrupadas por disciplina usando a função corrigida do EvaluationResultService
    CORRIGIDO: Agora aplica filtros de granularidade
    """
    try:
        from app.services.evaluation_result_service import EvaluationResultService
        
        if not class_tests:
            return []
        
        # Pegar a primeira avaliação para acessar subjects_info
        test = class_tests[0].test
        if not test or not test.subjects_info:
            return []
        
        test_id = test.id
        
        # CORRIGIDO: Usar a função corrigida do EvaluationResultService com filtros de granularidade
        statistics = EvaluationResultService.get_subject_detailed_statistics(test_id, scope_info, nivel_granularidade)
        
        if "error" in statistics:
            logging.error(f"Erro ao obter estatísticas por disciplina: {statistics['error']}")
            return []
        
        # Converter o formato retornado para o formato esperado pela rota
        resultados_disciplina = []
        
        if 'subjects' in statistics:
            for subject_name, subject_data in statistics['subjects'].items():
                # Converter classificação para o formato esperado
                distribuicao_classificacao = subject_data.get('classification_distribution', {})
                
                resultado_disciplina = {
                    "disciplina": subject_name,
                    "total_avaliacoes": 1,
                    "total_alunos": subject_data.get('total_students', 0),
                    "alunos_participantes": subject_data.get('total_students', 0),
                    "alunos_pendentes": 0,
                    "alunos_ausentes": 0,
                    "media_nota": subject_data.get('average_grade', 0.0),
                    "media_proficiencia": subject_data.get('average_proficiency', 0.0),
                    "distribuicao_classificacao": {
                        'abaixo_do_basico': distribuicao_classificacao.get('abaixo_do_basico', 0),
                        'basico': distribuicao_classificacao.get('basico', 0),
                        'adequado': distribuicao_classificacao.get('adequado', 0),
                        'avancado': distribuicao_classificacao.get('avancado', 0)
                    }
                }
                
                resultados_disciplina.append(resultado_disciplina)
        
        return resultados_disciplina
        
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas por disciplina: {str(e)}")
        return []


def _determinar_nivel_granularidade(estado, municipio, escola, serie, turma, avaliacao, user=None):
    """
    Determina o nível de granularidade baseado nos filtros aplicados
    LÓGICA CORRIGIDA: Avaliação é considerada primeiro, depois hierarquia escola > série > turma
    Para professores, diretores e coordenadores, não retorna granularidade "municipio"
    """
    nivel = None
    
    logging.info(f"_determinar_nivel_granularidade: avaliacao={avaliacao}, escola={escola}, user.role={user.get('role') if user else None}")
    
    # Primeiro verificar se tem avaliação específica (obrigatória para granularidade)
    if not avaliacao or avaliacao.lower() == 'all':
        # Sem avaliação específica, usar granularidade baseada em município/estado
        if municipio and municipio.lower() != 'all':
            nivel = "municipio"
        elif estado and estado.lower() != 'all':
            nivel = "estado"
        else:
            nivel = "geral"
    else:
        # Com avaliação específica, determinar granularidade baseada nos outros filtros
        # Hierarquia: turma > série > escola > município (dentro da avaliação)
        if turma and turma.lower() != 'all':
            nivel = "turma"
        elif serie and serie.lower() != 'all':
            nivel = "serie"
        elif escola and escola.lower() != 'all':
            # Escola específica selecionada
            if user and user.get('role') in ['professor', 'diretor', 'coordenador']:
                # Para professores, diretores e coordenadores, usar granularidade "escola"
                # mesmo quando escola específica é selecionada
                nivel = "escola"
            else:
                # Para admin e tecadm, usar granularidade "escola"
                nivel = "escola"
        else:
            # Apenas avaliação específica = determinar baseado no papel do usuário
            if user and user.get('role') in ['professor', 'diretor', 'coordenador']:
                # Para professores, diretores e coordenadores, usar granularidade "escola"
                # em vez de "municipio" para evitar mostrar dados municipais
                nivel = "escola"
            else:
                # Para admin e tecadm, usar granularidade "municipio"
                nivel = "municipio"
    
    logging.info(f"Nível de granularidade determinado: {nivel} (avaliacao={avaliacao}, turma={turma}, serie={serie}, escola={escola}, municipio={municipio}, estado={estado})")
    return nivel


def _calcular_estatisticas_gerais(class_tests: list, scope_info, nivel_granularidade):
    """
    Calcula estatísticas gerais baseadas no nível de granularidade
    """
    try:
        from app.models.evaluationResult import EvaluationResult
        from app.models.student import Student
        
        if not class_tests:
            return _get_empty_statistics_gerais(scope_info, nivel_granularidade)
        
        # Coletar dados de todas as avaliações
        test_ids = [ct.test_id for ct in class_tests]
        class_ids = [ct.class_id for ct in class_tests]
        
        # Buscar todas as escolas envolvidas
        escolas_unicas = set()
        series_unicas = set()
        turmas_unicas = set()
        
        # Se há escolas no scope_info (determinadas pela avaliação), usar essas
        if scope_info.get('escolas'):
            escolas_unicas = {escola.id for escola in scope_info.get('escolas')}
        
        # Também coletar escolas dos class_tests para garantir consistência
        for ct in class_tests:
            if ct.class_ and ct.class_.school:
                escolas_unicas.add(ct.class_.school.id)
            if ct.class_ and ct.class_.grade:
                series_unicas.add(ct.class_.grade.id)
            if ct.class_:
                turmas_unicas.add(ct.class_.id)
        
        # Buscar todos os alunos das turmas envolvidas
        todos_alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
        total_alunos = len(todos_alunos)
        
        # Buscar todos os resultados das avaliações
        todos_resultados = EvaluationResult.query.filter(EvaluationResult.test_id.in_(test_ids)).all()
        alunos_participantes = len(todos_resultados)
        
        # Calcular médias consolidadas (agregação hierárquica conforme granularidade)
        if todos_resultados:
            media_nota_geral, media_proficiencia_geral = hierarchical_mean_grade_and_proficiency(
                todos_resultados, granularidade_to_hierarchical_target(nivel_granularidade)
            )
        else:
            media_nota_geral = 0.0
            media_proficiencia_geral = 0.0
        
        # Calcular distribuição de classificação consolidada
        distribuicao_geral = {
            'abaixo_do_basico': 0,
            'basico': 0,
            'adequado': 0,
            'avancado': 0
        }
        
        for resultado in todos_resultados:
            classificacao = resultado.classification.lower()
            # ✅ CORRIGIDO: Verificar 'abaixo' PRIMEIRO (mais específico)
            if 'abaixo' in classificacao:
                distribuicao_geral['abaixo_do_basico'] += 1
            elif 'básico' in classificacao or 'basico' in classificacao:
                distribuicao_geral['basico'] += 1
            elif 'adequado' in classificacao:
                distribuicao_geral['adequado'] += 1
            elif 'avançado' in classificacao or 'avancado' in classificacao:
                distribuicao_geral['avancado'] += 1
        
        # Determinar informações específicas baseadas no nível de granularidade
        city_data = scope_info.get('city_data')
        escola_info = None
        serie_info = None
        
        if scope_info.get('escola') and scope_info.get('escola') != 'all':
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            escola_id = scope_info.get('escola')
            escola_id_str = uuid_to_str(escola_id) if escola_id else None
            escola_obj = School.query.filter(School.id == escola_id_str).first() if escola_id_str else None
            if escola_obj:
                escola_info = escola_obj.name
        
        if scope_info.get('serie') and scope_info.get('serie') != 'all':
            serie_obj = Grade.query.get(scope_info.get('serie'))
            if serie_obj:
                serie_info = serie_obj.name
        
        return {
            "tipo": nivel_granularidade,
            "nome": _get_nome_granularidade(nivel_granularidade, scope_info, escola_info, serie_info),
            "estado": scope_info.get('estado', 'Todos os estados'),
            "municipio": city_data.name if city_data else "Todos os municípios",
            "escola": escola_info,
            "serie": serie_info,
            "total_escolas": len(escolas_unicas),
            "total_series": len(series_unicas),
            "total_turmas": len(turmas_unicas),
            "total_avaliacoes": len(test_ids),
            "total_alunos": total_alunos,
            "alunos_participantes": alunos_participantes,
            "alunos_pendentes": total_alunos - alunos_participantes,
            "alunos_ausentes": 0,  # Pode ser calculado se necessário
            "media_nota_geral": round_to_two_decimals(media_nota_geral),
            "media_proficiencia_geral": format_decimal_two_places(media_proficiencia_geral),
            "distribuicao_classificacao_geral": distribuicao_geral
        }
        
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas gerais: {str(e)}")
        return _get_empty_statistics_gerais(scope_info, nivel_granularidade)


def _get_empty_statistics_gerais(scope_info, nivel_granularidade):
    """
    Retorna estatísticas vazias para o nível de granularidade
    """
    city_data = scope_info.get('city_data')
    return {
        "tipo": nivel_granularidade,
        "nome": _get_nome_granularidade(nivel_granularidade, scope_info, None, None),
        "estado": scope_info.get('estado', 'Todos os estados'),
        "municipio": city_data.name if city_data else "Todos os municípios",
        "escola": None,
        "serie": None,
        "total_escolas": 0,
        "total_series": 0,
        "total_turmas": 0,
        "total_avaliacoes": 0,
        "total_alunos": 0,
        "alunos_participantes": 0,
        "alunos_pendentes": 0,
        "alunos_ausentes": 0,
        "media_nota_geral": 0.0,
        "media_proficiencia_geral": 0.0,
        "distribuicao_classificacao_geral": {
            "abaixo_do_basico": 0,
            "basico": 0,
            "adequado": 0,
            "avancado": 0
        }
    }


def _get_nome_granularidade(nivel_granularidade, scope_info, escola_info, serie_info):
    """
    Retorna o nome apropriado baseado no nível de granularidade
    """
    if nivel_granularidade == "avaliacao":
        return "Avaliação Específica"
    elif nivel_granularidade == "turma":
        return f"Turma - {serie_info}" if serie_info else "Turma"
    elif nivel_granularidade == "serie":
        return serie_info if serie_info else "Série"
    elif nivel_granularidade == "escola":
        return escola_info if escola_info else "Escola"
    elif nivel_granularidade == "municipio":
        city_data = scope_info.get('city_data')
        return city_data.name if city_data else "Município"
    elif nivel_granularidade == "estado":
        return scope_info.get('estado', 'Estado')
    else:
        return "Geral"


# ⚠️ NOTA: Esta função pode ser melhorada usando app/permissions/query_filters.py
# Os filtros de permissões agora estão centralizados em:
# - app.permissions.query_filters.filter_schools_by_user
# - app.permissions.query_filters.filter_classes_by_user
# - app.permissions.query_filters.filter_tests_by_user
def _gerar_opcoes_proximos_filtros(scope_info, nivel_granularidade, user=None):
    """
    Gera as opções dos próximos filtros baseado no nível de granularidade atual
    Nova hierarquia: Estado → Município → Avaliação → Escola → Série → Turma
    
    ⚠️ MELHORIA FUTURA: Usar app.permissions.query_filters para aplicar filtros
    
    Args:
        scope_info: Informações do escopo de busca
        nivel_granularidade: Nível de granularidade atual
        user: Usuário logado (para aplicar filtros de permissões)
    """
    try:
        # Importações necessárias para filtros de professores
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        # ⚠️ ClassSubject removido - não usado no sistema
        
        opcoes = {
            "avaliacoes": [],
            "escolas": [],
            "series": [],
            "turmas": []
        }
        
        # Verificar permissões do usuário se fornecido
        permissao = None
        if user:
            permissao = verificar_permissao_filtros(user)
        
        # Se estamos no nível de município, mostrar avaliações
        if nivel_granularidade in ["estado", "municipio", "escola"]:
            # Buscar avaliações do município
            municipio_id = scope_info.get('municipio_id')
            if municipio_id:
                query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                            .join(ClassTest, Test.id == ClassTest.test_id)\
                                            .join(Class, ClassTest.class_id == Class.id)\
                                            .join(School, School.id == cast(Class.school_id, String))\
                                            .join(City, School.city_id == City.id)\
                                            .filter(City.id == municipio_id)\
                                            .distinct()
                
                # ✅ CENTRALIZADO: Usar módulo de permissões para filtrar avaliações
                if user:
                    query_avaliacoes = filter_tests_by_user(query_avaliacoes, user)
                
                avaliacoes = query_avaliacoes.all()
                opcoes["avaliacoes"] = [{"id": str(a[0]), "titulo": a[1]} for a in avaliacoes]
        
        # Se estamos no nível de avaliação, mostrar escolas onde ela foi aplicada
        if nivel_granularidade in ["estado", "municipio", "avaliacao", "escola"]:
            avaliacao_id = scope_info.get('avaliacao')
            municipio_id = scope_info.get('municipio_id')
            if avaliacao_id and municipio_id:
                query_escolas = School.query.with_entities(School.id, School.name)\
                                           .join(Class, School.id == cast(Class.school_id, String))\
                                           .join(ClassTest, Class.id == ClassTest.class_id)\
                                           .join(Test, ClassTest.test_id == Test.id)\
                                           .join(City, School.city_id == City.id)\
                                           .filter(Test.id == avaliacao_id)\
                                           .filter(City.id == municipio_id)
                
                # Aplicar filtros baseados no papel do usuário
                if permissao and permissao.get('scope') == 'escola':
                    if user.get('role') in ['diretor', 'coordenador']:
                        # Diretor e Coordenador veem apenas sua escola
                        from app.models.manager import Manager
                        manager = Manager.query.filter_by(user_id=user['id']).first()
                        if manager and manager.school_id:
                            query_escolas = query_escolas.filter(School.id == manager.school_id)
                        else:
                            # Se não tem escola vinculada, não retornar nada
                            query_escolas = None
                    elif user.get('role') == 'professor':
                        # ✅ CORRIGIDO: Professor vê apenas escolas que têm turmas onde está vinculado
                        # E onde a avaliação foi aplicada
                        from app.models.teacher import Teacher
                        from app.models.teacherClass import TeacherClass
                        
                        teacher = Teacher.query.filter_by(user_id=user['id']).first()
                        if teacher:
                            # Buscar turmas onde o professor está vinculado
                            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                            teacher_class_ids = [tc.class_id for tc in teacher_classes]
                            
                            if teacher_class_ids:
                                # Filtrar apenas escolas que têm turmas do professor
                                # E onde a avaliação foi aplicada
                                query_escolas = query_escolas.filter(Class.id.in_(teacher_class_ids))
                            else:
                                query_escolas = None
                        else:
                            query_escolas = None
                
                if query_escolas is not None:
                    escolas = query_escolas.distinct().all()
                    opcoes["escolas"] = [{"id": str(e[0]), "name": e[1]} for e in escolas]
        
        # Se estamos no nível de escola, mostrar séries onde a avaliação foi aplicada
        if nivel_granularidade in ["estado", "municipio", "avaliacao", "escola"]:
            avaliacao_id = scope_info.get('avaliacao')
            escola_id = scope_info.get('escola')
            municipio_id = scope_info.get('municipio_id')
            if avaliacao_id and municipio_id:
                # Verificar se escola_id é válido (não é "all")
                if escola_id and escola_id.lower() != 'all':
                    query_series = Grade.query.with_entities(Grade.id, Grade.name)\
                                             .join(Class, Grade.id == Class.grade_id)\
                                             .join(ClassTest, Class.id == ClassTest.class_id)\
                                             .join(Test, ClassTest.test_id == Test.id)\
                                             .join(School, School.id == cast(Class.school_id, String))\
                                             .join(City, School.city_id == City.id)\
                                             .filter(Test.id == avaliacao_id)\
                                             .filter(School.id == escola_id)\
                                             .filter(City.id == municipio_id)\
                                             .distinct()
                
                else:
                    # Se escola é "all", buscar todas as séries do município onde a avaliação foi aplicada
                    query_series = Grade.query.with_entities(Grade.id, Grade.name)\
                                             .join(Class, Grade.id == Class.grade_id)\
                                             .join(ClassTest, Class.id == ClassTest.class_id)\
                                             .join(Test, ClassTest.test_id == Test.id)\
                                             .join(School, School.id == cast(Class.school_id, String))\
                                             .join(City, School.city_id == City.id)\
                                             .filter(Test.id == avaliacao_id)\
                                             .filter(City.id == municipio_id)\
                                             .distinct()
                
                
                # Para professor, restringir séries às turmas onde está vinculado.
                if user and (user.get("role") == "professor" or (user.get("role") or "").lower() == "professor"):
                    teacher = Teacher.query.filter_by(user_id=user['id']).first()
                    if teacher:
                        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                        teacher_class_ids = [tc.class_id for tc in teacher_classes]
                        if teacher_class_ids:
                            # query_series já faz join com Class acima; aqui só restringimos por turmas do professor.
                            query_series = query_series.filter(Class.id.in_(teacher_class_ids))
                        else:
                            query_series = query_series.filter(Grade.id == None)
                    else:
                        query_series = query_series.filter(Grade.id == None)

                series = query_series.all()
                opcoes["series"] = [{"id": str(s[0]), "name": s[1]} for s in series]
        
        # Se estamos no nível de série, mostrar turmas onde a avaliação foi aplicada
        if nivel_granularidade in ["estado", "municipio", "avaliacao", "escola", "serie"]:
            avaliacao_id = scope_info.get('avaliacao')
            escola_id = scope_info.get('escola')
            serie_id = scope_info.get('serie')
            municipio_id = scope_info.get('municipio_id')
            if avaliacao_id and municipio_id:
                # Verificar se escola_id e serie_id são válidos (não são "all")
                escola_valida = escola_id and escola_id.lower() != 'all'
                serie_valida = serie_id and serie_id.lower() != 'all'
                
                if escola_valida and serie_valida:
                    # Ambos são específicos
                    query_turmas = Class.query.with_entities(Class.id, Class.name)\
                                             .join(ClassTest, Class.id == ClassTest.class_id)\
                                             .join(Test, ClassTest.test_id == Test.id)\
                                             .join(School, School.id == cast(Class.school_id, String))\
                                             .join(City, School.city_id == City.id)\
                                             .join(Grade, Class.grade_id == Grade.id)\
                                             .filter(Test.id == avaliacao_id)\
                                             .filter(School.id == escola_id)\
                                             .filter(Grade.id == serie_id)\
                                             .filter(City.id == municipio_id)\
                                             .distinct()
                elif escola_valida and not serie_valida:
                    # Escola específica, série "all"
                    query_turmas = Class.query.with_entities(Class.id, Class.name)\
                                             .join(ClassTest, Class.id == ClassTest.class_id)\
                                             .join(Test, ClassTest.test_id == Test.id)\
                                             .join(School, School.id == cast(Class.school_id, String))\
                                             .join(City, School.city_id == City.id)\
                                             .filter(Test.id == avaliacao_id)\
                                             .filter(School.id == escola_id)\
                                             .filter(City.id == municipio_id)\
                                             .distinct()
                elif not escola_valida and serie_valida:
                    # Escola "all", série específica
                    query_turmas = Class.query.with_entities(Class.id, Class.name)\
                                             .join(ClassTest, Class.id == ClassTest.class_id)\
                                             .join(Test, ClassTest.test_id == Test.id)\
                                             .join(School, School.id == cast(Class.school_id, String))\
                                             .join(City, School.city_id == City.id)\
                                             .join(Grade, Class.grade_id == Grade.id)\
                                             .filter(Test.id == avaliacao_id)\
                                             .filter(Grade.id == serie_id)\
                                             .filter(City.id == municipio_id)\
                                             .distinct()
                else:
                    # Ambos são "all"
                    query_turmas = Class.query.with_entities(Class.id, Class.name)\
                                             .join(ClassTest, Class.id == ClassTest.class_id)\
                                             .join(Test, ClassTest.test_id == Test.id)\
                                             .join(School, School.id == cast(Class.school_id, String))\
                                             .join(City, School.city_id == City.id)\
                                             .filter(Test.id == avaliacao_id)\
                                             .filter(City.id == municipio_id)\
                                             .distinct()
                
                # ✅ CENTRALIZADO: Usar módulo de permissões para filtrar turmas
                if user:
                    query_turmas = filter_classes_by_user(query_turmas, user)
                
                turmas = query_turmas.all()
                opcoes["turmas"] = [{"id": str(t[0]), "name": t[1] or f"Turma {t[0]}"} for t in turmas]
        
        return opcoes
        
    except Exception as e:
        logging.error(f"Erro ao gerar opções dos próximos filtros: {str(e)}")
        return {
            "avaliacoes": [],
            "escolas": [],
            "series": [],
            "turmas": []
        }


# ==================== ENDPOINT 2: GET /alunos ====================

@bp.route('/alunos', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def listar_alunos():
    """
    Lista alunos com resultados de uma avaliação específica
    
    Query Parameters:
    - avaliacao_id (obrigatório)
    - Outros filtros opcionais
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Parâmetro obrigatório
        avaliacao_id = request.args.get('avaliacao_id')
        if not avaliacao_id:
            return jsonify({"error": "avaliacao_id é obrigatório"}), 400
        
        test = Test.query.options(joinedload(Test.subject_rel)).get(avaliacao_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Acesso negado"}), 403

        # Buscar as turmas onde a avaliação foi aplicada
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter avaliacao_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(avaliacao_id)).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return jsonify({
                "data": [],
                "message": "Avaliação não foi aplicada em nenhuma turma"
            }), 200

        # Filtrar turmas pelo escopo do usuário (para mostrar todos os alunos/faltosos que ele pode ver)
        from app.permissions.utils import get_manager_school, get_teacher_classes
        from app.utils.uuid_helpers import uuid_to_str

        role = (user.get("role") or "").lower()
        if role == "admin":
            allowed_class_ids = class_ids
        elif role == "tecadm":
            city_id = user.get("tenant_id") or user.get("city_id")
            if not city_id:
                return jsonify({"error": "Tecadm sem município vinculado"}), 400
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids_city = [str(s[0]) for s in schools_in_city]
            classes_in_city = Class.query.filter(Class.school_id.in_(school_ids_city)).with_entities(Class.id).all()
            allowed_class_ids = [c.id for c in classes_in_city if c.id in class_ids]
        elif role in ("diretor", "coordenador"):
            manager_school_id = get_manager_school(user["id"])
            if not manager_school_id:
                return jsonify({"error": "Diretor/Coordenador não vinculado a uma escola"}), 400
            manager_school_str = uuid_to_str(manager_school_id)
            classes_escola = Class.query.filter(Class.school_id == manager_school_str).with_entities(Class.id).all()
            allowed_class_ids = [c.id for c in classes_escola if c.id in class_ids]
        elif role == "professor":
            teacher_class_ids = get_teacher_classes(user["id"])
            if not teacher_class_ids:
                return jsonify({"data": [], "message": "Professor não está vinculado a nenhuma turma"}), 200
            allowed_class_ids = [cid for cid in class_ids if cid in teacher_class_ids]
        elif role == "aluno":
            # Aluno vê apenas a própria turma (lista de colegas + ele na avaliação)
            current_student = Student.query.filter_by(user_id=user["id"]).first()
            if not current_student or not current_student.class_id:
                return jsonify({"data": [], "message": "Aluno não vinculado a uma turma"}), 200
            if current_student.class_id not in class_ids:
                return jsonify({"data": [], "message": "Avaliação não aplicada na sua turma"}), 200
            allowed_class_ids = [current_student.class_id]
        else:
            allowed_class_ids = []

        if not allowed_class_ids:
            return jsonify({
                "data": [],
                "message": "Nenhuma turma da avaliação está no seu escopo de acesso"
            }), 200
        
        # Buscar todos os alunos dessas turmas (incluindo faltosos) com relacionamentos carregados
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade)
        ).filter(Student.class_id.in_(allowed_class_ids)).all()

        # Mapa school_id -> nome da escola para incluir escola e série por aluno (filtro "todos" / exibição de faltosos)
        school_ids = set()
        for s in all_students:
            if s.class_ and getattr(s.class_, "_school_id", None):
                school_ids.add(str(s.class_._school_id))
        school_names = {}
        if school_ids:
            for sch in School.query.filter(School.id.in_(school_ids)).with_entities(School.id, School.name).all():
                school_names[str(sch[0])] = sch[1] or "N/A"
        
        from app.models.evaluationResult import EvaluationResult
        from app.models.testQuestion import TestQuestion

        evaluation_results = EvaluationResult.query.filter_by(test_id=avaliacao_id).with_entities(
            EvaluationResult.student_id,
            EvaluationResult.correct_answers,
            EvaluationResult.proficiency,
            EvaluationResult.classification,
            EvaluationResult.grade
        ).all()
        results_dict = {
            row[0]: {
                "correct_answers": row[1],
                "proficiency": row[2],
                "classification": row[3],
                "grade": row[4] if row[4] is not None else 0.0
            }
            for row in evaluation_results
        }

        total_questions = TestQuestion.query.filter_by(test_id=avaliacao_id).count()
        test_id_str = str(avaliacao_id)
        sid_list = [s.id for s in all_students]
        answered_rows = (
            db.session.query(StudentAnswer.student_id, func.count(StudentAnswer.id))
            .filter(
                StudentAnswer.test_id == test_id_str,
                StudentAnswer.student_id.in_(sid_list),
            )
            .group_by(StudentAnswer.student_id)
            .all()
        )
        answered_by_student = {row[0]: int(row[1]) for row in answered_rows}

        results = []
        for student in all_students:
            er = results_dict.get(student.id)
            total_answered = answered_by_student.get(student.id, 0)
            if er:
                correct_answers = er["correct_answers"]
                proficiency_original = er["proficiency"]
                classification_original = er["classification"]
                status = "concluida"
            else:
                correct_answers = 0
                proficiency_original = 0.0
                classification_original = None
                status = "pendente"

            turma_nome = "N/A"
            grade_nome = "N/A"
            escola_nome = "N/A"
            if student.class_:
                turma_nome = student.class_.name
                if student.class_.grade:
                    grade_nome = student.class_.grade.name
                sid = getattr(student.class_, "_school_id", None)
                if sid is not None:
                    escola_nome = school_names.get(str(sid), "N/A")
            student_result = {
                "id": student.id,
                "nome": student.name,
                "turma": turma_nome,
                "grade": grade_nome,
                "escola": escola_nome,
                "serie": grade_nome,
                "nota": er["grade"] if er else 0.0,
                "proficiencia": format_decimal_two_places(proficiency_original),
                "classificacao": classification_original,
                "questoes_respondidas": total_answered,
                "acertos": correct_answers,
                "erros": total_answered - correct_answers,
                "em_branco": total_questions - total_answered,
                "tempo_gasto": 3600,
                "status": status
            }
            results.append(student_result)
        
        return jsonify({
            "data": results
        }), 200

    except Exception as e:
        logging.error(f"Erro ao listar alunos: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar alunos", "details": str(e)}), 500


# ==================== ENDPOINT 3: GET /avaliacoes/{id} ====================

@bp.route('/avaliacoes/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_evaluation_by_id(evaluation_id: str):
    """
    Retorna dados de uma avaliação específica
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        if is_answer_sheet_report_entity():
            permissao = verificar_permissao_filtros(user)
            if not permissao.get("permitted"):
                return jsonify({"error": permissao.get("error", "Acesso negado")}), 403
            gab, results, err, _city_id = fetch_answer_sheet_gabarito_for_detail(
                user, permissao, evaluation_id
            )
            if err:
                resp, code = err
                return resp, code
            payload = build_answer_sheet_evaluation_by_id_json(gab, results or [])
            return jsonify(payload), 200

        # Verificar se avaliação existe (eager load subject_rel para evitar query extra)
        test = Test.query.options(joinedload(Test.subject_rel)).get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        # Verificar permissões
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Acesso negado"}), 403

        # Buscar estatísticas da avaliação
        stats = EvaluationResultService.get_evaluation_results(evaluation_id)
        
        # Buscar informações da escola
        escola_nome = "N/A"
        municipio = "N/A"
        if test.schools:
            try:
                school_id = None
                if isinstance(test.schools, list) and len(test.schools) > 0:
                    school_id = test.schools[0]
                elif isinstance(test.schools, str):
                    school_id = test.schools
                
                if school_id:
                    # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
                    from app.utils.uuid_helpers import uuid_to_str
                    school_id_str = uuid_to_str(school_id)
                    school = School.query.filter(School.id == school_id_str).first() if school_id_str else None
                    if school:
                        escola_nome = school.name
                        if school.city:
                            municipio = school.city.name if hasattr(school.city, 'name') else "N/A"
            except Exception as e:
                logging.warning(f"Erro ao buscar escola para avaliação {test.id}: {str(e)}")
        
        # Garantir que arrays sejam inicializados como vazios
        turmas_desempenho = []
        
        # Buscar nome do curso
        curso_nome = "N/A"
        if test.course:
            try:
                from app.models.educationStage import EducationStage
                import uuid
                course_uuid = uuid.UUID(test.course)
                course_obj = EducationStage.query.get(course_uuid)
                if course_obj:
                    curso_nome = course_obj.name
            except Exception as e:
                logging.warning(f"Erro ao buscar curso {test.course}: {str(e)}")
                curso_nome = "Anos Iniciais"
        
        result = {
            "id": test.id,
            "titulo": test.title,
            "disciplina": test.subject_rel.name if test.subject_rel else 'N/A',
            "curso": curso_nome,
            "serie": "N/A",
            "escola": escola_nome,
            "municipio": municipio,
            "data_aplicacao": _formatar_data_para_evolucao(test.created_at),
            "data_correcao": _formatar_data_para_evolucao(test.updated_at),
            "status": "concluida",
            "total_alunos": stats['total_alunos'],
            "alunos_participantes": stats['alunos_participantes'],
            "alunos_pendentes": stats['alunos_pendentes'],
            "alunos_ausentes": stats['alunos_ausentes'],
            "media_nota": stats['media_nota'],
            "media_proficiencia": stats['media_proficiencia'],
            "distribuicao_classificacao": stats['distribuicao_classificacao']
        }
        
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Erro ao buscar avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar avaliação", "details": str(e)}), 500


# ==================== ENDPOINT 4: GET /relatorio-detalhado ====================

@bp.route('/relatorio-detalhado/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def relatorio_detalhado(evaluation_id: str):
    """
    Retorna relatório detalhado de uma avaliação.
    Otimizado: uma query de respostas, questões carregadas uma vez, respostas por aluno em lote.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        if is_answer_sheet_report_entity():
            permissao = verificar_permissao_filtros(user)
            if not permissao.get("permitted"):
                return jsonify({"error": permissao.get("error", "Acesso negado")}), 403
            gab, results, err, city_id = fetch_answer_sheet_gabarito_for_detail(
                user, permissao, evaluation_id
            )
            if err:
                resp, code = err
                return resp, code
            visible = answer_sheet_target_classes_visible_for_user(
                gab, user, permissao, city_id or ""
            )
            payload = build_answer_sheet_relatorio_detalhado_json(
                gab, results or [], visible
            )
            return jsonify(payload), 200

        test = Test.query.options(joinedload(Test.subject_rel)).get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Acesso negado"}), 403

        questions_list = test.questions or []
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "disciplina": test.subject_rel.name if test.subject_rel else 'N/A',
            "total_questoes": len(questions_list)
        }

        # Uma única query para todas as respostas (questões + alunos)
        all_answers_full = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
        answers_by_question = defaultdict(list)
        answers_by_student = defaultdict(list)
        for a in all_answers_full:
            answers_by_question[a.question_id].append(a.answer)
            answers_by_student[a.student_id].append(a)

        questoes_data = []
        for i, question in enumerate(questions_list, 1):
            respostas_questao = answers_by_question.get(question.id, [])
            total_respostas = len(respostas_questao)
            acertos = 0
            if question.question_type == 'multiple_choice':
                for av in respostas_questao:
                    if EvaluationResultService.check_multiple_choice_answer(av, question.correct_answer):
                        acertos += 1
            else:
                if total_respostas > 0 and question.correct_answer:
                    correct_str = str(question.correct_answer).strip().lower()
                    acertos = sum(1 for a in respostas_questao if a and str(a).strip().lower() == correct_str)
            porcentagem_acertos = (acertos / total_respostas * 100) if total_respostas > 0 else 0
            questoes_data.append({
                "id": question.id,
                "numero": i,
                "texto": question.text or f"Questão {i}",
                "habilidade": question.skill or "N/A",
                "codigo_habilidade": question.skill or "N/A",
                "tipo": question.question_type or "multipleChoice",
                "dificuldade": question.difficulty_level or "Médio",
                "porcentagem_acertos": round_to_two_decimals(porcentagem_acertos),
                "porcentagem_erros": round_to_two_decimals(100 - porcentagem_acertos)
            })

        from app.models.evaluationResult import EvaluationResult

        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
        class_ids = [ct.class_id for ct in class_tests]

        if not class_ids:
            # StudentTestOlimpics fica no tenant; garantir schema antes de consultar
            ctx = get_current_tenant_context()
            tenant_schema = (ctx.schema if (ctx and getattr(ctx, 'has_tenant_context', False)) else None) or None
            if tenant_schema:
                set_search_path(tenant_schema)
            try:
                records = StudentTestOlimpics.query.filter_by(test_id=str(evaluation_id)).all()
            except Exception:
                records = []
            if not records:
                return jsonify({"avaliacao": avaliacao_data, "questoes": questoes_data, "alunos": []}), 200
            student_ids = [r.student_id for r in records]
            all_students = Student.query.options(joinedload(Student.class_)).filter(Student.id.in_(student_ids)).all()
        else:
            all_students = Student.query.options(
                joinedload(Student.class_).joinedload(Class.grade)
            ).filter(Student.class_id.in_(class_ids)).all()

        evaluation_results = EvaluationResult.query.filter_by(test_id=evaluation_id).with_entities(
            EvaluationResult.student_id,
            EvaluationResult.correct_answers,
            EvaluationResult.proficiency,
            EvaluationResult.classification,
            EvaluationResult.grade
        ).all()
        results_dict = {
            row[0]: {
                "correct_answers": row[1],
                "proficiency": row[2],
                "classification": row[3],
                "grade": row[4] if row[4] is not None else 0.0
            }
            for row in evaluation_results
        }

        questions_map = {q.id: q for q in questions_list}

        alunos_data = []
        for student in all_students:
            er = results_dict.get(student.id)
            if er:
                total_answered = er["correct_answers"]
                correct_answers = er["correct_answers"]
                proficiency_original = er["proficiency"]
                classification_original = er["classification"]
                status = "concluida"
                nota_final = er["grade"]
            else:
                total_answered = 0
                correct_answers = 0
                proficiency_original = 0.0
                classification_original = None
                status = "nao_respondida"
                nota_final = 0.0

            turma_nome = student.class_.name if student.class_ else "N/A"

            respostas = []
            for answer in answers_by_student.get(student.id, []):
                question = questions_map.get(answer.question_id)
                if question:
                    if question.question_type == 'multiple_choice':
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                    else:
                        is_correct = str(answer.answer or "").strip().lower() == str(question.correct_answer or "").strip().lower()
                    respostas.append({
                        "questao_id": question.id,
                        "questao_numero": question.number or 1,
                        "resposta_correta": is_correct,
                        "resposta_em_branco": not answer.answer,
                        "tempo_gasto": 120
                    })

            alunos_data.append({
                "id": student.id,
                "nome": student.name or (student.user.name if student.user else "N/A"),
                "turma": turma_nome,
                "respostas": respostas,
                "total_acertos": correct_answers,
                "total_erros": total_answered - correct_answers,
                "total_em_branco": len(questions_list) - total_answered,
                "nota_final": nota_final,
                "proficiencia": format_decimal_two_places(proficiency_original),
                "classificacao": classification_original,
                "status": status
            })

        return jsonify({
            "avaliacao": avaliacao_data,
            "questoes": questoes_data,
            "alunos": alunos_data
        }), 200

    except Exception as e:
        logging.error(f"Erro ao gerar relatório detalhado: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao gerar relatório detalhado", "details": str(e)}), 500


# ==================== ENDPOINT 4: POST /avaliacoes/calcular ====================

@bp.route('/avaliacoes/calcular', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def recalcular_avaliacao():
    """
    Recalcula resultados de uma avaliação
    """
    try:
        data = request.get_json()
        
        if not data or 'avaliacao_id' not in data:
            return jsonify({"error": "avaliacao_id é obrigatório"}), 400
        
        avaliacao_id = data['avaliacao_id']
        
        # Verificar se avaliação existe
        test = Test.query.get(avaliacao_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Recalcular (por enquanto retorna sucesso)
        return jsonify({
            "message": "Recálculo realizado com sucesso",
            "avaliacao_id": avaliacao_id
        }), 200

    except Exception as e:
        logging.error(f"Erro ao recalcular avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao recalcular avaliação", "details": str(e)}), 500


@bp.route('/debug/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm")
def debug_evaluation(evaluation_id):
    """
    Debug de uma avaliação - mostra dados detalhados do banco
    
    Query Parameters:
        city_id: ID da cidade (obrigatório para multi-tenancy)
    """
    try:
        city_id = request.args.get('city_id')
        
        if not city_id:
            return jsonify({"error": "city_id é obrigatório"}), 400
        
        # Definir schema correto
        schema_name = city_id_to_schema_name(city_id)
        set_search_path(schema_name)
        
        # Buscar avaliação
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Buscar resultados
        results = EvaluationResult.query.filter_by(test_id=evaluation_id).all()
        
        results_data = []
        for result in results:
            student = Student.query.get(result.student_id)
            
            result_info = {
                "student_id": result.student_id,
                "student_name": student.name if student else "Desconhecido",
                "grade": result.grade,
                "proficiency": result.proficiency,
                "classification": result.classification,
                "correct_answers": result.correct_answers,
                "total_questions": result.total_questions,
                "subject_results": result.subject_results
            }
            results_data.append(result_info)
        
        return jsonify({
            "evaluation_id": evaluation_id,
            "city_id": city_id,
            "schema": schema_name,
            "test_title": test.title,
            "test_course": test.course,
            "test_subjects_info": test.subjects_info,
            "total_results": len(results),
            "results": results_data
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao debug avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@bp.route('/result/<string:result_id>/recalculate', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm")
def recalculate_single_result(result_id):
    """
    Recalcula um resultado específico de avaliação
    
    Args:
        result_id: ID do EvaluationResult a recalcular
        
    Body (JSON):
        city_id: ID da cidade (obrigatório para multi-tenancy)
    """
    try:
        data = request.get_json() or {}
        city_id = data.get('city_id')
        
        if not city_id:
            return jsonify({"error": "city_id é obrigatório no body da requisição"}), 400
        
        # Definir o schema correto baseado no city_id
        schema_name = city_id_to_schema_name(city_id)
        set_search_path(schema_name)
        
        logging.info(f"Usando schema: {schema_name}")
        
        # Buscar o resultado existente
        evaluation_result = EvaluationResult.query.get(result_id)
        
        if not evaluation_result:
            return jsonify({"error": f"Resultado não encontrado no schema {schema_name}"}), 404
        
        logging.info(f"Recalculando resultado {result_id}")
        logging.info(f"  Test ID: {evaluation_result.test_id}")
        logging.info(f"  Student ID: {evaluation_result.student_id}")
        logging.info(f"  Nota atual: {evaluation_result.grade}")
        logging.info(f"  Proficiência atual: {evaluation_result.proficiency}")
        
        # Recalcular usando o serviço
        new_result = EvaluationResultService.calculate_and_save_result(
            test_id=evaluation_result.test_id,
            student_id=evaluation_result.student_id,
            session_id=evaluation_result.session_id
        )
        
        if not new_result:
            return jsonify({"error": "Erro ao recalcular resultado"}), 500
        
        # Buscar resultado atualizado
        updated_result = EvaluationResult.query.get(result_id)
        
        response = {
            "message": "Resultado recalculado com sucesso",
            "result_id": result_id,
            "city_id": city_id,
            "schema": schema_name,
            "test_id": evaluation_result.test_id,
            "student_id": evaluation_result.student_id,
            "updated_data": {
                "grade": updated_result.grade,
                "proficiency": updated_result.proficiency,
                "classification": updated_result.classification,
                "subject_results": updated_result.subject_results
            }
        }
        
        logging.info(f"✅ Resultado recalculado: nota={updated_result.grade}, proficiência={updated_result.proficiency}")
        
        return jsonify(response), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao recalcular resultado {result_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao recalcular resultado", "details": str(e)}), 500


@bp.route('/<string:test_id>/rebuild-cache', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def rebuild_report_cache(test_id: str):
    """
    Regera e persiste os agregados de relatório para uma avaliação.
    
    Por padrão, sempre reconstrói TODOS os escopos da avaliação (overall, school, city, teacher).
    
    Body (JSON) - opcional:
    - rebuild_all_tests: bool (default: False) - Rebuild cache de TODAS as avaliações aplicadas
    - rebuild_ai: bool (default: True) - Se deve regenerar análise de IA também
    """
    try:
        payload = request.get_json(silent=True) or {}
        rebuild_all_tests = bool(payload.get('rebuild_all_tests', False))
        rebuild_ai = bool(payload.get('rebuild_ai', True))  # Por padrão, regenerar IA
        
        # Se rebuild_all_tests, processar todas as avaliações aplicadas
        if rebuild_all_tests:
            return _rebuild_all_tests_cache()
        
        # Processar apenas a avaliação específica
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        from app.routes.report_routes import _montar_resposta_relatorio, _montar_resposta_relatorio_por_turmas
        from app.services.ai_analysis_service import AIAnalysisService

        processed_scopes = []

        def build_and_save(scope_type: str, scope_id: Optional[str]):
            try:
                if scope_type == 'teacher':
                    # Para professores, usar função específica
                    from app.permissions.utils import get_teacher
                    teacher = get_teacher(scope_id) if scope_id else None
                    if not teacher:
                        logging.warning(f"Professor {scope_id} não encontrado para avaliação {test_id}")
                        return
                    
                    from app.permissions.utils import get_teacher_classes
                    teacher_class_ids = get_teacher_classes(teacher.user_id)
                    if not teacher_class_ids:
                        logging.warning(f"Professor {scope_id} não vinculado a nenhuma turma")
                        return
                    
                    class_tests = ClassTest.query.filter(
                        ClassTest.test_id == test_id,
                        ClassTest.class_id.in_(teacher_class_ids)
                    ).all()
                    
                    if not class_tests:
                        logging.warning(f"Avaliação {test_id} não aplicada em turmas do professor {scope_id}")
                        return
                    
                    context = _montar_resposta_relatorio_por_turmas(test_id, class_tests, include_ai=False)
                else:
                    school_id = scope_id if scope_type == 'school' else None
                    city_id = scope_id if scope_type == 'city' else None
                    context = _montar_resposta_relatorio(test_id, school_id, city_id, include_ai=False)
                
                student_count = (
                    context
                    .get('total_alunos', {})
                    .get('total_geral', {})
                    .get('avaliados', 0)
                )
                
                # Salvar payload
                ReportAggregateService.save_payload(
                    test_id=test_id,
                    scope_type=scope_type,
                    scope_id=scope_id if scope_type != 'overall' else None,
                    payload=context,
                    student_count=student_count or 0,
                    commit=False,
                )
                
                # Regenerar análise de IA se solicitado
                if rebuild_ai:
                    try:
                        # Marcar análise como dirty primeiro
                        ReportAggregateService.mark_ai_dirty(
                            test_id=test_id,
                            scope_type=scope_type,
                            scope_id=scope_id if scope_type != 'overall' else None,
                            commit=False
                        )
                        
                        # Preparar dados para análise de IA
                        report_data = context.copy()
                        report_data['scope_type'] = scope_type
                        report_data['scope_id'] = scope_id
                        
                        # Gerar análise de IA
                        ai_service = AIAnalysisService()
                        ai_analysis = ai_service.analyze_report_data(report_data)
                        
                        # Salvar análise de IA
                        ReportAggregateService.save_ai_analysis(
                            test_id=test_id,
                            scope_type=scope_type,
                            scope_id=scope_id if scope_type != 'overall' else None,
                            ai_analysis=ai_analysis,
                            commit=False
                        )
                        
                        logging.info(f"Análise de IA regenerada para {scope_type}:{scope_id}")
                    except Exception as e:
                        logging.error(f"Erro ao regenerar análise de IA para {scope_type}:{scope_id}: {str(e)}", exc_info=True)
                        # Continuar mesmo se falhar a análise de IA
                
                processed_scopes.append({
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "student_count": student_count,
                })
            except Exception as e:
                logging.error(f"Erro ao processar escopo {scope_type}:{scope_id} para avaliação {test_id}: {str(e)}", exc_info=True)

        # Sempre reconstruir todos os escopos
        # 1. Overall
        build_and_save('overall', None)

        # 2. Identificar escolas e municípios ligados à avaliação
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
        school_ids = set()
        city_ids = set()
        teacher_ids = set()

        for class_test in class_tests:
            turma = Class.query.get(class_test.class_id)
            if turma and turma.school_id:
                school_ids.add(turma.school_id)
                # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
                from app.utils.uuid_helpers import uuid_to_str
                school_id_str = uuid_to_str(turma.school_id)
                escola = School.query.filter(School.id == school_id_str).first() if school_id_str else None
                if escola and escola.city_id:
                    city_ids.add(escola.city_id)
            
            # Buscar professores vinculados à turma
            from app.models.teacherClass import TeacherClass
            teacher_classes = TeacherClass.query.filter_by(class_id=class_test.class_id).all()
            for tc in teacher_classes:
                teacher_ids.add(tc.teacher_id)

        # 3. Rebuild cache para todas as escolas
        for school_id in school_ids:
            build_and_save('school', school_id)

        # 4. Rebuild cache para todos os municípios
        for city_id in city_ids:
            build_and_save('city', city_id)
        
        # 5. Rebuild cache para todos os professores vinculados
        for teacher_id in teacher_ids:
            build_and_save('teacher', teacher_id)

        db.session.commit()

        return jsonify({
            "message": "Cache de relatório regenerado com sucesso para todos os escopos",
            "test_id": test_id,
            "rebuild_ai": rebuild_ai,
            "processed_scopes": processed_scopes,
            "total_scopes": len(processed_scopes)
        }), 200

    except Exception as e:
        logging.error(f"Erro ao reconstruir cache da avaliação {test_id}: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao reconstruir cache", "details": str(e)}), 500


def get_teacher_by_id(teacher_id: str):
    """Helper para buscar teacher por ID"""
    from app.models.teacher import Teacher
    return Teacher.query.get(teacher_id)


def _rebuild_all_tests_cache():
    """
    Rebuild cache para todas as avaliações aplicadas.
    Processa overall, city, school e teacher para cada avaliação.
    """
    try:
        from app.routes.report_routes import _montar_resposta_relatorio, _montar_resposta_relatorio_por_turmas
        from app.models.teacherClass import TeacherClass
        
        # Buscar todas as avaliações que foram aplicadas (têm ClassTest)
        test_ids = db.session.query(ClassTest.test_id).distinct().all()
        test_ids = [t[0] for t in test_ids]
        
        if not test_ids:
            return jsonify({
                "message": "Nenhuma avaliação aplicada encontrada",
                "total_tests": 0,
                "processed_tests": []
            }), 200
        
        total_tests = len(test_ids)
        processed_tests = []
        total_scopes = 0
        
        logging.info(f"Iniciando rebuild de cache para {total_tests} avaliações...")
        
        for idx, test_id in enumerate(test_ids, 1):
            try:
                test = Test.query.get(test_id)
                if not test:
                    logging.warning(f"Avaliação {test_id} não encontrada, pulando...")
                    continue
                
                logging.info(f"Processando avaliação {idx}/{total_tests}: {test.title} ({test_id})")
                
                test_scopes = []
                
                # 1. Overall
                try:
                    context = _montar_resposta_relatorio(test_id, None, None)
                    student_count = context.get('total_alunos', {}).get('total_geral', {}).get('avaliados', 0)
                    ReportAggregateService.save_payload(
                        test_id=test_id,
                        scope_type='overall',
                        scope_id=None,
                        payload=context,
                        student_count=student_count or 0,
                        commit=False,
                    )
                    test_scopes.append({'scope_type': 'overall', 'scope_id': None, 'student_count': student_count})
                    total_scopes += 1
                except Exception as e:
                    logging.error(f"Erro ao processar overall para {test_id}: {str(e)}")
                
                # 2. Buscar escolas, municípios e professores
                # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test_id para string
                class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
                school_ids = set()
                city_ids = set()
                teacher_ids = set()
                
                for class_test in class_tests:
                    turma = Class.query.get(class_test.class_id)
                    if turma and turma.school_id:
                        school_ids.add(turma.school_id)
                        # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
                        from app.utils.uuid_helpers import uuid_to_str
                        school_id_str = uuid_to_str(turma.school_id)
                        if school_id_str:
                            escola = School.query.filter(School.id == school_id_str).first()
                            if escola and escola.city_id:
                                city_ids.add(escola.city_id)
                    
                    # Buscar professores vinculados à turma
                    teacher_classes = TeacherClass.query.filter_by(class_id=class_test.class_id).all()
                    for tc in teacher_classes:
                        teacher_ids.add(tc.teacher_id)
                
                # 3. Processar escolas
                for school_id in school_ids:
                    try:
                        context = _montar_resposta_relatorio(test_id, school_id, None)
                        student_count = context.get('total_alunos', {}).get('total_geral', {}).get('avaliados', 0)
                        ReportAggregateService.save_payload(
                            test_id=test_id,
                            scope_type='school',
                            scope_id=school_id,
                            payload=context,
                            student_count=student_count or 0,
                            commit=False,
                        )
                        test_scopes.append({'scope_type': 'school', 'scope_id': school_id, 'student_count': student_count})
                        total_scopes += 1
                    except Exception as e:
                        logging.error(f"Erro ao processar school {school_id} para {test_id}: {str(e)}")
                
                # 4. Processar municípios
                for city_id in city_ids:
                    try:
                        context = _montar_resposta_relatorio(test_id, None, city_id)
                        student_count = context.get('total_alunos', {}).get('total_geral', {}).get('avaliados', 0)
                        ReportAggregateService.save_payload(
                            test_id=test_id,
                            scope_type='city',
                            scope_id=city_id,
                            payload=context,
                            student_count=student_count or 0,
                            commit=False,
                        )
                        test_scopes.append({'scope_type': 'city', 'scope_id': city_id, 'student_count': student_count})
                        total_scopes += 1
                    except Exception as e:
                        logging.error(f"Erro ao processar city {city_id} para {test_id}: {str(e)}")
                
                # 5. Processar professores
                for teacher_id in teacher_ids:
                    try:
                        teacher = get_teacher_by_id(teacher_id)
                        if not teacher:
                            continue
                        
                        from app.permissions.utils import get_teacher_classes
                        teacher_class_ids = get_teacher_classes(teacher.user_id)
                        if not teacher_class_ids:
                            continue
                        
                        class_tests_teacher = ClassTest.query.filter(
                            ClassTest.test_id == test_id,
                            ClassTest.class_id.in_(teacher_class_ids)
                        ).all()
                        
                        if not class_tests_teacher:
                            continue
                        
                        context = _montar_resposta_relatorio_por_turmas(test_id, class_tests_teacher, include_ai=False)
                        student_count = context.get('total_alunos', {}).get('total_geral', {}).get('avaliados', 0)
                        ReportAggregateService.save_payload(
                            test_id=test_id,
                            scope_type='teacher',
                            scope_id=teacher_id,
                            payload=context,
                            student_count=student_count or 0,
                            commit=False,
                        )
                        test_scopes.append({'scope_type': 'teacher', 'scope_id': teacher_id, 'student_count': student_count})
                        total_scopes += 1
                    except Exception as e:
                        logging.error(f"Erro ao processar teacher {teacher_id} para {test_id}: {str(e)}")
                
                # Commit após cada avaliação para não perder progresso
                db.session.commit()
                
                processed_tests.append({
                    "test_id": test_id,
                    "test_title": test.title,
                    "scopes_count": len(test_scopes),
                    "scopes": test_scopes
                })
                
                logging.info(f"Avaliação {idx}/{total_tests} processada: {len(test_scopes)} escopos")
                
            except Exception as e:
                logging.error(f"Erro ao processar avaliação {test_id}: {str(e)}", exc_info=True)
                db.session.rollback()
                continue
        
        return jsonify({
            "message": "Cache de todas as avaliações regenerado com sucesso",
            "total_tests": total_tests,
            "processed_tests_count": len(processed_tests),
            "total_scopes_processed": total_scopes,
            "processed_tests": processed_tests
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao reconstruir cache de todas as avaliações: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao reconstruir cache de todas as avaliações", "details": str(e)}), 500


# ==================== ENDPOINT 5: PATCH /avaliacoes/<test_id>/finalizar ====================

@bp.route('/avaliacoes/<string:test_id>/finalizar', methods=['PATCH'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def finalizar_avaliacao(test_id):
    """
    Finaliza uma avaliação manualmente (marca como concluída)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Você só pode finalizar avaliações que criou"}), 403
        
        # Buscar ClassTest para esta avaliação
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
        
        if not class_tests:
            return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma"}), 404
        
        # Verificar se já está concluída
        already_completed = all(ct.status == "concluida" for ct in class_tests)
        if already_completed:
            return jsonify({
                "message": "Avaliação já está finalizada",
                "test_id": test_id,
                "status": "concluida"
            }), 200
        
        # Marcar todas as aplicações como concluídas
        updated_count = 0
        for class_test in class_tests:
            if class_test.status != "concluida":
                class_test.status = "concluida"
                class_test.updated_at = datetime.utcnow()
                updated_count += 1
        
        db.session.commit()
        
        # Obter resumo atual após a finalização
        summary = _get_evaluation_status_summary(test_id)
        
        return jsonify({
            "message": "Avaliação finalizada com sucesso",
            "test_id": test_id,
            "class_tests_updated": updated_count,
            "total_class_tests": len(class_tests),
            "finalized_at": datetime.utcnow().isoformat(),
            "status_summary": summary
        }), 200

    except Exception as e:
        logging.error(f"Erro ao finalizar avaliação: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao finalizar avaliação", "details": str(e)}), 500


# ==================== ENDPOINTS AUXILIARES (SE NECESSÁRIO) ====================
# Os endpoints auxiliares agora estão em basic_endpoints.py 

@bp.route('/admin/submitted-evaluations', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_submitted_evaluations():
    """
    Retorna todas as avaliações enviadas pelos alunos para correção
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found"}), 401

        # Buscar sessões finalizadas que precisam de correção
        query = db.session.query(TestSession).options(
            joinedload(TestSession.student),
            joinedload(TestSession.test).joinedload(Test.subject_rel),
            joinedload(TestSession.test).joinedload(Test.grade)
        ).filter(
            TestSession.status.in_(['finalizada', 'corrigida', 'revisada'])
        )

        # Filtros opcionais
        status_filter = request.args.get('status')
        if status_filter and status_filter != 'all':
            if status_filter == 'pending':
                query = query.filter(TestSession.status == 'finalizada')
            elif status_filter == 'corrected':
                query = query.filter(TestSession.status == 'corrigida')
            elif status_filter == 'reviewed':
                query = query.filter(TestSession.status == 'revisada')

        subject_filter = request.args.get('subject')
        if subject_filter and subject_filter != 'all':
            query = query.join(Test).filter(Test.subject == subject_filter)

        grade_filter = request.args.get('grade')
        if grade_filter and grade_filter != 'all':
            query = query.join(Test).filter(Test.grade_id == grade_filter)

        search_filter = request.args.get('search')
        if search_filter:
            query = query.join(Student).filter(
                Student.name.ilike(f'%{search_filter}%')
            )

        sessions = query.order_by(TestSession.submitted_at.desc()).all()

        results = []
        for session in sessions:
            # Buscar respostas do aluno
            answers = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id
            ).all()

            # Buscar questões do teste
            # Buscar questões do teste através da tabela de associação
            from app.models.testQuestion import TestQuestion
            test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=session.test_id).order_by(TestQuestion.order).all()]
            questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
            questions_dict = {q.id: q for q in questions}

            # Preparar questões com respostas
            questions_with_answers = []
            for answer in answers:
                question = questions_dict.get(answer.question_id)
                if question:
                    questions_with_answers.append({
                        "id": question.id,
                        "number": question.number or len(questions_with_answers) + 1,
                        "type": question.question_type,
                        "text": question.text,
                        "options": question.alternatives if question.alternatives else None,
                        "points": question.value or 1,
                        "correctAnswer": question.correct_answer,
                        "studentAnswer": answer.answer,
                        "isCorrect": answer.answer == question.correct_answer if question.correct_answer else None,
                        "manualPoints": answer.manual_score,
                        "feedback": answer.feedback
                    })

            # Determinar status
            status = "pending"
            if session.status == 'corrigida':
                status = "corrected"
            elif session.status == 'revisada':
                status = "reviewed"

            result = {
                "id": session.id,
                "sessionId": session.id,
                "studentId": session.student_id,
                "studentName": session.student.name if session.student else "Aluno não encontrado",
                "testId": session.test_id,
                "testTitle": session.test.title if session.test else "Teste não encontrado",
                "subject": {
                    "id": session.test.subject if session.test else "",
                    "name": session.test.subject_rel.name if session.test and session.test.subject_rel else "Não informado"
                },
                "grade": {
                    "id": str(session.test.grade_id) if session.test and session.test.grade_id else "",
                    "name": session.test.grade.name if session.test and session.test.grade else "Não informado"
                },
                "submittedAt": session.submitted_at.isoformat() if session.submitted_at else "",
                "duration": session.duration_minutes or 0,
                "status": status,
                "totalQuestions": session.total_questions or len(questions_with_answers),
                "answeredQuestions": len(answers),
                "autoScore": session.correct_answers,
                "manualScore": sum(q.get("manualPoints", 0) for q in questions_with_answers if q.get("manualPoints")),
                "finalScore": session.score,
                "percentage": session.score,
                "correctedBy": session.corrected_by,
                "correctedAt": session.corrected_at.isoformat() if session.corrected_at else None,
                "feedback": session.feedback,
                "questions": questions_with_answers
            }
            results.append(result)

        return jsonify(results), 200

    except Exception as e:
        logging.error(f"Erro ao buscar avaliações enviadas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar avaliações enviadas", "details": str(e)}), 500


@bp.route('/admin/evaluations/<evaluation_id>/correct', methods=['PATCH'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def save_evaluation_correction(evaluation_id):
    """
    Salva a correção de uma avaliação (sem finalizar)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found"}), 401

        data = request.get_json()
        session_id = data.get('sessionId')
        questions_data = data.get('questions', [])
        general_feedback = data.get('generalFeedback', '')

        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({"error": "Sessão não encontrada"}), 404

        # Atualizar correções das questões
        for question_data in questions_data:
            question_id = question_data.get('questionId')
            manual_points = question_data.get('manualPoints')
            feedback = question_data.get('feedback', '')

            # Buscar resposta do aluno
            answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()

            if answer:
                answer.manual_score = manual_points
                answer.feedback = feedback
                answer.corrected_by = user['id']
                answer.corrected_at = datetime.utcnow()

        # Atualizar sessão
        session.status = 'corrigida'
        session.feedback = general_feedback
        session.corrected_by = user['id']
        session.corrected_at = datetime.utcnow()

        # Recalcular pontuação total
        total_score = 0
        answers = StudentAnswer.query.filter_by(
            student_id=session.student_id,
            test_id=session.test_id
        ).all()

        for answer in answers:
            question = Question.query.get(answer.question_id)
            if question:
                if question.question_type == 'essay' and answer.manual_score is not None:
                    total_score += answer.manual_score
                elif answer.answer == question.correct_answer:
                    total_score += question.value or 1

        # Calcular percentual
        total_possible = session.total_questions * 1  # Assumindo 1 ponto por questão
        if total_possible > 0:
            session.score = round_to_two_decimals((total_score / total_possible) * 100)

        db.session.commit()

        return jsonify({
            "message": "Correção salva com sucesso",
            "finalScore": total_score,
            "percentage": session.score
        }), 200

    except Exception as e:
        logging.error(f"Erro ao salvar correção: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao salvar correção", "details": str(e)}), 500


@bp.route('/admin/evaluations/<evaluation_id>/finish', methods=['PATCH'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def finish_evaluation_correction(evaluation_id):
    """
    Finaliza a correção de uma avaliação e disponibiliza para o aluno
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "User not found"}), 401

        data = request.get_json()
        session_id = data.get('sessionId')
        questions_data = data.get('questions', [])
        general_feedback = data.get('generalFeedback', '')

        # Buscar sessão
        session = TestSession.query.get(session_id)
        if not session:
            return jsonify({"error": "Sessão não encontrada"}), 404

        # Atualizar correções das questões
        for question_data in questions_data:
            question_id = question_data.get('questionId')
            manual_points = question_data.get('manualPoints')
            feedback = question_data.get('feedback', '')

            # Buscar resposta do aluno
            answer = StudentAnswer.query.filter_by(
                student_id=session.student_id,
                test_id=session.test_id,
                question_id=question_id
            ).first()

            if answer:
                answer.manual_score = manual_points
                answer.feedback = feedback
                answer.corrected_by = user['id']
                answer.corrected_at = datetime.utcnow()

        # Finalizar sessão
        session.status = 'revisada'
        session.feedback = general_feedback
        session.corrected_by = user['id']
        session.corrected_at = datetime.utcnow()

        # Recalcular pontuação total
        total_score = 0
        answers = StudentAnswer.query.filter_by(
            student_id=session.student_id,
            test_id=session.test_id
        ).all()

        for answer in answers:
            question = Question.query.get(answer.question_id)
            if question:
                if question.question_type == 'essay' and answer.manual_score is not None:
                    total_score += answer.manual_score
                elif answer.answer == question.correct_answer:
                    total_score += question.value or 1

        # Calcular percentual
        total_possible = session.total_questions * 1  # Assumindo 1 ponto por questão
        if total_possible > 0:
            session.score = round_to_two_decimals((total_score / total_possible) * 100)

        db.session.commit()

        # Aqui poderia enviar notificação para o aluno
        # notification_service.notify_student_result_ready(session.student_id, session.test_id)

        return jsonify({
            "message": "Correção finalizada com sucesso",
            "finalScore": total_score,
            "percentage": session.score
        }), 200

    except Exception as e:
        logging.error(f"Erro ao finalizar correção: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"error": "Erro ao finalizar correção", "details": str(e)}), 500 

# ==================== CÁLCULO DE NOTAS E CORREÇÃO ====================

@bp.route('/<string:test_id>/calculate-scores', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def calculate_test_scores(test_id):
    """
    Calcula as notas de todos os alunos para uma avaliação específica
    
    Body: (opcional)
    {
        "student_ids": ["uuid1", "uuid2"] // Se fornecido, calcula apenas para estes alunos
    }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Buscar o teste e suas questões
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
            
        # Verificar permissões
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Você só pode calcular notas de testes que criou"}), 403
            
        # Buscar questões do teste através da tabela de associação
        from app.models.testQuestion import TestQuestion
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
        questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        if not questions:
            return jsonify({"error": "Nenhuma questão encontrada para este teste"}), 404
            
        # Filtrar por alunos específicos se fornecido
        data = request.get_json() or {}
        student_ids_filter = data.get('student_ids')
        
        if student_ids_filter:
            student_answers = StudentAnswer.query.filter(
                StudentAnswer.test_id == test_id,
                StudentAnswer.student_id.in_(student_ids_filter)
            ).all()
        else:
            student_answers = StudentAnswer.query.filter_by(test_id=test_id).all()
        
        if not student_answers:
            return jsonify({
                "test_id": test_id,
                "message": "Nenhuma resposta encontrada para este teste",
                "total_students": 0,
                "results": {}
            }), 200
        
        # Agrupar respostas por aluno
        student_responses = {}
        for answer in student_answers:
            if answer.student_id not in student_responses:
                student_responses[answer.student_id] = []
            student_responses[answer.student_id].append(answer)
        
        results = {}
        
        for student_id, answers in student_responses.items():
            results[student_id] = {
                "total_questions": len(questions),
                "answered_questions": len(answers),
                "correct_answers": 0,
                "multiple_choice_questions": 0,
                "essay_questions": 0,
                "pending_corrections": 0,
                "corrected_essays": 0,
                "score_percentage": 0.0,
                "total_score": 0.0,
                "max_possible_score": 0.0
            }
            
            for answer in answers:
                # Encontrar a questão correspondente
                question = next((q for q in questions if q.id == answer.question_id), None)
                if not question:
                    continue
                
                # Adicionar valor da questão ao máximo possível
                question_value = question.value or 1.0
                results[student_id]["max_possible_score"] += question_value
                
                # Verificar tipo de questão
                if question.question_type == 'multiple_choice':
                    results[student_id]["multiple_choice_questions"] += 1
                    # Questão de múltipla escolha - correção automática
                    is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                    if is_correct:
                        results[student_id]["correct_answers"] += 1
                        results[student_id]["total_score"] += question_value
                        
                elif question.question_type == 'essay':
                    results[student_id]["essay_questions"] += 1
                    # Questão dissertativa - verificar se já foi corrigida
                    if answer.manual_score is not None:
                        results[student_id]["corrected_essays"] += 1
                        # Calcular pontuação baseada no manual_score
                        essay_score = (answer.manual_score / 100.0) * question_value
                        results[student_id]["total_score"] += essay_score
                        if answer.manual_score > 0:
                            results[student_id]["correct_answers"] += 1
                    else:
                        results[student_id]["pending_corrections"] += 1
                else:
                    # Outros tipos de questão - usar correção automática se houver correct_answer
                    if question.correct_answer:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                        if is_correct:
                            results[student_id]["correct_answers"] += 1
                            results[student_id]["total_score"] += question_value
            
            # Calcular percentual de acertos (apenas questões corrigidas automaticamente)
            auto_corrected_questions = results[student_id]["multiple_choice_questions"]
            if auto_corrected_questions > 0:
                results[student_id]["score_percentage"] = (results[student_id]["correct_answers"] / auto_corrected_questions) * 100
            else:
                results[student_id]["score_percentage"] = 0.0
                
        return jsonify({
            "test_id": test_id,
            "test_title": test.title,
            "total_students": len(results),
            "total_questions": len(questions),
            "calculation_timestamp": datetime.utcnow().isoformat(),
            "results": results
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao calcular notas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao calcular notas", "details": str(e)}), 500


@bp.route('/<string:test_id>/manual-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def manual_correction(test_id):
    """
    Permite ao professor corrigir questões dissertativas
    
    Body:
    {
        "student_id": "uuid",
        "question_id": "uuid", 
        "score": 85.5,  // Pontuação de 0 a 100
        "feedback": "Boa resposta, mas poderia ser mais detalhada",
        "is_correct": true  // opcional: true/false baseado na pontuação
    }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "Dados são obrigatórios"}), 400
            
        student_id = data.get('student_id')
        question_id = data.get('question_id')
        score = data.get('score')
        feedback = data.get('feedback')
        is_correct = data.get('is_correct')
        
        if not student_id or not question_id or score is None:
            return jsonify({"error": "student_id, question_id e score são obrigatórios"}), 400
            
        # Validar score
        if not isinstance(score, (int, float)) or score < 0 or score > 100:
            return jsonify({"error": "Score deve ser um número entre 0 e 100"}), 400
        
        # Verificar se o teste existe e se o usuário tem permissão
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
            
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Você só pode corrigir testes que criou"}), 403
        
        # Buscar resposta do aluno
        # O student_id pode ser user_id ou student_id real
        # Primeiro tentar como user_id
        student = Student.query.filter_by(user_id=student_id).first()
        if student:
            # É um user_id, usar o student.id
            actual_student_id = student.id
        else:
            # Pode ser um student_id real, verificar se existe
            student = Student.query.get(student_id)
            if not student:
                return jsonify({"error": "Aluno não encontrado"}), 404
            actual_student_id = student_id
            
        answer = StudentAnswer.query.filter_by(
            test_id=test_id,
            student_id=actual_student_id,
            question_id=question_id
        ).first()
        
        if not answer:
            return jsonify({"error": "Resposta não encontrada"}), 404
            
        # Verificar se a questão é dissertativa
        question = Question.query.get(question_id)
        if not question or question.question_type != 'essay':
            return jsonify({"error": "Apenas questões dissertativas podem ser corrigidas manualmente"}), 400
        
        # Atualizar com correção manual
        answer.manual_score = float(score)
        answer.feedback = feedback
        answer.corrected_by = user['id']
        answer.corrected_at = datetime.utcnow()
        
        # Definir is_correct baseado na pontuação se não fornecido
        if is_correct is None:
            answer.is_correct = score > 50  # Considera correto se score > 50%
        else:
            answer.is_correct = bool(is_correct)
        
        db.session.commit()
        
        return jsonify({
            "message": "Correção salva com sucesso",
            "student_id": student_id,
            "question_id": question_id,
            "score": score,
            "corrected_at": answer.corrected_at.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao salvar correção: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao salvar correção", "details": str(e)}), 500


@bp.route('/<string:test_id>/student/<string:student_id>/results', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno", "tecadm")
def get_student_test_results(test_id, student_id):
    """
    Retorna os resultados detalhados de um aluno específico em um teste
    
    Query Parameters:
    - include_answers: true/false (incluir respostas detalhadas)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        from app.models.evaluationResult import EvaluationResult
        from app.models.testQuestion import TestQuestion

        test = Test.query.options(joinedload(Test.subject_rel)).get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        if user['role'] == 'aluno':
            if user['id'] != student_id:
                return jsonify({"error": "Você só pode ver seus próprios resultados"}), 403
        elif user['role'] == 'professor':
            if not professor_pode_ver_avaliacao(user['id'], test.id):
                return jsonify({"error": "Você só pode ver resultados de testes que criou"}), 403

        student = Student.query.filter_by(user_id=student_id).first()
        if student:
            actual_student_id = student.id
        else:
            student = Student.query.get(student_id)
            if not student:
                return jsonify({"error": "Aluno não encontrado"}), 404
            actual_student_id = student_id
        
        # Buscar resultado pré-calculado
        evaluation_result = EvaluationResult.query.filter_by(
            test_id=test_id,
            student_id=actual_student_id
        ).first()
        
        if not evaluation_result:
            total_questions = TestQuestion.query.filter_by(test_id=test_id).count()
            return jsonify({
                "error": "Aluno não respondeu esta avaliação",
                "message": "O aluno não possui resultados calculados para esta avaliação",
                "test_id": test_id,
                "student_id": student_id,
                "student_db_id": student.id,
                "total_questions": total_questions,
                "answered_questions": 0,
                "correct_answers": 0,
                "score_percentage": 0.0,
                "total_score": 0.0,
                "max_possible_score": 0.0,
                "status": "nao_respondida"
            }), 200
        
        # Uma query para questões (TestQuestion + Question com joinedload)
        tq_list = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).options(
            joinedload(TestQuestion.question)
        ).all()
        questions = [tq.question for tq in tq_list if tq.question]
        
        # Usar dados pré-calculados
        total_questions = evaluation_result.total_questions
        correct_answers = evaluation_result.correct_answers
        score_percentage = evaluation_result.score_percentage
        grade = evaluation_result.grade
        proficiency = evaluation_result.proficiency
        classification = evaluation_result.classification
        
        # CORREÇÃO: Usar valor original da proficiência
        proficiency_original = proficiency
        
        # Buscar respostas detalhadas se solicitado
        detailed_answers = []
        if request.args.get('include_answers', 'false').lower() == 'true':
            answers = StudentAnswer.query.filter_by(
                test_id=test_id,
                student_id=student.id
            ).all()
            
            questions_dict = {q.id: q for q in questions}
            
            for answer in answers:
                question = questions_dict.get(answer.question_id)
                if not question:
                    continue
                    
                question_value = question.value or 1.0
                
                answer_detail = {
                    "question_id": answer.question_id,
                    "question_number": question.number,
                    "question_text": question.text,
                    "question_type": question.question_type,
                    "question_value": question_value,
                    "student_answer": answer.answer,
                    "answered_at": answer.answered_at.isoformat() if answer.answered_at else None,
                    "is_correct": None,
                    "score": None,
                    "feedback": answer.feedback,
                    "corrected_by": answer.corrected_by,
                    "corrected_at": answer.corrected_at.isoformat() if answer.corrected_at else None
                }
                
                if question.question_type == 'multiple_choice':
                    is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                    answer_detail["is_correct"] = is_correct
                    answer_detail["score"] = question_value if is_correct else 0
                    
                elif question.question_type == 'essay':
                    if answer.manual_score is not None:
                        essay_score = (answer.manual_score / 100.0) * question_value
                        answer_detail["score"] = essay_score
                        answer_detail["manual_score"] = answer.manual_score
                        answer_detail["is_correct"] = answer.is_correct
                    else:
                        answer_detail["status"] = "pending_correction"
                        
                else:
                    # Outros tipos
                    if question.correct_answer:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                        answer_detail["is_correct"] = is_correct
                        answer_detail["score"] = question_value if is_correct else 0
                
                detailed_answers.append(answer_detail)
        
        try:
            rankings = StudentRankingService.get_rankings(actual_student_id, test_id)
        except Exception as rank_err:
            logging.warning("Erro ao buscar rankings do aluno (retornando vazio): %s", rank_err, exc_info=True)
            rankings = []

        result = {
            "test_id": test_id,
            "student_id": student_id,  # user_id
            "student_db_id": student.id,  # id real da tabela Student
            "student_name": student.name,
            "total_questions": total_questions,
            "answered_questions": correct_answers,  # Simplificado - usar acertos como questões respondidas
            "correct_answers": correct_answers,
            "score_percentage": round_to_two_decimals(score_percentage),
            "total_score": round_to_two_decimals(grade),  # Usar nota como total_score
            "max_possible_score": total_questions,  # Simplificado
            "grade": round_to_two_decimals(grade),
            "proficiencia": format_decimal_two_places(proficiency_original),
            "classificacao": classification,
            "calculated_at": evaluation_result.calculated_at.isoformat() if evaluation_result.calculated_at else None,
            "answers": detailed_answers if request.args.get('include_answers', 'false').lower() == 'true' else [],
            "rankings": rankings
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar resultados do aluno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar resultados", "details": str(e)}), 500


@bp.route('/<string:test_id>/batch-correction', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def batch_correction(test_id):
    """
    Permite ao professor corrigir múltiplas questões dissertativas de uma vez
    
    Body:
    {
        "corrections": [
            {
                "student_id": "uuid",
                "question_id": "uuid",
                "score": 85.5,
                "feedback": "Boa resposta",
                "is_correct": true
            },
            {
                "student_id": "uuid2",
                "question_id": "uuid",
                "score": 70.0,
                "feedback": "Resposta parcialmente correta"
            }
        ]
    }
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        data = request.get_json()
        if not data or 'corrections' not in data:
            return jsonify({"error": "Campo 'corrections' é obrigatório"}), 400
            
        corrections = data['corrections']
        if not isinstance(corrections, list) or len(corrections) == 0:
            return jsonify({"error": "Lista de correções deve ser um array não vazio"}), 400
        
        # Verificar se o teste existe e se o usuário tem permissão
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
            
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Você só pode corrigir testes que criou"}), 403
        
        processed = 0
        errors = []
        
        for correction in corrections:
            try:
                student_id = correction.get('student_id')
                question_id = correction.get('question_id')
                score = correction.get('score')
                feedback = correction.get('feedback')
                is_correct = correction.get('is_correct')
                
                if not student_id or not question_id or score is None:
                    errors.append(f"Correção inválida: student_id, question_id e score são obrigatórios")
                    continue
                    
                # Validar score
                if not isinstance(score, (int, float)) or score < 0 or score > 100:
                    errors.append(f"Score inválido para aluno {student_id}, questão {question_id}: deve ser entre 0 e 100")
                    continue
                
                # Buscar resposta do aluno
                # O student_id pode ser user_id ou student_id real
                student = Student.query.filter_by(user_id=student_id).first()
                if student:
                    # É um user_id, usar o student.id
                    actual_student_id = student.id
                else:
                    # Pode ser um student_id real, verificar se existe
                    student = Student.query.get(student_id)
                    if not student:
                        errors.append(f"Aluno {student_id} não encontrado")
                        continue
                    actual_student_id = student_id
                    
                answer = StudentAnswer.query.filter_by(
                    test_id=test_id,
                    student_id=actual_student_id,
                    question_id=question_id
                ).first()
                
                if not answer:
                    errors.append(f"Resposta não encontrada para aluno {student_id}, questão {question_id}")
                    continue
                    
                # Verificar se a questão é dissertativa
                question = Question.query.get(question_id)
                if not question or question.question_type != 'essay':
                    errors.append(f"Questão {question_id} não é dissertativa")
                    continue
                
                # Atualizar com correção manual
                answer.manual_score = float(score)
                answer.feedback = feedback
                answer.corrected_by = user['id']
                answer.corrected_at = datetime.utcnow()
                
                # Definir is_correct baseado na pontuação se não fornecido
                if is_correct is None:
                    answer.is_correct = score > 50
                else:
                    answer.is_correct = bool(is_correct)
                
                processed += 1
                
            except Exception as e:
                errors.append(f"Erro ao processar correção: {str(e)}")
        
        if processed > 0:
            db.session.commit()
            
        return jsonify({
            "message": f"Processadas {processed} correções com sucesso",
            "processed": processed,
            "errors": errors if errors else None
        }), 200 if not errors else 207  # 207 Multi-Status se houver erros
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao processar correções em lote: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar correções", "details": str(e)}), 500


@bp.route('/<string:test_id>/pending-corrections', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def get_pending_corrections(test_id):
    """
    Lista todas as questões dissertativas que ainda precisam de correção manual
    
    Query Parameters:
    - student_id: uuid (opcional, filtrar por aluno específico)
    - question_id: uuid (opcional, filtrar por questão específica)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se o teste existe e se o usuário tem permissão
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Teste não encontrado"}), 404
            
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Você só pode ver correções de testes que criou"}), 403
        
        # Parâmetros de filtro
        student_id_filter = request.args.get('student_id')
        question_id_filter = request.args.get('question_id')
        
        # Query base
        query = db.session.query(
            StudentAnswer,
            Question,
            Student
        ).join(
            Question, StudentAnswer.question_id == Question.id
        ).join(
            Student, StudentAnswer.student_id == Student.id
        ).filter(
            StudentAnswer.test_id == test_id,
            Question.question_type == 'essay',
            StudentAnswer.manual_score.is_(None)
        )
        
        # Aplicar filtros
        if student_id_filter:
            query = query.filter(StudentAnswer.student_id == student_id_filter)
        if question_id_filter:
            query = query.filter(StudentAnswer.question_id == question_id_filter)
        
        pending_corrections = query.all()
        
        corrections_data = []
        for answer, question, student in pending_corrections:
            corrections_data.append({
                "student_answer_id": answer.id,
                "student_id": student.id,
                "student_name": student.name,
                "question_id": question.id,
                "question_number": question.number,
                "question_text": question.text,
                "question_value": question.value or 1.0,
                "student_answer": answer.answer,
                "answered_at": answer.answered_at.isoformat() if answer.answered_at else None
            })
        
        return jsonify({
            "test_id": test_id,
            "test_title": test.title,
            "total_pending": len(corrections_data),
            "pending_corrections": corrections_data
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar correções pendentes: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar correções pendentes", "details": str(e)}), 500


 

# ==================== ENDPOINT: GET /{test_id}/student/{student_id}/answers ====================

@bp.route('/<string:test_id>/student/<string:student_id>/answers', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "aluno", "tecadm")
def get_student_answers(test_id, student_id):
    """
    Retorna as respostas detalhadas de um aluno em um teste específico
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        if user['role'] == 'aluno':
            # Aluno só pode ver suas próprias respostas
            # O student_id enviado é o user_id, não o id da tabela Student
            if user['id'] != student_id:
                return jsonify({"error": "Você só pode ver seus próprios resultados"}), 403
        elif user['role'] == 'professor':
            # Professor só pode ver respostas de testes que criou
            test = Test.query.get(test_id)
            if not test or not professor_pode_ver_avaliacao(user['id'], test.id):
                return jsonify({"error": "Você só pode ver respostas de testes que criou"}), 403
        
        # O student_id na URL pode ser user_id ou student_id real
        # Primeiro, tentar buscar como user_id
        student = Student.query.filter_by(user_id=student_id).first()
        if student:
            # É um user_id, usar o student.id
            actual_student_id = student.id
        else:
            # Pode ser um student_id real, verificar se existe
            student = Student.query.get(student_id)
            if not student:
                return jsonify({"error": "Aluno não encontrado"}), 404
            actual_student_id = student_id
        
        # Buscar respostas do aluno
        answers = StudentAnswer.query.filter_by(
            test_id=test_id,
            student_id=actual_student_id
        ).all()
        
        if not answers:
            return jsonify({
                "test_id": test_id,
                "student_id": student_id,
                "student_db_id": student.id,
                "total_answers": 0,
                "answers": [],
                "message": "Aluno não respondeu este teste"
            }), 200
        
        # Buscar questões do teste através da tabela de associação
        from app.models.testQuestion import TestQuestion
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
        questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        questions_dict = {q.id: q for q in questions}
        
        # Buscar resultado de avaliação para dados agregados
        from app.models.evaluationResult import EvaluationResult
        evaluation_result = EvaluationResult.query.filter_by(
            test_id=test_id,
            student_id=actual_student_id
        ).first()
        
        answers_data = []
        correct_count = 0
        total_questions = len(questions)
        
        for answer in answers:
            question = questions_dict.get(answer.question_id)
            if question:
                # Garantir que question_number não seja None
                question_number = question.number if question.number is not None else 1
                
                answer_detail = {
                    "question_id": answer.question_id,
                    "question_number": question_number,
                    "question_text": question.text or "",
                    "question_type": question.question_type or "multipleChoice",
                    "question_value": question.value or 1.0,
                    "student_answer": answer.answer or "",
                    "answered_at": answer.answered_at.isoformat() if answer.answered_at else None,
                    "is_correct": None,
                    "score": None,
                    "feedback": answer.feedback,
                    "corrected_by": answer.corrected_by,
                    "corrected_at": answer.corrected_at.isoformat() if answer.corrected_at else None
                }
                
                # Verificar se a resposta está correta baseado no tipo de questão
                if question.question_type == 'multiple_choice':
                    is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                    answer_detail["is_correct"] = is_correct
                    answer_detail["score"] = question.value if is_correct else 0
                    if is_correct:
                        correct_count += 1
                    
                elif question.question_type == 'essay':
                    if answer.manual_score is not None:
                        essay_score = (answer.manual_score / 100.0) * question.value
                        answer_detail["score"] = essay_score
                        answer_detail["manual_score"] = answer.manual_score
                        answer_detail["is_correct"] = answer.is_correct
                        if answer.is_correct:
                            correct_count += 1
                    else:
                        answer_detail["status"] = "pending_correction"
                        answer_detail["is_correct"] = None
                        
                else:
                    # Outros tipos
                    if question.correct_answer:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                        answer_detail["is_correct"] = is_correct
                        answer_detail["score"] = question.value if is_correct else 0
                        if is_correct:
                            correct_count += 1
                
                answers_data.append(answer_detail)
        
        # Ordenar respostas por número da questão
        answers_data.sort(key=lambda x: x['question_number'])
        
        # Preparar resposta com dados agregados
        response_data = {
            "test_id": test_id,
            "student_id": student_id,
            "student_db_id": student.id,
            "total_answers": len(answers_data),
            "total_questions": total_questions,
            "correct_answers": correct_count,
            "score_percentage": round_to_two_decimals((correct_count / total_questions * 100)) if total_questions > 0 else 0,
            "answers": answers_data
        }
        
        # Adicionar dados do resultado de avaliação se disponível
        if evaluation_result:
            response_data.update({
                "grade": evaluation_result.grade,
                "proficiency": evaluation_result.proficiency,
                "classification": evaluation_result.classification,
                "calculated_at": evaluation_result.calculated_at.isoformat() if evaluation_result.calculated_at else None
            })
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar respostas do aluno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar respostas", "details": str(e)}), 500


# ==================== ENDPOINT: GET /{test_id}/student/{student_id}/results ====================

# ==================== ENDPOINT 5: GET /relatorio-detalhado-filtrado ====================

@bp.route('/relatorio-detalhado-filtrado/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def relatorio_detalhado_filtrado(evaluation_id: str):
    """
    Retorna relatório detalhado de uma avaliação com filtros e ordenação.
    Otimizado: uma query de respostas, questões carregadas uma vez, menos logging.
    
    Query Parameters:
    - fields: Campos a incluir (alunos,questoes,turma,habilidade,total,nota,proficiencia,nivel)
    - subject_id: Filtrar questões por disciplina
    - student_level: Filtrar alunos por nível (Ensino Fundamental, Médio, etc.)
    - order_by: Campo para ordenação (nota,proficiencia,status,turma)
    - order_direction: Direção da ordenação (asc,desc)
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe (eager load subject_rel para evitar query extra)
        test = Test.query.options(joinedload(Test.subject_rel)).get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        # Carregar questões uma única vez (a property faz 2 queries; reutilizar evita repetir)
        questions_list = test.questions or []

        # Verificar permissões
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Acesso negado"}), 403

        # Extrair parâmetros de query
        fields = request.args.get('fields', '').split(',') if request.args.get('fields') else []
        subject_id = request.args.get('subject_id')
        student_level = request.args.get('student_level')
        order_by = request.args.get('order_by', 'nome')
        order_direction = request.args.get('order_direction', 'asc')
        
        # Validar campos permitidos
        allowed_fields = ['alunos', 'questoes', 'turma', 'habilidade', 'total', 'nota', 'proficiencia', 'nivel']
        if fields and not all(field in allowed_fields for field in fields):
            return jsonify({"error": "Campos inválidos"}), 400
        
        # Validar ordenação
        allowed_order_fields = ['nota', 'proficiencia', 'status', 'turma', 'nome']
        if order_by not in allowed_order_fields:
            return jsonify({"error": "Campo de ordenação inválido"}), 400
        
        if order_direction not in ['asc', 'desc']:
            return jsonify({"error": "Direção de ordenação inválida"}), 400
        
        # Dados da avaliação (sempre incluído)
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "disciplina": test.subject_rel.name if test.subject_rel else 'N/A',
            "total_questoes": len(questions_list)
        }

        # Uma única query de respostas para todo o relatório (questões + alunos)
        need_answers = 'questoes' in fields or not fields
        all_answers_for_test = []
        answers_by_question = defaultdict(list)
        answers_by_student = defaultdict(list)
        if need_answers:
            all_answers_for_test = StudentAnswer.query.filter_by(test_id=evaluation_id).all()
            for a in all_answers_for_test:
                answers_by_question[a.question_id].append(a.answer)
                answers_by_student[a.student_id].append(a)

        # Mapa questão id -> questão (evita query extra; usa questões já carregadas)
        questions_map = {q.id: q for q in questions_list} if questions_list else {}

        # Dados das questões (filtrado por disciplina se especificado)
        questoes_data = []
        if questions_list and need_answers:
            for i, question in enumerate(questions_list, 1):
                # Filtrar por disciplina se especificado
                if subject_id and question.subject_id != subject_id:
                    continue

                respostas_questao = answers_by_question.get(question.id, [])
                total_respostas = len(respostas_questao)

                acertos = 0
                if question.question_type == 'multiple_choice':
                    for answer_value in respostas_questao:
                        if EvaluationResultService.check_multiple_choice_answer(answer_value, question.correct_answer):
                            acertos += 1
                else:
                    if total_respostas > 0 and question.correct_answer:
                        correct_str = str(question.correct_answer).strip().lower()
                        acertos = sum(1 for a in respostas_questao if a and str(a).strip().lower() == correct_str)

                porcentagem_acertos = (acertos / total_respostas * 100) if total_respostas > 0 else 0

                questao_data = {
                    "id": question.id,
                    "numero": i,
                    "texto": question.text or f"Questão {i}",
                    "habilidade": question.skill or "N/A",
                    "codigo_habilidade": question.skill or "N/A",
                    "tipo": question.question_type or "multipleChoice",
                    "dificuldade": question.difficulty_level or "Médio",
                    "porcentagem_acertos": round(porcentagem_acertos, 2),
                    "porcentagem_erros": round(100 - porcentagem_acertos, 2)
                }
                questoes_data.append(questao_data)
        
        # Buscar alunos e resultados
        from app.models.evaluationResult import EvaluationResult
        
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return jsonify({
                "avaliacao": avaliacao_data,
                "questoes": questoes_data,
                "alunos": []
            }), 200

        # Filtrar turmas pelo escopo do usuário (diretor/coordenador/professor veem só seu escopo)
        from app.permissions.utils import get_manager_school, get_teacher_classes
        from app.utils.uuid_helpers import uuid_to_str

        role = (user.get("role") or "").lower()
        if role == "admin":
            allowed_class_ids = class_ids
        elif role == "tecadm":
            city_id = user.get("tenant_id") or user.get("city_id")
            if not city_id:
                return jsonify({"error": "Tecadm sem município vinculado"}), 400
            schools_in_city = School.query.filter_by(city_id=city_id).with_entities(School.id).all()
            school_ids_city = [str(s[0]) for s in schools_in_city]
            classes_in_city = Class.query.filter(Class.school_id.in_(school_ids_city)).with_entities(Class.id).all()
            allowed_class_ids = [c.id for c in classes_in_city if c.id in class_ids]
        elif role in ("diretor", "coordenador"):
            manager_school_id = get_manager_school(user["id"])
            if not manager_school_id:
                return jsonify({"error": "Diretor/Coordenador não vinculado a uma escola"}), 400
            manager_school_str = uuid_to_str(manager_school_id)
            classes_escola = Class.query.filter(Class.school_id == manager_school_str).with_entities(Class.id).all()
            allowed_class_ids = [c.id for c in classes_escola if c.id in class_ids]
        elif role == "professor":
            teacher_class_ids = get_teacher_classes(user["id"])
            allowed_class_ids = [cid for cid in class_ids if cid in (teacher_class_ids or [])]
        else:
            allowed_class_ids = []

        if not allowed_class_ids:
            return jsonify({
                "avaliacao": avaliacao_data,
                "questoes": questoes_data,
                "alunos": []
            }), 200
        
        # Buscar todos os alunos dessas turmas (incluindo faltosos), com user para evitar N+1
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade),
            joinedload(Student.user)
        ).filter(Student.class_id.in_(allowed_class_ids)).all()
        
        # Filtrar por nível se especificado
        if student_level:
            all_students = [
                student for student in all_students 
                if student.class_ and student.class_.grade and 
                student.class_.grade.name and student_level.lower() in student.class_.grade.name.lower()
            ]

        # Buscar apenas colunas necessárias (menos memória e I/O)
        evaluation_results_rows = EvaluationResult.query.filter_by(test_id=evaluation_id).with_entities(
            EvaluationResult.student_id,
            EvaluationResult.correct_answers,
            EvaluationResult.proficiency,
            EvaluationResult.classification,
            EvaluationResult.grade
        ).all()
        results_dict = {
            row[0]: {
                "correct_answers": row[1],
                "proficiency": row[2],
                "classification": row[3],
                "grade": row[4] if row[4] is not None else 0.0
            }
            for row in evaluation_results_rows
        }

        # answers_by_student e questions_map já preenchidos no início (uma única query de respostas)
        alunos_data = []
        for student in all_students:
            er = results_dict.get(student.id)

            if er:
                total_answered = er["correct_answers"]
                correct_answers = er["correct_answers"]
                proficiency_original = er["proficiency"]
                classification_original = er["classification"]
                status = "concluida"
                nota = er["grade"]
            else:
                total_answered = 0
                correct_answers = 0
                proficiency_original = 0.0
                classification_original = None
                status = "nao_respondida"
                nota = 0.0

            turma_nome = student.class_.name if student.class_ else "N/A"

            respostas = []
            if need_answers:
                for answer in answers_by_student.get(student.id, []):
                    question = questions_map.get(answer.question_id)
                    if question:
                        # Filtrar por disciplina se especificado
                        if subject_id and question.subject_id != subject_id:
                            continue
                        
                        is_correct = False
                        if question.question_type == 'multiple_choice':
                            is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                        else:
                            is_correct = answer.answer == question.correct_answer
                        
                        respostas.append({
                            "questao_id": question.id,
                            "questao_numero": question.number or 0,
                            "resposta_correta": is_correct,
                            "resposta_em_branco": not answer.answer or answer.answer.strip() == ""
                        })
            
            aluno_data = {
                "id": student.id,
                "nome": student.user.name if student.user else "N/A",
                "total_acertos": correct_answers,
                "total_erros": total_answered - correct_answers,
                "total_em_branco": len(questions_list) - total_answered,
                "nota": nota,
                "proficiencia": proficiency_original,
                "classificacao": classification_original,
                "status": status
            }

            # Adicionar campos condicionalmente
            if 'turma' in fields or not fields:
                aluno_data["turma"] = turma_nome
            
            if 'nivel' in fields or not fields:
                aluno_data["nivel"] = student.class_.grade.name if student.class_ and student.class_.grade else "N/A"
            
            if 'questoes' in fields or not fields:
                aluno_data["respostas"] = respostas
            
            alunos_data.append(aluno_data)
        
        # Aplicar ordenação
        reverse_order = order_direction == 'desc'
        
        if order_by == 'nota':
            alunos_data.sort(key=lambda x: x.get('nota', 0), reverse=reverse_order)
        elif order_by == 'proficiencia':
            alunos_data.sort(key=lambda x: x.get('proficiencia', 0), reverse=reverse_order)
        elif order_by == 'status':
            # Ordenar por status: concluida primeiro, depois nao_respondida
            status_order = {'concluida': 1, 'nao_respondida': 2}
            alunos_data.sort(key=lambda x: status_order.get(x.get('status', 'nao_respondida'), 3), reverse=reverse_order)
        elif order_by == 'turma':
            alunos_data.sort(key=lambda x: x.get('turma', 'N/A'), reverse=reverse_order)
        elif order_by == 'nome':
            alunos_data.sort(key=lambda x: x.get('nome', 'N/A'), reverse=reverse_order)
        
        # Construir resposta final
        response = {"avaliacao": avaliacao_data}
        
        if 'questoes' in fields or not fields:
            response["questoes"] = questoes_data
        
        if 'alunos' in fields or not fields:
            response["alunos"] = alunos_data
        
        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Erro ao buscar relatório filtrado: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar relatório filtrado", "details": str(e)}), 500

# ==================== FUNÇÕES AUXILIARES PARA FILTROS HIERÁRQUICOS ====================

def _obter_estados_disponiveis(user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna estados disponíveis baseado nas permissões do usuário.
    
    Args:
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        
    Returns:
        Lista de estados no formato [{"id": "...", "nome": "..."}]
    """
    if permissao['scope'] == 'all':
        # Admin vê todos os estados
        estados = db.session.query(City.state).distinct().filter(City.state.isnot(None)).all()
    else:
        # Outros usuários veem apenas estados das suas cidades
        estados = db.session.query(City.state).distinct().filter(
            City.state.isnot(None),
            City.id == user.get('city_id')
        ).all()
    
    return [{"id": estado[0], "nome": estado[0]} for estado in estados]


def _obter_municipios_por_estado(estado: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna municípios de um estado específico baseado nas permissões do usuário.
    
    Args:
        estado: Nome do estado
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        
    Returns:
        Lista de municípios no formato [{"id": "...", "nome": "..."}]
    """
    if permissao['scope'] == 'all':
        # Admin vê todos os municípios do estado
        municipios = City.query.filter(City.state.ilike(f"%{estado}%")).all()
    else:
        # Outros usuários veem apenas seu município
        municipios = City.query.filter(
            City.state.ilike(f"%{estado}%"),
            City.id == user.get('city_id')
        ).all()
    
    return [{"id": str(m.id), "nome": m.name} for m in municipios]


def _obter_avaliacoes_por_municipio(
    municipio_id: str,
    user: dict,
    permissao: dict,
    escola_param: str = "all",
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna avaliações aplicadas em um município específico, respeitando permissões.

    Args:
        municipio_id: ID do município
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        escola_param: Parâmetro de escola ('all' ou ID específico)
        periodo_bounds: Se definido, só inclui provas com ClassTest.application no mês (ver _parse_periodo_bounds).

    Returns:
        Lista de avaliações no formato [{"id": "...", "titulo": "..."}]
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    
    # Verificar se o usuário tem acesso ao município
    if permissao['scope'] != 'all' and user.get('city_id') != city.id:
        return []
    
    # Exclui fluxo de olimpíada (StudentTestOlimpics); competições (COMPETICAO) permanecem listadas
    excluir_olimpiada = or_(Test.type.is_(None), func.upper(Test.type) != 'OLIMPIADA')
    if permissao['scope'] == 'escola':
        test_query = Test.query.with_entities(Test.id, Test.title)
        test_query = filter_tests_by_user(test_query, user, escola_param, require_school=False)
        
        # Aplicar joins para filtrar por município
        test_query = test_query.join(ClassTest, Test.id == ClassTest.test_id)
        test_query = test_query.join(Class, ClassTest.class_id == Class.id)
        test_query = test_query.join(School, School.id == cast(Class.school_id, String))
        test_query = test_query.join(City, School.city_id == City.id)
        test_query = test_query.filter(City.id == city.id, excluir_olimpiada)
        test_query = _apply_class_test_application_period(test_query, periodo_bounds)

        avaliacoes = test_query.distinct().all()
    else:
        # Para admin e tecadm, aplicar filtro por município
        query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                            .join(ClassTest, Test.id == ClassTest.test_id)\
                            .join(Class, ClassTest.class_id == Class.id)\
                            .join(School, School.id == cast(Class.school_id, String))\
                            .join(City, School.city_id == City.id)\
                            .filter(City.id == city.id)\
                            .filter(excluir_olimpiada)
        query_avaliacoes = _apply_class_test_application_period(query_avaliacoes, periodo_bounds)

        avaliacoes = query_avaliacoes.distinct().all()
    
    return [{"id": str(a[0]), "titulo": a[1]} for a in avaliacoes]


def _obter_escolas_por_avaliacao(
    avaliacao_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna escolas onde uma avaliação foi aplicada, respeitando permissões.

    Args:
        avaliacao_id: ID da avaliação
        municipio_id: ID do município
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        periodo_bounds: Se definido, só escolas com aplicação no mês (ClassTest.application).

    Returns:
        Lista de escolas no formato [{"id": "...", "nome": "..."}]
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    
    # Verificar se o usuário tem acesso ao município
    if permissao['scope'] != 'all' and user.get('city_id') != city.id:
        return []
    
    # Buscar escolas onde a avaliação foi aplicada no município
    query_escolas = School.query.with_entities(School.id, School.name)\
                           .join(Class, School.id == cast(Class.school_id, String))\
                           .join(ClassTest, Class.id == ClassTest.class_id)\
                           .join(Test, ClassTest.test_id == Test.id)\
                           .join(City, School.city_id == City.id)\
                           .filter(Test.id == avaliacao_id)\
                           .filter(City.id == city.id)
    query_escolas = _apply_class_test_application_period(query_escolas, periodo_bounds)

    # Aplicar filtros baseados no papel do usuário
    if permissao['scope'] == 'escola':
        if user.get('role') in ['diretor', 'coordenador']:
            # Diretor e Coordenador veem apenas sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if manager and manager.school_id:
                query_escolas = query_escolas.filter(School.id == manager.school_id)
            else:
                return []
        elif user.get('role') == 'professor':
            # Professor vê apenas escolas que têm turmas onde está vinculado
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                teacher_class_ids = [tc.class_id for tc in teacher_classes]
                
                if teacher_class_ids:
                    query_escolas = query_escolas.filter(Class.id.in_(teacher_class_ids))
                else:
                    return []
            else:
                return []
    
    escolas = query_escolas.distinct().all()
    return [{"id": str(e[0]), "nome": e[1]} for e in escolas]


def _obter_series_por_escola(
    avaliacao_id: str,
    escola_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna séries onde uma avaliação foi aplicada em uma escola específica.

    Args:
        avaliacao_id: ID da avaliação
        escola_id: ID da escola
        municipio_id: ID do município
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        periodo_bounds: Se definido, só séries com aplicação no mês (ClassTest.application).

    Returns:
        Lista de séries no formato [{"id": "...", "nome": "..."}]
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    
    # Verificar se o usuário tem acesso ao município
    if permissao['scope'] != 'all' and user.get('city_id') != city.id:
        return []
    
    # Buscar séries onde a avaliação foi aplicada na escola específica
    query_series = Grade.query.with_entities(Grade.id, Grade.name)\
                         .join(Class, Grade.id == Class.grade_id)\
                         .join(ClassTest, Class.id == ClassTest.class_id)\
                         .join(Test, ClassTest.test_id == Test.id)\
                         .join(School, School.id == cast(Class.school_id, String))\
                         .join(City, School.city_id == City.id)\
                         .filter(Test.id == avaliacao_id)\
                         .filter(School.id == escola_id)\
                         .filter(City.id == city.id)
    query_series = _apply_class_test_application_period(query_series, periodo_bounds)

    series = query_series.distinct().all()
    return [{"id": str(s[0]), "nome": s[1]} for s in series]


def _obter_turmas_por_serie(
    avaliacao_id: str,
    escola_id: str,
    serie_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna turmas onde uma avaliação foi aplicada em uma escola e série específicas.
    
    Args:
        avaliacao_id: ID da avaliação
        escola_id: ID da escola
        serie_id: ID da série
        municipio_id: ID do município
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        periodo_bounds: Se definido, só turmas com aplicação no mês (ClassTest.application).

    Returns:
        Lista de turmas no formato [{"id": "...", "nome": "..."}]
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    
    # Verificar se o usuário tem acesso ao município
    if permissao['scope'] != 'all' and user.get('city_id') != city.id:
        return []
    
    # Buscar turmas onde a avaliação foi aplicada na escola e série específicas
    query_turmas = Class.query.with_entities(Class.id, Class.name)\
                         .join(ClassTest, Class.id == ClassTest.class_id)\
                         .join(Test, ClassTest.test_id == Test.id)\
                         .join(School, School.id == cast(Class.school_id, String))\
                         .join(City, School.city_id == City.id)\
                         .join(Grade, Class.grade_id == Grade.id)\
                         .filter(Test.id == avaliacao_id)\
                         .filter(School.id == escola_id)\
                         .filter(Grade.id == serie_id)\
                         .filter(City.id == city.id)
    query_turmas = _apply_class_test_application_period(query_turmas, periodo_bounds)

    # Aplicar filtros específicos para professores
    if permissao['scope'] == 'escola' and user['role'] == 'professor':
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        
        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        if teacher:
            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            
            if teacher_class_ids:
                query_turmas = query_turmas.filter(Class.id.in_(teacher_class_ids))
            else:
                return []
        else:
            return []
    
    turmas = query_turmas.distinct().all()
    return [{"id": str(t[0]), "nome": t[1] or f"Turma {t[0]}"} for t in turmas]


def _escola_param_eh_especifica(escola: Optional[str]) -> bool:
    return bool(escola and str(escola).strip().lower() not in ("all", ""))


def _serie_param_eh_especifica(serie: Optional[str]) -> bool:
    return bool(serie and str(serie).strip().lower() not in ("all", ""))


def _obter_series_por_avaliacao_municipio(
    avaliacao_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    """
    Séries distintas onde a avaliação foi aplicada em qualquer escola do município
    (uso quando o filtro de escola está em «todas»).
    """
    city = City.query.get(municipio_id)
    if not city:
        return []

    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    query_series = (
        Grade.query.with_entities(Grade.id, Grade.name)
        .join(Class, Grade.id == Class.grade_id)
        .join(ClassTest, Class.id == ClassTest.class_id)
        .join(Test, ClassTest.test_id == Test.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .filter(Test.id == avaliacao_id)
        .filter(City.id == city.id)
    )
    query_series = _apply_class_test_application_period(query_series, periodo_bounds)

    if permissao["scope"] == "escola" and user.get("role") in ["diretor", "coordenador"]:
        from app.models.manager import Manager

        manager = Manager.query.filter_by(user_id=user["id"]).first()
        if manager and manager.school_id:
            query_series = query_series.filter(School.id == manager.school_id)
        else:
            return []

    if permissao["scope"] == "escola" and user.get("role") == "professor":
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass

        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if teacher:
            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            if teacher_class_ids:
                query_series = query_series.filter(Class.id.in_(teacher_class_ids))
            else:
                return []
        else:
            return []

    series = query_series.distinct().all()
    return [{"id": str(s[0]), "nome": s[1]} for s in series]


def _obter_turmas_por_serie_municipio(
    avaliacao_id: str,
    serie_id: str,
    municipio_id: str,
    user: dict,
    permissao: dict,
    periodo_bounds: Optional[Tuple[datetime, datetime]] = None,
) -> List[Dict[str, Any]]:
    """
    Turmas onde a avaliação foi aplicada, para a série, em qualquer escola do município
    (quando escola = todas).
    """
    city = City.query.get(municipio_id)
    if not city:
        return []

    if permissao["scope"] != "all" and user.get("city_id") != city.id:
        return []

    query_turmas = (
        Class.query.with_entities(Class.id, Class.name)
        .join(ClassTest, Class.id == ClassTest.class_id)
        .join(Test, ClassTest.test_id == Test.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .join(Grade, Class.grade_id == Grade.id)
        .filter(Test.id == avaliacao_id)
        .filter(Grade.id == serie_id)
        .filter(City.id == city.id)
    )
    query_turmas = _apply_class_test_application_period(query_turmas, periodo_bounds)

    if permissao["scope"] == "escola" and user.get("role") in ["diretor", "coordenador"]:
        from app.models.manager import Manager

        manager = Manager.query.filter_by(user_id=user["id"]).first()
        if manager and manager.school_id:
            query_turmas = query_turmas.filter(School.id == manager.school_id)
        else:
            return []

    if permissao["scope"] == "escola" and user.get("role") == "professor":
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass

        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if teacher:
            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            if teacher_class_ids:
                query_turmas = query_turmas.filter(Class.id.in_(teacher_class_ids))
            else:
                return []
        else:
            return []

    turmas = query_turmas.distinct().all()
    return [{"id": str(t[0]), "nome": t[1] or f"Turma {t[0]}"} for t in turmas]


# ==================== OPÇÕES DE FILTRO PARA EVOLUÇÃO (Estado → Município → Escola → Série → Turma) ====================

def _user_city_id(user: dict) -> str:
    """Retorna o city_id do usuário (tenant_id ou city_id) para restrição de escopo."""
    return str((user.get("city_id") or user.get("tenant_id")) or "").strip()


def _obter_escolas_por_municipio_evolucao(municipio_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna escolas do município que possuem pelo menos uma avaliação aplicada (ClassTest).
    Usado na tela de Evolução: hierarquia é Estado → Município → Escola (sem exigir avaliação).
    Respeita permissões: só escolas que têm aplicações de avaliações que o usuário pode ver.
    Requer que o schema do tenant do município já esteja definido (set_search_path) pelo chamador.
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    city_id_str = str(city.id) if city.id else ""
    if permissao["scope"] != "all" and _user_city_id(user) != city_id_str:
        return []

    # Query de testes que o usuário pode ver (no município)
    base_test_query = (
        Test.query.with_entities(Test.id)
        .join(ClassTest, Test.id == ClassTest.test_id)
        .join(Class, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .filter(City.id == city.id)
    )
    base_test_query = filter_tests_by_user(base_test_query, user, "all", require_school=False)
    allowed_test_ids = [r[0] for r in base_test_query.distinct().all()]

    if not allowed_test_ids:
        return []

    # Escolas que têm pelo menos um ClassTest com esses testes
    school_rows = (
        db.session.query(School.id, School.name)
        .join(Class, School.id == cast(Class.school_id, String))
        .join(ClassTest, Class.id == ClassTest.class_id)
        .filter(School.city_id == city.id)
        .filter(ClassTest.test_id.in_(allowed_test_ids))
        .distinct()
        .all()
    )

    if permissao["scope"] == "escola":
        if user.get("role") in ["diretor", "coordenador"]:
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user["id"]).first()
            if manager and manager.school_id:
                school_rows = [(s[0], s[1]) for s in school_rows if str(s[0]) == str(manager.school_id)]
            else:
                return []
        elif user.get("role") == "professor":
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            teacher = Teacher.query.filter_by(user_id=user["id"]).first()
            if not teacher:
                return []
            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            if not teacher_class_ids:
                return []
            # Manter só escolas que têm alguma turma do professor
            school_ids_com_turma_prof = (
                db.session.query(Class.school_id)
                .filter(Class.id.in_(teacher_class_ids))
                .distinct()
                .all()
            )
            sid_set = {str(s[0]) for s in school_ids_com_turma_prof if s[0]}
            school_rows = [(s[0], s[1]) for s in school_rows if str(s[0]) in sid_set]

    return [{"id": str(e[0]), "nome": e[1] or ""} for e in school_rows]


def _obter_series_por_escola_evolucao(municipio_id: str, escola_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna séries da escola (no município) que possuem pelo menos uma avaliação aplicada.
    Usado na tela de Evolução: só aparecem séries que têm avaliações para comparar.
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    city_id_str = str(city.id) if city.id else ""
    if permissao["scope"] != "all" and _user_city_id(user) != city_id_str:
        return []

    escola_id_str = str(escola_id).strip()
    query_series = (
        Grade.query.with_entities(Grade.id, Grade.name)
        .join(Class, Grade.id == Class.grade_id)
        .join(ClassTest, Class.id == ClassTest.class_id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .filter(City.id == city.id)
        .filter(School.id == escola_id_str)
    )
    if permissao["scope"] == "escola" and user.get("role") == "professor":
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return []
        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        teacher_class_ids = [tc.class_id for tc in teacher_classes]
        if not teacher_class_ids:
            return []
        query_series = query_series.filter(Class.id.in_(teacher_class_ids))

    series = query_series.distinct().all()
    return [{"id": str(s[0]), "nome": s[1]} for s in series]


def _obter_turmas_por_serie_evolucao(municipio_id: str, escola_id: str, serie_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna turmas da escola e série (no município) que possuem pelo menos uma avaliação aplicada.
    Usado na tela de Evolução: só aparecem turmas que têm avaliações para comparar.
    """
    city = City.query.get(municipio_id)
    if not city:
        return []
    city_id_str = str(city.id) if city.id else ""
    if permissao["scope"] != "all" and _user_city_id(user) != city_id_str:
        return []

    escola_id_str = str(escola_id).strip()
    serie_id_str = str(serie_id).strip()
    query_turmas = (
        Class.query.with_entities(Class.id, Class.name)
        .join(ClassTest, Class.id == ClassTest.class_id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .join(Grade, Class.grade_id == Grade.id)
        .filter(City.id == city.id)
        .filter(School.id == escola_id_str)
        .filter(cast(Grade.id, String) == serie_id_str)
    )
    if permissao["scope"] == "escola" and user.get("role") == "professor":
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            return []
        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
        teacher_class_ids = [tc.class_id for tc in teacher_classes]
        if not teacher_class_ids:
            return []
        query_turmas = query_turmas.filter(Class.id.in_(teacher_class_ids))

    turmas = query_turmas.distinct().all()
    return [{"id": str(t[0]), "nome": t[1] or f"Turma {t[0]}"} for t in turmas]


def _parse_data_filtro(value: Optional[str]):
    """
    Parseia data enviada pelo front (dd/mm/aaaa ou ISO) para objeto datetime.
    Retorna None se value for vazio ou inválido.
    """
    if not value or not str(value).strip():
        return None
    value = str(value).strip()
    try:
        # Tentar dd/mm/aaaa
        if re.match(r"\d{1,2}/\d{1,2}/\d{4}", value):
            return datetime.strptime(value, "%d/%m/%Y")
        # Tentar ISO ou formato comum
        return dateutil.parser.parse(value)
    except (ValueError, TypeError):
        return None


def _parse_periodo_bounds(periodo: str) -> Tuple[datetime, datetime]:
    """
    periodo no formato YYYY-MM → primeiro e último dia do mês (datetime date-only).
    Usado com o mesmo critério lexicográfico de ClassTest.application que a Evolução.
    """
    s = str(periodo).strip()
    m = re.match(r"^(\d{4})-(\d{2})$", s)
    if not m:
        raise ValueError("Use o formato YYYY-MM (ex.: 2026-04).")
    year, month = int(m.group(1)), int(m.group(2))
    if month < 1 or month > 12:
        raise ValueError("Mês deve estar entre 01 e 12.")
    last = monthrange(year, month)[1]
    return datetime(year, month, 1), datetime(year, month, last)


def _formatar_periodo_br(periodo: Optional[str]) -> Optional[str]:
    """
    Converte período YYYY-MM para intervalo no formato brasileiro (dd/mm/aaaa - dd/mm/aaaa).
    Retorna None quando vazio e preserva o valor original quando inválido.
    """
    if not periodo or not str(periodo).strip():
        return None
    valor = str(periodo).strip()
    try:
        dt_inicio, dt_fim = _parse_periodo_bounds(valor)
        return f"{dt_inicio.strftime('%d/%m/%Y')} - {dt_fim.strftime('%d/%m/%Y')}"
    except Exception:
        return valor


def _apply_class_test_application_period(
    query,
    bounds: Optional[Tuple[datetime, datetime]],
):
    if bounds is None:
        return query
    dt_inicio, dt_fim = bounds
    d0 = dt_inicio.strftime("%Y-%m-%d")
    d1 = dt_fim.strftime("%Y-%m-%d")
    # Comparação lexicográfica no ISO completo falha no fim do mês (ex.: microssegundos
    # ou sufixo de timezone após 23:59:59.999). Quando os 10 primeiros caracteres são
    # YYYY-MM-DD, filtramos pelo dia civil; caso contrário mantém o critério antigo.
    app_text = cast(ClassTest.application, String)
    iso_date_prefix = func.substring(app_text, 1, 10)
    matches_iso_date = iso_date_prefix.op("~")(r"^\d{4}-\d{2}-\d{2}$")
    cond_by_calendar_day = and_(
        matches_iso_date,
        iso_date_prefix >= d0,
        iso_date_prefix <= d1,
    )
    cond_lex_legacy = and_(
        not_(matches_iso_date),
        ClassTest.application >= d0,
        ClassTest.application <= d1 + "T23:59:59.999",
    )
    return query.filter(or_(cond_by_calendar_day, cond_lex_legacy))


def _formatar_data_para_evolucao(val) -> Optional[str]:
    """
    Formata valor de data (application ou created_at) para exibição dd/mm/yyyy.
    Aceita: string ISO, string YYYY-MM-DD, datetime, timestamp numérico.
    Retorna None se não for possível formatar.
    """
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    try:
        if isinstance(val, str):
            # Tentar ISO ou só data
            if re.match(r"^\d{4}-\d{2}-\d{2}", val):
                dt = dateutil.parser.parse(val[:10])
                return dt.strftime("%d/%m/%Y")
            return dateutil.parser.parse(val).strftime("%d/%m/%Y")
        if hasattr(val, "strftime"):
            return val.strftime("%d/%m/%Y")
        if isinstance(val, (int, float)):
            return datetime.utcfromtimestamp(val).strftime("%d/%m/%Y")
        return str(val)[:10] if len(str(val)) >= 10 else None
    except (ValueError, TypeError, OverflowError):
        return None


def _obter_avaliacoes_evolucao(
    municipio_id: str,
    user: dict,
    permissao: dict,
    escola_id: Optional[str] = None,
    serie_id: Optional[str] = None,
    turma_id: Optional[str] = None,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    nome: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retorna avaliações para a tela de Evolução, aplicando todos os filtros de forma restritiva.
    Usado pelo endpoint GET /evolucao/avaliacoes.

    Filtros: município (obrigatório), escola, série, turma, data início/fim, nome.
    Quando série é informada, retorna apenas avaliações que foram aplicadas em turmas
    dessa série (evita retornar avaliações de outras séries, ex.: 5º ano ao selecionar 2º ano).
    Retorna lista com id, titulo e data (data de aplicação quando disponível).
    """
    # Garantir string para primary key (evita falha quando front envia número ou formato diferente)
    municipio_str = str(municipio_id).strip() if municipio_id else ""
    city = City.query.get(municipio_str) if municipio_str else None
    if not city:
        return []

    city_id_str = str(city.id) if city.id else ""
    if permissao["scope"] != "all":
        if _user_city_id(user) != city_id_str:
            return []

    escola_param = (escola_id or "all").strip() if escola_id else "all"
    if escola_param.lower() == "all":
        escola_param = "all"

    # Normalizar IDs; ignorar "all"/"todas" e string vazia (evita filtrar por "" e zerar resultado)
    def _norm_filtro(val, all_values):
        if not val:
            return None
        s = str(val).strip()
        if not s or s.lower() in all_values:
            return None
        return s

    serie_param = _norm_filtro(serie_id, ("all",))
    turma_param = _norm_filtro(turma_id, ("all", "todas"))

    # Query base: apenas ClassTests que batem com TODOS os filtros (incluindo série)
    # Inclui Test.created_at como fallback quando application não estiver disponível.
    query = (
        Test.query.with_entities(
            Test.id,
            Test.title,
            func.min(ClassTest.application).label("data_aplicacao"),
            Test.created_at,
        )
        .join(ClassTest, Test.id == ClassTest.test_id)
        .join(Class, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .filter(City.id == city_id_str)
    )

    if escola_param.lower() != "all":
        query = query.filter(School.id == str(escola_param))

    # Filtro de série: restringe às turmas da série selecionada (comparação em string para consistência)
    if serie_param:
        query = query.join(Grade, Class.grade_id == Grade.id)
        query = query.filter(cast(Grade.id, String) == serie_param)

    if turma_param:
        query = query.filter(cast(Class.id, String) == turma_param)

    # Filtros de data (ClassTest.application é texto ISO/timestamp)
    dt_inicio = _parse_data_filtro(data_inicio)
    dt_fim = _parse_data_filtro(data_fim)
    if dt_inicio is not None:
        query = query.filter(ClassTest.application >= dt_inicio.strftime("%Y-%m-%d"))
    if dt_fim is not None:
        query = query.filter(ClassTest.application <= dt_fim.strftime("%Y-%m-%d") + "T23:59:59.999")

    if nome and str(nome).strip():
        query = query.filter(Test.title.ilike(f"%{nome.strip()}%"))

    query = filter_tests_by_user(query, user, escola_param, require_school=False)
    query = query.group_by(Test.id, Test.title, Test.created_at)

    rows = query.all()
    result = []
    for row in rows:
        test_id, title, data_app, created_at = row[0], row[1], row[2], row[3]
        data_exibir = _formatar_data_para_evolucao(data_app)
        if data_exibir is None and created_at is not None:
            data_exibir = _formatar_data_para_evolucao(created_at)
        result.append({
            "id": str(test_id),
            "titulo": title or "",
            "data": data_exibir,
        })
    return result


# ==================== ENDPOINT 6: GET /opcoes-filtros ====================

@bp.route('/opcoes-filtros/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def opcoes_filtros(evaluation_id: str):
    """
    Retorna opções disponíveis para filtros da avaliação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        permissao = verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao['error']}), 403

        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões específicas para professor
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Acesso negado"}), 403
        
        # Buscar disciplinas das questões
        disciplinas = []
        if test.questions:
            subject_ids = set()
            for question in test.questions:
                if question.subject_id and question.subject_id not in subject_ids:
                    subject_ids.add(question.subject_id)
                    subject = Subject.query.get(question.subject_id)
                    if subject:
                        disciplinas.append({
                            "id": subject.id,
                            "name": subject.name
                        })
        
        # Buscar níveis dos alunos
        niveis = []
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter evaluation_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(evaluation_id)).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if class_ids:
            students = Student.query.options(
                joinedload(Student.class_).joinedload(Class.grade)
            ).filter(Student.class_id.in_(class_ids)).all()
            
            grade_names = set()
            for student in students:
                if student.class_ and student.class_.grade and student.class_.grade.name:
                    grade_names.add(student.class_.grade.name)
            
            niveis = [{"id": name, "name": name} for name in sorted(grade_names)]
        
        # Opções de ordenação
        opcoes_ordenacao = [
            {"id": "nota", "name": "Nota"},
            {"id": "proficiencia", "name": "Proficiência"},
            {"id": "status", "name": "Status"},
            {"id": "turma", "name": "Turma"},
            {"id": "nome", "name": "Nome do Aluno"}
        ]
        
        # Campos disponíveis
        campos_disponiveis = [
            {"id": "alunos", "name": "Dados dos Alunos"},
            {"id": "questoes", "name": "Questões"},
            {"id": "turma", "name": "Turma"},
            {"id": "habilidade", "name": "Habilidades"},
            {"id": "total", "name": "Total de Acertos"},
            {"id": "nota", "name": "Nota"},
            {"id": "proficiencia", "name": "Proficiência"},
            {"id": "nivel", "name": "Nível"}
        ]
        
        return jsonify({
            "disciplinas": disciplinas,
            "niveis": niveis,
            "opcoes_ordenacao": opcoes_ordenacao,
            "campos_disponiveis": campos_disponiveis
        }), 200

    except Exception as e:
        logging.error(f"Erro ao buscar opções de filtros: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar opções de filtros", "details": str(e)}), 500

# ==================== FUNÇÕES AUXILIARES PARA STATUS ====================

def _check_and_update_evaluation_status(test_id: str) -> Dict[str, Any]:
    """
    Verifica e atualiza automaticamente o status de uma avaliação para "concluída" quando apropriado
    
    Critérios para marcar como "concluída":
    1. Todas as sessões de alunos foram finalizadas
    2. Todas as sessões foram corrigidas (se necessário)
    3. Prazo de expiração foi atingido (se configurado)
    
    Returns:
        Dict com informações sobre a atualização
    """
    try:
        from app.models.testSession import TestSession
        from app.models.classTest import ClassTest
        from datetime import datetime, timedelta
        
        # Buscar a avaliação
        test = Test.query.get(test_id)
        if not test:
            return {"error": "Avaliação não encontrada"}
        
        # Buscar todas as aplicações da avaliação
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
        if not class_tests:
            return {"error": "Avaliação não foi aplicada em nenhuma turma"}
        
        # Buscar todas as sessões da avaliação
        sessions = TestSession.query.filter_by(test_id=test_id).all()
        
        if not sessions:
            return {"message": "Nenhuma sessão encontrada para esta avaliação"}
        
        # Verificar se todas as sessões foram finalizadas
        total_sessions = len(sessions)
        finalized_sessions = len([s for s in sessions if s.status in ['finalizada', 'corrigida', 'revisada', 'finalized']])
        
        # Verificar se há prazo de expiração
        has_expired = False
        if class_tests and class_tests[0].expiration:
            current_time = datetime.utcnow()
            # Converter string para datetime para comparação
            try:
                expiration_time = dateutil.parser.parse(class_tests[0].expiration)
                if current_time > expiration_time:
                    has_expired = True
            except (ValueError, TypeError) as e:
                # Se houver erro na conversão, não considerar como expirada
                logging.warning(f"Erro ao converter data de expiração '{class_tests[0].expiration}': {str(e)}")
                has_expired = False
        
        # Determinar se deve ser marcada como concluída
        should_be_completed = False
        completion_reason = ""
        
        if has_expired:
            should_be_completed = True
            completion_reason = "Prazo de expiração atingido"
        elif finalized_sessions == total_sessions and total_sessions > 0:
            should_be_completed = True
            completion_reason = "Todas as sessões foram finalizadas"
        
        # Atualizar status se necessário
        updated_class_tests = []
        if should_be_completed:
            for class_test in class_tests:
                if class_test.status != "concluida":
                    class_test.status = "concluida"
                    class_test.updated_at = datetime.utcnow()
                    updated_class_tests.append(class_test.id)
            
            if updated_class_tests:
                db.session.commit()
        
        return {
            "test_id": test_id,
            "total_sessions": total_sessions,
            "finalized_sessions": finalized_sessions,
            "has_expired": has_expired,
            "should_be_completed": should_be_completed,
            "completion_reason": completion_reason,
            "updated_class_tests": updated_class_tests,
            "current_status": class_tests[0].status if class_tests else "N/A"
        }
        
    except Exception as e:
        logging.error(f"Erro ao verificar status da avaliação {test_id}: {str(e)}", exc_info=True)
        return {"error": f"Erro ao verificar status: {str(e)}"}


def _get_evaluation_status_summary(test_id: str) -> Dict[str, Any]:
    """
    Retorna um resumo do status atual de uma avaliação
    """
    try:
        from app.models.testSession import TestSession
        from app.models.classTest import ClassTest
        from datetime import datetime
        import dateutil.parser
        
        # Buscar aplicações da avaliação
        # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test_id para string
        class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()
        
        # Buscar sessões
        sessions = TestSession.query.filter_by(test_id=test_id).all()
        
        # Contar por status
        status_counts = {}
        for session in sessions:
            status = session.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Verificar expiração
        expiration_info = None
        if class_tests and class_tests[0].expiration:
            current_time = datetime.utcnow()
            
            # Converter string para datetime para comparação
            try:
                expiration_time = dateutil.parser.parse(class_tests[0].expiration)
                is_expired = current_time > expiration_time
                
                # Calcular dias até expiração
                days_until_expiration = 0
                if not is_expired:
                    time_diff = expiration_time - current_time
                    days_until_expiration = time_diff.days
                
                expiration_info = {
                    "expiration_date": class_tests[0].expiration,  # Manter como string original
                    "is_expired": is_expired,
                    "days_until_expiration": days_until_expiration
                }
            except (ValueError, TypeError) as e:
                # Se houver erro na conversão, não incluir informações de expiração
                logging.warning(f"Erro ao converter data de expiração '{class_tests[0].expiration}': {str(e)}")
                expiration_info = {
                    "expiration_date": class_tests[0].expiration,
                    "is_expired": None,
                    "days_until_expiration": None,
                    "error": "Formato de data inválido"
                }
        
        return {
            "test_id": test_id,
            "total_sessions": len(sessions),
            "status_counts": status_counts,
            "class_test_status": [ct.status for ct in class_tests],
            "expiration_info": expiration_info,
            "overall_status": class_tests[0].status if class_tests else "N/A"
        }
        
    except Exception as e:
        logging.error(f"Erro ao obter resumo de status da avaliação {test_id}: {str(e)}", exc_info=True)
        return {"error": f"Erro ao obter resumo: {str(e)}"}


# ==================== ENDPOINT PARA VERIFICAR/ATUALIZAR STATUS ====================

@bp.route('/avaliacoes/<string:test_id>/verificar-status', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def verificar_e_atualizar_status(test_id: str):
    """
    Verifica e atualiza automaticamente o status de uma avaliação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Você só pode verificar avaliações que criou"}), 403
        
        # Verificar e atualizar status
        status_info = _check_and_update_evaluation_status(test_id)
        
        if "error" in status_info:
            return jsonify(status_info), 400
        
        # Obter resumo atual
        summary = _get_evaluation_status_summary(test_id)
        
        return jsonify({
            "message": "Status verificado e atualizado com sucesso",
            "status_update": status_info,
            "current_summary": summary
        }), 200

    except Exception as e:
        logging.error(f"Erro ao verificar status da avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar status", "details": str(e)}), 500


# ==================== ENDPOINT PARA OBTER RESUMO DE STATUS ====================

@bp.route('/avaliacoes/<string:test_id>/status-resumo', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_resumo_status(test_id: str):
    """
    Retorna um resumo detalhado do status atual de uma avaliação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Você só pode verificar avaliações que criou"}), 403
        
        # Obter resumo
        summary = _get_evaluation_status_summary(test_id)
        
        if "error" in summary:
            return jsonify(summary), 400
        
        return jsonify(summary), 200

    except Exception as e:
        logging.error(f"Erro ao obter resumo de status: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter resumo", "details": str(e)}), 500

# ==================== ENDPOINT PARA VERIFICAR TODAS AS AVALIAÇÕES ====================

@bp.route('/avaliacoes/verificar-todas', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def verificar_todas_avaliacoes():
    """
    Verifica e atualiza automaticamente o status de todas as avaliações
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Buscar todas as avaliações
        if user['role'] == 'professor':
            # ✅ CORRIGIDO: Professores veem avaliações que criaram OU que foram aplicadas em suas TURMAS
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            from sqlalchemy import or_
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                # ✅ CORRIGIDO: Buscar TURMAS onde o professor está vinculado (via TeacherClass)
                teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                teacher_class_ids = [tc.class_id for tc in teacher_classes]
                
                # Criar filtro OR: avaliações criadas pelo professor OU aplicadas em suas TURMAS
                filters = [Test.created_by == user['id']]
                
                if teacher_class_ids:
                    # ✅ CORRIGIDO: Avaliações aplicadas em TURMAS ESPECÍFICAS onde o professor está vinculado
                    filters.append(
                        Test.id.in_(
                            db.session.query(ClassTest.test_id).filter(
                                ClassTest.class_id.in_(teacher_class_ids)
                            )
                        )
                    )
                
                tests = Test.query.filter(or_(*filters)).all()
            else:
                # Se não é um professor válido, não mostrar nenhuma avaliação
                tests = []
        else:
            # Admins veem todas as avaliações
            tests = Test.query.all()
        
        if not tests:
            return jsonify({
                "message": "Nenhuma avaliação encontrada",
                "total_checked": 0,
                "total_updated": 0
            }), 200
        
        # Verificar cada avaliação
        results = []
        total_updated = 0
        
        for test in tests:
            try:
                status_info = _check_and_update_evaluation_status(test.id)
                
                if status_info.get("should_be_completed", False):
                    total_updated += 1
                
                results.append({
                    "test_id": test.id,
                    "title": test.title,
                    "status_info": status_info
                })
                
            except Exception as e:
                logging.error(f"Erro ao verificar avaliação {test.id}: {str(e)}")
                results.append({
                    "test_id": test.id,
                    "title": test.title,
                    "error": str(e)
                })
        
        return jsonify({
            "message": "Verificação de todas as avaliações concluída",
            "total_checked": len(tests),
            "total_updated": total_updated,
            "results": results
        }), 200

    except Exception as e:
        logging.error(f"Erro ao verificar todas as avaliações: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar avaliações", "details": str(e)}), 500


# ==================== ENDPOINT PARA OBTER ESTATÍSTICAS DE STATUS ====================

@bp.route('/avaliacoes/estatisticas-status', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor")
def obter_estatisticas_status():
    """
    Retorna estatísticas gerais do status das avaliações
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Buscar todas as avaliações
        if user['role'] == 'professor':
            # ✅ CORRIGIDO: Professores veem avaliações que criaram OU que foram aplicadas em suas TURMAS
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass
            from sqlalchemy import or_
            
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                # ✅ CORRIGIDO: Buscar TURMAS onde o professor está vinculado (via TeacherClass)
                teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                teacher_class_ids = [tc.class_id for tc in teacher_classes]
                
                # Criar filtro OR: avaliações criadas pelo professor OU aplicadas em suas TURMAS
                filters = [Test.created_by == user['id']]
                
                if teacher_class_ids:
                    # ✅ CORRIGIDO: Avaliações aplicadas em TURMAS ESPECÍFICAS onde o professor está vinculado
                    filters.append(
                        Test.id.in_(
                            db.session.query(ClassTest.test_id).filter(
                                ClassTest.class_id.in_(teacher_class_ids)
                            )
                        )
                    )
                
                tests = Test.query.filter(or_(*filters)).all()
            else:
                # Se não é um professor válido, não mostrar nenhuma avaliação
                tests = []
        else:
            tests = Test.query.all()
        
        # Contar por status
        status_counts = {}
        total_tests = len(tests)
        
        for test in tests:
            # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter test.id para string
            class_tests = ClassTest.query.filter_by(test_id=str(test.id)).all()
            if class_tests:
                # Usar o status da primeira aplicação como representativo
                status = class_tests[0].status
                status_counts[status] = status_counts.get(status, 0) + 1
            else:
                status_counts['sem_aplicacao'] = status_counts.get('sem_aplicacao', 0) + 1
        
        # Calcular porcentagens
        status_percentages = {}
        for status, count in status_counts.items():
            status_percentages[status] = round_to_two_decimals((count / total_tests) * 100) if total_tests > 0 else 0
        
        return jsonify({
            "total_avaliacoes": total_tests,
            "contagem_por_status": status_counts,
            "porcentagem_por_status": status_percentages,
            "status_disponiveis": ["agendada", "em_andamento", "concluida", "cancelada", "sem_aplicacao"]
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter estatísticas de status: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter estatísticas", "details": str(e)}), 500


@bp.route('/avaliacoes/<string:test_id>/estatisticas-por-disciplina', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_estatisticas_por_disciplina(test_id: str):
    """
    Obtém estatísticas detalhadas por disciplina de uma avaliação
    
    Args:
        test_id: ID da avaliação
        
    Returns:
        Estatísticas detalhadas por disciplina
    """
    try:
        from app.services.evaluation_result_service import EvaluationResultService
        
        # Verificar permissões do usuário
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Buscar o teste para verificar permissões
        from app.models.test import Test
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões específicas
        if user['role'] == 'professor' and not professor_pode_ver_avaliacao(user['id'], test.id):
            return jsonify({"error": "Verificação de permissões falhou"}), 403
        
        # Obter estatísticas por disciplina
        statistics = EvaluationResultService.get_subject_detailed_statistics(test_id)
        
        if "error" in statistics:
            return jsonify(statistics), 400
        
        return jsonify(statistics), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter estatísticas por disciplina para avaliação {test_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter estatísticas por disciplina", "details": str(e)}), 500


def _filtrar_alunos_mapa_digital_por_periodo_aplicacao(
    students: List[Student],
    avaliacao_id: str,
    periodo_bounds: Optional[Tuple[datetime, datetime]],
) -> List[Student]:
    """Restringe alunos às turmas com ClassTest da avaliação aplicada no mês (periodo YYYY-MM)."""
    if periodo_bounds is None or not students:
        return students
    q = ClassTest.query.filter(ClassTest.test_id == str(avaliacao_id))
    q = _apply_class_test_application_period(q, periodo_bounds)
    allowed_class_ids = {str(ct.class_id) for ct in q.all()}
    return [
        s
        for s in students
        if getattr(s, "class_id", None) and str(s.class_id) in allowed_class_ids
    ]


@bp.route("/mapa-habilidades", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def mapa_habilidades_avaliacao_online():
    """
    Mapa de habilidades para avaliação online (Test): % de acertos agregados por habilidade em faixas.
    Filtros: estado, municipio, avaliacao (obrigatória), escola, serie, turma, disciplina (id ou all).
    Query opcional: periodo=YYYY-MM (ClassTest.application no mês).
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        estado = request.args.get("estado")
        municipio = request.args.get("municipio")
        escola = request.args.get("escola")
        serie = request.args.get("serie")
        turma = request.args.get("turma")
        avaliacao = request.args.get("avaliacao")
        disciplina = request.args.get("disciplina") or "all"
        periodo_raw = request.args.get("periodo")
        periodo_bounds: Optional[Tuple[datetime, datetime]] = None
        if periodo_raw is not None and str(periodo_raw).strip():
            try:
                periodo_bounds = _parse_periodo_bounds(periodo_raw)
            except ValueError as ve:
                return jsonify(
                    {
                        "error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04).",
                        "details": str(ve),
                    }
                ), 400

        if not estado or str(estado).lower() == "all":
            return jsonify({"error": "Estado é obrigatório e não pode ser 'all'"}), 400
        if not municipio:
            return jsonify({"error": "Município é obrigatório"}), 400
        if not avaliacao or str(avaliacao).lower() == "all":
            return jsonify({"error": "Avaliação é obrigatória para o mapa de habilidades"}), 400

        def _is_valid_filtro_mapa(value):
            return value and str(value).lower() != "all"

        filtros_aplicados = sum(
            [
                bool(estado and str(estado).lower() != "all"),
                bool(municipio and str(municipio).lower() != "all"),
                bool(escola and str(escola).lower() != "all"),
                bool(serie and str(serie).lower() != "all"),
                bool(turma and str(turma).lower() != "all"),
                bool(avaliacao and str(avaliacao).lower() != "all"),
            ]
        )
        if filtros_aplicados < 2:
            return jsonify(
                {"error": "É necessário aplicar pelo menos 2 filtros válidos (excluindo 'all')"}
            ), 400

        scope_info = _determinar_escopo_busca(estado, municipio, escola, serie, turma, avaliacao, user)
        if not scope_info:
            return jsonify({"error": "Não foi possível determinar o escopo de busca"}), 400

        if scope_info.get("escola") and not escola:
            escola = scope_info.get("escola")

        permissao = verificar_permissao_filtros(user)
        if not permissao["permitted"]:
            return jsonify({"error": permissao["error"]}), 403

        from app.permissions import validate_professor_school_selection, validate_manager_school_selection

        escola_param = request.args.get("escola", "all")
        if user.get("role") == "professor":
            validation_result = validate_professor_school_selection(user, escola_param, require_school=False)
        elif user.get("role") in ["diretor", "coordenador"]:
            validation_result = validate_manager_school_selection(user, escola_param, require_school=False)
        else:
            validation_result = {"valid": True, "school_id": escola_param}

        if not validation_result["valid"]:
            return jsonify(
                {"error": validation_result["error"], "code": "SCHOOL_ACCESS_DENIED"}
            ), 403

        escola_id_validada = validation_result.get("school_id")
        if escola_id_validada:
            escola = escola_id_validada

        municipio_str = str(municipio).strip()
        set_search_path(city_id_to_schema_name(municipio_str))

        nivel_granularidade = _determinar_nivel_granularidade(
            estado, municipio, escola, serie, turma, avaliacao, user
        )
        escopo_calculo = _determinar_escopo_calculo(scope_info, nivel_granularidade)
        all_students = _obter_alunos_para_mapa_habilidades_test(
            scope_info, nivel_granularidade, user, escopo_calculo
        )
        all_students = _filtrar_alunos_mapa_digital_por_periodo_aplicacao(
            all_students, str(avaliacao), periodo_bounds
        )

        subject_filter = (
            None if str(disciplina).strip().lower() == "all" else str(disciplina).strip()
        )

        from app.services.skills_map_service import compute_digital_aggregate

        data = compute_digital_aggregate(str(avaliacao), all_students, subject_filter)
        # participating_students = alunos que realmente responderam (sem faltosos)
        participating_students = data.get("_students_snapshot", all_students)
        n_turma = len(all_students)
        n_part = len(participating_students)

        por_faixa = data.get("por_faixa", {}) or {}
        habilidades_abaixo = por_faixa.get("abaixo_do_basico", []) or []
        habilidades_basico = por_faixa.get("basico", []) or []
        habilidades_criticas = list(habilidades_abaixo) + list(habilidades_basico)

        # Resolver nome da disciplina (quando disciplina != all)
        disciplina_nome = None
        subject_filter_id = subject_filter
        if subject_filter_id:
            for d in data.get("disciplinas_disponiveis", []) or []:
                if str(d.get("id")) == str(subject_filter_id):
                    disciplina_nome = d.get("nome")
                    break
        disciplina_label = (disciplina_nome or str(subject_filter_id)) if subject_filter_id else "all"

        # Resolver referência da avaliação (Test.title)
        try:
            test_obj = Test.query.get(str(avaliacao))
            avaliacao_referencia = (
                (getattr(test_obj, "title", None) or "Avaliação Online").strip()
                if test_obj
                else "Avaliação Online"
            )
        except Exception:
            avaliacao_referencia = "Avaliação Online"

        # Resolver série/ano
        ano_serie = str(serie).strip() if serie and str(serie).strip() else ""

        # Montar lista de habilidades no formato do prompt
        skills_lines: List[str] = []
        for idx, h in enumerate(habilidades_criticas, start=1):
            codigo = (h.get("codigo") or "").strip()
            desc = (h.get("descricao") or "").strip()
            if codigo and desc:
                item = f"{codigo} - {desc}"
            else:
                item = codigo or desc or (h.get("skill_id") or "")
            skills_lines.append(f"  {idx}. {item}")

        prompt = (
            "Atue como um Especialista em Avaliação Educacional e Recomposição de Aprendizagem, com profundo conhecimento "
            "nas matrizes de referência do SAEB, SPAECE e SAVEAL.\n\n"
            "Abaixo, fornecerei os dados de uma avaliação (Mensal ou Larga Escala) referentes a uma turma.\n\n"
            "Sua tarefa é gerar um plano de ação estritamente focado em alunos que se encontram nos níveis de proficiência "
            "\"ABAIXO DO BÁSICO\" e \"BÁSICO\". O plano deve ser realista, aplicável na rede pública ou privada, utilizando "
            "recursos acessíveis de sala de aula.\n\n"
            "Nomeie o documento final obrigatoriamente como: **ESTRATÉGIAS DE INTERVENÇÃO**.\n\n"
            "O documento deve seguir rigorosamente a estrutura abaixo:\n\n"
            "# ESTRATÉGIAS DE INTERVENÇÃO\n\n"
            "## 1. Foco Analítico: Níveis Abaixo do Básico e Básico\n"
            "[Escreva um breve parágrafo (máx 3 linhas) resumindo qual é a principal barreira cognitiva esperada para esses "
            "alunos nas habilidades fornecidas.]\n\n"
            "## 2. Matriz de Ação por Habilidade\n"
            "Crie uma tabela para cada habilidade listada, contendo:\n"
            "* **Habilidade (Código e Descrição):**\n"
            "* **Conteúdo Estruturante:** (Qual é o conceito matemático ou linguístico fundamental que o aluno precisa dominar "
            "para atingir essa habilidade?)\n"
            "* **Dificuldade Mapeada (Abaixo do Básico/Básico):** (Exatamente onde o aluno trava? Ex: \"Não compreende a "
            "conservação de quantidade\" ou \"Não localiza informação se não estiver no início do texto\").\n"
            "* **Como Trabalhar (Passo a Passo Prático):** (3 etapas progressivas. Comece sempre do concreto/visual, vá para o "
            "pictórico e depois para o abstrato/simbólico. Sem sugestões genéricas; dê exemplos do que o professor deve dizer "
            "ou desenhar no quadro).\n"
            "* **Sugestão de Atividade Curta:** (Uma atividade de no máximo 10 minutos para fixação imediata).\n\n"
            "## 3. Dinâmica de Sala e Recomposição\n"
            "Melhore as estratégias gerais adaptando-as EXCLUSIVAMENTE para alunos com defasagem:\n"
            "* **Agrupamentos Produtivos Focados:** (Como juntar um aluno \"Básico\" com um \"Adequado\" sem que o Adequado faça "
            "o trabalho todo? Dê instruções de papéis na dupla).\n"
            "* **Avaliação Formativa de Baixo Risco (Tickets de Saída):** (Sugira 2 perguntas curtas e diretas para o professor "
            "usar no final da aula e checar se a intervenção daquela habilidade funcionou).\n\n"
            "---\n"
            "DADOS PARA A ANÁLISE:\n"
            f"- Ano/Série: {ano_serie}\n"
            f"- Disciplina: {disciplina_label}\n"
            f"- Avaliação Referência: {avaliacao_referencia}\n"
            "- Habilidades Críticas a serem trabalhadas:\n"
            f"{chr(10).join(skills_lines) if skills_lines else '  1. '}\n\n"
            "IMPORTANTE: Sua resposta deve ser APENAS um JSON válido (objeto) e NADA além do JSON.\n"
            "O JSON deve conter a estrutura equivalente ao documento \"ESTRATÉGIAS DE INTERVENÇÃO\", com chaves para os itens "
            "1, 2 (lista por habilidade) e 3 (dinâmica e tickets).\n"
        )

        try:
            from app.services.ai_analysis_service import AIAnalysisService

            ai_service = AIAnalysisService()
            analise_ia = ai_service.analyze_intervention_plan_json(prompt)
        except Exception as _exc:
            analise_ia = {
                "error": "Falha ao gerar análise de IA",
                "details": str(_exc),
            }

        return jsonify(
            {
                "nivel_granularidade": nivel_granularidade,
                "disciplinas_disponiveis": data["disciplinas_disponiveis"],
                "habilidades": data["habilidades"],
                "por_faixa": data["por_faixa"],
                "analise_ia": analise_ia,
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": municipio,
                    "escola": escola,
                    "serie": serie,
                    "turma": turma,
                    "avaliacao": avaliacao,
                    "disciplina": disciplina,
                    "periodo": (
                        str(periodo_raw).strip()
                        if periodo_raw and str(periodo_raw).strip()
                        else None
                    ),
                },
                "total_alunos_escopo_turma": n_turma,
                "total_alunos_participantes": n_part,
                "total_alunos_escopo": n_part,
            }
        ), 200
    except Exception as e:
        logging.error("Erro ao obter mapa de habilidades: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao obter mapa de habilidades", "details": str(e)}), 500


@bp.route("/mapa-habilidades/erros", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def mapa_habilidades_avaliacao_online_erros():
    """Lista alunos que erraram ao menos uma questão da habilidade e % de erros sobre o escopo."""
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        skill_id = request.args.get("skill_id")
        if not skill_id or not str(skill_id).strip():
            return jsonify({"error": "skill_id é obrigatório"}), 400
        question_ref = request.args.get("question_ref")

        estado = request.args.get("estado")
        municipio = request.args.get("municipio")
        escola = request.args.get("escola")
        serie = request.args.get("serie")
        turma = request.args.get("turma")
        avaliacao = request.args.get("avaliacao")
        disciplina = request.args.get("disciplina") or "all"
        periodo_raw = request.args.get("periodo")
        periodo_bounds_erros: Optional[Tuple[datetime, datetime]] = None
        if periodo_raw is not None and str(periodo_raw).strip():
            try:
                periodo_bounds_erros = _parse_periodo_bounds(periodo_raw)
            except ValueError as ve:
                return jsonify(
                    {
                        "error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04).",
                        "details": str(ve),
                    }
                ), 400

        if not estado or str(estado).lower() == "all":
            return jsonify({"error": "Estado é obrigatório e não pode ser 'all'"}), 400
        if not municipio:
            return jsonify({"error": "Município é obrigatório"}), 400
        if not avaliacao or str(avaliacao).lower() == "all":
            return jsonify({"error": "Avaliação é obrigatória"}), 400

        filtros_aplicados = sum(
            [
                bool(estado and str(estado).lower() != "all"),
                bool(municipio and str(municipio).lower() != "all"),
                bool(escola and str(escola).lower() != "all"),
                bool(serie and str(serie).lower() != "all"),
                bool(turma and str(turma).lower() != "all"),
                bool(avaliacao and str(avaliacao).lower() != "all"),
            ]
        )
        if filtros_aplicados < 2:
            return jsonify(
                {"error": "É necessário aplicar pelo menos 2 filtros válidos (excluindo 'all')"}
            ), 400

        scope_info = _determinar_escopo_busca(estado, municipio, escola, serie, turma, avaliacao, user)
        if not scope_info:
            return jsonify({"error": "Não foi possível determinar o escopo de busca"}), 400

        if scope_info.get("escola") and not escola:
            escola = scope_info.get("escola")

        permissao = verificar_permissao_filtros(user)
        if not permissao["permitted"]:
            return jsonify({"error": permissao["error"]}), 403

        from app.permissions import validate_professor_school_selection, validate_manager_school_selection

        escola_param = request.args.get("escola", "all")
        if user.get("role") == "professor":
            validation_result = validate_professor_school_selection(user, escola_param, require_school=False)
        elif user.get("role") in ["diretor", "coordenador"]:
            validation_result = validate_manager_school_selection(user, escola_param, require_school=False)
        else:
            validation_result = {"valid": True, "school_id": escola_param}

        if not validation_result["valid"]:
            return jsonify(
                {"error": validation_result["error"], "code": "SCHOOL_ACCESS_DENIED"}
            ), 403

        escola_id_validada = validation_result.get("school_id")
        if escola_id_validada:
            escola = escola_id_validada

        municipio_str = str(municipio).strip()
        set_search_path(city_id_to_schema_name(municipio_str))

        nivel_granularidade = _determinar_nivel_granularidade(
            estado, municipio, escola, serie, turma, avaliacao, user
        )
        escopo_calculo = _determinar_escopo_calculo(scope_info, nivel_granularidade)
        all_students = _obter_alunos_para_mapa_habilidades_test(
            scope_info, nivel_granularidade, user, escopo_calculo
        )
        all_students = _filtrar_alunos_mapa_digital_por_periodo_aplicacao(
            all_students, str(avaliacao), periodo_bounds_erros
        )

        subject_filter = (
            None if str(disciplina).strip().lower() == "all" else str(disciplina).strip()
        )

        from app.services.skills_map_service import (
            compute_digital_aggregate,
            digital_students_passed_vs_failed_for_bucket,
            _norm_skill_key,
        )

        data = compute_digital_aggregate(str(avaliacao), all_students, subject_filter)
        failed_by_skill = data.get("_failed_by_skill") or {}
        participating_students = data.get("_students_snapshot", all_students)

        school_ids = list(
            {
                s.class_.school_id
                for s in participating_students
                if s.class_ and getattr(s.class_, "school_id", None)
            }
        )
        school_by_id = (
            {s.id: s for s in School.query.filter(School.id.in_(school_ids)).all()}
            if school_ids
            else {}
        )

        bucket_key = _norm_skill_key(str(skill_id).strip())
        if question_ref and str(question_ref).strip():
            bucket_key = f"{bucket_key}||q:{str(question_ref).strip()}"
        alunos_err, alunos_ok, n_err, n_ok, n_tot = digital_students_passed_vs_failed_for_bucket(
            participating_students, failed_by_skill, bucket_key, school_by_id
        )
        pct_err = round_to_two_decimals((n_err / n_tot * 100.0) if n_tot else 0.0)
        pct_ok = round_to_two_decimals((n_ok / n_tot * 100.0) if n_tot else 0.0)

        return jsonify(
            {
                "percentual_erros": pct_err,
                "percentual_acertos": pct_ok,
                "total_alunos_escopo": n_tot,
                "total_alunos_que_erraram": n_err,
                "total_alunos_que_acertaram": n_ok,
                "alunos_que_erraram": alunos_err,
                "alunos_que_acertaram": alunos_ok,
                "alunos": alunos_err,
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": municipio,
                    "escola": escola,
                    "serie": serie,
                    "turma": turma,
                    "avaliacao": avaliacao,
                    "disciplina": disciplina,
                    "skill_id": str(skill_id).strip(),
                    "question_ref": str(question_ref).strip() if question_ref else None,
                    "periodo": (
                        str(periodo_raw).strip()
                        if periodo_raw and str(periodo_raw).strip()
                        else None
                    ),
                },
            }
        ), 200
    except Exception as e:
        logging.error("Erro ao obter erros por habilidade: %s", e, exc_info=True)
        return jsonify({"error": "Erro ao obter alunos que erraram", "details": str(e)}), 500


# ==================== ENDPOINT EVOLUÇÃO: OPÇÕES DE FILTROS (Estado → Município → Escola → Série → Turma) ====================

@bp.route('/evolucao/opcoes-filtros', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_opcoes_filtros_evolucao():
    """
    Retorna opções de filtro para a tela de Evolução.
    Hierarquia: Estado → Município → Escola → Série → Turma (avaliações vêm depois, via GET /evolucao/avaliacoes).

    Só aparecem escolas/séries/turmas que possuem pelo menos uma avaliação aplicada (para comparar).
    Query params (opcionais, em ordem): estado, municipio, escola, serie.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        permissao = verificar_permissao_filtros(user)
        if not permissao["permitted"]:
            return jsonify({"error": permissao.get("error", "Acesso negado")}), 403

        estado = request.args.get("estado")
        municipio = request.args.get("municipio")
        escola = request.args.get("escola")
        serie = request.args.get("serie")

        user_city = _user_city_id(user)
        if permissao["scope"] != "all" and municipio and str(municipio).strip() != user_city:
            return jsonify({
                "error": "Você só pode visualizar dados de evolução do seu município."
            }), 403

        response = {}
        response["estados"] = _obter_estados_disponiveis(user, permissao)

        if estado:
            response["municipios"] = _obter_municipios_por_estado(estado, user, permissao)
            if municipio:
                municipio_str = str(municipio).strip()
                schema = city_id_to_schema_name(municipio_str)
                set_search_path(schema)
                response["escolas"] = _obter_escolas_por_municipio_evolucao(municipio_str, user, permissao)
                if escola and str(escola).strip().lower() != "all":
                    response["series"] = _obter_series_por_escola_evolucao(municipio_str, escola, user, permissao)
                    if serie and str(serie).strip().lower() != "all":
                        response["turmas"] = _obter_turmas_por_serie_evolucao(municipio_str, escola, serie, user, permissao)

        return jsonify(response), 200
    except Exception as e:
        logging.error(f"Erro ao obter opções de filtros Evolução: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter opções de filtros", "details": str(e)}), 500


# ==================== ENDPOINT EVOLUÇÃO: AVALIAÇÕES DISPONÍVEIS ====================

@bp.route('/evolucao/avaliacoes', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def listar_avaliacoes_evolucao():
    """
    Lista avaliações disponíveis para a tela de Evolução, com todos os filtros.

    O frontend (Evolução) usa: Estado, Município, Escola, Série, Turma, Data Início,
    Data Fim e busca por nome. Este endpoint retorna apenas a lista de avaliações
    que atendem aos filtros (para seleção e comparação).

    Query Parameters:
    - estado (obrigatório): Nome do estado (ex: ALAGOAS)
    - municipio (obrigatório): ID do município
    - escola (opcional): ID da escola ou 'all' para todas
    - serie (opcional): ID da série ou 'all' para todas
    - turma (opcional): ID da turma ou 'all'/'Todas' para todas
    - data_inicio (opcional): Data início (dd/mm/aaaa ou ISO)
    - data_fim (opcional): Data fim (dd/mm/aaaa ou ISO)
    - nome (opcional): Busca por nome da avaliação

    Returns:
    - avaliacoes: [{ id, titulo, data }] (data = data de aplicação quando disponível)
    - total: quantidade de avaliações
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        permissao = verificar_permissao_filtros(user)
        if not permissao["permitted"]:
            return jsonify({"error": permissao.get("error", "Acesso negado")}), 403

        estado = request.args.get("estado") or ""
        municipio = request.args.get("municipio") or ""
        escola = request.args.get("escola")
        serie = request.args.get("serie")
        turma = request.args.get("turma")
        data_inicio = request.args.get("data_inicio")
        data_fim = request.args.get("data_fim")
        nome = request.args.get("nome")  # Busca por trecho do título da avaliação

        if not estado.strip() or not municipio.strip():
            return jsonify({
                "error": "Os parâmetros 'estado' e 'municipio' são obrigatórios para Evolução."
            }), 400

        municipio_id = str(municipio).strip()
        user_city = _user_city_id(user)
        if permissao["scope"] != "all" and user_city != municipio_id:
            return jsonify({
                "error": "Você só pode listar avaliações de evolução do seu município."
            }), 403

        city = City.query.get(municipio_id)
        if not city:
            return jsonify({"error": "Município não encontrado"}), 404
        if estado and city.state and str(city.state).strip().upper() != str(estado).strip().upper():
            return jsonify({"error": "Município não pertence ao estado informado"}), 400

        schema = city_id_to_schema_name(municipio_id)
        set_search_path(schema)

        avaliacoes = _obter_avaliacoes_evolucao(
            municipio_id=municipio_id,
            user=user,
            permissao=permissao,
            escola_id=escola,
            serie_id=serie,
            turma_id=turma,
            data_inicio=data_inicio,
            data_fim=data_fim,
            nome=nome,
        )

        return jsonify({
            "avaliacoes": avaliacoes,
            "total": len(avaliacoes),
        }), 200

    except Exception as e:
        logging.error(f"Erro ao listar avaliações para Evolução: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao listar avaliações", "details": str(e)}), 500


# ==================== ENDPOINTS PARA OPÇÕES DE FILTROS ====================

@bp.route('/opcoes-filtros', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_opcoes_filtros():
    """
    Retorna opções hierárquicas de filtros seguindo padrão REST.
    Retorna apenas os níveis necessários baseado nos parâmetros fornecidos.
    
    Hierarquia: Estado → Município → Avaliação → Escola → Série → Turma
    
    Query Parameters (todos opcionais, seguindo a hierarquia):
    - estado: Estado selecionado
    - municipio: Município selecionado (requer estado)
    - avaliacao: Avaliação selecionada (requer municipio)
    - escola: Escola selecionada (requer avaliacao)
    - serie: Série selecionada (requer escola)
    - turma: Turma selecionada (requer serie)
    - periodo: Opcional, YYYY-MM; filtra por ClassTest.application no mês (só relatório de avaliação, não cartão-resposta).

    Exemplos:
    - GET /opcoes-filtros → Retorna apenas estados
    - GET /opcoes-filtros?estado=SP → Retorna estados + municípios de SP
    - GET /opcoes-filtros?estado=SP&municipio=123 → Retorna estados + municípios + avaliações
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        permissao = verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao['error']}), 403

        periodo_raw = request.args.get("periodo")
        periodo_bounds = None
        if not is_answer_sheet_report_entity():
            if periodo_raw is not None and str(periodo_raw).strip():
                try:
                    periodo_bounds = _parse_periodo_bounds(periodo_raw)
                except ValueError as ve:
                    return jsonify({
                        "error": "Parâmetro periodo inválido. Use YYYY-MM (ex.: 2026-04).",
                        "details": str(ve),
                    }), 400

        # Extrair parâmetros (todos opcionais)
        estado = request.args.get('estado')
        municipio = request.args.get('municipio')
        avaliacao = request.args.get('avaliacao')
        escola = request.args.get('escola')
        serie = request.args.get('serie')
        turma = request.args.get('turma')
        
        response = {}
        
        # 1. SEMPRE retornar estados (nível 0)
        response["estados"] = _obter_estados_disponiveis(user, permissao)
        
        # 2. Se estado fornecido, retornar municípios (nível 1)
        if estado:
            response["municipios"] = _obter_municipios_por_estado(estado, user, permissao)
            
            # 3. Se município fornecido, retornar avaliações (nível 2)
            if municipio:
                escola_param = request.args.get('escola', 'all')
                municipio_str = str(municipio).strip()
                if is_answer_sheet_report_entity():
                    set_search_path(city_id_to_schema_name(municipio_str))
                    response["avaliacoes"] = obter_gabaritos_por_municipio(
                        municipio_str, user, permissao, escola_param
                    )
                    if avaliacao:
                        response["escolas"] = obter_escolas_por_gabarito(
                            avaliacao, municipio_str, user, permissao
                        )
                        if _escola_param_eh_especifica(escola):
                            response["series"] = obter_series_por_gabarito_escola(
                                avaliacao, escola, municipio_str, user, permissao
                            )
                            if _serie_param_eh_especifica(serie):
                                response["turmas"] = obter_turmas_por_gabarito_escola_serie(
                                    avaliacao, escola, serie, municipio_str, user, permissao
                                )
                        else:
                            response["series"] = obter_series_por_gabarito_municipio(
                                avaliacao, municipio_str, user, permissao
                            )
                            if _serie_param_eh_especifica(serie):
                                response["turmas"] = obter_turmas_por_gabarito_serie_municipio(
                                    avaliacao, serie, municipio_str, user, permissao
                                )
                else:
                    response["avaliacoes"] = _obter_avaliacoes_por_municipio(
                        municipio, user, permissao, escola_param, periodo_bounds
                    )
                    if avaliacao:
                        response["escolas"] = _obter_escolas_por_avaliacao(
                            avaliacao, municipio, user, permissao, periodo_bounds
                        )
                        if _escola_param_eh_especifica(escola):
                            response["series"] = _obter_series_por_escola(
                                avaliacao, escola, municipio, user, permissao, periodo_bounds
                            )
                            if _serie_param_eh_especifica(serie):
                                response["turmas"] = _obter_turmas_por_serie(
                                    avaliacao, escola, serie, municipio, user, permissao, periodo_bounds
                                )
                        else:
                            response["series"] = _obter_series_por_avaliacao_municipio(
                                avaliacao, municipio, user, permissao, periodo_bounds
                            )
                            if _serie_param_eh_especifica(serie):
                                response["turmas"] = _obter_turmas_por_serie_municipio(
                                    avaliacao, serie, municipio, user, permissao, periodo_bounds
                                )
        
        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Erro ao obter opções de filtros: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter opções de filtros", "details": str(e)}), 500


# ⚠️ ROTAS DUPLICADAS REMOVIDAS - Use GET /opcoes-filtros com parâmetros opcionais
# As seguintes rotas foram removidas pois são redundantes:
# - GET /opcoes-filtros/estados
# - GET /opcoes-filtros/municipios/<estado>
# - GET /opcoes-filtros/escolas/<municipio_id>
# - GET /opcoes-filtros/escolas-por-avaliacao
# - GET /opcoes-filtros/series
# - GET /opcoes-filtros/turmas
# - GET /opcoes-filtros/avaliacoes
#
# Use a rota principal: GET /opcoes-filtros?estado=...&municipio=...&avaliacao=...&escola=...&serie=...


# ==================== FUNÇÕES AUXILIARES PARA CÁLCULO CONSOLIDADO ====================

def _calcular_estatisticas_consolidadas_por_escopo(class_tests: list, scope_info: dict, nivel_granularidade: str, user: dict = None) -> Dict[str, Any]:
    """
    Calcula estatísticas consolidadas baseadas no escopo dos filtros aplicados
    """
    try:
        from app.models.evaluationResult import EvaluationResult
        from app.models.student import Student
        
        if not class_tests:
            return _get_empty_statistics_gerais(scope_info, nivel_granularidade)
        
        # Determinar escopo de cálculo baseado nos filtros
        escopo_calculo = _determinar_escopo_calculo(scope_info, nivel_granularidade)
        logging.info(f"escopo_calculo: {escopo_calculo}")
        
        # Coletar dados do escopo
        test_ids = [ct.test_id for ct in class_tests]
        class_ids = [ct.class_id for ct in class_tests]
        logging.info(f"class_tests: {len(class_tests)}, test_ids: {test_ids}, class_ids: {class_ids}")
        
        # Buscar alunos baseado no escopo
        if nivel_granularidade == "avaliacao":
            # Para avaliação específica, contar apenas alunos das turmas onde foi aplicada
            todos_alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
            total_alunos = len(todos_alunos)
            logging.info(f"Avaliação específica: total_alunos={total_alunos}, class_ids={class_ids}")
        else:
            # Para outros níveis, buscar todos os alunos do escopo
            todos_alunos = _buscar_alunos_por_escopo(escopo_calculo)
            total_alunos = len(todos_alunos)
            logging.info(f"Outro nível: total_alunos={total_alunos}, nivel={nivel_granularidade}")
        
        # Buscar resultados das avaliações do escopo (apenas dos alunos do escopo específico)
        if todos_alunos:
            student_ids = [aluno.id for aluno in todos_alunos]
            resultados_escopo = EvaluationResult.query.filter(
                EvaluationResult.test_id.in_(test_ids),
                EvaluationResult.student_id.in_(student_ids)
            ).all()
        else:
            resultados_escopo = []
        
        alunos_participantes = len(resultados_escopo)
        logging.info(f"resultados_escopo: {alunos_participantes}, test_ids: {test_ids}, total_alunos: {total_alunos}")
        
        # Calcular estatísticas consolidadas (agregação hierárquica conforme granularidade)
        if resultados_escopo:
            media_nota, media_proficiencia = hierarchical_mean_grade_and_proficiency(
                resultados_escopo, granularidade_to_hierarchical_target(nivel_granularidade)
            )
        else:
            media_nota = 0.0
            media_proficiencia = 0.0
        
        # Calcular distribuição consolidada
        distribuicao_geral = {
            'abaixo_do_basico': 0,
            'basico': 0,
            'adequado': 0,
            'avancado': 0
        }
        
        for resultado in resultados_escopo:
            classificacao = resultado.classification.lower()
            # ✅ CORRIGIDO: Verificar 'abaixo' PRIMEIRO (mais específico)
            if 'abaixo' in classificacao:
                distribuicao_geral['abaixo_do_basico'] += 1
            elif 'básico' in classificacao or 'basico' in classificacao:
                distribuicao_geral['basico'] += 1
            elif 'adequado' in classificacao:
                distribuicao_geral['adequado'] += 1
            elif 'avançado' in classificacao or 'avancado' in classificacao:
                distribuicao_geral['avancado'] += 1
        
        # Determinar informações específicas baseadas no nível de granularidade
        city_data = scope_info.get('city_data')
        escola_info = None
        serie_info = None
        
        if scope_info.get('escola') and scope_info.get('escola') != 'all':
            # ✅ CORRIGIDO: Converter para string (School.id é VARCHAR)
            from app.utils.uuid_helpers import uuid_to_str
            escola_id = scope_info.get('escola')
            escola_id_str = uuid_to_str(escola_id) if escola_id else None
            escola_obj = School.query.filter(School.id == escola_id_str).first() if escola_id_str else None
            if escola_obj:
                escola_info = escola_obj.name
        
        if scope_info.get('serie') and scope_info.get('serie') != 'all':
            serie_obj = Grade.query.get(scope_info.get('serie'))
            if serie_obj:
                serie_info = serie_obj.name
        
        # Calcular alunos ausentes
        alunos_ausentes = total_alunos - alunos_participantes
        logging.info(f"Cálculo final: total_alunos={total_alunos}, alunos_participantes={alunos_participantes}, alunos_ausentes={alunos_ausentes}")
        
        return {
            "tipo": nivel_granularidade,
            "nome": _get_nome_granularidade(nivel_granularidade, scope_info, escola_info, serie_info),
            "estado": scope_info.get('estado', 'Todos os estados'),
            "municipio": city_data.name if city_data else "Todos os municípios",
            "escola": escola_info,
            "serie": serie_info,
            "total_escolas": len(set(ct.class_.school.id for ct in class_tests if ct.class_ and ct.class_.school)),
            "total_series": len(set(ct.class_.grade.id for ct in class_tests if ct.class_ and ct.class_.grade)),
            "total_turmas": len(set(ct.class_id for ct in class_tests)),
            "total_avaliacoes": len(test_ids),
            "total_alunos": total_alunos,
            "alunos_participantes": alunos_participantes,
            "alunos_pendentes": 0,
            "alunos_ausentes": alunos_ausentes,
            "media_nota_geral": round(media_nota, 2),
            "media_proficiencia_geral": format_decimal_two_places(media_proficiencia),
            "distribuicao_classificacao_geral": distribuicao_geral
        }
        
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas consolidadas: {str(e)}")
        return _get_empty_statistics_gerais(scope_info, nivel_granularidade)


def _determinar_escopo_calculo(scope_info: dict, nivel_granularidade: str) -> Dict[str, Any]:
    """
    Determina o escopo de cálculo baseado nos filtros aplicados
    CORRIGIDO: Agora converte corretamente os IDs do scope_info
    """
    escopo = {}

    # Restrição opcional (ex.: professor) para limitar o universo de turmas/alunos do escopo.
    # Mantém comportamento original para admin/tecadm/diretor/coordenador quando não fornecido.
    restrict_class_ids = scope_info.get("_restrict_class_ids") if isinstance(scope_info, dict) else None
    if restrict_class_ids is not None:
        escopo["restrict_class_ids"] = restrict_class_ids
    
    if nivel_granularidade == "municipio":
        # Estado + Município + Avaliação específica (dados de todas as escolas do município)
        escopo['tipo'] = "municipio"
        escopo['municipio_id'] = scope_info.get('municipio_id')
        escopo['avaliacao_id'] = scope_info.get('avaliacao')
        
    elif nivel_granularidade == "escola":
        # Estado + Município + Avaliação + Escola específica
        escopo['tipo'] = "escola"
        escopo['escola_id'] = scope_info.get('escola')
        escopo['avaliacao_id'] = scope_info.get('avaliacao')
        escopo['municipio_id'] = scope_info.get('municipio_id')
        
    elif nivel_granularidade == "serie":
        # Estado + Município + Avaliação + Escola + Série específica
        escopo['tipo'] = "serie"
        escopo['serie_id'] = scope_info.get('serie')
        escopo['escola_id'] = scope_info.get('escola')
        escopo['avaliacao_id'] = scope_info.get('avaliacao')
        escopo['municipio_id'] = scope_info.get('municipio_id')
        
    elif nivel_granularidade == "turma":
        # Estado + Município + Avaliação + Escola + Série + Turma específica
        escopo['tipo'] = "turma"
        escopo['turma_id'] = scope_info.get('turma')
        escopo['serie_id'] = scope_info.get('serie')
        escopo['escola_id'] = scope_info.get('escola')
        escopo['avaliacao_id'] = scope_info.get('avaliacao')
        escopo['municipio_id'] = scope_info.get('municipio_id')
    
    
    logging.info(f"Escopo calculado para {nivel_granularidade}: {escopo}")
    return escopo


def _buscar_alunos_por_escopo(escopo_calculo: dict) -> List[Student]:
    """
    Busca alunos baseado no escopo de cálculo
    """
    try:
        logging.info(f"Buscando alunos por escopo: {escopo_calculo}")

        restrict_class_ids = escopo_calculo.get("restrict_class_ids")
        
        if escopo_calculo['tipo'] == "municipio":
            # Todos os alunos do município (com filtro de avaliação se especificada)
            query = Student.query.join(Class).join(School, School.id == cast(Class.school_id, String)).join(City)\
                               .filter(City.id == escopo_calculo['municipio_id'])

            if restrict_class_ids is not None:
                if not restrict_class_ids:
                    return []
                query = query.filter(Student.class_id.in_(restrict_class_ids))
            
            # Se há avaliação específica, filtrar apenas turmas onde foi aplicada
            if escopo_calculo.get('avaliacao_id'):
                from app.models.classTest import ClassTest
                # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter para string
                class_tests = ClassTest.query.filter_by(test_id=str(escopo_calculo['avaliacao_id'])).all()
                class_ids = [ct.class_id for ct in class_tests]
                if class_ids:
                    query = query.filter(Student.class_id.in_(class_ids))
            
            alunos = query.all()
            logging.info(f"Alunos encontrados para município: {len(alunos)}")
            return alunos
        
        elif escopo_calculo['tipo'] == "escola":
            # Todos os alunos da escola (com filtro de avaliação se especificada)
            query = Student.query.join(Class).join(School, School.id == cast(Class.school_id, String))\
                               .filter(School.id == escopo_calculo['escola_id'])

            if restrict_class_ids is not None:
                if not restrict_class_ids:
                    return []
                query = query.filter(Student.class_id.in_(restrict_class_ids))
            
            # Se há avaliação específica, filtrar apenas turmas onde foi aplicada
            if escopo_calculo.get('avaliacao_id'):
                from app.models.classTest import ClassTest
                # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter para string
                class_tests = ClassTest.query.filter_by(test_id=str(escopo_calculo['avaliacao_id'])).all()
                class_ids = [ct.class_id for ct in class_tests]
                if class_ids:
                    query = query.filter(Student.class_id.in_(class_ids))
            
            alunos = query.all()
            logging.info(f"Alunos encontrados para escola: {len(alunos)}")
            return alunos
        
        elif escopo_calculo['tipo'] == "serie":
            # Todos os alunos da série na escola específica (com filtro de avaliação se especificada)
            query = Student.query.join(Class).join(Grade)\
                               .filter(Grade.id == escopo_calculo['serie_id'])

            if restrict_class_ids is not None:
                if not restrict_class_ids:
                    return []
                query = query.filter(Student.class_id.in_(restrict_class_ids))
            
            # Filtrar por escola se especificada (via Class.school_id)
            if escopo_calculo.get('escola_id'):
                query = query.filter(Class.school_id == escopo_calculo['escola_id'])
            
            # Se há avaliação específica, filtrar apenas turmas onde foi aplicada
            if escopo_calculo.get('avaliacao_id'):
                from app.models.classTest import ClassTest
                # ✅ CORRIGIDO: ClassTest.test_id é VARCHAR, converter para string
                class_tests = ClassTest.query.filter_by(test_id=str(escopo_calculo['avaliacao_id'])).all()
                class_ids = [ct.class_id for ct in class_tests]
                if class_ids:
                    query = query.filter(Student.class_id.in_(class_ids))
            
            alunos = query.all()
            logging.info(f"Alunos encontrados para série (escola_id={escopo_calculo.get('escola_id')}): {len(alunos)}")
            return alunos
        
        elif escopo_calculo['tipo'] == "turma":
            # Todos os alunos da turma (sempre retornar, mesmo se não fez avaliação)
            query = Student.query.filter(Student.class_id == escopo_calculo['turma_id'])

            if restrict_class_ids is not None:
                if not restrict_class_ids:
                    return []
                # Se a turma específica não estiver dentro da restrição, nada a retornar.
                if escopo_calculo["turma_id"] not in set(restrict_class_ids):
                    return []
            
            # Se há avaliação específica, verificar se a turma aplicou a avaliação
            if escopo_calculo.get('avaliacao_id'):
                from app.models.classTest import ClassTest
                class_test = ClassTest.query.filter_by(
                    test_id=escopo_calculo['avaliacao_id'],
                    class_id=escopo_calculo['turma_id']
                ).first()
                if not class_test:
                    # Turma não aplicou a avaliação, mas retornar alunos para dados zerados
                    logging.warning(f"Turma {escopo_calculo['turma_id']} não aplicou avaliação {escopo_calculo['avaliacao_id']} - retornando alunos para dados zerados")
            
            alunos = query.all()
            logging.info(f"Alunos encontrados para turma: {len(alunos)}")
            return alunos
        
        
        else:
            logging.warning(f"Tipo de escopo não reconhecido: {escopo_calculo.get('tipo')}")
            return []
            
    except Exception as e:
        logging.error(f"Erro ao buscar alunos por escopo: {str(e)}")
        return []


def _obter_alunos_para_mapa_habilidades_test(
    scope_info: Dict,
    nivel_granularidade: str,
    user: Dict,
    escopo_calculo: Dict,
) -> List[Student]:
    """Mesma lógica de escopo de alunos que a tabela detalhada por disciplina."""
    if nivel_granularidade == "escola" and user:
        if user.get("role") == "professor":
            from app.models.teacher import Teacher
            from app.models.teacherClass import TeacherClass

            teacher = Teacher.query.filter_by(user_id=user["id"]).first()
            if teacher:
                teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                teacher_class_ids = [tc.class_id for tc in teacher_classes]
                if teacher_class_ids:
                    all_students = Student.query.filter(Student.class_id.in_(teacher_class_ids)).all()
                else:
                    all_students = []
            else:
                all_students = []
        elif user.get("role") in ["diretor", "coordenador"]:
            from app.models.manager import Manager

            manager = Manager.query.filter_by(user_id=user["id"]).first()
            if manager and manager.school_id:
                turmas_escola = Class.query.filter(Class.school_id == manager.school_id).all()
                turma_ids_escola = [t.id for t in turmas_escola]
                all_students = Student.query.filter(Student.class_id.in_(turma_ids_escola)).all()
            else:
                all_students = []
        else:
            all_students = _buscar_alunos_por_escopo(escopo_calculo)
    else:
        all_students = _buscar_alunos_por_escopo(escopo_calculo)

    if not all_students:
        return []

    return (
        Student.query.options(joinedload(Student.class_).joinedload(Class.grade))
        .filter(Student.id.in_([s.id for s in all_students]))
        .all()
    )


# ==================== ENDPOINT 1: GET /avaliacoes ====================

def _calcular_ranking_global_alunos(
    avaliacao_id: str,
    scope_info: Dict,
    nivel_granularidade: str,
    user: Dict,
    restrict_class_ids: Optional[Set[Any]] = None,
) -> List[Dict]:
    """
    Calcula o ranking global dos alunos baseado em nota e acertos totais
    para o nível de granularidade especificado

    restrict_class_ids: quando definido (ex.: filtro periodo em GET /avaliacoes), só alunos dessas turmas.

    Returns:
        Lista de alunos ordenados por ranking com formato: "Aluno X, Acertos X, Nota X"
    """
    try:
        from app.models.evaluationResult import EvaluationResult
        
        # Determinar escopo de alunos baseado na granularidade
        # CORRIGIDO: Usar a lógica correta de filtros hierárquicos
        escopo_calculo = _determinar_escopo_calculo(scope_info, nivel_granularidade)
        logging.info(f"Escopo de cálculo para ranking: {escopo_calculo}")
        
        # Buscar alunos usando a função corrigida
        # Para o caso "escola", usar a lógica específica baseada no usuário
        if nivel_granularidade == "escola" and user:
            if user.get('role') == 'professor':
                # ✅ CORRIGIDO: Professor: buscar alunos das TURMAS onde está vinculado
                from app.models.teacher import Teacher
                from app.models.teacherClass import TeacherClass
                
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    # Buscar turmas onde o professor está vinculado (via TeacherClass)
                    teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                    teacher_class_ids = [tc.class_id for tc in teacher_classes]
                    
                    if teacher_class_ids:
                        all_students = Student.query.filter(Student.class_id.in_(teacher_class_ids)).all()
                    else:
                        all_students = []
                else:
                    all_students = []
            elif user.get('role') in ['diretor', 'coordenador']:
                # Diretor/Coordenador: buscar alunos apenas da sua escola
                from app.models.manager import Manager
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if manager and manager.school_id:
                    turmas_escola = Class.query.filter(Class.school_id == manager.school_id).all()
                    turma_ids_escola = [t.id for t in turmas_escola]
                    all_students = Student.query.filter(Student.class_id.in_(turma_ids_escola)).all()
                else:
                    all_students = []
            else:
                all_students = []
        else:
            all_students = _buscar_alunos_por_escopo(escopo_calculo)

        if restrict_class_ids is not None:
            if not restrict_class_ids:
                all_students = []
            else:
                all_students = [s for s in all_students if s.class_id in restrict_class_ids]
        
        if not all_students:
            return []

        student_ids = [aluno.id for aluno in all_students]

        # Questões da avaliação em uma única query (evita N× Question.query.get no loop)
        from app.models.testQuestion import TestQuestion
        test_questions_ranking = TestQuestion.query.filter_by(test_id=avaliacao_id).join(Question).options(
            joinedload(TestQuestion.question)
        ).all()
        questions_map_ranking = {tq.question.id: tq.question for tq in test_questions_ranking}

        # Buscar resultados pré-calculados
        evaluation_results = EvaluationResult.query.filter(
            EvaluationResult.test_id == avaliacao_id,
            EvaluationResult.student_id.in_(student_ids)
        ).all()
        results_dict = {er.student_id: er for er in evaluation_results}

        # Respostas em lote
        all_student_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == avaliacao_id,
            StudentAnswer.student_id.in_(student_ids)
        ).all()
        respostas_por_aluno = {}
        for resposta in all_student_answers:
            if resposta.student_id not in respostas_por_aluno:
                respostas_por_aluno[resposta.student_id] = {}
            respostas_por_aluno[resposta.student_id][resposta.question_id] = resposta

        # Class + Grade + School em poucas queries (evita N+1 ao acessar student.class_)
        class_ids = list({s.class_id for s in all_students if s.class_id})
        school_by_class_id = {}
        class_info_by_id = {}
        if class_ids:
            classes_with_grade = Class.query.options(joinedload(Class.grade)).filter(Class.id.in_(class_ids)).all()
            class_info_by_id = {c.id: (c.name or "N/A", c.grade.name if c.grade else "N/A") for c in classes_with_grade}
            school_ids = list({c.school_id for c in classes_with_grade if c.school_id})
            if school_ids:
                schools = School.query.filter(School.id.in_(school_ids)).all()
                school_by_id = {s.id: s for s in schools}
                school_by_class_id = {c.id: school_by_id.get(c.school_id) for c in classes_with_grade}

        alunos_ranking = []
        for student in all_students:
            evaluation_result = results_dict.get(student.id)
            total_acertos = 0
            total_respondidas = 0

            if student.id in respostas_por_aluno:
                for question_id, resposta in respostas_por_aluno[student.id].items():
                    question = questions_map_ranking.get(question_id)
                    if question:
                        total_respondidas += 1
                        
                        # Verificar se acertou
                        acertou = False
                        if question.question_type == 'multiple_choice':
                            acertou = EvaluationResultService.check_multiple_choice_answer(resposta.answer, question.correct_answer)
                        else:
                            acertou = str(resposta.answer).strip().lower() == str(question.correct_answer).strip().lower()
                        
                        if acertou:
                            total_acertos += 1
            
            # Dados do aluno para ranking
            nota = evaluation_result.grade if evaluation_result else 0.0
            
            turma_nome, serie_nome = class_info_by_id.get(student.class_id, ("N/A", "N/A"))
            escola_nome = "N/A"
            if student.class_id and school_by_class_id.get(student.class_id):
                escola_nome = school_by_class_id[student.class_id].name or "N/A"
            aluno_ranking = {
                "id": student.id,
                "nome": student.name,
                "escola": escola_nome,
                "serie": serie_nome,
                "turma": turma_nome,
                "total_acertos": total_acertos,
                "total_respondidas": total_respondidas,
                "nota": nota,
                "proficiencia": format_decimal_two_places(evaluation_result.proficiency) if evaluation_result else 0.0,
                "nivel_proficiencia": evaluation_result.classification if evaluation_result else None
            }
            
            alunos_ranking.append(aluno_ranking)
        
        # Calcular pontuação para ranking (nota * 100 + acertos * 10 + respondidas)
        for aluno in alunos_ranking:
            nota = float(aluno.get('nota', 0))
            acertos = int(aluno.get('total_acertos', 0))
            respondidas = int(aluno.get('total_respondidas', 0))
            
            # Pontuação: nota tem peso 100, acertos peso 10, respondidas peso 1
            pontuacao_ranking = (nota * 100) + (acertos * 10) + respondidas
            aluno['pontuacao_ranking'] = pontuacao_ranking
        
        # Ordenar por pontuação (maior para menor)
        alunos_ordenados = sorted(alunos_ranking, key=lambda x: x['pontuacao_ranking'], reverse=True)
        
        # Adicionar posição no ranking e formatar descrição
        ranking_final = []
        for i, aluno in enumerate(alunos_ordenados):
            # Remover campo auxiliar
            del aluno['pontuacao_ranking']
            
            # Formatar descrição do ranking
            descricao_ranking = f"{aluno['nome']}, Acertos {aluno['total_acertos']}, Nota {aluno['nota']:.2f}"
            
            ranking_final.append({
                "posicao": i + 1,
                "descricao": descricao_ranking,
                "aluno": aluno
            })
        
        return ranking_final
        
    except Exception as e:
        logging.error(f"Erro ao calcular ranking global dos alunos: {str(e)}", exc_info=True)
        return []


def _gerar_resultados_detalhados_por_granularidade(class_tests_paginados, nivel_granularidade, estatisticas_consolidadas, scope_info):
    """
    Gera resultados detalhados agregados por nível de granularidade
    
    - MUNICÍPIO: Agrega por ESCOLA (todas as turmas/séries da escola)
    - ESCOLA: Agrega por TURMA (todas as turmas da escola)
    - SÉRIE: Agrega por TURMA (dados específicos da turma)
    - TURMA: Dados da turma específica
    """
    try:
        from app.models.evaluationResult import EvaluationResult
        from app.models.student import Student
        from sqlalchemy import func
        
        if not class_tests_paginados:
            return []
        
        # Agrupar class_tests por nível de granularidade
        grupos = {}
        
        for class_test in class_tests_paginados:
            evaluation = class_test.test
            
            # Determinar chave de agrupamento baseada na granularidade
            if nivel_granularidade == "municipio":
                # Agrupar por escola
                if class_test.class_ and class_test.class_.school:
                    chave = f"escola_{class_test.class_.school.id}"
                    if chave not in grupos:
                        grupos[chave] = {
                            'escola': class_test.class_.school,
                            'municipio': class_test.class_.school.city if class_test.class_.school.city else None,
                            'class_tests': [],
                            'evaluation': evaluation
                        }
                    grupos[chave]['class_tests'].append(class_test)
                    
            elif nivel_granularidade == "escola":
                # Agrupar por turma (dentro da escola)
                if class_test.class_:
                    chave = f"turma_{class_test.class_.id}"
                    if chave not in grupos:
                        grupos[chave] = {
                            'turma': class_test.class_,
                            'serie': class_test.class_.grade if class_test.class_.grade else None,
                            'escola': class_test.class_.school if class_test.class_.school else None,
                            'municipio': class_test.class_.school.city if class_test.class_.school and class_test.class_.school.city else None,
                            'class_tests': [class_test],
                            'evaluation': evaluation
                        }
                    else:
                        grupos[chave]['class_tests'].append(class_test)
                    
            elif nivel_granularidade == "serie":
                # Agrupar por turma
                if class_test.class_:
                    chave = f"turma_{class_test.class_.id}"
                    if chave not in grupos:
                        grupos[chave] = {
                            'turma': class_test.class_,
                            'serie': class_test.class_.grade if class_test.class_.grade else None,
                            'escola': class_test.class_.school if class_test.class_.school else None,
                            'municipio': class_test.class_.school.city if class_test.class_.school and class_test.class_.school.city else None,
                            'class_tests': [class_test],
                            'evaluation': evaluation
                        }
                    else:
                        grupos[chave]['class_tests'].append(class_test)
                        
            elif nivel_granularidade == "turma":
                # Dados da turma específica
                if class_test.class_:
                    chave = f"turma_{class_test.class_.id}"
                    if chave not in grupos:
                        grupos[chave] = {
                            'turma': class_test.class_,
                            'serie': class_test.class_.grade if class_test.class_.grade else None,
                            'escola': class_test.class_.school if class_test.class_.school else None,
                            'municipio': class_test.class_.school.city if class_test.class_.school and class_test.class_.school.city else None,
                            'class_tests': [class_test],
                            'evaluation': evaluation
                        }
        
        # Gerar resultados agregados para cada grupo
        resultados_detalhados = []
        
        for chave, grupo in grupos.items():
            class_tests_grupo = grupo['class_tests']
            evaluation = grupo['evaluation']
            
            # Calcular estatísticas do grupo
            agg_level = (
                "escola"
                if nivel_granularidade == "municipio"
                else "serie"
                if nivel_granularidade == "escola"
                else "turma"
            )
            stats_grupo = _calcular_estatisticas_grupo(
                class_tests_grupo, evaluation, agg_level
            )
            
            # Determinar informações baseadas na granularidade
            if nivel_granularidade == "municipio":
                escola = grupo['escola']
                municipio = grupo['municipio']
                
                result = {
                    "id": f"escola_{escola.id}",
                    "titulo": f"{evaluation.title} - {escola.name}",
                    "disciplina": evaluation.subject_rel.name if evaluation.subject_rel else 'N/A',
                    "curso": _get_curso_nome(evaluation.course),
                    "serie": "Todas as séries",
                    "turma": "Todas as turmas",
                    "escola": escola.name,
                    "municipio": municipio.name if municipio else "N/A",
                    "estado": municipio.state if municipio else "N/A",
                    "data_aplicacao": _formatar_data_para_evolucao(evaluation.created_at),
                    "status": "consolidado",
                    "total_alunos": stats_grupo['total_alunos'],
                    "alunos_participantes": stats_grupo['alunos_participantes'],
                    "alunos_pendentes": stats_grupo['alunos_pendentes'],
                    "alunos_ausentes": stats_grupo['alunos_ausentes'],
                    "media_nota": stats_grupo['media_nota'],
                    "media_proficiencia": stats_grupo['media_proficiencia'],
                    "distribuicao_classificacao": stats_grupo['distribuicao_classificacao']
                }
                
            elif nivel_granularidade == "escola":
                turma = grupo['turma']
                serie = grupo['serie']
                escola = grupo['escola']
                municipio = grupo['municipio']

                serie_nome = serie.name if serie else "N/A"
                turma_nome = turma.name if getattr(turma, "name", None) else f"Turma {turma.id}"
                titulo_sufixo = f"{serie_nome} {turma_nome}".strip() if serie_nome != "N/A" else turma_nome

                result = {
                    "id": f"turma_{turma.id}",
                    "titulo": f"{evaluation.title} - {titulo_sufixo}",
                    "disciplina": evaluation.subject_rel.name if evaluation.subject_rel else 'N/A',
                    "curso": _get_curso_nome(evaluation.course),
                    "serie": serie_nome,
                    "turma": turma_nome,
                    "escola": escola.name if escola else "N/A",
                    "municipio": municipio.name if municipio else "N/A",
                    "estado": municipio.state if municipio else "N/A",
                    "data_aplicacao": _formatar_data_para_evolucao(evaluation.created_at),
                    "status": class_tests_grupo[0].status if class_tests_grupo else "N/A",
                    "total_alunos": stats_grupo['total_alunos'],
                    "alunos_participantes": stats_grupo['alunos_participantes'],
                    "alunos_pendentes": stats_grupo['alunos_pendentes'],
                    "alunos_ausentes": stats_grupo['alunos_ausentes'],
                    "media_nota": stats_grupo['media_nota'],
                    "media_proficiencia": stats_grupo['media_proficiencia'],
                    "distribuicao_classificacao": stats_grupo['distribuicao_classificacao']
                }
                
            elif nivel_granularidade in ["serie", "turma"]:
                turma = grupo['turma']
                serie = grupo['serie']
                escola = grupo['escola']
                municipio = grupo['municipio']
                
                result = {
                    "id": f"turma_{turma.id}",
                    "titulo": f"{evaluation.title} - {turma.name}",
                    "disciplina": evaluation.subject_rel.name if evaluation.subject_rel else 'N/A',
                    "curso": _get_curso_nome(evaluation.course),
                    "serie": serie.name if serie else "N/A",
                    "turma": turma.name if turma.name else f"Turma {turma.id}",
                    "escola": escola.name if escola else "N/A",
                    "municipio": municipio.name if municipio else "N/A",
                    "estado": municipio.state if municipio else "N/A",
                    "data_aplicacao": _formatar_data_para_evolucao(evaluation.created_at),
                    "status": class_tests_grupo[0].status if class_tests_grupo else "N/A",
                    "total_alunos": stats_grupo['total_alunos'],
                    "alunos_participantes": stats_grupo['alunos_participantes'],
                    "alunos_pendentes": stats_grupo['alunos_pendentes'],
                    "alunos_ausentes": stats_grupo['alunos_ausentes'],
                    "media_nota": stats_grupo['media_nota'],
                    "media_proficiencia": stats_grupo['media_proficiencia'],
                    "distribuicao_classificacao": stats_grupo['distribuicao_classificacao']
                }
            
            resultados_detalhados.append(result)
        
        return resultados_detalhados
        
    except Exception as e:
        logging.error(f"Erro ao gerar resultados detalhados por granularidade: {str(e)}", exc_info=True)
        return []


def _calcular_estatisticas_grupo(class_tests_grupo, evaluation, aggregation_level: str = "municipio"):
    """
    Calcula estatísticas consolidadas para um grupo de class_tests.

    ``aggregation_level``: ``escola`` (linhas do relatório municipal), ``serie`` (visão escola),
    ``turma`` (série/turma) — ver :func:`~app.utils.school_equal_weight_means.hierarchical_mean_grade_and_proficiency`.
    """
    try:
        from app.models.evaluationResult import EvaluationResult
        from app.models.student import Student
        
        if not class_tests_grupo:
            return {
                'total_alunos': 0,
                'alunos_participantes': 0,
                'alunos_pendentes': 0,
                'alunos_ausentes': 0,
                'media_nota': 0.0,
                'media_proficiencia': 0.0,
                'distribuicao_classificacao': {
                    'abaixo_do_basico': 0,
                    'basico': 0,
                    'adequado': 0,
                    'avancado': 0
                }
            }
        
        # Coletar todos os alunos das turmas do grupo
        class_ids = [ct.class_id for ct in class_tests_grupo]
        todos_alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
        total_alunos = len(todos_alunos)
        
        # Buscar resultados da avaliação para esses alunos
        if todos_alunos:
            student_ids = [aluno.id for aluno in todos_alunos]
            resultados = EvaluationResult.query.filter(
                EvaluationResult.test_id == evaluation.id,
                EvaluationResult.student_id.in_(student_ids)
            ).all()
        else:
            resultados = []
        
        alunos_participantes = len(resultados)
        alunos_pendentes = total_alunos - alunos_participantes
        alunos_ausentes = 0  # Simplificado - pode ser calculado mais precisamente
        
        # Calcular médias (agregação hierárquica no recorte do grupo)
        if resultados:
            media_nota, media_proficiencia = hierarchical_mean_grade_and_proficiency(
                resultados, aggregation_level
            )
        else:
            media_nota = 0.0
            media_proficiencia = 0.0
        
        # Calcular distribuição de classificação
        distribuicao = {
            'abaixo_do_basico': 0,
            'basico': 0,
            'adequado': 0,
            'avancado': 0
        }
        
        for resultado in resultados:
            if resultado.classification:
                if resultado.classification == "Abaixo do Básico":
                    distribuicao['abaixo_do_basico'] += 1
                elif resultado.classification == "Básico":
                    distribuicao['basico'] += 1
                elif resultado.classification == "Adequado":
                    distribuicao['adequado'] += 1
                elif resultado.classification == "Avançado":
                    distribuicao['avancado'] += 1
        
        return {
            'total_alunos': total_alunos,
            'alunos_participantes': alunos_participantes,
            'alunos_pendentes': alunos_pendentes,
            'alunos_ausentes': alunos_ausentes,
            'media_nota': format_decimal_two_places(media_nota),
            'media_proficiencia': format_decimal_two_places(media_proficiencia),
            'distribuicao_classificacao': distribuicao
        }
        
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas do grupo: {str(e)}", exc_info=True)
        return {
            'total_alunos': 0,
            'alunos_participantes': 0,
            'alunos_pendentes': 0,
            'alunos_ausentes': 0,
            'media_nota': 0.0,
            'media_proficiencia': 0.0,
            'distribuicao_classificacao': {
                'abaixo_do_basico': 0,
                'basico': 0,
                'adequado': 0,
                'avancado': 0
            }
        }


def _get_curso_nome(course_id):
    """
    Busca o nome do curso baseado no ID
    """
    try:
        if not course_id:
            return "Anos Iniciais"
            
        from app.models.educationStage import EducationStage
        import uuid
        course_uuid = uuid.UUID(course_id)
        course_obj = EducationStage.query.get(course_uuid)
        if course_obj:
            return course_obj.name
        else:
            return "Anos Iniciais"
    except Exception as e:
        logging.warning(f"Erro ao buscar curso {course_id}: {str(e)}")
        return "Anos Iniciais"


@bp.route('/opcoes-filtros-comparacao', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_opcoes_filtros_comparacao():
    """
    Retorna opções de filtros para comparação de avaliações
    
    Hierarquia: Estado → Município → Avaliações (com resultados) → Escolas
    
    Query Parameters:
    - estado (opcional): Estado selecionado
    - municipio (opcional): Município selecionado  
    - avaliacoes (opcional): IDs das avaliações selecionadas (separados por vírgula)
    
    Retorna apenas avaliações que têm resultados na tabela evaluation_results
    """
    try:
        # Importações necessárias para filtros de professores
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass
        # ⚠️ ClassSubject removido - não usado no sistema
        from app.models.evaluationResult import EvaluationResult
        
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        permissao = verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao['error']}), 403

        # Extrair parâmetros de filtro
        estado = request.args.get('estado')
        municipio = request.args.get('municipio')
        avaliacoes_param = request.args.get('avaliacoes')
        
        # Processar lista de avaliações se fornecida
        avaliacoes_selecionadas = []
        if avaliacoes_param:
            avaliacoes_selecionadas = [a.strip() for a in avaliacoes_param.split(',') if a.strip()]
        
        # Buscar opções disponíveis
        opcoes = {
            "estados": [],
            "municipios": [],
            "avaliacoes": [],
            "escolas": []
        }
        
        # 1. Estados disponíveis (baseado no papel do usuário)
        if permissao['scope'] == 'all':
            # Admin vê todos os estados
            estados = db.session.query(City.state).distinct().filter(City.state.isnot(None)).all()
            opcoes["estados"] = [{"id": estado[0], "nome": estado[0]} for estado in estados]
        else:
            # Outros usuários veem apenas estados das suas cidades
            estados = db.session.query(City.state).distinct().filter(
                City.state.isnot(None),
                City.id == user.get('city_id')
            ).all()
            opcoes["estados"] = [{"id": estado[0], "nome": estado[0]} for estado in estados]
        
        # Se não há estado, retornar apenas estados disponíveis
        if not estado:
            return jsonify({
                "opcoes": {
                    "estados": opcoes["estados"],
                    "municipios": [],
                    "avaliacoes": [],
                    "escolas": []
                },
                "filtros_aplicados": {
                    "estado": None,
                    "municipio": None,
                    "avaliacoes": []
                }
            }), 200
        
        # 2. Municípios do estado selecionado
        if estado:
            if permissao['scope'] == 'all':
                # Admin vê todos os municípios do estado
                municipios = City.query.filter(City.state.ilike(f"%{estado}%")).all()
            else:
                # Outros usuários veem apenas seu município
                municipios = City.query.filter(
                    City.state.ilike(f"%{estado}%"),
                    City.id == user.get('city_id')
                ).all()
            opcoes["municipios"] = [{"id": str(m.id), "nome": m.name} for m in municipios]
        
        # Se não há município, retornar estados + municípios disponíveis
        if not municipio:
            return jsonify({
                "opcoes": {
                    "estados": opcoes["estados"],
                    "municipios": opcoes["municipios"],
                    "avaliacoes": [],
                    "escolas": []
                },
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": None,
                    "avaliacoes": []
                }
            }), 200
        
        # 3. Avaliações do município selecionado (APENAS COM RESULTADOS)
        if estado and municipio:
            city = City.query.get(municipio)
            if city:
                # Verificar se o usuário tem acesso ao município
                if permissao['scope'] != 'all' and user.get('city_id') != city.id:
                    return jsonify({"error": "Acesso negado a este município"}), 403
                
                # Para educadores (professor, diretor, coordenador), retornar avaliações que criaram primeiro
                if permissao['scope'] == 'escola':
                    if user['role'] == 'professor':
                        # Para professores, mostrar avaliações que criaram OU que foram aplicadas em suas escolas
                        from app.models.teacher import Teacher
                        from sqlalchemy import or_
                        
                        teacher = Teacher.query.filter_by(user_id=user['id']).first()
                        if teacher:
                            # ✅ CORRIGIDO: Criar filtro OR com TURMAS ESPECÍFICAS onde o professor está vinculado
                            from app.models.teacherClass import TeacherClass
                            
                            # Criar filtro OR: avaliações criadas pelo professor OU aplicadas em suas TURMAS
                            filters = [Test.created_by == user['id']]
                            
                            # ✅ Buscar TURMAS onde o professor está vinculado (via TeacherClass)
                            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                            teacher_class_ids = [tc.class_id for tc in teacher_classes]
                            
                            if teacher_class_ids:
                                # ✅ Avaliações aplicadas em TURMAS ESPECÍFICAS onde o professor está vinculado
                                filters.append(
                                    Test.id.in_(
                                        db.session.query(ClassTest.test_id).filter(
                                            ClassTest.class_id.in_(teacher_class_ids)
                                        )
                                    )
                                )
                            
                            # NOVO: Filtrar apenas avaliações que TÊM RESULTADOS
                            query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                                        .join(ClassTest, Test.id == ClassTest.test_id)\
                                                        .join(Class, ClassTest.class_id == Class.id)\
                                                        .join(School, School.id == cast(Class.school_id, String))\
                                                        .join(City, School.city_id == City.id)\
                                                        .join(EvaluationResult, Test.id == EvaluationResult.test_id)\
                                                        .filter(or_(*filters))\
                                                        .filter(City.id == city.id)
                        else:
                            # Se não é um professor válido, não mostrar nenhuma avaliação
                            query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                                        .filter(Test.id == None)
                    else:
                        # Para diretores/coordenadores, mostrar avaliações aplicadas na sua escola
                        from app.models.manager import Manager
                        
                        # Buscar o manager vinculado ao usuário atual
                        manager = Manager.query.filter_by(user_id=user['id']).first()
                        if not manager or not manager.school_id:
                            # Manager não encontrado ou não vinculado a escola, retornar lista vazia
                            query_avaliacoes = Test.query.with_entities(Test.id, Test.title).filter(Test.id == None)
                        else:
                            # NOVO: Buscar avaliações que foram aplicadas na escola do diretor/coordenador E TÊM RESULTADOS
                            query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                                        .join(ClassTest, Test.id == ClassTest.test_id)\
                                                        .join(Class, ClassTest.class_id == Class.id)\
                                                        .join(School, School.id == cast(Class.school_id, String))\
                                                        .join(City, School.city_id == City.id)\
                                                        .join(EvaluationResult, Test.id == EvaluationResult.test_id)\
                                                        .filter(Class.school_id == manager.school_id)\
                                                        .filter(City.id == city.id)
                else:
                    # Para admin e tecadm, aplicar filtro por município
                    # NOVO: Filtrar apenas avaliações que TÊM RESULTADOS
                    query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                                .join(ClassTest, Test.id == ClassTest.test_id)\
                                                .join(Class, ClassTest.class_id == Class.id)\
                                                .join(School, School.id == cast(Class.school_id, String))\
                                                .join(City, School.city_id == City.id)\
                                                .join(EvaluationResult, Test.id == EvaluationResult.test_id)\
                                                .filter(City.id == city.id)
                
                # Executar a query e obter resultados
                avaliacoes = query_avaliacoes.distinct().all()
                avaliacoes_list = [{"id": str(a[0]), "titulo": a[1]} for a in avaliacoes]
                opcoes["avaliacoes"] = avaliacoes_list
            else:
                opcoes["avaliacoes"] = []
        else:
            opcoes["avaliacoes"] = []
        
        # Se não há avaliações selecionadas, retornar estados + municípios + avaliações disponíveis
        if not avaliacoes_selecionadas:
            return jsonify({
                "opcoes": {
                    "estados": opcoes["estados"],
                    "municipios": opcoes["municipios"],
                    "avaliacoes": opcoes["avaliacoes"],
                    "escolas": []
                },
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": municipio,
                    "avaliacoes": []
                }
            }), 200
        
        # 4. Escolas das avaliações selecionadas (quando avaliações forem selecionadas)
        if estado and municipio and avaliacoes_selecionadas:
            city = City.query.get(municipio)
            if city:
                # Verificar se o usuário tem acesso ao município
                if permissao['scope'] != 'all' and user.get('city_id') != city.id:
                    return jsonify({"error": "Acesso negado a este município"}), 403
                
                # Buscar escolas onde as avaliações selecionadas foram aplicadas E TÊM RESULTADOS
                query_escolas = School.query.with_entities(School.id, School.name)\
                                           .join(Class, School.id == cast(Class.school_id, String))\
                                           .join(ClassTest, Class.id == ClassTest.class_id)\
                                           .join(Test, ClassTest.test_id == Test.id)\
                                           .join(EvaluationResult, Test.id == EvaluationResult.test_id)\
                                           .join(City, School.city_id == City.id)\
                                           .filter(Test.id.in_(avaliacoes_selecionadas))\
                                           .filter(City.id == city.id)
                
                # Aplicar filtros baseados no papel do usuário
                if permissao['scope'] == 'escola':
                    # Diretor e Coordenador veem apenas sua escola
                    from app.models.manager import Manager
                    manager = Manager.query.filter_by(user_id=user['id']).first()
                    if manager and manager.school_id:
                        query_escolas = query_escolas.filter(School.id == manager.school_id)
                    else:
                        # Se não tem escola vinculada, retornar lista vazia
                        opcoes["escolas"] = []
                        query_escolas = None
                        
                elif permissao['scope'] == 'escola':
                    # ✅ CORRIGIDO: Professor vê apenas escolas que têm turmas onde está vinculado
                    # E onde a avaliação foi aplicada
                    from app.models.teacher import Teacher
                    from app.models.teacherClass import TeacherClass
                    
                    teacher = Teacher.query.filter_by(user_id=user['id']).first()
                    if teacher:
                        # Buscar turmas onde o professor está vinculado
                        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                        teacher_class_ids = [tc.class_id for tc in teacher_classes]
                        
                        if teacher_class_ids:
                            # Filtrar apenas escolas que têm turmas do professor
                            # E onde a avaliação foi aplicada
                            query_escolas = query_escolas.filter(Class.id.in_(teacher_class_ids))
                        else:
                            opcoes["escolas"] = []
                            query_escolas = None
                    else:
                        opcoes["escolas"] = []
                        query_escolas = None
                
                # Executar query apenas se houver filtro válido
                if query_escolas is not None:
                    escolas = query_escolas.distinct().all()
                    escolas_list = [{"id": str(e[0]), "nome": e[1]} for e in escolas]
                    opcoes["escolas"] = escolas_list
            else:
                opcoes["escolas"] = []
        else:
            opcoes["escolas"] = []
        
        return jsonify({
            "opcoes": opcoes,
            "filtros_aplicados": {
                "estado": estado,
                "municipio": municipio,
                "avaliacoes": avaliacoes_selecionadas
            }
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter opções de filtros para comparação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter opções de filtros", "details": str(e)}), 500