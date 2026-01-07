from flask import Blueprint, jsonify, request
from app.models.grades import Grade
from app.models.educationStage import EducationStage
from app.models.teacher import Teacher
from app.models.manager import Manager
from app.models.schoolTeacher import SchoolTeacher
from app.models.studentClass import Class
from app.models.school import School
from app import db
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
import logging

bp = Blueprint('grades', __name__, url_prefix="/grades")

@bp.route("/", methods=["GET"])
@jwt_required()
def getEducationStages():
    # Query with explicit joins
    grades = db.session.query(
        Grade,
        EducationStage
    ).join(
        EducationStage, Grade.education_stage_id == EducationStage.id
    ).all()

    result = [{
        "id": grade.id,
        "name": grade.name,
        "education_stage_id": grade.education_stage_id,
        "education_stage": {
            "id": stage.id,
            "name": stage.name
        } if stage else None
    } for grade, stage in grades]
    
    return jsonify(result)

@bp.route("/by-education-stage/<education_stage_id>", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor", "responsavel")
def getAllGradesByEducationStage(education_stage_id):
    try:
        # Verifica se a etapa de ensino existe
        education_stage = EducationStage.query.get(education_stage_id)
        if not education_stage:
            return jsonify({"error": "Etapa de ensino não encontrada"}), 404

        # Buscar todas as grades da etapa sem filtros
        grades = Grade.query.filter(Grade.education_stage_id == education_stage_id).all()
        
        result = [{
            "id": str(grade.id),
            "name": grade.name,
            "education_stage_id": str(grade.education_stage_id),
            "education_stage": {
                "id": str(education_stage.id),
                "name": education_stage.name
            }
        } for grade in grades]
        
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Erro ao buscar grades: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar grades", "details": str(e)}), 500

@bp.route("/education-stage/<education_stage_id>", methods=["GET"])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador", "professor")
def getGradesByEducationStage(education_stage_id):
    try:
        user = get_current_user_from_token()
        
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 404
        
        # Verifica se a etapa de ensino existe
        education_stage = EducationStage.query.get(education_stage_id)
        if not education_stage:
            return jsonify({"error": "Etapa de ensino não encontrada"}), 404

        # Query base: buscar grades da etapa que têm classes em escolas
        query = db.session.query(Grade).distinct().join(
            Class, Class.grade_id == Grade.id
        ).join(
            School, Class.school_id == School.id
        ).filter(
            Grade.education_stage_id == education_stage_id
        )
        
        # Aplicar filtros baseados na role
        if user['role'] == "admin":
            # Admin vê todas as grades que têm escolas no sistema
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
            query = query.filter(School.id == manager.school_id)
        elif user['role'] == "professor":
            # Filtrar pelas escolas onde o professor está vinculado
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if not teacher:
                return jsonify([]), 200
            
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            school_ids = [ts.school_id for ts in teacher_schools]
            
            if not school_ids:
                return jsonify([]), 200
            query = query.filter(School.id.in_(school_ids))
        
        grades = query.all()
        
        result = [{
            "id": str(grade.id),
            "name": grade.name,
            "education_stage_id": str(grade.education_stage_id),
            "education_stage": {
                "id": str(education_stage.id),
                "name": education_stage.name
            }
        } for grade in grades]
        
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Erro ao buscar grades: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao buscar grades", "details": str(e)}), 500

@bp.route("/<grade_id>", methods=["DELETE"])
@jwt_required()
def deleteGrade(grade_id):
    try:
        grade = Grade.query.get(grade_id)
        if not grade:
            return jsonify({"error": "Grade não encontrada"}), 404

        # Verifica se há classes ou estudantes associados
        if grade.classes or grade.students:
            return jsonify({"error": "Não é possível excluir grade que possui classes ou estudantes associados"}), 400

        db.session.delete(grade)
        db.session.commit()
        
        return jsonify({"message": "Grade excluída com sucesso"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao excluir grade", "details": str(e)}), 500

@bp.route("/<grade_id>", methods=["PUT"])
@jwt_required()
def updateGrade(grade_id):
    try:
        grade = Grade.query.get(grade_id)
        if not grade:
            return jsonify({"error": "Grade não encontrada"}), 404

        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Dados não fornecidos"}), 400

        # Atualiza o nome se fornecido
        if 'name' in data:
            if not data['name'] or not data['name'].strip():
                return jsonify({"error": "Nome da grade é obrigatório"}), 400
            grade.name = data['name'].strip()

        # Atualiza a etapa de ensino se fornecida
        if 'education_stage_id' in data:
            education_stage = EducationStage.query.get(data['education_stage_id'])
            if not education_stage:
                return jsonify({"error": "Etapa de ensino não encontrada"}), 404
            grade.education_stage_id = data['education_stage_id']

        db.session.commit()
        
        return jsonify({
            "id": grade.id,
            "name": grade.name,
            "education_stage_id": grade.education_stage_id,
            "message": "Grade atualizada com sucesso"
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Erro ao atualizar grade", "details": str(e)}), 500
