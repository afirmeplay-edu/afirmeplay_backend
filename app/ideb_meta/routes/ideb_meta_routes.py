# -*- coding: utf-8 -*-
"""
Rotas para persistência da Calculadora de Metas IDEB.
Usa município (City) e nível do sistema.
GET: carregar dados por contexto (city_id, level).
PUT: salvar/atualizar dados (upsert por contexto).
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Optional, Set

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app import db
from app.ideb_meta.models import IdebMetaSave
from app.models.city import City
from app.models.school import School
from app.permissions import get_current_user_from_token
from app.permissions.roles import Roles
from app.permissions.utils import get_manager_school, get_teacher_schools

bp = Blueprint('ideb_meta', __name__, url_prefix='/ideb-meta')


def _ideb_meta_allowed_school_ids(user: Optional[Dict[str, Any]]) -> Optional[Set[str]]:
    """
    Escolas que o usuário pode ver/editar na calculadora de metas (lista escolas).

    None = sem restrição (admin, tecadm): vê todas as escolas do município no JSON.
    set vazio = perfil restrito sem escola vinculada.
    set não vazio = apenas esses IDs (diretor/coordenador: uma; professor: todas as vinculadas).
    """
    if not user:
        return set()
    role = Roles.normalize(user.get('role', ''))
    if Roles.is_admin_role(role):
        return None
    uid = user.get('id')
    if not uid:
        return set()
    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        sid = get_manager_school(uid)
        return {str(sid)} if sid else set()
    if role == Roles.PROFESSOR:
        ids = get_teacher_schools(uid)
        return {str(x) for x in ids} if ids else set()
    return set()


def _sanitize_active_entity_id(active_entity_id: Any, city_id: str, allowed: Optional[Set[str]]) -> Any:
    """Evita que o front mantenha seleção de outra escola na resposta após filtrar escolas."""
    if allowed is None:
        return active_entity_id
    if active_entity_id is None:
        return None
    ae = str(active_entity_id).strip()
    if ae == str(city_id):
        return active_entity_id
    if ae.lower() in ('municipio', 'municipality', 'municipal'):
        return active_entity_id
    if not allowed:
        return None
    if ae in allowed:
        return active_entity_id
    return None


def _filter_payload_for_ideb_response(
    payload: Optional[Dict[str, Any]],
    user: Optional[Dict[str, Any]],
    city_id: str,
) -> Dict[str, Any]:
    """Diretor/coordenador/professor: mantém dados municipais do JSON, mas só suas escolas em escolas[]."""
    if not payload:
        return {}
    allowed = _ideb_meta_allowed_school_ids(user)
    if allowed is None:
        return copy.deepcopy(payload)
    out = copy.deepcopy(payload)
    md = out.get('municipalityData')
    if isinstance(md, dict):
        md = dict(md)
        out['municipalityData'] = md
        escolas = md.get('escolas')
        if isinstance(escolas, list):
            md['escolas'] = [
                e for e in escolas
                if isinstance(e, dict) and str(e.get('id')) in allowed
            ]
    out['activeEntityId'] = _sanitize_active_entity_id(out.get('activeEntityId'), city_id, allowed)
    return out


def _merge_put_payload_for_restricted_school_roles(
    existing: Optional[Dict[str, Any]],
    incoming: Dict[str, Any],
    city_id: str,
    allowed: Set[str],
) -> Dict[str, Any]:
    """
    Mescla PUT sem permitir que diretor/coordenador/professor sobrescrevam o bloco
    municipal nem alterem escolas de terceiros; só atualiza entradas das próprias escolas.
    """
    base = copy.deepcopy(existing) if existing else {}
    if not isinstance(base, dict):
        base = {}
    base.setdefault('municipalityData', {})
    if not isinstance(base['municipalityData'], dict):
        base['municipalityData'] = {}
    base_md = base['municipalityData']
    base_md.setdefault('escolas', [])
    if not isinstance(base_md['escolas'], list):
        base_md['escolas'] = []

    inc_md = incoming.get('municipalityData') if isinstance(incoming.get('municipalityData'), dict) else {}
    inc_escolas = inc_md.get('escolas') if isinstance(inc_md.get('escolas'), list) else []

    by_id: Dict[str, Any] = {}
    for e in base_md['escolas']:
        if isinstance(e, dict) and e.get('id') is not None:
            by_id[str(e['id'])] = e
    for e in inc_escolas:
        if not isinstance(e, dict) or e.get('id') is None:
            continue
        eid = str(e['id'])
        if eid in allowed:
            by_id[eid] = e

    new_escolas = []
    seen: Set[str] = set()
    for e in base_md['escolas']:
        if not isinstance(e, dict) or e.get('id') is None:
            continue
        eid = str(e['id'])
        if eid in allowed:
            new_escolas.append(by_id.get(eid, e))
        else:
            new_escolas.append(e)
        seen.add(eid)
    for eid, e in by_id.items():
        if eid not in seen:
            new_escolas.append(e)

    base_md['escolas'] = new_escolas

    if 'customTarget' in incoming:
        base['customTarget'] = incoming.get('customTarget')
    if 'targetYear' in incoming:
        base['targetYear'] = incoming.get('targetYear')
    if 'activeEntityId' in incoming:
        base['activeEntityId'] = _sanitize_active_entity_id(incoming.get('activeEntityId'), city_id, allowed)

    return base


def _user_can_access_city(city_id):
    """Verifica se o usuário pode acessar o município (admin ou próprio município)."""
    user = get_current_user_from_token()
    if not user:
        return False
    if Roles.normalize(user.get('role', '')) == Roles.ADMIN:
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

    user = get_current_user_from_token()
    return jsonify({
        "payload": _filter_payload_for_ideb_response(record.payload, user, city_id),
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

    user = get_current_user_from_token()
    allowed = _ideb_meta_allowed_school_ids(user)

    record = IdebMetaSave.query.filter_by(city_id=city_id, level=level).first()

    if allowed is None:
        payload = {
            'municipalityData': data.get('municipalityData'),
            'customTarget': data.get('customTarget'),
            'activeEntityId': data.get('activeEntityId'),
            'targetYear': data.get('targetYear'),
        }
    else:
        existing = record.payload if record and record.payload else None
        payload = _merge_put_payload_for_restricted_school_roles(
            existing if isinstance(existing, dict) else None,
            data,
            city_id,
            allowed,
        )

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
        "payload": _filter_payload_for_ideb_response(record.payload, user, city_id),
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

    user = get_current_user_from_token()
    allowed = _ideb_meta_allowed_school_ids(user)
    sch = School.query.get(str(school_id))
    if not sch or str(sch.city_id) != str(city_id):
        return jsonify({"erro": "Escola não encontrada ou não pertence a este município"}), 400
    if allowed is not None and str(school_id) not in allowed:
        return jsonify({
            "erro": "Sem permissão para incluir ou alterar dados de outra escola na calculadora de metas",
        }), 403

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
        "payload": _filter_payload_for_ideb_response(record.payload, user, city_id),
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
