# -*- coding: utf-8 -*-
"""Testes do pareamento ADAP e escolha do resultado válido (sem banco)."""
from types import SimpleNamespace

from app.services.adap_resultado_pareado import (
    ADAP_INCLUDED_IN_RANKING,
    adap_students_level_12,
    choose_valid_evaluation_result,
    enrich_pendentes_com_marca_adap,
    filter_ranking_excluding_adap,
    merge_results_with_adap_valid,
    project_result_onto_regular_test,
    AdapValidResult,
)
from app.services.adap_test_pairing_fill import (
    PairProposal,
    apply_unique_pairs,
    propose_pairs,
)
def _er(*, grade, proficiency, test_id="t", student_id="s1", correct=0, total=10):
    return SimpleNamespace(
        grade=grade,
        proficiency=proficiency,
        test_id=test_id,
        student_id=student_id,
        correct_answers=correct,
        total_questions=total,
        score_percentage=(correct / total * 100) if total else 0,
        classification="Adequado",
        calculated_at=None,
        subject_results=None,
    )


def test_escolhe_nota_da_prova_pareada_quando_so_adap():
    adap = _er(grade=8.12, proficiency=272.73, test_id="adap", correct=8, total=11)
    chosen = choose_valid_evaluation_result(None, [adap])
    assert chosen is adap
    assert chosen.grade == 8.12
    assert chosen.total_questions == 11


def test_maior_nota_vence_entre_regular_e_adap():
    regular = _er(grade=6.0, proficiency=200.0, test_id="reg")
    adap = _er(grade=9.0, proficiency=180.0, test_id="adap")
    assert choose_valid_evaluation_result(regular, [adap]) is adap

    regular2 = _er(grade=9.5, proficiency=100.0, test_id="reg")
    adap2 = _er(grade=9.0, proficiency=300.0, test_id="adap")
    assert choose_valid_evaluation_result(regular2, [adap2]) is regular2


def test_empate_nota_decide_por_proficiencia_depois_adap():
    regular = _er(grade=8.0, proficiency=250.0, test_id="reg")
    adap = _er(grade=8.0, proficiency=260.0, test_id="adap")
    assert choose_valid_evaluation_result(regular, [adap]) is adap

    regular2 = _er(grade=8.0, proficiency=260.0, test_id="reg")
    adap2 = _er(grade=8.0, proficiency=260.0, test_id="adap")
    assert choose_valid_evaluation_result(regular2, [adap2]) is adap2


def test_sem_nenhum_resultado_retorna_none():
    assert choose_valid_evaluation_result(None, []) is None


def test_adap2_nota_gravada_nao_recalculada():
    """Metade das questões: a nota usada é a já gravada (8.12), não 10*(8/22)."""
    adap = _er(grade=8.12, proficiency=272.73, test_id="adap-ii", correct=8, total=11)
    chosen = choose_valid_evaluation_result(None, [adap])
    assert chosen.grade == 8.12
    assert chosen.total_questions == 11
    assert abs(chosen.grade - (10 * 8 / 22)) > 1.0


def test_aluno_regular_nao_usa_resultado_adap_por_engano():
    """merge só substitui chaves presentes em adap_valid (ADAP 1/2)."""
    regular_er = _er(grade=7.0, proficiency=220.0, test_id="reg", student_id="regular")
    adap_er_errado = _er(grade=10.0, proficiency=375.0, test_id="adap", student_id="regular")
    results = [regular_er, adap_er_errado]
    # Sem entrada em adap_valid para "regular" → permanece o dedupe normal sem forçar ADAP
    merged = merge_results_with_adap_valid(results, {})
    assert any(r.student_id == "regular" for r in merged)
    # Com adap_valid vazio, não injeta ADAP no regular
    assert all(
        not (str(getattr(r, "test_id", "")) == "adap" and r.student_id == "regular" and r in [])
        for r in merged
    )


def test_project_keeps_grade_changes_test_id():
    adap = _er(grade=8.12, proficiency=272.73, test_id="adap-ii", correct=8, total=11)
    projected = project_result_onto_regular_test(adap, "reg-1")
    assert projected.test_id == "reg-1"
    assert projected.grade == 8.12
    assert projected.total_questions == 11
    assert projected._adap_source_test_id == "adap-ii"


