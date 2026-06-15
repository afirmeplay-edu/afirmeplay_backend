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
