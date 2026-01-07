# -*- coding: utf-8 -*-
"""
Rotas para filtros hierárquicos de formulários socioeconômicos
Funciona sem necessidade de avaliação
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app import db
from app.models.city import City
from app.models.school import School
from app.models.grades import Grade
from app.models.studentClass import Class
from app.models.educationStage import EducationStage
from app.models.teacher import Teacher
from app.models.schoolTeacher import SchoolTeacher
from app.models.manager import Manager
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
import logging
from typing import List, Dict, Any

bp = Blueprint('form_filters', __name__, url_prefix='/forms')


def _verificar_permissao_filtros(user: dict) -> Dict[str, Any]:
    """
    Verifica permissões do usuário para acessar filtros baseado no seu papel
    
    Args:
        user: Dicionário com informações do usuário logado
        
    Returns:
        Dict com informações de permissão e filtros aplicáveis
    """
    from app.permissions.rules import get_user_permission_scope
    return get_user_permission_scope(user)


def _obter_estados_disponiveis(user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna estados disponíveis baseado nas permissões do usuário.
    
    Args:
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        
    Returns:
        Lista de estados no formato [{"id": "...", "nome": "..."}]
    """
    try:
        if permissao['scope'] == 'all':
            # Admin vê todos os estados
            estados = db.session.query(City.state).distinct().filter(City.state.isnot(None)).all()
        else:
            # Outros usuários veem apenas estados das suas cidades
            estados = db.session.query(City.state).distinct().filter(
                City.state.isnot(None),
                City.id == user.get('city_id')
            ).all()
        
        return [{"id": estado[0], "nome": estado[0], "name": estado[0]} for estado in estados]
    except Exception as e:
        logging.error(f"Erro ao obter estados: {str(e)}")
        return []