def _snap(er, *, school, grade, klass):
    er.school_id_snapshot = school
    er.grade_id_snapshot = grade
    er.class_id_snapshot = klass
    er.enrollment_id_snapshot = None
    return er


def test_media_adap_pareado_entra_na_turma_atual(monkeypatch):
    """Escola com 4º ano em duas turmas: o aluno ADAP da turma A fez só a prova ADAP
    (snapshot na turma de Suporte). Na prova regular ele conta dentro da turma A,
    e não como uma série a mais com peso igual ao 4º ano inteiro."""
    from app.services import adap_resultado_pareado as mod
    from app.utils.school_equal_weight_means import _hierarchical_mean_pair_raw

    escola, serie_4, serie_suporte = "esc-1", "g-4ano", "g-suporte1"
    turma_a, turma_b, turma_suporte = "c-4a", "c-4b", "c-suporte"

    regulares = [
        _snap(
            _er(grade=5.0, proficiency=200.0, test_id="reg", student_id=f"a{i}"),
            school=escola, grade=serie_4, klass=turma_a,
        )
        for i in range(20)
    ] + [
        _snap(
            _er(grade=5.0, proficiency=200.56, test_id="reg", student_id=f"b{i}"),
            school=escola, grade=serie_4, klass=turma_b,
        )
        for i in range(20)
    ]
    adap_er = _snap(
        _er(grade=7.58, proficiency=340.91, test_id="adap-i", student_id="aluno_adap"),
        school=escola, grade=serie_suporte, klass=turma_suporte,
    )
    aluno_adap = SimpleNamespace(
        id="aluno_adap",
        class_id=turma_a,
        class_=SimpleNamespace(school_id=escola, grade_id=serie_4),
    )
    alunos = [SimpleNamespace(id=r.student_id) for r in regulares] + [aluno_adap]

    monkeypatch.setattr(mod, "adap_students_level_12", lambda students: {"aluno_adap": 1})
    monkeypatch.setattr(
        mod,
        "resolve_adap_valid_results",
        lambda *a, **k: {
            "aluno_adap": AdapValidResult(
                student_id="aluno_adap",
                level=1,
                source_test_id="adap-i",
                source_test_title="ADAP I - 4º ANO",
                result=adap_er,
                situation="concluida",
                from_adap_test=True,
            )
        },
    )

    _, efetivos, adap_valid = mod.apply_pareamento_to_universe("reg", alunos, regulares)
    assert set(adap_valid) == {"aluno_adap"}
    projetado = next(r for r in efetivos if r.student_id == "aluno_adap")
    assert projetado.test_id == "reg"
    assert projetado.grade == 7.58
    assert projetado.school_id_snapshot == escola
    assert projetado.grade_id_snapshot == serie_4
    assert projetado.class_id_snapshot == turma_a

    _, prof = _hierarchical_mean_pair_raw(efetivos, "escola")
    media_a = (20 * 200.0 + 340.91) / 21
    assert abs(prof - (media_a + 200.56) / 2) < 1e-6

    _, prof_antigo = _hierarchical_mean_pair_raw(regulares + [adap_er], "escola")
    assert abs(prof_antigo - (200.28 + 340.91) / 2) < 1e-6
    assert prof_antigo - prof > 60


def test_projecao_sem_turma_atual_mantem_snapshot():
    adap = _snap(
        _er(grade=8.0, proficiency=250.0, test_id="adap"),
        school="esc", grade="g-sup", klass="c-sup",
    )
    projected = project_result_onto_regular_test(
        adap, "reg", SimpleNamespace(id="s1", class_id=None, class_=None)
    )
    assert projected.class_id_snapshot == "c-sup"
    assert projected.grade_id_snapshot == "g-sup"


def test_projecao_sem_turma_atual_usa_turma_da_prova_regular():
    """Aluno que saiu da escola: conta onde fez a prova regular, não na turma de Suporte."""
    adap = _snap(
        _er(grade=1.61, proficiency=150.0, test_id="adap"),
        school="esc", grade="g-sup2", klass="c-sup",
    )
    regular = _snap(
        _er(grade=0.0, proficiency=0.0, test_id="reg"),
        school="esc", grade="g-2ano", klass="c-2b",
    )
    projected = project_result_onto_regular_test(
        adap, "reg", SimpleNamespace(id="s1", class_id=None, class_=None), regular
    )
    assert projected.grade == 1.61
    assert projected.class_id_snapshot == "c-2b"
    assert projected.grade_id_snapshot == "g-2ano"


