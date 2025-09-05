# -*- coding: utf-8 -*-
"""
Rotas especializadas para resultados de avaliações
Endpoints para análise de dados, estatísticas e relatórios
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.services.evaluation_calculator import EvaluationCalculator
from app.services.evaluation_filters import EvaluationFilters
from app.services.evaluation_aggregator import EvaluationAggregator
from app.services.evaluation_result_service import EvaluationResultService
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
from app.models.classTest import ClassTest
from app.models.schoolTeacher import SchoolTeacher
from app.models.skill import Skill
from app import db
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import func, case
from datetime import datetime
from sqlalchemy.orm import joinedload
import dateutil.parser

bp = Blueprint('evaluation_results', __name__, url_prefix='/evaluation-results')




def verificar_permissao_filtros(user: dict, scope_info: dict = None) -> Dict[str, Any]:
    """
    Verifica permissões do usuário para acessar filtros baseado no seu papel
    
    Args:
        user: Dicionário com informações do usuário logado
        scope_info: Dicionário com informações do escopo (opcional)
    
    Returns:
        Dict com informações de permissão e filtros aplicáveis
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
        # Professor vê avaliações que criou (simplificado)
        return {
            'permitted': True,
            'scope': 'escolas_vinculadas',
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

# ==================== ENDPOINTS TEMPORÁRIOS DE TESTE ====================

@bp.route('/grades', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def listar_grades():
    """
    Lista todas as grades (séries) disponíveis
    """
    try:
        grades = Grade.query.all()
        result = [{
            "id": str(grade.id),
            "name": grade.name,
            "education_stage_id": str(grade.education_stage_id) if grade.education_stage_id else None
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
    Formata um número para duas casas decimais sem arredondamento (trunca)
    """
    return float(f"{value:.2f}")

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
        
        # Buscar dados do escopo
        city_data = scope_info.get('city_data')
        
        # Aplicar filtros baseados nas permissões do usuário
        permissao = verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao['error']}), 403
        
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
            # Diretor e Coordenador veem apenas sua escola
            from app.models.manager import Manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if not manager or not manager.school_id:
                escola_ids = []  # Sem escola vinculada
            else:
                escola_ids = [escola.id for escola in escolas_escopo if escola.id == manager.school_id]
        elif permissao['scope'] == 'escolas_vinculadas':
            # Professor vê todas as escolas do escopo (simplificado para mostrar avaliações que criou)
            escola_ids = [escola.id for escola in escolas_escopo]
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
        if not escola_ids and avaliacao and avaliacao.lower() != 'all':
            return jsonify({
                "nivel_granularidade": "municipio",
                "filtros_aplicados": {
                    "estado": estado,
                    "municipio": municipio,
                    "escola": escola,
                    "serie": serie,
                    "turma": turma,
                    "avaliacao": avaliacao
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
            
            # Construir query base com filtros de permissões
            query_base = ClassTest.query.join(Test, ClassTest.test_id == Test.id)\
                                       .join(Class, ClassTest.class_id == Class.id)\
                                       .join(Grade, Class.grade_id == Grade.id)\
                                       .join(School, Class.school_id == School.id)\
                                       .join(City, School.city_id == City.id)\
                                       .options(
                                           joinedload(ClassTest.test).joinedload(Test.subject_rel),
                                           joinedload(ClassTest.class_).joinedload(Class.grade),
                                           joinedload(ClassTest.class_).joinedload(Class.school).joinedload(School.city)
                                       )
            
            # Aplicar filtros baseados nas permissões do usuário
            if permissao['scope'] == 'municipio':
                # Tecadm vê apenas avaliações do seu município
                query_base = query_base.filter(City.id == user.get('city_id'))
            elif permissao['scope'] == 'escola':
                # Diretor e Coordenador veem apenas avaliações da sua escola
                from app.models.manager import Manager
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if not manager or not manager.school_id:
                    # Se não tem manager ou escola vinculada, retornar lista vazia
                    query_base = query_base.filter(School.id == None)  # Força resultado vazio
                else:
                    query_base = query_base.filter(School.id == manager.school_id)
            elif permissao['scope'] == 'escolas_vinculadas':
                # Professor vê avaliações de todas as escolas (filtro será aplicado por created_by)
                pass
            
            # Aplicar filtro por escolas do escopo (se houver)
            if escola_ids:
                query_base = query_base.filter(School.id.in_(escola_ids))
            
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
                school_filter = School.query.get(escola)
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
            if permissao['scope'] == 'escolas_vinculadas' and user['role'] == 'professor':
                # Professor vê apenas avaliações que criou
                query_base = query_base.filter(Test.created_by == user['id'])
                
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
                                               .join(School, Class.school_id == School.id)\
                                               .join(City, School.city_id == City.id)\
                                               .filter(School.id.in_(escola_ids))\
                                               .options(
                                                   joinedload(ClassTest.test).joinedload(Test.subject_rel),
                                                   joinedload(ClassTest.class_).joinedload(Class.grade),
                                                   joinedload(ClassTest.class_).joinedload(Class.school).joinedload(School.city)
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
                        query_base = query_base.filter(Test.created_by == user['id'])
                    
                    todas_avaliacoes_escopo = query_base.all()
                    logging.info(f"Query executada com nova sessão: {len(todas_avaliacoes_escopo)} avaliações encontradas")
                else:
                    raise inner_e
                    
        except Exception as e:
            logging.error(f"Erro ao buscar avaliações do escopo: {str(e)}")
            db.session.rollback()
            return jsonify({"error": "Erro ao buscar avaliações", "details": str(e)}), 500
        
        # Determinar nível de granularidade
        nivel_granularidade = _determinar_nivel_granularidade(estado, municipio, escola, serie, turma, avaliacao)
        logging.info(f"nivel_granularidade: {nivel_granularidade}, estado: {estado}, municipio: {municipio}, escola: {escola}, serie: {serie}, turma: {turma}, avaliacao: {avaliacao}")
        
        # Calcular estatísticas consolidadas baseadas no escopo dos filtros
        estatisticas_consolidadas = _calcular_estatisticas_consolidadas_por_escopo(todas_avaliacoes_escopo, scope_info, nivel_granularidade)
        
        # Calcular estatísticas por disciplina
        resultados_por_disciplina = _calcular_estatisticas_por_disciplina(todas_avaliacoes_escopo)
        
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
                                               .join(School, Class.school_id == School.id)\
                                               .join(City, School.city_id == City.id)\
                                               .filter(School.id.in_(escola_ids))\
                                               .options(
                                                   joinedload(ClassTest.test).joinedload(Test.subject_rel),
                                                   joinedload(ClassTest.class_).joinedload(Class.grade),
                                                   joinedload(ClassTest.class_).joinedload(Class.school).joinedload(School.city)
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
                    if permissao['scope'] == 'escolas_vinculadas' and user['role'] == 'professor':
                        query_base = query_base.filter(Test.created_by == user['id'])
                    
                    total = query_base.count()
                    offset = (page - 1) * per_page
                    class_tests_paginados = query_base.offset(offset).limit(per_page).all()
                else:
                    raise inner_e
                    
        except Exception as e:
            logging.error(f"Erro ao aplicar paginação: {str(e)}")
            db.session.rollback()
            return jsonify({"error": "Erro ao aplicar paginação", "details": str(e)}), 500
        
        # Gerar resultados detalhados usando estatísticas consolidadas
        resultados_detalhados = []
        for class_test in class_tests_paginados:
            evaluation = class_test.test
            
            # Usar estatísticas consolidadas em vez de calcular individualmente
            stats = {
                'total_alunos': estatisticas_consolidadas['total_alunos'],
                'alunos_participantes': estatisticas_consolidadas['alunos_participantes'],
                'alunos_pendentes': estatisticas_consolidadas['alunos_pendentes'],
                'alunos_ausentes': estatisticas_consolidadas['alunos_ausentes'],
                'media_nota': estatisticas_consolidadas['media_nota_geral'],
                'media_proficiencia': estatisticas_consolidadas['media_proficiencia_geral'],
                'distribuicao_classificacao': estatisticas_consolidadas['distribuicao_classificacao_geral']
            }
            
            # Buscar informações da escola
            escola_nome = "N/A"
            municipio_nome = "N/A"
            estado_nome = "N/A"
            if class_test.class_ and class_test.class_.school:
                escola_nome = class_test.class_.school.name
                if class_test.class_.school.city:
                    municipio_nome = class_test.class_.school.city.name
                    estado_nome = class_test.class_.school.city.state
            
            # Buscar informações da turma e série
            serie_nome = "N/A"
            grade_id = None
            turma_nome = "N/A"
            if class_test.class_ and class_test.class_.grade:
                serie_nome = class_test.class_.grade.name
                grade_id = str(class_test.class_.grade.id)
                turma_nome = class_test.class_.name if class_test.class_.name else f"Turma {class_test.class_.id}"
            
            # Buscar nome do curso
            curso_nome = "N/A"
            if evaluation.course:
                try:
                    from app.models.educationStage import EducationStage
                    import uuid
                    course_uuid = uuid.UUID(evaluation.course)
                    course_obj = EducationStage.query.get(course_uuid)
                    if course_obj:
                        curso_nome = course_obj.name
                    else:
                        curso_nome = "Anos Iniciais"
                except Exception as e:
                    logging.warning(f"Erro ao buscar curso {evaluation.course}: {str(e)}")
                    curso_nome = "Anos Iniciais"
            
            result = {
                "id": evaluation.id,
                "titulo": evaluation.title,
                "disciplina": evaluation.subject_rel.name if evaluation.subject_rel else 'N/A',
                "curso": curso_nome,
                "serie": serie_nome,
                "turma": turma_nome,
                "escola": escola_nome,
                "municipio": municipio_nome,
                "estado": estado_nome,
                "data_aplicacao": evaluation.created_at.isoformat() if evaluation.created_at else None,
                "status": class_test.status,
                "total_alunos": stats['total_alunos'],
                "alunos_participantes": stats['alunos_participantes'],
                "alunos_pendentes": stats['alunos_pendentes'],
                "alunos_ausentes": stats['alunos_ausentes'],
                "media_nota": stats['media_nota'],
                "media_proficiencia": stats['media_proficiencia'],
                "distribuicao_classificacao": stats['distribuicao_classificacao']
            }
            
            resultados_detalhados.append(result)
        
        # Calcular total de páginas
        total_pages = (total + per_page - 1) // per_page
        
        # Gerar opções dos próximos filtros
        opcoes_proximos_filtros = _gerar_opcoes_proximos_filtros(scope_info, nivel_granularidade)
        
        # Gerar tabela detalhada por disciplina (apenas se uma avaliação específica for selecionada)
        tabela_detalhada = {}
        ranking_alunos = []
        
        if avaliacao and avaliacao.lower() != 'all':
            tabela_detalhada = _gerar_tabela_detalhada_por_disciplina(
                avaliacao, scope_info, nivel_granularidade, user
            )
            
            # Calcular ranking global dos alunos
            ranking_alunos = _calcular_ranking_global_alunos(
                avaliacao, scope_info, nivel_granularidade, user
            )
        
        return jsonify({
            "nivel_granularidade": nivel_granularidade,
            "filtros_aplicados": {
                "estado": estado,
                "municipio": municipio,
                "escola": escola,
                "serie": serie,
                "turma": turma,
                "avaliacao": avaliacao
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


def _gerar_tabela_detalhada_por_disciplina(avaliacao_id: str, scope_info: Dict, nivel_granularidade: str, user: Dict) -> Dict[str, Any]:
    """
    Gera tabela detalhada organizada por disciplina com dados dos alunos
    CORRIGIDA: Agora mostra TODOS os alunos em TODAS as disciplinas com TODAS as questões
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
                "numero": question.number or 1,
                "habilidade": skill_description,  # Descrição da habilidade
                "codigo_habilidade": skill_code,  # Código da habilidade
                "question_id": question.id  # Adicionar ID da questão para facilitar busca
            })
        
        # Determinar escopo de alunos baseado na granularidade
        class_tests = ClassTest.query.filter_by(test_id=avaliacao_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return {"disciplinas": list(questoes_por_disciplina.values())}
        
        # Buscar alunos baseado no escopo e filtros
        query_alunos = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade),
            joinedload(Student.class_).joinedload(Class.school).joinedload(School.city)
        ).filter(Student.class_id.in_(class_ids))
        
        # Log para debug
        logging.info(f"Total de turmas encontradas para avaliação {avaliacao_id}: {len(class_ids)}")
        logging.info(f"Turmas: {class_ids}")
        
        # Aplicar filtros baseados na granularidade
        if nivel_granularidade in ['escola', 'serie', 'turma']:
            # Fazer join com Class apenas uma vez
            query_alunos = query_alunos.join(Class)
            
            # Filtrar por escola se especificada
            if scope_info.get('escolas') and len(scope_info['escolas']) == 1:
                escola_id = scope_info['escolas'][0].id
                query_alunos = query_alunos.filter(Class.school_id == escola_id)
            
            # Filtrar por série se especificada
            if nivel_granularidade in ['serie', 'turma'] and scope_info.get('serie_id') and scope_info['serie_id'] != 'all':
                query_alunos = query_alunos.filter(Class.grade_id == scope_info['serie_id'])
            
            # Filtrar por turma se especificada
            if nivel_granularidade == 'turma' and scope_info.get('turma_id') and scope_info['turma_id'] != 'all':
                query_alunos = query_alunos.filter(Student.class_id == scope_info['turma_id'])
        
        all_students = query_alunos.all()
        
        # Log para debug
        logging.info(f"Total de alunos encontrados: {len(all_students)}")
        
        # Buscar resultados pré-calculados
        evaluation_results = EvaluationResult.query.filter_by(test_id=avaliacao_id).all()
        results_dict = {er.student_id: er for er in evaluation_results}
        
        logging.info(f"Total de resultados encontrados: {len(evaluation_results)}")
        
        # Buscar TODAS as respostas de TODOS os alunos para esta avaliação
        all_student_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == avaliacao_id
        ).all()
        
        # Criar dicionário de respostas por aluno
        respostas_por_aluno = {}
        for resposta in all_student_answers:
            if resposta.student_id not in respostas_por_aluno:
                respostas_por_aluno[resposta.student_id] = {}
            respostas_por_aluno[resposta.student_id][resposta.question_id] = resposta
        
        logging.info(f"Total de respostas encontradas: {len(all_student_answers)}")
        
        # Para cada disciplina, mostrar TODOS os alunos com TODAS as questões
        for subject_id, disciplina_data in questoes_por_disciplina.items():
            alunos_disciplina = []
            logging.info(f"Processando disciplina: {disciplina_data['nome']} (ID: {subject_id})")
            
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
                    if student.class_.school:
                        escola_nome = student.class_.school.name or "N/A"
                
                # Buscar resultado pré-calculado
                evaluation_result = results_dict.get(student.id)
                
                # Calcular acertos/erros por questão desta disciplina
                respostas_por_questao = []
                total_acertos = 0
                total_erros = 0
                total_respondidas = 0
                
                # Para cada questão desta disciplina, verificar se o aluno respondeu
                for questao_info in disciplina_data["questoes"]:
                    questao_numero = questao_info["numero"]
                    question_id = questao_info["question_id"]
                    
                    # Buscar a questão diretamente pelo ID (mais eficiente)
                    question = Question.query.get(question_id)
                    
                    if question:
                        # Verificar se o aluno respondeu esta questão
                        resposta_aluno = respostas_por_aluno.get(student.id, {}).get(question.id)
                        
                        if resposta_aluno:
                            # Aluno respondeu esta questão
                            total_respondidas += 1
                            
                            # Log detalhado para debug
                            logging.info(f"Verificando resposta do aluno {student.name} para questão {question.number}")
                            logging.info(f"Tipo da questão: {question.question_type}")
                            logging.info(f"Resposta do aluno: '{resposta_aluno.answer}' (tipo: {type(resposta_aluno.answer)})")
                            logging.info(f"Alternativas da questão: {question.alternatives}")
                            logging.info(f"Resposta correta: '{question.correct_answer}'")
                            
                            # Verificar se acertou
                            acertou = False
                            if question.question_type == 'multiple_choice':
                                logging.info(f"Questão de múltipla escolha - verificando com alternatives")
                                acertou = EvaluationResultService.check_multiple_choice_answer(resposta_aluno.answer, question.correct_answer)
                                logging.info(f"Resultado da verificação múltipla escolha: {acertou}")
                            else:
                                logging.info(f"Questão não é múltipla escolha - comparando respostas diretamente")
                                logging.info(f"Resposta do aluno: '{resposta_aluno.answer}' vs Resposta correta: '{question.correct_answer}'")
                                acertou = str(resposta_aluno.answer).strip().lower() == str(question.correct_answer).strip().lower()
                                logging.info(f"Resultado da verificação direta: {acertou}")
                            
                            if acertou:
                                total_acertos += 1
                                logging.info(f"Aluno {student.name} ACERTOU a questão {question.number}")
                            else:
                                total_erros += 1
                                logging.info(f"Aluno {student.name} ERROU a questão {question.number}")
                            
                            respostas_por_questao.append({
                                "questao": question.number or 1,
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
                            logging.info(f"Aluno {student.name} NÃO respondeu a questão {questao_info['numero']}")
                
                # CORREÇÃO: Calcular nota, proficiência e classificação baseado nos acertos específicos desta disciplina
                disciplina_nota = 0.0
                disciplina_proficiencia = 0.0
                disciplina_classificacao = "Abaixo do Básico"
                
                if total_respondidas > 0:
                    # Obter informações do curso da avaliação
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
                    
                    # Usar o EvaluationCalculator para calcular corretamente
                    from app.services.evaluation_calculator import EvaluationCalculator
                    result = EvaluationCalculator.calculate_complete_evaluation(
                        correct_answers=total_acertos,
                        total_questions=total_respondidas,
                        course_name=course_name,
                        subject_name=disciplina_data['nome']
                    )
                    
                    disciplina_nota = result['grade']
                    disciplina_proficiencia = result['proficiency']
                    disciplina_classificacao = result['classification']
                
                # Determinar status do aluno
                status = "concluida" if total_respondidas > 0 else "pendente"
                
                # Dados do aluno para esta disciplina (sempre incluído, mesmo sem respostas)
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
                    "percentual_acertos": round((total_acertos / total_respondidas * 100), 2) if total_respondidas > 0 else 0.0
                }
                
                alunos_disciplina.append(aluno_disciplina)
                logging.info(f"Aluno {student.name} processado para disciplina {disciplina_data['nome']}: {total_respondidas} questões respondidas, {total_acertos} acertos, {total_erros} erros")
            
            disciplina_data["alunos"] = alunos_disciplina
            logging.info(f"Disciplina {disciplina_data['nome']}: {len(alunos_disciplina)} alunos processados")
        
        # NOVA FUNCIONALIDADE: Calcular dados gerais (média de todas as disciplinas)
        # Obter informações do curso da avaliação para classificação geral
        course_name = "Anos Iniciais"  # Padrão
        if test.course:
            try:
                from app.models.educationStage import EducationStage
                import uuid
                course_uuid = uuid.UUID(test.course)
                course_obj = EducationStage.query.get(course_uuid)
                if course_obj:
                    course_name = course_obj.name
            except (ValueError, TypeError, Exception):
                pass
        
        dados_gerais = _calcular_dados_gerais_alunos(questoes_por_disciplina, course_name)
        
        return {
            "disciplinas": list(questoes_por_disciplina.values()),
            "geral": dados_gerais
        }
        
    except Exception as e:
        logging.error(f"Erro ao gerar tabela detalhada por disciplina: {str(e)}", exc_info=True)
        return {"disciplinas": [], "geral": {"alunos": []}, "error": str(e)}


def _calcular_dados_gerais_alunos(questoes_por_disciplina: dict, course_name: str = "Anos Iniciais") -> dict:
    """
    Calcula dados gerais (média de todas as disciplinas) para cada aluno
    """
    try:
        # Criar dicionário para armazenar dados consolidados por aluno
        dados_alunos = {}
        
        # Para cada disciplina, coletar dados dos alunos
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
                
                # Acumular dados das disciplinas
                dados_alunos[aluno_id]["notas_disciplinas"].append(aluno_data["nota"])
                dados_alunos[aluno_id]["proficiencias_disciplinas"].append(aluno_data["proficiencia"])
                dados_alunos[aluno_id]["total_acertos_geral"] += aluno_data["total_acertos"]
                dados_alunos[aluno_id]["total_questoes_geral"] += aluno_data["total_questoes_disciplina"]
                dados_alunos[aluno_id]["total_respondidas_geral"] += aluno_data["total_respondidas"]
        
        # Calcular médias e classificação geral para cada aluno
        alunos_gerais = []
        for aluno_id, dados in dados_alunos.items():
            # Calcular médias
            if dados["notas_disciplinas"]:
                nota_geral = sum(dados["notas_disciplinas"]) / len(dados["notas_disciplinas"])
                proficiencia_geral = sum(dados["proficiencias_disciplinas"]) / len(dados["proficiencias_disciplinas"])
            else:
                nota_geral = 0.0
                proficiencia_geral = 0.0
            
            # Calcular percentual geral
            if dados["total_questoes_geral"] > 0:
                percentual_acertos_geral = (dados["total_acertos_geral"] / dados["total_questoes_geral"]) * 100
            else:
                percentual_acertos_geral = 0.0
            
            # Determinar classificação geral baseada na proficiência média
            # CORREÇÃO: Para Anos Finais/Ensino Médio, usar faixas de Matemática
            if "finais" in course_name.lower() or "médio" in course_name.lower() or "medio" in course_name.lower():
                # Faixas de Matemática para Anos Finais/Ensino Médio
                if proficiencia_geral >= 340:
                    nivel_proficiencia_geral = "Avançado"
                elif proficiencia_geral >= 290:
                    nivel_proficiencia_geral = "Adequado"
                elif proficiencia_geral >= 212.50:
                    nivel_proficiencia_geral = "Básico"
                else:
                    nivel_proficiencia_geral = "Abaixo do Básico"
            else:
                # Faixas padrão para outros níveis (Educação Infantil/Anos Iniciais/EJA)
                if proficiencia_geral >= 263:
                    nivel_proficiencia_geral = "Avançado"
                elif proficiencia_geral >= 213:
                    nivel_proficiencia_geral = "Adequado"
                elif proficiencia_geral >= 163:
                    nivel_proficiencia_geral = "Básico"
                else:
                    nivel_proficiencia_geral = "Abaixo do Básico"
            
            # Determinar status geral
            status_geral = "concluida" if dados["total_respondidas_geral"] > 0 else "pendente"
            
            aluno_geral = {
                "id": dados["id"],
                "nome": dados["nome"],
                "escola": dados["escola"],
                "serie": dados["serie"],
                "turma": dados["turma"],
                "nota_geral": round(nota_geral, 2),
                "proficiencia_geral": format_decimal_two_places(proficiencia_geral),
                "nivel_proficiencia_geral": nivel_proficiencia_geral,
                "total_acertos_geral": dados["total_acertos_geral"],
                "total_questoes_geral": dados["total_questoes_geral"],
                "total_respondidas_geral": dados["total_respondidas_geral"],
                "total_em_branco_geral": dados["total_questoes_geral"] - dados["total_respondidas_geral"],
                "percentual_acertos_geral": round(percentual_acertos_geral, 2),
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
    class_tests = ClassTest.query.filter_by(test_id=test_id).all()
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
            # Aluno NÃO respondeu - contar como "Abaixo do Básico"
            classificacoes['Abaixo do Básico'] += 1
    
    # Calcular médias apenas dos alunos que participaram
    media_nota = round(sum(notas) / len(notas), 2) if notas else 0.0
    media_proficiencia = format_decimal_two_places(sum(proficiencias) / len(proficiencias)) if proficiencias else 0.0
    
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
    
    # Calcular médias apenas dos alunos que participaram
    media_nota = round(sum(notas) / len(notas), 2) if notas else 0.0
    media_proficiencia = format_decimal_two_places(sum(proficiencias) / len(proficiencias)) if proficiencias else 0.0
    
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
            media_nota_geral = sum(r.grade for r in todos_resultados) / len(todos_resultados)
            media_proficiencia_geral = sum(r.proficiency for r in todos_resultados) / len(todos_resultados)
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
            if 'abaixo' in classificacao or 'básico' in classificacao:
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
            "alunos_ausentes": total_alunos - alunos_participantes,  # Calculado corretamente
            "media_nota_geral": round(media_nota_geral, 2),
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
        
        # Buscar escolas do escopo
        escolas = []
        
        # Se uma avaliação específica foi selecionada, buscar as escolas onde ela foi aplicada
        if is_valid_filter(avaliacao):
            # Buscar na tabela class_test todas as entradas para esta avaliação
            class_tests_avaliacao = ClassTest.query.filter_by(test_id=avaliacao).all()
            
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
                school = School.query.get(escola)
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
                # Diretor e Coordenador veem apenas sua escola
                from app.models.manager import Manager
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if not manager or not manager.school_id:
                    escolas = []  # Sem escola vinculada
                else:
                    escolas = [e for e in escolas if e.id == manager.school_id]
            elif permissao['scope'] == 'escolas_vinculadas':
                # Professor vê todas as escolas do escopo (filtro será por created_by na avaliação)
                pass
        
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


def _calcular_estatisticas_por_disciplina(class_tests: list):
    """
    Calcula estatísticas agrupadas por disciplina baseado nos acertos específicos de cada disciplina
    """
    try:
        from app.models.evaluationResult import EvaluationResult
        from app.models.student import Student
        from app.models.question import Question
        from app.models.subject import Subject
        from app.models.testQuestion import TestQuestion
        from app.models.studentAnswer import StudentAnswer
        from app.services.evaluation_result_service import EvaluationResultService
        
        if not class_tests:
            return []
        
        # Pegar a primeira avaliação para acessar subjects_info
        test = class_tests[0].test
        if not test or not test.subjects_info:
            return []
        
        # Buscar informações das disciplinas
        subject_ids = test.subjects_info
        subjects = Subject.query.filter(Subject.id.in_(subject_ids)).all()
        
        if not subjects:
            return []
        
        # Coletar dados das turmas
        class_ids = [ct.class_id for ct in class_tests]
        test_id = test.id
        
        # Buscar todos os alunos das turmas envolvidas
        todos_alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
        total_alunos = len(todos_alunos)
        
        # Buscar alunos que participaram da avaliação
        evaluation_results = EvaluationResult.query.filter_by(test_id=test_id).all()
        alunos_participantes = len(evaluation_results)
        
        resultados_disciplina = []
        
        for subject in subjects:
            # Buscar questões desta disciplina para esta avaliação
            questions = Question.query.filter(
                Question.subject_id == subject.id
            ).join(TestQuestion).filter(
                TestQuestion.test_id == test_id
            ).all()
            
            if not questions:
                continue
            
            total_questions_disciplina = len(questions)
            question_ids = [q.id for q in questions]
            
            # CORREÇÃO: Calcular estatísticas baseadas nos acertos específicos desta disciplina
            notas_disciplina = []
            proficiencias_disciplina = []
            classificacoes_disciplina = {'Abaixo do Básico': 0, 'Básico': 0, 'Adequado': 0, 'Avançado': 0}
            
            for student in todos_alunos:
                # Buscar respostas do aluno para esta disciplina específica
                answers = StudentAnswer.query.filter(
                    StudentAnswer.test_id == test_id,
                    StudentAnswer.student_id == student.id,
                    StudentAnswer.question_id.in_(question_ids)
                ).all()
                
                if not answers:
                    continue
                
                # Calcular acertos específicos desta disciplina
                acertos_disciplina = 0
                for answer in answers:
                    question = next((q for q in questions if q.id == answer.question_id), None)
                    if question:
                        if question.question_type == 'multiple_choice':
                            is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                        else:
                            is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                        
                        if is_correct:
                            acertos_disciplina += 1
                
                # Calcular nota e proficiência para esta disciplina específica
                if total_questions_disciplina > 0:
                    percentual_acertos = (acertos_disciplina / total_questions_disciplina) * 100
                    nota_disciplina = format_decimal_two_places(percentual_acertos / 10)
                    proficiencia_disciplina = format_decimal_two_places((acertos_disciplina / total_questions_disciplina) * 400)
                    
                    notas_disciplina.append(nota_disciplina)
                    proficiencias_disciplina.append(proficiencia_disciplina)
                    
                    # Determinar classificação baseada na proficiência específica da disciplina
                    if proficiencia_disciplina >= 300:
                        classificacoes_disciplina['Avançado'] += 1
                    elif proficiencia_disciplina >= 200:
                        classificacoes_disciplina['Adequado'] += 1
                    elif proficiencia_disciplina >= 100:
                        classificacoes_disciplina['Básico'] += 1
                    else:
                        classificacoes_disciplina['Abaixo do Básico'] += 1
            
            # Calcular médias da disciplina
            if notas_disciplina:
                media_nota_disciplina = format_decimal_two_places(sum(notas_disciplina) / len(notas_disciplina))
                media_proficiencia_disciplina = format_decimal_two_places(sum(proficiencias_disciplina) / len(proficiencias_disciplina))
            else:
                media_nota_disciplina = 0.0
                media_proficiencia_disciplina = 0.0
            
            # Converter classificação para o formato esperado
            distribuicao_disciplina = {
                'abaixo_do_basico': classificacoes_disciplina['Abaixo do Básico'],
                'basico': classificacoes_disciplina['Básico'],
                'adequado': classificacoes_disciplina['Adequado'],
                'avancado': classificacoes_disciplina['Avançado']
            }
            
            resultado_disciplina = {
                "disciplina": subject.name,
                "total_avaliacoes": 1,  # Uma avaliação pode ter múltiplas disciplinas
                "total_alunos": total_alunos,
                "alunos_participantes": alunos_participantes,
                "alunos_pendentes": total_alunos - alunos_participantes,
                "alunos_ausentes": 0,
                "media_nota": media_nota_disciplina,
                "media_proficiencia": media_proficiencia_disciplina,
                "distribuicao_classificacao": distribuicao_disciplina
            }
            
            resultados_disciplina.append(resultado_disciplina)
        
        return resultados_disciplina
        
    except Exception as e:
        logging.error(f"Erro ao calcular estatísticas por disciplina: {str(e)}")
        return []


def _determinar_nivel_granularidade(estado, municipio, escola, serie, turma, avaliacao):
    """
    Determina o nível de granularidade baseado nos filtros aplicados
    """
    nivel = None
    if avaliacao:
        nivel = "avaliacao"
    elif turma:
        nivel = "turma"
    elif serie:
        nivel = "serie"
    elif escola:
        nivel = "escola"
    elif municipio:
        nivel = "municipio"
    elif estado:
        nivel = "estado"
    else:
        nivel = "geral"
    
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
        
        # Calcular médias consolidadas
        if todos_resultados:
            media_nota_geral = sum(r.grade for r in todos_resultados) / len(todos_resultados)
            media_proficiencia_geral = sum(r.proficiency for r in todos_resultados) / len(todos_resultados)
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
            if 'abaixo' in classificacao or 'básico' in classificacao:
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
            escola_obj = School.query.get(scope_info.get('escola'))
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
            "media_nota_geral": round(media_nota_geral, 2),
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


def _gerar_opcoes_proximos_filtros(scope_info, nivel_granularidade):
    """
    Gera as opções dos próximos filtros baseado no nível de granularidade atual
    Nova hierarquia: Estado → Município → Avaliação → Escola → Série → Turma
    """
    try:
        opcoes = {
            "avaliacoes": [],
            "escolas": [],
            "series": [],
            "turmas": []
        }
        
        # Se estamos no nível de município, mostrar avaliações
        if nivel_granularidade in ["estado", "municipio"]:
            # Buscar avaliações do município
            municipio_id = scope_info.get('municipio_id')
            if municipio_id:
                query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                            .join(ClassTest, Test.id == ClassTest.test_id)\
                                            .join(Class, ClassTest.class_id == Class.id)\
                                            .join(School, Class.school_id == School.id)\
                                            .join(City, School.city_id == City.id)\
                                            .filter(City.id == municipio_id)\
                                            .distinct()
                
                avaliacoes = query_avaliacoes.all()
                opcoes["avaliacoes"] = [{"id": str(a[0]), "titulo": a[1]} for a in avaliacoes]
        
        # Se estamos no nível de avaliação, mostrar escolas onde ela foi aplicada
        if nivel_granularidade in ["estado", "municipio", "avaliacao"]:
            avaliacao_id = scope_info.get('avaliacao')
            municipio_id = scope_info.get('municipio_id')
            if avaliacao_id and municipio_id:
                query_escolas = School.query.with_entities(School.id, School.name)\
                                           .join(Class, School.id == Class.school_id)\
                                           .join(ClassTest, Class.id == ClassTest.class_id)\
                                           .join(Test, ClassTest.test_id == Test.id)\
                                           .join(City, School.city_id == City.id)\
                                           .filter(Test.id == avaliacao_id)\
                                           .filter(City.id == municipio_id)\
                                           .distinct()
                
                escolas = query_escolas.all()
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
                                             .join(School, Class.school_id == School.id)\
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
                                             .join(School, Class.school_id == School.id)\
                                             .join(City, School.city_id == City.id)\
                                             .filter(Test.id == avaliacao_id)\
                                             .filter(City.id == municipio_id)\
                                             .distinct()
                
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
                                             .join(School, Class.school_id == School.id)\
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
                                             .join(School, Class.school_id == School.id)\
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
                                             .join(School, Class.school_id == School.id)\
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
                                             .join(School, Class.school_id == School.id)\
                                             .join(City, School.city_id == City.id)\
                                             .filter(Test.id == avaliacao_id)\
                                             .filter(City.id == municipio_id)\
                                             .distinct()
                
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
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
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
        
        # Verificar se avaliação existe
        test = Test.query.get(avaliacao_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Buscar TODOS os alunos das turmas onde a avaliação foi aplicada
        # Primeiro, buscar as turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=avaliacao_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return jsonify({
                "data": [],
                "message": "Avaliação não foi aplicada em nenhuma turma"
            }), 200
        
        # Buscar todos os alunos dessas turmas com relacionamentos carregados
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade)
        ).filter(Student.class_id.in_(class_ids)).all()
        
        # ✅ NOVO: Buscar resultados pré-calculados da tabela evaluation_results
        from app.models.evaluationResult import EvaluationResult
        
        evaluation_results = EvaluationResult.query.filter_by(test_id=avaliacao_id).all()
        results_dict = {er.student_id: er for er in evaluation_results}
        
        total_questions = len(test.questions) if test.questions else 0
        
        results = []
        for student in all_students:
            # Verificar se o aluno tem resultado calculado
            evaluation_result = results_dict.get(student.id)
            
            if evaluation_result:
                # Aluno respondeu - usar resultados pré-calculados
                total_answered = evaluation_result.correct_answers  # Simplificado
                correct_answers = evaluation_result.correct_answers
                
                # CORREÇÃO: Usar valores originais da proficiência
                proficiency_original = evaluation_result.proficiency
                classification_original = evaluation_result.classification
                
                status = "concluida"
            else:
                # Aluno NÃO respondeu - retornar zeros
                total_answered = 0
                correct_answers = 0
                proficiency_original = 0.0
                classification_original = 'Abaixo do Básico'
                status = "pendente"
            
            # Buscar informações da turma e grade
            turma_nome = "N/A"
            grade_nome = "N/A"
            if student.class_:
                turma_nome = student.class_.name
                if student.class_.grade:
                    grade_nome = student.class_.grade.name
            
            student_result = {
                "id": student.id,
                "nome": student.name,
                "turma": turma_nome,
                "grade": grade_nome,
                "nota": evaluation_result.grade if evaluation_result else 0.0,
                "proficiencia": format_decimal_two_places(proficiency_original),
                "classificacao": classification_original,
                "questoes_respondidas": total_answered,
                "acertos": correct_answers,
                "erros": total_answered - correct_answers,
                "em_branco": total_questions - total_answered,
                "tempo_gasto": 3600,  # Placeholder - pode ser implementado
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

        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
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
                    school = School.query.get(school_id)
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
            "data_aplicacao": test.created_at.isoformat() if test.created_at else None,
            "data_correcao": test.updated_at.isoformat() if test.updated_at else None,
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
    Retorna relatório detalhado de uma avaliação
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Dados da avaliação
        avaliacao_data = {
            "id": test.id,
            "titulo": test.title,
            "disciplina": test.subject_rel.name if test.subject_rel else 'N/A',
            "total_questoes": len(test.questions) if test.questions else 0
        }
        
        # Dados das questões
        questoes_data = []
        if test.questions:
            for i, question in enumerate(test.questions, 1):
                # Calcular porcentagem de acertos
                total_respostas = StudentAnswer.query.filter_by(
                    test_id=evaluation_id, 
                    question_id=question.id
                ).count()
                
                # Calcular acertos corretamente baseado no tipo de questão
                acertos = 0
                if question.question_type == 'multiple_choice':
                    # Para questões de múltipla escolha, verificar correct_answer
                    for answer in StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        question_id=question.id
                    ).all():
                        if EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer):
                            acertos += 1
                else:
                    # Para outros tipos, usar correct_answer
                    acertos = StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        question_id=question.id,
                        answer=question.correct_answer
                    ).count() if total_respostas > 0 else 0
                
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
        
        # Dados dos alunos (buscar diretamente)
        from app.models.evaluationResult import EvaluationResult
        
        # Buscar TODOS os alunos das turmas onde a avaliação foi aplicada
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return jsonify({
                "avaliacao": avaliacao_data,
                "questoes": questoes_data,
                "alunos": []
            }), 200
        
        # Buscar todos os alunos dessas turmas
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade)
        ).filter(Student.class_id.in_(class_ids)).all()
        
        # Buscar resultados pré-calculados
        evaluation_results = EvaluationResult.query.filter_by(test_id=evaluation_id).all()
        results_dict = {er.student_id: er for er in evaluation_results}
        
        alunos_data = []
        for student in all_students:
            # Verificar se o aluno tem resultado calculado
            evaluation_result = results_dict.get(student.id)
            
            if evaluation_result:
                # Aluno respondeu - usar resultados pré-calculados
                total_answered = evaluation_result.correct_answers  # Simplificado
                correct_answers = evaluation_result.correct_answers
                
                # CORREÇÃO: Usar valores originais da proficiência
                proficiency_original = evaluation_result.proficiency
                classification_original = evaluation_result.classification
                
                status = "concluida"
            else:
                # Aluno NÃO respondeu - retornar zeros
                total_answered = 0
                correct_answers = 0
                proficiency_original = 0.0
                classification_original = 'Abaixo do Básico'
                status = "nao_respondida"
            
            # Buscar informações da turma
            turma_nome = "N/A"
            if student.class_:
                turma_nome = student.class_.name
            
            # Buscar respostas detalhadas do aluno
            respostas = []
            student_answers = StudentAnswer.query.filter_by(
                test_id=evaluation_id,
                student_id=student.id
            ).all()
            
            for answer in student_answers:
                question = Question.query.get(answer.question_id)
                if question:
                    # Verificar se a resposta está correta
                    is_correct = False
                    if question.question_type == 'multiple_choice':
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer)
                    else:
                        is_correct = str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower()
                    
                    resposta_data = {
                        "questao_id": question.id,
                        "questao_numero": question.number or 1,
                        "resposta_correta": is_correct,
                        "resposta_em_branco": not answer.answer,
                        "tempo_gasto": 120  # Placeholder
                    }
                    respostas.append(resposta_data)
            
            aluno_detalhado = {
                "id": student.id,
                "nome": student.name,
                "turma": turma_nome,
                "respostas": respostas,
                "total_acertos": correct_answers,
                "total_erros": total_answered - correct_answers,
                "total_em_branco": len(test.questions) - total_answered if test.questions else 0,
                "nota_final": evaluation_result.grade if evaluation_result else 0.0,
                "proficiencia": format_decimal_two_places(proficiency_original),
                "classificacao": classification_original,
                "status": status
            }
            alunos_data.append(aluno_detalhado)
        
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
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Você só pode finalizar avaliações que criou"}), 403
        
        # Buscar ClassTest para esta avaliação
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
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
            session.score = round((total_score / total_possible) * 100, 1)

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
            session.score = round((total_score / total_possible) * 100, 1)

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
        if user['role'] == 'professor' and test.created_by != user['id']:
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
            
        if user['role'] == 'professor' and test.created_by != user['id']:
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
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
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

        # Verificar permissões
        if user['role'] == 'aluno':
            # Aluno só pode ver seus próprios resultados
            # O student_id enviado é o user_id, não o id da tabela Student
            if user['id'] != student_id:
                return jsonify({"error": "Você só pode ver seus próprios resultados"}), 403
        elif user['role'] == 'professor':
            # Professor só pode ver resultados de testes que criou
            test = Test.query.get(test_id)
            if not test or test.created_by != user['id']:
                return jsonify({"error": "Você só pode ver resultados de testes que criou"}), 403
        
        # ✅ NOVO: Buscar resultado pré-calculado da tabela evaluation_results
        from app.models.evaluationResult import EvaluationResult
        
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
        
        # Buscar resultado pré-calculado
        evaluation_result = EvaluationResult.query.filter_by(
            test_id=test_id,
            student_id=actual_student_id
        ).first()
        
        if not evaluation_result:
            return jsonify({
                "error": "Aluno não respondeu esta avaliação",
                "message": "O aluno não possui resultados calculados para esta avaliação",
                "test_id": test_id,
                "student_id": student_id,
                "student_db_id": student.id,
                "total_questions": len(test.questions) if test.questions else 0,
                "answered_questions": 0,
                "correct_answers": 0,
                "score_percentage": 0.0,
                "total_score": 0.0,
                "max_possible_score": 0.0,
                "status": "nao_respondida"
            }), 200
        
        # ✅ NOVO: Usar dados pré-calculados da tabela evaluation_results
        test = Test.query.get(test_id)
        # Buscar questões do teste através da tabela de associação
        from app.models.testQuestion import TestQuestion
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
        questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        
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
        
        result = {
            "test_id": test_id,
            "student_id": student_id,  # user_id
            "student_db_id": student.id,  # id real da tabela Student
            "total_questions": total_questions,
            "answered_questions": correct_answers,  # Simplificado - usar acertos como questões respondidas
            "correct_answers": correct_answers,
            "score_percentage": round(score_percentage, 2),
            "total_score": round(grade, 2),  # Usar nota como total_score
            "max_possible_score": total_questions,  # Simplificado
            "grade": round(grade, 2),
            "proficiencia": format_decimal_two_places(proficiency_original),
            "classificacao": classification,
            "calculated_at": evaluation_result.calculated_at.isoformat() if evaluation_result.calculated_at else None,
            "answers": detailed_answers if request.args.get('include_answers', 'false').lower() == 'true' else []
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
            
        if user['role'] == 'professor' and test.created_by != user['id']:
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
            
        if user['role'] == 'professor' and test.created_by != user['id']:
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
@role_required("admin", "professor", "coordenador", "diretor", "aluno")
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
            if not test or test.created_by != user['id']:
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
            "score_percentage": round((correct_count / total_questions * 100), 2) if total_questions > 0 else 0,
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
@role_required("admin", "professor", "coordenador", "diretor")
def relatorio_detalhado_filtrado(evaluation_id: str):
    """
    Retorna relatório detalhado de uma avaliação com filtros e ordenação
    
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

        # Verificar se avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
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
            "total_questoes": len(test.questions) if test.questions else 0
        }
        
        # Dados das questões (filtrado por disciplina se especificado)
        questoes_data = []
        if test.questions and ('questoes' in fields or not fields):
            for i, question in enumerate(test.questions, 1):
                # Filtrar por disciplina se especificado
                if subject_id and question.subject_id != subject_id:
                    continue
                
                # Calcular porcentagem de acertos
                total_respostas = StudentAnswer.query.filter_by(
                    test_id=evaluation_id, 
                    question_id=question.id
                ).count()
                
                # Calcular acertos
                acertos = 0
                if question.question_type == 'multiple_choice':
                    for answer in StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        question_id=question.id
                    ).all():
                        if EvaluationResultService.check_multiple_choice_answer(answer.answer, question.correct_answer):
                            acertos += 1
                else:
                    acertos = StudentAnswer.query.filter_by(
                        test_id=evaluation_id,
                        question_id=question.id,
                        answer=question.correct_answer
                    ).count() if total_respostas > 0 else 0
                
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
        
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return jsonify({
                "avaliacao": avaliacao_data,
                "questoes": questoes_data,
                "alunos": []
            }), 200
        
        # Buscar todos os alunos dessas turmas
        all_students = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade)
        ).filter(Student.class_id.in_(class_ids)).all()
        
        # Filtrar por nível se especificado
        if student_level:
            all_students = [
                student for student in all_students 
                if student.class_ and student.class_.grade and 
                student.class_.grade.name and student_level.lower() in student.class_.grade.name.lower()
            ]
        
        # Buscar resultados pré-calculados
        evaluation_results = EvaluationResult.query.filter_by(test_id=evaluation_id).all()
        results_dict = {er.student_id: er for er in evaluation_results}
        
        alunos_data = []
        for student in all_students:
            evaluation_result = results_dict.get(student.id)
            
            if evaluation_result:
                # Aluno respondeu
                total_answered = evaluation_result.correct_answers
                correct_answers = evaluation_result.correct_answers
                proficiency_original = evaluation_result.proficiency
                classification_original = evaluation_result.classification
                status = "concluida"
                nota = evaluation_result.grade if hasattr(evaluation_result, 'grade') else 0.0
            else:
                # Aluno NÃO respondeu
                total_answered = 0
                correct_answers = 0
                proficiency_original = 0.0
                classification_original = 'Abaixo do Básico'
                status = "nao_respondida"
                nota = 0.0
            
            # Buscar informações da turma
            turma_nome = "N/A"
            if student.class_:
                turma_nome = student.class_.name
            
            # Buscar respostas detalhadas do aluno
            respostas = []
            if 'questoes' in fields or not fields:
                student_answers = StudentAnswer.query.filter_by(
                    test_id=evaluation_id,
                    student_id=student.id
                ).all()
                
                for answer in student_answers:
                    question = Question.query.get(answer.question_id)
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
                "total_em_branco": len(test.questions) - total_answered if test.questions else 0,
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
        if user['role'] == 'professor' and test.created_by != user['id']:
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
        class_tests = ClassTest.query.filter_by(test_id=evaluation_id).all()
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
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
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
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
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
        if user['role'] == 'professor' and test.created_by != user['id']:
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
        if user['role'] == 'professor' and test.created_by != user['id']:
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
            # Professores só veem suas próprias avaliações
            tests = Test.query.filter_by(created_by=user['id']).all()
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
            tests = Test.query.filter_by(created_by=user['id']).all()
        else:
            tests = Test.query.all()
        
        # Contar por status
        status_counts = {}
        total_tests = len(tests)
        
        for test in tests:
            class_tests = ClassTest.query.filter_by(test_id=test.id).all()
            if class_tests:
                # Usar o status da primeira aplicação como representativo
                status = class_tests[0].status
                status_counts[status] = status_counts.get(status, 0) + 1
            else:
                status_counts['sem_aplicacao'] = status_counts.get('sem_aplicacao', 0) + 1
        
        # Calcular porcentagens
        status_percentages = {}
        for status, count in status_counts.items():
            status_percentages[status] = round((count / total_tests) * 100, 2) if total_tests > 0 else 0
        
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
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Verificação de permissões falhou"}), 403
        
        # Obter estatísticas por disciplina
        statistics = EvaluationResultService.get_subject_detailed_statistics(test_id)
        
        if "error" in statistics:
            return jsonify(statistics), 400
        
        return jsonify(statistics), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter estatísticas por disciplina para avaliação {test_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter estatísticas por disciplina", "details": str(e)}), 500

# ==================== ENDPOINTS PARA OPÇÕES DE FILTROS ====================

@bp.route('/opcoes-filtros', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_opcoes_filtros():
    """
    Retorna as opções disponíveis para os filtros de avaliações
    Nova hierarquia: Estado → Município → Avaliação → Escola → Série → Turma
    
    Query Parameters:
    - estado (obrigatório): Estado selecionado
    - municipio (opcional): Município selecionado
    - avaliacao (opcional): Avaliação selecionada
    - escola (opcional): Escola selecionada
    - serie (opcional): Série selecionada
    - turma (opcional): Turma selecionada
    """
    try:
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
        avaliacao = request.args.get('avaliacao')
        escola = request.args.get('escola')
        serie = request.args.get('serie')
        turma = request.args.get('turma')
        
        if not estado:
            return jsonify({"error": "Parâmetro 'estado' é obrigatório"}), 400
        
        # Buscar opções disponíveis
        opcoes = {
            "estados": [],
            "municipios": [],
            "avaliacoes": [],
            "escolas": [],
            "series": [],
            "turmas": []
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
        
        # 3. Avaliações do município selecionado
        if estado and municipio:
            city = City.query.get(municipio)
            if city:
                # Verificar se o usuário tem acesso ao município
                if permissao['scope'] != 'all' and user.get('city_id') != city.id:
                    return jsonify({"error": "Acesso negado a este município"}), 403
                
                # Para educadores (professor, diretor, coordenador), retornar avaliações que criaram primeiro
                if permissao['scope'] in ['escola', 'escolas_vinculadas']:
                    # Para educadores, mostrar avaliações que criaram no município
                    query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                        .filter(Test.created_by == user['id'])
                    
                    # Aplicar joins
                    query_avaliacoes = query_avaliacoes.join(ClassTest, Test.id == ClassTest.test_id)
                    query_avaliacoes = query_avaliacoes.join(Class, ClassTest.class_id == Class.id)
                    query_avaliacoes = query_avaliacoes.join(School, Class.school_id == School.id)
                    query_avaliacoes = query_avaliacoes.join(City, School.city_id == City.id)
                    query_avaliacoes = query_avaliacoes.filter(City.id == city.id)
                    
                    # Aplicar filtros adicionais baseados no papel do usuário
                    if permissao['scope'] == 'escola':
                        query_avaliacoes = query_avaliacoes.filter(School.id == user.get('school_id', ''))
                    elif permissao['scope'] == 'escolas_vinculadas':
                        # Professor vê avaliações que criou (filtro já aplicado por created_by)
                        pass
                else:
                    # Para admin e tecadm, aplicar filtro por município
                    query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                        .join(ClassTest, Test.id == ClassTest.test_id)\
                                        .join(Class, ClassTest.class_id == Class.id)\
                                        .join(School, Class.school_id == School.id)\
                                        .join(City, School.city_id == City.id)\
                                        .filter(City.id == city.id)
                
                # Executar a query e obter resultados
                avaliacoes = query_avaliacoes.distinct().all()
                avaliacoes_list = [{"id": str(a[0]), "titulo": a[1]} for a in avaliacoes]
                opcoes["avaliacoes"] = avaliacoes_list
            else:
                opcoes["avaliacoes"] = []
        else:
            opcoes["avaliacoes"] = []
        
        # 4. Escolas do município (quando avaliação for selecionada)
        if estado and municipio and avaliacao:
            city = City.query.get(municipio)
            if city:
                # Verificar se o usuário tem acesso ao município
                if permissao['scope'] != 'all' and user.get('city_id') != city.id:
                    return jsonify({"error": "Acesso negado a este município"}), 403
                
                # Buscar escolas onde a avaliação foi aplicada no município
                query_escolas = School.query.with_entities(School.id, School.name)\
                                           .join(Class, School.id == Class.school_id)\
                                           .join(ClassTest, Class.id == ClassTest.class_id)\
                                           .join(Test, ClassTest.test_id == Test.id)\
                                           .join(City, School.city_id == City.id)\
                                           .filter(Test.id == avaliacao)\
                                           .filter(City.id == city.id)
                
                # Aplicar filtros baseados no papel do usuário
                if permissao['scope'] == 'escola':
                    # Diretor e Coordenador veem apenas sua escola
                    query_escolas = query_escolas.filter(School.id == user.get('school_id', ''))
                elif permissao['scope'] == 'escolas_vinculadas':
                    # Professor vê todas as escolas onde a avaliação foi aplicada (filtro será por created_by)
                    pass
                
                escolas = query_escolas.distinct().all()
                escolas_list = [{"id": str(e[0]), "nome": e[1]} for e in escolas]
                opcoes["escolas"] = escolas_list
            else:
                opcoes["escolas"] = []
        else:
            opcoes["escolas"] = []
        
        # 5. Séries da escola (quando escola for selecionada)
        if estado and municipio and avaliacao and escola:
            city = City.query.get(municipio)
            if city:
                # Verificar se o usuário tem acesso ao município
                if permissao['scope'] != 'all' and user.get('city_id') != city.id:
                    return jsonify({"error": "Acesso negado a este município"}), 403
                
                # Buscar séries onde a avaliação foi aplicada na escola específica
                query_series = Grade.query.with_entities(Grade.id, Grade.name)\
                                         .join(Class, Grade.id == Class.grade_id)\
                                         .join(ClassTest, Class.id == ClassTest.class_id)\
                                         .join(Test, ClassTest.test_id == Test.id)\
                                         .join(School, Class.school_id == School.id)\
                                         .join(City, School.city_id == City.id)\
                                         .filter(Test.id == avaliacao)\
                                         .filter(School.id == escola)\
                                         .filter(City.id == city.id)
                
                series = query_series.distinct().all()
                series_list = [{"id": str(s[0]), "nome": s[1]} for s in series]
                opcoes["series"] = series_list
            else:
                opcoes["series"] = []
        else:
            opcoes["series"] = []
        
        # 6. Turmas da série (quando série for selecionada)
        if estado and municipio and avaliacao and escola and serie:
            city = City.query.get(municipio)
            if city:
                # Verificar se o usuário tem acesso ao município
                if permissao['scope'] != 'all' and user.get('city_id') != city.id:
                    return jsonify({"error": "Acesso negado a este município"}), 403
                
                # Buscar turmas onde a avaliação foi aplicada na escola e série específicas
                query_turmas = Class.query.with_entities(Class.id, Class.name)\
                                         .join(ClassTest, Class.id == ClassTest.class_id)\
                                         .join(Test, ClassTest.test_id == Test.id)\
                                         .join(School, Class.school_id == School.id)\
                                         .join(City, School.city_id == City.id)\
                                         .join(Grade, Class.grade_id == Grade.id)\
                                         .filter(Test.id == avaliacao)\
                                         .filter(School.id == escola)\
                                         .filter(Grade.id == serie)\
                                         .filter(City.id == city.id)
                
                turmas = query_turmas.distinct().all()
                turmas_list = [{"id": str(t[0]), "nome": t[1] or f"Turma {t[0]}"} for t in turmas]
                opcoes["turmas"] = turmas_list
            else:
                opcoes["turmas"] = []
        else:
            opcoes["turmas"] = []
        
        return jsonify({
            "opcoes": opcoes,
            "filtros_aplicados": {
                "estado": estado,
                "municipio": municipio,
                "avaliacao": avaliacao,
                "escola": escola,
                "serie": serie,
                "turma": turma
            },
            "hierarquia": "Estado → Município → Avaliação → Escola → Série → Turma"
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter opções de filtros: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter opções de filtros", "details": str(e)}), 500


@bp.route('/opcoes-filtros/estados', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_estados():
    """
    Retorna todos os estados disponíveis baseado nas permissões do usuário
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        permissao = verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao['error']}), 403

        if permissao['scope'] == 'all':
            # Admin vê todos os estados
            estados = db.session.query(City.state).distinct().filter(City.state.isnot(None)).all()
        else:
            # Outros usuários veem apenas estados das suas cidades
            estados = db.session.query(City.state).distinct().filter(
                City.state.isnot(None),
                City.id == user.get('city_id')
            ).all()
        
        estados_list = [{"id": estado[0], "nome": estado[0]} for estado in estados]
        
        return jsonify({
            "estados": estados_list,
            "total": len(estados_list)
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter estados: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter estados", "details": str(e)}), 500


@bp.route('/opcoes-filtros/municipios/<string:estado>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_municipios_estado(estado: str):
    """
    Retorna municípios de um estado específico baseado nas permissões do usuário
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        permissao = verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao['error']}), 403

        if permissao['scope'] == 'all':
            # Admin vê todos os municípios do estado
            municipios = City.query.filter(City.state.ilike(f"%{estado}%")).all()
        else:
            # Outros usuários veem apenas o seu município
            municipios = City.query.filter(
                City.state.ilike(f"%{estado}%"),
                City.id == user.get('city_id')
            ).all()
        
        municipios_list = [{"id": str(m.id), "nome": m.name} for m in municipios]
        
        return jsonify({
            "municipios": municipios_list,
            "estado": estado,
            "total": len(municipios_list)
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter municípios do estado {estado}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter municípios", "details": str(e)}), 500


@bp.route('/opcoes-filtros/escolas/<string:municipio_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_escolas_municipio(municipio_id: str):
    """
    Retorna escolas de um município específico baseado nas permissões do usuário
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar permissões
        permissao = verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao['error']}), 403

        # Verificar se o usuário tem acesso ao município
        if permissao['scope'] != 'all' and user.get('city_id') != municipio_id:
            return jsonify({"error": "Acesso negado a este município"}), 403

        if permissao['scope'] == 'all':
            # Admin vê todas as escolas do município
            escolas = School.query.filter_by(city_id=municipio_id).all()
        elif permissao['scope'] == 'municipio':
            # Tecadm vê todas as escolas do município
            escolas = School.query.filter_by(city_id=municipio_id).all()
        elif permissao['scope'] == 'escola':
            # Diretor e Coordenador veem apenas sua escola
            escolas = School.query.filter(
                School.city_id == municipio_id,
                School.id == user.get('school_id', '')
            ).all()
        elif permissao['scope'] == 'escolas_vinculadas':
            # Professor vê todas as escolas do município (filtro será por created_by na avaliação)
            escolas = School.query.filter_by(city_id=municipio_id).all()
        else:
            escolas = []

        escolas_list = [{"id": str(e.id), "nome": e.name} for e in escolas]
        
        return jsonify({
            "escolas": escolas_list,
            "municipio_id": municipio_id,
            "total": len(escolas_list)
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter escolas do município {municipio_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter escolas", "details": str(e)}), 500


@bp.route('/opcoes-filtros/escolas-por-avaliacao', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_escolas_por_avaliacao():
    """
    Retorna escolas onde uma avaliação específica foi aplicada
    Nova hierarquia: Estado → Município → Avaliação → Escolas
    """
    try:
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
        avaliacao = request.args.get('avaliacao')
        
        if not estado:
            return jsonify({"error": "Parâmetro 'estado' é obrigatório"}), 400
        
        if not municipio:
            return jsonify({"error": "Parâmetro 'municipio' é obrigatório"}), 400
        
        if not avaliacao:
            return jsonify({"error": "Parâmetro 'avaliacao' é obrigatório"}), 400
        
        # Buscar município
        city = City.query.get(municipio)
        if not city:
            city = City.query.filter(City.name.ilike(f"%{municipio}%")).first()
        
        if not city:
            return jsonify({"error": "Município não encontrado"}), 404
        
        # Verificar se o usuário tem acesso ao município
        if permissao['scope'] != 'all' and user.get('city_id') != city.id:
            return jsonify({"error": "Acesso negado a este município"}), 403
        
        # Buscar avaliação
        test = Test.query.get(avaliacao)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões específicas para professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Buscar escolas onde a avaliação foi aplicada no município
        query_escolas = School.query.with_entities(School.id, School.name)\
                                   .join(Class, School.id == Class.school_id)\
                                   .join(ClassTest, Class.id == ClassTest.class_id)\
                                   .join(Test, ClassTest.test_id == Test.id)\
                                   .join(City, School.city_id == City.id)\
                                   .filter(Test.id == avaliacao)\
                                   .filter(City.id == city.id)
        
        # Aplicar filtros baseados no papel do usuário
        if permissao['scope'] == 'escola':
            # Diretor e Coordenador veem apenas sua escola
            query_escolas = query_escolas.filter(School.id == user.get('school_id', ''))
        elif permissao['scope'] == 'escolas_vinculadas':
            # Professor vê todas as escolas onde a avaliação foi aplicada (filtro será por created_by)
            pass
        
        escolas = query_escolas.distinct().all()
        escolas_list = [{"id": str(e[0]), "nome": e[1]} for e in escolas]
        
        return jsonify({
            "escolas": escolas_list,
            "total": len(escolas_list),
            "avaliacao": {
                "id": test.id,
                "titulo": test.title
            },
            "municipio": city.name,
            "estado": estado
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter escolas por avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter escolas por avaliação", "details": str(e)}), 500


@bp.route('/opcoes-filtros/series', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_series():
    """
    Retorna séries disponíveis baseado na avaliação e escola escolhidas
    Nova hierarquia: Estado → Município → Avaliação → Escola → Séries
    """
    try:
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
        avaliacao = request.args.get('avaliacao')
        escola = request.args.get('escola')
        
        if not estado:
            return jsonify({"error": "Parâmetro 'estado' é obrigatório"}), 400
        
        if not municipio:
            return jsonify({"error": "Parâmetro 'municipio' é obrigatório"}), 400
        
        if not avaliacao:
            return jsonify({"error": "Parâmetro 'avaliacao' é obrigatório"}), 400
        
        if not escola:
            return jsonify({"error": "Parâmetro 'escola' é obrigatório"}), 400
        
        # Buscar município
        city = City.query.get(municipio)
        if not city:
            city = City.query.filter(City.name.ilike(f"%{municipio}%")).first()
        
        if not city:
            return jsonify({"error": "Município não encontrado"}), 404
        
        # Verificar se o usuário tem acesso ao município
        if permissao['scope'] != 'all' and user.get('city_id') != city.id:
            return jsonify({"error": "Acesso negado a este município"}), 403
        
        # Buscar avaliação
        test = Test.query.get(avaliacao)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões específicas para professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Buscar escola
        school = School.query.get(escola)
        if not school:
            return jsonify({"error": "Escola não encontrada"}), 404
        
        # Verificar se o usuário tem acesso à escola
        if permissao['scope'] == 'escola' and school.id != user.get('school_id', ''):
            return jsonify({"error": "Acesso negado a esta escola"}), 403
        elif permissao['scope'] == 'escolas_vinculadas':
            # Professor pode acessar qualquer escola onde suas avaliações foram aplicadas
            pass
        
        # Buscar séries onde a avaliação foi aplicada na escola específica
        query_series = Grade.query.with_entities(Grade.id, Grade.name)\
                                 .join(Class, Grade.id == Class.grade_id)\
                                 .join(ClassTest, Class.id == ClassTest.class_id)\
                                 .join(Test, ClassTest.test_id == Test.id)\
                                 .join(School, Class.school_id == School.id)\
                                 .join(City, School.city_id == City.id)\
                                 .filter(Test.id == avaliacao)\
                                 .filter(School.id == escola)\
                                 .filter(City.id == city.id)
        
        series = query_series.distinct().all()
        series_list = [{"id": str(s[0]), "nome": s[1]} for s in series]
        
        return jsonify({
            "series": series_list,
            "total": len(series_list),
            "escola": {
                "id": school.id,
                "nome": school.name
            },
            "avaliacao": {
                "id": test.id,
                "titulo": test.title
            },
            "municipio": city.name,
            "estado": estado
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter séries: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter séries", "details": str(e)}), 500


@bp.route('/opcoes-filtros/turmas', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_turmas():
    """
    Retorna turmas disponíveis baseado na avaliação, escola e série escolhidas
    Nova hierarquia: Estado → Município → Avaliação → Escola → Série → Turmas
    """
    try:
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
        avaliacao = request.args.get('avaliacao')
        escola = request.args.get('escola')
        serie = request.args.get('serie')
        
        if not estado:
            return jsonify({"error": "Parâmetro 'estado' é obrigatório"}), 400
        
        if not municipio:
            return jsonify({"error": "Parâmetro 'municipio' é obrigatório"}), 400
        
        if not avaliacao:
            return jsonify({"error": "Parâmetro 'avaliacao' é obrigatório"}), 400
        
        if not escola:
            return jsonify({"error": "Parâmetro 'escola' é obrigatório"}), 400
        
        if not serie:
            return jsonify({"error": "Parâmetro 'serie' é obrigatório"}), 400
        
        # Buscar município
        city = City.query.get(municipio)
        if not city:
            city = City.query.filter(City.name.ilike(f"%{municipio}%")).first()
        
        if not city:
            return jsonify({"error": "Município não encontrado"}), 404
        
        # Verificar se o usuário tem acesso ao município
        if permissao['scope'] != 'all' and user.get('city_id') != city.id:
            return jsonify({"error": "Acesso negado a este município"}), 403
        
        # Buscar avaliação
        test = Test.query.get(avaliacao)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões específicas para professor
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403
        
        # Buscar escola
        school = School.query.get(escola)
        if not school:
            return jsonify({"error": "Escola não encontrada"}), 404
        
        # Verificar se o usuário tem acesso à escola
        if permissao['scope'] == 'escola' and school.id != user.get('school_id', ''):
            return jsonify({"error": "Acesso negado a esta escola"}), 403
        elif permissao['scope'] == 'escolas_vinculadas':
            # Professor pode acessar qualquer escola onde suas avaliações foram aplicadas
            pass
        
        # Buscar série
        grade = Grade.query.get(serie)
        if not grade:
            return jsonify({"error": "Série não encontrada"}), 404
        
        # Buscar turmas onde a avaliação foi aplicada na escola e série específicas
        query_turmas = Class.query.with_entities(Class.id, Class.name)\
                                 .join(ClassTest, Class.id == ClassTest.class_id)\
                                 .join(Test, ClassTest.test_id == Test.id)\
                                 .join(School, Class.school_id == School.id)\
                                 .join(City, School.city_id == City.id)\
                                 .join(Grade, Class.grade_id == Grade.id)\
                                 .filter(Test.id == avaliacao)\
                                 .filter(School.id == escola)\
                                 .filter(Grade.id == serie)\
                                 .filter(City.id == city.id)
        
        turmas = query_turmas.distinct().all()
        turmas_list = [{"id": str(t[0]), "nome": t[1] or f"Turma {t[0]}"} for t in turmas]
        
        return jsonify({
            "turmas": turmas_list,
            "total": len(turmas_list),
            "serie": {
                "id": grade.id,
                "nome": grade.name
            },
            "escola": {
                "id": school.id,
                "nome": school.name
            },
            "avaliacao": {
                "id": test.id,
                "titulo": test.title
            },
            "municipio": city.name,
            "estado": estado
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter turmas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter turmas", "details": str(e)}), 500


@bp.route('/opcoes-filtros/avaliacoes', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def obter_avaliacoes():
    """
    Retorna avaliações disponíveis baseado no estado e município escolhidos
    Nova hierarquia: Estado → Município → Avaliações
    """
    try:

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
        
        if not estado:
            return jsonify({"error": "Parâmetro 'estado' é obrigatório"}), 400
        
        if not municipio:
            return jsonify({"error": "Parâmetro 'municipio' é obrigatório"}), 400
        
        # Buscar município
        city = City.query.get(municipio)
        if not city:
            city = City.query.filter(City.name.ilike(f"%{municipio}%")).first()
        
        if not city:
            return jsonify({"error": "Município não encontrado"}), 404
        
        # Verificar se o usuário tem acesso ao município
        if permissao['scope'] != 'all' and user.get('city_id') != city.id:
            return jsonify({"error": "Acesso negado a este município"}), 403
        
        # Para educadores (professor, diretor, coordenador), retornar avaliações que criaram e que estão aplicadas
        if permissao['scope'] in ['escola', 'escolas_vinculadas']:
            if permissao['scope'] == 'escola':
                # Diretor e Coordenador veem apenas avaliações que criaram e que estão aplicadas na sua escola
                from app.models.manager import Manager
                
                # Buscar o manager vinculado ao usuário atual
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if not manager or not manager.school_id:
                    # Manager não encontrado ou não vinculado a escola, retornar lista vazia
                    query_avaliacoes = Test.query.with_entities(Test.id, Test.title).filter(Test.id == None)
                else:
                    # Buscar avaliações que o diretor/coordenador criou e que estão aplicadas na sua escola
                    query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                                .filter(Test.created_by == user['id'])\
                                                .join(ClassTest, Test.id == ClassTest.test_id)\
                                                .join(Class, ClassTest.class_id == Class.id)\
                                                .filter(Class.school_id == manager.school_id)
            elif permissao['scope'] == 'escolas_vinculadas':
                # Professor vê avaliações que criou (simplificado)
                query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                            .filter(Test.created_by == user['id'])
                
                # Aplicar joins para verificar se estão aplicadas
                query_avaliacoes = query_avaliacoes.join(ClassTest, Test.id == ClassTest.test_id)
                query_avaliacoes = query_avaliacoes.join(Class, ClassTest.class_id == Class.id)
                query_avaliacoes = query_avaliacoes.join(School, Class.school_id == School.id)
                query_avaliacoes = query_avaliacoes.join(City, School.city_id == City.id)
                query_avaliacoes = query_avaliacoes.filter(City.id == city.id)
        else:
            # Para admin e tecadm, manter lógica atual
            query_avaliacoes = Test.query.with_entities(Test.id, Test.title)\
                                        .join(ClassTest, Test.id == ClassTest.test_id)\
                                        .join(Class, ClassTest.class_id == Class.id)\
                                        .join(School, Class.school_id == School.id)\
                                        .join(City, School.city_id == City.id)\
                                        .filter(City.id == city.id)
        
        avaliacoes = query_avaliacoes.distinct().all()
        avaliacoes_list = [{"id": str(a[0]), "titulo": a[1]} for a in avaliacoes]
        
        return jsonify({
            "avaliacoes": avaliacoes_list,
            "total": len(avaliacoes_list),
            "municipio": city.name,
            "estado": estado
        }), 200

    except Exception as e:
        logging.error(f"Erro ao obter avaliações: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter avaliações", "details": str(e)}), 500

# ==================== FUNÇÕES AUXILIARES PARA CÁLCULO CONSOLIDADO ====================

def _calcular_estatisticas_consolidadas_por_escopo(class_tests: list, scope_info: dict, nivel_granularidade: str) -> Dict[str, Any]:
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
        
        # Buscar resultados das avaliações do escopo
        resultados_escopo = EvaluationResult.query.filter(EvaluationResult.test_id.in_(test_ids)).all()
        alunos_participantes = len(resultados_escopo)
        logging.info(f"resultados_escopo: {alunos_participantes}, test_ids: {test_ids}")
        
        # Calcular estatísticas consolidadas
        if resultados_escopo:
            media_nota = sum(r.grade for r in resultados_escopo) / len(resultados_escopo)
            media_proficiencia = sum(r.proficiency for r in resultados_escopo) / len(resultados_escopo)
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
            if 'abaixo' in classificacao or 'básico' in classificacao:
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
            escola_obj = School.query.get(scope_info.get('escola'))
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
    """
    escopo = {}
    
    if nivel_granularidade == "avaliacao":
        # Avaliação específica selecionada
        escopo['tipo'] = "avaliacao"
        escopo['avaliacao_id'] = scope_info.get('avaliacao')
        escopo['municipio_id'] = scope_info.get('municipio_id')
        # Buscar as turmas onde esta avaliação foi aplicada
        from app.models.classTest import ClassTest
        class_tests = ClassTest.query.filter_by(test_id=escopo['avaliacao_id']).all()
        escopo['class_ids'] = [ct.class_id for ct in class_tests]
        logging.info(f"Escopo avaliação: {escopo}")
        
    elif nivel_granularidade == "municipio":
        # Estado + Município + Avaliação "all"
        escopo['tipo'] = "municipio"
        escopo['municipio_id'] = scope_info.get('municipio_id')
        escopo['avaliacao_id'] = None  # "all" - todas as avaliações
        
    elif nivel_granularidade == "escola":
        # Estado + Município + Avaliação + Escola "all"
        escopo['tipo'] = "escola"
        escopo['escola_id'] = scope_info.get('escola')
        escopo['avaliacao_id'] = scope_info.get('avaliacao')
        
    elif nivel_granularidade == "serie":
        # Estado + Município + Avaliação + Escola + Série "all"
        escopo['tipo'] = "serie"
        escopo['serie_id'] = scope_info.get('serie')
        escopo['escola_id'] = scope_info.get('escola')
        escopo['avaliacao_id'] = scope_info.get('avaliacao')
        
    elif nivel_granularidade == "turma":
        # Estado + Município + Avaliação + Escola + Série + Turma "all"
        escopo['tipo'] = "turma"
        escopo['turma_id'] = scope_info.get('turma')
        escopo['serie_id'] = scope_info.get('serie')
        escopo['escola_id'] = scope_info.get('escola')
        escopo['avaliacao_id'] = scope_info.get('avaliacao')
    
    logging.info(f"Escopo calculado para {nivel_granularidade}: {escopo}")
    return escopo


def _buscar_alunos_por_escopo(escopo_calculo: dict) -> List[Student]:
    """
    Busca alunos baseado no escopo de cálculo
    """
    try:
        logging.info(f"Buscando alunos por escopo: {escopo_calculo}")
        
        if escopo_calculo['tipo'] == "avaliacao":
            # Todos os alunos das turmas onde a avaliação foi aplicada
            class_ids = escopo_calculo.get('class_ids', [])
            logging.info(f"Tipo avaliação, class_ids: {class_ids}")
            if class_ids:
                alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
                logging.info(f"Alunos encontrados para avaliação: {len(alunos)}")
                return alunos
            else:
                logging.warning("Nenhum class_id encontrado para avaliação")
                return []
        
        elif escopo_calculo['tipo'] == "municipio":
            # Todos os alunos do município
            alunos = Student.query.join(Class).join(School).join(City)\
                               .filter(City.id == escopo_calculo['municipio_id']).all()
            logging.info(f"Alunos encontrados para município: {len(alunos)}")
            return alunos
        
        elif escopo_calculo['tipo'] == "escola":
            # Todos os alunos da escola
            alunos = Student.query.join(Class).join(School)\
                               .filter(School.id == escopo_calculo['escola_id']).all()
            logging.info(f"Alunos encontrados para escola: {len(alunos)}")
            return alunos
        
        elif escopo_calculo['tipo'] == "serie":
            # Todos os alunos da série
            alunos = Student.query.join(Class).join(Grade)\
                               .filter(Grade.id == escopo_calculo['serie_id']).all()
            logging.info(f"Alunos encontrados para série: {len(alunos)}")
            return alunos
        
        elif escopo_calculo['tipo'] == "turma":
            # Todos os alunos da turma
            alunos = Student.query.filter(Student.class_id == escopo_calculo['turma_id']).all()
            logging.info(f"Alunos encontrados para turma: {len(alunos)}")
            return alunos
        
        else:
            # Fallback: retornar alunos das turmas das avaliações
            class_ids = escopo_calculo.get('class_ids', [])
            logging.info(f"Fallback, class_ids: {class_ids}")
            alunos = Student.query.filter(Student.class_id.in_(class_ids)).all()
            logging.info(f"Alunos encontrados no fallback: {len(alunos)}")
            return alunos
            
    except Exception as e:
        logging.error(f"Erro ao buscar alunos por escopo: {str(e)}")
        return []


# ==================== ENDPOINT 1: GET /avaliacoes ====================

def _calcular_ranking_global_alunos(avaliacao_id: str, scope_info: Dict, nivel_granularidade: str, user: Dict) -> List[Dict]:
    """
    Calcula o ranking global dos alunos baseado em nota e acertos totais
    para o nível de granularidade especificado
    
    Args:
        avaliacao_id: ID da avaliação
        scope_info: Informações do escopo de busca
        nivel_granularidade: Nível de granularidade atual
        user: Informações do usuário logado
    
    Returns:
        Lista de alunos ordenados por ranking com formato: "Aluno X, Acertos X, Nota X"
    """
    try:
        from app.models.evaluationResult import EvaluationResult
        
        # Determinar escopo de alunos baseado na granularidade
        class_tests = ClassTest.query.filter_by(test_id=avaliacao_id).all()
        class_ids = [ct.class_id for ct in class_tests]
        
        if not class_ids:
            return []
        
        # Buscar alunos baseado no escopo e filtros
        query_alunos = Student.query.options(
            joinedload(Student.class_).joinedload(Class.grade),
            joinedload(Student.class_).joinedload(Class.school).joinedload(School.city)
        ).filter(Student.class_id.in_(class_ids))
        
        # Aplicar filtros baseados na granularidade
        if nivel_granularidade in ['escola', 'serie', 'turma']:
            # Filtrar por escola se especificada
            if scope_info.get('escolas') and len(scope_info['escolas']) == 1:
                escola_id = scope_info['escolas'][0].id
                query_alunos = query_alunos.join(Class).filter(Class.school_id == escola_id)
            
            # Filtrar por série se especificada
            if nivel_granularidade in ['serie', 'turma'] and scope_info.get('serie_id') and scope_info['serie_id'] != 'all':
                query_alunos = query_alunos.join(Class).filter(Class.grade_id == scope_info['serie_id'])
            
            # Filtrar por turma se especificada
            if nivel_granularidade == 'turma' and scope_info.get('turma_id') and scope_info['turma_id'] != 'all':
                query_alunos = query_alunos.filter(Student.class_id == scope_info['turma_id'])
        
        all_students = query_alunos.all()
        
        if not all_students:
            return []
        
        # Buscar resultados pré-calculados
        evaluation_results = EvaluationResult.query.filter_by(test_id=avaliacao_id).all()
        results_dict = {er.student_id: er for er in evaluation_results}
        
        # Buscar todas as respostas dos alunos para esta avaliação
        all_student_answers = StudentAnswer.query.filter(
            StudentAnswer.test_id == avaliacao_id
        ).all()
        
        # Criar dicionário de respostas por aluno
        respostas_por_aluno = {}
        for resposta in all_student_answers:
            if resposta.student_id not in respostas_por_aluno:
                respostas_por_aluno[resposta.student_id] = {}
            respostas_por_aluno[resposta.student_id][resposta.question_id] = resposta
        
        # Calcular estatísticas para cada aluno
        alunos_ranking = []
        
        for student in all_students:
            # Buscar resultado pré-calculado
            evaluation_result = results_dict.get(student.id)
            
            # Calcular acertos totais
            total_acertos = 0
            total_respondidas = 0
            
            if student.id in respostas_por_aluno:
                for question_id, resposta in respostas_por_aluno[student.id].items():
                    # Buscar a questão para verificar se acertou
                    question = Question.query.get(question_id)
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
            
            aluno_ranking = {
                "id": student.id,
                "nome": student.name,
                "escola": student.class_.school.name if student.class_ and student.class_.school else "N/A",
                "serie": student.class_.grade.name if student.class_ and student.class_.grade else "N/A",
                "turma": student.class_.name if student.class_ else "N/A",
                "total_acertos": total_acertos,
                "total_respondidas": total_respondidas,
                "nota": nota,
                "proficiencia": format_decimal_two_places(evaluation_result.proficiency) if evaluation_result else 0.0,
                "nivel_proficiencia": evaluation_result.classification if evaluation_result else "Abaixo do Básico"
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
            descricao_ranking = f"{aluno['nome']}, Acertos {aluno['total_acertos']}, Nota {aluno['nota']:.1f}"
            
            ranking_final.append({
                "posicao": i + 1,
                "descricao": descricao_ranking,
                "aluno": aluno
            })
        
        return ranking_final
        
    except Exception as e:
        logging.error(f"Erro ao calcular ranking global dos alunos: {str(e)}", exc_info=True)
        return []