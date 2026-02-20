"""
Corrige problemas de UTF-8 (interrogações) em todos os campos de texto
da tabela question: title, description, text, formatted_text, command,
subtitle, formatted_solution, difficulty_level e strings dentro de alternatives/topics.
"""

import os
import sys
import re
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, "app", ".env"))
except ImportError:
    pass

from app.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified
from app.models.question import Question

# Mapeamento: texto corrompido -> texto correto (ordem: mais específico primeiro)
# Padrões com ?? onde era um caractere acentuado (UTF-8 lido errado)
REPLACEMENTS = [
    # Corrigir conversões erradas (regex ??o -> ção trocou chão/vão por chção/vção)
    ("chção", "chão"),
    ("vção", "vão"),
    # Enunciados: palavras do exemplo "Mãe da rua" e similares
    ("M??e", "Mãe"),
    ("M?e", "Mãe"),
    ("p??tio", "pátio"),
    ("p?tio", "pátio"),
    ("voc??", "você"),
    ("voc?", "você"),
    ("cal??adas", "calçadas"),
    ("cal??ada", "calçada"),
    ("cal?adas", "calçadas"),
    ("cal?ada", "calçada"),
    ("um p?? ", "um pé "),
    ("um p? ", "um pé "),
    (" p?? ", " pé "),
    (" p? ", " pé "),
    ("p?? s??", "pé só"),
    ("p? s?", "pé só"),
    ("s??!", "só!"),
    ("s?!", "só!"),
    (" s?? ", " só "),
    (" s? ", " só "),
    # ch??o e v??o ANTES da regex ??o->ção (para não virar chção/vção)
    ("ch??o", "chão"),
    ("v??o", "vão"),
    ("ch?o", "chão"),
    ("v?o", "vão"),
    # ?? sozinho entre espaços = "é" (verbo): "onde ?? a rua" -> "onde é a rua"
    (" ?? ", " é "),
    (" ? ", " é "),
    (".?? ", ".é "),
    (".? ", ".é "),
    # Novos exemplos (enunciados matemática/geral)
    ("num??rica", "numérica"),
    ("num?rica", "numérica"),
    ("(??C)", "(°C)"),
    ("??C)", "°C)"),
    ("(??C", "(°C"),
    (" ??C ", " °C "),
    ("??C", "°C"),
    ("c??mara", "câmara"),
    ("c?mara", "câmara"),
    ("munic??pios", "municípios"),
    ("munic?pios", "municípios"),
    (" h?? ", " há "),
    (" h? ", " há "),
    ("h?? na", "há na"),
    ("regição", "região"),
    ("mil??simos", "milésimos"),
    ("mil?simos", "milésimos"),
    ("gin??stica", "ginástica"),
    ("gin?stica", "ginástica"),
    ("danção", "dança"),  # aula de dança (não "danção")
    ("tr??s", "três"),
    ("tr?s", "três"),
    ("inscri????o", "inscrição"),
    ("prefer??ncia", "preferência"),
    ("prefer?ncia", "preferência"),
    ("sim??trico", "simétrico"),
    ("sim?trico", "simétrico"),
    ("Al??m", "Além"),
    ("??rea", "área"),
    ("?rea", "área"),
    ("fra????o", "fração"),
    ("fra??o", "fração"),
    ("fra?o", "fração"),
    # Texto "O socorro" e similares (contos, literatura)
    ("profissção", "profissão"),
    ("profiss??o", "profissão"),
    ("profiss?o", "profissão"),
    (" ??? ", " — "),  # travessão: "sua profissão — coveiro — era"
    ("???O", "\"O"),
    ("???T", "\"T"),
    ("???M", "\"M"),
    ("???V", "\"V"),
    ("???P", "\"P"),
    ("!???", "!\""),
    (".???", ".\""),
    ("distra????o", "distração"),
    ("distra??o", "distração"),
    ("of??cio", "ofício"),
    ("of?cio", "ofício"),
    ("Ningu??m", "Ninguém"),
    ("Ningu?m", "Ninguém"),
    ("sil??ncio", "silêncio"),
    ("sil?ncio", "silêncio"),
    ("cemit??rio", "cemitério"),
    ("cemit?rio", "cemitério"),
    ("S?? ", "Só "),
    ("l?? ", "lá "),
    (" l?? ", " lá "),
    ("l?? em", "lá em"),
    ("l?? v", "lá v"),
    ("cabeção", "cabeça"),
    ("??bria", "sobria"),
    ("?bria", "sobria"),
    ("h??????", "há?"),
    ("h?????", "há?"),
    ("h????", "há?"),
    ("entção", "então"),
    ("ent??o", "então"),
    ("ent?o", "então"),
    ("terr??vel", "terrível"),
    ("terr?vel", "terrível"),
    ("b??bado", "bêbado"),
    ("b?bado", "bêbado"),
    ("razção", "razão"),
    ("raz??o", "razão"),
    ("raz?o", "razão"),
    ("Algu??m", "Alguém"),
    ("Algu?m", "Alguém"),
    (" a p?? ", " a pá "),   # pá (ferramenta)
    (" a p? ", " a pá "),
    ("p??s-se", "pôs-se"),
    ("p?s-se", "pôs-se"),
    ("P??R", "Pôr"),
    ("P?R", "Pôr"),
    ("p??r do sol", "pôr do sol"),
    ("p?r do sol", "pôr do sol"),
    # Dificuldade e níveis
    ("Abaixo do B??sico", "Abaixo do Básico"),
    ("Abaixo do B?sico", "Abaixo do Básico"),
    ("B??sico", "Básico"),
    ("B?sico", "Básico"),
    ("Avan??ado", "Avançado"),
    ("Avan?ado", "Avançado"),
    ("Adequado", "Adequado"),  # pode estar ok
    # Termos comuns em questões (?? = ç, ã, á, etc.)
    ("informa????o", "informação"),
    ("informa??o", "informação"),
    ("informa??es", "informações"),
    ("descri????o", "descrição"),
    ("descri??o", "descrição"),
    ("descri??es", "descrições"),
    ("interpreta????o", "interpretação"),
    ("interpreta??o", "interpretação"),
    ("situa????o", "situação"),
    ("situa??o", "situação"),
    ("situa??es", "situações"),
    ("avalia????o", "avaliação"),
    ("avalia??o", "avaliação"),
    ("quest??o", "questão"),
    ("quest?o", "questão"),
    ("quest??es", "questões"),
    ("quest?es", "questões"),
    ("op????o", "opção"),
    ("op??o", "opção"),
    ("op??es", "opções"),
    ("solu????o", "solução"),
    ("solu??o", "solução"),
    ("an??lise", "análise"),
    ("an?lise", "análise"),
    ("matem??tica", "matemática"),
    ("matem?tica", "matemática"),
    ("portugu??s", "português"),
    ("portugu?s", "português"),
    ("l??ngua", "língua"),
    ("l?ngua", "língua"),
    ("n??mero", "número"),
    ("n?mero", "número"),
    ("n??meros", "números"),
    ("m??dia", "média"),
    ("m?dia", "média"),
    ("necess??rio", "necessário"),
    ("necess?rio", "necessário"),
    ("conte??do", "conteúdo"),
    ("conte?do", "conteúdo"),
    ("t??tulo", "título"),
    ("t?tulo", "título"),
    ("texto", "texto"),
    ("enunciado", "enunciado"),
    ("alternativa", "alternativa"),
    ("resposta", "resposta"),
    ("correta", "correta"),
    ("incorreta", "incorreta"),
    ("explica????o", "explicação"),
    ("explica??o", "explicação"),
    ("rela????o", "relação"),
    ("rela??o", "relação"),
    ("rela??es", "relações"),
    ("comunica????o", "comunicação"),
    ("comunica??o", "comunicação"),
    ("organiza????o", "organização"),
    ("organiza??o", "organização"),
    ("apresenta????o", "apresentação"),
    ("apresenta??o", "apresentação"),
    ("observa????o", "observação"),
    ("observa??o", "observação"),
    ("poss??vel", "possível"),
    ("poss?vel", "possível"),
    ("pr??tica", "prática"),
    ("pr?tica", "prática"),
    ("caracter??stica", "característica"),
    ("caracter?stica", "característica"),
    ("caracter??sticas", "características"),
    ("estrat??gia", "estratégia"),
    ("estrat?gia", "estratégia"),
    ("estrat??gias", "estratégias"),
    ("an??lise", "análise"),
    ("m??ltiplas", "múltiplas"),
    ("m?ltiplas", "múltiplas"),
    ("m??ltiplos", "múltiplos"),
    ("c??digo", "código"),
    ("c?digo", "código"),
    ("significado", "significado"),
    ("palavras", "palavras"),
    ("express??es", "expressões"),
    ("express?es", "expressões"),
    ("express??o", "expressão"),
    ("express?o", "expressão"),
    ("pontua????o", "pontuação"),
    ("pontua??o", "pontuação"),
    ("varia????o", "variação"),
    ("varia??o", "variação"),
    ("varia????es", "variações"),
    ("ling??stica", "linguística"),
    ("ling?stica", "linguística"),
    ("ling??sticas", "linguísticas"),
    ("gram??tica", "gramática"),
    ("gram?tica", "gramática"),
    ("ortografia", "ortografia"),
    ("sem??ntico", "semântico"),
    ("sem?ntico", "semântico"),
    ("sem??ntica", "semântica"),
    ("contexto", "contexto"),
    ("coer??ncia", "coerência"),
    ("coer?ncia", "coerência"),
    ("coes??o", "coesão"),
    ("coes?o", "coesão"),
    ("par??grafo", "parágrafo"),
    ("par?grafo", "parágrafo"),
    ("n??cleo", "núcleo"),
    ("n?cleo", "núcleo"),
    ("c??lculo", "cálculo"),
    ("c?lculo", "cálculo"),
    ("c??lculos", "cálculos"),
    ("opera????o", "operação"),
    ("opera??o", "operação"),
    ("opera????es", "operações"),
    ("equa????o", "equação"),
    ("equa??o", "equação"),
    ("equa????es", "equações"),
    ("geometria", "geometria"),
    ("??ngulo", "ângulo"),
    ("?ngulo", "ângulo"),
    ("??ngulos", "ângulos"),
    ("rea????o", "reação"),
    ("rea??o", "reação"),
    ("rea????es", "reações"),
    ("causa", "causa"),
    ("consequ??ncia", "consequência"),
    ("consequ?ncia", "consequência"),
    ("consequ??ncias", "consequências"),
    ("multissemi??ticos", "multissemióticos"),
    ("multissemi?ticos", "multissemióticos"),
    ("suportes", "suportes"),
    ("diferentes", "diferentes"),
    ("elementos", "elementos"),
    ("constitutivos", "constitutivos"),
    ("narrativos", "narrativos"),
    ("g??neros", "gêneros"),
    ("g?neros", "gêneros"),
    ("textuais", "textuais"),
    ("diversos", "diversos"),
    ("persuas??o", "persuasão"),
    ("persuas?o", "persuasão"),
    ("verbais", "verbais"),
    ("multimodais", "multimodais"),
    ("localizar", "localizar"),
    ("expl??cita", "explícita"),
    ("expl?cita", "explícita"),
    ("expl??citas", "explícitas"),
    ("inferir", "inferir"),
    ("sentido", "sentido"),
    ("efeitos", "efeitos"),
    ("decorrentes", "decorrentes"),
    ("uso", "uso"),
    ("adv??rbios", "advérbios"),
    ("adv?rbios", "advérbios"),
    ("adjetivos", "adjetivos"),
    ("verbos", "verbos"),
    ("enuncia????o", "enunciação"),
    ("enuncia??o", "enunciação"),
    ("derivadas", "derivadas"),
    ("afixos", "afixos"),
    ("mecanismos", "mecanismos"),
    ("progress??o", "progressão"),
    ("progress?o", "progressão"),
    ("referencia????o", "referenciação"),
    ("referencia??o", "referenciação"),
    ("lexical", "lexical"),
    ("pronominal", "pronominal"),
    ("variedades", "variedades"),
    ("dom??nio", "domínio"),
    ("dom?nio", "domínio"),
    ("liter??rio", "literário"),
    ("liter?rio", "literário"),
    ("pertencentes", "pertencentes"),
    ("n??mero", "número"),
    ("n?mero", "número"),
    ("ordens", "ordens"),
    ("naturais", "naturais"),
    ("multiplica????o", "multiplicação"),
    ("multiplica??o", "multiplicação"),
    ("divis??o", "divisão"),
    ("divis?o", "divisão"),
    ("adi????o", "adição"),
    ("adi??o", "adição"),
    ("parcelas", "parcelas"),
    ("iguais", "iguais"),
    ("configura????o", "configuração"),
    ("configura??o", "configuração"),
    ("retangular", "retangular"),
    ("tabelas", "tabelas"),
    ("gr??ficos", "gráficos"),
    ("gr?ficos", "gráficos"),
    ("barras", "barras"),
    ("colunas", "colunas"),
    ("pict??ricos", "pictóricos"),
    ("pict?ricos", "pictóricos"),
    ("linhas", "linhas"),
    ("dados", "dados"),
    ("apresentados", "apresentados"),
    ("entrada", "entrada"),
    ("dupla", "dupla"),
    ("simples", "simples"),
    ("agrupadas", "agrupadas"),
    ("agrupados", "agrupados"),
    # Comuns em enunciados (frases)
    (" at?? ", " até "),
    (" at? ", " até "),
    ("tamb??m", "também"),
    ("tamb?m", "também"),
    ("por??m", "porém"),
    ("por?m", "porém"),
    ("pr??prio", "próprio"),
    ("pr?prio", "próprio"),
    ("pr??pria", "própria"),
    ("al??m", "além"),
    ("al?m", "além"),
    ("algum", "algum"),
    ("ningu??m", "ninguém"),
    ("ningu?m", "ninguém"),
    ("algu??m", "alguém"),
    ("algu?m", "alguém"),
    ("compreens??o", "compreensão"),
    ("compreens?o", "compreensão"),
    ("leitura", "leitura"),
    ("escolha", "escolha"),
    ("marque", "marque"),
    ("assinale", "assinale"),
    ("segundo", "segundo"),
    ("trecho", "trecho"),
    ("afirma", "afirma"),
    ("correto", "correto"),
    ("incorreto", "incorreto"),
    ("verdadeiro", "verdadeiro"),
    ("falso", "falso"),
]

