# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import os
import math
import csv
import qrcode
import sys
# Adicionar o diretório pai ao path para encontrar o módulo app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Imports do nosso sistema
from app import create_app
from app.models.test import Test
from app.models.student import Student
from app.models.testSession import TestSession
from app.models.formCoordinates import FormCoordinates
from app import db

# Imports para PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, portrait
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader

# --- Parâmetros Globais de Layout ---
# (Idênticos)
LARGURA_CONTEUDO = 700
ALTURA_CONTEUDO = 300
PADDING_EXTERNO = 10
LARGURA_FINAL = LARGURA_CONTEUDO + (2 * PADDING_EXTERNO) # 720
ALTURA_FINAL = ALTURA_CONTEUDO + (2 * PADDING_EXTERNO)   # 320
LARGURA_COL_NUM = 35
LARGURA_COL_ALT = 40
ALTURA_LINHA = 28
PADDING_HORIZONTAL_COL = 8
PADDING_VERTICAL_FORM = 10
RAIO_CIRCULO = 9
ESPESSURA_LINHA = 1
TAMANHO_FONTE_NUM = 16
TAMANHO_FONTE_ALT = 14
ALTERNATIVAS = ["A", "B", "C", "D"]
MAX_QUESTOES_POR_COLUNA = 10
QR_CODE_SIZE = 100
TAMANHO_FONTE_NOME = 14
PADDING_NOME_QR = 5
PADDING_LEFT_AREA_QR = 15
PADDING_QR_FORM = 25
SPACING_FORM_COLS = 30
MAX_LARGURA_NOME = QR_CODE_SIZE + 10