def _obter_municipios_por_estado(estado: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna municípios de um estado específico baseado nas permissões do usuário.
    
    Args:
        estado: Nome do estado
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        
    Returns:
        Lista de municípios no formato [{"id": "...", "nome": "...", "estado_id": "..."}]
    """
    try:
        if permissao['scope'] == 'all':
            # Admin vê todos os municípios do estado
            municipios = City.query.filter(City.state.ilike(f"%{estado}%")).all()
        else:
            # Outros usuários veem apenas seu município
            municipios = City.query.filter(
                City.state.ilike(f"%{estado}%"),
                City.id == user.get('city_id')
            ).all()
        
        return [{"id": str(m.id), "nome": m.name, "name": m.name, "estado_id": m.state} for m in municipios]
    except Exception as e:
        logging.error(f"Erro ao obter municípios: {str(e)}")
        return []


def _obter_escolas_por_municipio(municipio_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna escolas de um município específico, sem necessidade de avaliação.
    
    Args:
        municipio_id: ID do município
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        
    Returns:
        Lista de escolas no formato [{"id": "...", "nome": "...", "name": "..."}]
    """
    try:
        city = City.query.get(municipio_id)
        if not city:
            return []
        
        # Verificar se o usuário tem acesso ao município
        if permissao['scope'] != 'all' and user.get('city_id') != city.id:
            return []
        
        # Buscar escolas do município
        query_escolas = School.query.filter(School.city_id == municipio_id)
        
        # Aplicar filtros baseados no papel do usuário
        if permissao['scope'] == 'escola':
            if user.get('role') in ['diretor', 'coordenador']:
                # Diretor e Coordenador veem apenas sua escola
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if manager and manager.school_id:
                    query_escolas = query_escolas.filter(School.id == manager.school_id)
                else:
                    return []
            elif user.get('role') == 'professor':
                # Professor vê apenas escolas onde está vinculado
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                    school_ids = [ts.school_id for ts in teacher_schools]
                    if school_ids:
                        query_escolas = query_escolas.filter(School.id.in_(school_ids))
                    else:
                        return []
                else:
                    return []
        
        escolas = query_escolas.all()
        return [{
            "id": str(e.id),
            "nome": e.name,
            "name": e.name,
            "city_id": str(e.city_id) if e.city_id else None,
            "municipio_id": str(e.city_id) if e.city_id else None,
            "address": e.address,
            "domain": e.domain
        } for e in escolas]
    except Exception as e:
        logging.error(f"Erro ao obter escolas: {str(e)}")
        return []


def _obter_series_por_escola(escola_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna séries que têm turmas em uma escola específica, sem necessidade de avaliação.
    
    Args:
        escola_id: ID da escola
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        
    Returns:
        Lista de séries no formato [{"id": "...", "nome": "...", "education_stage_id": "..."}]
    """
    try:
        school = School.query.get(escola_id)
        if not school:
            return []
        
        # Verificar se o usuário tem acesso à escola
        if permissao['scope'] == 'escola':
            if user.get('role') in ['diretor', 'coordenador']:
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if not manager or manager.school_id != escola_id:
                    return []
            elif user.get('role') == 'professor':
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                    school_ids = [ts.school_id for ts in teacher_schools]
                    if escola_id not in school_ids:
                        return []
                else:
                    return []
        elif permissao['scope'] == 'municipio':
            if user.get('city_id') != school.city_id:
                return []
        
        # Buscar séries que têm turmas na escola
        query_series = Grade.query.with_entities(Grade.id, Grade.name, Grade.education_stage_id)\
                         .join(Class, Grade.id == Class.grade_id)\
                         .filter(Class.school_id == escola_id)\
                         .distinct()
        
        series = query_series.all()
        return [{
            "id": str(s[0]),
            "nome": s[1],
            "name": s[1],
            "education_stage_id": str(s[2]) if s[2] else None,
            "educationStageId": str(s[2]) if s[2] else None
        } for s in series]
    except Exception as e:
        logging.error(f"Erro ao obter séries: {str(e)}")
        return []


def _obter_turmas_por_serie(serie_id: str, escola_id: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    """
    Retorna turmas de uma série específica em uma escola, sem necessidade de avaliação.
    
    Args:
        serie_id: ID da série
        escola_id: ID da escola
        user: Dicionário com informações do usuário
        permissao: Dicionário com informações de permissão
        
    Returns:
        Lista de turmas no formato [{"id": "...", "nome": "...", "name": "..."}]
    """
    try:
        school = School.query.get(escola_id)
        if not school:
            return []
        
        grade = Grade.query.get(serie_id)
        if not grade:
            return []
        
        # Verificar se o usuário tem acesso à escola
        if permissao['scope'] == 'escola':
            if user.get('role') in ['diretor', 'coordenador']:
                manager = Manager.query.filter_by(user_id=user['id']).first()
                if not manager or manager.school_id != escola_id:
                    return []
            elif user.get('role') == 'professor':
                teacher = Teacher.query.filter_by(user_id=user['id']).first()
                if teacher:
                    teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                    school_ids = [ts.school_id for ts in teacher_schools]
                    if escola_id not in school_ids:
                        return []
                else:
                    return []
        elif permissao['scope'] == 'municipio':
            if user.get('city_id') != school.city_id:
                return []
        
        # Buscar turmas da série na escola
        query_turmas = Class.query.filter(
            Class.grade_id == serie_id,
            Class.school_id == escola_id
        )
        
        # Aplicar filtros específicos para professores
        if permissao['scope'] == 'escola' and user.get('role') == 'professor':
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                from app.models.teacherClass import TeacherClass
                teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                teacher_class_ids = [tc.class_id for tc in teacher_classes]
                if teacher_class_ids:
                    query_turmas = query_turmas.filter(Class.id.in_(teacher_class_ids))
                else:
                    return []
            else:
                return []
        
        turmas = query_turmas.all()
        return [{
            "id": str(t.id),
            "nome": t.name or f"Turma {t.id}",
            "name": t.name or f"Turma {t.id}",
            "grade_id": str(t.grade_id) if t.grade_id else None,
            "school_id": str(t.school_id) if t.school_id else None
        } for t in turmas]
    except Exception as e:
        logging.error(f"Erro ao obter turmas: {str(e)}")
        return []


# ==================== ROTA UNIFICADA ====================

@bp.route('/filter-options', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def obter_opcoes_filtros():
    """
    Retorna opções hierárquicas de filtros para formulários socioeconômicos.
    Funciona sem necessidade de avaliação.
    
    Hierarquia: Estado → Município → Escola → Série → Turma
    
    Query Parameters (todos opcionais, seguindo a hierarquia):
    - estado: Estado selecionado
    - municipio: Município selecionado (requer estado)
    - escola: Escola selecionada (requer municipio)
    - serie: Série selecionada (requer escola)
    - turma: Turma selecionada (requer serie)
    
    Exemplos:
    - GET /forms/filter-options → Retorna apenas estados
    - GET /forms/filter-options?estado=SP → Retorna estados + municípios de SP
    - GET /forms/filter-options?estado=SP&municipio=123 → Retorna estados + municípios + escolas
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Verificar permissões
        permissao = _verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao.get('error', 'Acesso negado')}), 403
        
        # Extrair parâmetros (todos opcionais)
        estado = request.args.get('estado')
        municipio = request.args.get('municipio')
        escola = request.args.get('escola')
        serie = request.args.get('serie')
        turma = request.args.get('turma')
        
        response = {}
        
        # 1. SEMPRE retornar estados (nível 0)
        response["estados"] = _obter_estados_disponiveis(user, permissao)
        
        # 2. Se estado fornecido, retornar municípios (nível 1)
        if estado:
            response["municipios"] = _obter_municipios_por_estado(estado, user, permissao)
            
            # 3. Se município fornecido, retornar escolas (nível 2)
            if municipio:
                response["escolas"] = _obter_escolas_por_municipio(municipio, user, permissao)
                
                # 4. Se escola fornecido, retornar séries (nível 3)
                if escola:
                    response["series"] = _obter_series_por_escola(escola, user, permissao)
                    
                    # 5. Se série fornecido, retornar turmas (nível 4)
                    if serie:
                        response["turmas"] = _obter_turmas_por_serie(serie, escola, user, permissao)
        
        return jsonify(response), 200
        
    except Exception as e:
        logging.error(f"Erro ao obter opções de filtros: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter opções de filtros", "details": str(e)}), 500


