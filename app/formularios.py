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
from reportlab.platypus import SimpleDocTemplate, Image as RLImage, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# --- Dimensões A4 em pixels (para o PNG) ---
# Escolha o DPI do PNG. 300 dá 2480 x 3508 px; 200 dá 1654 x 2339 px.
DPI_PNG = 150
_MM_POR_INCH = 25.4
A4_LARGURA_MM = 210
A4_ALTURA_MM  = 297

A4_PX_LARGURA = int(DPI_PNG * (A4_LARGURA_MM / _MM_POR_INCH))  # ~2480 px a 300 DPI
A4_PX_ALTURA  = int(DPI_PNG * (A4_ALTURA_MM  / _MM_POR_INCH))  # ~3508 px a 300 DPI

# --- Parâmetros Globais de Layout ---
# Ajustados para ocupar mais espaço da folha A4 com margem mínima
LARGURA_CONTEUDO = A4_PX_LARGURA - 20  # Usar quase toda largura A4 (10px de cada lado)
ALTURA_CONTEUDO = 1200   # Aumentado significativamente para formulário maior
PADDING_EXTERNO = 10     # Margem mínima de 10px
LARGURA_FINAL = A4_PX_LARGURA  # Usar toda largura A4
ALTURA_FINAL = A4_PX_ALTURA
LARGURA_COL_NUM = 45        # Aumentado para melhor visibilidade
LARGURA_COL_ALT = 50        # Aumentado para melhor visibilidade
ALTURA_LINHA = 45           # Aumentado para criar mais espaçamento visual entre as questões
PADDING_HORIZONTAL_COL = 12 # Aumentado para melhor espaçamento
PADDING_VERTICAL_FORM = 15  # Aumentado para melhor espaçamento
RAIO_CIRCULO = 14           # Aumentado para melhor visibilidade
ESPESSURA_LINHA = 3         # Aumentado para melhor definição das linhas
TAMANHO_FONTE_NUM = 24       # Aumentado para melhor legibilidade
TAMANHO_FONTE_ALT = 22       # Aumentado para melhor legibilidade
ALTERNATIVAS = ["A", "B", "C", "D"]
MAX_QUESTOES_POR_COLUNA = 25  # Aumentado para suportar até 100 questões (4 colunas)
QR_CODE_SIZE = 150           # Aumentado para melhor visibilidade
TAMANHO_FONTE_NOME = 20      # Nome do aluno / prova
TAMANHO_FONTE_TITULO = 22    # "CARTÃO-RESPOSTA"
TAMANHO_FONTE_HEADER = 28    # Nome, Estado, Município, Escola
TAMANHO_FONTE_TEXTO = 20     # Instruções
PADDING_NOME_QR = 5
PADDING_LEFT_AREA_QR = 15
PADDING_QR_FORM = 25
SPACING_FORM_COLS = 30
MAX_LARGURA_NOME = QR_CODE_SIZE + 10
HEADER_HEIGHT = 120  # Altura do cabeçalho com informações do aluno

