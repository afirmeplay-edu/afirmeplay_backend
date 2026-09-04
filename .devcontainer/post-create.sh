#!/usr/bin/env bash
# DevContainer post-create: garante deps Python mesmo se requirements.txt mudou após o build da imagem.
set -euo pipefail

echo ">>> Atualizando dependências Python (requirements.txt)..."
sudo python -m pip install --upgrade pip
sudo pip install -r requirements.txt

echo ">>> Checando Poppler (pdf2image)..."
if command -v pdftoppm >/dev/null 2>&1; then
  echo "    pdftoppm: $(command -v pdftoppm)"
else
  echo "    AVISO: pdftoppm não encontrado no PATH"
fi

if [ ! -f app/.env ]; then
  echo
  echo "    AVISO: app/.env não encontrado."
  echo "    Copie app/.env.example para app/.env e preencha DATABASE_URL e as demais chaves."
fi

echo
echo ">>> Pronto. Suba a API com:"
echo "    python run.py"
echo
echo "    Celery (opcional):"
echo "    celery -A app.report_analysis.celery_app worker --loglevel=info --concurrency=4 --prefetch-multiplier=1"
