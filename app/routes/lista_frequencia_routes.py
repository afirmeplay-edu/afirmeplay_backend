"""
Endpoint de Lista de Frequência (dados reais).
Para avaliações, provas físicas e frequência diária do professor.
Legenda de status: P, A, T, NE, SE, SS, I. Sem dados de assinatura.
"""

from collections import defaultdict
from datetime import datetime
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.orm import joinedload, selectinload

from app import db
from app.decorators.role_required import role_required
from app.models.city import City
from app.models.studentClass import Class
from app.models.school import School
from app.models.student import Student
from app.models.grades import Grade
from app.models.classSubject import ClassSubject
from app.models.subject import Subject
from app.exams.models.test import Test
from app.exams.models.classTest import ClassTest
from app.exams.models.testSession import TestSession
from app.answer_sheets.models.answerSheetGabarito import AnswerSheetGabarito
from app.answer_sheets.models.answerSheetResult import AnswerSheetResult
from app.reports.report_analysis.answer_sheet_report_builder import get_answer_sheet_target_classes_for_report
from app.utils.uuid_helpers import ensure_uuid

bp = Blueprint("lista_frequencia", __name__, url_prefix="/lista-frequencia")

# Legenda para status: P = Presente; A = Ausente; T = Transferido; NE: Necessidades Específicas;
# SE = Sala Extra; SS = Sala Suporte; I = Inserido
LEGENDA = {
    "P": "Presente",
    "A": "Ausente",
    "T": "Transferido",
    "NE": "Necessidades Específicas",
    "SE": "Sala Extra",
    "SS": "Sala Suporte",
    "I": "Inserido",
}

# Valores válidos para status (uso em estudantes)
STATUS_VALIDOS = frozenset(LEGENDA.keys())

INSTRUCOES_APLICADOR = (
    "Prezado(a) Aplicador(a), preencha os círculos completamente e com nitidez "
    "de acordo com a legenda acima, verifique a assinatura de cada aluno presente."
)


# Status de sessão considerados como "presente" na avaliação
SESSION_STATUS_PRESENTE = ("finalizada", "expirada", "corrigida", "revisada")

_CLASS_LIST_OPTIONS = (
    selectinload(Class.class_subjects).joinedload(ClassSubject.subject),
    joinedload(Class.grade),
)


def _turmas_query(query):
    """Eager-load de série e disciplinas para evitar N+1 no cabeçalho."""
    return query.options(*_CLASS_LIST_OPTIONS)


