# -*- coding: utf-8 -*-
"""
Rotas para persistência da Calculadora de Metas IDEB.
GET: carregar dados por contexto (state_id, municipality_id, level).
PUT: salvar/atualizar dados (upsert por contexto).
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app import db
from app.ideb_meta.models import IdebMetaSave
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

bp = Blueprint('ideb_meta', __name__, url_prefix='/ideb-meta')


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
    Retorna o payload salvo para o contexto (state_id, municipality_id, level).
    Query: state_id, municipality_id, level.
    Resposta: 200 com payload e updated_at, ou 404 se não existir.
    """
    state_id = request.args.get('state_id')
    municipality_id = request.args.get('municipality_id')
    level = request.args.get('level')

    if not state_id or not municipality_id or not level:
        return jsonify({
            "erro": "Parâmetros obrigatórios: state_id, municipality_id, level",
        }), 400

    record = IdebMetaSave.query.filter_by(
        state_id=state_id,
        municipality_id=municipality_id,
        level=level,
    ).first()

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
    Salva ou atualiza os dados da calculadora para o contexto.
    Body: state_id, municipality_id, level + municipalityData, customTarget,
    activeEntityId, targetYear (objeto completo do front).
    Faz upsert por (state_id, municipality_id, level).
    """
    data = request.get_json()
    if not data:
        return jsonify({"erro": "Body JSON obrigatório"}), 400

    state_id = data.get('state_id')
    municipality_id = data.get('municipality_id')
    level = data.get('level')

    if not state_id or not municipality_id or not level:
        return jsonify({
            "erro": "Body deve conter state_id, municipality_id e level",
        }), 400

    payload = {
        'municipalityData': data.get('municipalityData'),
        'customTarget': data.get('customTarget'),
        'activeEntityId': data.get('activeEntityId'),
        'targetYear': data.get('targetYear'),
    }

    record = IdebMetaSave.query.filter_by(
        state_id=state_id,
        municipality_id=municipality_id,
        level=level,
    ).first()

    if record:
        record.payload = payload
        db.session.commit()
        db.session.refresh(record)
        status = 200
    else:
        record = IdebMetaSave(
            state_id=state_id,
            municipality_id=municipality_id,
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
