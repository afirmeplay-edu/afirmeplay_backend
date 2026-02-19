"""
Mescla a estrutura organizacao_habilidades_matematica (novo formato) com o arquivo
habilidades_matematica_data.json atual. Mantém D1-D37 (6º-9º); gera entradas para
1º-5º a partir da organização (compartilhadas com grade_id null, 5º único com grade 5º).
D1-D28 do grupo 1º-5º são gravados como EF15_D1 a EF15_D28 para não colidir com 6º-9º.

Uso: python scripts/merge_math_from_organizacao.py
     (lê scripts/organizacao_matematica_novo.json e scripts/habilidades_matematica_data.json)
"""

import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MATEMATICA_ID = "44f3421e-ca84-4fe5-a449-a3d9bfa3db3d"
GRADE_5_ANO = "f5688bb2-9624-487f-ab1f-40b191c96b76"


def load_organizacao(path=None):
    path = path or os.path.join(SCRIPT_DIR, "organizacao_matematica_novo.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Arquivo de organização não encontrado: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("organizacao_habilidades_matematica", data)


def build_new_entries(organizacao):
    """Gera lista de entradas no formato do JSON de habilidades (code, description, subject_id, grade_id)."""
    entries = []
    shared = organizacao.get("habilidades_compartilhadas", [])
    unicas = organizacao.get("habilidades_unicas_por_serie", [])

    for group in shared:
        grade_id = None  # compartilhadas
        for h in group.get("habilidades", []):
            code = h.get("codigo", "").strip()
            desc = h.get("descricao", "").strip()
            if not code or not desc:
                continue
            # No primeiro grupo (1º-5º), D1-D28 viram EF15_D1 a EF15_D28
            if re.match(r"^D(\d+)$", code):
                num = int(re.match(r"^D(\d+)$", code).group(1))
                if 1 <= num <= 28:
                    code = f"EF15_D{num}"
            entries.append({
                "code": code,
                "description": desc,
                "subject_id": MATEMATICA_ID,
                "grade_id": grade_id,
            })

    for block in unicas:
        serie = block.get("serie", "")
        grade_id = GRADE_5_ANO if "5º" in serie else None
        for h in block.get("habilidades", []):
            code = h.get("codigo", "").strip()
            desc = h.get("descricao", "").strip()
            if not code or not desc:
                continue
            entries.append({
                "code": code,
                "description": desc,
                "subject_id": MATEMATICA_ID,
                "grade_id": grade_id,
            })

    return entries


def main():
    current_path = os.path.join(SCRIPT_DIR, "habilidades_matematica_data.json")
    with open(current_path, "r", encoding="utf-8") as f:
        current = json.load(f)

    organizacao_path = os.path.join(SCRIPT_DIR, "organizacao_matematica_novo.json")
    organizacao = load_organizacao(organizacao_path)
    new_entries = build_new_entries(organizacao)
    new_codes = {e["code"] for e in new_entries}

    # Manter apenas D1-D37 (6º-9º) do atual; o resto de matemática é substituído pelas novas entradas
    def keep_skill(s):
        if s.get("subject_id") != MATEMATICA_ID:
            return True
        code = s.get("code", "")
        m = re.match(r"^D(\d+)$", code)
        if m and 1 <= int(m.group(1)) <= 37:
            return True  # manter D1-D37
        return code not in new_codes

    kept = [s for s in current.get("habilidades", []) if keep_skill(s)]
    # Remover 'comment' das novas entradas para o formato esperado pelo update script
    for e in new_entries:
        if "comment" in e:
            del e["comment"]
    out_hab = kept + new_entries

    current["habilidades"] = out_hab
    with open(current_path, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    print(f"Merge concluído: {len(kept)} habilidades mantidas (D1-D37 + outras), {len(new_entries)} da organização.")
    print(f"Total no arquivo: {len(out_hab)}")


if __name__ == "__main__":
    main()
