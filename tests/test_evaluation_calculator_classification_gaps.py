"""Garante faixas contíguas (sem buraco decimal) na classificação GERAL/Mat/Outras."""

from app.services.evaluation_calculator import EvaluationCalculator as EC


def test_anos_iniciais_matematica_224_9_is_basico_not_abaixo():
    """Caso Quebrangulo / Cristino: média ~224.9 não pode cair no fallback Abaixo."""
    assert (
        EC.determine_classification(224.9, "Anos Iniciais", "GERAL", has_matematica=True)
        == "Básico"
    )
    assert (
        EC.determine_classification(224.9, "Anos Iniciais", "Matemática")
        == "Básico"
    )


def test_anos_iniciais_portugues_199_63_is_basico_not_abaixo():
    """Relatório consolidado LP 5º: 199.63 não pode cair no gap 199→200."""
    assert (
        EC.determine_classification(199.63, "Anos Iniciais", "Português")
        == "Básico"
    )
    assert (
        EC.determine_classification(199.63, "Anos Iniciais", "GERAL", has_matematica=False)
        == "Básico"
    )


def test_anos_iniciais_outras_boundary_scan():
    cases = [
        (149.0, "Abaixo do Básico"),
        (149.99, "Abaixo do Básico"),
        (150.0, "Básico"),
        (199.0, "Básico"),
        (199.63, "Básico"),
        (199.99, "Básico"),
        (200.0, "Adequado"),
        (249.99, "Adequado"),
        (250.0, "Avançado"),
    ]
    for proficiency, expected in cases:
        for subject in ("Português", "Ciências", "História"):
            got = EC.determine_classification(proficiency, "Anos Iniciais", subject)
            assert got == expected, (
                f"{subject} p={proficiency}: esperado {expected!r}, obtido {got!r}"
            )


def test_anos_finais_outras_closes_gap_199_to_200():
    assert (
        EC.determine_classification(199.63, "Anos Finais", "Português")
        == "Abaixo do Básico"
    )
    assert (
        EC.determine_classification(200.0, "Anos Finais", "Português")
        == "Básico"
    )


def test_anos_iniciais_matematica_boundary_scan():
    cases = [
        (174.0, "Abaixo do Básico"),
        (174.99, "Abaixo do Básico"),
        (175.0, "Básico"),
        (224.0, "Básico"),
        (224.1, "Básico"),
        (224.99, "Básico"),
        (225.0, "Adequado"),
        (274.99, "Adequado"),
        (275.0, "Avançado"),
    ]
    for proficiency, expected in cases:
        got = EC.determine_classification(
            proficiency, "Anos Iniciais", "GERAL", has_matematica=True
        )
        assert got == expected, f"p={proficiency}: esperado {expected!r}, obtido {got!r}"


def test_legacy_geral_anos_iniciais_closes_gap_without_has_matematica():
    assert (
        EC.determine_classification(224.9, "Anos Iniciais", "GERAL", has_matematica=None)
        == "Básico"
    )
