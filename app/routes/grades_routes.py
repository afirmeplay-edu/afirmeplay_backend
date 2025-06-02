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
