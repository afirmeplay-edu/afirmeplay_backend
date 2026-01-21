"""
NOVA ABORDAGEM: Detecção baseada em realidade, não em grid teórico

Princípio: Deixe a imagem dizer onde estão as bolhas.
Não force a imagem a se encaixar num modelo rígido.

Fluxo:
1. Threshold adaptativo + Morphology
2. Encontrar contornos (bolhas reais)
3. Filtrar por área + circularidade + bounding box quadrado
4. Agrupar por LINHAS (clustering por Y)
5. Classificar RELATIVAMENTE (esquerda→direita = A→D)
6. Fill ratio em bolhas reais (não esperadas)
"""

import cv2
import numpy as np
from scipy import stats
from collections import defaultdict

def detectar_bolhas_robustas(block_img_gray):
    """
    Detectar bolhas usando threshold adaptativo + morphology.
    
    ✅ Sem HoughCircles
    ✅ Sem grid virtual
    ✅ Baseado em contornos reais
    """
    
    h, w = block_img_gray.shape[:2]
    
    # Tentar múltiplos métodos e combinar
    bolhas_totais = set()
    
    # Método 1: Threshold adaptativo (para imagens reais com variação de iluminação)
    thresh1 = cv2.adaptiveThreshold(
        block_img_gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=21,
        C=10
    )
    
    # Método 2: Threshold simples (para casos mais diretos)
    _, thresh2 = cv2.threshold(block_img_gray, 100, 255, cv2.THRESH_BINARY)
    
    # Método 3: Threshold Otsu (adaptativo automático)
    _, thresh3 = cv2.threshold(block_img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    thresholds = [thresh1, thresh2, thresh3]
    
    for thresh_idx, thresh in enumerate(thresholds):
        # Morphology
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filtro 1: Área (bolha típica: raio ~7px = área ~150px²)
            if area < 80 or area > 300:
                continue
            
            # Filtro 2: Bounding box aproximadamente quadrado
            x, y, w_bb, h_bb = cv2.boundingRect(contour)
            aspect_ratio = float(w_bb) / h_bb if h_bb > 0 else 0
            if aspect_ratio < 0.7 or aspect_ratio > 1.3:
                continue
            
            # Filtro 3: Circularidade
            perimeter = cv2.arcLength(contour, True)
            if perimeter == 0:
                continue
            circularity = 4 * np.pi * area / (perimeter ** 2)
            if circularity < 0.6:
                continue
            
            # ✅ Bolha válida
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            radius = int(np.sqrt(area / np.pi))
            
            # Usar tupla (cx, cy) como chave única para evitar duplicatas
            bolhas_totais.add((cx, cy, radius, area, circularity))
    
    # Converter de volta para lista
    bolhas = []
    for cx, cy, radius, area, circularity in bolhas_totais:
        bolhas.append({
            'cx': cx,
            'cy': cy,
            'radius': radius,
            'area': area,
            'circularity': circularity
        })
    
    print(f"[INFO] Detectadas {len(bolhas)} bolhas (testados {len(thresholds)} métodos de threshold)")
    return bolhas, thresh1


def agrupar_bolhas_por_linhas(bolhas, tolerance_y=8):
    """
    Agrupar bolhas por LINHAS (questões).
    
    Usa clustering por Y com tolerância.
    Cada grupo = 1 questão com múltiplas alternativas.
    """
    
    if not bolhas:
        return []
    
    # Ordenar por Y
    bolhas_sorted = sorted(bolhas, key=lambda b: b['cy'])
    
    linhas = []
    grupo_atual = [bolhas_sorted[0]]
    y_ref = bolhas_sorted[0]['cy']
    
    for bolha in bolhas_sorted[1:]:
        # Se Y está próximo da referência, adicionar ao grupo
        if abs(bolha['cy'] - y_ref) <= tolerance_y:
            grupo_atual.append(bolha)
        else:
            # Novo grupo
            linhas.append(grupo_atual)
            grupo_atual = [bolha]
            y_ref = bolha['cy']
    
    # Último grupo
    if grupo_atual:
        linhas.append(grupo_atual)
    
    # Dentro de cada linha, ordenar por X (esquerda → direita)
    for linha in linhas:
        linha.sort(key=lambda b: b['cx'])
    
    print(f"[INFO] Agrupadas em {len(linhas)} linhas")
    return linhas


def classificar_alternativas(linhas):
    """
    Classificar alternativas RELATIVAMENTE.
    
    Para cada linha (questão):
    - 1ª bolha (esquerda) = A
    - 2ª bolha = B
    - 3ª bolha = C
    - 4ª bolha (direita) = D
    
    ✅ Não depende de coordenadas absolutas
    ✅ Funciona com N alternativas
    """
    
    questoes = []
    
    for linha_idx, linha in enumerate(linhas):
        # Número de alternativas nesta linha
        num_alternativas = len(linha)
        
        if num_alternativas == 0:
            print(f"[WARN] Linha {linha_idx}: Sem bolhas!")
            continue
        
        # Mapear bolhas para letras
        alternativas = []
        for alt_idx, bolha in enumerate(linha):
            letra = chr(65 + alt_idx)  # A, B, C, D, ...
            alternativas.append({
                'letra': letra,
                'bolha': bolha,
                'idx': alt_idx
            })
        
        questoes.append({
            'q_num': linha_idx + 1,
            'num_alternativas': num_alternativas,
            'alternativas': alternativas,
            'y_position': linha[0]['cy']  # Y real da questão
        })
    
    print(f"[INFO] Classificadas {len(questoes)} questões")
    return questoes


def medir_fill_ratio_robusto(block_img_gray, bolha, expand=1.0):
    """
    Medir fill_ratio em bolha REAL.
    
    expand: fator de expansão do raio (1.0 = exato, 1.1 = 10% maior)
    """
    
    h, w = block_img_gray.shape[:2]
    
    cx = int(bolha['cx'])
    cy = int(bolha['cy'])
    radius = int(bolha['radius'] * expand)
    
    # Criar máscara circular
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (cx, cy), radius, 255, -1)
    
    # Extrair pixels dentro do círculo
    pixels_inside = block_img_gray[mask == 255]
    
    if len(pixels_inside) == 0:
        return 0.0
    
    # Contar pixels escuros (< 100 é seguro para papel com marca preta)
    dark_pixels = np.sum(pixels_inside < 100)
    
    fill_ratio = dark_pixels / len(pixels_inside)
    return fill_ratio


