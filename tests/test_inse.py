# -*- coding: utf-8 -*-
# Carrega constantes INSE sem importar app (app/__init__.py exige Flask).
# Exec: python -m unittest tests.test_inse
import importlib.util
import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CONSTANTS = _ROOT / "app" / "socioeconomic_forms" / "constants"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_norm = _load("inse_normalizer", _CONSTANTS / "inse_normalizer.py")
_score = _load("inse_scoring", _CONSTANTS / "inse_scoring.py")

normalizar_respostas = _norm.normalizar_respostas
normalizar_escolaridade = _norm.normalizar_escolaridade
BENS_PONTOS_CANONICO = _score.BENS_PONTOS_CANONICO
INSE_PONTUACAO_MAXIMA_TEORICA = _score.INSE_PONTUACAO_MAXIMA_TEORICA
calcular_pontos_inse_canonico = _score.calcular_pontos_inse_canonico
pontuacao_para_nivel_inse = _score.pontuacao_para_nivel_inse
INSE_FAIXAS = _score.INSE_FAIXAS


class TestInse(unittest.TestCase):
    def test_geladeira_tabela_pdf_innovplay(self):
        # PDF: Nenhum=0, 1=3, 2=4, 3 ou mais=5 (canônico 1/2/3+)
        self.assertEqual(BENS_PONTOS_CANONICO["geladeira"]["1"], 3)
        self.assertEqual(BENS_PONTOS_CANONICO["geladeira"]["2"], 4)
        self.assertEqual(BENS_PONTOS_CANONICO["geladeira"]["3+"], 5)

    def test_pontuacao_maxima_teorica(self):
        self.assertEqual(INSE_PONTUACAO_MAXIMA_TEORICA, 94)

    def test_formsdata_mae_pai_bens(self):
        # formsData: q8 mãe, q9 pai, bens em q12*, serviços em q13*
        r = {
            "q8": "Não completou o 5º ano",
            "q9": "Ensino Médio completo",
            "q12a": "2",
            "q12b": "Nenhum",
            "q12c": "1",
            "q12d": "1",
            "q12e": "1",
            "q12f": "Nenhum",
            "q12g": "1",
            "q13a": "Não",
            "q13b": "Sim",
            "q13c": "Não",
            "q13d": "Sim",
            "q13e": "Sim",
            "q13f": "Não",
            "q13g": "Sim",
            "q13h": "Não",
            "q13i": "Não",
        }
        n = normalizar_respostas(r)
        self.assertEqual(n["mae_escolaridade"], "fundamental_incompleto")
        self.assertEqual(n["pai_escolaridade"], "medio_completo")
        # Geladeira vem de q12a=2 (4 pts no PDF), não de q13a=Sim/Não do serviço
        self.assertEqual(n["bens"]["geladeira"], "2")
        p, _ = calcular_pontos_inse_canonico(n)
        self.assertGreater(p, 0)

    def test_geladeira_string_3_mapeia_para_3_ou_mais(self):
        # Dígito "3" sozinho: `normalizar_quantidade_bens` mapeia para "3+" (regra "3" in t).
        n = normalizar_respostas({"q12a": "3"})
        self.assertEqual(n["bens"]["geladeira"], "3+")
        self.assertEqual(BENS_PONTOS_CANONICO["geladeira"]["3+"], 5)

    def test_template_api_mae_pai_bens(self):
        # aluno_jovem_questions: q9 mãe, q10 pai, bens q13*, serviços q14*
        r = {
            "q9": "Ensino Superior completo (faculdade ou graduação)",
            "q10": "Ensino Médio completo",
            "q13a": "3 ou mais",
            "q13b": "1",
            "q13c": "2",
            "q13d": "3 ou mais",
            "q13e": "2",
            "q13f": "1",
            "q13g": "2",
            "q14a": "Sim",
            "q14b": "Sim",
            "q14c": "Sim",
            "q14d": "Sim",
            "q14e": "Sim",
            "q14f": "Sim",
            "q14g": "Sim",
            "q14h": "Sim",
            "q14i": "Sim",
        }
        n = normalizar_respostas(r)
        self.assertEqual(n["mae_escolaridade"], "superior_completo")
        self.assertEqual(n["pai_escolaridade"], "medio_completo")

    def test_inep_two_questions_only(self):
        r = {
            "q8": "Ensino Fundamental completo",
            "q9": "Não sei",
        }
        n = normalizar_respostas(r)
        self.assertEqual(n["mae_escolaridade"], "fundamental_completo")
        self.assertEqual(n["pai_escolaridade"], "nao_sei")

    def test_nao_inep_se_existe_subpergunta_q10a(self):
        r = {
            "q8": "Ensino Fundamental completo",
            "q9": "Não sei",
            "q10a": "Sempre",
        }
        n = normalizar_respostas(r)
        self.assertEqual(n["mae_escolaridade"], "fundamental_completo")
        self.assertEqual(n["pai_escolaridade"], "nao_sei")

    def test_alias_formsdata_ate_5_ano(self):
        t = "Ensino Fundamental até o 5º ano"
        self.assertEqual(normalizar_escolaridade(t), "fundamental_ate_4")

    def test_pontuacao_para_nivel(self):
        self.assertEqual(pontuacao_para_nivel_inse(9), (None, "Não calculado"))
        self.assertEqual(pontuacao_para_nivel_inse(10)[0], 1)
        self.assertEqual(pontuacao_para_nivel_inse(30)[0], 1)
        self.assertEqual(pontuacao_para_nivel_inse(31)[0], 2)
        self.assertEqual(pontuacao_para_nivel_inse(110)[0], 5)
        self.assertEqual(pontuacao_para_nivel_inse(111)[0], 6)
        self.assertEqual(len(INSE_FAIXAS), 6)


if __name__ == "__main__":
    unittest.main()
