from flask import Blueprint, jsonify, request
from app.models.skill import Skill
from app import db

skill_bp = Blueprint('skill_bp', __name__)

@skill_bp.route('/skills', methods=['GET'])
def get_all_skills():
    """
    Busca todas as skills cadastradas no sistema.
    ---
    tags:
      - Skills
    responses:
      200:
        description: Lista de skills retornada com sucesso.
        schema:
          type: array
          items:
            $ref: '#/definitions/Skill'
      500:
        description: Erro interno no servidor.
    """
    try:
        skills = Skill.query.all()
        return jsonify([{
            "id": skill.id,
            "code": skill.code,
            "description": skill.description,
            "subject_id": skill.subject_id,
            "grade_id": skill.grade_id
        } for skill in skills]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@skill_bp.route('/skills/subject/<subject_id>', methods=['GET'])
def get_skills_by_subject(subject_id):
    """
    Busca skills por ID do subject.
    ---
    tags:
      - Skills
    parameters:
      - name: subject_id
        in: path
        type: string
        required: true
        description: ID do subject para buscar as skills.
    responses:
      200:
        description: Lista de skills para o subject especificado.
        schema:
          type: array
          items:
            $ref: '#/definitions/Skill'
      404:
        description: Nenhuma skill encontrada para este subject.
      500:
        description: Erro interno no servidor.
    """
    try:
        skills = Skill.query.filter_by(subject_id=subject_id).all()
        if not skills:
            return jsonify({"message": "Nenhuma skill encontrada para este subject."}), 404
        return jsonify([{
            "id": skill.id,
            "code": skill.code,
            "description": skill.description,
            "subject_id": skill.subject_id,
            "grade_id": skill.grade_id
        } for skill in skills]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500 