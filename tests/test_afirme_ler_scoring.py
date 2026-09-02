# -*- coding: utf-8 -*-
"""Cálculos canônicos de IFL / PL1–LF (MVP). Sem banco."""
from app.afirme_ler.scoring import FluencyScoring, StudentReadingInput
from app.afirme_ler.scoring.params import FluencyScoringParams
from app.afirme_ler.scoring.from_session import input_from_fluency_payload
from app.afirme_ler.services.fluency_metrics_service import build_fluency_record


def _presente(**kwargs) -> StudentReadingInput:
    defaults = dict(
        status="presente",
        palavras_corretas=0,
        silabacoes=0,
        soletracoes=0,
        desconhecidas_corretas=0,
        texto_palavras_lidas=0,
        texto_erros=0,
        tempo_segundos=60,
        prosodia_adequada=False,
        compreensao_acertos=0,
        compreensao_validas=4,
    )
    defaults.update(kwargs)
    return StudentReadingInput(**defaults)


def test_ppm_e_precisao_do_texto():
    score = FluencyScoring.score_student(
        _presente(texto_palavras_lidas=80, texto_erros=6, tempo_segundos=60)
    )
    assert score.palavras_corretas_texto == 74
    assert score.ppm == 74.0
    assert score.precisao == 92.5


def test_divisor_zero_retorna_zero():
    score = FluencyScoring.score_student(
        _presente(texto_palavras_lidas=0, texto_erros=0, tempo_segundos=0, compreensao_validas=0)
    )
    assert score.ppm == 0.0
    assert score.precisao == 0.0
    assert score.compreensao_pct == 0.0


def test_lf_exige_mais_de_65_corretas_e_precisao_minima():
    # 66 corretas no texto, mas precisão 82.5% → não LF
    baixo_prec = _presente(texto_palavras_lidas=80, texto_erros=14)
    assert FluencyScoring.score_student(baixo_prec).palavras_corretas_texto == 66
    assert FluencyScoring.score_student(baixo_prec).precisao == 82.5
    assert FluencyScoring.classificar(baixo_prec) != "LF"

    # 72 corretas e 90% → LF
    assert FluencyScoring.classificar(
        _presente(texto_palavras_lidas=80, texto_erros=8)
    ) == "LF"

    # exatamente 65 corretas, mesmo com boa precisão → não LF (usa >)
    limite = _presente(texto_palavras_lidas=70, texto_erros=5)
    assert FluencyScoring.score_student(limite).palavras_corretas_texto == 65
    assert FluencyScoring.classificar(limite) != "LF"


def test_lf_precisao_inclusiva_vs_estrita():
    data = _presente(texto_palavras_lidas=80, texto_erros=8)
    assert FluencyScoring.score_student(data).precisao == 90.0
    assert FluencyScoring.classificar(data) == "LF"
    assert (
        FluencyScoring.classificar(
            data, FluencyScoringParams(precisao_inclusiva=False)
        )
        != "LF"
    )


def test_li_e_queda_quando_desconhecidas_insuficientes():
    assert (
        FluencyScoring.classificar(
            _presente(palavras_corretas=11, desconhecidas_corretas=6)
        )
        == "LI"
    )
    queda = FluencyScoring.classificar(
        _presente(palavras_corretas=11, desconhecidas_corretas=5, silabacoes=2)
    )
    assert queda == "PL3"


def test_pl4_pl3_pl2_pl1():
    assert FluencyScoring.classificar(_presente(palavras_corretas=8)) == "PL4"
    assert FluencyScoring.classificar(_presente(palavras_corretas=10)) == "PL4"
    assert FluencyScoring.classificar(_presente(palavras_corretas=0, silabacoes=1)) == "PL3"
    assert FluencyScoring.classificar(_presente(palavras_corretas=0, soletracoes=1)) == "PL2"
    assert FluencyScoring.classificar(_presente()) == "PL1"


def test_limite_desconhecidas_pl4_nao_classifica():
    params = FluencyScoringParams(limite_desconhecidas_pl4=99)
    assert FluencyScoring.classificar(_presente(palavras_corretas=8), params) == "PL4"


def test_ausente_nao_classifica():
    score = FluencyScoring.score_student(
        _presente(status="ausente", texto_palavras_lidas=80, texto_erros=0)
    )
    assert score.avaliado is False
    assert score.nivel is None
    assert score.nivel_label == "Sem perfil"
    assert score.ppm == 0.0


def test_ifl_metade_pl1_metade_lf():
    scores = [
        FluencyScoring.score_student(_presente()),
        FluencyScoring.score_student(
            _presente(texto_palavras_lidas=80, texto_erros=8)
        ),
    ]
    agg = FluencyScoring.agregar(scores, previstos=2)
    assert agg.avaliados == 2
    assert agg.ifl == 5.0
    assert [band.code for band in agg.distribuicao] == list(FluencyScoring.LEVEL_CODES)
    assert len(agg.distribuicao) == 6


