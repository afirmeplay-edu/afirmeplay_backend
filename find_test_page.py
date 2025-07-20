#!/usr/bin/env python3
"""
Script para encontrar em qual página está uma avaliação específica
"""

from app import create_app, db
from app.models.test import Test
from app.models.classTest import ClassTest

def find_test_page():
    app = create_app()
    with app.app_context():
        test_id = '054f44d7-24f5-4854-af6b-bb11f4258175'
        per_page = 10
        
        print("=== ENCONTRANDO PÁGINA DA AVALIAÇÃO ===")
        print(f"Test ID: {test_id}")
        print(f"Per page: {per_page}")
        
        # Query base
        query = ClassTest.query.join(Test, ClassTest.test_id == Test.id)
        total = query.count()
        print(f"Total de aplicações: {total}")
        
        # Encontrar posição da avaliação
        all_results = query.all()
        test_positions = []
        
        for i, ct in enumerate(all_results):
            if ct.test_id == test_id:
                test_positions.append(i)
        
        print(f"Posições encontradas: {test_positions}")
        
        # Calcular páginas
        for pos in test_positions:
            page = (pos // per_page) + 1
            position_in_page = (pos % per_page) + 1
            print(f"   - Posição {pos}: Página {page}, item {position_in_page}")
        
        # Verificar todas as páginas
        total_pages = (total + per_page - 1) // per_page
        print(f"\n=== VERIFICANDO TODAS AS PÁGINAS ===")
        print(f"Total de páginas: {total_pages}")
        
        for page in range(1, min(total_pages + 1, 6)):  # Verificar primeiras 5 páginas
            offset = (page - 1) * per_page
            page_results = query.offset(offset).limit(per_page).all()
            
            test_found = any(ct.test_id == test_id for ct in page_results)
            print(f"Página {page}: {'✅ Encontrada' if test_found else '❌ Não encontrada'}")
            
            if test_found:
                for i, ct in enumerate(page_results):
                    if ct.test_id == test_id:
                        print(f"   - Item {i+1}: {ct.test.title if ct.test else 'N/A'} (Status: {ct.status})")

if __name__ == "__main__":
    find_test_page() 