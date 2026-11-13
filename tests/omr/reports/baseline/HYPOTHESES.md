# Confirmação de hipóteses (antes de alterar o corretor)

Amostras: 12 JPGs em `avaliacoes_marcadas/` (scans ~1654×2338, warp → 2480×3508).
Harness: `tests/omr/run_harness.py --tag baseline` (sem DB).

## (a) Scans quase binários — CONFIRMADA

- Em todos os 12: `hist[:16]+hist[240:] ≈ 0.999` (scan) e ≈0.95 após A4.
- `unique_gray` ≈ 50–57 níveis (quase 1-bit).
- Marcas viram pontilhado/stippling; anéis impressos ficam irregulares.

## (b) Passo vertical / escala / âncoras — CONFIRMADA (e mais grave)

- Pitch real medido (Hough / projeção): **~52.5–53.8 px** vs `ROW_HEIGHT_PX=51.97`.
- Drift vertical visível nos overlays: linhas ciano sobem em relação às bolhas.
- **Offset sistemático por bloco** (Hough, mediana):
  - típico **dx ≈ +24…+28 px**, **dy ≈ +18…+27 px**
  - em alguns blocos (esp. B1) dx chega a **~55–60 px** (≈ 1× `BUBBLE_SPACING_PX`)
- Isso **ultrapassa o orçamento de ±12 px** da Fase B1.
- Com grid nominal, o baseline nos 2 cartões com GT já rotulados:
  - **55 falsos brancos**, **29 trocas de letra**, **1 INVALID indevido**, só **3 ok_mark**.
  - Causa dominante: amostrar fora da bolha marcada (geometria), não só limiar.

## (c) `_build_ink_strength_map` enfraquece marcas densas — PARCIAL / NÃO ISOLADA

- Em cartões binários o blur da própria imagem como “papel” **pode** elevar o papel local sob manchas densas e reduzir contraste.
- Porém, com centros ±25 px errados, o score já falha antes do mapa de tinta.
- **Decisão:** só implementar B2 **depois** de B1 (com busca ampla aprovada); medir contribuição isolada no harness.

## (d) Limiares absolutos FLOOR 28 / FLOOR_LO 18 — NÃO CONFIRMADA como causa principal

- Nos overlays, bolhas **claramente pretas** caem em branco porque o disco de análise está no papel/anel vizinho.
- Com geometria errada, baixar floor aumentaria falso marcado.
- **Decisão:** não mexer nos floors até geometria estável; C2 (duas passadas) pode ajudar em marcas fracas **após** B1.

## (e) Traços verticais cobrindo duas linhas — CONFIRMADA (presente)

- Ex.: Q5–Q7 coluna A no cartão `20574648` (cauda ligando A’s).
- Risco de bleed / INVALID / troca de linha.
- C3 permanece pertinente.

## (f) Anel impresso infla bolhas vazias — CONFIRMADA (presente)

- Scans binários: anel grosso e irregular; score de vazias sobe.
- Contribui a INVALID/ambiguidade quando o centro acerta o anel.
- B3 (template vazio) e raio interno 0.6·r (C1) permanecem pertinentes **após** alinhamento.

## Conclusão operacional

1. **Geometria é o gargalo #1.** Sem recuperar offset/pitch por bloco, B2/B3/C1/C2 não batem o critério de −90% falsos brancos.
2. B1 como especificado (±12 px) **é insuficiente** nestas amostras.
3. Proposta (pedir aprovação):  
   - **passo grosso** por bloco: estimar `(dx, dy)` mediano com busca ±40–50 px (Hough ou matchTemplate), **ou** regressão robusta com correspondências nessa janela;  
   - depois **refino fino ±12 px** + RANSAC `y=a+b·row`, `x=c+d·col`;  
   - fallback às constantes atuais se evidência fraca (como já previsto).
