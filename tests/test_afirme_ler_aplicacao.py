# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.afirme_ler.services.fluency_aplicacao_service import (
    build_texto_payload,
    merge_list_words,
)


def test_merge_list_words_fills_unread_from_canonical_list():
    words = merge_list_words(
        ["NEVE", "LATA", "NATUREZA", "MANGA"],
        [
            {"index": 0, "word": "NEVE", "status": "acertou", "source": "manual"},
            {"index": 1, "word": "LATA", "status": "inventou", "source": "manual"},
        ],
        last_word_position=2,
    )
    assert [item["status"] for item in words] == [
        "acertou",
        "inventou",
        "nao_leu",
        "nao_leu",
    ]
    assert words[2]["word"] == "NATUREZA"
    assert words[0]["source"] == "manual"
    assert "source" not in words[2]


def test_texto_sem_markings_devolve_conteudo_completo():
    reading_text = SimpleNamespace(
        id="text-1",
        title="O siri Anastácio",
        content="LINHA UM PALAVRA.\nLINHA DOIS RESTO DO TEXTO.",
    )
    payload = build_texto_payload(
        reading_text=reading_text,
        part={
            "wordsRead": 3,
            "lastWordPosition": 3,
            "totalWords": 7,
            "unreadAfterEnd": 4,
            "errorsCount": 0,
            "lines": [
                {"lineIndex": 0, "text": "LINHA UM PALAVRA.", "wrongWordsCount": 0},
                {
                    "lineIndex": 1,
                    "text": "LINHA DOIS RESTO DO TEXTO.",
                    "wrongWordsCount": 0,
                },
            ],
        },
        audio={"hasAudio": False},
    )
    assert payload["hasWordMarkings"] is False
    assert payload["markings"] is None
    assert payload["words"] is None
    assert payload["content"] == reading_text.content
    assert len(payload["lines"]) == 2
    assert payload["lastWordPosition"] == 3
    assert payload["lastLineIndex"] == 0


def test_texto_com_markings_devolve_palavras():
    reading_text = SimpleNamespace(
        id="text-1",
        title="O siri",
        content="O PEQUENINO SIRI NASCEU.",
    )
    payload = build_texto_payload(
        reading_text=reading_text,
        part={
            "wordsRead": 3,
            "lastWordPosition": 3,
            "totalWords": 4,
            "markings": [
                {"index": 0, "word": "O", "status": "acertou", "source": "manual"},
                {"index": 1, "word": "PEQUENINO", "status": "acertou"},
                {"index": 2, "word": "SIRI", "status": "errou", "source": "manual"},
            ],
            "lines": [
                {
                    "lineIndex": 0,
                    "text": "O PEQUENINO SIRI NASCEU.",
                    "wrongWordsCount": 1,
                }
            ],
        },
        audio={"hasAudio": True, "audioUrl": "/audio?part=q3"},
    )
    assert payload["hasWordMarkings"] is True
    assert payload["words"][2]["status"] == "errou"
    assert payload["words"][3]["word"] == "NASCEU."
    assert payload["words"][3]["status"] == "nao_leu"
    assert payload["audioUrl"] == "/audio?part=q3"
    assert payload["content"] == reading_text.content
