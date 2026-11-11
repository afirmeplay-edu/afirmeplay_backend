# -*- coding: utf-8 -*-
import pytest

from app.utils.render_math import render_math_in_html, render_math_in_text


def test_render_math_in_text_inline_fraction():
    result = render_math_in_text(r'$\frac{1}{3}$')
    assert 'data:image/png;base64,' in result
    assert 'math-inline-img' in result
    assert r'$\frac{1}{3}$' not in result


def test_render_math_in_text_display_mode():
    result = render_math_in_text(r'$$\frac{a}{b}$$')
    assert 'math-display-img' in result
    assert r'$$\frac{a}{b}$$' not in result


def test_render_math_in_text_invalid_latex_keeps_delimiter():
    result = render_math_in_text(r'$\notavalidcommand{xyz}$')
    assert result == r'$\notavalidcommand{xyz}$'


def test_render_math_in_text_plain_text_unchanged():
    assert render_math_in_text('Apenas texto') == 'Apenas texto'


def test_render_math_in_text_ignores_currency_rs_pairs():
    """Dois R$ no mesmo parágrafo não podem virar delimitador inline."""
    text = (
        'Marina fez uma compra de R$ 103,75 no supermercado. '
        'Para pagar essa compra, ela utilizou R$ 55,50 em dinheiro.'
    )
    result = render_math_in_text(text)
    assert result == text
    assert '103,75' in result
    assert '55,50' in result
    assert 'math-rendered' not in result
    assert 'data:image/png' not in result


def test_render_math_in_html_ignores_currency_rs_pairs():
    html = (
        '<p>Marina fez uma compra de R$ 103,75 no supermercado. '
        'Para pagar essa compra, ela utilizou R$ 55,50 em dinheiro '
        'e pagou o restante com o cartão de crédito.</p>'
    )
    result = render_math_in_html(html)
    assert 'R$ 103,75' in result
    assert 'R$ 55,50' in result
    assert 'math-rendered' not in result


def test_render_math_in_text_ignores_us_dollar_prefix():
    text = 'O preço era US$ 10 e depois US$ 20.'
    assert render_math_in_text(text) == text


def test_render_math_in_text_keeps_real_formula_beside_currency():
    text = r'Com R$ 10,00 restam $\frac{1}{2}$ do total.'
    result = render_math_in_text(text)
    assert 'R$ 10,00' in result
    assert 'math-inline-img' in result
    assert r'$\frac{1}{2}$' not in result


def test_render_math_in_html_preserves_tags():
    html = '<p>A fração $x^{2}$ está <strong>aqui</strong>.</p>'
    result = render_math_in_html(html)
    assert result.startswith('<p>')
    assert '<strong>aqui</strong>' in result
    assert 'math-inline-img' in result
    assert '$x^{2}$' not in result


def test_render_math_in_html_skips_latex_inside_tags():
    html = '<img src="/x" alt="$fake$" />'
    result = render_math_in_html(html)
    assert result == html