def _cabecalho_real(classe, tipo, test=None, gabarito=None, school=None, city=None):
    """Monta o cabeçalho a partir da turma (Class) e do tipo de lista.
    Se test ou gabarito tiver título, usa em nome_prova_ano.
    """
    if school is None:
        school = classe.school
    if city is None and school is not None:
        city = school.city
    grade = classe.grade if hasattr(classe, "grade") else None

    municipio_uf = None
    if city and city.name:
        municipio_uf = (
            f"{city.name.upper()}/{city.state.upper()}"
            if city.state
            else city.name.upper()
        )

    ano = datetime.now().year
    if test and getattr(test, "title", None):
        nome_prova_ano = f"{test.title} – {ano}"
        lista_presenca_curso = "LISTA DE PRESENÇA – AVALIAÇÃO"
    elif gabarito and getattr(gabarito, "title", None) and str(gabarito.title).strip():
        nome_prova_ano = f"{str(gabarito.title).strip()} – {ano}"
        lista_presenca_curso = "LISTA DE PRESENÇA – AVALIAÇÃO"
    else:
        titulos = {
            "avaliacao": (f"NOME DA PROVA – {ano}", "LISTA DE PRESENÇA – AVALIAÇÃO"),
            "prova_fisica": (f"PROVA FÍSICA – {ano}", "LISTA DE PRESENÇA – PROVA FÍSICA"),
            "frequencia_diaria": (f"FREQUÊNCIA DIÁRIA – {ano}", "LISTA DE PRESENÇA – FREQUÊNCIA DIÁRIA"),
        }
        nome_prova_ano, lista_presenca_curso = titulos.get(
            tipo, (f"NOME DA PROVA – {ano}", "LISTA DE PRESENÇA – CURSO")
        )

    # Disciplinas da turma (ClassSubject + Subject)
    disciplinas = []
    if hasattr(classe, "class_subjects") and classe.class_subjects:
        for cs in classe.class_subjects:
            if cs.subject and cs.subject.name:
                disciplinas.append(cs.subject.name.upper())
    disciplina = " E ".join(disciplinas) if disciplinas else None

    # Série (do Grade) e turma separados
    serie = grade.name if grade else None
    turma = getattr(classe, "turma", None)
    if turma is None and classe and classe.name:
        name_stripped = (classe.name or "").strip()
        if name_stripped:

            def _norm(s):
                """Normaliza para comparação: ° e º como equivalentes, maiúsculas."""
                if not s:
                    return ""
                s = s.strip().upper()
                for old, new in (("º", "O"), ("°", "O"), ("ª", "A")):
                    s = s.replace(old, new)
                return s

            # Tenta obter turma removendo a série do início do nome (ex: "6° ANO A" com série "6º ano" -> "A")
            if serie:
                serie_norm = _norm(serie)
                name_norm = _norm(name_stripped)
                if serie_norm and name_norm.startswith(serie_norm):
                    rest = name_stripped[len(serie_norm) :].strip().lstrip(" -–—").strip()
                    if rest:
                        turma = rest

            # Fallback: última palavra com 1 caractere (A, B, 1) = turma; ou 3+ palavras (ex: "6° ANO A")
            if turma is None:
                partes = name_stripped.split()
                if partes:
                    ultima = partes[-1]
                    if len(ultima) == 1:
                        turma = ultima
                    elif len(partes) > 2:
                        turma = ultima

    return {
        "nome_prova_ano": nome_prova_ano,
        "lista_presenca_curso": lista_presenca_curso,
        "municipio_uf": municipio_uf,
        "rede": getattr(school, "rede", None) if school else None,
        "nome_escola": school.name if school else None,
        "serie": serie,
        "turma": turma,
        "serie_turma": classe.name if classe else None,
        "turno": classe.shift,
        "disciplina": disciplina,
        "legenda": LEGENDA,
        "instrucoes_aplicador": INSTRUCOES_APLICADOR,
    }


def _status_estudante_avaliacao(student_ids, test_id):
    """
    Retorna mapa student_id -> status (P ou A) para os alunos que fizeram a avaliação.
    P = presente (sessão finalizada/corrigida/revisada ou com submitted_at); A = ausente.
    """
    if not student_ids or not test_id:
        return {}
    sessoes = (
        TestSession.query.filter(
            TestSession.test_id == test_id,
            TestSession.student_id.in_(student_ids),
        )
        .all()
    )
    resultado = {}
    for sess in sessoes:
        presente = (
            sess.status in SESSION_STATUS_PRESENTE
            or sess.submitted_at is not None
        )
        resultado[str(sess.student_id)] = "P" if presente else "A"
    return resultado


def _status_estudante_cartao_resposta(student_ids, gabarito_id):
    """
    P = aluno com resultado de correção do cartão para o gabarito; A = sem resultado.
    """
    if not student_ids or not gabarito_id:
        return {}
    rows = (
        AnswerSheetResult.query.filter(
            AnswerSheetResult.gabarito_id == gabarito_id,
            AnswerSheetResult.student_id.in_(student_ids),
        )
        .all()
    )
    com_resultado = {str(r.student_id) for r in rows}
    return {sid: ("P" if sid in com_resultado else "A") for sid in student_ids}


def _estudantes_payload(alunos, fill_status, test=None, gabarito=None, status_map=None):
    """Monta a lista de estudantes; status_map opcional (pré-carregado em lote)."""
    if fill_status and gabarito:
        status_map = status_map or _status_estudante_cartao_resposta(
            [str(s.id) for s in alunos], gabarito.id
        )
        return [
            {
                "numero": idx + 1,
                "nome_estudante": (s.name or "").strip() or None,
                "status": status_map.get(str(s.id), "A"),
            }
            for idx, s in enumerate(alunos)
        ]
    if fill_status and test:
        status_map = status_map or _status_estudante_avaliacao(
            [str(s.id) for s in alunos], test.id
        )
        return [
            {
                "numero": idx + 1,
                "nome_estudante": (s.name or "").strip() or None,
                "status": status_map.get(str(s.id), "A"),
            }
            for idx, s in enumerate(alunos)
        ]
    return [
        {
            "numero": idx + 1,
            "nome_estudante": (s.name or "").strip() or None,
            "status": None,
        }
        for idx, s in enumerate(alunos)
    ]


