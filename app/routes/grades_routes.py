from flask import Blueprint, jsonify, request
from app.models.grades import Grade
from app.models.educationStage import EducationStage
from app import db
from flask_jwt_extended import jwt_required

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

@bp.route("/education-stage/<education_stage_id>", methods=["GET"])
@jwt_required()
def getGradesByEducationStage(education_stage_id):
    try:
        # Verifica se a etapa de ensino existe
        education_stage = EducationStage.query.get(education_stage_id)
        if not education_stage:
            return jsonify({"error": "Etapa de ensino não encontrada"}), 404

        # Busca todas as grades da etapa de ensino
        grades = Grade.query.filter_by(education_stage_id=education_stage_id).all()
        
        result = [{
            "id": grade.id,
            "name": grade.name,
            "education_stage_id": grade.education_stage_id,
            "education_stage": {
                "id": education_stage.id,
                "name": education_stage.name
            }
        } for grade in grades]
        
        return jsonify(result), 200

    except Exception as e:
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
