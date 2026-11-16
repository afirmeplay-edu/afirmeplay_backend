# -*- coding: utf-8 -*-
"""ADAP 3 fora da Lista de Frequência de prova/cartão regular (helper central)."""
from app.services.adap_objetivo import (
    ADAP_OBJETIVO_EXCLUIDO,
    ADAP_OBJETIVO_NIVEIS,
    e_adap_excluido_prova_objetiva,
    prova_direcionada_adap3,
)


def test_helper_objetivo_so_1_e_2():
    assert ADAP_OBJETIVO_NIVEIS == (1, 2)
    assert ADAP_OBJETIVO_EXCLUIDO == 3
    assert e_adap_excluido_prova_objetiva(3) is True
    assert e_adap_excluido_prova_objetiva(1) is False
    assert e_adap_excluido_prova_objetiva(2) is False
    assert e_adap_excluido_prova_objetiva(None) is False


def test_cartao_regular_nao_inclui_adap3():
    assert prova_direcionada_adap3(gabarito_level=None) is False


def test_cartao_adap1_e_adap2_nao_incluem_flag_adap3():
    assert prova_direcionada_adap3(gabarito_level=1) is False
    assert prova_direcionada_adap3(gabarito_level=2) is False


def test_cartao_adap3_inclui():
    assert prova_direcionada_adap3(gabarito_level=3) is True


def test_prova_online_regular_nao_inclui_adap3():
    assert prova_direcionada_adap3(grade_name="1º Ano") is False


def test_prova_online_adap3_inclui():
    assert prova_direcionada_adap3(grade_name="ADAP 3") is True
    assert prova_direcionada_adap3(grade_name="Suporte 3") is True


def test_prova_online_adap1_nao_liga_flag_adap3():
    assert prova_direcionada_adap3(grade_name="ADAP 1") is False


def test_sem_contexto_flag_false():
    assert prova_direcionada_adap3() is False
