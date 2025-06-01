from flask import Blueprint, jsonify
from app.models.grades import Grade
from app.models.grades import Grade
from flask_jwt_extended import jwt_required

bp = Blueprint('grades', __name__, url_prefix="/grades")

@bp.route("/", methods=["GET"])
@jwt_required()
def getEducationStages():
    grades = Grade.query.all()
    result = [{"id": g.id, "name": g.name, "education_stage_id":g.education_stage_id} for g in grades]
    return jsonify(result)