# ==================== ROTAS DIRETAS ====================

@bp.route('/schools/city/<string:city_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def buscar_escolas_por_cidade(city_id):
    """
    Busca escolas de um município específico.
    
    Args:
        city_id: ID do município (path parameter)
        
    Returns:
        Lista de escolas do município
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Verificar permissões
        permissao = _verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao.get('error', 'Acesso negado')}), 403
        
        escolas = _obter_escolas_por_municipio(city_id, user, permissao)
        return jsonify(escolas), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar escolas por cidade: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar escolas", "details": str(e)}), 500


@bp.route('/grades/school/<string:school_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def buscar_series_por_escola(school_id):
    """
    Busca séries que têm turmas em uma escola específica.
    
    Args:
        school_id: ID da escola (path parameter)
        
    Returns:
        Lista de séries da escola
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Verificar permissões
        permissao = _verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao.get('error', 'Acesso negado')}), 403
        
        series = _obter_series_por_escola(school_id, user, permissao)
        return jsonify(series), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar séries por escola: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar séries", "details": str(e)}), 500


@bp.route('/classes/grade/<string:grade_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def buscar_turmas_por_serie(grade_id):
    """
    Busca turmas de uma série específica.
    Opcionalmente filtra por escola via query parameter.
    
    Args:
        grade_id: ID da série (path parameter)
        
    Query Parameters:
        escola: ID da escola (opcional) - se fornecido, filtra turmas da série na escola
        
    Returns:
        Lista de turmas da série
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        # Verificar permissões
        permissao = _verificar_permissao_filtros(user)
        if not permissao['permitted']:
            return jsonify({"error": permissao.get('error', 'Acesso negado')}), 403
        
        escola_id = request.args.get('escola')
        
        if escola_id:
            # Se escola fornecida, usar função que filtra por escola também
            turmas = _obter_turmas_por_serie(grade_id, escola_id, user, permissao)
        else:
            # Buscar todas as turmas da série (respeitando permissões)
            grade = Grade.query.get(grade_id)
            if not grade:
                return jsonify([]), 200
            
            query_turmas = Class.query.filter(Class.grade_id == grade_id)
            
            # Aplicar filtros de permissão
            if permissao['scope'] == 'escola':
                if user.get('role') in ['diretor', 'coordenador']:
                    manager = Manager.query.filter_by(user_id=user['id']).first()
                    if manager and manager.school_id:
                        query_turmas = query_turmas.filter(Class.school_id == manager.school_id)
                    else:
                        return jsonify([]), 200
                elif user.get('role') == 'professor':
                    teacher = Teacher.query.filter_by(user_id=user['id']).first()
                    if teacher:
                        from app.models.teacherClass import TeacherClass
                        teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
                        teacher_class_ids = [tc.class_id for tc in teacher_classes]
                        if teacher_class_ids:
                            query_turmas = query_turmas.filter(Class.id.in_(teacher_class_ids))
                        else:
                            return jsonify([]), 200
                    else:
                        return jsonify([]), 200
            elif permissao['scope'] == 'municipio':
                city_id = user.get('city_id')
                if city_id:
                    query_turmas = query_turmas.join(School, Class.school_id == cast(School.id, PostgresUUID)).filter(School.city_id == city_id)
            
            turmas_objs = query_turmas.all()
            turmas = [{
                "id": str(t.id),
                "nome": t.name or f"Turma {t.id}",
                "name": t.name or f"Turma {t.id}",
                "grade_id": str(t.grade_id) if t.grade_id else None,
                "school_id": str(t.school_id) if t.school_id else None
            } for t in turmas_objs]
        
        return jsonify(turmas), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar turmas por série: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar turmas", "details": str(e)}), 500


@bp.route('/grades/<string:grade_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def buscar_serie_por_id(grade_id):
    """
    Busca informações de uma série específica por ID.
    
    Args:
        grade_id: ID da série (path parameter)
        
    Returns:
        Informações da série incluindo education_stage_id
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        
        grade = Grade.query.get(grade_id)
        if not grade:
            return jsonify({"error": "Série não encontrada"}), 404
        
        # Buscar education stage
        education_stage = EducationStage.query.get(grade.education_stage_id) if grade.education_stage_id else None
        
        return jsonify({
            "id": str(grade.id),
            "name": grade.name,
            "nome": grade.name,
            "education_stage_id": str(grade.education_stage_id) if grade.education_stage_id else None,
            "educationStageId": str(grade.education_stage_id) if grade.education_stage_id else None,
            "education_stage": {
                "id": str(education_stage.id),
                "name": education_stage.name,
                "nome": education_stage.name
            } if education_stage else None
        }), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar série: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar série", "details": str(e)}), 500

