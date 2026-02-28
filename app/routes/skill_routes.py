from flask import Blueprint, jsonify, request
from app.models.skill import Skill
from app.models.grades import Grade
from app.models.question import Question
from app.models.test import Test
from app.models.classTest import ClassTest
from app import db
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required, get_current_user_from_token
from app.permissions.utils import get_teacher_classes
from app.utils.question_helpers import get_questions_from_test
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list
from app.utils.tenant_middleware import set_search_path, city_id_to_schema_name
from app.utils.eja_grade_mapping import get_effective_grade_id_for_skills

import logging

skill_bp = Blueprint('skill_bp', __name__)


def _skill_to_dict(skill):
    """Retorna dicionário padrão de uma skill para resposta JSON. grade_ids: lista de IDs das turmas."""
    grade_ids = [str(g.id) for g in (skill.grades or [])]
    return {
        "id": str(skill.id),
        "code": skill.code,
        "description": skill.description,
        "subject_id": skill.subject_id,
        "grade_ids": grade_ids,
        "grade_id": grade_ids[0] if grade_ids else None,  # compatibilidade: primeiro da lista
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
    Body JSON: code (obrigatório), description (obrigatório), subject_id (opcional),
    grade_id (opcional, uma turma) ou grade_ids (opcional, lista de turmas).
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

        grade_ids = data.get("grade_ids")
        if not grade_ids and data.get("grade_id") not in (None, ""):
            grade_ids = [data.get("grade_id")]
        if not isinstance(grade_ids, list):
            grade_ids = []
        grade_uuids = []
        for gid in grade_ids:
            if gid in (None, ""):
                continue
            gu = ensure_uuid(gid)
            if gu is None:
                return jsonify({"error": f"grade_id inválido: {gid}"}), 400
            grade_uuids.append(gu)

        skill = Skill(code=code, description=description, subject_id=subject_id)
        db.session.add(skill)
        db.session.flush()
        for gu in grade_uuids:
            grade = Grade.query.get(gu)
            if grade:
                skill.grades.append(grade)
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
    grade_ids = data.get("grade_ids")
    if not grade_ids and data.get("grade_id") not in (None, ""):
        grade_ids = [data.get("grade_id")]
    if not isinstance(grade_ids, list):
        grade_ids = []
    grade_uuids = []
    for gid in grade_ids:
        if gid in (None, ""):
            continue
        gu = ensure_uuid(gid)
        if gu is None:
            return None, "grade_id inválido"
        grade_uuids.append(gu)
    return {
        "code": code,
        "description": description,
        "subject_id": subject_id,
        "grade_ids": grade_uuids,
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
            grade_ids = kwargs.pop("grade_ids", [])
            skill = Skill(**kwargs)
            db.session.add(skill)
            db.session.flush()
            for gu in grade_ids:
                grade = Grade.query.get(gu)
                if grade:
                    skill.grades.append(grade)
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

    EJA: 1º período equivale a 1º ano, 2º período a 2º ano, até 9º período a 9º ano.
    Para grades de EJA (períodos), as skills do ano correspondente são retornadas.
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
        effective_grade_id = get_effective_grade_id_for_skills(grade_id)
        grade_uuid = ensure_uuid(effective_grade_id)
        if grade_uuid:
            skills = Skill.query.filter(Skill.grades.any(Grade.id == grade_uuid)).all()
        else:
            skills = []
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

        # Professor: garantir schema do município para encontrar Test e ClassTest (multi-tenant)
        if user['role'] == 'professor' and user.get('city_id'):
            schema = city_id_to_schema_name(user['city_id'])
            if schema and schema != 'public':
                set_search_path(schema)

        # Verificar se a avaliação existe
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404

        # Professor: pode ver se criou a avaliação OU se ela foi aplicada em alguma de suas turmas
        if user['role'] == 'professor':
            criou_avaliacao = str(test.created_by or '') == str(user.get('id') or '')
            if not criou_avaliacao:
                teacher_class_ids = get_teacher_classes(user['id'])
                if not teacher_class_ids:
                    return jsonify({"error": "Acesso negado"}), 403
                # ClassTest.class_id é UUID; teacher_class_ids pode ser UUID ou str
                class_ids_norm = ensure_uuid_list(teacher_class_ids)
                aplicada_na_turma = ClassTest.query.filter(
                    ClassTest.test_id == str(test_id),
                    ClassTest.class_id.in_(class_ids_norm)
                ).first()
                if not aplicada_na_turma:
                    return jsonify({"error": "Acesso negado"}), 403

        # Buscar questões da avaliação usando helper multitenant
        questions = get_questions_from_test(test_id, order_by_test_question=True)
        
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
                            grade_ids = [str(g.id) for g in (skill_obj.grades or [])]
                            skills_data.append({
                                "id": skill_obj.id,
                                "code": skill_obj.code,
                                "description": skill_obj.description,
                                "subject_id": skill_obj.subject_id,
                                "grade_ids": grade_ids,
                                "grade_id": grade_ids[0] if grade_ids else None,
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