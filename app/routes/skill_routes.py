from flask import Blueprint, jsonify, request
from app.models.skill import Skill
from app.models.question import Question
from app.models.test import Test
from app import db
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.utils.uuid_helpers import ensure_uuid
import logging

skill_bp = Blueprint('skill_bp', __name__)


def _skill_to_dict(skill):
    """Retorna dicionário padrão de uma skill para resposta JSON."""
    return {
        "id": str(skill.id),
        "code": skill.code,
        "description": skill.description,
        "subject_id": skill.subject_id,
        "grade_id": str(skill.grade_id) if skill.grade_id else None,
    }

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
        return jsonify([_skill_to_dict(skill) for skill in skills]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@skill_bp.route('/skills', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def create_skill():
    """
    Cria uma nova habilidade (skill) no banco.
    Body JSON: code (obrigatório), description (obrigatório), subject_id (opcional), grade_id (opcional).
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Corpo JSON obrigatório"}), 400

        code = (data.get("code") or "").strip()
        description = (data.get("description") or "").strip()
        if not code:
            return jsonify({"error": "code é obrigatório"}), 400
        if not description:
            return jsonify({"error": "description é obrigatório"}), 400

        subject_id = data.get("subject_id")
        if subject_id is not None and subject_id != "":
            subject_id = str(subject_id).strip() or None
        else:
            subject_id = None

        grade_id = data.get("grade_id")
        if grade_id is not None and grade_id != "":
            grade_uuid = ensure_uuid(grade_id)
            if grade_uuid is None:
                return jsonify({"error": "grade_id inválido"}), 400
        else:
            grade_uuid = None

        skill = Skill(
            code=code,
            description=description,
            subject_id=subject_id,
            grade_id=grade_uuid,
        )
        db.session.add(skill)
        db.session.commit()
        return jsonify(_skill_to_dict(skill)), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar skill: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def _parse_skill_item(data, index):
    """
    Valida e extrai campos de um item de skill para criação.
    Retorna (skill_kwargs, None) em sucesso ou (None, mensagem_erro) em falha.
    """
    if not isinstance(data, dict):
        return None, "item deve ser um objeto"
    code = (data.get("code") or "").strip()
    description = (data.get("description") or "").strip()
    if not code:
        return None, "code é obrigatório"
    if not description:
        return None, "description é obrigatório"
    subject_id = data.get("subject_id")
    if subject_id is not None and subject_id != "":
        subject_id = str(subject_id).strip() or None
    else:
        subject_id = None
    grade_id = data.get("grade_id")
    if grade_id is not None and grade_id != "":
        grade_uuid = ensure_uuid(grade_id)
        if grade_uuid is None:
            return None, "grade_id inválido"
    else:
        grade_uuid = None
    return {
        "code": code,
        "description": description,
        "subject_id": subject_id,
        "grade_id": grade_uuid,
    }, None


@skill_bp.route('/skills/batch', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def create_skills_batch():
    """
    Cria várias habilidades em lote via JSON.
    Body: { "skills": [ { "code", "description", "subject_id?", "grade_id?" }, ... ] }
    Retorna lista de habilidades criadas e lista de erros por índice (itens inválidos são ignorados).
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Corpo JSON obrigatório"}), 400

        raw = data.get("skills") if isinstance(data, dict) else None
        if not isinstance(raw, list):
            return jsonify({"error": "Campo 'skills' deve ser um array"}), 400

        created = []
        errors = []
        to_insert = []

        for index, item in enumerate(raw):
            kwargs, err = _parse_skill_item(item, index)
            if err:
                errors.append({"index": index, "error": err})
                continue
            to_insert.append(kwargs)

        if not to_insert:
            return jsonify({
                "error": "Nenhum item válido para criar",
                "errors": errors,
            }), 400

        for kwargs in to_insert:
            skill = Skill(**kwargs)
            db.session.add(skill)
            db.session.flush()
            created.append(_skill_to_dict(skill))

        db.session.commit()
        response = {"created": created, "count": len(created)}
        if errors:
            response["errors"] = errors
        return jsonify(response), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao criar skills em lote: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@skill_bp.route('/skills/<skill_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def delete_skill(skill_id):
    """
    Remove uma habilidade (skill) do banco pelo id.
    Retorna 404 se não existir, 200 com mensagem em caso de sucesso.
    """
    try:
        skill_uuid = ensure_uuid(skill_id)
        if not skill_uuid:
            return jsonify({"error": "ID da habilidade inválido"}), 400

        skill = Skill.query.get(skill_uuid)
        if not skill:
            return jsonify({"error": "Habilidade não encontrada"}), 404

        db.session.delete(skill)
        db.session.commit()
        return jsonify({"message": "Habilidade removida com sucesso"}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao deletar skill {skill_id}: {str(e)}", exc_info=True)
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
        return jsonify([_skill_to_dict(skill) for skill in skills]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@skill_bp.route('/skills/grade/<grade_id>', methods=['GET'])
def get_skills_by_grade(grade_id):
    """
    Busca skills por ID do grade.
    ---
    tags:
      - Skills
    parameters:
      - name: grade_id
        in: path
        type: string
        required: true
        description: ID do grade para buscar as skills.
    responses:
      200:
        description: Lista de skills para o grade especificado.
        schema:
          type: array
          items:
            $ref: '#/definitions/Skill'
      404:
        description: Nenhuma skill encontrada para este grade.
      500:
        description: Erro interno no servidor.
    """
    try:
        skills = Skill.query.filter_by(grade_id=grade_id).all()
        if not skills:
            return jsonify({"message": "Nenhuma skill encontrada para este grade."}), 404
        return jsonify([_skill_to_dict(skill) for skill in skills]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@skill_bp.route('/skills/evaluation/<test_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_skills_by_evaluation(test_id):
    """
    Busca skills utilizadas em uma avaliação específica.
    Extrai as skills das questões da avaliação.
    ---
    tags:
      - Skills
    parameters:
      - name: test_id
        in: path
        type: string
        required: true
        description: ID da avaliação para buscar as skills.
    responses:
      200:
        description: Lista de skills utilizadas na avaliação.
        schema:
          type: array
          items:
            $ref: '#/definitions/Skill'
      404:
        description: Avaliação não encontrada ou sem skills.
      500:
        description: Erro interno no servidor.
    """
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401

        # Verificar se a avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Verificar permissões
        if user['role'] == 'professor' and test.created_by != user['id']:
            return jsonify({"error": "Acesso negado"}), 403

        # Buscar questões da avaliação
        # Buscar questões do teste através da tabela de associação
        from app.models.testQuestion import TestQuestion
        test_question_ids = [tq.question_id for tq in TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()]
        questions = Question.query.filter(Question.id.in_(test_question_ids)).all() if test_question_ids else []
        
        if not questions:
            return jsonify({"message": "Avaliação não possui questões."}), 404

        # Extrair skills únicas das questões
        skills_set = set()
        skills_data = []
        
        for question in questions:
            if question.skill:
                # O campo skill pode conter múltiplas skills separadas por vírgula
                question_skills = [s.strip() for s in question.skill.split(',') if s.strip()]
                
                for skill_code in question_skills:
                    if skill_code not in skills_set:
                        skills_set.add(skill_code)
                        
                        # Buscar informações da skill no banco
                        # Primeiro tentar buscar por ID (UUID)
                        skill_obj = None
                        try:
                            import uuid
                            # Remover chaves se existirem
                            skill_id_clean = skill_code.strip('{}')
                            uuid_obj = uuid.UUID(skill_id_clean)
                            skill_obj = Skill.query.filter_by(id=str(uuid_obj)).first()
                        except (ValueError, AttributeError):
                            pass
                        
                        # Se não encontrou por ID, tentar por código
                        if not skill_obj:
                            skill_obj = Skill.query.filter_by(code=skill_code).first()
                        
                        if skill_obj:
                            # Skill encontrada no banco
                            skills_data.append({
                                "id": skill_obj.id,
                                "code": skill_obj.code,
                                "description": skill_obj.description,
                                "subject_id": skill_obj.subject_id,
                                "grade_id": skill_obj.grade_id,
                                "source": "database"
                            })
                        else:
                            # Skill não encontrada no banco, criar entrada básica
                            skills_data.append({
                                "id": None,
                                "code": skill_code,
                                "description": f"Skill {skill_code} (não cadastrada)",
                                "subject_id": question.subject_id,
                                "grade_id": question.grade_level,
                                "source": "question"
                            })

        if not skills_data:
            return jsonify({"message": "Nenhuma skill encontrada na avaliação."}), 404

        # Ordenar por código da skill
        skills_data.sort(key=lambda x: x['code'])

        return jsonify(skills_data), 200

    except Exception as e:
        logging.error(f"Erro ao buscar skills da avaliação {test_id}: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500 