def classificar_resposta_questao(block_img_gray, questao, threshold=0.3):
    """
    Classificar resposta de uma questão.
    
    Processa as 4 alternativas da questão.
    Retorna: ('A', 0.75) ou (None, 0.0)
    """
    
    fill_ratios = []
    for alt in questao['alternativas']:
        fill_ratio = medir_fill_ratio_robusto(block_img_gray, alt['bolha'])
        fill_ratios.append({
            'letra': alt['letra'],
            'fill_ratio': fill_ratio
        })
    
    # Encontrar alternativa com maior fill_ratio
    best = max(fill_ratios, key=lambda x: x['fill_ratio'])
    
    if best['fill_ratio'] >= threshold:
        return best['letra'], best['fill_ratio']
    else:
        return None, best['fill_ratio']


def processar_bloco_robusto(block_img_gray):
    """
    Pipeline completo: Detector robusto para um bloco.
    
    Retorna: {Q1: 'A', Q2: 'B', ..., Q6: None, ...}
    """
    
    print("\n" + "="*80)
    print("PROCESSANDO BLOCO COM NOVA ESTRATÉGIA")
    print("="*80)
    
    # 1. Detectar bolhas
    bolhas, thresh = detectar_bolhas_robustas(block_img_gray)
    
    if len(bolhas) < 4:
        print("[ERRO] Menos de 4 bolhas detectadas. Pode não ser um bloco de resposta.")
        return {}
    
    # 2. Agrupar por linhas
    linhas = agrupar_bolhas_por_linhas(bolhas, tolerance_y=8)
    
    if len(linhas) == 0:
        print("[ERRO] Nenhuma linha detectada.")
        return {}
    
    # 3. Classificar alternativas
    questoes = classificar_alternativas(linhas)
    
    # 4. Medir fill_ratio e classificar resposta
    respostas = {}
    for questao in questoes:
        q_num = questao['q_num']
        resposta, fill_ratio = classificar_resposta_questao(
            block_img_gray, 
            questao, 
            threshold=0.3
        )
        
        respostas[q_num] = resposta
        
        # Debug
        if q_num in [1, len(questoes)//2 + 1, len(questoes)]:
            print(f"\nQ{q_num}: Y={questao['y_position']}px")
            print(f"  {questao['num_alternativas']} alternativas")
            print(f"  Resposta: {resposta} (fill_ratio={fill_ratio:.2f})")
    
    print("\n" + "="*80)
    print(f"RESULTADO: {respostas}")
    print("="*80)
    
    return respostas


# ============================================================================
# TESTE COM IMAGEM SINTÉTICA
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("TESTE: Nova estratégia vs. HoughCircles")
    print("="*80)
    
    # Criar imagem sintética (bloco de resposta)
    block_width = 155
    block_height = 473
    img = np.ones((block_height, block_width, 3), dtype=np.uint8) * 240
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Parâmetros baseados no grid (para referência)
    start_x = 34
    start_y = 15
    line_height = 18
    bubble_spacing = 19
    bubble_radius = 7
    
    # Gerar 6 questões com 4 alternativas cada
    # Algumas marcadas, algumas não
    questions = [1, 2, 3, 4, 5, 6]
    marked = [0, 1, 2, 1, 0, 2]  # Qual alternativa está marcada (None = nenhuma)
    
    for q_idx, q_num in enumerate(questions):
        y = start_y + q_idx * line_height
        
        for alt_idx in range(4):
            x = start_x + alt_idx * bubble_spacing + 7
            
            # Sempre desenhar círculo preto (preenchido)
            # A diferença está no "fill" - bolha marcada tem mais tinta
            if alt_idx == marked[q_idx]:
                # Bolha marcada: círculo preto sólido (mais tinta)
                cv2.circle(img, (x, y), bubble_radius, (0, 0, 0), -1)
            else:
                # Bolha não marcada: círculo cinza claro (menos tinta)
                cv2.circle(img, (x, y), bubble_radius, (220, 220, 220), -1)
    
    # Converter para cinza para processamento
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Salvar imagem de teste
    cv2.imwrite("debug_corrections/teste_sintetico_nova_abordagem.jpg", img)
    print("✓ Imagem sintética criada")
    
    # Processar com nova estratégia
    respostas = processar_bloco_robusto(img_gray)
    
    # Validar resultado
    print("\nValidação:")
    for q_num in questions:
        resp = respostas.get(q_num)
        expected = chr(65 + marked[q_num - 1])
        status = "✓" if resp == expected else "✗"
        print(f"{status} Q{q_num}: {resp} (esperado {expected})")
