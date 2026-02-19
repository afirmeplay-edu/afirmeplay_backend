#!/usr/bin/env python3
"""
Script para corrigir encoding de estados na tabela city.
Execute: python scripts/fix_city_states.py
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import db, create_app
from app.models.city import City

# Mapeamento de estados corretos
ESTADOS_CORRETOS = {
    'rondonia': 'Rondônia',
    'acre': 'Acre',
    'amazonas': 'Amazonas',
    'roraima': 'Roraima',
    'para': 'Pará',
    'amapa': 'Amapá',
    'tocantins': 'Tocantins',
    'maranhao': 'Maranhão',
    'piaui': 'Piauí',
    'ceara': 'Ceará',
    'rio grande do norte': 'Rio Grande do Norte',
    'paraiba': 'Paraíba',
    'pernambuco': 'Pernambuco',
    'alagoas': 'Alagoas',
    'sergipe': 'Sergipe',
    'bahia': 'Bahia',
    'minas gerais': 'Minas Gerais',
    'espirito santo': 'Espírito Santo',
    'rio de janeiro': 'Rio de Janeiro',
    'sao paulo': 'São Paulo',
    'parana': 'Paraná',
    'santa catarina': 'Santa Catarina',
    'rio grande do sul': 'Rio Grande do Sul',
    'mato grosso do sul': 'Mato Grosso do Sul',
    'mato grosso': 'Mato Grosso',
    'goias': 'Goiás',
    'distrito federal': 'Distrito Federal',
}

def normalize_for_comparison(text):
    """Remove acentos e normaliza para comparação."""
    import unicodedata
    if not text:
        return ""
    # Normalizar NFD (decompor acentos)
    nfd = unicodedata.normalize('NFD', text)
    # Remover marcas diacríticas
    without_accents = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return without_accents.lower().strip()

def main():
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("VERIFICANDO ESTADOS ATUAIS")
        print("=" * 60)
        
        # Buscar todos os estados únicos
        cities = City.query.all()
        estados_encontrados = {}
        
        for city in cities:
            estado = city.state
            if estado not in estados_encontrados:
                estados_encontrados[estado] = []
            estados_encontrados[estado].append(city.name)
        
        print(f"\nTotal de estados encontrados: {len(estados_encontrados)}\n")
        
        for estado, cidades in sorted(estados_encontrados.items()):
            print(f"  {estado}: {len(cidades)} cidade(s)")
        
        print("\n" + "=" * 60)
        print("CORRIGINDO ESTADOS")
        print("=" * 60)
        
        corrigidos = 0
        
        for city in cities:
            if not city.state:
                continue
            
            # Normalizar estado atual
            estado_normalizado = normalize_for_comparison(city.state)
            
            # Verificar se precisa correção
            if estado_normalizado in ESTADOS_CORRETOS:
                estado_correto = ESTADOS_CORRETOS[estado_normalizado]
                
                if city.state != estado_correto:
                    print(f"\n  Corrigindo: '{city.state}' → '{estado_correto}'")
                    print(f"    Cidade: {city.name} (ID: {city.id})")
                    city.state = estado_correto
                    corrigidos += 1
        
        if corrigidos > 0:
            print(f"\n{'-' * 60}")
            print(f"Total de cidades corrigidas: {corrigidos}")
            print(f"{'-' * 60}")
            
            resposta = input("\nDeseja salvar as alterações? (s/N): ")
            
            if resposta.lower() in ['s', 'sim', 'y', 'yes']:
                db.session.commit()
                print("\n✅ Alterações salvas com sucesso!")
            else:
                db.session.rollback()
                print("\n❌ Alterações descartadas.")
        else:
            print("\n✅ Nenhuma correção necessária. Todos os estados já estão corretos!")
        
        print("\n" + "=" * 60)
        print("ESTADOS FINAIS")
        print("=" * 60)
        
        # Buscar estados novamente
        cities = City.query.all()
        estados_finais = {}
        
        for city in cities:
            estado = city.state
            if estado not in estados_finais:
                estados_finais[estado] = 0
            estados_finais[estado] += 1
        
        print()
        for estado, total in sorted(estados_finais.items()):
            print(f"  {estado}: {total} cidade(s)")
        
        print("\n" + "=" * 60)

if __name__ == '__main__':
    main()
