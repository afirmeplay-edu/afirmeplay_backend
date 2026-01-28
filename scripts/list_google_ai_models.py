# -*- coding: utf-8 -*-
"""
Script para listar os modelos disponíveis no Google AI Studio (Gemini)
para a chave/plano configurado.

Uso:
  python scripts/list_google_ai_models.py
  python scripts/list_google_ai_models.py --key SUA_CHAVE_AQUI

A chave pode vir de:
  - Variável de ambiente GOOGLE_AI_STUDIO_API_KEY
  - Argumento --key (opcional)
"""
import argparse
import os
import sys

# Carregar .env se existir (igual ao projeto)
try:
    from dotenv import load_dotenv
    load_dotenv("app/.env")
except ImportError:
    pass

import google.generativeai as genai


def main():
    parser = argparse.ArgumentParser(description="Lista modelos disponíveis no Google AI Studio (Gemini)")
    parser.add_argument(
        "--key",
        type=str,
        default=None,
        help="API key do Google AI Studio (opcional; usa GOOGLE_AI_STUDIO_API_KEY se não informado)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Mostrar mais detalhes de cada modelo (nome, display_name, etc.)",
    )
    args = parser.parse_args()

    api_key = args.key or os.getenv("GOOGLE_AI_STUDIO_API_KEY")
    if not api_key:
        print("Erro: informe a chave por --key ou defina GOOGLE_AI_STUDIO_API_KEY no ambiente (ou em app/.env)")
        sys.exit(1)

    genai.configure(api_key=api_key)

    print("Modelos disponíveis para seu plano (Google AI Studio / Gemini):\n")
    try:
        for model in genai.list_models():
            # model pode ser objeto (name, display_name) ou dict-like
            if hasattr(model, "name"):
                name = model.name
                display = getattr(model, "display_name", "")
                desc = getattr(model, "description", "")
            else:
                name = model.get("name", model.get("id", str(model)))
                display = model.get("display_name", "")
                desc = model.get("description", "")
            if args.verbose:
                print(f"  {name}")
                if display:
                    print(f"    display_name: {display}")
                if desc:
                    print(f"    description: {(desc[:80] + '...') if len(desc) > 80 else desc}")
                print()
            else:
                # Para GOOGLE_AI_STUDIO_MODEL use só o id (ex: gemini-1.5-flash)
                short_name = name.replace("models/", "") if name.startswith("models/") else name
                print(f"  {short_name}")
    except Exception as e:
        print(f"Erro ao listar modelos: {e}")
        sys.exit(1)

    print("\nConcluído. Use um dos nomes acima em GOOGLE_AI_STUDIO_MODEL (ex: gemini-1.5-flash).")


if __name__ == "__main__":
    main()