def _montar_listas_turmas_bulk(turmas, tipo, test, fill_status, gabarito=None, city_fallback=None):
    """
    Monta várias turmas com poucas queries (alunos, escolas e status em lote).
    """
    if not turmas:
        return []

    class_ids = [c.id for c in turmas]
    alunos_por_turma = defaultdict(list)
    if class_ids:
        for aluno in (
            Student.query.filter(Student.class_id.in_(class_ids))
            .order_by(Student.class_id, Student.name)
            .all()
        ):
            alunos_por_turma[aluno.class_id].append(aluno)

    school_ids = {str(c._school_id) for c in turmas if c._school_id}
    schools_by_id = {}
    if school_ids:
        for escola in (
            School.query.filter(School.id.in_(list(school_ids)))
            .options(joinedload(School.city))
            .all()
        ):
            schools_by_id[str(escola.id)] = escola

    status_map_global = None
    if fill_status and (gabarito or test):
        todos_ids = [
            str(s.id)
            for cid in class_ids
            for s in alunos_por_turma.get(cid, [])
        ]
        if gabarito:
            status_map_global = _status_estudante_cartao_resposta(todos_ids, gabarito.id)
        else:
            status_map_global = _status_estudante_avaliacao(todos_ids, test.id)

    lista = []
    for classe in turmas:
        escola = schools_by_id.get(str(classe._school_id)) if classe._school_id else None
        cidade = city_fallback
        if cidade is None and escola is not None:
            cidade = escola.city
        cabecalho = _cabecalho_real(
            classe, tipo, test=test, gabarito=gabarito, school=escola, city=cidade
        )
        alunos = alunos_por_turma.get(classe.id, [])
        lista.append({
            "class_id": str(classe.id),
            "cabecalho": cabecalho,
            "estudantes": _estudantes_payload(
                alunos, fill_status, test=test, gabarito=gabarito, status_map=status_map_global
            ),
        })
    return lista


def _response_turmas_lista(lista):
    """Resposta em lote: legenda/instruções uma vez (payload menor, evita crash no cliente)."""
    if not lista:
        return jsonify({"turmas": []}), 200
    if len(lista) == 1:
        return jsonify({"turmas": lista}), 200
    turmas = []
    for item in lista:
        cab = dict(item["cabecalho"])
        cab.pop("legenda", None)
        cab.pop("instrucoes_aplicador", None)
        turmas.append({
            "class_id": item["class_id"],
            "cabecalho": cab,
            "estudantes": item["estudantes"],
        })
    return jsonify({
        "legenda": LEGENDA,
        "instrucoes_aplicador": INSTRUCOES_APLICADOR,
        "turmas": turmas,
    }), 200


def _montar_lista_turma(classe, tipo, test, fill_status, gabarito=None):
    """Monta um item de lista (cabecalho + estudantes) para uma turma."""
    cabecalho = _cabecalho_real(classe, tipo, test=test, gabarito=gabarito)
    alunos = (
        Student.query.filter_by(class_id=classe.id)
        .order_by(Student.name)
        .all()
    )
    estudantes = _estudantes_payload(
        alunos, fill_status, test=test, gabarito=gabarito
    )
    return {"cabecalho": cabecalho, "estudantes": estudantes}


