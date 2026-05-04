from flask import Blueprint, request, jsonify, make_response
from app.play_tv.models import (
    PlayTvVideo,
    PlayTvVideoSchool,
    PlayTvVideoClass,
    PlayTvVideoResource,
)
from app.models.school import School
from app.models.grades import Grade
from app.models.subject import Subject
from app.models.city import City
from app.models.studentClass import Class
from app.models.manager import Manager
from app.models.teacher import Teacher
from app.models.schoolTeacher import SchoolTeacher
from app.models.student import Student
from app.decorators.role_required import role_required, get_current_user_from_token
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import exists, and_, or_
from sqlalchemy.orm import joinedload
from app import db
from app.utils.tenant_middleware import get_current_tenant_context, set_search_path
from app.services.storage.minio_service import MinIOService
import logging
import uuid
import os
from urllib.parse import urlparse
from datetime import timedelta
from werkzeug.utils import secure_filename

bp = Blueprint('playtv', __name__, url_prefix='/play-tv')

_MAX_RESOURCE_UPLOAD_BYTES = int(os.getenv('PLAY_TV_MAX_UPLOAD_MB', '50')) * 1024 * 1024


@bp.before_request
def handle_options():
    if request.method == 'OPTIONS':
        response = make_response()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        return response


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    logging.error(f"Database error: {str(error)}")
    return jsonify({"erro": "Erro no banco de dados", "detalhes": str(error)}), 500


@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(error)}), 400


@bp.errorhandler(Exception)
def handle_generic_error(error):
    logging.error(f"Unexpected error: {str(error)}", exc_info=True)
    return jsonify({"erro": "Erro interno do servidor", "detalhes": str(error)}), 500


def _play_tv_tenant_error():
    return jsonify({
        "erro": "Play TV requer contexto de município. Administradores devem enviar X-City-ID ou X-City-Slug."
    }), 400


def _require_play_tv_tenant():
    ctx = get_current_tenant_context()
    if not ctx or not getattr(ctx, "has_tenant_context", False) or ctx.schema == "public":
        return None, _play_tv_tenant_error()
    return ctx, None


def _serialize_resources(video):
    items = []
    for r in sorted(video.resources, key=lambda x: (x.sort_order or 0, x.id or "")):
        item = {
            "id": r.id,
            "type": r.resource_type,
            "title": r.title,
            "sort_order": r.sort_order or 0,
        }
        if r.resource_type == "link":
            item["url"] = r.url
        elif r.resource_type == "file":
            item["file_name"] = r.original_filename
            item["mime_type"] = r.content_type
            item["size_bytes"] = r.size_bytes
        items.append(item)
    return items


def _video_payload(video, *, schools=None, classes=None):
    sch = schools
    if sch is None:
        sch = [{"id": vs.school.id, "name": vs.school.name} for vs in video.video_schools]
    cls = classes
    if cls is None:
        cls = [{"id": vc.class_.id, "name": vc.class_.name} for vc in video.video_classes]
    return {
        "id": video.id,
        "url": video.url,
        "title": video.title,
        "entire_municipality": bool(video.entire_municipality),
        "schools": sch,
        "classes": cls,
        "grade": {"id": str(video.grade.id), "name": video.grade.name} if video.grade else None,
        "subject": {"id": video.subject.id, "name": video.subject.name} if video.subject else None,
        "resources": _serialize_resources(video),
        "created_at": video.created_at.isoformat() if video.created_at else None,
        "created_by": {
            "id": video.creator.id,
            "name": video.creator.name,
        } if video.creator else None,
    }


def _user_can_use_entire_municipality(user):
    if not user:
        return False
    return user.get("role") in ("admin", "tecadm")


def _delete_file_resources_from_minio(video):
    minio = MinIOService()
    bucket = minio.BUCKETS.get("PLAY_TV_RESOURCES")
    for r in video.resources:
        if r.resource_type == "file" and r.minio_object_name:
            b = r.minio_bucket or bucket
            minio.delete_file(b, r.minio_object_name)


