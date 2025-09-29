# -*- coding: utf-8 -*-
"""
Gerador de PDF com template dinâmico para relatórios de avaliação
Baseado no layout desenvolvido em test_pdf_layout.py com dados dinâmicos do report_routes.py
"""

from io import BytesIO
from datetime import datetime
from typing import Dict, Any, List
import logging

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageTemplate, Frame, PageBreak, KeepTogether
from reportlab.platypus import BaseDocTemplate
from reportlab.pdfgen import canvas


def _header(canvas: canvas.Canvas, doc, logo_esq=None, logo_dir=None):
    """Função para desenhar cabeçalho com logos em todas as páginas"""
    # Por enquanto, não desenhar nada para evitar erros com logos
    pass


def gerar_pdf_com_template_dinamico(test, total_alunos: Dict, niveis_aprendizagem: Dict, 
                                  proficiencia: Dict, nota_geral: Dict, acertos_habilidade: Dict, 
                                  ai_analysis: Dict, avaliacao_data: Dict, scope_type: str = 'all') -> bytes:
    """
    Gera arquivo PDF usando reportlab com layout do template e dados dinâmicos
    
    Args:
        test: Objeto Test da avaliação
        total_alunos: Dados de participação dos alunos
        niveis_aprendizagem: Dados de níveis de aprendizagem por disciplina
        proficiencia: Dados de proficiência por disciplina
        nota_geral: Dados de notas por disciplina
        acertos_habilidade: Dados de acertos por habilidade
        ai_analysis: Análise da IA
        avaliacao_data: Dados básicos da avaliação
        scope_type: Tipo de escopo ('school', 'city', 'all') - determina se mostra 'TURMA' ou 'ESCOLA'
    
    Returns:
        bytes: Conteúdo do PDF gerado
    """
    try:
        # Criar buffer para o PDF
        buffer = BytesIO()
        
        # Criar documento PDF com margens
        doc = BaseDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=25*mm,
            leftMargin=25*mm,
            topMargin=30*mm,
            bottomMargin=25*mm
        )
        
        # Criar template de página
        frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
        page_template = PageTemplate('normal', [frame], onPage=_header)
        doc.addPageTemplates([page_template])
        
        # Obter informações dinâmicas da escola e município
        escola_nome, municipio_nome, uf = _obter_dados_escola_municipio(test)
        
        # Determinar período atual
        mes_atual, ano_atual, periodo = _obter_dados_periodo()
        
        # Preparar elementos do PDF
        elements = []
        
        # ===== CAPA =====
        _adicionar_capa(elements, test.title, escola_nome, municipio_nome, uf, mes_atual, ano_atual, scope_type)
        
        # ===== SUMÁRIO =====
        _adicionar_sumario(elements)
        
        # ===== APRESENTAÇÃO E CONSIDERAÇÕES GERAIS =====
        _adicionar_apresentacao_consideracoes(elements, test.title, municipio_nome, uf, 
                                            total_alunos, avaliacao_data, scope_type)
        
        # ===== PARTICIPAÇÃO =====
        _adicionar_participacao(elements, total_alunos, test.title, scope_type, ai_analysis)
        
        # ===== NÍVEIS DE APRENDIZAGEM =====
        _adicionar_niveis_aprendizagem(elements, niveis_aprendizagem, test.title, scope_type)
        
        # ===== PROFICIÊNCIA E NOTAS =====
        _adicionar_proficiencia_notas(elements, proficiencia, nota_geral, test.title, scope_type, ai_analysis)
        
        # ===== ACERTOS POR HABILIDADE =====
        _adicionar_acertos_habilidade(elements, acertos_habilidade, test.title, scope_type)
        
        # Construir PDF
        print("=== INICIANDO CONSTRUÇÃO DO PDF DINÂMICO ===")
        print(f"Total de elements: {len(elements)}")
        doc.build(elements)
        print("PDF dinâmico construído com sucesso")
        
        # Obter conteúdo do buffer
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        buffer.close()
        print(f"PDF dinâmico gerado com {len(pdf_content)} bytes")
        
        return pdf_content
        
    except Exception as e:
        print(f"ERRO ao gerar PDF dinâmico: {str(e)}")
        import traceback
        print(f"Traceback completo: {traceback.format_exc()}")
        logging.error(f"Erro ao gerar PDF dinâmico: {str(e)}")
        raise


def _obter_dados_escola_municipio(test):
    """Obtém dados da escola e município"""
    escola_nome = "Escola não identificada"
    municipio_nome = "Município não identificado"
    uf = "AL"
    
    try:
        if test.class_tests:
            from app.models.studentClass import Class
            first_class_test = test.class_tests[0]
            first_class = Class.query.get(first_class_test.class_id)
            if first_class and first_class.school:
                escola_nome = first_class.school.name
                if first_class.school.city:
                    municipio_nome = first_class.school.city.name
                    uf = first_class.school.city.state or "AL"
    except Exception as e:
        logging.warning(f"Erro ao obter dados da escola/município: {str(e)}")
    
    return escola_nome, municipio_nome, uf


def _obter_dados_periodo():
    """Obtém dados do período atual"""
    now = datetime.now()
    
    # Mapear meses para português
    meses_portugues = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    
    mes_atual = meses_portugues[now.month]
    ano_atual = now.year
    periodo = f"{ano_atual}.1"
    
    return mes_atual, ano_atual, periodo


