from flask import Blueprint, jsonify
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
