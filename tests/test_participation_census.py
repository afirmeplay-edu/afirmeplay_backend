# -*- coding: utf-8 -*-
"""Censo de participação, sem banco e sem endpoint."""
from app.services.participation_census import (
    AlunoEntradaCenso,
    ClassTestEntrada,
    DisciplinaCenso,
    ParticipationCensusRequest,
    ProvaCenso,
    ProvaPareadaCenso,
    ResultadoEntradaCenso,
    build_participation_census,
    percentual_censo,
)

LP = DisciplinaCenso("lp", "Língua Portuguesa")
MAT = DisciplinaCenso("mat", "Matemática")
CIE = DisciplinaCenso("cie", "Ciências")


def _prova(test_id, disciplina, *pares):
    return ProvaCenso(
        test_id=test_id,
        disciplinas=(disciplina,),
        provas_adap=tuple(
            ProvaPareadaCenso(par[0], par[1] if len(par) > 1 else None) for par in pares
        ),
    )


def _aluno(sid, turma, *, especial=False, nivel=None, escola="esc", serie="5ano"):
    return AlunoEntradaCenso(
        student_id=sid,
        escola_id=escola,
        serie_id=serie,
        turma_id=turma,
        is_special=especial,
        nivel_adap=nivel,
    )


def _res(sid, test_id, quando=1, snapshot=None):
    return ResultadoEntradaCenso(
        student_id=sid,
        test_id=test_id,
        calculated_at=quando,
        class_id_snapshot=snapshot,
    )


def _censo(alunos, resultados, *, universo="todos", class_tests=None, provas=None, **kwargs):
    provas = provas or (
        _prova("reg-lp", LP, ("adap-lp", 1)),
        _prova("reg-mat", MAT, ("adap-mat", 1)),
    )
    if class_tests is None:
        turmas = {aluno.turma_id for aluno in alunos if aluno.turma_id}
        class_tests = [
            ClassTestEntrada(turma, prova.test_id) for turma in turmas for prova in provas
        ]
    return build_participation_census(
        ParticipationCensusRequest(
            municipio_id="cidade",
            provas=provas,
            universo=universo,
            alunos=alunos,
            class_tests=class_tests,
            resultados=resultados,
            **kwargs,
        )
    )


def _por_id(censo):
    return {aluno.student_id: aluno for aluno in censo.alunos}


def _disc(aluno, disciplina_id):
    return next(item for item in aluno.disciplinas if item.disciplina_id == disciplina_id)


def test_card_e_celula_usam_o_mesmo_agregado():
    from app.services.participation_census import campos_participacao, contagens_celula

    alunos = [
        _aluno("a", "t1", escola="e1"),
        _aluno("b", "t1", escola="e1"),
        _aluno("c", "t2", escola="e2"),
    ]
    censo = _censo(
        alunos,
        [_res("a", "reg-lp"), _res("a", "reg-mat"), _res("b", "reg-lp"), _res("c", "reg-lp"), _res("c", "reg-mat")],
        universo="regular",
    )
    card = campos_participacao(censo, grupo=True)
    assert card["total_alunos"] == 3
    assert card["alunos_participantes"] == 2
    assert card["alunos_parciais"] == 1
    assert card["percentual_comparecimento"] == censo.geral.percentual_completa
    mat_1, presentes_1 = contagens_celula(censo, "e1", "5ano", None)
    mat_2, presentes_2 = contagens_celula(censo, "e2", "5ano", None)
    assert (mat_1 + mat_2, presentes_1 + presentes_2) == (3, 2)
    mat_lp, presentes_lp = contagens_celula(censo, "e1", "5ano", "Língua Portuguesa")
    assert (mat_lp, presentes_lp) == (2, 2)


def test_arredondamento_da_taxa_usa_a_mesma_regra_do_sistema():
    assert percentual_censo(289, 320) == 90.31
    assert percentual_censo(314, 320) == 98.12
    assert percentual_censo(302, 320) == 94.38
    assert percentual_censo(301, 320) == 94.06
    assert percentual_censo(0, 0) == 0.0


def test_completa_e_pelo_menos_uma_em_duas_e_tres_provas():
    provas = (
        _prova("reg-lp", LP),
        _prova("reg-mat", MAT),
        _prova("reg-cie", CIE),
    )
    alunos = [_aluno("so_lp", "t1"), _aluno("duas", "t1"), _aluno("tres", "t1"), _aluno("nenhuma", "t1")]
    resultados = [
        _res("so_lp", "reg-lp"),
        _res("duas", "reg-lp"),
        _res("duas", "reg-mat"),
        _res("tres", "reg-lp"),
        _res("tres", "reg-mat"),
        _res("tres", "reg-cie"),
    ]
    censo = _censo(alunos, resultados, provas=provas)
    por_id = _por_id(censo)
    assert por_id["so_lp"].participacao_pelo_menos_uma is True
    assert por_id["so_lp"].participacao_completa is False
    assert por_id["duas"].participacao_completa is False
    assert por_id["tres"].participacao_completa is True
    assert por_id["nenhuma"].participacao_completa is False
    assert por_id["nenhuma"].participacao_pelo_menos_uma is False
    assert censo.geral.presentes_completos == 1
    assert censo.geral.presentes_pelo_menos_uma == 3
    assert censo.geral.ausentes == 1
    assert censo.geral.matriculados == 4


