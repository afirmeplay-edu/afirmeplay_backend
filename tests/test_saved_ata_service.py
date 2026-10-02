"""Testes de normalização de content.options em atas salvas."""
from app.services.saved_ata_service import (
    SavedAtaValidationError,
    _normalize_content,
    _validate_payload,
)


def test_normalize_content_keeps_first_apoio_as_string_and_extras_arrays():
    content = {
        "escola": "Escola X",
        "options": {
            "assinaturaApoioRegular": "Maria",
            "cpfApoioRegular": "111",
            "assinaturaApoioSuporte": "João",
            "cpfApoioSuporte": "222",
            "apoiosRegularExtras": [
                {"assinatura": "Ana", "cpf": "333"},
                {"assinatura": "Bia", "cpf": 444},
            ],
            "apoiosSuporteExtras": [],
            "outraChave": "preservar",
        },
    }
    out = _normalize_content(content)
    opts = out["options"]
    assert opts["assinaturaApoioRegular"] == "Maria"
    assert opts["cpfApoioRegular"] == "111"
    assert opts["assinaturaApoioSuporte"] == "João"
    assert opts["cpfApoioSuporte"] == "222"
    assert opts["apoiosRegularExtras"] == [
        {"assinatura": "Ana", "cpf": "333"},
        {"assinatura": "Bia", "cpf": "444"},
    ]
    assert opts["apoiosSuporteExtras"] == []
    assert opts["outraChave"] == "preservar"


def test_normalize_content_old_ata_without_extras_stays_valid():
    content = {
        "options": {
            "assinaturaApoioRegular": "Só um",
            "cpfApoioRegular": "999",
        }
    }
    out = _normalize_content(content)
    assert "apoiosRegularExtras" not in out["options"]
    assert "apoiosSuporteExtras" not in out["options"]
    assert out["options"]["assinaturaApoioRegular"] == "Só um"


def test_validate_payload_rejects_invalid_extras_type():
    payload = {
        "filters": {
            "municipio_id": "city-1",
            "escola_id": "school-1",
            "modo_lista": "cartao_resposta",
        },
        "content": {
            "options": {
                "apoiosRegularExtras": "nao-array",
            }
        },
    }
    try:
        _validate_payload(payload)
        assert False, "esperava SavedAtaValidationError"
    except SavedAtaValidationError as err:
        assert "apoiosRegularExtras" in err.message