@bp.route('/videos', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def list_videos():
    try:
        _, err = _require_play_tv_tenant()
        if err:
            return err

        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        scope = or_(
            PlayTvVideo.entire_municipality.is_(True),
            exists().where(PlayTvVideoSchool.video_id == PlayTvVideo.id),
        )
        query = (
            PlayTvVideo.query.options(
                joinedload(PlayTvVideo.grade),
                joinedload(PlayTvVideo.subject),
                joinedload(PlayTvVideo.creator),
                joinedload(PlayTvVideo.video_schools).joinedload(PlayTvVideoSchool.school),
                joinedload(PlayTvVideo.video_classes).joinedload(PlayTvVideoClass.class_),
                joinedload(PlayTvVideo.resources),
            )
            .join(Grade, PlayTvVideo.grade_id == Grade.id)
            .join(Subject, PlayTvVideo.subject_id == Subject.id)
            .filter(scope)
        )

        state = request.args.get('state')
        municipality = request.args.get('municipality') or request.args.get('municipality_id')
        school = request.args.get('school') or request.args.get('school_id')
        grade = request.args.get('grade') or request.args.get('grade_id')
        subject = request.args.get('subject') or request.args.get('subject_id')
        class_id = request.args.get('class') or request.args.get('class_id')

        ctx = get_current_tenant_context()
        tenant_city = City.query.get(ctx.city_id) if ctx and ctx.city_id else None

        if state:
            if tenant_city and tenant_city.state:
                if state.lower() not in (tenant_city.state or "").lower():
                    return jsonify([]), 200

        if municipality:
            city_obj = City.query.get(municipality)
            if city_obj and tenant_city and str(city_obj.id) != str(tenant_city.id):
                return jsonify([]), 200
            if not city_obj and tenant_city and tenant_city.name:
                if municipality.lower() not in (tenant_city.name or "").lower():
                    return jsonify([]), 200

        if school:
            school_obj = School.query.get(school)
            if school_obj:
                query = query.filter(
                    or_(
                        PlayTvVideo.entire_municipality.is_(True),
                        exists().where(
                            and_(
                                PlayTvVideoSchool.video_id == PlayTvVideo.id,
                                PlayTvVideoSchool.school_id == school_obj.id,
                            )
                        ),
                    )
                )
            else:
                name_subq = (
                    db.session.query(PlayTvVideoSchool.video_id)
                    .join(School, PlayTvVideoSchool.school_id == School.id)
                    .filter(School.name.ilike(f"%{school}%"))
                )
                query = query.filter(
                    or_(
                        PlayTvVideo.entire_municipality.is_(True),
                        PlayTvVideo.id.in_(name_subq),
                    )
                )

        if grade:
            grade_obj = Grade.query.get(grade)
            if grade_obj:
                query = query.filter(Grade.id == grade_obj.id)
            else:
                query = query.filter(Grade.name.ilike(f"%{grade}%"))

        if subject:
            subject_obj = Subject.query.get(subject)
            if subject_obj:
                query = query.filter(Subject.id == subject_obj.id)
            else:
                query = query.filter(Subject.name.ilike(f"%{subject}%"))

        if class_id:
            class_obj = Class.query.get(class_id)
            if class_obj:
                query = query.filter(
                    or_(
                        ~exists().where(PlayTvVideoClass.video_id == PlayTvVideo.id),
                        exists().where(
                            and_(
                                PlayTvVideoClass.video_id == PlayTvVideo.id,
                                PlayTvVideoClass.class_id == class_obj.id,
                            )
                        ),
                    )
                )

        if user['role'] == 'tecadm':
            city_id = user.get('tenant_id') or user.get('city_id')
            if city_id and tenant_city and str(city_id) != str(tenant_city.id):
                return jsonify([]), 200
        elif user['role'] in ['diretor', 'coordenador']:
            manager = Manager.query.filter_by(user_id=user['id']).first()
            if manager and manager.school_id:
                query = query.filter(
                    or_(
                        PlayTvVideo.entire_municipality.is_(True),
                        exists().where(
                            and_(
                                PlayTvVideoSchool.video_id == PlayTvVideo.id,
                                PlayTvVideoSchool.school_id == manager.school_id,
                            )
                        ),
                    )
                )
        elif user['role'] == 'professor':
            teacher = Teacher.query.filter_by(user_id=user['id']).first()
            if teacher:
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                school_ids = [ts.school_id for ts in teacher_schools]
                if school_ids:
                    query = query.filter(
                        or_(
                            PlayTvVideo.entire_municipality.is_(True),
                            exists().where(
                                and_(
                                    PlayTvVideoSchool.video_id == PlayTvVideo.id,
                                    PlayTvVideoSchool.school_id.in_(school_ids),
                                )
                            ),
                        )
                    )
        elif user['role'] == 'aluno':
            student = Student.query.filter_by(user_id=user['id']).first()
            if student:
                query = query.filter(PlayTvVideo.grade_id == student.grade_id)
                query = query.filter(
                    or_(
                        PlayTvVideo.entire_municipality.is_(True),
                        exists().where(
                            and_(
                                PlayTvVideoSchool.video_id == PlayTvVideo.id,
                                PlayTvVideoSchool.school_id == student.school_id,
                            )
                        ),
                    )
                )
                query = query.filter(
                    or_(
                        ~exists().where(PlayTvVideoClass.video_id == PlayTvVideo.id),
                        exists().where(
                            and_(
                                PlayTvVideoClass.video_id == PlayTvVideo.id,
                                PlayTvVideoClass.class_id == student.class_id,
                            )
                        ),
                    )
                )

        videos = query.distinct().all()
        result = [_video_payload(v) for v in videos]
        return jsonify(result), 200

    except Exception as e:
        logging.error(f"Erro ao listar vídeos: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao listar vídeos", "detalhes": str(e)}), 500


