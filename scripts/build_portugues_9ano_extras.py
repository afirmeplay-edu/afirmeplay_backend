"""
Gera JSON com habilidades extras do 9º Ano de Português (códigos LP9).
Execute uma vez: python scripts/build_portugues_9ano_extras.py
"""
import json
import os

PORTUGUES_ID = "4d29b4f1-7bd7-42c0-84d5-111dc7025b90"
NONO_ANO_ID = "3c68a0b5-9613-469e-8376-6fb678c60363"

HABILIDADES = [
    {"codigo": "LP9L1.1", "descricao": "Identificar o uso de recursos persuasivos em textos verbais e não verbais."},
    {"codigo": "LP9L1.2", "descricao": "Identificar elementos constitutivos de textos pertencentes ao domínio jornalístico/midiático."},
    {"codigo": "LP9L1.3", "descricao": "Identificar formas de organização de textos normativos, legais e/ou reivindicatórios."},
    {"codigo": "LP9L1.4", "descricao": "Identificar teses/opiniões/posicionamento explícitos e argumentos em textos."},
    {"codigo": "LP9L1.5", "descricao": "Identificar elementos constitutivos de gêneros de divulgação cientifica."},
    {"codigo": "LP9L2.1", "descricao": "Analisar elementos constitutivos de textos pertencentes ao domínio literário."},
    {"codigo": "LP9L2.2", "descricao": "Analisar a intertextualidade entre textos literários ou entre estes e outros textos verbais ou não verbais."},
    {"codigo": "LP9L2.3", "descricao": "Inferir a presença de valores sociais, culturais e humanos em textos literários."},
    {"codigo": "LP9L2.4", "descricao": "Analisar efeitos de sentido produzido pelo uso de formas de apropriação textual (paráfrase, citação etc.)."},
    {"codigo": "LP9L2.5", "descricao": "Inferir informações implícitas em distintos textos."},
    {"codigo": "LP9L2.6", "descricao": "Distinguir fatos de opiniões em textos."},
    {"codigo": "LP9L2.7", "descricao": "Inferir, em textos multissemióticos, efeitos de humor, ironia e/ou crítica."},
    {"codigo": "LP9L2.8", "descricao": "Analisar marcas de parcialidade em textos jornalísticos."},
    {"codigo": "LP9L2.9", "descricao": "Analisar a relação temática entre diferentes gêneros jornalísticos."},
    {"codigo": "LP9L2.10", "descricao": "Analisar os efeitos de sentido decorrentes dos mecanismos de construção de textos jornalísticos/midiáticos."},
    {"codigo": "LP9L3.1", "descricao": "Avaliar diferentes graus de parcialidade em textos jornalísticos."},
    {"codigo": "LP9L3.2", "descricao": "Avaliar a fidedignidade de informações sobre um mesmo fato divulgado em diferentes veículos e mídias."},
    {"codigo": "LP9A1.1", "descricao": "Identificar os recursos de modalização em textos diversos."},
    {"codigo": "LP9A2.1", "descricao": "Analisar o uso de figuras de linguagem como estratégia argumentativa."},
    {"codigo": "LP9A2.2", "descricao": "Analisar os efeitos de sentido dos tempos, modos e/ou vozes verbais com base no gênero textual e na intenção comunicativa."},
    {"codigo": "LP9A2.3", "descricao": "Analisar os mecanismos que contribuem para a progressão textual."},
    {"codigo": "LP9A2.4", "descricao": "Analisar os processos de referenciação lexical e pronominal."},
    {"codigo": "LP9A2.5", "descricao": "Analisar as variedades linguísticas em textos."},
    {"codigo": "LP9A2.6", "descricao": "Analisar os efeitos de sentido produzidos pelo uso de modalizadores em textos diversos."},
    {"codigo": "LP9A3.1", "descricao": "Avaliar a adequação das variedades linguísticas em contextos de uso."},
    {"codigo": "LP9A3.2", "descricao": "Avaliar a eficácia das estratégias argumentativas em textos de diferentes gêneros."},
    {"codigo": "LP9A4.1", "descricao": "Pruduzir texto em língua portuguesa, de acordo com o gênero textual e o tema demandados."},
]


def run():
    out = {"habilidades": []}
    
    for h in HABILIDADES:
        out["habilidades"].append({
            "code": h["codigo"],
            "description": h["descricao"],
            "subject_id": PORTUGUES_ID,
            "grade_id": NONO_ANO_ID,
            "comment": "Única: 9º Ano",
        })
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "habilidades_portugues_9ano_extras.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Gerado: {path}")
    print(f"   Total: {len(out['habilidades'])} habilidades do 9º Ano")


if __name__ == "__main__":
    run()
