#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste simples para gerar formulário sem dependências do Flask
"""

import sys
import os
from PIL import Image, ImageDraw, ImageFont
import qrcode
import uuid
import json

# Adicionar o diretório pai ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Parâmetros do formulário (copiados do formularios.py)
DPI_PNG = 150
_MM_POR_INCH = 25.4
A4_LARGURA_MM = 210
A4_ALTURA_MM = 297

A4_PX_LARGURA = int(DPI_PNG * (A4_LARGURA_MM / _MM_POR_INCH))
A4_PX_ALTURA = int(DPI_PNG * (A4_ALTURA_MM / _MM_POR_INCH))

# Parâmetros de layout
LARGURA_CONTEUDO = A4_PX_LARGURA - 20
PADDING_EXTERNO = 10
LARGURA_FINAL = A4_PX_LARGURA
ALTURA_FINAL = A4_PX_ALTURA
LARGURA_COL_NUM = 45
LARGURA_COL_ALT = 50
ALTURA_LINHA = 45
PADDING_HORIZONTAL_COL = 12
RAIO_CIRCULO = 14
ESPESSURA_LINHA = 3
TAMANHO_FONTE_NUM = 24
TAMANHO_FONTE_ALT = 22
ALTERNATIVAS = ["A", "B", "C", "D"]
MAX_QUESTOES_POR_COLUNA = 25
QR_CODE_SIZE = 150
TAMANHO_FONTE_NOME = 20
TAMANHO_FONTE_TITULO = 22
TAMANHO_FONTE_HEADER = 28
TAMANHO_FONTE_TEXTO = 20

def gerar_formulario_teste():
    """Gera um formulário de teste simples"""
    
    # Dados de teste
    aluno_id = "12345"
    aluno_nome = "João Silva Santos"
    num_questoes_total = 20
    
    # Calcular altura necessária
    altura_cabecalho = 300
    altura_instrucoes_estimada = 200
    questoes_por_linha = min(num_questoes_total, MAX_QUESTOES_POR_COLUNA)
    altura_grid_necessaria = (questoes_por_linha * ALTURA_LINHA) + 40 + 20
    altura_total_necessaria = altura_cabecalho + altura_instrucoes_estimada + altura_grid_necessaria + 100
    altura_imagem_final = max(ALTURA_FINAL, altura_total_necessaria)
    
    # Criar imagem
    imagem = Image.new('RGB', (LARGURA_FINAL, altura_imagem_final), 'white')
    desenho = ImageDraw.Draw(imagem)
    
    # Carregar fontes
    try:
        fonte_num = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_NUM)
        fonte_alt = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_ALT)
        fonte_nome = ImageFont.truetype("arialbd.ttf", TAMANHO_FONTE_NOME)
        fonte_titulo = ImageFont.truetype("arialbd.ttf", TAMANHO_FONTE_TITULO)
        fonte_header = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_HEADER)
        fonte_instrucoes = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_TEXTO)
    except IOError:
        try:
            fonte_num = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_NUM)
            fonte_alt = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_ALT)
            fonte_nome = ImageFont.truetype("DejaVuSans-Bold.ttf", TAMANHO_FONTE_NOME)
            fonte_titulo = ImageFont.truetype("DejaVuSans-Bold.ttf", TAMANHO_FONTE_TITULO)
            fonte_header = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_HEADER)
            fonte_instrucoes = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_TEXTO)
        except IOError:
            print("Usando fontes padrão")
            fonte_num = ImageFont.load_default()
            fonte_alt = ImageFont.load_default()
            fonte_nome = ImageFont.load_default()
            fonte_titulo = ImageFont.load_default()
            fonte_header = ImageFont.load_default()
            fonte_instrucoes = ImageFont.load_default()
    
    offset_global_x = PADDING_EXTERNO
    offset_global_y = PADDING_EXTERNO
    
    # Gerar QR Code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=2)
    qr.add_data(str(aluno_id))
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").resize((QR_CODE_SIZE, QR_CODE_SIZE))
    
    # Desenhar cabeçalho
    y_atual = offset_global_y + 10
    
    # Título "CARTÃO-RESPOSTA"
    try:
        largura_titulo = desenho.textlength("CARTÃO-RESPOSTA", font=fonte_titulo)
    except AttributeError:
        try: 
            bbox = desenho.textbbox((0,0), "CARTÃO-RESPOSTA", font=fonte_titulo)
            largura_titulo = bbox[2]-bbox[0]
        except: 
            largura_titulo, _ = desenho.textsize("CARTÃO-RESPOSTA", font=fonte_titulo)
    
    x_titulo = offset_global_x + (LARGURA_CONTEUDO - largura_titulo) // 2
    desenho.text((int(x_titulo), int(y_atual)), "CARTÃO-RESPOSTA", fill='black', font=fonte_titulo)
    y_atual += 30
    
    # Turma
    try:
        largura_turma = desenho.textlength("Turma: 9º Ano A", font=fonte_header)
    except AttributeError:
        try: 
            bbox = desenho.textbbox((0,0), "Turma: 9º Ano A", font=fonte_header)
            largura_turma = bbox[2]-bbox[0]
        except: 
            largura_turma, _ = desenho.textsize("Turma: 9º Ano A", font=fonte_header)
    
    x_turma = offset_global_x + (LARGURA_CONTEUDO - largura_turma) // 2
    desenho.text((int(x_turma), int(y_atual)), "Turma: 9º Ano A", fill='black', font=fonte_header)
    y_atual += 40
    
    # Calcular altura do cabeçalho
    altura_base = 80
    altura_info_aluno = 150
    altura_tabela_nome = 80
    altura_prova_assinatura = 60
    header_height = altura_base + altura_info_aluno + altura_tabela_nome + altura_prova_assinatura + 30
    
    header_y_start = y_atual
    header_y_end = header_y_start + header_height
    
    # Desenhar borda da tabela de cabeçalho
    desenho.rectangle([
        (offset_global_x + 10, header_y_start),
        (offset_global_x + LARGURA_CONTEUDO - 10, header_y_end)
    ], outline='black', width=2)
    
    # Linha vertical para separar as colunas
    col_divider_x = offset_global_x + LARGURA_CONTEUDO - 200
    desenho.line([
        (col_divider_x, header_y_start),
        (col_divider_x, header_y_end)
    ], fill='black', width=1)
    
    # Coluna esquerda - Informações do aluno
    x_info = offset_global_x + 20
    y_info = header_y_start + 15
    
    # Informações do aluno
    desenho.text((x_info, y_info), f"Nome completo: {aluno_nome}", fill='black', font=fonte_nome)
    y_info += 40
    desenho.text((x_info, y_info), "Estado: Alagoas", fill='black', font=fonte_nome)
    y_info += 40
    desenho.text((x_info, y_info), "Município: São Miguel dos Campos", fill='black', font=fonte_nome)
    y_info += 40
    desenho.text((x_info, y_info), "Escola: Escola Municipal Rui Palmeira", fill='black', font=fonte_nome)
    y_info += 50
    
    # Label "NOME DO ALUNO:"
    desenho.text((x_info, y_info), "NOME DO ALUNO:", fill='black', font=fonte_nome)
    y_info += 25
    
    # Tabela para o aluno preencher o nome
    grid_x_start = x_info
    grid_y_start = y_info
    largura_disponivel = col_divider_x - 40 - x_info
    box_size = (largura_disponivel - (20 * 2)) // 26
    box_spacing = 1
    
    for row in range(2):
        for col in range(26):
            x_box = grid_x_start + col * (box_size + box_spacing)
            y_box = grid_y_start + row * (box_size + box_spacing)
            desenho.rectangle([
                (x_box, y_box),
                (x_box + box_size, y_box + box_size)
            ], outline='black', width=1)
    
    y_info += 70  # Espaçamento dos quadradinhos
    
    # Nome da prova
    desenho.text((x_info, y_info), "Nome da prova:", fill='black', font=fonte_nome)
    y_info += 25
    desenho.text((x_info, y_info), "2º AVALIE SÃO MIGUEL", fill='black', font=fonte_header)
    y_info += 50  # Aumentado para dar mais espaço para assinatura
    
    # Coluna direita - QR Code
    qr_x = col_divider_x + 10
    qr_y = header_y_start + 20
    imagem.paste(img_qr, (int(qr_x), int(qr_y)))
    
    # Label "QR Code:"
    qr_label_y = qr_y + QR_CODE_SIZE + 10
    desenho.text((qr_x, qr_label_y), "QR Code:", fill='black', font=fonte_nome)
    
    # Linha pontilhada para assinatura (no final do cabeçalho)
    line_y = header_y_end - 80  # Aumentado para dar mais espaço para assinatura
    line_x_start = offset_global_x + 20
    line_x_end = offset_global_x + LARGURA_CONTEUDO - 20
    line_center_x = (line_x_start + line_x_end) // 2
    
    # Desenhar linha pontilhada
    dash_length = 8
    gap_length = 4
    current_x = line_x_start
    while current_x < line_x_end:
        desenho.line([
            (current_x, line_y),
            (min(current_x + dash_length, line_x_end), line_y)
        ], fill='black', width=2)
        current_x += dash_length + gap_length
    
    # Label "Assinatura do participante:"
    try:
        largura_assinatura = desenho.textlength("Assinatura do participante:", font=fonte_nome)
    except AttributeError:
        try: 
            bbox = desenho.textbbox((0,0), "Assinatura do participante:", font=fonte_nome)
            largura_assinatura = bbox[2]-bbox[0]
        except: 
            largura_assinatura, _ = desenho.textsize("Assinatura do participante:", font=fonte_nome)
    
    x_assinatura = line_center_x - (largura_assinatura // 2)
    desenho.text((int(x_assinatura), int(line_y + 20)), "Assinatura do participante:", fill='black', font=fonte_nome)
    
    # Instruções
    y_instrucoes = header_y_end + 40
    instrucoes = [
        "1. Verifique se o seu nome completo, o número da sua matrícula e os demais dados impressos neste cartão CARTÃO-RESPOSTA estão corretos.",
        "2. O CARTÃO-RESPOSTA é o único documento que será utilizado para a correção eletrônica de suas provas.",
        "3. Preencha suas respostas neste CARTÃO-RESPOSTA nos campos apropriados.",
        "",
        "Para todas as marcações neste CARTÃO-RESPOSTA, preencha os círculos completamente e com nitidez."
    ]
    
    y_atual_instrucoes = y_instrucoes
    for i, instrucao in enumerate(instrucoes):
        if instrucao:
            desenho.text((offset_global_x + 20, y_atual_instrucoes), instrucao, fill='black', font=fonte_instrucoes)
            y_atual_instrucoes += 20
            
            # Adicionar espaçamento maior entre os itens 1, 2 e 3
            if instrucao.startswith(('1.', '2.', '3.')):
                y_atual_instrucoes += 30  # Aumentado para dar mais espaço entre instruções
        else:
            y_atual_instrucoes += 10
    
    # Linha separadora após as instruções
    y_linha_separadora = y_atual_instrucoes + 10
    desenho.line([
        (offset_global_x + 20, y_linha_separadora),
        (offset_global_x + LARGURA_CONTEUDO - 20, y_linha_separadora)
    ], fill='black', width=2)
    
    # Grid de respostas
    y_form_inicio = y_linha_separadora + 20
    altura_grid = altura_grid_necessaria
    
    # Desenhar borda da tabela de questões
    desenho.rectangle([
        (offset_global_x + 10, y_form_inicio),
        (offset_global_x + LARGURA_CONTEUDO - 10, y_form_inicio + altura_grid)
    ], outline='black', width=2)
    
    # Desenhar grid de respostas
    espaco_disponivel = LARGURA_CONTEUDO - 40
    espaco_entre_colunas = 20
    
    if num_questoes_total <= MAX_QUESTOES_POR_COLUNA:
        x_colunas = [offset_global_x + 20]
    else:
        num_colunas = (num_questoes_total + MAX_QUESTOES_POR_COLUNA - 1) // MAX_QUESTOES_POR_COLUNA
        if num_colunas > 4:
            num_colunas = 4
        
        largura_col_unica = LARGURA_COL_NUM + (len(ALTERNATIVAS) * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
        largura_total_colunas = (num_colunas * largura_col_unica) + ((num_colunas - 1) * espaco_entre_colunas)
        x_inicio = offset_global_x + 20 + (espaco_disponivel - largura_total_colunas) // 2
        
        x_colunas = []
        for i in range(num_colunas):
            x_colunas.append(x_inicio + i * (largura_col_unica + espaco_entre_colunas))
    
    # Desenhar colunas de questões
    for col_idx, x_col in enumerate(x_colunas):
        questoes_nesta_coluna = min(MAX_QUESTOES_POR_COLUNA, num_questoes_total - col_idx * MAX_QUESTOES_POR_COLUNA)
        
        # Desenhar bordas da coluna
        largura_col_unica = LARGURA_COL_NUM + (len(ALTERNATIVAS) * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
        altura_efetiva_linhas = questoes_nesta_coluna * ALTURA_LINHA
        y_final_borda_real = y_form_inicio + altura_efetiva_linhas + 20
        
        desenho.line([(x_col, y_form_inicio), (x_col, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
        desenho.line([(x_col + largura_col_unica - 1, y_form_inicio), (x_col + largura_col_unica - 1, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
        
        # Linha vertical separando número das alternativas
        x_vert_num = x_col + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM
        desenho.line([(x_vert_num, y_form_inicio), (x_vert_num, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
        
        # Desenhar questões
        for i in range(questoes_nesta_coluna):
            num_questao = col_idx * MAX_QUESTOES_POR_COLUNA + i + 1
            y_questao = y_form_inicio + i * ALTURA_LINHA
            
            # Número da questão
            desenho.text((x_col + PADDING_HORIZONTAL_COL + 5, y_questao + 5), str(num_questao), fill='black', font=fonte_num)
            
            # Alternativas
            for j, alt in enumerate(ALTERNATIVAS):
                x_alt = x_vert_num + 5 + j * LARGURA_COL_ALT
                y_alt = y_questao + 5
                
                # Círculo da alternativa
                desenho.ellipse([
                    (x_alt, y_alt),
                    (x_alt + RAIO_CIRCULO * 2, y_alt + RAIO_CIRCULO * 2)
                ], outline='black', width=ESPESSURA_LINHA)
                
                # Letra da alternativa
                desenho.text((x_alt + RAIO_CIRCULO - 3, y_alt + 2), alt, fill='black', font=fonte_alt)
    
    # Desenhar borda externa
    desenho.rectangle([
        (offset_global_x, offset_global_y),
        (offset_global_x + LARGURA_CONTEUDO, offset_global_y + altura_imagem_final - PADDING_EXTERNO)
    ], outline='black', width=ESPESSURA_LINHA * 2)
    
    # Salvar imagem
    imagem.save("teste_formulario.png")
    print(f"✅ Formulário de teste gerado!")
    print(f"📁 Arquivo: teste_formulario.png")
    print(f"📏 Dimensões: {imagem.size}")
    
    return imagem

if __name__ == "__main__":
    gerar_formulario_teste()
