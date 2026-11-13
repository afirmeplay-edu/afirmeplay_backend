# Harness OMR (`tests/omr`)

Regressão do corretor `AnswerSheetCorrectionNewGrid` **sem banco**.

## Rodar

```bash
cd afirmeplay_backend
python tests/omr/run_harness.py --tag baseline
```

Requisitos: `opencv-python`, `numpy`. Não precisa Flask/DB.

## Artefatos

- `fixtures/ground_truth.json` — marcação esperada por imagem (`null` = branco, `"INVALID"` = dupla real)
- `reports/<tag>/report.json` — métricas completas
- `reports/<tag>/report.md` — tabela por cartão
- `reports/<tag>/overlays/` — debug visual

## Métricas

- `false_blank` — marca real lida como branco
- `false_mark` — branco lido como letra
- `letter_swap` — letra errada
- `false_invalid` — INVALID indevido
