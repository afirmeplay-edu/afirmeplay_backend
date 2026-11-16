"""Testes puros do relatório de habilidade e gabarito (sem banco)."""

from app.habilidade_gabarito.helpers import (
    REPORT_NAME,
    questao_row,
    skill_texts_answer_sheet,
    skill_texts_digital,
)


class _Skill:
    def __init__(self, code, description):
        self.code = code
        self.description = description


def test_nome_do_relatorio():
    assert REPORT_NAME == "Relatório de habilidade e gabarito"


def test_questao_row_normaliza_gabarito_e_habilidade_vazia():
    row = questao_row(3, "", "", "b")
    assert row == {
        "numero": 3,
        "habilidade": "N/A",
        "descricao_habilidade": "",
        "gabarito": "B",
    }
    sem_letra = questao_row(1, "EF05LP01", "Ler textos", None)
    assert sem_letra["gabarito"] == ""
    assert sem_letra["habilidade"] == "EF05LP01"
    assert sem_letra["descricao_habilidade"] == "Ler textos"


def test_skill_texts_digital_codigo_e_uuid_ausente():
    sid = "11111111-1111-1111-1111-111111111111"
    missing = "22222222-2222-2222-2222-222222222222"
    skills_db = {sid: _Skill("EF05MA01", "Resolver problemas")}
    codigo, descricao = skill_texts_digital(sid, skills_db)
    assert codigo == "EF05MA01"
    assert descricao == "Resolver problemas"

    codigo, descricao = skill_texts_digital(f"{sid},{missing}", skills_db)
    assert "EF05MA01" in codigo
    assert "N/A" in codigo
    assert "Resolver problemas" in descricao
    assert "não foi encontrada" in descricao

    codigo, descricao = skill_texts_digital("EF15LP03", {})
    assert codigo == "EF15LP03"
    assert descricao == ""


def test_skill_texts_answer_sheet_sem_habilidade():
    codigo, descricao = skill_texts_answer_sheet([], {})
    assert codigo == "N/A"
    assert descricao == ""