def test_completa_usa_o_que_a_turma_recebeu():
    provas = (
        _prova("reg-lp", LP),
        _prova("reg-mat", MAT),
        _prova("reg-cie", CIE),
    )
    aluno = _aluno("b", "turma-b")
    censo = _censo(
        [aluno],
        [_res("b", "reg-lp")],
        provas=provas,
        class_tests=(ClassTestEntrada("turma-b", "reg-lp"),),
    )
    assert censo.alunos[0].participacao_completa is True
    assert _disc(censo.alunos[0], "mat").elegivel is False
    assert _disc(censo.alunos[0], "cie").elegivel is False


def test_adap_so_com_prova_pareada_entra_na_visao_inclusiva():
    aluno = _aluno("a1", "t1", especial=True, nivel=1)
    censo_regular = _censo([aluno], [_res("a1", "adap-lp"), _res("a1", "adap-mat")], universo="regular")
    assert censo_regular.alunos == ()
    assert censo_regular.geral.matriculados == 0

    for universo in ("adap", "regular_adap", "todos"):
        censo = _censo(
            [aluno],
            [_res("a1", "adap-lp"), _res("a1", "adap-mat")],
            universo=universo,
        )
        registro = censo.alunos[0]
        assert registro.participacao_completa is True
        assert registro.perfil == "adap"
        assert registro.nivel_adap == 1
        lp = _disc(registro, "lp")
        assert lp.situacao == "presente"
        assert lp.test_id_valido == "adap-lp"
        assert [origem.tipo for origem in lp.origens] == ["adap"]


def test_nivel_diferente_da_prova_adap_nao_anula_presenca():
    aluno = _aluno("a1", "t1", especial=True, nivel=1)
    provas = (
        _prova("reg-lp", LP, ("adap-lp-2", 2)),
        _prova("reg-mat", MAT, ("adap-mat-2", 2)),
    )
    censo = _censo(
        [aluno],
        [_res("a1", "adap-lp-2"), _res("a1", "adap-mat-2")],
        universo="adap",
        provas=provas,
    )
    assert censo.alunos[0].participacao_completa is True
    assert _disc(censo.alunos[0], "lp").origens[0].nivel_da_prova == 2


def test_duas_modalidades_nao_viram_presenca():
    aluno = _aluno("ax", "t1", especial=True, nivel=2)
    censo = _censo(
        [aluno],
        [
            _res("ax", "reg-lp", quando=1),
            _res("ax", "adap-lp", quando=2),
            _res("ax", "adap-mat", quando=2),
        ],
        universo="todos",
    )
    lp = _disc(censo.alunos[0], "lp")
    mat = _disc(censo.alunos[0], "mat")
    assert lp.situacao == "inconsistente"
    assert lp.motivo_inconsistencia == "ambas_modalidades"
    assert lp.test_id_valido is None
    assert {origem.tipo for origem in lp.origens} == {"regular", "adap"}
    assert mat.situacao == "presente"
    assert censo.alunos[0].participacao_completa is False
    assert censo.alunos[0].participacao_pelo_menos_uma is True
    assert censo.geral.inconsistentes == 1
    assert censo.geral.ausentes == 0
    assert censo.geral.por_disciplina[0].inconsistentes == 1
    assert censo.geral.por_disciplina[0].presentes == 0


def test_modalidade_errada_fica_inconsistente():
    adap = _aluno("a3", "t1", especial=True, nivel=3)
    regular = _aluno("r", "t1")
    censo = _censo(
        [adap, regular],
        [_res("a3", "reg-mat"), _res("r", "adap-lp")],
        universo="todos",
    )
    por_id = _por_id(censo)
    assert _disc(por_id["a3"], "mat").situacao == "inconsistente"
    assert _disc(por_id["a3"], "mat").motivo_inconsistencia == "modalidade_incorreta"
    assert _disc(por_id["a3"], "lp").situacao == "ausente"
    assert _disc(por_id["r"], "lp").situacao == "inconsistente"
    assert _disc(por_id["r"], "lp").motivo_inconsistencia == "modalidade_incorreta"
    assert por_id["a3"].participacao_pelo_menos_uma is False
    assert por_id["r"].participacao_pelo_menos_uma is False