# Ordenar por tamanho do texto errado (maior primeiro) para não sobrescrever partes
REPLACEMENTS.sort(key=lambda x: -len(x[0]))


def fix_string(s):
    """Aplica correções UTF-8 em uma string."""
    if s is None or not isinstance(s, str):
        return s
    # Caractere de substituição Unicode (quando encoding falha) vira ? para os padrões casarem
    out = s.replace("\ufffd", "?")
    # Entidades HTML do caractere de substituição (comum em enunciados com HTML)
    out = re.sub(r"&#65533;", "?", out, flags=re.IGNORECASE)
    out = re.sub(r"&#x[fF][fF][fF][dD];", "?", out)
    for wrong, right in REPLACEMENTS:
        if wrong in out:
            out = out.replace(wrong, right)
    # Segunda passagem: padrões comuns de sufixos (?? = um caractere acentuado)
    out = re.sub(r"n\?\?o\b", "não", out)
    out = re.sub(r"n\?o\b", "não", out)
    out = re.sub(r"(\w)\?\?o\b", r"\1ção", out)  # descri??o -> descrição
    out = re.sub(r"(\w)\?o\b", r"\1ção", out)
    out = re.sub(r"(\w)\?\?es\b", r"\1ções", out)
    out = re.sub(r"(\w)\?es\b", r"\1ções", out)
    out = re.sub(r"(\w)\?\?a\b", r"\1ção", out)  # opera??a -> operação
    out = re.sub(r"(\w)\?a\b", r"\1ção", out)
    out = re.sub(r"(\w)\?\?os\b", r"\1ços", out)
    out = re.sub(r"(\w)\?\?as\b", r"\1ças", out)
    out = re.sub(r"B\?\?sico", "Básico", out)
    out = re.sub(r"B\?sico", "Básico", out)
    out = re.sub(r"Avan\?\?ado", "Avançado", out)
    out = re.sub(r"Avan\?ado", "Avançado", out)
    # Interrogações no final da frase (1, 2 ou mais) = "é": "esse número ??" -> "esse número é"
    out = re.sub(r" (\?+)\s*([.]|$|\n)", r" é\2", out)
    out = re.sub(r" (\?+)\s*$", " é", out)
    return out