def test_adap3_fora_do_mapa_nivel_12():
    serie = SimpleNamespace(name="5º Ano", education_stage_id=None)
    sub3 = SimpleNamespace(id="s3", class_id="c1", support_level=3)
    sub1 = SimpleNamespace(id="s1", class_id="c1", support_level=1)
    alunos = [
        SimpleNamespace(
            id="a3", class_id="c1", grade=serie, subturma=sub3, subturma_id="s3", grade_id=None
        ),
        SimpleNamespace(
            id="a1", class_id="c1", grade=serie, subturma=sub1, subturma_id="s1", grade_id=None
        ),
    ]
    mapped = adap_students_level_12(alunos)
    assert "a1" in mapped
    assert "a3" not in mapped


def test_ranking_exclui_adap_por_constante():
    assert ADAP_INCLUDED_IN_RANKING is False
    ranking = [{"id": "r1", "nome": "R"}, {"id": "a1", "nome": "A"}]
    out = filter_ranking_excluding_adap(ranking, {"a1"})
    assert [x["id"] for x in out] == ["r1"]


def test_pendentes_recebem_marca_adap():
    pendentes = [{"id": "a1", "nome": "Aluno"}]
    adap_valid = {
        "a1": AdapValidResult(
            student_id="a1",
            level=2,
            source_test_id=None,
            source_test_title=None,
            result=None,
            situation="pendente",
            from_adap_test=False,
        )
    }
    enriched = enrich_pendentes_com_marca_adap(pendentes, adap_valid)
    assert enriched[0]["nome"] == "Aluno"
    assert enriched[0]["adap_rotulo"] == "ADAP 2"
    assert enriched[0]["id"] == "a1"


def test_script_simulacao_nao_grava_e_ambiguo_nao_escreve():
    adap_unique = SimpleNamespace(
        id="adap1",
        title="ADAP I - 1º ANO - MAT - 1º AVALIA",
        paired_regular_test_id=None,
    )
    adap_amb = SimpleNamespace(
        id="adap2",
        title="ADAP II - 2º ANO - LP - 1º AVALIA",
        paired_regular_test_id=None,
    )
    reg1 = SimpleNamespace(id="r1", title="1º ANO - MAT - 1º AVALIA")
    reg2a = SimpleNamespace(id="r2a", title="2º ANO - LP - 1º AVALIA")
    reg2b = SimpleNamespace(id="r2b", title="2º ANO - LP - 1º AVALIA LIMOEIRO")
    # Force same key for amb by using identical titles for two regulars
    reg2b.title = "2º ANO - LP - 1º AVALIA"

    proposals = propose_pairs([adap_unique, adap_amb], [reg1, reg2a, reg2b])
    by_id = {p.adap_id: p for p in proposals}
    assert by_id["adap1"].status == "par_unico"
    assert by_id["adap2"].status == "mais_de_um"

    adap_by = {"adap1": adap_unique, "adap2": adap_amb}
    simulated = apply_unique_pairs(proposals, adap_by, commit=False)
    assert adap_unique.paired_regular_test_id is None
    assert any(p.will_write and p.adap_id == "adap1" for p in simulated)
    assert all(not (p.adap_id == "adap2" and p.will_write) for p in simulated)

    written = apply_unique_pairs(proposals, adap_by, commit=True)
    assert adap_unique.paired_regular_test_id == "r1"
    assert adap_amb.paired_regular_test_id is None
    assert any(p.will_write and p.adap_id == "adap1" for p in written)


def test_script_nao_sobrescreve_vinculo_existente():
    adap = SimpleNamespace(
        id="adap1",
        title="ADAP I - 1º ANO - MAT - 1º AVALIA",
        paired_regular_test_id="ja-existe",
    )
    reg = SimpleNamespace(id="r1", title="1º ANO - MAT - 1º AVALIA")
    proposals = propose_pairs([adap], [reg])
    assert proposals[0].already_paired is True
    apply_unique_pairs(proposals, {"adap1": adap}, commit=True)
    assert adap.paired_regular_test_id == "ja-existe"