def test_adap_3_entra_em_adap_regular_adap_e_todos_e_sai_de_regular():
    aluno = _aluno("a3", "t1", especial=True, nivel=3)
    resultados = [_res("a3", "adap-lp"), _res("a3", "adap-mat")]
    assert _censo([aluno], resultados, universo="regular").geral.matriculados == 0
    for universo in ("adap", "regular_adap", "todos"):
        censo = _censo([aluno], resultados, universo=universo)
        assert censo.geral.matriculados == 1
        assert censo.alunos[0].participacao_completa is True
        assert censo.alunos[0].nivel_adap == 3


def test_snapshot_sem_turma_fica_no_historico_e_fora_da_taxa():
    aluno = AlunoEntradaCenso(student_id="snap", escola_id=None, turma_id=None)
    censo = _censo([aluno], [_res("snap", "reg-lp", snapshot="turma-antiga")])
    assert censo.historico == 1
    assert censo.alunos[0].historico is True
    assert censo.alunos[0].no_denominador is False
    assert censo.geral.matriculados == 0
    assert censo.geral.presentes_completos == 0
    assert censo.geral.presentes_pelo_menos_uma == 0

    oculto = _censo(
        [aluno],
        [_res("snap", "reg-lp", snapshot="turma-antiga")],
        incluir_historico=False,
    )
    assert oculto.alunos == ()
    assert oculto.historico == 1


def test_transferido_interno_nao_entra_como_faltante():
    aluno = _aluno("mudou", "turma-nova")
    censo = _censo([aluno], [], excluir_faltantes={"mudou"})
    assert censo.alunos[0].excluido_transferencia is True
    assert censo.alunos[0].no_denominador is False
    assert censo.geral.matriculados == 0
    assert censo.geral.ausentes == 0


def test_duplicata_fica_com_a_prova_mais_recente():
    aluno = _aluno("a1", "t1", especial=True, nivel=1)
    provas = (_prova("reg-lp", LP, ("adap-antiga", 1), ("adap-nova", 1)),)
    censo = _censo(
        [aluno],
        [
            _res("a1", "adap-antiga", quando=1),
            _res("a1", "adap-nova", quando=5),
            _res("a1", "adap-nova", quando=3),
        ],
        universo="adap",
        provas=provas,
        class_tests=(ClassTestEntrada("t1", "reg-lp"),),
    )
    lp = _disc(censo.alunos[0], "lp")
    assert lp.situacao == "presente"
    assert lp.test_id_valido == "adap-nova"


def test_professor_nao_ve_aluno_de_outra_turma():
    alunos = [_aluno("dentro", "t1"), _aluno("fora", "t2")]
    censo = _censo(
        alunos,
        [_res("dentro", "reg-lp"), _res("dentro", "reg-mat"), _res("fora", "reg-lp"), _res("fora", "reg-mat")],
        class_ids_permitidos={"t1"},
    )
    assert set(_por_id(censo)) == {"dentro"}
    assert censo.geral.matriculados == 1


def test_agregado_soma_o_censo_e_nao_a_media_das_taxas():
    alunos = [
        _aluno("a", "t1", escola="e1"),
        _aluno("b", "t2", escola="e2"),
        _aluno("c", "t2", escola="e2"),
        _aluno("d", "t2", escola="e2"),
    ]
    resultados = [
        _res("a", "reg-lp"),
        _res("a", "reg-mat"),
        _res("b", "reg-lp"),
        _res("b", "reg-mat"),
    ]
    censo = _censo(alunos, resultados, universo="regular")
    assert censo.geral.matriculados == 4
    assert censo.geral.presentes_completos == 2
    assert censo.geral.percentual_completa == 50.0
    taxas = [item.percentual_completa for item in censo.por_escola]
    assert taxas == [100.0, 33.33]
    assert sum(item.matriculados for item in censo.por_escola) == censo.geral.matriculados
    assert sum(item.presentes_completos for item in censo.por_turma) == 2


def test_educacao_especial_sem_nivel_so_entra_em_todos_e_nao_conta_presenca():
    aluno = _aluno("sem", "t1", especial=True, nivel=None)
    resultados = [_res("sem", "reg-lp"), _res("sem", "reg-mat")]
    assert _censo([aluno], resultados, universo="regular").alunos == ()
    assert _censo([aluno], resultados, universo="adap").alunos == ()
    assert _censo([aluno], resultados, universo="regular_adap").alunos == ()
    censo = _censo([aluno], resultados, universo="todos")
    assert censo.geral.matriculados == 1
    assert _disc(censo.alunos[0], "lp").situacao == "inconsistente"
    assert censo.alunos[0].participacao_pelo_menos_uma is False
    assert censo.geral.ausentes == 0
    assert censo.geral.inconsistentes == 1