def fix_json_strings(obj):
    """Recursivamente corrige strings dentro de dict/list (ex: alternatives, topics)."""
    if obj is None:
        return obj
    if isinstance(obj, str):
        return fix_string(obj)
    if isinstance(obj, dict):
        return {k: fix_json_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fix_json_strings(v) for v in obj]
    return obj


def get_db_session():
    database_url = Config.SQLALCHEMY_DATABASE_URI
    if not database_url:
        raise SystemExit("DATABASE_URL não configurada.")
    kwargs = {}
    if "postgresql" in database_url:
        kwargs["client_encoding"] = "utf8"
    engine = create_engine(database_url, **kwargs)
    return sessionmaker(bind=engine)()


def main():
    session = get_db_session()
    text_columns = [
        "title", "description", "text", "formatted_text", "secondstatement",
        "command", "subtitle", "formatted_solution", "difficulty_level"
    ]
    json_columns = ["alternatives", "topics"]

    print("\n" + "=" * 60)
    print("CORREÇÃO UTF-8 EM TODOS OS CAMPOS DAS QUESTÕES")
    print("=" * 60)

    questions = session.query(Question).all()
    total = len(questions)
    updated_count = 0

    for i, q in enumerate(questions, 1):
        changed = False
        modified_cols = set()
        for col in text_columns:
            val = getattr(q, col, None)
            if val and isinstance(val, str):
                fixed = fix_string(val)
                if fixed != val:
                    setattr(q, col, fixed)
                    changed = True
                    modified_cols.add(col)
        for col in json_columns:
            val = getattr(q, col, None)
            if val is not None:
                fixed = fix_json_strings(val)
                if fixed != val:
                    setattr(q, col, fixed)
                    flag_modified(q, col)
                    changed = True
        if changed:
            updated_count += 1
            for col in modified_cols:
                flag_modified(q, col)
        if (i % 100 == 0) or (i == total):
            print(f"  Processadas: {i}/{total}")

    if updated_count > 0:
        session.commit()
        print(f"\n✓ {updated_count} questões atualizadas. Commit realizado.")
    else:
        print("\nNenhuma alteração necessária.")

    session.close()
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