def _obter_estilos():
    """Define e retorna os estilos do template"""
    styles = getSampleStyleSheet()
    
    # Cores do template
    COR_AZUL_ESCURO = colors.HexColor('#1f4e79')
    COR_CINZA_CLARO = colors.HexColor('#d9d9d9')
    
    # Estilo para título da capa
    capa_title_style = ParagraphStyle(
        'CapaTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=30,
        spaceBefore=100,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulo da capa
    capa_subtitle_style = ParagraphStyle(
        'CapaSubtitle',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=50,
        fontName='Helvetica'
    )
    
    # Estilo para rodapé da capa
    capa_footer_style = ParagraphStyle(
        'CapaFooter',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceBefore=200,
        fontName='Helvetica'
    )
    
    # Estilo para título do sumário
    sumario_title_style = ParagraphStyle(
        'SumarioTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=30,
        spaceBefore=50,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para itens do sumário
    sumario_item_style = ParagraphStyle(
        'SumarioItem',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=8,
        leftIndent=0,
        fontName='Helvetica'
    )
    
    # Estilo para subitens do sumário
    sumario_subitem_style = ParagraphStyle(
        'SumarioSubitem',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=6,
        leftIndent=40,
        firstLineIndent=-20,
        fontName='Helvetica'
    )
    
    # Estilo para títulos de página
    titulo_pagina_style = ParagraphStyle(
        'TituloPagina',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para parágrafos com primeira linha indentada
    paragrafo_indentado_style = ParagraphStyle(
        'ParagrafoIndentado',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=12,
        spaceBefore=6,
        firstLineIndent=36,
        fontName='Helvetica',
        leading=14
    )
    
    # Estilo para listas
    lista_style = ParagraphStyle(
        'Lista',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=8,
        spaceBefore=4,
        leftIndent=72,
        fontName='Helvetica',
        leading=14
    )
    
    # Estilo para títulos principais de seção
    titulo_principal_style = ParagraphStyle(
        'TituloPrincipal',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=COR_AZUL_ESCURO,
        alignment=TA_LEFT,
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulos de tabela
    subtitulo_tabela_style = ParagraphStyle(
        'SubtituloTabela',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=8,
        spaceBefore=8,
        fontName='Helvetica-Bold',
        backColor=COR_CINZA_CLARO
    )
    
    # Estilo para resumos
    resumo_style = ParagraphStyle(
        'Resumo',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_LEFT,
        leftIndent=0,
        spaceAfter=6,
        spaceBefore=4,
        leading=12,
        fontName='Helvetica'
    )
    
    # Estilo para células de tabela com alinhamento à esquerda
    table_cell_left_style = ParagraphStyle(
        'TableCellLeft',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_LEFT,
        leftIndent=0,
        spaceAfter=0,
        spaceBefore=0,
        leading=10,
        fontName='Helvetica'
    )
    
    return {
        'capa_title_style': capa_title_style,
        'capa_subtitle_style': capa_subtitle_style,
        'capa_footer_style': capa_footer_style,
        'sumario_title_style': sumario_title_style,
        'sumario_item_style': sumario_item_style,
        'sumario_subitem_style': sumario_subitem_style,
        'titulo_pagina_style': titulo_pagina_style,
        'paragrafo_indentado_style': paragrafo_indentado_style,
        'lista_style': lista_style,
        'titulo_principal_style': titulo_principal_style,
        'subtitulo_tabela_style': subtitulo_tabela_style,
        'resumo_style': resumo_style,
        'table_cell_left_style': table_cell_left_style
    }


def _adicionar_capa(elements: List, avaliacao_titulo: str, escola_nome: str, 
                   municipio_nome: str, uf: str, mes_atual: str, ano_atual: int, scope_type: str = 'all'):
    """Adiciona a capa do relatório"""
    estilos = _obter_estilos()
    
    # Título principal - ajustado conforme o escopo
    if scope_type == 'city':
        # Para relatório por município: "Relatório da {Nome da avaliação} Da rede Municipal de Ensino {nome do municipio} / {Estado}"
        titulo_principal = f"Relatório da {avaliacao_titulo} Da rede Municipal de Ensino {municipio_nome} / {uf}"
    else:
        # Para relatório por escola: título original
        titulo_principal = f"Relatório da Avaliação {avaliacao_titulo} da rede Municipal de Ensino {municipio_nome} / {uf}"
    
    elements.append(Paragraph(titulo_principal, estilos['capa_title_style']))
    
    # Subtítulo - ajustado conforme o escopo
    elements.append(Spacer(1, 40))  # Espaço entre título e subtítulo
    
    if scope_type == 'city':
        # Para relatório por município: apenas "MUNICIPAL" em negrito maiúsculo
        subtitulo = "<b>MUNICIPAL</b>"
        elements.append(Paragraph(subtitulo, estilos['capa_subtitle_style']))
    else:
        # Para relatório por escola: nome da escola
        elements.append(Paragraph(escola_nome, estilos['capa_subtitle_style']))
    
    # Rodapé (mês/ano) - permanece igual
    elements.append(Paragraph(f"{mes_atual} / {ano_atual}", estilos['capa_footer_style']))
    
    # Nova página
    elements.append(PageBreak())


def _adicionar_sumario(elements: List):
    """Adiciona o sumário do relatório"""
    estilos = _obter_estilos()
    
    # Título do sumário
    elements.append(Paragraph("SUMÁRIO", estilos['sumario_title_style']))
    
    # Itens do sumário com variáveis dinâmicas (sem números de páginas marcados com <<)
    elementos_sumario = [
        ("1. APRESENTAÇÃO", ""),
        ("2. CONSIDERAÇÕES GERAIS", ""),
        ("3. PARTICIPAÇÃO DA REDE NO PROCESSO DA AVALIAÇÃO DIAGNÓSTICA", ""),
        ("4. RENDIMENTO POR ESCOLA", ""),
        ("4.1 PROFICIÊNCIA POR UNIDADE DE ENSINO", ""),
        ("4.2 NOTA POR UNIDADE DE ENSINO", ""),
        ("4.3 ACERTOS POR HABILIDADE POR UNIDADE DE ENSINO", ""),
        ("4.4 ACERTOS POR HABILIDADE POR UNIDADE DE ENSINO", "")
    ]
    
    # Criar sumário usando Paragraphs individuais para melhor controle de indentação
    for item, pagina in elementos_sumario:
        numero = item.split()[0]
        if numero != "4." and numero.startswith("4.") and numero.count(".") == 1:   # detecta "4.1", "4.2", etc.
            texto = f"{item} {pagina}" if pagina else item
            elements.append(Paragraph(texto, estilos['sumario_subitem_style']))
        else:
            texto = f"{item} {pagina}" if pagina else item
            elements.append(Paragraph(texto, estilos['sumario_item_style']))
    
    # Nova página
    elements.append(PageBreak())


def _adicionar_apresentacao_consideracoes(elements: List, avaliacao_titulo: str, 
                                        municipio_nome: str, uf: str, 
                                        total_alunos: Dict, avaliacao_data: Dict, scope_type: str = 'all'):
    """Adiciona as páginas de apresentação e considerações gerais"""
    estilos = _obter_estilos()
    
    # 1. APRESENTAÇÃO
    elements.append(Paragraph("1. APRESENTAÇÃO", estilos['titulo_pagina_style']))
    
    # Obter dados dinâmicos
    total_avaliados = total_alunos.get('total_geral', {}).get('avaliados', 0)
    percentual_avaliados = total_alunos.get('total_geral', {}).get('percentual', 0)
    disciplinas_str = ', '.join(avaliacao_data.get('disciplinas', ['Disciplina Geral']))
    
    # Parágrafo principal com dados dinâmicos - ajustado conforme o escopo
    if scope_type == 'city':
        # Para relatório municipal: mostrar "Município X" ao invés de "9º ano"
        paragrafo_principal = f"""Este relatório apresenta os resultados da <b>{avaliacao_titulo}</b> <b>{municipio_nome}</b> – <b>{uf}</b> referente ao <b>Município {municipio_nome}</b> de <b>2025</b>. Foram avaliados <b>{total_avaliados}</b> alunos, o que corresponde a <b>{percentual_avaliados}%</b> do total de estudantes dessas séries."""
    else:
        # Para relatório por escola: mostrar nome da escola ao invés de apenas "Escola"
        # Precisamos obter o nome da escola - vamos buscar da primeira turma
        escola_nome = "Escola"
        if total_alunos.get('por_turma'):
            # Se temos dados por turma, pegar o nome da escola da primeira turma
            # Assumindo que todas as turmas são da mesma escola
            escola_nome = "Escola"  # Fallback padrão
        elif total_alunos.get('por_escola'):
            # Se temos dados por escola, pegar o nome da primeira escola
            escola_nome = total_alunos['por_escola'][0].get('escola', 'Escola')
        
        paragrafo_principal = f"""Este relatório apresenta os resultados da <b>{avaliacao_titulo}</b> <b>{municipio_nome}</b> – <b>{uf}</b> referente ao <b>9º ano</b> de <b>2025</b> da <b>{escola_nome}</b>. Foram avaliados <b>{total_avaliados}</b> alunos, o que corresponde a <b>{percentual_avaliados}%</b> do total de estudantes dessas séries."""
    
    elements.append(Paragraph(paragrafo_principal, estilos['paragrafo_indentado_style']))
    
    # Subtítulo
    elements.append(Paragraph("Para a análise, utilizamos:", estilos['paragrafo_indentado_style']))
    
    # Lista
    elements.append(Paragraph("• Frequência absoluta (número de alunos)", estilos['lista_style']))
    elements.append(Paragraph("• Frequência relativa (percentual)", estilos['lista_style']))
    elements.append(Paragraph("• Média aritmética simples", estilos['lista_style']))
    
    # Parágrafos adicionais com dados dinâmicos
    paragrafo_disciplinas = f"""As competências avaliadas foram as disciplinas de <b>{disciplinas_str}</b>, com dados apresentados por turma, por série e consolidado para toda a rede. Gráficos nominais por aluno e rendimento de cada turma estão disponíveis na <b>Plataforma InnovPlay</b>, nas respectivas unidades de ensino."""
    
    elements.append(Paragraph(paragrafo_disciplinas, estilos['paragrafo_indentado_style']))
    
    paragrafo_escala = """A escala de cores das médias variou do <b>vermelho (0)</b> ao <b>verde (10)</b>. Para identificar descritores/habilidades com índice de erro superior a 40%, registramos esses itens em destaque <b>vermelho</b>, sinalizando prioridades de intervenção pedagógica."""
    
    elements.append(Paragraph(paragrafo_escala, estilos['paragrafo_indentado_style']))
    
    # 2. CONSIDERAÇÕES GERAIS
    elements.append(Paragraph("2. CONSIDERAÇÕES GERAIS", estilos['titulo_pagina_style']))
    
    consideracao1 = """Antes de olharmos os resultados é importante nos atentarmos que cada escola tem suas especificidades, assim como cada turma. Existem resultados que só serão explicados considerando estas especificidades."""
    
    elements.append(Paragraph(consideracao1, estilos['paragrafo_indentado_style']))
    
    consideracao2 = """As turmas são únicas e, portanto, a observação das necessidades de cada turma deve ser analisada através do sistema."""
    
    elements.append(Paragraph(consideracao2, estilos['paragrafo_indentado_style']))
    
    # Nova página
    elements.append(PageBreak())


def _adicionar_participacao(elements: List, total_alunos: Dict, avaliacao_titulo: str, scope_type: str = 'all', ai_analysis: Dict = None):
    """Adiciona a seção de participação"""
    estilos = _obter_estilos()
    
    # Determinar rótulo da coluna baseado no escopo
    if scope_type == 'city':
        coluna_label = "ESCOLA"
        dados_key = "por_escola"
        nome_key = "escola"
    else:
        coluna_label = "SÉRIE/TURNO"
        dados_key = "por_turma"
        nome_key = "turma"
    
    # Título principal
    elements.append(Paragraph(f"1. PARTICIPAÇÃO DA REDE NO PROCESSO DA {avaliacao_titulo.upper()}", 
                             estilos['titulo_principal_style']))
    
    # Subtítulo da tabela
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f"TOTAL DE ALUNOS QUE REALIZARAM A {avaliacao_titulo.upper()}", 
                             estilos['subtitulo_tabela_style']))
    
    # Dados dinâmicos da participação
    dados_participacao = [
        # Cabeçalho
        [coluna_label, 'MATRICULADOS', 'AVALIADOS', 'PERCENTUAL', 'FALTOSOS']
    ]
    
    # Adicionar dados por turma ou escola
    for item_data in total_alunos.get(dados_key, []):
        # Quebrar texto para nomes de escolas longos
        nome_item = item_data.get(nome_key, '')
        if scope_type == 'city' and len(nome_item) > 20:
            # Quebrar em linhas de no máximo 20 caracteres
            palavras = nome_item.split()
            linhas = []
            linha_atual = ""
            for palavra in palavras:
                if len(linha_atual + " " + palavra) <= 20:
                    linha_atual += (" " + palavra) if linha_atual else palavra
                else:
                    if linha_atual:
                        linhas.append(linha_atual)
                    linha_atual = palavra
            if linha_atual:
                linhas.append(linha_atual)
            nome_item = "\n".join(linhas)
        
        # Wrap nome_item in Paragraph to interpret \n for line breaks
        if "\n" in nome_item:
            nome_item_cell = Paragraph(nome_item, estilos['table_cell_left_style'])
        else:
            nome_item_cell = nome_item
        
        dados_participacao.append([
            nome_item_cell,
            str(item_data.get('matriculados', 0)),
            str(item_data.get('avaliados', 0)),
            f"{item_data.get('percentual', 0)}%",
            str(item_data.get('faltosos', 0))
        ])
    
    # Adicionar linha total
    total_geral = total_alunos.get('total_geral', {})
    dados_participacao.append([
        'Geral',
        str(total_geral.get('matriculados', 0)),
        str(total_geral.get('avaliados', 0)),
        f"{total_geral.get('percentual', 0)}%",
        str(total_geral.get('faltosos', 0))
    ])
    
    # Criar tabela com larguras ajustadas para nomes de escolas longos
    elements.append(Spacer(1, 1))
    if scope_type == 'city':
        # Para relatório municipal, dar mais espaço para nomes de escolas
        tabela_participacao = Table(dados_participacao, colWidths=[150, 90, 80, 80, 80])
    else:
        # Para relatório por turma, manter largura original
        tabela_participacao = Table(dados_participacao, colWidths=[100, 90, 80, 80, 80])
    
    # Aplicar estilo
    tabela_participacao.setStyle(TableStyle([
        # Cabeçalho
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -2), 'RIGHT'),
        ('FONTNAME', (0, 1), (0, -2), 'Helvetica-Bold'),
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        
        # Linha total
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d9d9d9')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),
        ('ALIGN', (1, -1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(tabela_participacao)
    
    # Análise da IA para participação
    if ai_analysis and ai_analysis.get('participacao'):
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(ai_analysis['participacao'], estilos['paragrafo_indentado_style']))


def _adicionar_niveis_aprendizagem(elements: List, niveis_aprendizagem: Dict, avaliacao_titulo: str, scope_type: str = 'all'):
    """Adiciona a seção de níveis de aprendizagem"""
    estilos = _obter_estilos()
    
    # Determinar rótulo baseado no escopo
    if scope_type == 'city':
        rotulo_principal = "ESCOLA/GERAL"
        coluna_label = "ESCOLA"
        dados_key = "por_escola"
        nome_key = "escola"
    else:
        rotulo_principal = "TURMA/GERAL"
        coluna_label = "TURMA"
        dados_key = "por_turma"
        nome_key = "turma"
    
    # Subtítulo da seção
    elements.append(Spacer(1, 6))
    subtitulo_niveis = Paragraph(f"NÍVEIS DE APRENDIZAGEM POR {rotulo_principal} - {avaliacao_titulo.upper()}", 
                                estilos['subtitulo_tabela_style'])
    
    # Título "GERAL"
    titulo_geral = Paragraph("GERAL", estilos['titulo_pagina_style'])
    
    # Tabela GERAL
    dados_niveis_geral = [
        [coluna_label, 'ABAIXO DO BÁSICO', 'BÁSICO', 'ADEQUADO', 'AVANÇADO']
    ]
    
    # Adicionar dados dinâmicos da tabela GERAL
    if 'GERAL' in niveis_aprendizagem and niveis_aprendizagem['GERAL'].get(dados_key):
        for item_data in niveis_aprendizagem['GERAL'][dados_key]:
            # Quebrar texto para nomes de escolas longos
            nome_item = item_data.get(nome_key, '')
            if scope_type == 'city' and len(nome_item) > 20:
                # Quebrar em linhas de no máximo 20 caracteres
                palavras = nome_item.split()
                linhas = []
                linha_atual = ""
                for palavra in palavras:
                    if len(linha_atual + " " + palavra) <= 20:
                        linha_atual += (" " + palavra) if linha_atual else palavra
                    else:
                        if linha_atual:
                            linhas.append(linha_atual)
                        linha_atual = palavra
                if linha_atual:
                    linhas.append(linha_atual)
                nome_item = "\n".join(linhas)
            
            dados_niveis_geral.append([
                nome_item,
                str(item_data.get('abaixo_do_basico', 0)),
                str(item_data.get('basico', 0)),
                str(item_data.get('adequado', 0)),
                str(item_data.get('avancado', 0))
            ])
    
    # Criar tabela GERAL com larguras ajustadas
    if scope_type == 'city':
        # Para relatório municipal, dar mais espaço para nomes de escolas
        tabela_niveis_geral = Table(dados_niveis_geral, colWidths=[150, 100, 80, 80, 80])
    else:
        # Para relatório por turma, manter largura original
        tabela_niveis_geral = Table(dados_niveis_geral, colWidths=[100, 100, 80, 80, 80])
    
    # Aplicar estilo à tabela GERAL
    tabela_niveis_geral.setStyle(TableStyle([
        # Cabeçalho
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#1f4e79')),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#c00000')),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#ffc000')),
        ('BACKGROUND', (3, 0), (3, 0), colors.HexColor('#70ad47')),
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor('#00b050')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    # Resumo GERAL
    if 'GERAL' in niveis_aprendizagem and (niveis_aprendizagem['GERAL'].get('geral') or niveis_aprendizagem['GERAL'].get('total_geral')):
        geral_data = niveis_aprendizagem['GERAL'].get('geral') or niveis_aprendizagem['GERAL'].get('total_geral')
        total_geral = geral_data.get('total', 0)
        resumo_niveis_geral = [
            Paragraph(f"GERAL (total de {total_geral} alunos avaliados):", estilos['resumo_style']),
            Paragraph(f"• Abaixo do básico: {geral_data.get('abaixo_do_basico', 0)} alunos ({(geral_data.get('abaixo_do_basico', 0)/total_geral*100) if total_geral > 0 else 0:.1f}%)", estilos['resumo_style']),
            Paragraph(f"• Básico: {geral_data.get('basico', 0)} alunos ({(geral_data.get('basico', 0)/total_geral*100) if total_geral > 0 else 0:.1f}%)", estilos['resumo_style']),
            Paragraph(f"• Adequado: {geral_data.get('adequado', 0)} alunos ({(geral_data.get('adequado', 0)/total_geral*100) if total_geral > 0 else 0:.1f}%)", estilos['resumo_style']),
            Paragraph(f"• Avançado: {geral_data.get('avancado', 0)} alunos ({(geral_data.get('avancado', 0)/total_geral*100) if total_geral > 0 else 0:.1f}%)", estilos['resumo_style'])
        ]
    else:
        resumo_niveis_geral = [Paragraph("Dados não disponíveis", estilos['resumo_style'])]
    
    # Manter elementos juntos
    elementos_geral = [
        subtitulo_niveis,
        Spacer(1, 1),
        titulo_geral,
        Spacer(1, 1),
        tabela_niveis_geral,
        Spacer(1, 2)
    ] + resumo_niveis_geral
    
    elements.append(KeepTogether(elementos_geral))
    
    # Tabelas por disciplina
    for disciplina, dados in niveis_aprendizagem.items():
        if disciplina != 'GERAL' and dados and dados.get(dados_key):
            elements.append(Spacer(1, 6))
            
            # Título da disciplina
            titulo_disciplina = Paragraph(disciplina.upper(), estilos['titulo_pagina_style'])
            
            # Dados da tabela
            dados_niveis_disciplina = [
                [coluna_label, 'ABAIXO DO BÁSICO', 'BÁSICO', 'ADEQUADO', 'AVANÇADO']
            ]
            
            for item_data in dados[dados_key]:
                # Quebrar texto para nomes de escolas longos
                nome_item = item_data.get(nome_key, '')
                if scope_type == 'city' and len(nome_item) > 20:
                    # Quebrar em linhas de no máximo 20 caracteres
                    palavras = nome_item.split()
                    linhas = []
                    linha_atual = ""
                    for palavra in palavras:
                        if len(linha_atual + " " + palavra) <= 20:
                            linha_atual += (" " + palavra) if linha_atual else palavra
                        else:
                            if linha_atual:
                                linhas.append(linha_atual)
                            linha_atual = palavra
                    if linha_atual:
                        linhas.append(linha_atual)
                    nome_item = "\n".join(linhas)
                
                dados_niveis_disciplina.append([
                    nome_item,
                    str(item_data.get('abaixo_do_basico', 0)),
                    str(item_data.get('basico', 0)),
                    str(item_data.get('adequado', 0)),
                    str(item_data.get('avancado', 0))
                ])
            
            # Criar tabela com larguras ajustadas
            if scope_type == 'city':
                # Para relatório municipal, dar mais espaço para nomes de escolas
                tabela_niveis_disciplina = Table(dados_niveis_disciplina, colWidths=[150, 100, 80, 80, 80])
            else:
                # Para relatório por turma, manter largura original
                tabela_niveis_disciplina = Table(dados_niveis_disciplina, colWidths=[100, 100, 80, 80, 80])
            
            # Aplicar estilo
            tabela_niveis_disciplina.setStyle(TableStyle([
                # Cabeçalho
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#1f4e79')),
                ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#c00000')),
                ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#ffc000')),
                ('BACKGROUND', (3, 0), (3, 0), colors.HexColor('#70ad47')),
                ('BACKGROUND', (4, 0), (4, 0), colors.HexColor('#00b050')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
                
                # Linhas de dados
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                
                # Bordas
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            # Resumo da disciplina
            if dados.get('geral') or dados.get('total_geral'):
                disc_data = dados.get('geral') or dados.get('total_geral')
                total_disc = disc_data.get('total', 0)
                resumo_niveis_disciplina = [
                    Paragraph(f"{disciplina.upper()} (total de {total_disc} alunos avaliados):", estilos['resumo_style']),
                    Paragraph(f"• Abaixo do básico: {disc_data.get('abaixo_do_basico', 0)} alunos ({(disc_data.get('abaixo_do_basico', 0)/total_disc*100) if total_disc > 0 else 0:.1f}%)", estilos['resumo_style']),
                    Paragraph(f"• Básico: {disc_data.get('basico', 0)} alunos ({(disc_data.get('basico', 0)/total_disc*100) if total_disc > 0 else 0:.1f}%)", estilos['resumo_style']),
                    Paragraph(f"• Adequado: {disc_data.get('adequado', 0)} alunos ({(disc_data.get('adequado', 0)/total_disc*100) if total_disc > 0 else 0:.1f}%)", estilos['resumo_style']),
                    Paragraph(f"• Avançado: {disc_data.get('avancado', 0)} alunos ({(disc_data.get('avancado', 0)/total_disc*100) if total_disc > 0 else 0:.1f}%)", estilos['resumo_style'])
                ]
            else:
                resumo_niveis_disciplina = [Paragraph("Dados não disponíveis", estilos['resumo_style'])]
            
            # Manter elementos juntos
            elementos_disciplina = [
                titulo_disciplina,
                Spacer(1, 1),
                tabela_niveis_disciplina,
                Spacer(1, 2)
            ] + resumo_niveis_disciplina
            
            elements.append(KeepTogether(elementos_disciplina))


def _adicionar_proficiencia_notas(elements: List, proficiencia: Dict, nota_geral: Dict, avaliacao_titulo: str, scope_type: str = 'all', ai_analysis: Dict = None):
    """Adiciona as seções de proficiência e notas"""
    estilos = _obter_estilos()
    
    # Nova página
    elements.append(PageBreak())
    
    # ===== PROFICIÊNCIA =====
    # Ajustar título conforme o escopo
    if scope_type == 'city':
        subtitulo_proficiencia = Paragraph(f"PROFICIÊNCIA POR ESCOLA/GERAL - {avaliacao_titulo.upper()}", 
                                          estilos['subtitulo_tabela_style'])
    else:
        subtitulo_proficiencia = Paragraph(f"PROFICIÊNCIA POR TURMA/GERAL - {avaliacao_titulo.upper()}", 
                                          estilos['subtitulo_tabela_style'])
    
    # Obter disciplinas dinâmicas
    disciplinas_prof = []
    if proficiencia and proficiencia.get('por_disciplina'):
        for disc in proficiencia['por_disciplina'].keys():
            if disc != 'GERAL':
                disciplinas_prof.append(disc)
    
    # Dados da tabela de proficiência - ajustar cabeçalho conforme escopo
    if scope_type == 'city':
        dados_proficiencia = [
            ['ESCOLA'] + disciplinas_prof + ['MÉDIA', 'MUNICIPAL']
        ]
    else:
        dados_proficiencia = [
            ['SÉRIE/TURNO'] + disciplinas_prof + ['MÉDIA', 'MUNICIPAL']
        ]
    
    # Obter média municipal
    media_municipal = 265.00  # Valor padrão, pode ser dinâmico
    if proficiencia and proficiencia.get('media_municipal_por_disciplina'):
        # Usar primeira disciplina como referência
        if disciplinas_prof:
            media_municipal = proficiencia['media_municipal_por_disciplina'].get(disciplinas_prof[0], 265.00)
    
    # Adicionar dados por turma ou escola conforme o escopo
    if scope_type == 'city':
        # Para relatório municipal, usar dados por escola
        if proficiencia and proficiencia.get('por_disciplina', {}).get('GERAL', {}).get('por_escola'):
            for escola_data in proficiencia['por_disciplina']['GERAL']['por_escola']:
                # Quebrar texto para nomes de escolas longos
                nome_item = escola_data.get('escola', '')
                if scope_type == 'city' and len(nome_item) > 20:
                    palavras = nome_item.split()
                    linhas = []
                    linha_atual = ""
                    for palavra in palavras:
                        if len(linha_atual + " " + palavra) <= 20:
                            linha_atual += (" " + palavra) if linha_atual else palavra
                        else:
                            if linha_atual:
                                linhas.append(linha_atual)
                            linha_atual = palavra
                    if linha_atual:
                        linhas.append(linha_atual)
                    nome_item = "\n".join(linhas)
                
                # Wrap nome_item in Paragraph to interpret \n for line breaks
                if "\n" in nome_item:
                    nome_item_cell = Paragraph(nome_item, estilos['table_cell_left_style'])
                else:
                    nome_item_cell = nome_item
                
                linha = [nome_item_cell]
                
                # Adicionar proficiência por disciplina
                soma_prof = 0
                count_prof = 0
                for disc in disciplinas_prof:
                    if disc in proficiencia['por_disciplina'] and 'por_escola' in proficiencia['por_disciplina'][disc]:
                        # Buscar proficiência desta escola nesta disciplina
                        prof_escola = 0
                        for escola_disc in proficiencia['por_disciplina'][disc]['por_escola']:
                            if escola_disc.get('escola') == escola_data.get('escola'):
                                prof_escola = escola_disc.get('media', 0)
                                break
                        linha.append(f"{prof_escola:.2f}")
                        soma_prof += prof_escola
                        count_prof += 1
                    else:
                        linha.append("0.00")
                
                # Média da escola
                media_escola = soma_prof / count_prof if count_prof > 0 else 0
                linha.append(f"{media_escola:.2f}")
                
                # Média municipal (média de todas as escolas)
                if proficiencia and proficiencia.get('por_disciplina', {}).get('GERAL', {}).get('media_geral'):
                    media_municipal = proficiencia['por_disciplina']['GERAL']['media_geral']
                    linha.append(f"{media_municipal:.2f}")
                else:
                    linha.append("0.00")
                
                dados_proficiencia.append(linha)
    else:
        # Para relatório por turma, usar dados por turma
        if proficiencia and proficiencia.get('por_disciplina', {}).get('GERAL', {}).get('por_turma'):
            for turma_data in proficiencia['por_disciplina']['GERAL']['por_turma']:
                linha = [turma_data.get('turma', '')]
                
                # Adicionar proficiência por disciplina
                soma_prof = 0
                count_prof = 0
                for disc in disciplinas_prof:
                    if disc in proficiencia['por_disciplina'] and proficiencia['por_disciplina'][disc].get('por_turma'):
                        # Buscar proficiência desta turma nesta disciplina
                        prof_turma = 0
                        for turma_disc in proficiencia['por_disciplina'][disc]['por_turma']:
                            if turma_disc.get('turma') == turma_data.get('turma'):
                                prof_turma = turma_disc.get('proficiencia', 0)
                                break
                        linha.append(f"{prof_turma:.2f}")
                        soma_prof += prof_turma
                        count_prof += 1
                    else:
                        linha.append("0.00")
                
                # Média
                media = soma_prof / count_prof if count_prof > 0 else 0
                linha.append(f"{media:.2f}")
                
                # Municipal (mesmo valor para todas as turmas)
                linha.append(f"{media_municipal:.2f}")
                
                dados_proficiencia.append(linha)
    
    # Adicionar linha GERAL - ajustar conforme escopo
    if proficiencia and proficiencia.get('por_disciplina'):
        if scope_type == 'city':
            linha_geral = ['MUNICIPAL GERAL']
        else:
            linha_geral = ['9º GERAL']
        soma_geral = 0
        count_geral = 0
        
        for disc in disciplinas_prof:
            if disc in proficiencia['por_disciplina']:
                media_disc = proficiencia['por_disciplina'][disc].get('media_geral', 0)
                linha_geral.append(f"{media_disc:.2f}")
                soma_geral += media_disc
                count_geral += 1
            else:
                linha_geral.append("0.00")
        
        # Média geral
        media_geral_total = soma_geral / count_geral if count_geral > 0 else 0
        linha_geral.append(f"{media_geral_total:.2f}")
        
        # Municipal vazio para linha geral
        linha_geral.append("")
        
        dados_proficiencia.append(linha_geral)
    
    # Criar tabela de proficiência
    tabela_proficiencia = Table(dados_proficiencia, colWidths=[100, 100, 100, 80, 80])
    
    # Aplicar estilo
    num_turmas = len(dados_proficiencia) - 2  # Excluir cabeçalho e linha geral
    tabela_proficiencia.setStyle(TableStyle([
        # Cabeçalho
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -2), 'RIGHT'),
        ('FONTNAME', (0, 1), (0, -2), 'Helvetica-Bold'),
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        
        # Linha total
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d9d9d9')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),
        ('ALIGN', (1, -1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        
        # Mesclar coluna municipal
        ('SPAN', (4, 1), (4, num_turmas)) if num_turmas > 0 else ('SPAN', (4, 1), (4, 1)),
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    # Manter elementos juntos
    elementos_proficiencia = [
        subtitulo_proficiencia,
        Spacer(1, 1),
        tabela_proficiencia
    ]
    
    elements.append(KeepTogether(elementos_proficiencia))
    
    # Análise da IA para proficiência
    if ai_analysis and ai_analysis.get('proficiencia'):
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(ai_analysis['proficiencia'], estilos['paragrafo_indentado_style']))
    
    # ===== NOTAS =====
    elements.append(Spacer(1, 6))
    
    # Ajustar título conforme o escopo
    if scope_type == 'city':
        subtitulo_nota = Paragraph(f"NOTA POR ESCOLA/GERAL - {avaliacao_titulo.upper()}", 
                                  estilos['subtitulo_tabela_style'])
    else:
        subtitulo_nota = Paragraph(f"NOTA POR TURMA/GERAL - {avaliacao_titulo.upper()}", 
                                  estilos['subtitulo_tabela_style'])
    
    # Dados da tabela de notas - ajustar cabeçalho conforme escopo
    if scope_type == 'city':
        dados_nota = [
            ['ESCOLA'] + disciplinas_prof + ['MÉDIA', 'MUNICIPAL']
        ]
    else:
        dados_nota = [
            ['SÉRIE/TURNO'] + disciplinas_prof + ['MÉDIA', 'MUNICIPAL']
        ]
    
    # Obter média municipal de notas
    media_municipal_nota = 5.50  # Valor padrão
    if nota_geral and nota_geral.get('media_municipal_por_disciplina'):
        if disciplinas_prof:
            media_municipal_nota = nota_geral['media_municipal_por_disciplina'].get(disciplinas_prof[0], 5.50)
    
    # Adicionar dados por turma ou escola conforme o escopo
    if scope_type == 'city':
        # Para relatório municipal, usar dados por escola
        if nota_geral and nota_geral.get('por_disciplina', {}).get('GERAL', {}).get('por_escola'):
            for escola_data in nota_geral['por_disciplina']['GERAL']['por_escola']:
                # Quebrar texto para nomes de escolas longos
                nome_item = escola_data.get('escola', '')
                if scope_type == 'city' and len(nome_item) > 20:
                    palavras = nome_item.split()
                    linhas = []
                    linha_atual = ""
                    for palavra in palavras:
                        if len(linha_atual + " " + palavra) <= 20:
                            linha_atual += (" " + palavra) if linha_atual else palavra
                        else:
                            if linha_atual:
                                linhas.append(linha_atual)
                            linha_atual = palavra
                    if linha_atual:
                        linhas.append(linha_atual)
                    nome_item = "\n".join(linhas)
                
                # Wrap nome_item in Paragraph to interpret \n for line breaks
                if "\n" in nome_item:
                    nome_item_cell = Paragraph(nome_item, estilos['table_cell_left_style'])
                else:
                    nome_item_cell = nome_item
                
                linha = [nome_item_cell]
                
                # Adicionar notas por disciplina
                soma_nota = 0
                count_nota = 0
                for disc in disciplinas_prof:
                    if disc in nota_geral['por_disciplina'] and 'por_escola' in nota_geral['por_disciplina'][disc]:
                        # Buscar nota desta escola nesta disciplina
                        nota_escola = 0
                        for escola_disc in nota_geral['por_disciplina'][disc]['por_escola']:
                            if escola_disc.get('escola') == escola_data.get('escola'):
                                nota_escola = escola_disc.get('media', 0)
                                break
                        linha.append(f"{nota_escola:.2f}")
                        soma_nota += nota_escola
                        count_nota += 1
                    else:
                        linha.append("0.00")
                
                # Média da escola
                media_escola = soma_nota / count_nota if count_nota > 0 else 0
                linha.append(f"{media_escola:.2f}")
                
                # Média municipal (média de todas as escolas)
                if nota_geral and nota_geral.get('por_disciplina', {}).get('GERAL', {}).get('media_geral'):
                    media_municipal = nota_geral['por_disciplina']['GERAL']['media_geral']
                    linha.append(f"{media_municipal:.2f}")
                else:
                    linha.append("0.00")
                
                dados_nota.append(linha)
    else:
        # Para relatório por turma, usar dados por turma
        if nota_geral and nota_geral.get('por_disciplina', {}).get('GERAL', {}).get('por_turma'):
            for turma_data in nota_geral['por_disciplina']['GERAL']['por_turma']:
                linha = [turma_data.get('turma', '')]
                
                # Adicionar notas por disciplina
                soma_nota = 0
                count_nota = 0
                for disc in disciplinas_prof:
                    if disc in nota_geral['por_disciplina'] and nota_geral['por_disciplina'][disc].get('por_turma'):
                        # Buscar nota desta turma nesta disciplina
                        nota_turma = 0
                        for turma_disc in nota_geral['por_disciplina'][disc]['por_turma']:
                            if turma_disc.get('turma') == turma_data.get('turma'):
                                nota_turma = turma_disc.get('nota', 0)
                                break
                        linha.append(f"{nota_turma:.2f}")
                        soma_nota += nota_turma
                        count_nota += 1
                    else:
                        linha.append("0.00")
                
                # Média
                media = soma_nota / count_nota if count_nota > 0 else 0
                linha.append(f"{media:.2f}")
                
                # Municipal
                linha.append(f"{media_municipal_nota:.2f}")
                
                dados_nota.append(linha)
    
    # Adicionar linha GERAL - ajustar conforme escopo
    if nota_geral and nota_geral.get('por_disciplina'):
        if scope_type == 'city':
            linha_geral = ['MUNICIPAL GERAL']
        else:
            linha_geral = ['9º GERAL']
        soma_geral = 0
        count_geral = 0
        
        for disc in disciplinas_prof:
            if disc in nota_geral['por_disciplina']:
                media_disc = nota_geral['por_disciplina'][disc].get('media_geral', 0)
                linha_geral.append(f"{media_disc:.2f}")
                soma_geral += media_disc
                count_geral += 1
            else:
                linha_geral.append("0.00")
        
        # Média geral
        media_geral_total = soma_geral / count_geral if count_geral > 0 else 0
        linha_geral.append(f"{media_geral_total:.2f}")
        
        # Municipal vazio para linha geral
        linha_geral.append("")
        
        dados_nota.append(linha_geral)
    
    # Criar tabela de notas
    tabela_nota = Table(dados_nota, colWidths=[100, 100, 100, 80, 80])
    
    # Aplicar estilo (similar à proficiência)
    num_turmas_nota = len(dados_nota) - 2
    tabela_nota.setStyle(TableStyle([
        # Cabeçalho
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -2), 'RIGHT'),
        ('FONTNAME', (0, 1), (0, -2), 'Helvetica-Bold'),
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        
        # Linha total
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d9d9d9')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),
        ('ALIGN', (1, -1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        
        # Mesclar coluna municipal
        ('SPAN', (4, 1), (4, num_turmas_nota)) if num_turmas_nota > 0 else ('SPAN', (4, 1), (4, 1)),
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    # Manter elementos juntos
    elementos_nota = [
        subtitulo_nota,
        Spacer(1, 1),
        tabela_nota
    ]
    
    elements.append(KeepTogether(elementos_nota))
    
    # Análise da IA para notas
    if ai_analysis and ai_analysis.get('notas'):
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(ai_analysis['notas'], estilos['paragrafo_indentado_style']))


def _adicionar_acertos_habilidade(elements: List, acertos_habilidade: Dict, avaliacao_titulo: str, scope_type: str = 'all'):
    """Adiciona a seção de acertos por habilidade"""
    estilos = _obter_estilos()
    
    # Nova página
    elements.append(PageBreak())
    
    # Subtítulo principal - ajustar conforme o escopo
    if scope_type == 'city':
        subtitulo_acertos = Paragraph(f"ACERTOS POR HABILIDADE ESCOLA/GERAL - {avaliacao_titulo.upper()}", 
                                     estilos['subtitulo_tabela_style'])
    else:
        subtitulo_acertos = Paragraph(f"ACERTOS POR HABILIDADE TURMA/GERAL - {avaliacao_titulo.upper()}", 
                                     estilos['subtitulo_tabela_style'])
    
    elements.append(Spacer(1, 2))
    elements.append(subtitulo_acertos)
    
    # Função para aplicar cores às tabelas de acertos
    def aplicar_cores_acertos(tabela, dados):
        estilos_tabela = []
        
        # Linha 1: Números das questões (azul escuro)
        estilos_tabela.extend([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ])
        
        # Linha 2: Códigos das habilidades (amarelo)
        estilos_tabela.extend([
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ffc000')),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.black),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 7),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'),
        ])
        
        # Linha 3: Percentuais (verde se > 70%, branco se <= 70%)
        if len(dados) > 2:
            for col, percentual_str in enumerate(dados[2]):
                try:
                    percentual = float(percentual_str.replace('%', ''))
                    if percentual > 70:
                        cor_fundo = colors.HexColor('#00b050')  # Verde
                    else:
                        cor_fundo = colors.white
                    
                    estilos_tabela.append(('BACKGROUND', (col, 2), (col, 2), cor_fundo))
                except:
                    estilos_tabela.append(('BACKGROUND', (col, 2), (col, 2), colors.white))
        
        estilos_tabela.extend([
            ('TEXTCOLOR', (0, 2), (-1, 2), colors.black),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica'),
            ('FONTSIZE', (0, 2), (-1, 2), 7),
            ('ALIGN', (0, 2), (-1, 2), 'CENTER'),
            ('VALIGN', (0, 2), (-1, 2), 'MIDDLE'),
        ])
        
        # Bordas e padding
        estilos_tabela.extend([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ])
        
        return estilos_tabela
    
    # Processar cada disciplina
    for disciplina, dados in acertos_habilidade.items():
        if disciplina != 'GERAL' and dados and dados.get('questoes'):
            elements.append(Spacer(1, 6))
            
            # Título da disciplina
            titulo_disciplina_acertos = Paragraph(disciplina.upper(), estilos['subtitulo_tabela_style'])
            
            # Obter questões dinâmicas
            questoes = dados['questoes']
            
            # Dividir questões em duas tabelas (1-13 e 14-26)
            meio = len(questoes) // 2
            questoes_1 = questoes[:meio] if meio > 0 else questoes
            questoes_2 = questoes[meio:] if meio > 0 and len(questoes) > meio else []
            
            # Primeira tabela (questões 1-13)
            if questoes_1:
                # Linha 1: Números das questões
                linha_questoes_1 = []
                for questao in questoes_1:
                    linha_questoes_1.append(f"{questao.get('numero_questao', 1)}ª Q")
                
                # Linha 2: Códigos das habilidades
                linha_codigos_1 = []
                for questao in questoes_1:
                    linha_codigos_1.append(questao.get('codigo', 'N/A'))
                
                # Linha 3: Percentuais
                linha_percentuais_1 = []
                for questao in questoes_1:
                    linha_percentuais_1.append(f"{questao.get('percentual', 0)}%")
                
                dados_acertos_1 = [linha_questoes_1, linha_codigos_1, linha_percentuais_1]
                
                # Criar tabela 1
                tabela_acertos_1 = Table(dados_acertos_1, colWidths=[35] * len(linha_questoes_1))
                tabela_acertos_1.setStyle(TableStyle(aplicar_cores_acertos(tabela_acertos_1, dados_acertos_1)))
            
            # Segunda tabela (questões 14-26)
            if questoes_2:
                # Linha 1: Números das questões
                linha_questoes_2 = []
                for questao in questoes_2:
                    linha_questoes_2.append(f"{questao.get('numero_questao', 1)}ª Q")
                
                # Linha 2: Códigos das habilidades
                linha_codigos_2 = []
                for questao in questoes_2:
                    linha_codigos_2.append(questao.get('codigo', 'N/A'))
                
                # Linha 3: Percentuais
                linha_percentuais_2 = []
                for questao in questoes_2:
                    linha_percentuais_2.append(f"{questao.get('percentual', 0)}%")
                
                dados_acertos_2 = [linha_questoes_2, linha_codigos_2, linha_percentuais_2]
                
                # Criar tabela 2
                tabela_acertos_2 = Table(dados_acertos_2, colWidths=[35] * len(linha_questoes_2))
                tabela_acertos_2.setStyle(TableStyle(aplicar_cores_acertos(tabela_acertos_2, dados_acertos_2)))
            
            # Manter elementos da disciplina juntos
            elementos_disciplina_acertos = [titulo_disciplina_acertos, Spacer(1, 1)]
            
            if questoes_1:
                elementos_disciplina_acertos.append(tabela_acertos_1)
                
                if questoes_2:
                    elementos_disciplina_acertos.append(Spacer(1, 6))  # Espaço entre tabelas
                    elementos_disciplina_acertos.append(tabela_acertos_2)
            
            elements.append(KeepTogether(elementos_disciplina_acertos))
