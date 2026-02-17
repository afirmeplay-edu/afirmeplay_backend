"""
Endpoint de Lista de Frequência (dados reais).
Para avaliações, provas físicas e frequência diária do professor.
Legenda de status: P, A, T, NE, SE, SS, I. Sem dados de assinatura.
"""

from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.decorators.role_required import role_required
from app.models.studentClass import Class
from app.models.student import Student
from app.models.grades import Grade
from app.models.classSubject import ClassSubject
from app.models.subject import Subject
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.testSession import TestSession
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


def _cabecalho_real(classe, tipo, test=None):
    """Monta o cabeçalho a partir da turma (Class) e do tipo de lista. Se test for informado, usa test.title em nome_prova_ano."""
    school = classe.school
    city = school.city if school else None
    grade = classe.grade if hasattr(classe, "grade") else None

    municipio_uf = None
    if city:
        municipio_uf = f"{city.name.upper()}/{city.state.upper()}" if city.state else city.name.upper()

    ano = datetime.now().year
    if test and getattr(test, "title", None):
        nome_prova_ano = f"{test.title} – {ano}"
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
        "turno": getattr(classe, "turno", None),
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


def _montar_lista_turma(classe, tipo, test, fill_status):
    """Monta um item de lista (cabecalho + estudantes) para uma turma."""
    cabecalho = _cabecalho_real(classe, tipo, test=test)
    alunos = (
        Student.query.filter_by(class_id=classe.id)
        .order_by(Student.name)
        .all()
    )
    if fill_status and test:
        student_ids = [str(s.id) for s in alunos]
        status_map = _status_estudante_avaliacao(student_ids, test.id)
        estudantes = [
            {
                "numero": idx + 1,
                "nome_estudante": (s.name or "").strip() or None,
                "status": status_map.get(str(s.id), "A"),
            }
            for idx, s in enumerate(alunos)
        ]
    else:
        estudantes = [
            {
                "numero": idx + 1,
                "nome_estudante": (s.name or "").strip() or None,
                "status": None,
            }
            for idx, s in enumerate(alunos)
        ]
    return {"cabecalho": cabecalho, "estudantes": estudantes}


@bp.route("/", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def lista_frequencia():
    """
    Retorna lista de frequência com dados reais.

    Por turma: class_id (obrigatório). Status dos estudantes fica null.

    Por avaliação já feita: test_id (obrigatório). Opcional: class_id para uma turma;
    grade_id para filtrar por série: retorna todas as turmas da avaliação com essa série
    (resposta em turmas[]). Status P/A conforme TestSession.
    Query param opcional: tipo = avaliacao | prova_fisica | frequencia_diaria
    """
    test_id = request.args.get("test_id")
    class_id = request.args.get("class_id")
    grade_id = request.args.get("grade_id")

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

        # Filtro apenas por série: retornar todas as turmas da avaliação com essa grade_id
        if grade_id and not class_id:
            grade_uuid = ensure_uuid(grade_id)
            if not grade_uuid:
                return jsonify({"erro": "grade_id inválido"}), 400
            class_ids_avaliacao = [ct.class_id for ct in class_tests]
            turmas_grade = (
                Class.query.filter(
                    Class.id.in_(class_ids_avaliacao),
                    Class.grade_id == grade_uuid,
                )
                .order_by(Class.name)
                .all()
            )
            if not turmas_grade:
                return jsonify({
                    "erro": "Nenhuma turma desta série está vinculada a esta avaliação.",
                }), 404

        elif len(class_tests) == 1 and not grade_id:
            class_uuid = class_tests[0].class_id
        else:
            if class_id:
                class_uuid = ensure_uuid(class_id)
                if not class_uuid:
                    return jsonify({"erro": "class_id inválido"}), 400
                if not any(ct.class_id == class_uuid for ct in class_tests):
                    return jsonify({"erro": "Turma não está vinculada a esta avaliação"}), 404
            else:
                class_uuid = class_tests[0].class_id

        if turmas_grade is None:
            classe = Class.query.get(class_uuid)
            if not classe:
                return jsonify({"erro": "Turma não encontrada"}), 404

    else:
        if not class_id:
            return jsonify({"erro": "Informe class_id ou test_id"}), 400
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
        # Resposta: todas as turmas da série que fizeram a avaliação
        lista = []
        for c in turmas_grade:
            item = _montar_lista_turma(c, tipo, test, fill_status=True)
            lista.append({
                "class_id": str(c.id),
                "cabecalho": item["cabecalho"],
                "estudantes": item["estudantes"],
            })
        return jsonify({"turmas": lista}), 200

    item = _montar_lista_turma(classe, tipo, test, fill_status=(test_id is not None))
    payload = {
        "cabecalho": item["cabecalho"],
        "estudantes": item["estudantes"],
    }
    if class_uuid:
        payload["class_id"] = str(class_uuid)
    return jsonify(payload), 200