# --- Função Auxiliar para Desenhar Uma Coluna (sem alterações) ---
# Coleta coordenadas ABSOLUTAS (relativas ao 0,0 da imagem final)
def desenhar_coluna_formulario(desenho, fonte_num, fonte_alt, num_questao_inicial, num_questoes_nesta_coluna, offset_x, offset_y, lista_coords_abs):
    """Desenha uma única coluna do formulário com borda inferior ajustada
       e adiciona coordenadas ABSOLUTAS à lista_coords_abs."""
    largura_col_unica = LARGURA_COL_NUM + (len(ALTERNATIVAS) * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
    altura_efetiva_linhas = num_questoes_nesta_coluna * ALTURA_LINHA
    # Altura final da coluna (sem padding extra desnecessário)
    padding_extra_final = 0  # Removido padding extra que causava linhas vazias
    y_final_borda_real = offset_y + altura_efetiva_linhas + padding_extra_final

    desenho.line([(offset_x, offset_y), (offset_x, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
    desenho.line([(offset_x + largura_col_unica - 1, offset_y), (offset_x + largura_col_unica - 1, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)
    x_vert_num = offset_x + PADDING_HORIZONTAL_COL + LARGURA_COL_NUM
    desenho.line([(x_vert_num, offset_y), (x_vert_num, y_final_borda_real)], fill='black', width=ESPESSURA_LINHA)

    # W e H são sempre inteiros
    coord_width = RAIO_CIRCULO * 2
    coord_height = RAIO_CIRCULO * 2

    desenho.line([(offset_x, offset_y), (offset_x + largura_col_unica - 1, offset_y)], fill='black', width=ESPESSURA_LINHA)

    if num_questoes_nesta_coluna == 0:
         return

    for i in range(num_questoes_nesta_coluna):
        linha_atual = num_questao_inicial + i
        y_linha_superior = offset_y + (i * ALTURA_LINHA)
        y_linha_inferior = y_linha_superior + ALTURA_LINHA
        centro_y_linha = y_linha_superior + (ALTURA_LINHA / 2)

        # Sempre desenhar linha horizontal para fechar cada questão
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
def _draw_text_with_bold(desenho, text, x, y, font_normal, font_bold):
    """Desenha texto com partes em negrito"""
    import re
    
    # Dividir texto por **texto**
    parts = re.split(r'(\*\*.*?\*\*)', text)
    current_x = x
    
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            # Texto em negrito
            bold_text = part[2:-2]  # Remove **
            desenho.text((current_x, y), bold_text, fill='black', font=font_bold)
            # Calcular largura do texto em negrito
            try:
                width = desenho.textlength(bold_text, font=font_bold)
            except AttributeError:
                try:
                    bbox = desenho.textbbox((0,0), bold_text, font=font_bold)
                    width = bbox[2] - bbox[0]
                except:
                    width = len(bold_text) * 8  # Fallback
            current_x += width
        else:
            # Texto normal
            if part.strip():  # Só desenhar se não for vazio
                desenho.text((current_x, y), part, fill='black', font=font_normal)
                try:
                    width = desenho.textlength(part, font=font_normal)
                except AttributeError:
                    try:
                        bbox = desenho.textbbox((0,0), part, font=font_normal)
                        width = bbox[2] - bbox[0]
                    except:
                        width = len(part) * 6  # Fallback
                current_x += width

def gerar_formulario_com_qrcode(aluno_id, aluno_nome, num_questoes_total, nome_arquivo_saida, student_data=None, test_data=None):
    """
    Gera formulário em 720x320, retorna a imagem e as coordenadas INTEIRAS das
    respostas e do QR Code RELATIVAS ao canto sup. esq. do RETÂNGULO EXTERNO.
    
    Args:
        aluno_id: ID do aluno
        aluno_nome: Nome do aluno
        num_questoes_total: Número total de questões (agora suporta até 100)
        nome_arquivo_saida: Nome do arquivo de saída
        student_data: Dicionário com dados completos do aluno (opcional)
        test_data: Dicionário com dados do teste (opcional)
    """
    if not 1 <= num_questoes_total <= 100:
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
        fonte_titulo = ImageFont.truetype("arialbd.ttf", TAMANHO_FONTE_TITULO)
        fonte_header = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_HEADER)
    except IOError:
        try:
            fonte_num = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_NUM)
            fonte_alt = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_ALT)
            fonte_nome = ImageFont.truetype("DejaVuSans-Bold.ttf", TAMANHO_FONTE_NOME)
            fonte_titulo = ImageFont.truetype("DejaVuSans-Bold.ttf", TAMANHO_FONTE_TITULO)
            fonte_header = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_HEADER)
        except IOError:
            print("Aviso: Fontes Arial/DejaVu Sans (Bold) não encontradas.")
            fonte_num = ImageFont.load_default()
            fonte_alt = ImageFont.load_default()
            fonte_nome = ImageFont.load_default()
            fonte_titulo = ImageFont.load_default()
            fonte_header = ImageFont.load_default()

    # Preparar dados do aluno (usar dados completos se disponíveis)
    if student_data:
        nome_aluno = student_data.get('student_name', aluno_nome)
        turma = student_data.get('class_name', 'Turma não informada')
        escola = student_data.get('school_name', 'Escola não informada')
        municipio = student_data.get('city_name', 'Município não informado')
        estado = student_data.get('state_name', 'Estado não informado')
    else:
        nome_aluno = aluno_nome
        turma = 'Turma não informada'
        escola = 'Escola não informada'
        municipio = 'Município não informado'
        estado = 'Estado não informado'

    # Calcular layout do grid de respostas
    largura_col_unica = LARGURA_COL_NUM + (len(ALTERNATIVAS) * LARGURA_COL_ALT) + (PADDING_HORIZONTAL_COL * 2)
    
    # Calcular número de colunas necessárias
    num_colunas = (num_questoes_total + MAX_QUESTOES_POR_COLUNA - 1) // MAX_QUESTOES_POR_COLUNA
    if num_colunas > 4:  # Máximo 4 colunas
        num_colunas = 4
    
    # Posições do QR Code (canto superior direito) - ajustado para novo layout
    x_qr_abs = offset_global_x + LARGURA_CONTEUDO - QR_CODE_SIZE - 80  # Aumentado conforme sugestão
    y_qr_abs = offset_global_y + 30

    # Calcular altura necessária para o grid de respostas (ANTES de criar a imagem)
    num_linhas_necessarias = (num_questoes_total + MAX_QUESTOES_POR_COLUNA - 1) // MAX_QUESTOES_POR_COLUNA
    if num_linhas_necessarias > 1:
        num_linhas_necessarias = 1  # Máximo 1 linha de colunas (até 4 colunas)
    
    questoes_por_linha = min(num_questoes_total, MAX_QUESTOES_POR_COLUNA)
    padding_extra_final = 0  # Removido padding extra desnecessário
    altura_grid_necessaria = (questoes_por_linha * ALTURA_LINHA) + 10  # Altura do grid sem padding extra
    
    # Calcular altura total necessária (ajustado para fontes menores)
    altura_cabecalho = 600  # Aumentado para dar mais espaço vertical
    altura_instrucoes_estimada = 250  # Aumentado para dar mais espaço
    altura_total_necessaria = altura_cabecalho + altura_instrucoes_estimada + altura_grid_necessaria + 150  # +150 para margens
    
    # Ajustar altura da imagem se necessário
    altura_imagem_final = max(ALTURA_FINAL, altura_total_necessaria)
    
    # Se a altura calculada for maior que ALTURA_FINAL, usar a altura calculada
    if altura_total_necessaria > ALTURA_FINAL:
        altura_imagem_final = altura_total_necessaria
    
    # Criar imagem com altura dinâmica
    imagem = Image.new('RGB', (LARGURA_FINAL, altura_imagem_final), 'white')
    desenho = ImageDraw.Draw(imagem)
    coordenadas_respostas_abs = []

    # Desenhar cabeçalho
    y_atual = offset_global_y + 10
    
    # Turma será desenhada na coluna da esquerda, abaixo da escola

    # Calcular altura necessária para o cabeçalho baseado no conteúdo (fontes menores)
    # Altura base: título + turma + espaçamentos
    altura_base = 100  # Ajustado para fontes menores
    
    # Altura das informações do aluno
    altura_info_aluno = 200  # Ajustado para fontes menores e espaçamentos
    
    # Altura da tabela do nome (2 linhas x 26 colunas)
    altura_tabela_nome = 80  # Ajustado para fontes menores
    
    # Altura da seção de prova e assinatura
    altura_prova_assinatura = 60  # Ajustado para fontes menores
    
    # Altura total do cabeçalho
    header_height = altura_base + altura_info_aluno + altura_tabela_nome + altura_prova_assinatura + 60  # +30 para padding
    
    header_y_start = y_atual
    header_y_end = header_y_start + header_height
    
    # Desenhar borda da tabela de cabeçalho
    desenho.rectangle([
        (offset_global_x + 10, header_y_start),
        (offset_global_x + LARGURA_CONTEUDO - 10, header_y_end)
    ], outline='black', width=2)
    
    # Linha vertical para separar as colunas (mais espaço para QR Code)
    col_divider_x = offset_global_x + LARGURA_CONTEUDO - 200  # Aumentado para dar mais espaço ao QR Code
    desenho.line([
        (col_divider_x, header_y_start),
        (col_divider_x, header_y_end)
    ], fill='black', width=1)

    # Coluna esquerda - Informações do aluno
    x_info = offset_global_x + 20
    y_info = header_y_start + 15
    
    # Nome completo (negrito)
    desenho.text((x_info, y_info), f"Nome completo: {nome_aluno}", fill='black', font=fonte_nome)
    y_info += 40
    
    # Estado (negrito)
    desenho.text((x_info, y_info), f"Estado: {estado}", fill='black', font=fonte_nome)
    y_info += 40
    
    # Município (negrito)
    desenho.text((x_info, y_info), f"Município: {municipio}", fill='black', font=fonte_nome)
    y_info += 40
    
    # Escola (negrito)
    desenho.text((x_info, y_info), f"Escola: {escola}", fill='black', font=fonte_nome)
    y_info += 30  # Espaçamento para turma
    
    # Turma (na coluna da esquerda, abaixo da escola)
    turma = student_data.get('turma', 'G') if student_data else 'G'
    desenho.text((x_info, y_info), f"Turma: {turma}", fill='black', font=fonte_nome)
    y_info += 30  # Espaçamento para NOME DO ALUNO
    
    # Label "NOME DO ALUNO:" (negrito)
    desenho.text((x_info, y_info), "NOME DO ALUNO:", fill='black', font=fonte_nome)
    y_info += 25
    
    # Tabela para o aluno preencher o nome (2 linhas x 26 colunas)
    grid_x_start = x_info
    grid_y_start = y_info
    
    # Calcular largura disponível para os quadradinhos (usar toda a coluna esquerda)
    largura_disponivel = col_divider_x - 10 - x_info  # Largura da coluna esquerda menos margens mínimas
    box_size = (largura_disponivel - (19 * 1)) // 20  # 19 espaços entre 20 caixas, usar 20 caixas
    box_spacing = 1  # Espaçamento menor entre caixas para maximizar largura
    
    for row in range(2):
        for col in range(20):
            x_box = grid_x_start + col * (box_size + box_spacing)
            y_box = grid_y_start + row * (box_size + box_spacing)
            desenho.rectangle([
                (x_box, y_box),
                (x_box + box_size, y_box + box_size)
            ], outline='black', width=1)
    
    y_info += 100  # Aumentado para evitar sobreposição com quadradinhos
    
    # Label "Nome da prova:" (negrito)
    desenho.text((x_info, y_info), "Nome da prova:", fill='black', font=fonte_nome)
    y_info += 30  # Aumentado para dar mais espaço entre label e nome da prova
    
    # Nome da prova (fonte menor)
    test_name = test_data.get('title', 'Avaliação') if test_data else 'Avaliação'
    desenho.text((x_info, y_info), test_name, fill='black', font=fonte_nome)
    y_info += 60  # Espaçamento maior para linha de assinatura (como na imagem)

    # Coluna direita - QR Code
    qr_x = col_divider_x + 10
    qr_y = header_y_start + 20
    imagem.paste(img_qr, (int(qr_x), int(qr_y)))
    
    # Label "QR Code:" (negrito)
    qr_label_y = qr_y + QR_CODE_SIZE + 10
    desenho.text((qr_x, qr_label_y), "QR Code:", fill='black', font=fonte_nome)
    
    # Linha pontilhada para assinatura (DENTRO do cabeçalho, abaixo do nome da prova)
    line_y = y_info + 20  # Posicionar abaixo do nome da prova, dentro do cabeçalho
    line_x_start = x_info  # Começar na coluna esquerda
    line_x_end = col_divider_x - 20  # Terminar antes da divisória das colunas
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
    
    # Label "Assinatura do participante:" (centralizado)
    try:
        largura_assinatura = desenho.textlength("Assinatura do participante:", font=fonte_nome)
    except AttributeError:
        try: bbox = desenho.textbbox((0,0), "Assinatura do participante:", font=fonte_nome); largura_assinatura = bbox[2]-bbox[0]
        except: largura_assinatura, _ = desenho.textsize("Assinatura do participante:", font=fonte_nome)
    
    x_assinatura = line_center_x - (largura_assinatura // 2)
    desenho.text((int(x_assinatura), int(line_y + 15)), "Assinatura do participante:", fill='black', font=fonte_nome)
    
    # Atualizar y_info para incluir a linha de assinatura no cabeçalho
    y_info = line_y + 40  # Espaçamento reduzido após o label

    # Desenhar instruções abaixo do cabeçalho
    y_instrucoes = header_y_end + 40  # Aumentado conforme sugestão
    
    # Instruções do cartão-resposta
    instrucoes = [
        "1. Verifique se o seu nome completo, o número da sua matrícula e os demais dados impressos neste cartão **CARTÃO-RESPOSTA** estão corretos. Preencha o seu nome completo e assine somente no local apropriado.",
        "2. O **CARTÃO-RESPOSTA** é o único documento que será utilizado para a correção eletrônica de suas provas. Não o amasse, não o dobre, nem o rasure. Não haverá substituição deste **CARTÃO-RESPOSTA** por erro de preenchimento.",
        "3. Preencha suas respostas neste **CARTÃO-RESPOSTA** nos campos apropriados, sob a pena de impossibilidade da leitura óptica de suas respostas."
    ]
    
    # Texto adicional (após linha divisória)
    texto_adicional = "Para todas as marcações neste **CARTÃO-RESPOSTA**, preencha os círculos completamente e com nitidez, utilizando caneta esferográfica de tinta preta fabricada em material transparente."
    
    # Fonte para as instruções (menor que o cabeçalho)
    try:
        fonte_instrucoes = ImageFont.truetype("arial.ttf", TAMANHO_FONTE_TEXTO)
    except IOError:
        try:
            fonte_instrucoes = ImageFont.truetype("DejaVuSans.ttf", TAMANHO_FONTE_TEXTO)
        except IOError:
            fonte_instrucoes = ImageFont.load_default()
    
    # Desenhar instruções (apenas itens 1, 2, 3)
    y_atual_instrucoes = y_instrucoes
    
    for i, instrucao in enumerate(instrucoes):
        # Quebrar texto em linhas se necessário
        try:
            largura_max = LARGURA_CONTEUDO - 80  # Aumentada margem para evitar ultrapassar borda direita
            linhas_texto, altura_texto, altura_linha = wrap_text(instrucao, fonte_instrucoes, largura_max)
            
            for j, linha in enumerate(linhas_texto):
                # Processar texto com negrito
                _draw_text_with_bold(desenho, linha, offset_global_x + 20, y_atual_instrucoes, fonte_instrucoes, fonte_nome)
                y_atual_instrucoes += altura_linha + 4  # Espaçamento ajustado para fonte menor
        except Exception as e:
            # Fallback se wrap_text falhar
            _draw_text_with_bold(desenho, instrucao, offset_global_x + 20, y_atual_instrucoes, fonte_instrucoes, fonte_nome)
            y_atual_instrucoes += 20  # Ajustado para fonte menor
        
        # Adicionar espaçamento maior entre os itens 1, 2 e 3
        y_atual_instrucoes += 30  # Aumentado para dar mais espaço entre instruções
    
    # Linha divisória grossa (entre item 3 e texto adicional)
    y_linha_divisoria = y_atual_instrucoes + 10
    desenho.line([
        (offset_global_x + 20, y_linha_divisoria),
        (offset_global_x + LARGURA_CONTEUDO - 20, y_linha_divisoria)
    ], fill='black', width=3)  # Linha mais grossa
    
    # Desenhar texto adicional (após linha divisória)
    y_atual_instrucoes = y_linha_divisoria + 20  # Espaço após linha divisória
    
    try:
        largura_max = LARGURA_CONTEUDO - 80
        linhas_texto, altura_texto, altura_linha = wrap_text(texto_adicional, fonte_instrucoes, largura_max)
        
        for j, linha in enumerate(linhas_texto):
            _draw_text_with_bold(desenho, linha, offset_global_x + 20, y_atual_instrucoes, fonte_instrucoes, fonte_nome)
            y_atual_instrucoes += altura_linha + 4
    except Exception as e:
        _draw_text_with_bold(desenho, texto_adicional, offset_global_x + 20, y_atual_instrucoes, fonte_instrucoes, fonte_nome)
        y_atual_instrucoes += 20
    
    # Desenhar grid de respostas em tabela separada (abaixo do texto adicional)
    y_form_inicio = y_atual_instrucoes + 20  # Espaço após o texto adicional
    
    # Usar a altura já calculada anteriormente
    altura_grid = altura_grid_necessaria
    
    
    # Calcular altura total das instruções
    altura_instrucoes = y_linha_divisoria - y_instrucoes + 20  # Altura das instruções + linha divisória + padding
    
    # Borda da tabela removida - as colunas individuais já têm suas próprias bordas
    # desenho.rectangle([
    #     (offset_global_x + 10, y_form_inicio),
    #     (offset_global_x + LARGURA_CONTEUDO - 10, y_form_inicio + altura_grid)
    # ], outline='black', width=2)
    
    # Calcular posições das colunas
    espaco_disponivel = LARGURA_CONTEUDO - 40  # Margem de 20px de cada lado
    espaco_entre_colunas = 20
    
    if num_colunas == 1:
        x_colunas = [offset_global_x + 20]
    elif num_colunas == 2:
        x_colunas = [
            offset_global_x + 20,
            offset_global_x + 20 + largura_col_unica + espaco_entre_colunas
        ]
    elif num_colunas == 3:
        x_colunas = [
            offset_global_x + 20,
            offset_global_x + 20 + largura_col_unica + espaco_entre_colunas,
            offset_global_x + 20 + 2 * (largura_col_unica + espaco_entre_colunas)
        ]
    else:  # 4 colunas
        x_colunas = [
            offset_global_x + 20,
            offset_global_x + 20 + largura_col_unica + espaco_entre_colunas,
            offset_global_x + 20 + 2 * (largura_col_unica + espaco_entre_colunas),
            offset_global_x + 20 + 3 * (largura_col_unica + espaco_entre_colunas)
        ]
    
    # Ajustar posição do grid para dentro da tabela
    y_grid_interno = y_form_inicio + 20  # Padding interno da tabela
    
    # Desenhar colunas
    questao_atual = 1
    for col in range(num_colunas):
        if questao_atual > num_questoes_total:
            break
            
        questoes_restantes = num_questoes_total - questao_atual + 1
        questoes_nesta_coluna = min(MAX_QUESTOES_POR_COLUNA, questoes_restantes)
        
        desenhar_coluna_formulario(
            desenho, fonte_num, fonte_alt, 
            questao_atual, questoes_nesta_coluna, 
            int(x_colunas[col]), int(y_grid_interno), 
            coordenadas_respostas_abs
        )
        
        questao_atual += questoes_nesta_coluna


    # Calcular limites MÁXIMOS potenciais do conteúdo (absolutos)
    x_min_potential_abs = min(x_colunas) if x_colunas else x_qr_abs
    y_min_potential_abs = header_y_start  # Começar do cabeçalho
    x_max_potential_abs = max(x_colunas) + largura_col_unica if x_colunas else x_qr_abs + QR_CODE_SIZE
    x_max_potential_abs = max(x_max_potential_abs, x_qr_abs + QR_CODE_SIZE)
    y_max_potential_form_abs = y_form_inicio + altura_grid  # Incluir altura da tabela de questões
    y_max_potential_qr_abs = y_qr_abs + QR_CODE_SIZE
    y_max_potential_instrucoes_abs = y_linha_divisoria + altura_instrucoes  # Incluir altura das instruções
    y_max_potential_abs = max(y_max_potential_form_abs, y_max_potential_qr_abs, y_max_potential_instrucoes_abs)

    # Definir coordenadas do retângulo externo FIXO (absolutas)
    # Arredonda aqui para garantir que a origem do relativo seja inteira
    rect_x0 = int(round(x_min_potential_abs - PADDING_EXTERNO))
    rect_y0 = int(round(y_min_potential_abs - PADDING_EXTERNO))
    rect_x1 = int(round(x_max_potential_abs + PADDING_EXTERNO))
    rect_y1 = int(round(y_max_potential_abs + PADDING_EXTERNO))

    rect_x0 = max(0, rect_x0)
    rect_y0 = max(0, rect_y0)
    # Permitir que a borda se expanda além dos limites fixos se necessário
    rect_x1 = max(rect_x1, LARGURA_FINAL - 1)  # Garantir largura mínima
    rect_y1 = max(rect_y1, altura_imagem_final - 1)  # Garantir altura mínima

    # Desenha o retângulo externo (necessário para correção do formulário)
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




