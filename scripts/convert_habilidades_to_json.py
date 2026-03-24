"""
Script auxiliar para converter os dados das habilidades do formato original
para o formato simplificado que o script de atualização espera.

IMPORTANTE: Cole os dados do usuário na variável DADOS_ORIGINAIS abaixo.
"""

import json

# IDs das séries
GRADE_IDS = {
    "1º Ano": "391ed6e8-fc45-46f8-8e4c-065005d2329f",
    "2º Ano": "74821122-e632-4301-b6f5-42b92b802a55",
    "3º Ano": "ea1ed64b-c9f5-4156-93b2-497ecf9e0d84",
    "4º Ano": "b8cdea4d-22fe-4647-a9f3-c575eb82c514",
    "5º Ano": "f5688bb2-9624-487f-ab1f-40b191c96b76"
}

PORTUGUES_ID = "4d29b4f1-7bd7-42c0-84d5-111dc7025b90"

# COLE AQUI OS DADOS QUE O USUÁRIO FORNECEU
# (o JSON completo que ele enviou)
DADOS_ORIGINAIS = {
  "organizacao_curricular": {
    "habilidades_compartilhadas": [
      {
        "series_aplicaveis": "1º, 2º, 3º, 4º e 5º Ano",
        "habilidades": [
          {"codigo": "CEEF01LP01", "descricao": "Identificar as múltiplas linguagens que fazem parte do cotidiano da criança."},
          {"codigo": "EF15LP01", "descricao": "Identificar a função social de textos que circulam em campos da vida social dos quais participa cotidianamente (a casa, a rua, a comunidade, a escola) e nas mídias impressa, de massa e digital, reconhecendo para que foram produzidos, onde circulam, quem os produziu e a quem se destinam."}
        ]
      }
    ],
    "habilidades_unicas_por_serie": [
      {
        "serie": "1º Ano",
        "habilidades": [
          {"codigo": "EF01LP01", "descricao": "Reconhecer que textos são lidos e escritos da esquerda para a direita e de cima para baixo da página."}
        ]
      }
    ]
  }
}


def convert():
    """Converte os dados originais para o formato simplificado."""
    
    result = {"habilidades": []}
    org = DADOS_ORIGINAIS.get("organizacao_curricular", {})
    
    # Processar habilidades compartilhadas
    print("📚 Processando habilidades compartilhadas...")
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
    output_file = "habilidades_portugues_data.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Arquivo salvo: {output_file}")
    print(f"📊 Total de habilidades: {len(result['habilidades'])}")


if __name__ == "__main__":
    convert()
