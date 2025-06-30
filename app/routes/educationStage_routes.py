from flask import Blueprint, jsonify, request
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from app import db
from flask_jwt_extended import jwt_required

bp = Blueprint('education_stages', __name__, url_prefix="/education_stages")

@bp.route("", methods=["GET"])
@jwt_required()
def getEducationStages():
    stages = EducationStage.query.all()
    result = [{"id": s.id, "name": s.name} for s in stages]
    return jsonify(result)

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
