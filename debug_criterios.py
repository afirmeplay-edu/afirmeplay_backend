#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para debug dos critérios de detecção
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator

def debug_criterios():
    app = create_app()
    with app.app_context():
        pdf_generator = PhysicalTestPDFGenerator()
        
        # Testar critérios com as proporções detectadas
        proporcoes_teste = {
            'A': 0.625,
            'B': 0.475, 
            'C': 0.388,
            'D': 0.400
        }
        
        print("🔧 Testando critérios de detecção...")
        print(f"📊 Proporções: {proporcoes_teste}")
        
        # Aplicar critérios
        resultado = pdf_generator._aplicar_criterios_deteccao(proporcoes_teste, 1)
        
        print(f"✅ Resultado: {resultado}")
        
        # Testar com diferentes proporções
        print("\n🔧 Testando com proporções mais baixas...")
        proporcoes_teste2 = {
            'A': 0.625,
            'B': 0.475, 
            'C': 0.388,
            'D': 0.400
        }
        
        resultado2 = pdf_generator._aplicar_criterios_deteccao(proporcoes_teste2, 2)
        print(f"✅ Resultado 2: {resultado2}")

if __name__ == "__main__":
    debug_criterios()
