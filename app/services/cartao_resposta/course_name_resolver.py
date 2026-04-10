import re


_GRADE_NUMBER_PATTERN = re.compile(r"\b([1-9]|1[0-2])(?:\s*[oº°])?\b")


def infer_course_name_from_grade(grade_name: str) -> str:
    """
    Inferir nome do curso a partir de diferentes formatos de série.

    Exemplos aceitos:
    - "5º ano", "5° ANO", "5 ano", "5o ano"
    - "9º ano", "9 ano"
    - "1º médio", "2 medio"
    """
    grade_lower = (grade_name or "").strip().lower()
    if not grade_lower:
        return "Anos Iniciais"

    if "infantil" in grade_lower or "pré" in grade_lower or "pre" in grade_lower:
        return "Educação Infantil"

    if "especial" in grade_lower:
        return "Educação Especial"

    if "eja" in grade_lower:
        return "EJA"

    if "médio" in grade_lower or "medio" in grade_lower:
        return "Ensino Médio"

    if "anos iniciais" in grade_lower or "fundamental i" in grade_lower:
        return "Anos Iniciais"

    if "anos finais" in grade_lower or "fundamental ii" in grade_lower:
        return "Anos Finais"

    match = _GRADE_NUMBER_PATTERN.search(grade_lower)
    if match:
        grade_number = int(match.group(1))
        if 1 <= grade_number <= 5:
            return "Anos Iniciais"
        if 6 <= grade_number <= 9:
            return "Anos Finais"
        if 10 <= grade_number <= 12:
            return "Ensino Médio"

    return "Anos Iniciais"
