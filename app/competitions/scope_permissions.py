# -*- coding: utf-8 -*-
"""
Permissões de escopo por role na criação/edição de competições.

Regras:
- Admin: todos os escopos (individual = sistema todo).
- Tec adm: apenas escopo do seu município (município, escola, turma dentro do município).
- Diretor/Coordenador: apenas da sua escola (escola, turma da escola).
- Professor: apenas suas turmas (turma entre as que leciona).
Escopo "série" foi removido.
"""
from typing import List, Set, Any, Dict

from app.competitions.constants import SCOPE_OPTIONS
from app.permissions.roles import Roles
from app.permissions.utils import (
    get_teacher_classes,
    get_manager_school,
)


def get_allowed_competition_scopes(user: Dict[str, Any]) -> List[str]:
    """
    Retorna a lista de valores de escopo que o usuário pode usar ao criar/editar competição.
    O frontend deve exibir apenas essas opções no select de escopo.
    """
    if not user:
        return []
    role = Roles.normalize(user.get("role", ""))
    if role == Roles.ADMIN:
        return list(SCOPE_OPTIONS)
    if role == Roles.TECADM:
        return ["individual", "turma", "escola", "municipio"]
    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        return ["individual", "turma", "escola"]
    if role == Roles.PROFESSOR:
        return ["individual", "turma"]
    return ["individual"]


def _norm_set(ids: Any) -> Set[str]:
    if ids is None:
        return set()
    if isinstance(ids, (list, tuple)):
        return {str(x).strip().lower() for x in ids if x is not None}
    return {str(ids).strip().lower()} if ids else set()


def validate_scope_and_filter_for_user(
    scope: str, scope_filter: Dict[str, Any], user: Dict[str, Any]
) -> None:
    """
    Valida se o par (scope, scope_filter) é permitido para o usuário conforme seu role.
    Levanta ValueError com mensagem clara se não for permitido.
    """
    scope = (scope or "individual").strip().lower()
    if scope not in SCOPE_OPTIONS:
        raise ValueError(f"Escopo inválido: {scope}")

    allowed = get_allowed_competition_scopes(user)
    if scope not in allowed:
        raise ValueError(
            f"Seu perfil não permite usar o escopo '{scope}'. "
            f"Escopos permitidos para você: {', '.join(allowed)}."
        )

    if scope == "individual":
        return

    sf = scope_filter or {}
    role = Roles.normalize(user.get("role", ""))

    if role == Roles.ADMIN:
        return

    if role == Roles.TECADM:
        city_id_raw = (user.get("city_id") or user.get("tenant_id") or "").strip()
        city_id = city_id_raw.lower()
        if not city_id_raw:
            raise ValueError(
                "Usuário tecadm sem município vinculado. Não é possível definir escopo por município, escola ou turma."
            )
        if scope == "municipio":
            ids = _norm_set(sf.get("municipality_ids") or sf.get("city_ids"))
            if not ids or ids - {city_id}:
                raise ValueError(
                    "Tec adm só pode criar competição para o seu próprio município."
                )
            return
        if scope == "escola":
            from app.models.school import School

            school_ids = _norm_set(sf.get("school_ids"))
            if not school_ids:
                raise ValueError("Informe ao menos uma escola em scope_filter.")
            schools = School.query.filter(School.id.in_(list(school_ids))).all()
            for s in schools:
                cid = str(getattr(s, "city_id", None) or "").strip().lower()
                if cid != city_id:
                    raise ValueError(
                        "Tec adm só pode selecionar escolas do seu município."
                    )
            return
        if scope == "turma":
            from app.models.studentClass import Class
            from app.models.school import School

            class_ids = _norm_set(sf.get("class_ids"))
            if not class_ids:
                raise ValueError("Informe ao menos uma turma em scope_filter.")
            classes = Class.query.filter(Class.id.in_(list(class_ids))).all()
            for c in classes:
                sch = getattr(c, "school", None)
                if not sch:
                    raise ValueError("Turma sem escola vinculada.")
                cid = (getattr(sch, "city_id", None) or "").strip().lower()
                if cid != city_id:
                    raise ValueError(
                        "Tec adm só pode selecionar turmas de escolas do seu município."
                    )
            return

    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        school_id = get_manager_school(user["id"])
        school_id_str = (school_id or "").strip().lower()
        if not school_id_str:
            raise ValueError(
                "Diretor/Coordenador sem escola vinculada. Não é possível usar escopo por escola ou turma."
            )
        if scope == "escola":
            school_ids = _norm_set(sf.get("school_ids"))
            if not school_ids or school_ids - {school_id_str}:
                raise ValueError(
                    "Diretor/Coordenador só pode criar competição para a sua própria escola."
                )
            return
        if scope == "turma":
            from app.models.studentClass import Class

            class_ids = _norm_set(sf.get("class_ids"))
            if not class_ids:
                raise ValueError("Informe ao menos uma turma em scope_filter.")
            classes = Class.query.filter(Class.id.in_(list(class_ids))).all()
            for cl in classes:
                cl_school = str(getattr(cl, "school_id", "") or "").strip().lower()
                if cl_school != school_id_str:
                    raise ValueError(
                        "Diretor/Coordenador só pode selecionar turmas da sua escola."
                    )
            return
    if role == Roles.PROFESSOR:
        if scope != "turma":
            return
        teacher_class_ids = get_teacher_classes(user["id"])
        allowed_class_ids = {str(x).strip().lower() for x in teacher_class_ids}
        class_ids = _norm_set(sf.get("class_ids"))
        if not class_ids:
            raise ValueError("Informe ao menos uma turma em scope_filter.")
        if class_ids - allowed_class_ids:
            raise ValueError(
                "Professor só pode criar competição para turmas em que você leciona."
            )
