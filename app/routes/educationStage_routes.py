from flask import Blueprint, jsonify, request
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from app.models.teacher import Teacher
from app.models.manager import Manager
from app.models.schoolTeacher import SchoolTeacher
from app.models.studentClass import Class
from app.models.school import School
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from app import db
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from sqlalchemy import cast, String
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
import logging

bp = Blueprint('education_stages', __name__, url_prefix="/education_stages")

@bp.route("", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def getEducationStages():
    try:
        user = get_current_user_from_token()
        
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        # Query base: buscar education_stages que têm grades com classes em escolas
        # Comparar School.id (VARCHAR) com Class.school_id (UUID em texto) via cast explícito em Class
        query = db.session.query(EducationStage).distinct().join(
            Grade, Grade.education_stage_id == EducationStage.id
        ).join(
            Class, Class.grade_id == Grade.id
        ).join(
            School, School.id == cast(Class.school_id, String)
        )
        
        # Aplicar filtros baseados na role
        if user['role'] == "admin":
            # Admin vê todos os education stages que têm escolas no sistema
            pass
        elif user['role'] == "tecadm":
            # Filtrar por município do tecadm
            city_id = user.get('tenant_id') or user.get('city_id')
            if not city_id:
                return jsonify([]), 200
            query = query.filter(School.city_id == city_id)
        elif user['role'] in ["diretor", "coordenador"]:
            # Filtrar pela escola do manager
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if not manager or not manager.school_id:
                return jsonify([]), 200
            # Converter manager.school_id para UUID, mas comparar School.id como texto
            manager_school_id_uuid = ensure_uuid(manager.school_id)
            if manager_school_id_uuid:
                query = query.filter(School.id == str(manager_school_id_uuid))
        elif user['role'] == "professor":
            # Professor: retornar apenas etapas onde ele tem TURMA vinculada (TeacherClass → Class → Grade → EducationStage)
            from app.models.teacherClass import TeacherClass

            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify([]), 200

            teacher_classes = TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            class_ids = [tc.class_id for tc in teacher_classes]
            if not class_ids:
                return jsonify([]), 200

            query = query.filter(Class.id.in_(class_ids))
        
        stages = query.all()
        result = [{"id": str(s.id), "name": s.name} for s in stages]
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar etapas de ensino: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar etapas de ensino", "details": str(e)}), 500

@bp.route("/all", methods=["GET"])
@jwt_required()
def getAllEducationStages():
    """
    Retorna todos os cursos (education stages) do sistema sem filtros ou permissões.
    """
    try:
        stages = EducationStage.query.all()
        result = [{"id": str(s.id), "name": s.name} for s in stages]
        return jsonify(result), 200
        
    except Exception as e:
        logging.error(f"Erro ao buscar todos os cursos: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar todos os cursos", "details": str(e)}), 500

@bp.route("<string:stage_id>", methods=["GET"])
@jwt_required()
def getGradesByEducationId(stage_id):
    grades = Grade.query.filter_by(education_stage_id=stage_id).all()
    return jsonify([{"id":g.id,"name":g.name} for g in grades])

@bp.route("/<stage_id>", methods=["DELETE"])
@jwt_required()
def deleteEducationStage(stage_id):
    try:
        education_stage = EducationStage.query.get(stage_id)
        if not education_stage:
            return jsonify({"error": "Etapa de ensino não encontrada"}), 404

        # Verifica se há grades associadas
        if education_stage.grades:
            return jsonify({"error": "Não é possível excluir etapa de ensino que possui grades associadas"}), 400

        db.session.delete(education_stage)
        db.session.commit()
        
        return jsonify({"message": "Etapa de ensino excluída com sucesso"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao excluir etapa de ensino", "details": str(e)}), 500

@bp.route("/<stage_id>", methods=["PUT"])
@jwt_required()
def updateEducationStage(stage_id):
    try:
        education_stage = EducationStage.query.get(stage_id)
        if not education_stage:
            return jsonify({"error": "Etapa de ensino não encontrada"}), 404

        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400

        # Atualiza o nome se fornecido
        if 'name' in data:
            if not data['name'] or not data['name'].strip():
                return jsonify({"error": "Nome da etapa de ensino é obrigatório"}), 400
            education_stage.name = data['name'].strip()

        db.session.commit()
        
        return jsonify({
            "id": education_stage.id,
            "name": education_stage.name,
            "message": "Etapa de ensino atualizada com sucesso"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao atualizar etapa de ensino", "details": str(e)}), 500