def test_participacao_avaliados_sobre_previstos():
    scores = [
        FluencyScoring.score_student(_presente()),
        FluencyScoring.score_student(_presente(status="ausente")),
    ]
    agg = FluencyScoring.agregar(scores, previstos=120)
    assert agg.avaliados == 1
    assert agg.participacao == 0.83


def test_pre_leitores_e_taxas_auxiliares():
    scores = [
        FluencyScoring.score_student(_presente()),
        FluencyScoring.score_student(
            _presente(
                texto_palavras_lidas=80,
                texto_erros=8,
                tempo_segundos=60,
                prosodia_adequada=True,
            )
        ),
    ]
    agg = FluencyScoring.agregar(scores, previstos=2)
    assert agg.pre_leitores_pct == 50.0
    assert agg.leitores_fluentes_pct == 50.0
    assert agg.velocidade_adequada_pct == 50.0
    assert agg.precisao_adequada_pct == 50.0
    assert agg.prosodia_adequada_pct == 50.0


def test_delta_e_evolucao():
    entrada = FluencyScoring.agregar(
        [FluencyScoring.score_student(_presente())], previstos=1
    )
    formativa = FluencyScoring.agregar(
        [
            FluencyScoring.score_student(
                _presente(texto_palavras_lidas=80, texto_erros=8)
            )
        ],
        previstos=1,
    )
    com_delta = FluencyScoring.aplicar_delta(formativa, entrada)
    lf = next(band for band in com_delta.distribuicao if band.code == "LF")
    pl1 = next(band for band in com_delta.distribuicao if band.code == "PL1")
    assert lf.percentual_anterior == 0.0
    assert lf.delta == 100.0
    assert pl1.delta == -100.0
    assert FluencyScoring.evolucao("LF", "PL1") == "avanco"
    assert FluencyScoring.evolucao("PL1", "LI") == "regressao"
    assert FluencyScoring.evolucao("LI", "LI") == "manutencao"
    assert FluencyScoring.evolucao("LI", None) is None
    assert FluencyScoring.ifl_do_nivel("LI") == 6.0
    assert FluencyScoring.ifl_do_nivel(None) is None


def test_agregar_por_reusa_a_mesma_formula():
    a = FluencyScoring.score_student(_presente())
    b = FluencyScoring.score_student(
        _presente(texto_palavras_lidas=80, texto_erros=8)
    )
    por_escola = FluencyScoring.agregar_por(
        [("e1", a), ("e2", b)],
        {"e1": 1, "e2": 1},
    )
    assert por_escola["e1"].ifl == 0.0
    assert por_escola["e2"].ifl == 10.0


def test_adapter_conta_markings_incluindo_silabou():
    data = input_from_fluency_payload(
        status="finalizada",
        fluency_data={
            "prosodyLevel": 4,
            "q1": {
                "wordsRead": 13,
                "errorsCount": 1,
                "readingTimeSeconds": 60,
                "markings": (
                    [{"index": i, "word": "ok", "status": "acertou"} for i in range(11)]
                    + [
                        {"index": 11, "word": "si", "status": "silabou"},
                        {"index": 12, "word": "so", "status": "soletrou"},
                    ]
                ),
            },
            "q2": {
                "wordsRead": 6,
                "errorsCount": 0,
                "readingTimeSeconds": 60,
                "markings": [
                    {"index": i, "word": "x", "status": "acertou"} for i in range(6)
                ],
            },
            "q3": {
                "wordsRead": 20,
                "lastWordPosition": 20,
                "errorsCount": 2,
                "readingTimeSeconds": 60,
            },
        },
        comprehension_correct=3,
        comprehension_total=4,
        prosody_level=4,
    )
    score = FluencyScoring.score_student(data)
    assert score.status == "presente"
    assert score.palavras_corretas == 11
    assert score.silabacoes == 1
    assert score.soletracoes == 1
    assert score.desconhecidas_corretas == 6
    assert score.texto_palavras_lidas == 20
    assert score.texto_erros == 2
    assert score.prosodia_adequada is True
    assert score.nivel == "LI"


def test_sessao_aceita_marking_silabou():
    record, _ = build_fluency_record(
        {
            "q1": {
                "wordsRead": 2,
                "errorsCount": 0,
                "readingTimeSeconds": 60,
                "markings": [
                    {"index": 0, "word": "casa", "status": "acertou"},
                    {"index": 1, "word": "bola", "status": "silabou"},
                ],
            }
        }
    )
    assert record["q1"]["markings"][1]["status"] == "silabou"