@bp.route("/", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def lista_frequencia():
    """
    Retorna lista de frequência com dados reais.

    Por turma: class_id (obrigatório). Status dos estudantes fica null.

    Por avaliação aplicada: test_id (obrigatório).
    - Sem class_id e sem grade_id: retorna TODAS as turmas da avaliação em { "turmas": [...] }.
    - Com grade_id (e sem class_id): retorna só as turmas daquela série em { "turmas": [...] }.
    - Com class_id: retorna uma única turma (cabecalho + estudantes).
    Status P/A conforme TestSession.

    Por cartão resposta (gabarito): gabarito_id + city_id (município) obrigatórios.
    Turmas alvo via get_answer_sheet_target_classes_for_report; P/A conforme AnswerSheetResult.
    Query param opcional: tipo = avaliacao | prova_fisica | frequencia_diaria
    """
    gabarito_id = (request.args.get("gabarito_id") or "").strip()
    city_id = (request.args.get("city_id") or "").strip()
    test_id = request.args.get("test_id")
    class_id = request.args.get("class_id")
    grade_id = request.args.get("grade_id")
    school_id = request.args.get("school_id")

    if gabarito_id:
        if not city_id:
            return jsonify({"erro": "Informe city_id (município) ao usar gabarito_id"}), 400
        gab = AnswerSheetGabarito.query.get(gabarito_id)
        if not gab:
            return jsonify({"erro": "Gabarito não encontrado"}), 404
        turmas_alvo = get_answer_sheet_target_classes_for_report(gab, "city", city_id)
        if not turmas_alvo:
            return jsonify({
                "erro": "Nenhuma turma encontrada para este cartão neste município.",
            }), 404

        tipo = request.args.get("tipo", "avaliacao")
        if tipo not in ("avaliacao", "prova_fisica", "frequencia_diaria"):
            tipo = "avaliacao"

        class_uuid = None
        if class_id:
            class_uuid = ensure_uuid(class_id)
            if not class_uuid:
                return jsonify({"erro": "class_id inválido"}), 400
            turmas_filtradas = [c for c in turmas_alvo if c.id == class_uuid]
            if not turmas_filtradas:
                return jsonify({"erro": "Turma não está entre as turmas deste cartão"}), 404
        elif grade_id:
            grade_uuid = ensure_uuid(grade_id)
            if not grade_uuid:
                return jsonify({"erro": "grade_id inválido"}), 400
            turmas_filtradas = [c for c in turmas_alvo if c.grade_id == grade_uuid]
            if not turmas_filtradas:
                return jsonify({
                    "erro": "Nenhuma turma desta série está vinculada a este cartão.",
                }), 404
        else:
            turmas_filtradas = list(turmas_alvo)

        if class_id and class_uuid:
            classe = turmas_filtradas[0]
            item = _montar_lista_turma(classe, tipo, test=None, fill_status=True, gabarito=gab)
            payload = {
                "cabecalho": item["cabecalho"],
                "estudantes": item["estudantes"],
                "class_id": str(class_uuid),
            }
            return jsonify(payload), 200

        city_fallback = City.query.get(city_id) if city_id else None
        if len(turmas_filtradas) > 1:
            lista = _montar_listas_turmas_bulk(
                turmas_filtradas, tipo, test=None, fill_status=True,
                gabarito=gab, city_fallback=city_fallback,
            )
        else:
            c = turmas_filtradas[0]
            item = _montar_lista_turma(c, tipo, test=None, fill_status=True, gabarito=gab)
            lista = [{
                "class_id": str(c.id),
                "cabecalho": item["cabecalho"],
                "estudantes": item["estudantes"],
            }]
        return _response_turmas_lista(lista)

    classe = None
    class_uuid = None
    test = None
    turmas_grade = None  # quando preenchido, resposta será { "turmas": [...] }

    if test_id:
        test = Test.query.get(test_id)
        if not test:
            return jsonify({"erro": "Avaliação não encontrada"}), 404

        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        if not class_tests:
            return jsonify({"erro": "Avaliação não está vinculada a nenhuma turma"}), 404

        class_ids_avaliacao = [ct.class_id for ct in class_tests]

        # Filtro apenas por série: retornar todas as turmas da avaliação com essa grade_id
        if grade_id and not class_id:
            grade_uuid = ensure_uuid(grade_id)
            if not grade_uuid:
                return jsonify({"erro": "grade_id inválido"}), 400
            turmas_grade = (
                _turmas_query(
                    Class.query.filter(
                        Class.id.in_(class_ids_avaliacao),
                        Class.grade_id == grade_uuid,
                    )
                )
                .order_by(Class.name)
                .all()
            )
            if not turmas_grade:
                return jsonify({
                    "erro": "Nenhuma turma desta série está vinculada a esta avaliação.",
                }), 404

        # Turma específica: class_id informado
        elif class_id:
            class_uuid = ensure_uuid(class_id)
            if not class_uuid:
                return jsonify({"erro": "class_id inválido"}), 400
            if not any(ct.class_id == class_uuid for ct in class_tests):
                return jsonify({"erro": "Turma não está vinculada a esta avaliação"}), 404
            classe = Class.query.get(class_uuid)
            if not classe:
                return jsonify({"erro": "Turma não encontrada"}), 404

        # Sem class_id nem grade_id: retornar TODAS as turmas da avaliação (ex.: "todas as turmas")
        elif not class_id and not grade_id:
            turmas_grade = (
                _turmas_query(Class.query.filter(Class.id.in_(class_ids_avaliacao)))
                .order_by(Class.grade_id, Class.name)
                .all()
            )

        if turmas_grade is None and classe is None:
            return jsonify({"erro": "Turma não encontrada"}), 404

    else:
        if city_id and not class_id:
            # city_id em public.city é VARCHAR; não usar uuid.UUID na comparação (evita cast ::UUID no SQL)
            city_id_str = city_id.strip()
            if not city_id_str:
                return jsonify({"erro": "city_id inválido"}), 400

            school_ids_city = [
                str(s.id) for s in School.query.filter(School.city_id == city_id_str).all()
            ]
            if not school_ids_city:
                return jsonify({"erro": "Nenhuma escola encontrada para o município informado"}), 404
            query = Class.query.filter(Class._school_id.in_(school_ids_city))

            if school_id:
                school_uuid = ensure_uuid(school_id)
                if not school_uuid:
                    return jsonify({"erro": "school_id inválido"}), 400
                query = query.filter(Class._school_id == str(school_uuid))

            if grade_id:
                grade_uuid = ensure_uuid(grade_id)
                if not grade_uuid:
                    return jsonify({"erro": "grade_id inválido"}), 400
                query = query.filter(Class.grade_id == grade_uuid)

            turmas_grade = (
                _turmas_query(query).order_by(Class.grade_id, Class.name).all()
            )
            if not turmas_grade:
                return jsonify({"erro": "Nenhuma turma encontrada para os filtros informados"}), 404
        else:
            if not class_id:
                return jsonify({"erro": "Informe class_id, test_id ou city_id"}), 400
            class_uuid = ensure_uuid(class_id)
            if not class_uuid:
                return jsonify({"erro": "class_id inválido"}), 400
            classe = Class.query.get(class_uuid)
            if not classe:
                return jsonify({"erro": "Turma não encontrada"}), 404

    tipo = request.args.get("tipo", "avaliacao")
    if tipo not in ("avaliacao", "prova_fisica", "frequencia_diaria"):
        tipo = "avaliacao"

    if turmas_grade is not None:
        fill_status_bulk = test is not None
        city_fallback = City.query.get(city_id) if city_id else None
        try:
            if len(turmas_grade) > 1:
                lista = _montar_listas_turmas_bulk(
                    turmas_grade, tipo, test, fill_status_bulk, city_fallback=city_fallback
                )
            else:
                c = turmas_grade[0]
                item = _montar_lista_turma(c, tipo, test, fill_status=fill_status_bulk)
                lista = [{
                    "class_id": str(c.id),
                    "cabecalho": item["cabecalho"],
                    "estudantes": item["estudantes"],
                }]
        except Exception:
            current_app.logger.exception("Erro ao montar lista de frequência em lote")
            return jsonify({"erro": "Erro ao gerar listas em lote. Tente filtrar por escola ou série."}), 500
        return _response_turmas_lista(lista)

    item = _montar_lista_turma(classe, tipo, test, fill_status=(test_id is not None))
    payload = {
        "cabecalho": item["cabecalho"],
        "estudantes": item["estudantes"],
    }
    if class_uuid:
        payload["class_id"] = str(class_uuid)
    return jsonify(payload), 200
