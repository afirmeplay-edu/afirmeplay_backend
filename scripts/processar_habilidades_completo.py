"""
Script para processar TODAS as habilidades de Português e gerar o JSON formatado.

INSTRUÇÕES:
1. Cole o JSON completo fornecido pelo usuário no arquivo 'dados_originais.json' nesta pasta
2. Execute: python scripts/processar_habilidades_completo.py
3. O arquivo 'habilidades_portugues_data.json' será gerado automaticamente
"""

import json
import os

# IDs das séries
GRADE_IDS = {
    "1º Ano": "391ed6e8-fc45-46f8-8e4c-065005d2329f",
    "2º Ano": "74821122-e632-4301-b6f5-42b92b802a55",
    "3º Ano": "ea1ed64b-c9f5-4156-93b2-497ecf9e0d84",
    "4º Ano": "b8cdea4d-22fe-4647-a9f3-c575eb82c514",
    "5º Ano": "f5688bb2-9624-487f-ab1f-40b191c96b76"
}

PORTUGUES_ID = "4d29b4f1-7bd7-42c0-84d5-111dc7025b90"


def processar():
    """Processa o JSON e converte para o formato do banco."""
    
    # Carregar dados originais
    script_dir = os.path.dirname(__file__)
    input_file = os.path.join(script_dir, 'dados_originais.json')
    
    if not os.path.exists(input_file):
        print("❌ Arquivo 'dados_originais.json' não encontrado!")
        print("   Por favor, crie o arquivo com o JSON completo fornecido.")
        return
    
    print("📂 Carregando dados originais...")
    with open(input_file, 'r', encoding='utf-8') as f:
        dados = json.load(f)
    
    result = {"habilidades": []}
    org = dados.get("organizacao_curricular", {})
    
    # Processar habilidades compartilhadas
    print("\n📚 Processando habilidades compartilhadas...")
    for group in org.get("habilidades_compartilhadas", []):
        series_aplicaveis = group.get("series_aplicaveis", "")
        habilidades = group.get("habilidades", [])
        
        for hab in habilidades:
            result["habilidades"].append({
                "code": hab["codigo"],
                "description": hab["descricao"],
                "subject_id": PORTUGUES_ID,
                "grade_id": None,  # Compartilhadas usam NULL
                "comment": f"Compartilhada: {series_aplicaveis}"
            })
        
        print(f"   ✅ {len(habilidades)} habilidades de: {series_aplicaveis}")
    
    # Processar habilidades únicas por série
    print("\n📘 Processando habilidades únicas por série...")
    for grade_data in org.get("habilidades_unicas_por_serie", []):
        serie = grade_data.get("serie", "")
        habilidades = grade_data.get("habilidades", [])
        
        if serie not in GRADE_IDS:
            print(f"   ⚠️  Série '{serie}' não encontrada no mapeamento, pulando...")
            continue
        
        grade_id = GRADE_IDS[serie]
        
        for hab in habilidades:
            result["habilidades"].append({
                "code": hab["codigo"],
                "description": hab["descricao"],
                "subject_id": PORTUGUES_ID,
                "grade_id": grade_id,
                "comment": f"Única: {serie}"
            })
        
        print(f"   ✅ {len(habilidades)} habilidades de: {serie}")
    
    # Salvar resultado
    output_file = os.path.join(script_dir, 'habilidades_portugues_data.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Arquivo salvo: habilidades_portugues_data.json")
    print(f"📊 Total de habilidades: {len(result['habilidades'])}")
    print("\n🚀 Próximo passo: Execute 'python scripts/update_portuguese_skills_direct.py'")


if __name__ == "__main__":
    processar()