# --- Função Auxiliar para Desenhar Uma Coluna (sem alterações) ---
# Coleta coordenadas ABSOLUTAS (relativas ao 0,0 da imagem final)
def desenhar_coluna_formulario(desenho, fonte_num, fonte_alt, num_questao_inicial, num_questoes_nesta_coluna, offset_x, offset_y, lista_coords_abs):
    """Desenha uma única coluna do formulário com borda inferior ajustada
       e adiciona coordenadas ABSOLUTAS à lista_coords_abs."""
    largura_col_unica = LARGURA_COL_NUM + (len(ALTERNATIVAS) * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
    altura_efetiva_linhas = num_questoes_nesta_coluna * ALTURA_LINHA
    y_final_borda_real = offset_y + altura_efetiva_linhas

    desenho.line([(offset_x, offset_y), (offset_x, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
    desenho.line([(offset_x + largura_col_unica - 1, offset_y), (offset_x + largura_col_unica - 1, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
    x_vert_num = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM
    desenho.line([(x_vert_num, offset_y), (x_vert_num, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)

    # W e H são sempre inteiros
    coord_width = RAIO_CIRCULO * 2
    coord_height = RAIO_CIRCULO * 2

    desenho.line([(offset_x, offset_y), (offset_x + largura_col_unica - 1, offset_y)], fill='black', width=ESPESSURA_LINHA)

    if num_questoes_nesta_coluna == 0:
         desenho.line([(offset_x, offset_y), (offset_x + largura_col_unica - 1, offset_y)], fill='black', width=ESPESSURA_LINHA)
         return

    for i in range(num_questoes_nesta_coluna):
        linha_atual = num_questao_inicial + i
        y_linha_superior = offset_y + (i * ALTURA_LINHA)
        y_linha_inferior = y_linha_superior + ALTURA_LINHA
        centro_y_linha = y_linha_superior + (ALTURA_LINHA / 2)

        desenho.line([(offset_x, y_linha_inferior), (offset_x + largura_col_unica - 1, y_linha_inferior)], fill='black', width=ESPESSURA_LINHA)

        texto_num = str(linha_atual)
        centro_x_num = offset_x + PADDING_HORIZONTAL_COL + (LARGURA_COL_NUM / 2)
        try:
             desenho.text((centro_x_num, centro_y_linha), texto_num, fill='black', font=fonte_num, anchor="mm")
        except AttributeError:
             bbox_num = desenho.textbbox((0, 0), texto_num, font=fonte_num)
             largura_texto_num = bbox_num[2] - bbox_num[0]; altura_texto_num = bbox_num[3] - bbox_num[1]
             x_num_texto = centro_x_num - (largura_texto_num / 2)
             y_num_texto = centro_y_linha - (altura_texto_num / 2)
             desenho.text((x_num_texto, y_num_texto - 2), texto_num, fill='black', font=fonte_num)

        for j, alt in enumerate(ALTERNATIVAS):
            centro_x_alt = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM + (j * LARGURA_COL_ALT) + (LARGURA_COL_ALT / 2)

            x0_circ = centro_x_alt - RAIO_CIRCULO; y0_circ = centro_y_linha - RAIO_CIRCULO
            x1_circ = centro_x_alt + RAIO_CIRCULO; y1_circ = centro_y_linha + RAIO_CIRCULO
            desenho.ellipse([(x0_circ, y0_circ), (x1_circ, y1_circ)], outline='black', width=ESPESSURA_LINHA)
            try:
                desenho.text((centro_x_alt, centro_y_linha), alt, fill='black', font=fonte_alt, anchor="mm")
            except AttributeError:
                bbox_alt = desenho.textbbox((0, 0), alt, font=fonte_alt)
                largura_texto_alt = bbox_alt[2] - bbox_alt[0]; altura_texto_alt = bbox_alt[3] - bbox_alt[1]
                x_alt_texto = centro_x_alt - (largura_texto_alt / 2)
                y_alt_texto = centro_y_linha - (altura_texto_alt / 2)
                desenho.text((x_alt_texto, y_alt_texto - 1), alt, fill='black', font=fonte_alt)

            # Guarda coordenadas ABSOLUTAS, já convertidas para INT aqui
            coord_x_abs = int(round(x0_circ))
            coord_y_abs = int(round(y0_circ))
            lista_coords_abs.append((coord_x_abs, coord_y_abs, coord_width, coord_height))


# --- Função para Ler Alunos (sem alterações) ---
def ler_alunos(nome_arquivo_csv="alunos.txt"):
    """
    Lê um arquivo CSV de alunos, tentando vírgula e depois ponto e vírgula como delimitadores.
    Espera encontrar as colunas 'id' e 'nome'.
    Lida com valores ausentes (que se tornam None) em algumas colunas.
    """
    alunos = []
    delimitadores_tentar = [',', ';']

    try:
        # Determina o caminho absoluto para depuração
        caminho_arquivo_abs = os.path.abspath(nome_arquivo_csv)
        if not os.path.exists(caminho_arquivo_abs):
             print(f"Erro Crítico: Arquivo '{nome_arquivo_csv}' não encontrado no caminho: '{caminho_arquivo_abs}'.")
             return None

        with open(caminho_arquivo_abs, mode='r', newline='', encoding='utf-8-sig') as csvfile:
            leitor = None
            delimitador_usado = None

            # Tenta os delimitadores comuns
            for delim in delimitadores_tentar:
                try:
                    csvfile.seek(0) # Volta ao início
                    leitor_teste = csv.DictReader(csvfile, delimiter=delim)
                    # Verifica cabeçalhos (tentando limpar espaços neles também)
                    fieldnames_limpos = []
                    if leitor_teste.fieldnames:
                         fieldnames_limpos = [name.strip() for name in leitor_teste.fieldnames]

                    if fieldnames_limpos and 'id' in fieldnames_limpos and 'nome' in fieldnames_limpos:
                        leitor = leitor_teste
                        leitor.fieldnames = fieldnames_limpos # Usa os nomes limpos
                        delimitador_usado = delim
                        print(f"Arquivo CSV lido com sucesso usando o delimitador: '{delimitador_usado}'")
                        break # Sai do loop de tentativas

                except Exception as e_try:
                    # Ignora erros durante a tentativa, apenas não define o leitor
                    # print(f"Debug: Falha ao tentar delimitador '{delim}': {e_try}") # Descomente para depuração
                    pass

            # Se nenhum leitor válido foi encontrado
            if leitor is None:
                 csvfile.seek(0)
                 primeira_linha = csvfile.readline().strip()
                 print(f"Erro Crítico: Não foi possível ler o arquivo '{nome_arquivo_csv}' corretamente com os delimitadores {delimitadores_tentar}.")
                 print(f"          Verifique se o arquivo usa um desses delimitadores e se contém as colunas 'id' e 'nome' (sem espaços extras).")
                 print(f"          Cabeçalhos encontrados na primeira linha (bruto): '{primeira_linha}'")
                 # Tenta ler cabeçalhos com delimitadores explicitamente para dar mais detalhes
                 for delim in delimitadores_tentar:
                      try:
                           csvfile.seek(0)
                           temp_reader = csv.reader(csvfile, delimiter=delim)
                           header = next(temp_reader)
                           print(f"          Tentativa com delimitador '{delim}' resultou em cabeçalhos: {header}")
                      except:
                           pass # Ignora erros na tentativa de diagnóstico
                 return None

            # Processa as linhas usando o leitor que funcionou
            contador_linhas_processadas = 0
            for linha_num, linha in enumerate(leitor):
                 try:
                    # CORREÇÃO AQUI: Aplica strip() apenas se o valor for string
                    linha_limpa = {}
                    for k, v in linha.items():
                        chave_limpa = k # Assume que as chaves já estão limpas pelo fieldnames_limpos
                        valor_limpo = v.strip() if isinstance(v, str) else v # <--- A MUDANÇA PRINCIPAL
                        linha_limpa[chave_limpa] = valor_limpo

                    # Verifica se id e nome existem e não são vazios/None
                    if linha_limpa.get('id') and linha_limpa.get('nome'):
                        alunos.append(linha_limpa)
                        contador_linhas_processadas += 1
                    else:
                        print(f"Aviso: Linha {linha_num + 2} ignorada por ter ID ('{linha_limpa.get('id')}') ou Nome ('{linha_limpa.get('nome')}') inválido/vazio após limpeza.") # +2 por causa do cabeçalho e index 0
                 except Exception as e_linha:
                    # Captura outros erros inesperados no processamento da linha
                    print(f"Erro inesperado ao processar linha {linha_num + 2}: {e_linha} - Conteúdo bruto: {linha}")


        if not alunos:
             print(f"Aviso: Nenhum aluno válido foi adicionado da leitura de '{nome_arquivo_csv}'. Verifique os Avisos acima.")
        else:
             print(f"{contador_linhas_processadas} alunos lidos com sucesso.")


        return alunos

    except FileNotFoundError:
        # Este erro já é tratado acima com os.path.abspath, mas deixamos como fallback
        print(f"Erro Crítico: Arquivo '{nome_arquivo_csv}' não encontrado.")
        return None
    except Exception as e:
        print(f"Erro inesperado ao abrir ou processar o arquivo CSV: {e}")
        return None

# --- Função Auxiliar para Quebrar Texto (sem alterações) ---
def wrap_text(text, font, max_width):
    # (Código idêntico)
    linhas = []
    palavras = text.split()
    if not palavras:
        return [], 0, 0

    temp_img = Image.new('RGB', (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    linha_atual = ""
    if palavras:
        linha_atual = palavras[0]

    altura_linha_aprox = 0
    try:
        bbox = temp_draw.textbbox((0, 0), "Tg", font=font)
        altura_linha_aprox = bbox[3] - bbox[1]
    except AttributeError:
        largura_temp, altura_linha_aprox = temp_draw.textsize("Tg", font=font)
    altura_linha_aprox = int(altura_linha_aprox * 1.2)

    for palavra in palavras[1:]:
        linha_teste = linha_atual + " " + palavra
        largura_teste = 0
        try:
            largura_teste = temp_draw.textlength(linha_teste, font=font)
        except AttributeError:
             try:
                 bbox_teste = temp_draw.textbbox((0,0), linha_teste, font=font)
                 largura_teste = bbox_teste[2] - bbox_teste[0]
             except AttributeError:
                 largura_teste, _ = temp_draw.textsize(linha_teste, font=font)

        if largura_teste <= max_width:
            linha_atual = linha_teste
        else:
            linhas.append(linha_atual)
            linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)

    altura_total_texto = len(linhas) * altura_linha_aprox
    return linhas, altura_total_texto, altura_linha_aprox

# --- Função Principal (Coordenadas Relativas INTEIRAS) ---
def gerar_formulario_com_qrcode(aluno_id, aluno_nome, num_questoes_total, nome_arquivo_saida):
    """
    Gera formulário em 720x320, retorna a imagem e as coordenadas INTEIRAS das
    respostas e do QR Code RELATIVAS ao canto sup. esq. do RETÂNGULO EXTERNO.
    """
    if not 1 <= num_questoes_total <= 20:
        print(f"Erro: Número de questões inválido ({num_questoes_total}) para o ID {aluno_id}.")
        return None, None, None

    offset_global_x = PADDING_EXTERNO
    offset_global_y = PADDING_EXTERNO

    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=4, border=2)
    qr.add_data(str(aluno_id))
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").resize((QR_CODE_SIZE, QR_CODE_SIZE))

    try:
        fonte_num = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_NUM)
        fonte_alt = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_ALT)
        fonte_nome = ImageFont.truetype("arialbd.ttf", TAMANHO_FONTE_NOME)
    except IOError:
        try:
            fonte_num = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_NUM)
            fonte_alt = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_ALT)
            fonte_nome = ImageFont.truetype("DejaVuSans-Bold.ttf", TAMANHO_FONTE_NOME)
        except IOError:
            print("Aviso: Fontes Arial/DejaVu Sans (Bold) não encontradas.")
            fonte_num = ImageFont.load_default()
            fonte_alt = ImageFont.load_default()
            fonte_nome = ImageFont.load_default()

    linhas_nome, altura_bloco_nome, altura_linha_nome = wrap_text(aluno_nome, fonte_nome, MAX_LARGURA_NOME)

    largura_col_unica = LARGURA_COL_NUM + (len(ALTERNATIVAS) * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
    altura_bloco_form_para_layout = MAX_QUESTOES_POR_COLUNA * ALTURA_LINHA

    X_QR_FIXO_REL = PADDING_LEFT_AREA_QR
    Y_QR_FIXO_REL = (ALTURA_CONTEUDO / 2) - (QR_CODE_SIZE / 2)
    Y_QR_FIXO_REL = max(5, Y_QR_FIXO_REL)

    y_nome_bottom_rel = Y_QR_FIXO_REL - PADDING_NOME_QR
    y_nome_inicio_rel = y_nome_bottom_rel - altura_bloco_nome
    y_nome_inicio_rel = max(5, y_nome_inicio_rel)

    y_form_linhas_inicio_rel = (ALTURA_CONTEUDO / 2) - (altura_bloco_form_para_layout / 2)
    y_form_linhas_inicio_rel = max(5, y_form_linhas_inicio_rel)

    offset_x_col_esq_form_rel = X_QR_FIXO_REL + max(QR_CODE_SIZE, MAX_LARGURA_NOME) + PADDING_QR_FORM
    offset_x_col_dir_form_rel = offset_x_col_esq_form_rel + largura_col_unica + SPACING_FORM_COLS

    imagem = Image.new('RGB', (LARGURA_FINAL, ALTURA_FINAL), 'white')
    desenho = ImageDraw.Draw(imagem)
    coordenadas_respostas_abs = []

    x_qr_abs = offset_global_x + X_QR_FIXO_REL
    y_qr_abs = offset_global_y + Y_QR_FIXO_REL
    y_nome_inicio_abs = offset_global_y + y_nome_inicio_rel
    offset_x_col_esq_form_abs = offset_global_x + offset_x_col_esq_form_rel
    offset_x_col_dir_form_abs = offset_global_x + offset_x_col_dir_form_rel
    y_form_linhas_inicio_abs = offset_global_y + y_form_linhas_inicio_rel

    # Desenhar Nome
    y_linha_atual_nome_abs = y_nome_inicio_abs
    x_max_nome_abs = 0
    for linha in linhas_nome:
        largura_linha = 0
        try: largura_linha = desenho.textlength(linha, font=fonte_nome)
        except AttributeError:
            try: bbox = desenho.textbbox((0,0), linha, font=fonte_nome); largura_linha = bbox[2]-bbox[0]
            except: largura_linha, _ = desenho.textsize(linha, font=fonte_nome)

        x_nome_centro_rel = X_QR_FIXO_REL + (MAX_LARGURA_NOME / 2)
        x_linha_nome_rel = x_nome_centro_rel - (largura_linha / 2)
        x_linha_nome_abs = offset_global_x + x_linha_nome_rel

        # Usa int() para garantir posição inteira do texto
        desenho.text((int(round(x_linha_nome_abs)), int(round(y_linha_atual_nome_abs))), linha, fill='black', font=fonte_nome)
        y_linha_atual_nome_abs += altura_linha_nome
        x_max_nome_abs = max(x_max_nome_abs, x_linha_nome_abs + largura_linha)

    # Colar QR Code (já usa int)
    imagem.paste(img_qr, (int(round(x_qr_abs)), int(round(y_qr_abs))))

    # Desenhar Formulário(s) e coletar coords ABSOLUTAS
    if num_questoes_total <= MAX_QUESTOES_POR_COLUNA:
        num_questoes_col_esq = num_questoes_total
        desenhar_coluna_formulario(desenho, fonte_num, fonte_alt, 1, num_questoes_col_esq, int(round(offset_x_col_esq_form_abs)), int(round(y_form_linhas_inicio_abs)), coordenadas_respostas_abs)
    else:
        num_questoes_col_esq = MAX_QUESTOES_POR_COLUNA
        num_questoes_col_dir = num_questoes_total - MAX_QUESTOES_POR_COLUNA
        desenhar_coluna_formulario(desenho, fonte_num, fonte_alt, 1, num_questoes_col_esq, int(round(offset_x_col_esq_form_abs)), int(round(y_form_linhas_inicio_abs)), coordenadas_respostas_abs)
        desenhar_coluna_formulario(desenho, fonte_num, fonte_alt, 11, num_questoes_col_dir, int(round(offset_x_col_dir_form_abs)), int(round(y_form_linhas_inicio_abs)), coordenadas_respostas_abs)


    # Calcular limites MÁXIMOS potenciais do conteúdo (absolutos)
    x_min_potential_abs = x_qr_abs
    y_min_potential_abs = min(y_nome_inicio_abs, y_form_linhas_inicio_abs)
    x_max_potential_abs = offset_x_col_dir_form_abs + largura_col_unica
    x_max_potential_abs = max(x_max_potential_abs, x_qr_abs + QR_CODE_SIZE)
    x_max_potential_abs = max(x_max_potential_abs, x_max_nome_abs)
    y_max_potential_form_abs = y_form_linhas_inicio_abs + altura_bloco_form_para_layout
    y_max_potential_qr_abs = y_qr_abs + QR_CODE_SIZE
    y_max_potential_nome_abs = y_nome_inicio_abs + altura_bloco_nome
    y_max_potential_abs = max(y_max_potential_form_abs, y_max_potential_qr_abs, y_max_potential_nome_abs)

    # Definir coordenadas do retângulo externo FIXO (absolutas)
    # Arredonda aqui para garantir que a origem do relativo seja inteira
    rect_x0 = int(round(x_min_potential_abs - PADDING_EXTERNO))
    rect_y0 = int(round(y_min_potential_abs - PADDING_EXTERNO))
    rect_x1 = int(round(x_max_potential_abs + PADDING_EXTERNO))
    rect_y1 = int(round(y_max_potential_abs + PADDING_EXTERNO))

    rect_x0 = max(0, rect_x0)
    rect_y0 = max(0, rect_y0)
    rect_x1 = min(LARGURA_FINAL - 1, rect_x1)
    rect_y1 = min(ALTURA_FINAL - 1, rect_y1)

    # Desenha o retângulo externo FIXO
    desenho.rectangle([(rect_x0, rect_y0), (rect_x1, rect_y1)], outline='black', width=ESPESSURA_LINHA * 2)

    # ***** CONVERSÃO DAS COORDENADAS PARA RELATIVAS INTEIRAS *****
    coordenadas_respostas_relativas = []
    for abs_x, abs_y, w, h in coordenadas_respostas_abs:
        # abs_x e abs_y já são int da função desenhar_coluna
        # rect_x0 e rect_y0 agora também são int
        rel_x = abs_x - rect_x0
        rel_y = abs_y - rect_y0
        # w e h já são int
        coordenadas_respostas_relativas.append((rel_x, rel_y, w, h))

    # Converte coordenadas absolutas do QR (que podem ser float) para int
    qr_x_abs_int = int(round(x_qr_abs))
    qr_y_abs_int = int(round(y_qr_abs))
    # Calcula coordenadas relativas usando a origem inteira do retângulo
    qr_coords_rel_x = qr_x_abs_int - rect_x0
    qr_coords_rel_y = qr_y_abs_int - rect_y0
    # w e h do QR já são inteiros (QR_CODE_SIZE)
    qr_coords_rel = (qr_coords_rel_x, qr_coords_rel_y, QR_CODE_SIZE, QR_CODE_SIZE)
    # *************************************************************

    # --- Salvar e Retornar ---
    try:
        imagem.save(nome_arquivo_saida)
        # Retorna coordenadas RELATIVAS INTEIRAS
        return imagem, coordenadas_respostas_relativas, qr_coords_rel
    except Exception as e:
        print(f"Erro ao salvar a imagem '{nome_arquivo_saida}': {e}")
        return None, None, None

# --- Função para Gerar PDF (Layout 1x4 Retrato com Espaçamento Ajustado) ---
def gerar_pdf_formularios(lista_arquivos_png, nome_pdf_saida):
    """Gera um PDF A4 Retrato com até 4 formulários por página (layout 1x4),
       maximizando o tamanho e ajustando espaçamento vertical para caber."""
    if not lista_arquivos_png:
        print("Nenhum arquivo PNG para adicionar ao PDF.")
        return

    print(f"Iniciando geração do PDF '{nome_pdf_saida}' (A4 Retrato, 1x4)...")

    try:
        c = canvas.Canvas(nome_pdf_saida, pagesize=portrait(A4))
        largura_a4, altura_a4 = portrait(A4)

        imgs_por_linha = 1
        linhas_por_pagina = 4
        imgs_por_pagina = imgs_por_linha * linhas_por_pagina

        margem_h = 1.5 * cm
        margem_v = 1.0 * cm

        largura_util = largura_a4 - (2 * margem_h)
        altura_util = altura_a4 - (2 * margem_v)

        slot_largura_max = largura_util
        slot_altura_max = altura_util / linhas_por_pagina

        escala_larg = slot_largura_max / LARGURA_FINAL
        escala_alt = slot_altura_max / ALTURA_FINAL
        escala = min(escala_larg, escala_alt)

        img_largura_pdf = LARGURA_FINAL * escala
        img_altura_pdf = ALTURA_FINAL * escala

        x_start = margem_h + (largura_util - img_largura_pdf) / 2

        altura_total_imagens = linhas_por_pagina * img_altura_pdf
        espaco_v_total_restante = altura_util - altura_total_imagens

        if espaco_v_total_restante >= 0:
             espaco_v = espaco_v_total_restante / (linhas_por_pagina + 1)
             espaco_v = max(0.2 * cm, espaco_v)
        else:
             print("Aviso: Imagens podem estar muito grandes para caber perfeitamente com as margens.")
             espaco_v = 0.2 * cm

        contador_img_pagina = 0
        for i, img_path in enumerate(lista_arquivos_png):
            if not os.path.exists(img_path):
                print(f"Aviso: Arquivo de imagem não encontrado, pulando: {img_path}")
                continue

            img_na_pagina = contador_img_pagina % imgs_por_pagina
            linha_idx = img_na_pagina

            y_img = altura_a4 - margem_v - ((linha_idx + 1) * (img_altura_pdf + espaco_v)) + espaco_v

            try:
                img_reader = ImageReader(img_path)
                c.drawImage(img_reader, x_start, y_img, width=img_largura_pdf, height=img_altura_pdf, preserveAspectRatio=True, mask='auto')
                contador_img_pagina += 1

                if contador_img_pagina % imgs_por_pagina == 0 and i < len(lista_arquivos_png) - 1:
                    c.showPage()
            except Exception as e_draw:
                 print(f"Erro ao desenhar imagem '{img_path}' no PDF: {e_draw}")

        c.save()
        print(f"PDF '{nome_pdf_saida}' gerado com sucesso com {contador_img_pagina} formulários.")
        print(f"   Tamanho de cada formulário no PDF: {img_largura_pdf/cm:.2f} cm x {img_altura_pdf/cm:.2f} cm")
        print(f"   Espaçamento vertical entre formulários: {espaco_v/cm:.2f} cm")


    except Exception as e_pdf:
        print(f"Erro geral ao gerar PDF: {e_pdf}")


# --- Bloco Principal de Execução (usando banco de dados) ---
if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)

    # Inicializar aplicação Flask
    app = create_app()
    with app.app_context():
        while True:
            try:
                test_id = input("Digite o ID do teste: ")
                if test_id:
                    break
                else:
                    print("Por favor, digite um ID válido.")
            except ValueError:
                print("Entrada inválida! Digite um ID válido.")

        # Buscar teste no banco de dados
        test = Test.query.get(test_id)
        if not test:
            print(f"Teste {test_id} não encontrado no banco de dados")
            exit()

        # Buscar alunos do teste através de TestSession
        test_sessions = TestSession.query.filter_by(test_id=test_id).all()
        if not test_sessions:
            print(f"Nenhuma sessão de teste encontrada para o teste {test_id}")
            exit()

        # Buscar os alunos das sessões
        student_ids = [ts.student_id for ts in test_sessions]
        students = Student.query.filter(Student.id.in_(student_ids)).all()
        
        if not students:
            print(f"Nenhum aluno encontrado para o teste {test_id}")
            exit()

        print(f"Encontrados {len(students)} alunos para o teste {test_id}")

        # Buscar número de questões do teste
        from app.models.testQuestion import TestQuestion
        test_questions = TestQuestion.query.filter_by(test_id=test_id).all()
        num_q = len(test_questions)
        
        if num_q == 0:
            print(f"Nenhuma questão encontrada para o teste {test_id}")
            exit()

        print(f"Teste tem {num_q} questões")

        output_dir = "formularios_gerados"
        os.makedirs(output_dir, exist_ok=True)

        print("\nIniciando geração dos formulários PNG (Tamanho Final: {}x{})...".format(LARGURA_FINAL, ALTURA_FINAL))
        todas_coordenadas_respostas_rel = {}
        coordenadas_qr_salvas_rel = None
        lista_pngs_gerados = []

        total_alunos = len(students)
        for idx, student in enumerate(students):
            aluno_id = str(student.id)
            aluno_nome = student.name
            nome_arquivo_seguro = "".join(c for c in aluno_nome if c.isalnum() or c in (' ', '_')).rstrip().replace(" ", "_")
            nome_arquivo_base = f"formulario_{aluno_id}_{nome_arquivo_seguro}.png"
            nome_arquivo_png = os.path.join(output_dir, nome_arquivo_base)

            img_gerada, coords_resp_rel, coords_qr_rel = gerar_formulario_com_qrcode(aluno_id, aluno_nome, num_q, nome_arquivo_png)

            if img_gerada and coords_resp_rel and coords_qr_rel:
                todas_coordenadas_respostas_rel[aluno_id] = coords_resp_rel
                lista_pngs_gerados.append(nome_arquivo_png)
                if coordenadas_qr_salvas_rel is None:
                    coordenadas_qr_salvas_rel = coords_qr_rel
                
                # Salvar coordenadas no banco de dados
                form_coordinates = FormCoordinates(
                    test_id=test_id,
                    qr_code_id=aluno_id,
                    student_id=aluno_id,
                    coordinates=coords_resp_rel
                )
                db.session.add(form_coordinates)
                print(f"  ➕ Coordenadas salvas para {aluno_nome} (ID: {aluno_id})")
            else:
                 print(f"Falha ao gerar formulário para {aluno_nome} (ID:{aluno_id})")

            print(f"Progresso: {idx + 1}/{total_alunos} formulários gerados.", end='\r')

        # Salvar no banco de dados
        try:
            db.session.commit()
            print(f"\n✅ Coordenadas salvas no banco de dados")
        except Exception as e:
            print(f"\n❌ Erro ao salvar coordenadas: {e}")
            db.session.rollback()

        print(f"\n{len(lista_pngs_gerados)}/{total_alunos} formulários PNG gerados com sucesso em '{output_dir}'.")

        # --- Gerar PDF ---
        if lista_pngs_gerados:
            nome_arquivo_pdf = os.path.join(output_dir, "formularios_todos.pdf")
            gerar_pdf_formularios(lista_pngs_gerados, nome_arquivo_pdf)
        else:
             print("Nenhum formulário PNG foi gerado, PDF não será criado.")

    print("\nScript finalizado.")