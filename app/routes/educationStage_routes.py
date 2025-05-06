from flask import Blueprint, jsonify
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from flask_jwt_extended import jwt_required

bp = Blueprint('education_stages', __name__, url_prefix="/education_stages")

@bp.route("/", methods=["GET"])
@jwt_required()
def getEducationStages():
    stages = EducationStage.query.all()
    result = [{"id": s.id, "name": s.name} for s in stages]
    return jsonify(result)

@bp.route("/<string:stage_id>", methods=["GET"])
@jwt_required()
def getGradesByEducationId(stage_id):
    grades = Grade.query.filter_by(education_stage_id=stage_id).all()
    return jsonify([{"id":g.id,"name":g.name} for g in grades])
