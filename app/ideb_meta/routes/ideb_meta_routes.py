# -*- coding: utf-8 -*-
"""
Rotas para persistência da Calculadora de Metas IDEB.
Usa município (City) e nível do sistema.
GET: carregar dados por contexto (city_id, level).
PUT: salvar/atualizar dados (upsert por contexto).
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.models.city import City
from app.ideb_meta.models import IdebMetaSave
from app.permissions import get_current_user_from_token
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

bp = Blueprint('ideb_meta', __name__, url_prefix='/ideb-meta')


def _user_can_access_city(city_id):
    """Verifica se o usuário pode acessar o município (admin ou próprio município)."""
    user = get_current_user_from_token()
    if not user:
        return False
    if user.get('role') == 'admin':
        return True
    user_city_id = user.get('tenant_id') or user.get('city_id')
    return user_city_id == city_id


def _user_can_delete_for_city(city_id):
    """
    Verifica se o usuário pode deletar (escola do payload) para o município.
    Apenas admin (qualquer município) ou tecadm (apenas o próprio município).
    """
    user = get_current_user_from_token()
    if not user:
        return False
    role = (user.get('role') or '').lower()
    if role == 'admin':
        return True
    if role == 'tecadm':
        user_city_id = user.get('tenant_id') or user.get('city_id')
        return user_city_id == city_id
    return False


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error("Database error in ideb_meta: %s", str(error))
    return jsonify({"erro": "Erro no banco de dados", "detalhes": str(error)}), 500


@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error("Integrity error in ideb_meta: %s", str(error))
    return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(error)}), 400


@bp.route('', methods=['GET'])
@jwt_required()
def get_ideb_meta():
    """
    Retorna o payload salvo para o contexto (city_id, level).
    Query: city_id, level.
    Resposta: 200 com payload e updated_at, ou 404 se não existir.
    Valida que o município existe no sistema e que o usuário tem acesso.
    """
    city_id = request.args.get('city_id')
    level = request.args.get('level')

    if not city_id or not level:
        return jsonify({
            "erro": "Parâmetros obrigatórios: city_id, level",
        }), 400

    city = City.query.get(city_id)
    if not city:
        return jsonify({"erro": "Município não encontrado"}), 404

    if not _user_can_access_city(city_id):
        return jsonify({"erro": "Você não tem permissão para acessar este município"}), 403

    record = IdebMetaSave.query.filter_by(city_id=city_id, level=level).first()

    if not record:
        return jsonify({"erro": "Nenhum dado salvo para este contexto"}), 404

    return jsonify({
        "payload": record.payload,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }), 200


@bp.route('', methods=['PUT'])
@jwt_required()
def put_ideb_meta():
    """
    Salva ou atualiza os dados da calculadora para o contexto (city_id, level).
    Body: city_id, level + municipalityData, customTarget, activeEntityId, targetYear.
    Valida que o município existe e que o usuário tem acesso.
    """
    data = request.get_json()
    if not data:
        return jsonify({"erro": "Body JSON obrigatório"}), 400

    city_id = data.get('city_id')
    level = data.get('level')

    if not city_id or not level:
        return jsonify({
            "erro": "Body deve conter city_id e level",
        }), 400

    city = City.query.get(city_id)
    if not city:
        return jsonify({"erro": "Município não encontrado"}), 404

    if not _user_can_access_city(city_id):
        return jsonify({"erro": "Você não tem permissão para salvar neste município"}), 403

    payload = {
        'municipalityData': data.get('municipalityData'),
        'customTarget': data.get('customTarget'),
        'activeEntityId': data.get('activeEntityId'),
        'targetYear': data.get('targetYear'),
    }

    record = IdebMetaSave.query.filter_by(city_id=city_id, level=level).first()

    if record:
        record.payload = payload
        db.session.commit()
        db.session.refresh(record)
        status = 200
    else:
        record = IdebMetaSave(
            city_id=city_id,
            level=level,
            payload=payload,
        )
        db.session.add(record)
        db.session.commit()
        db.session.refresh(record)
        status = 201

    return jsonify({
        "payload": record.payload,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }), status


def _get_or_create_payload(city_id, level):
    """
    Retorna (IdebMetaSave, payload_dict) para o contexto.
    Se não existir registro, cria um com payload mínimo; payload_dict é mutável.
    """
    record = IdebMetaSave.query.filter_by(city_id=city_id, level=level).first()
    if record:
        payload = dict(record.payload) if record.payload else {}
    else:
        record = IdebMetaSave(city_id=city_id, level=level, payload={})
        db.session.add(record)
        db.session.flush()
        payload = {}
    # Garantir estrutura mínima para municipalityData.escolas
    if 'municipalityData' not in payload or payload['municipalityData'] is None:
        payload['municipalityData'] = {}
    md = payload['municipalityData']
    if not isinstance(md, dict):
        md = {}
        payload['municipalityData'] = md
    if 'escolas' not in md or not isinstance(md['escolas'], list):
        md['escolas'] = []
    return record, payload


@bp.route('/schools', methods=['POST'])
@jwt_required()
def add_school_to_calculator():
    """
    Adiciona uma escola ao payload da calculadora (municipalityData.escolas).
    Não cria registro na tabela School; só persiste no JSON da calculadora.
    Body: city_id, level, e escola { id, nome, level, ideb, historico? }.
    """
    data = request.get_json()
    if not data:
        return jsonify({"erro": "Body JSON obrigatório"}), 400

    city_id = data.get('city_id')
    level = data.get('level')
    escola = data.get('escola') or data.get('school')

    if not city_id or not level:
        return jsonify({"erro": "Body deve conter city_id e level"}), 400
    if not escola or not isinstance(escola, dict):
        return jsonify({"erro": "Body deve conter objeto 'escola' com id, nome, level, ideb"}), 400

    school_id = escola.get('id')
    if not school_id:
        return jsonify({"erro": "Objeto escola deve ter 'id'"}), 400

    city = City.query.get(city_id)
    if not city:
        return jsonify({"erro": "Município não encontrado"}), 404
    if not _user_can_access_city(city_id):
        return jsonify({"erro": "Você não tem permissão para acessar este município"}), 403

    record, payload = _get_or_create_payload(city_id, level)
    escolas = payload['municipalityData']['escolas']

    # Normalizar escola: id, nome, level, ideb, historico (opcional)
    nova = {
        'id': str(school_id),
        'nome': escola.get('nome') or escola.get('name') or '',
        'level': escola.get('level') or level,
        'ideb': escola.get('ideb'),
        'historico': escola.get('historico') if isinstance(escola.get('historico'), list) else [],
    }
    if nova.get('ideb') is None:
        nova['ideb'] = 0

    # Atualizar se já existe pelo id, senão adicionar
    for i, e in enumerate(escolas):
        if isinstance(e, dict) and str(e.get('id')) == str(school_id):
            escolas[i] = nova
            break
    else:
        escolas.append(nova)

    record.payload = payload
    db.session.commit()
    db.session.refresh(record)

    return jsonify({
        "payload": record.payload,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }), 200


@bp.route('/schools/<school_id>', methods=['DELETE'])
@jwt_required()
def remove_school_from_calculator(school_id):
    """
    Remove uma escola do payload da calculadora (municipalityData.escolas).
    Não remove da tabela School; só altera o JSON salvo.
    Apenas admin (qualquer município) ou tecadm (apenas o próprio município) podem deletar.
    Query: city_id, level.
    """
    city_id = request.args.get('city_id')
    level = request.args.get('level')

    if not city_id or not level:
        return jsonify({
            "erro": "Parâmetros obrigatórios: city_id, level",
        }), 400

    city = City.query.get(city_id)
    if not city:
        return jsonify({"erro": "Município não encontrado"}), 404
    if not _user_can_delete_for_city(city_id):
        return jsonify({
            "erro": "Apenas admin ou tec adm do município podem remover escola. Demais perfis não têm permissão.",
        }), 403

    record = IdebMetaSave.query.filter_by(city_id=city_id, level=level).first()
    if not record or not record.payload:
        return jsonify({"erro": "Nenhum dado salvo para este contexto"}), 404

    payload = dict(record.payload)
    md = payload.get('municipalityData')
    if not isinstance(md, dict):
        return jsonify({"payload": record.payload, "updated_at": _updated_at(record)}), 200

    escolas = md.get('escolas')
    if not isinstance(escolas, list):
        return jsonify({"payload": record.payload, "updated_at": _updated_at(record)}), 200

    md = dict(md)
    payload['municipalityData'] = md
    md['escolas'] = [e for e in escolas if isinstance(e, dict) and str(e.get('id')) != str(school_id)]

    record.payload = payload
    db.session.commit()
    db.session.refresh(record)

    return jsonify({
        "payload": record.payload,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }), 200


def _updated_at(record):
    return record.updated_at.isoformat() if record.updated_at else None
