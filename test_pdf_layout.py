#!/usr/bin/env python3
"""
Script para testar o layout do PDF com dados fictícios
"""

import sys
import os
from io import BytesIO
from datetime import datetime

# Adicionar o diretório do projeto ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar dependências do reportlab
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageTemplate, Frame, PageBreak, KeepTogether
from reportlab.platypus import BaseDocTemplate
from reportlab.pdfgen import canvas

def _header(canvas, doc, logo_esq=None, logo_dir=None):
    """Função para desenhar cabeçalho com logos em todas as páginas"""
    # Por enquanto, não desenhar nada para evitar erros com logos
    pass

def test_pdf_capa():
    """Testa a geração da capa do PDF"""
    
    print("=== INICIANDO TESTE DE CAPA PDF ===")
    
    # Criar buffer para o PDF
    buffer = BytesIO()
    
    # Criar documento PDF com margens adequadas para capa
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25*mm,
        leftMargin=25*mm,
        topMargin=30*mm,
        bottomMargin=25*mm
    )
    
    # Dados fictícios para teste
    municipio_nome = "São Miguel dos Campos"
    estado = "Alagoas"
    avaliacao_titulo = "1º AVALIE 2025"
    escola_nome = "Escola Municipal de Ensino Fundamental João Silva"
    serie = "9º ANO"  # Variável para a série
    
    # Determinar período atual
    from datetime import datetime
    now = datetime.now()
    meses_portugues = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
    }
    mes_atual = meses_portugues[now.month]
    ano_atual = now.year
    
    # Preparar elementos do PDF
    elements = []
    
    # Estilos do template
    styles = getSampleStyleSheet()
    
    # Estilo para o título principal da capa
    title_style = ParagraphStyle(
        'CapaTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=30,
        spaceBefore=100,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para o subtítulo (nome da escola)
    subtitle_style = ParagraphStyle(
        'CapaSubtitle',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=50,
        fontName='Helvetica'
    )
    
    # Estilo para o rodapé
    footer_style = ParagraphStyle(
        'CapaFooter',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceBefore=200,
        fontName='Helvetica'
    )
    
    # ===== CAPA DO RELATÓRIO =====
    
    # Título principal da capa
    titulo_relatorio = f"Relatório da Avaliação {avaliacao_titulo} da rede Municipal de Ensino {municipio_nome} / {estado}"
    elements.append(Paragraph(titulo_relatorio, title_style))
    
    # Subtítulo (nome da escola) - com espaço para não ficar colado
    elements.append(Spacer(1, 40))  # Espaço entre título e subtítulo
    elements.append(Paragraph(escola_nome, subtitle_style))
    
    # Rodapé (mês/ano) - posicionado na parte inferior
    elements.append(Paragraph(f"{mes_atual} / {ano_atual}", footer_style))
    
    # Quebra de página para o sumário
    elements.append(PageBreak())
    
    # ===== SUMÁRIO =====
    
    # Estilo para o título do sumário
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
    
    # Estilo para os itens principais do sumário
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
        'SumarioSubItem',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=6,
        leftIndent=40,
        firstLineIndent=-20,
        fontName='Helvetica'
    )
    
    # Título do sumário
    elements.append(Paragraph("SUMÁRIO", sumario_title_style))
    
    # Itens do sumário com variáveis dinâmicas (sem números de páginas marcados com <<)
    elementos_sumario = [
        ("1. APRESENTAÇÃO", ""),
        ("2. CONSIDERAÇÕES GERAIS", ""),
        (f"3. PARTICIPAÇÃO DA REDE NO PROCESSO DA {avaliacao_titulo}", ""),
        ("4. RENDIMENTO POR SÉRIE, POR TURMA E POR ESCOLA", ""),
        (f"4.1 PROFICIÊNCIA POR UNIDADE DE ENSINO/ TURMA - {serie}", ""),
        (f"4.2 NOTA POR UNIDADE DE ENSINO/ TURMA - {serie}", ""),
        (f"4.3 ACERTOS POR HABILIDADE POR UNIDADE DE ENSINO/ TURMA - {serie}", ""),
        (f"4.4 ACERTOS POR HABILIDADE POR UNIDADE DE ENSINO/ TURMA - {serie}", "")
    ]
    
    # Criar sumário usando Paragraphs individuais para melhor controle de indentação
    for item, pagina in elementos_sumario:
        numero = item.split()[0]
        if numero != "4." and numero.startswith("4.") and numero.count(".") == 1:   # detecta "4.1", "4.2", etc.
            texto = f"{item} {pagina}" if pagina else item
            elements.append(Paragraph(texto, sumario_subitem_style))
        else:
            texto = f"{item} {pagina}" if pagina else item
            elements.append(Paragraph(texto, sumario_item_style))
    
    # Adicionar quebra de página
    elements.append(PageBreak())
    
    # ===== PÁGINA 1. APRESENTAÇÃO + 2. CONSIDERAÇÕES GERAIS =====
    
    # Estilos para os parágrafos
    paragrafo_indentado_style = ParagraphStyle(
        'ParagrafoIndentado',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=12,  # Aumentar espaçamento entre parágrafos
        spaceBefore=6,  # Espaçamento antes do parágrafo
        firstLineIndent=36,  # Apenas primeira linha indentada
        fontName='Helvetica',
        leading=14  # Espaçamento entre linhas
    )
    
    # Estilo para lista pontilhada
    lista_style = ParagraphStyle(
        'Lista',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=8,  # Aumentar espaçamento
        spaceBefore=4,
        leftIndent=72,  # Indentação maior para lista
        fontName='Helvetica',
        leading=14  # Espaçamento entre linhas
    )
    
    # Estilo para títulos desta página (em negrito)
    titulo_pagina_style = ParagraphStyle(
        'TituloPagina',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=12,
        spaceBefore=12,
        fontName='Helvetica-Bold'  # Negrito
    )
    
    # 1. APRESENTAÇÃO
    elements.append(Paragraph("1. APRESENTAÇÃO", titulo_pagina_style))
    
    # Parágrafo principal
    paragrafo_principal = f"""Este relatório apresenta os resultados da <b>{avaliacao_titulo}</b> <b>{municipio_nome}</b> – <b>{estado}</b> referente ao <b>{serie}</b> de <b>{ano_atual}</b> da <b>{escola_nome}</b>. Foram avaliados <b>222</b> alunos, o que corresponde a <b>89%</b> do total de estudantes dessas séries."""
    elements.append(Paragraph(paragrafo_principal, paragrafo_indentado_style))
    
    # Subtítulo
    elements.append(Paragraph("Para a análise, utilizamos:", paragrafo_indentado_style))
    
    # Lista pontilhada
    elements.append(Paragraph("• Frequência absoluta (número de alunos)", lista_style))
    elements.append(Paragraph("• Frequência relativa (percentual)", lista_style))
    elements.append(Paragraph("• Média aritmética simples", lista_style))
    
    # Parágrafo adicional
    paragrafo_adicional1 = f"""As competências avaliadas foram as disciplinas de <b>Língua Portuguesa e Matemática</b>, com dados apresentados por turma, por série e consolidado para toda a rede. Gráficos nominais por aluno e rendimento de cada turma estão disponíveis na <b>Plataforma InnovPlay</b>, nas respectivas unidades de ensino."""
    elements.append(Paragraph(paragrafo_adicional1, paragrafo_indentado_style))
    
    # Parágrafo adicional
    paragrafo_adicional2 = """A escala de cores das médias variou do <b>vermelho (0)</b> ao <b>verde (10)</b>. Para identificar descritores/habilidades com índice de erro superior a 40%, registramos esses itens em destaque <b>vermelho</b>, sinalizando prioridades de intervenção pedagógica."""
    elements.append(Paragraph(paragrafo_adicional2, paragrafo_indentado_style))
    
    # 2. CONSIDERAÇÕES GERAIS
    elements.append(Paragraph("2. CONSIDERAÇÕES GERAIS", titulo_pagina_style))
    
    # Parágrafo 1
    paragrafo_consideracoes1 = """Antes de olharmos os resultados é importante nos atentarmos que cada escola tem suas especificidades, assim como cada turma. Existem resultados que só serão explicados considerando estas especificidades."""
    elements.append(Paragraph(paragrafo_consideracoes1, paragrafo_indentado_style))
    
    # Parágrafo 2
    paragrafo_consideracoes2 = """As turmas são únicas e, portanto, a observação das necessidades de cada turma deve ser analisada através do sistema."""
    elements.append(Paragraph(paragrafo_consideracoes2, paragrafo_indentado_style))
    
    # Adicionar quebra de página
    elements.append(PageBreak())
    
    # ===== PÁGINA 1. PARTICIPAÇÃO DA REDE =====
    
    # Estilo para título principal da página (menor, como subtítulo)
    titulo_principal_style = ParagraphStyle(
        'TituloPrincipal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=12,
        spaceBefore=0,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulo da tabela (menor, com fundo cinza claro)
    subtitulo_tabela_style = ParagraphStyle(
        'SubtituloTabela',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=8,
        spaceBefore=8,
        fontName='Helvetica-Bold',
        backColor=colors.HexColor('#d9d9d9')  # Fundo cinza claro
    )
    
    # 1. TÍTULO PRINCIPAL
    elements.append(Paragraph("1. PARTICIPAÇÃO DA REDE NO PROCESSO DA AVALIAÇÃO DIAGNÓSTICA", titulo_principal_style))
    
    # 2. SUBTÍTULO DA TABELA (com fundo cinza claro)
    elements.append(Paragraph("TOTAL DE ALUNOS QUE REALIZARAM A AVALIAÇÃO DIAGNÓSTICA 2025.1", subtitulo_tabela_style))
    
    # 3. TABELA DE PARTICIPAÇÃO
    # Dados da tabela (fixos por enquanto)
    dados_participacao = [
        # Cabeçalho
        ['SÉRIE/TURNO', 'MATRICULADOS', 'AVALIADOS', 'PERCENTUAL', 'FALTOSOS'],
        # Dados das turmas
        ['9º A', '38', '37', '97%', '1'],
        ['9º B', '37', '37', '100%', '0'],
        ['9º C', '35', '32', '91%', '3'],
        ['9º D', '36', '30', '83%', '6'],
        ['9º E', '37', '34', '92%', '3'],
        ['9º A-V', '36', '26', '72%', '10'],
        ['9º B-V', '30', '26', '87%', '4'],
        # Linha total
        ['9º GERAL', '249', '222', '89%', '27']
    ]
    
    # Criar tabela com colunas mais largas
    tabela_participacao = Table(dados_participacao, colWidths=[100, 90, 80, 80, 80])
    
    # Aplicar estilos à tabela
    tabela_participacao.setStyle(TableStyle([
        # Cabeçalho - fundo azul escuro, texto branco, negrito
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),  # Azul escuro
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduzir fonte do cabeçalho
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados - fundo branco, texto preto
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),  # Reduzir fonte dos dados
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, 1), (-1, -2), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        
        # Linha total - fundo cinza claro, texto preto, negrito
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d9d9d9')),  # Cinza claro
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),  # Reduzir fonte da linha total
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, -1), (-1, -1), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),  # Linha mais grossa abaixo do cabeçalho
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),  # Linha mais grossa acima do total
        
        # Espaçamento
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(tabela_participacao)
    
    # 4. ANÁLISE DA TABELA
    elements.append(Spacer(1, 12))  # Espaço antes da análise
    
    analise_participacao = """A escola avaliou <b>222 alunos</b> do 9º ano, o que representa <b>89%</b> do total de <b>249 alunos</b> matriculados. Registrou-se um total de <b>27 alunos faltosos</b>. A taxa de participação de <b>89%</b> é boa, indicando um bom engajamento geral. Contudo, a ausência de <b>27 alunos</b> é um número considerável. Recomenda-se a investigação das causas dessas ausências, um contato proativo com as famílias para elevar a participação em futuras avaliações e o planejamento de uma reposição diagnóstica para os alunos faltosos, visando obter um panorama mais completo da aprendizagem na série."""
    
    elements.append(Paragraph(analise_participacao, paragrafo_indentado_style))
    
    # ===== SEÇÃO NÍVEIS DE APRENDIZAGEM =====
    
    # 5. SUBTÍTULO DOS NÍVEIS DE APRENDIZAGEM
    subtitulo_niveis = Paragraph("NÍVEIS DE APRENDIZAGEM POR TURMA/GERAL - AVALIAÇÃO DIAGNÓSTICA 2025.1", subtitulo_tabela_style)
    
    # 6. TABELA GERAL DE NÍVEIS DE APRENDIZAGEM
    # Título "GERAL" acima da tabela
    titulo_geral = Paragraph("GERAL", titulo_pagina_style)
    
    # Dados da tabela geral (fixos por enquanto)
    dados_niveis_geral = [
        # Cabeçalho
        ['SÉRIE/TURNO', 'ABAIXO DO BÁSICO', 'BÁSICO', 'ADEQUADO', 'AVANÇADO'],
        # Dados das turmas
        ['9º A', '0', '0', '5', '32'],
        ['9º B', '0', '0', '0', '37'],
        ['9º C', '2', '3', '8', '19'],
        ['9º D', '5', '8', '12', '5'],
        ['9º E', '3', '4', '10', '17'],
        ['9º A-V', '8', '10', '6', '2'],
        ['9º B-V', '2', '2', '4', '18'],
        # Linha total
        ['9º GERAL', '20', '27', '45', '130']
    ]
    
    # Criar tabela geral com colunas mais largas
    tabela_niveis_geral = Table(dados_niveis_geral, colWidths=[100, 100, 80, 80, 80])
    
    # Aplicar estilos à tabela geral
    tabela_niveis_geral.setStyle(TableStyle([
        # Cabeçalho - cores específicas para cada coluna
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#1f4e79')),  # SÉRIE/TURNO - azul escuro
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#c00000')),  # ABAIXO DO BÁSICO - vermelho
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#ffc000')),  # BÁSICO - laranja/amarelo
        ('BACKGROUND', (3, 0), (3, 0), colors.HexColor('#70ad47')),  # ADEQUADO - verde claro
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor('#00b050')),  # AVANÇADO - verde escuro
        
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduzir fonte do cabeçalho
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados - fundo branco, texto preto
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),  # Reduzir fonte dos dados
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, 1), (-1, -2), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        
        # Linha total - fundo cinza claro, texto preto, negrito
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d9d9d9')),  # Cinza claro
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),  # Reduzir fonte da linha total
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, -1), (-1, -1), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),  # Linha mais grossa abaixo do cabeçalho
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),  # Linha mais grossa acima do total
        
        # Espaçamento
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # Envolver título, tabela e resumo em KeepTogether para evitar quebra de página
    elementos_tabela_geral = [
        Spacer(1, 2),  # Reduzir espaço antes do subtítulo
        subtitulo_niveis,
        Spacer(1, 1),  # Reduzir espaço antes da tabela
        titulo_geral,
        tabela_niveis_geral,
        Spacer(1, 2),  # Reduzir espaço antes do resumo
    ]
    
    # 7. RESUMO DOS NÍVEIS GERAIS
    
    # Estilo para resumo sem indentação
    resumo_style = ParagraphStyle(
        'Resumo',
        parent=styles['Normal'],
        fontSize=10,  # Reduzir tamanho da fonte
        textColor=colors.black,
        alignment=TA_LEFT,
        spaceAfter=6,  # Reduzir espaçamento
        spaceBefore=4,  # Reduzir espaçamento
        leftIndent=0,  # Sem indentação
        fontName='Helvetica',
        leading=12  # Reduzir leading
    )
    
    resumo_niveis_geral = """<b>GERAL</b> (total de <b>222 alunos</b> avaliados):<br/>
• Abaixo do básico: <b>20 alunos</b> (<b>9,0%</b>)<br/>
• Básico: <b>27 alunos</b> (<b>12,2%</b>)<br/>
• Adequado: <b>45 alunos</b> (<b>20,3%</b>)<br/>
• Avançado: <b>130 alunos</b> (<b>58,6%</b>)"""
    
    elementos_tabela_geral.append(Paragraph(resumo_niveis_geral, resumo_style))
    
    # Adicionar tabela geral com KeepTogether
    elements.append(KeepTogether(elementos_tabela_geral))
    
    # 8. TABELAS POR DISCIPLINA (exemplo com Língua Portuguesa)
    # Título da disciplina
    titulo_portugues = Paragraph("LÍNGUA PORTUGUESA", subtitulo_tabela_style)
    
    # Dados da tabela de Língua Portuguesa (mesmos dados por enquanto)
    dados_niveis_portugues = [
        # Cabeçalho
        ['SÉRIE/TURNO', 'ABAIXO DO BÁSICO', 'BÁSICO', 'ADEQUADO', 'AVANÇADO'],
        # Dados das turmas
        ['9º A', '0', '0', '5', '32'],
        ['9º B', '0', '0', '0', '37'],
        ['9º C', '2', '3', '8', '19'],
        ['9º D', '5', '8', '12', '5'],
        ['9º E', '3', '4', '10', '17'],
        ['9º A-V', '8', '10', '6', '2'],
        ['9º B-V', '2', '2', '4', '18'],
        # Linha total
        ['9º GERAL', '20', '27', '45', '130']
    ]
    
    # Criar tabela de Língua Portuguesa com colunas mais largas
    tabela_niveis_portugues = Table(dados_niveis_portugues, colWidths=[100, 100, 80, 80, 80])
    
    # Aplicar os mesmos estilos
    tabela_niveis_portugues.setStyle(TableStyle([
        # Cabeçalho - cores específicas para cada coluna
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#1f4e79')),  # SÉRIE/TURNO - azul escuro
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#c00000')),  # ABAIXO DO BÁSICO - vermelho
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#ffc000')),  # BÁSICO - laranja/amarelo
        ('BACKGROUND', (3, 0), (3, 0), colors.HexColor('#70ad47')),  # ADEQUADO - verde claro
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor('#00b050')),  # AVANÇADO - verde escuro
        
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduzir fonte do cabeçalho
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados - fundo branco, texto preto
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),  # Reduzir fonte dos dados
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, 1), (-1, -2), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        
        # Linha total - fundo cinza claro, texto preto, negrito
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d9d9d9')),  # Cinza claro
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),  # Reduzir fonte da linha total
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, -1), (-1, -1), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),  # Linha mais grossa abaixo do cabeçalho
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),  # Linha mais grossa acima do total
        
        # Espaçamento
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # Envolver título, tabela e resumo em KeepTogether para evitar quebra de página
    elementos_tabela_portugues = [
        Spacer(1, 6),  # Reduzir espaço antes da próxima seção
        titulo_portugues,
        tabela_niveis_portugues,
        Spacer(1, 2),  # Reduzir espaço antes do resumo
    ]
    
    # Resumo de Língua Portuguesa
    resumo_niveis_portugues = """<b>LÍNGUA PORTUGUESA</b> (total de <b>222 alunos</b> avaliados):<br/>
• Abaixo do básico: <b>20 alunos</b> (<b>9,0%</b>)<br/>
• Básico: <b>27 alunos</b> (<b>12,2%</b>)<br/>
• Adequado: <b>45 alunos</b> (<b>20,3%</b>)<br/>
• Avançado: <b>130 alunos</b> (<b>58,6%</b>)"""
    
    elementos_tabela_portugues.append(Paragraph(resumo_niveis_portugues, resumo_style))
    
    # Adicionar tabela de Língua Portuguesa com KeepTogether
    elements.append(KeepTogether(elementos_tabela_portugues))
    
    # ===== SEÇÃO PROFICIÊNCIA =====
    
    # 9. SUBTÍTULO DA PROFICIÊNCIA
    subtitulo_proficiencia = Paragraph("PROFICIÊNCIA POR TURMA/GERAL - AVALIAÇÃO DIAGNÓSTICA 2025.1", subtitulo_tabela_style)
    
    # Dados da tabela de proficiência (fixos por enquanto)
    dados_proficiencia = [
        # Cabeçalho
        ['SÉRIE/TURNO', 'LÍNGUA PORTUGUESA', 'MATEMÁTICA', 'MÉDIA', 'MUNICIPAL'],
        # Dados das turmas
        ['9º A', '348,00', '364,00', '356,00', '265,00'],
        ['9º B', '324,00', '323,00', '323,50', '265,00'],
        ['9º C', '348,00', '308,00', '328,00', '265,00'],
        ['9º D', '339,00', '261,00', '300,00', '265,00'],
        ['9º E', '259,00', '266,00', '262,50', '265,00'],
        ['9º A-V', '240,00', '181,00', '210,50', '265,00'],
        ['9º B-V', '234,00', '175,00', '204,50', '265,00'],
        # Linha total (sem coluna municipal)
        ['9º GERAL', '298,86', '268,29', '283,57', '']
    ]
    
    # Criar tabela de proficiência
    tabela_proficiencia = Table(dados_proficiencia, colWidths=[100, 100, 100, 80, 80])
    
    # Aplicar estilos à tabela de proficiência
    tabela_proficiencia.setStyle(TableStyle([
        # Cabeçalho - fundo azul escuro, texto branco, negrito
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),  # Azul escuro
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduzir fonte do cabeçalho
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados - fundo branco, texto preto
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),  # Reduzir fonte dos dados
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, 1), (-1, -2), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        
        # Linha total - fundo cinza claro, texto preto, negrito
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d9d9d9')),  # Cinza claro
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),  # Reduzir fonte da linha total
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, -1), (-1, -1), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        
        # Mesclar coluna MUNICIPAL (linhas 1-7, coluna 4)
        ('SPAN', (4, 1), (4, 7)),  # Mesclar células da coluna municipal das turmas
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),  # Linha mais grossa abaixo do cabeçalho
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),  # Linha mais grossa acima do total
        
        # Espaçamento
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # 11. ANÁLISE DA PROFICIÊNCIA
    analise_proficiencia = """A proficiência média da escola nesta avaliação diagnóstica foi de <b>298,86</b> em Língua Portuguesa e <b>268,29</b> em Matemática. Comparativamente, o desempenho em Língua Portuguesa (<b>298,86</b>) está significativamente acima da média de proficiência de <b>272,19</b> alcançada na Prova Saeb/2023 para o 9º ano. Este é um resultado excelente e um grande destaque para a escola, indicando um alto nível de domínio das competências em LP. Em Matemática, a proficiência de <b>268,29</b> encontra-se abaixo da média de <b>293,55</b> obtida no Saeb/2023. Apesar de ser uma proficiência considerável, ainda há uma lacuna para atingir o referencial nacional, indicando que esta é a área que demanda maior foco estratégico."""
    
    # Manter título, tabela e análise juntos
    elements.append(KeepTogether([
        Spacer(1, 2),  # Espaço antes do subtítulo
        subtitulo_proficiencia,
        Spacer(1, 1),  # Espaço antes da tabela
        tabela_proficiencia,
        Spacer(1, 2),  # Espaço antes da análise
        Paragraph(analise_proficiencia, paragrafo_indentado_style)
    ]))
    
    # ===== SEÇÃO NOTA =====
    
    # 12. SUBTÍTULO DA NOTA
    subtitulo_nota = Paragraph("NOTA POR TURMA/GERAL - AVALIAÇÃO DIAGNÓSTICA 2025.1", subtitulo_tabela_style)
    
    # Dados da tabela de nota (fixos por enquanto)
    dados_nota = [
        # Cabeçalho
        ['SÉRIE/TURNO', 'LÍNGUA PORTUGUESA', 'MATEMÁTICA', 'MÉDIA', 'MUNICIPAL'],
        # Dados das turmas
        ['9º A', '8,25', '8,79', '8,5', '5,50'],
        ['9º B', '7,45', '7,42', '7,44', '5,50'],
        ['9º C', '8,25', '6,93', '7,59', '5,50'],
        ['9º D', '7,96', '5,37', '6,67', '5,50'],
        ['9º E', '5,36', '5,53', '5,44', '5,50'],
        ['9º A-V', '4,68', '2,70', '3,69', '5,50'],
        ['9º B-V', '4,46', '2,57', '3,51', '5,50'],
        # Linha total (sem coluna municipal)
        ['9º GERAL', '6,77', '5,85', '6,31', '']
    ]
    
    # Criar tabela de nota
    tabela_nota = Table(dados_nota, colWidths=[100, 100, 100, 80, 80])
    
    # Aplicar os mesmos estilos da tabela de proficiência
    tabela_nota.setStyle(TableStyle([
        # Cabeçalho - fundo azul escuro, texto branco, negrito
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),  # Azul escuro
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),  # Reduzir fonte do cabeçalho
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        
        # Linhas de dados - fundo branco, texto preto
        ('BACKGROUND', (0, 1), (-1, -2), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -2), colors.black),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8),  # Reduzir fonte dos dados
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, 1), (-1, -2), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        
        # Linha total - fundo cinza claro, texto preto, negrito
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d9d9d9')),  # Cinza claro
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 8),  # Reduzir fonte da linha total
        ('ALIGN', (0, -1), (0, -1), 'LEFT'),   # Primeira coluna à esquerda
        ('ALIGN', (1, -1), (-1, -1), 'CENTER'), # Outras colunas centralizadas
        ('VALIGN', (0, -1), (-1, -1), 'MIDDLE'),
        
        # Mesclar coluna MUNICIPAL (linhas 1-7, coluna 4)
        ('SPAN', (4, 1), (4, 7)),  # Mesclar células da coluna municipal das turmas
        
        # Bordas
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.black),  # Linha mais grossa abaixo do cabeçalho
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),  # Linha mais grossa acima do total
        
        # Espaçamento
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # 14. ANÁLISE DA NOTA
    analise_nota = """A média geral de nota da escola na avaliação diagnóstica foi de <b>6,31</b>, com <b>6,77</b> em Língua Portuguesa e <b>5,85</b> em Matemática. Esta média geral de <b>6,31</b> está exatamente alinhada e ligeiramente acima da nota padronizada de <b>6,1</b> obtida na Prova Saeb/2023 para o 9º ano, o que é um resultado muito positivo para a escola como um todo. A nota em Língua Portuguesa (<b>6,77</b>) é excelente e reflete a alta proficiência alcançada. A nota em Matemática (<b>5,85</b>), embora contribua para a boa média geral, ainda está abaixo do ideal e indica a necessidade de melhorias nesta disciplina para que a escola possa elevar ainda mais seu desempenho global."""
    
    # Manter título, tabela e análise juntos
    elements.append(KeepTogether([
        Spacer(1, 6),  # Espaço antes do subtítulo
        subtitulo_nota,
        Spacer(1, 1),  # Espaço antes da tabela
        tabela_nota,
        Spacer(1, 2),  # Espaço antes da análise
        Paragraph(analise_nota, paragrafo_indentado_style)
    ]))
    
    # ===== SEÇÃO ACERTOS POR HABILIDADE =====
    
    # 15. NOVA PÁGINA PARA ACERTOS POR HABILIDADE
    elements.append(PageBreak())
    
    # 16. SUBTÍTULO DOS ACERTOS POR HABILIDADE
    subtitulo_acertos = Paragraph("ACERTOS POR HABILIDADE TURMA/GERAL - AVALIAÇÃO DIAGNÓSTICA 2025.1", subtitulo_tabela_style)
    
    # 17. TABELA DE ACERTOS POR HABILIDADE - LÍNGUA PORTUGUESA
    titulo_portugues_acertos = Paragraph("LÍNGUA PORTUGUESA", subtitulo_tabela_style)
    
    # Dados da tabela de acertos por habilidade (fixos por enquanto)
    # Primeira seção (questões 1-13)
    dados_acertos_portugues_1 = [
        # Linha 1: Números das questões
        ['1ª Q', '2ª Q', '3ª Q', '4ª Q', '5ª Q', '6ª Q', '7ª Q', '8ª Q', '9ª Q', '10ª Q', '11ª Q', '12ª Q', '13ª Q'],
        # Linha 2: Códigos das habilidades
        ['9L1.1', '9L1.2', '9L1.3', '9L2.5', '9L1.5', '9L2.1', '9L2.4', '9L2.2', '9A2.2', '9L2.3', '9L1.4', '9L2.7', '9L2.8'],
        # Linha 3: Percentuais de acerto
        ['67.1%', '46.4%', '69.4%', '53.2%', '48.6%', '43.2%', '42.3%', '69.8%', '63.5%', '53.2%', '68.5%', '60.8%', '77.9%']
    ]
    
    # Segunda seção (questões 14-26)
    dados_acertos_portugues_2 = [
        # Linha 1: Números das questões
        ['14ª Q', '15ª Q', '16ª Q', '17ª Q', '18ª Q', '19ª Q', '20ª Q', '21ª Q', '22ª Q', '23ª Q', '24ª Q', '25ª Q', '26ª Q'],
        # Linha 2: Códigos das habilidades
        ['9L2.5', '9L2.9', '9L2.6', '9L1.2', '9A2.4', '9A2.1', '9L1.6', '9L2.10', '9A2.3', '9L1.7', '9L2.11', '9L1.8', '9A2.5'],
        # Linha 3: Percentuais de acerto
        ['68.0%', '77.0%', '73.9%', '76.1%', '85.1%', '81.5%', '59.5%', '72.1%', '85.6%', '70.7%', '84.7%', '67.1%', '83.8%']
    ]
    
    # Criar tabelas de acertos por habilidade
    tabela_acertos_portugues_1 = Table(dados_acertos_portugues_1, colWidths=[35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35])
    tabela_acertos_portugues_2 = Table(dados_acertos_portugues_2, colWidths=[35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35])
    
    # Função para aplicar cores baseadas no percentual
    def aplicar_cores_acertos(tabela, dados):
        estilo = []
        
        # Linha 1: Cabeçalho das questões (azul escuro, texto branco, negrito)
        estilo.extend([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e79')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        ])
        
        # Linha 2: Códigos das habilidades (amarelo, texto preto, negrito)
        estilo.extend([
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ffc000')),
            ('TEXTCOLOR', (0, 1), (-1, 1), colors.black),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 7),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'),
        ])
        
        # Linha 3: Percentuais (verde se > 70%, branco caso contrário)
        for col in range(len(dados[2])):
            percentual_str = dados[2][col].replace('%', '')
            try:
                percentual = float(percentual_str)
                if percentual > 70:
                    # Verde para percentuais > 70%
                    estilo.extend([
                        ('BACKGROUND', (col, 2), (col, 2), colors.HexColor('#70ad47')),
                        ('TEXTCOLOR', (col, 2), (col, 2), colors.black),
                    ])
                else:
                    # Branco para percentuais <= 70%
                    estilo.extend([
                        ('BACKGROUND', (col, 2), (col, 2), colors.white),
                        ('TEXTCOLOR', (col, 2), (col, 2), colors.black),
                    ])
            except ValueError:
                # Se não conseguir converter, usar branco
                estilo.extend([
                    ('BACKGROUND', (col, 2), (col, 2), colors.white),
                    ('TEXTCOLOR', (col, 2), (col, 2), colors.black),
                ])
        
        # Estilo comum para a linha de percentuais
        estilo.extend([
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica'),
            ('FONTSIZE', (0, 2), (-1, 2), 7),
            ('ALIGN', (0, 2), (-1, 2), 'CENTER'),
            ('VALIGN', (0, 2), (-1, 2), 'MIDDLE'),
        ])
        
        # Bordas
        estilo.extend([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ])
        
        return estilo
    
    # Aplicar estilos às tabelas
    tabela_acertos_portugues_1.setStyle(TableStyle(aplicar_cores_acertos(tabela_acertos_portugues_1, dados_acertos_portugues_1)))
    tabela_acertos_portugues_2.setStyle(TableStyle(aplicar_cores_acertos(tabela_acertos_portugues_2, dados_acertos_portugues_2)))
    
    # Manter título e tabelas juntos
    elementos_acertos_portugues = [
        Spacer(1, 2),  # Espaço antes do subtítulo
        subtitulo_acertos,
        Spacer(1, 1),  # Espaço antes do título da disciplina
        titulo_portugues_acertos,
        Spacer(1, 1),  # Espaço antes da primeira tabela
        tabela_acertos_portugues_1,
        Spacer(1, 6),  # Espaço maior entre as tabelas (1-13 e 14-26)
        tabela_acertos_portugues_2
    ]
    
    elements.append(KeepTogether(elementos_acertos_portugues))
    
    # 18. TABELA DE ACERTOS POR HABILIDADE - MATEMÁTICA
    elements.append(Spacer(1, 6))  # Espaço antes da próxima disciplina
    
    titulo_matematica_acertos = Paragraph("MATEMÁTICA", subtitulo_tabela_style)
    
    # Dados da tabela de acertos por habilidade - Matemática (fixos por enquanto)
    dados_acertos_matematica_1 = [
        # Linha 1: Números das questões
        ['1ª Q', '2ª Q', '3ª Q', '4ª Q', '5ª Q', '6ª Q', '7ª Q', '8ª Q', '9ª Q', '10ª Q', '11ª Q', '12ª Q', '13ª Q'],
        # Linha 2: Códigos das habilidades
        ['9N1.1', '9N1.2', '9N1.3', '9N2.1', '9N1.4', '9N2.2', '9N2.3', '9N1.5', '9A1.1', '9N2.4', '9N1.6', '9N2.5', '9N1.7'],
        # Linha 3: Percentuais de acerto
        ['72.5%', '58.3%', '81.2%', '45.7%', '63.8%', '52.1%', '48.9%', '75.4%', '69.1%', '56.7%', '78.3%', '64.2%', '82.6%']
    ]
    
    dados_acertos_matematica_2 = [
        # Linha 1: Números das questões
        ['14ª Q', '15ª Q', '16ª Q', '17ª Q', '18ª Q', '19ª Q', '20ª Q', '21ª Q', '22ª Q', '23ª Q', '24ª Q', '25ª Q', '26ª Q'],
        # Linha 2: Códigos das habilidades
        ['9N2.6', '9N1.8', '9N2.7', '9A1.2', '9N1.9', '9N2.8', '9A1.3', '9N1.10', '9N2.9', '9A1.4', '9N1.11', '9N2.10', '9A1.5'],
        # Linha 3: Percentuais de acerto
        ['71.8%', '83.4%', '67.2%', '79.1%', '74.6%', '68.9%', '76.3%', '72.7%', '85.2%', '69.4%', '81.9%', '73.8%', '87.1%']
    ]
    
    # Criar tabelas de acertos por habilidade - Matemática
    tabela_acertos_matematica_1 = Table(dados_acertos_matematica_1, colWidths=[35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35])
    tabela_acertos_matematica_2 = Table(dados_acertos_matematica_2, colWidths=[35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35, 35])
    
    # Aplicar estilos às tabelas de matemática
    tabela_acertos_matematica_1.setStyle(TableStyle(aplicar_cores_acertos(tabela_acertos_matematica_1, dados_acertos_matematica_1)))
    tabela_acertos_matematica_2.setStyle(TableStyle(aplicar_cores_acertos(tabela_acertos_matematica_2, dados_acertos_matematica_2)))
    
    # Manter título e tabelas juntos
    elementos_acertos_matematica = [
        titulo_matematica_acertos,
        Spacer(1, 1),  # Espaço antes da primeira tabela
        tabela_acertos_matematica_1,
        Spacer(1, 6),  # Espaço maior entre as tabelas (1-13 e 14-26)
        tabela_acertos_matematica_2
    ]
    
    elements.append(KeepTogether(elementos_acertos_matematica))
    
    # Construir PDF
    print("=== INICIANDO CONSTRUÇÃO DO PDF ===")
    print(f"Total de elements: {len(elements)}")
    print("Chamando doc.build(elements)...")
    doc.build(elements)
    print("doc.build() concluído com sucesso")
    
    # Obter conteúdo do buffer
    print("Obtendo conteúdo do buffer...")
    buffer.seek(0)
    pdf_content = buffer.getvalue()
    buffer.close()
    print(f"PDF gerado com {len(pdf_content)} bytes")
    
    # Salvar arquivo de teste
    filename = f"teste_capa_pdf_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    with open(filename, 'wb') as f:
        f.write(pdf_content)
    
    print(f"✅ PDF de teste (CAPA) salvo como: {filename}")
    print("=== TESTE DE CAPA CONCLUÍDO COM SUCESSO ===")
    
    return filename

if __name__ == "__main__":
    try:
        filename = test_pdf_capa()
        print(f"\n🎉 Teste de CAPA concluído! Arquivo gerado: {filename}")
        print("Abra o arquivo PDF para verificar a capa.")
        
    except Exception as e:
        print(f"❌ Erro durante o teste: {str(e)}")
        import traceback
        traceback.print_exc()