def _parse_and_validate_resources(data, *, allow_file_type=False):
    """Valida lista resources do JSON; arquivos devem ser enviados via multipart."""
    raw = data.get("resources")
    if raw is None:
        return [], None
    if not isinstance(raw, list):
        return None, (jsonify({"erro": "resources deve ser uma lista"}), 400)
    out = []
    for idx, res in enumerate(raw):
        if not isinstance(res, dict):
            return None, (jsonify({"erro": f"Item {idx} de resources inválido"}), 400)
        rtype = res.get("type")
        title = (res.get("title") or "").strip()
        if not title:
            return None, (jsonify({"erro": f"title obrigatório em resources[{idx}]"}), 400)
        if len(title) > 200:
            return None, (jsonify({"erro": f"título do recurso muito longo em [{idx}]"}), 400)
        sort_order = res.get("sort_order", idx)
        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            sort_order = idx
        if rtype == "link":
            url = (res.get("url") or "").strip()
            if not url:
                return None, (jsonify({"erro": f"url obrigatória para link em resources[{idx}]"}), 400)
            parsed = urlparse(url)
            if not parsed.scheme or parsed.scheme not in ('http', 'https'):
                return None, (jsonify({"erro": f"URL inválida em resources[{idx}]"}), 400)
            out.append({"type": "link", "title": title, "url": url, "sort_order": sort_order})
        elif rtype == "file":
            if not allow_file_type:
                return None, (
                    jsonify({"erro": "Para anexar arquivo use POST /play-tv/videos/<id>/resources/file"}),
                    400,
                )
        else:
            return None, (jsonify({"erro": f"type inválido em resources[{idx}]"}), 400)
    return out, None


def _parse_link_resources_for_put(raw):
    """
    Para PUT: somente links. Cada item: id (opcional), type 'link', title, url, sort_order opcional.
    """
    if raw is None:
        return None, None
    if not isinstance(raw, list):
        return None, (jsonify({"erro": "resources deve ser uma lista"}), 400)
    out = []
    for idx, res in enumerate(raw):
        if not isinstance(res, dict):
            return None, (jsonify({"erro": f"Item {idx} de resources inválido"}), 400)
        if res.get("type") != "link":
            return None, (
                jsonify({
                    "erro": f"resources[{idx}]: no PUT use apenas type 'link'. "
                            f"Anexos: POST .../resources/file ou delete do recurso."
                }),
                400,
            )
        title = (res.get("title") or "").strip()
        if not title:
            return None, (jsonify({"erro": f"title obrigatório em resources[{idx}]"}), 400)
        if len(title) > 200:
            return None, (jsonify({"erro": f"título do recurso muito longo em [{idx}]"}), 400)
        url = (res.get("url") or "").strip()
        if not url:
            return None, (jsonify({"erro": f"url obrigatória em resources[{idx}]"}), 400)
        parsed = urlparse(url)
        if not parsed.scheme or parsed.scheme not in ("http", "https"):
            return None, (jsonify({"erro": f"URL inválida em resources[{idx}]"}), 400)
        sort_order = res.get("sort_order", idx)
        try:
            sort_order = int(sort_order)
        except (TypeError, ValueError):
            sort_order = idx
        rid = res.get("id")
        if rid is not None:
            rid = str(rid).strip() or None
        out.append({"id": rid, "title": title, "url": url, "sort_order": sort_order})
    return out, None


