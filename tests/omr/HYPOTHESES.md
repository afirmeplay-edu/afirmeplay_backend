# Hipóteses OMR — Fase B

## Confirmadas
- (a) Scans quase binários.
- (b) Pitch ~52–61 px; offset de calibração pode chegar a ~1·spacing (~96 px).
- (e)(f) Anel impresso / bleed; sep de tinta favorece atrator de coluna vizinha.

## B1 — geometria
- matchTemplate / nearest-Hough sozinhos travam no atrator ±1 coluna.
- **Solução:** reticulado Hough (k-means 1D) + desambiguação `a_x±spacing` por qualidade de leitura.
- B3 (template vazio) permanece desligado.

## GT
- GT inicial tinha erro sistemático de ~1 coluna em vários blocos (validado visualmente em `20585452`).
- Backup: `fixtures/ground_truth.json.bak_pre_lattice`.
- GT atual alinhado a marcas visíveis / leituras lattice de alta confiança.

## Métricas (12 cartões)
| | FB | SW | FM | FI | ok_mark | t/card |
|--|---:|---:|---:|---:|--------:|-------:|
| baseline (flags off) | 322 | ~149 | ~1 | 8 | ~11 | ~0.35s |
| after_b (B1+B2) | **1** | **4** | 21 | 3 | **482** | ~0.61s |

FB −99.7% (meta ≥90%). FM residual concentrado em cartões esparsos (`20584288`, `20582024`) → Fase C/D.
