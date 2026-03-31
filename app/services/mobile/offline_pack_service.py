"""
Geração e resgate de pacotes offline (código digitável + escopo).
Usa tabelas mobile_offline_pack_* no schema do município.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import false as sa_false
from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.models.mobile_models import MobileOfflinePackCode, MobileOfflinePackRedeemDevice
from app.models.mobile_offline_pack_registry import MobileOfflinePackRegistry
from app.models.school import School
from app.models.student import Student
from app.models.test import Test
from app.models.user import User
from app.services.mobile.bundle_service import (
    build_tests_questions_payload,
    collect_school_scope,
    ensure_bundle_generation,
)

_CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def _pepper() -> str:
    return (os.getenv("OFFLINE_PACK_CODE_PEPPER") or os.getenv("JWT_SECRET_KEY") or "").strip()


def generate_activation_code(groups: int = 3, chars_per_group: int = 4) -> str:
    """Código no formato XXXX-XXXX-XXXX (sem 0,O,1,I)."""
    parts: List[str] = []
    for _ in range(groups):
        parts.append(
            "".join(secrets.choice(_CODE_ALPHABET) for _ in range(chars_per_group))
        )
    return "-".join(parts)


def normalize_code(raw: str) -> str:
    if not raw or not isinstance(raw, str):
        raise ValueError("código obrigatório")
    s = "".join(c for c in raw.upper() if c in _CODE_ALPHABET)
    if len(s) != 12:
        raise ValueError("código deve ter 12 caracteres após normalização")
    return s


def normalize_mobile_input_code(raw: str) -> str:
    """Aceita código digitado com ou sem hífens."""
    if not raw or not isinstance(raw, str):
        raise ValueError("código obrigatório")
    s = "".join(c for c in raw.upper() if c in _CODE_ALPHABET)
    if len(s) != 12:
        raise ValueError("código inválido (12 caracteres, sem 0,O,1,I)")
    return s


def format_code(normalized: str, chars_per_group: int = 4) -> str:
    parts = [
        normalized[i : i + chars_per_group]
        for i in range(0, len(normalized), chars_per_group)
    ]
    return "-".join(parts)


def hash_code(normalized: str) -> str:
    return hashlib.sha256(f"{_pepper()}:{normalized}".encode("utf-8")).hexdigest()


def bind_tenant_context_for_redeem(city_id: str) -> None:
    """Define g.tenant_context + search_path para o schema do município (resgate pelo índice public)."""
    from flask import g

    from app.models.city import City
    from app.utils.tenant_middleware import TenantContext, city_id_to_schema_name, set_search_path

    city = City.query.get(city_id)
    if not city:
        raise ValueError("município não encontrado")
    ctx = TenantContext()
    ctx.city_id = str(city_id)
    ctx.city_slug = city.slug
    ctx.schema = city_id_to_schema_name(str(city_id))
    ctx.has_tenant_context = True
    g.tenant_context = ctx
    set_search_path(ctx.schema)


def user_scope_persisted(pack: MobileOfflinePackCode) -> Dict[str, Any]:
    d = dict(pack.scope_json or {})
    d.pop("_resolved", None)
    return d


def resolve_school_ids(city_id: str, scope: Dict[str, Any]) -> List[str]:
    typ = scope.get("type")
    if typ == "municipality":
        return [
            s.id
            for s in School.query.filter_by(city_id=city_id).order_by(School.name.asc()).all()
        ]
    if typ == "custom":
        raw_ids = scope.get("school_ids")
        if raw_ids:
            want = list({str(x) for x in raw_ids})
            schools = School.query.filter(
                School.id.in_(want), School.city_id == city_id
            ).all()
            if len(schools) != len(want):
                raise ValueError(
                    "uma ou mais escolas não existem ou não pertencem a este município"
                )
            return [s.id for s in schools]
        return [
            s.id
            for s in School.query.filter_by(city_id=city_id).order_by(School.name.asc()).all()
        ]
    raise ValueError('scope.type deve ser "municipality" ou "custom"')


def _optional_id_set(key: str, scope: Dict[str, Any]) -> Optional[Set[str]]:
    raw = scope.get(key)
    if not raw:
        return None
    return {str(x) for x in raw}


def collect_filtered_scope(
    school_ids: List[str],
    test_ids: Optional[Set[str]],
    class_ids: Optional[Set[str]],
    student_ids: Optional[Set[str]],
) -> Tuple[Dict[str, Test], List[Tuple[str, str]]]:
    """Agrega provas e vínculos aluno–prova conforme filtros."""
    all_tests: Dict[str, Test] = {}
    links_out: List[Tuple[str, str]] = []
    seen: Set[Tuple[str, str]] = set()

    for sch_id in school_ids:
        try:
            _, tests_map, school_links = collect_school_scope(sch_id)
        except ValueError:
            continue
        for stu_id, tid in school_links:
            if test_ids and tid not in test_ids:
                continue
            stu = Student.query.get(stu_id)
            if not stu or stu.school_id != sch_id:
                continue
            if class_ids:
                cid = str(stu.class_id) if stu.class_id else None
                if not cid or cid not in class_ids:
                    continue
            if student_ids and stu_id not in student_ids:
                continue
            key = (stu_id, tid)
            if key in seen:
                continue
            seen.add(key)
            links_out.append(key)
            t = tests_map.get(tid)
            if t:
                all_tests[tid] = t

    return all_tests, links_out


def _ensure_pack_bundle_versions(
    pack: MobileOfflinePackCode, school_ids_for_bundle: Set[str]
) -> Tuple[Dict[str, int], datetime]:
    """
    Cria/atualiza mobile_sync_bundle_generation por escola afetada (uma vez por pacote)
    e grava versões em scope_json._resolved.
    """
    scope = dict(pack.scope_json or {})
    internal = dict(scope.get("_resolved") or {})
    existing = internal.get("sync_bundle_version_by_school")
    if isinstance(existing, dict) and existing:
        raw_min = internal.get("bundle_valid_until_min")
        if raw_min:
            valid_min = _parse_iso_naive(raw_min)
        else:
            valid_min = datetime.utcnow()
        # normaliza chaves para str
        versions = {str(k): int(v) for k, v in existing.items()}
        return versions, valid_min

    versions: Dict[str, int] = {}
    min_valid: Optional[datetime] = None
    for sch_id in sorted(school_ids_for_bundle):
        v, valid_until, _ = ensure_bundle_generation(sch_id, None, True, 1)
        versions[str(sch_id)] = int(v)
        if min_valid is None or valid_until < min_valid:
            min_valid = valid_until

    if not min_valid:
        min_valid = datetime.utcnow()

    internal["sync_bundle_version_by_school"] = versions
    internal["bundle_valid_until_min"] = min_valid.isoformat() + "Z"
    scope["_resolved"] = internal
    pack.scope_json = scope
    flag_modified(pack, "scope_json")
    db.session.flush()
    return versions, min_valid


def _parse_iso_naive(raw: str) -> datetime:
    s = raw.rstrip("Z")
    if len(s) >= 26 and s[23] in "+-":
        s = s[:23]
    return datetime.fromisoformat(s)


def _serialize_student_row(s: Student) -> Dict[str, Any]:
    u = User.query.get(s.user_id) if s.user_id else None
    return {
        "id": s.id,
        "name": s.name,
        "registration": s.registration,
        "email": u.email if u else None,
        "user_id": s.user_id,
        "password_hash": u.password_hash if u else None,
        "class_id": str(s.class_id) if s.class_id else None,
        "grade_id": str(s.grade_id) if s.grade_id else None,
        "school_id": s.school_id,
    }


def register_offline_pack(
    *,
    city_id: str,
    created_by_user_id: str,
    scope: Dict[str, Any],
    ttl_hours: int,
    max_redemptions: int,
) -> Tuple[str, MobileOfflinePackCode]:
    """
    Gera código único, persiste hash e escopo. Retorna (código formatado, modelo).
    """
    if ttl_hours < 1 or ttl_hours > 24 * 14:
        raise ValueError("ttl_hours deve estar entre 1 e 336")
    if max_redemptions < 1 or max_redemptions > 10_000:
        raise ValueError("max_redemptions inválido")

    resolve_school_ids(city_id, scope)

    plain = None
    digest = None
    for _ in range(24):
        candidate = generate_activation_code()
        norm = "".join(c for c in candidate if c in _CODE_ALPHABET)
        if len(norm) != 12:
            continue
        h = hash_code(norm)
        if MobileOfflinePackCode.query.filter_by(code_hash=h).first():
            continue
        if MobileOfflinePackRegistry.query.filter_by(code_hash=h).first():
            continue
        plain = norm
        digest = h
        break
    if not plain or not digest:
        raise RuntimeError("não foi possível gerar código único; tente novamente")

    expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
    row = MobileOfflinePackCode(
        code_hash=digest,
        scope_json=dict(scope),
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
        max_redemptions=max_redemptions,
    )
    db.session.add(row)
    db.session.flush()
    db.session.add(
        MobileOfflinePackRegistry(
            code_hash=digest,
            city_id=city_id,
            pack_id=row.id,
        )
    )
    return format_code(plain), row


def _count_devices(pack_id) -> int:
    return MobileOfflinePackRedeemDevice.query.filter_by(pack_id=pack_id).count()


def _reserve_device_slot(pack: MobileOfflinePackCode, device_id: str) -> None:
    existing = MobileOfflinePackRedeemDevice.query.filter_by(
        pack_id=pack.id, device_id=device_id
    ).first()
    if existing:
        return
    if _count_devices(pack.id) >= pack.max_redemptions:
        raise PermissionError(
            "limite de dispositivos para este código foi atingido"
        )
    db.session.add(
        MobileOfflinePackRedeemDevice(pack_id=pack.id, device_id=device_id)
    )
    db.session.flush()


def redeem_offline_pack_page(
    *,
    pack: MobileOfflinePackCode,
    device_id: str,
    page: int,
    page_size: int,
    city_id: str,
) -> Dict[str, Any]:
    """Monta uma página do payload de download (alunos paginados; meta completa na pág. 1)."""
    if page < 1 or page_size < 1 or page_size > 200:
        raise ValueError("page >= 1 e 1 <= page_size <= 200")

    now = datetime.utcnow()
    if pack.revoked_at:
        raise ValueError("código revogado")
    if pack.expires_at < now:
        raise ValueError("código expirado")

    user_sc = user_scope_persisted(pack)
    school_ids = resolve_school_ids(city_id, user_sc)
    test_ids = _optional_id_set("test_ids", user_sc)
    class_ids = _optional_id_set("class_ids", user_sc)
    student_ids = _optional_id_set("student_ids", user_sc)

    tests_map, links = collect_filtered_scope(
        school_ids, test_ids, class_ids, student_ids
    )
    student_keys = sorted({sid for sid, _ in links})
    schools_touched: Set[str] = set()
    for sid, _ in links:
        stu = Student.query.get(sid)
        if stu and stu.school_id:
            schools_touched.add(stu.school_id)
    if not schools_touched and school_ids:
        schools_touched = set(school_ids)

    if page > 1:
        if not MobileOfflinePackRedeemDevice.query.filter_by(
            pack_id=pack.id, device_id=device_id
        ).first():
            raise ValueError(
                "baixe a página 1 deste código neste dispositivo antes das demais páginas"
            )

    versions, valid_min = _ensure_pack_bundle_versions(pack, schools_touched)

    if page == 1:
        _reserve_device_slot(pack, device_id)

    if student_keys:
        eligible_query = Student.query.filter(Student.id.in_(student_keys))
    else:
        eligible_query = Student.query.filter(sa_false())
    eligible_query = eligible_query.order_by(
        Student.school_id.asc(), Student.name.asc()
    )
    total_students = eligible_query.count()
    total_pages = max(1, (total_students + page_size - 1) // page_size)
    rows = eligible_query.offset((page - 1) * page_size).limit(page_size).all()
    students_payload = [_serialize_student_row(s) for s in rows]

    tests_payload, content_versions, questions_by_test = build_tests_questions_payload(
        tests_map
    )
    links_out = [{"student_id": a, "test_id": b} for a, b in links]

    include_full = page == 1
    sync_single: Optional[int] = None
    if len(versions) == 1:
        sync_single = int(next(iter(versions.values())))

    body: Dict[str, Any] = {
        "api_contract_version": "1.0",
        "city_id": city_id,
        "offline_pack_id": str(pack.id),
        "bundle_valid_until": valid_min.isoformat() + "Z",
        "sync_bundle_version_by_school": versions,
        "sync_bundle_version": sync_single,
        "page": page,
        "page_size": page_size,
        "total_students": total_students,
        "total_pages": total_pages,
        "unchanged": False,
        "students": students_payload,
        "student_test_links": links_out if include_full else [],
        "tests": tests_payload if include_full else {},
        "questions_by_test": questions_by_test if include_full else {},
        "test_content_version": content_versions if include_full else {},
    }
    if not include_full:
        body["includes_full_payload"] = False
    return body


def find_pack_by_code_normalized(normalized: str) -> MobileOfflinePackCode:
    h = hash_code(normalized)
    row = MobileOfflinePackCode.query.filter_by(code_hash=h).first()
    if not row:
        raise ValueError("código não encontrado")
    return row