@bp.route('/videos', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def create_video():
    try:
        _, err = _require_play_tv_tenant()
        if err:
            return err

        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400

        for field in ("url", "grade", "subject"):
            if field not in data:
                return jsonify({"erro": f"Campo obrigatório ausente: {field}"}), 400

        entire_municipality = bool(data.get("entire_municipality", False))
        schools_ids = data.get("schools")

        if entire_municipality:
            schools_ids = schools_ids or []
            if not isinstance(schools_ids, list):
                return jsonify({"erro": "schools deve ser uma lista"}), 400
        else:
            if "schools" not in data:
                return jsonify({"erro": "Campo obrigatório ausente: schools"}), 400
            schools_ids = data["schools"]
            if not isinstance(schools_ids, list) or len(schools_ids) == 0:
                return jsonify({"erro": "Pelo menos uma escola deve ser selecionada"}), 400

        url = data["url"].strip()
        if not url:
            return jsonify({"erro": "URL não pode estar vazia"}), 400
        parsed_url = urlparse(url)
        if not parsed_url.scheme or parsed_url.scheme not in ['http', 'https']:
            return jsonify({"erro": "URL inválida. Deve começar com http:// ou https://"}), 400

        title = data.get("title")
        if title and len(title) > 100:
            return jsonify({"erro": "Título não pode exceder 100 caracteres"}), 400

        resources_plan, res_err = _parse_and_validate_resources(data, allow_file_type=False)
        if res_err:
            return res_err

        grade_id = data["grade"]
        grade = Grade.query.get(grade_id)
        if not grade:
            return jsonify({"erro": "Série não encontrada"}), 404

        subject_id = data["subject"]
        subject = Subject.query.get(subject_id)
        if not subject:
            return jsonify({"erro": "Disciplina não encontrada"}), 404

        classes_ids = data.get("classes", [])
        classes = []
        if classes_ids:
            if not isinstance(classes_ids, list):
                return jsonify({"erro": "Classes deve ser uma lista"}), 400
            classes = Class.query.filter(Class.id.in_(classes_ids)).all()
            if len(classes) != len(classes_ids):
                return jsonify({"erro": "Uma ou mais classes não encontradas"}), 404

        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        ctx = get_current_tenant_context()
        tenant_city_id = str(ctx.city_id) if ctx and ctx.city_id else None

        if entire_municipality and not _user_can_use_entire_municipality(current_user):
            return jsonify({"erro": "Apenas administrador ou tecadm podem publicar para o município inteiro"}), 403

        schools = []
        if schools_ids:
            schools = School.query.filter(School.id.in_(schools_ids)).all()
            if len(schools) != len(schools_ids):
                return jsonify({"erro": "Uma ou mais escolas não encontradas"}), 404

        if classes:
            if entire_municipality:
                for c in classes:
                    sch = School.query.get(c.school_id)
                    if tenant_city_id and sch and str(sch.city_id) != tenant_city_id:
                        return jsonify({"erro": "Todas as turmas devem ser de escolas deste município"}), 400
            else:
                class_school_ids = {c.school_id for c in classes}
                school_ids_set = {s.id for s in schools}
                if not school_ids_set or not class_school_ids.issubset(school_ids_set):
                    return jsonify({"erro": "Todas as classes devem pertencer às escolas selecionadas"}), 400

        if current_user['role'] == 'tecadm':
            city_id = current_user.get('tenant_id') or current_user.get('city_id')
            if city_id and tenant_city_id and str(city_id) != tenant_city_id:
                return jsonify({"erro": "Contexto de município inconsistente com seu perfil"}), 403
            if city_id:
                for school in schools:
                    if school.city_id != city_id:
                        return jsonify({
                            "erro": f"Você não tem permissão para criar vídeos na escola {school.name}",
                        }), 403
        elif current_user['role'] in ['diretor', 'coordenador']:
            manager = Manager.query.filter_by(user_id=current_user['id']).first()
            if manager and manager.school_id:
                for school in schools:
                    if school.id != manager.school_id:
                        return jsonify({
                            "erro": f"Você não tem permissão para criar vídeos na escola {school.name}",
                        }), 403
        elif current_user['role'] == 'professor':
            teacher = Teacher.query.filter_by(user_id=current_user['id']).first()
            if teacher:
                teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
                allowed_school_ids = [ts.school_id for ts in teacher_schools]
                for school in schools:
                    if school.id not in allowed_school_ids:
                        return jsonify({
                            "erro": f"Você não tem permissão para criar vídeos na escola {school.name}",
                        }), 403

        new_video = PlayTvVideo(
            url=url,
            title=title,
            grade_id=grade_id,
            subject_id=subject_id,
            created_by=current_user['id'],
            entire_municipality=entire_municipality,
        )
        db.session.add(new_video)
        db.session.flush()

        for school in schools:
            db.session.add(PlayTvVideoSchool(video_id=new_video.id, school_id=school.id))
        for class_obj in classes:
            db.session.add(PlayTvVideoClass(video_id=new_video.id, class_id=class_obj.id))

        for rp in resources_plan:
            db.session.add(PlayTvVideoResource(
                id=str(uuid.uuid4()),
                video_id=new_video.id,
                resource_type="link",
                title=rp["title"],
                url=rp["url"],
                sort_order=rp["sort_order"],
            ))

        video_id = new_video.id
        db.session.commit()

        # Após commit, a conexão pode voltar ao pool com search_path=public; o vídeo
        # está em city_*. Sem re-fixar o tenant, o reload falha com "row not present".
        reload_ctx = get_current_tenant_context()
        if reload_ctx and reload_ctx.schema and reload_ctx.schema != "public":
            set_search_path(reload_ctx.schema)

        video = (
            PlayTvVideo.query.options(
                joinedload(PlayTvVideo.grade),
                joinedload(PlayTvVideo.subject),
                joinedload(PlayTvVideo.resources),
                joinedload(PlayTvVideo.video_schools).joinedload(PlayTvVideoSchool.school),
                joinedload(PlayTvVideo.video_classes).joinedload(PlayTvVideoClass.class_),
            )
            .filter_by(id=video_id)
            .first()
        )
        if not video:
            logging.error("Play TV: vídeo %s não encontrado após commit (verifique search_path / schema)", video_id)
            return jsonify({
                "erro": "Vídeo criado mas não foi possível recarregar os dados",
                "detalhes": "Confirme se as tabelas play_tv existem no schema do município",
            }), 500

        return jsonify({
            "mensagem": "Vídeo criado com sucesso!",
            "video": _video_payload(
                video,
                schools=[{"id": s.id, "name": s.name} for s in schools],
                classes=[{"id": c.id, "name": c.name} for c in classes] if classes else [],
            ),
        }), 201

    except SQLAlchemyError as e:
        logging.error(f"Erro no banco de dados: {str(e)}")
        db.session.rollback()
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except IntegrityError as e:
        logging.error(f"Erro de integridade: {str(e)}")
        db.session.rollback()
        return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao criar vídeo: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({"erro": "Erro ao criar vídeo", "detalhes": str(e)}), 500


def _get_video_for_user_or_404(video_id):
    video = PlayTvVideo.query.options(
        joinedload(PlayTvVideo.grade),
        joinedload(PlayTvVideo.subject),
        joinedload(PlayTvVideo.creator),
        joinedload(PlayTvVideo.resources),
        joinedload(PlayTvVideo.video_schools).joinedload(PlayTvVideoSchool.school),
        joinedload(PlayTvVideo.video_classes).joinedload(PlayTvVideoClass.class_),
    ).get(video_id)
    return video


def _user_may_edit_video(user, video):
    """Quem pode alterar o vídeo (não inclui DELETE do vídeo — só admin)."""
    if not user or not video:
        return False
    if (user.get("role") or "").lower() == "aluno":
        return False
    if not _user_may_access_video(user, video):
        return False
    role = (user.get("role") or "").lower()
    if video.entire_municipality and role not in ("admin", "tecadm"):
        return False
    return True


def _validate_editor_scope_for_schools(current_user, schools, tenant_city_id):
    """Mesmas regras de escopo de escola do POST /videos."""
    if current_user['role'] == 'tecadm':
        city_id = current_user.get('tenant_id') or current_user.get('city_id')
        if city_id and tenant_city_id and str(city_id) != tenant_city_id:
            return jsonify({"erro": "Contexto de município inconsistente com seu perfil"}), 403
        if city_id:
            for school in schools:
                if school.city_id != city_id:
                    return jsonify({
                        "erro": f"Você não tem permissão para usar a escola {school.name}",
                    }), 403
    elif current_user['role'] in ['diretor', 'coordenador']:
        manager = Manager.query.filter_by(user_id=current_user['id']).first()
        if manager and manager.school_id:
            for school in schools:
                if school.id != manager.school_id:
                    return jsonify({
                        "erro": f"Você não tem permissão para usar a escola {school.name}",
                    }), 403
    elif current_user['role'] == 'professor':
        teacher = Teacher.query.filter_by(user_id=current_user['id']).first()
        if teacher:
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            allowed_school_ids = [ts.school_id for ts in teacher_schools]
            for school in schools:
                if school.id not in allowed_school_ids:
                    return jsonify({
                        "erro": f"Você não tem permissão para usar a escola {school.name}",
                    }), 403
    return None


def _sync_link_resources_for_video(video_id, link_items):
    """
    link_items: lista de dicts com keys id (opcional), title, url, sort_order.
    Mantém recursos tipo 'file'. Substitui só os links pela lista final.
    """
    existing_links = (
        PlayTvVideoResource.query.filter_by(video_id=video_id, resource_type="link").all()
    )
    by_id = {r.id: r for r in existing_links}
    incoming_ids = set()
    for idx, item in enumerate(link_items):
        rid = item.get("id")
        title = item["title"]
        url = item["url"]
        sort_order = item.get("sort_order", idx)
        if rid:
            incoming_ids.add(rid)
            row = by_id.get(rid)
            if not row:
                raise ValueError(f"Recurso link id={rid} não encontrado neste vídeo")
            row.title = title
            row.url = url
            row.sort_order = sort_order
        else:
            db.session.add(PlayTvVideoResource(
                id=str(uuid.uuid4()),
                video_id=video_id,
                resource_type="link",
                title=title,
                url=url,
                sort_order=sort_order,
            ))
    for r in existing_links:
        if r.id not in incoming_ids:
            db.session.delete(r)


def _user_may_access_video(user, video):
    if not user or not video:
        return False
    video_school_ids = [vs.school_id for vs in video.video_schools]

    if user['role'] == 'tecadm':
        city_id = user.get('tenant_id') or user.get('city_id')
        if city_id:
            if video.entire_municipality:
                return True
            schools = School.query.filter(
                School.id.in_(video_school_ids), School.city_id == city_id,
            ).all()
            return bool(schools)
        return False
    if user['role'] in ['diretor', 'coordenador']:
        manager = Manager.query.filter_by(user_id=user['id']).first()
        if manager and manager.school_id:
            if video.entire_municipality:
                return True
            return manager.school_id in video_school_ids
        return False
    if user['role'] == 'professor':
        teacher = Teacher.query.filter_by(user_id=user['id']).first()
        if teacher:
            teacher_schools = SchoolTeacher.query.filter_by(teacher_id=teacher.id).all()
            allowed = [ts.school_id for ts in teacher_schools]
            if video.entire_municipality:
                return bool(allowed)
            return any(sid in allowed for sid in video_school_ids)
        return False
    if user['role'] == 'aluno':
        student = Student.query.filter_by(user_id=user['id']).first()
        if not student:
            return False
        if video.grade_id != student.grade_id:
            return False
        if not video.entire_municipality and student.school_id not in video_school_ids:
            return False
        class_ids = [vc.class_id for vc in video.video_classes]
        if class_ids and student.class_id not in class_ids:
            return False
        return True
    if user['role'] == 'admin':
        return True
    return False


@bp.route('/videos/<string:video_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def get_video(video_id):
    try:
        _, err = _require_play_tv_tenant()
        if err:
            return err

        video = _get_video_for_user_or_404(video_id)
        if not video:
            return jsonify({"erro": "Vídeo não encontrado"}), 404

        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não encontrado"}), 404

        if not _user_may_access_video(user, video):
            return jsonify({"erro": "Você não tem permissão para acessar este vídeo"}), 403

        return jsonify(_video_payload(video)), 200

    except Exception as e:
        logging.error(f"Erro ao buscar vídeo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao buscar vídeo", "detalhes": str(e)}), 500


@bp.route('/videos/<string:video_id>', methods=['PUT'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def update_video(video_id):
    """
    Atualização parcial: envie só os campos a alterar.

    - title, url, grade, subject, entire_municipality
    - schools, classes: quando enviados (ou ao mudar entire_municipality), as associações são recriadas
    - resources: somente links; lista completa desejada (com id para atualizar, sem id para criar;
      links omitidos são removidos). Anexos (file) não entram aqui — use POST/DELETE de arquivo.
    """
    try:
        _, err = _require_play_tv_tenant()
        if err:
            return err

        data = request.get_json()
        if not data:
            return jsonify({"erro": "Dados não fornecidos"}), 400

        video = PlayTvVideo.query.get(video_id)
        if not video:
            return jsonify({"erro": "Vídeo não encontrado"}), 404

        user = get_current_user_from_token()
        if not user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        if not _user_may_edit_video(user, video):
            return jsonify({"erro": "Você não tem permissão para editar este vídeo"}), 403

        ctx = get_current_tenant_context()
        tenant_city_id = str(ctx.city_id) if ctx and ctx.city_id else None

        if "entire_municipality" in data:
            em = bool(data["entire_municipality"])
            if em and not _user_can_use_entire_municipality(user):
                return jsonify({
                    "erro": "Apenas administrador ou tecadm podem definir envio ao município inteiro",
                }), 403
            video.entire_municipality = em

        if "url" in data:
            url = (data["url"] or "").strip()
            if not url:
                return jsonify({"erro": "URL não pode estar vazia"}), 400
            pu = urlparse(url)
            if not pu.scheme or pu.scheme not in ("http", "https"):
                return jsonify({"erro": "URL inválida. Use http:// ou https://"}), 400
            video.url = url

        if "title" in data:
            title = data["title"]
            if title is not None and len(str(title)) > 100:
                return jsonify({"erro": "Título não pode exceder 100 caracteres"}), 400
            video.title = title

        if "grade" in data:
            gid = data["grade"]
            if not Grade.query.get(gid):
                return jsonify({"erro": "Série não encontrada"}), 404
            video.grade_id = gid

        if "subject" in data:
            sid = data["subject"]
            if not Subject.query.get(sid):
                return jsonify({"erro": "Disciplina não encontrada"}), 404
            video.subject_id = sid

        if "schools" in data or "classes" in data or "entire_municipality" in data:
            if video.entire_municipality:
                if "schools" in data:
                    sraw = data["schools"]
                    if not isinstance(sraw, list):
                        return jsonify({"erro": "schools deve ser uma lista"}), 400
                    if len(sraw) > 0:
                        return jsonify({
                            "erro": "Com entire_municipality=true use schools: [] ou omita schools",
                        }), 400
                schools_ids = []
            elif "schools" in data:
                schools_ids = data["schools"]
                if not isinstance(schools_ids, list) or len(schools_ids) == 0:
                    return jsonify({"erro": "Pelo menos uma escola deve ser selecionada"}), 400
            else:
                schools_ids = [vs.school_id for vs in video.video_schools]

            if "classes" in data:
                classes_ids = data["classes"]
                if not isinstance(classes_ids, list):
                    return jsonify({"erro": "classes deve ser uma lista"}), 400
            else:
                classes_ids = [vc.class_id for vc in video.video_classes]

            if not video.entire_municipality and not schools_ids:
                return jsonify({"erro": "Informe ao menos uma escola"}), 400

            schools = []
            if schools_ids:
                schools = School.query.filter(School.id.in_(schools_ids)).all()
                if len(schools) != len(schools_ids):
                    return jsonify({"erro": "Uma ou mais escolas não encontradas"}), 404

            classes_objs = []
            if classes_ids:
                classes_objs = Class.query.filter(Class.id.in_(classes_ids)).all()
                if len(classes_objs) != len(classes_ids):
                    return jsonify({"erro": "Uma ou mais classes não encontradas"}), 404

            if classes_objs:
                if video.entire_municipality:
                    for c in classes_objs:
                        sch = School.query.get(c.school_id)
                        if tenant_city_id and sch and str(sch.city_id) != tenant_city_id:
                            return jsonify({
                                "erro": "Todas as turmas devem ser de escolas deste município",
                            }), 400
                else:
                    class_school_ids = {c.school_id for c in classes_objs}
                    school_ids_set = {s.id for s in schools}
                    if not school_ids_set or not class_school_ids.issubset(school_ids_set):
                        return jsonify({
                            "erro": "Todas as classes devem pertencer às escolas selecionadas",
                        }), 400

            scope_err = _validate_editor_scope_for_schools(user, schools, tenant_city_id)
            if scope_err:
                return scope_err

            PlayTvVideoSchool.query.filter_by(video_id=video.id).delete(synchronize_session=False)
            PlayTvVideoClass.query.filter_by(video_id=video.id).delete(synchronize_session=False)
            for s in schools:
                db.session.add(PlayTvVideoSchool(video_id=video.id, school_id=s.id))
            for c in classes_objs:
                db.session.add(PlayTvVideoClass(video_id=video.id, class_id=c.id))

        if "resources" in data:
            link_plan, res_err = _parse_link_resources_for_put(data["resources"])
            if res_err:
                return res_err
            try:
                _sync_link_resources_for_video(video.id, link_plan)
            except ValueError as ve:
                return jsonify({"erro": str(ve)}), 400

        vid = video.id
        db.session.commit()

        reload_ctx = get_current_tenant_context()
        if reload_ctx and reload_ctx.schema and reload_ctx.schema != "public":
            set_search_path(reload_ctx.schema)

        video_out = (
            PlayTvVideo.query.options(
                joinedload(PlayTvVideo.grade),
                joinedload(PlayTvVideo.subject),
                joinedload(PlayTvVideo.resources),
                joinedload(PlayTvVideo.video_schools).joinedload(PlayTvVideoSchool.school),
                joinedload(PlayTvVideo.video_classes).joinedload(PlayTvVideoClass.class_),
            )
            .filter_by(id=vid)
            .first()
        )
        if not video_out:
            return jsonify({"erro": "Vídeo atualizado mas falha ao recarregar"}), 500

        return jsonify({
            "mensagem": "Vídeo atualizado com sucesso",
            "video": _video_payload(video_out),
        }), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro ao atualizar vídeo: {e}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao atualizar vídeo: {e}", exc_info=True)
        return jsonify({"erro": "Erro ao atualizar vídeo", "detalhes": str(e)}), 500


@bp.route('/videos/<string:video_id>/resources/<string:resource_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def delete_video_resource(video_id, resource_id):
    """Remove um recurso (link ou arquivo). Arquivos são apagados do MinIO."""
    try:
        _, err = _require_play_tv_tenant()
        if err:
            return err

        video = PlayTvVideo.query.get(video_id)
        if not video:
            return jsonify({"erro": "Vídeo não encontrado"}), 404

        user = get_current_user_from_token()
        if not _user_may_edit_video(user, video):
            return jsonify({"erro": "Você não tem permissão"}), 403

        res = PlayTvVideoResource.query.filter_by(id=resource_id, video_id=video_id).first()
        if not res:
            return jsonify({"erro": "Recurso não encontrado"}), 404

        if res.resource_type == "file" and res.minio_object_name:
            m = MinIOService()
            m.delete_file(res.minio_bucket or m.BUCKETS["PLAY_TV_RESOURCES"], res.minio_object_name)

        db.session.delete(res)
        db.session.commit()
        return jsonify({"mensagem": "Recurso removido"}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(str(e))
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(str(e), exc_info=True)
        return jsonify({"erro": "Erro ao remover recurso", "detalhes": str(e)}), 500


@bp.route('/videos/<string:video_id>/resources/file', methods=['POST'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def upload_video_resource_file(video_id):
    try:
        _, err = _require_play_tv_tenant()
        if err:
            return err

        ctx = get_current_tenant_context()
        title = (request.form.get('title') or "").strip()
        if not title or len(title) > 200:
            return jsonify({"erro": "title obrigatório (máx. 200 caracteres)"}), 400

        upload = request.files.get('file')
        if not upload or not upload.filename:
            return jsonify({"erro": "Arquivo file é obrigatório"}), 400

        video = PlayTvVideo.query.get(video_id)
        if not video:
            return jsonify({"erro": "Vídeo não encontrado"}), 404

        user = get_current_user_from_token()
        if not _user_may_edit_video(user, video):
            return jsonify({"erro": "Você não tem permissão para anexar arquivo neste vídeo"}), 403

        upload.seek(0, os.SEEK_END)
        size = upload.tell()
        upload.seek(0)
        if size > _MAX_RESOURCE_UPLOAD_BYTES:
            return jsonify({"erro": "Arquivo excede o tamanho máximo permitido"}), 400

        raw_name = secure_filename(upload.filename) or "upload"
        resource_id = str(uuid.uuid4())
        bucket = MinIOService.BUCKETS["PLAY_TV_RESOURCES"]
        city_part = str(ctx.city_id).replace("-", "_")
        object_name = f"{city_part}/{video_id}/{resource_id}_{raw_name}"

        data = upload.read()
        minio = MinIOService()
        result = minio.upload_file(
            bucket_name=bucket,
            object_name=object_name,
            data=data,
            content_type=upload.content_type,
        )
        if not result:
            return jsonify({"erro": "Falha ao enviar arquivo para o armazenamento"}), 500

        sort_order_raw = request.form.get("sort_order")
        try:
            sort_order = int(sort_order_raw) if sort_order_raw is not None else 0
        except (TypeError, ValueError):
            sort_order = 0

        res = PlayTvVideoResource(
            id=resource_id,
            video_id=video_id,
            resource_type="file",
            title=title,
            minio_bucket=result.get("bucket") or bucket,
            minio_object_name=result.get("object_name"),
            original_filename=upload.filename[:500],
            content_type=(upload.content_type or "application/octet-stream")[:200],
            size_bytes=size,
            sort_order=sort_order,
        )
        db.session.add(res)
        db.session.commit()

        return jsonify({
            "mensagem": "Arquivo anexado com sucesso",
            "resource": {
                "id": res.id,
                "type": "file",
                "title": res.title,
                "file_name": res.original_filename,
                "mime_type": res.content_type,
                "size_bytes": res.size_bytes,
                "sort_order": res.sort_order,
            },
        }), 201

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(str(e))
        return jsonify({"erro": "Erro no banco de dados"}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(str(e), exc_info=True)
        return jsonify({"erro": "Erro ao enviar arquivo", "detalhes": str(e)}), 500


@bp.route('/videos/<string:video_id>/resources/<string:resource_id>/download', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm", "aluno")
def download_video_resource(video_id, resource_id):
    try:
        _, err = _require_play_tv_tenant()
        if err:
            return err

        video = _get_video_for_user_or_404(video_id)
        if not video:
            return jsonify({"erro": "Vídeo não encontrado"}), 404

        user = get_current_user_from_token()
        if not _user_may_access_video(user, video):
            return jsonify({"erro": "Você não tem permissão"}), 403

        res = PlayTvVideoResource.query.filter_by(id=resource_id, video_id=video_id).first()
        if not res or res.resource_type != "file":
            return jsonify({"erro": "Recurso não encontrado"}), 404
        if not res.minio_object_name:
            return jsonify({"erro": "Arquivo indisponível"}), 404

        minio = MinIOService()
        bucket = res.minio_bucket or minio.BUCKETS["PLAY_TV_RESOURCES"]
        try:
            url = minio.get_presigned_url(
                bucket,
                res.minio_object_name,
                expires=timedelta(hours=1),
            )
        except Exception as e:
            logging.error(f"presigned play_tv: {e}")
            return jsonify({"erro": "Não foi possível gerar link de download"}), 500

        return jsonify({
            "download_url": url,
            "expires_in_seconds": 3600,
            "file_name": res.original_filename,
        }), 200

    except Exception as e:
        logging.error(str(e), exc_info=True)
        return jsonify({"erro": "Erro ao gerar download"}), 500


@bp.route('/videos/<string:video_id>', methods=['DELETE'])
@jwt_required()
@role_required("admin", "professor", "diretor", "coordenador", "tecadm")
def delete_video(video_id):
    try:
        _, err = _require_play_tv_tenant()
        if err:
            return err

        current_user = get_current_user_from_token()
        if not current_user:
            return jsonify({"erro": "Usuário não autenticado"}), 401

        video = PlayTvVideo.query.options(joinedload(PlayTvVideo.resources)).get(video_id)
        if not video:
            return jsonify({"erro": "Vídeo não encontrado"}), 404

        role = (current_user.get("role") or "").lower()
        if role != "admin" and str(video.created_by) != str(current_user.get("id")):
            return jsonify({"erro": "Acesso negado."}), 403

        _delete_file_resources_from_minio(video)
        db.session.delete(video)
        db.session.commit()

        logging.info(f"Vídeo {video_id} deletado por usuário {current_user['id']}")
        return jsonify({"mensagem": "Vídeo excluído com sucesso!"}), 200

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"Erro no banco de dados: {str(e)}")
        return jsonify({"erro": "Erro no banco de dados", "detalhes": str(e)}), 500
    except Exception as e:
        db.session.rollback()
        logging.error(f"Erro ao excluir vídeo: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao excluir vídeo", "detalhes": str(e)}), 500
