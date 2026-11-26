"""Unit tests for EN/PT syllable counting and language detection."""

from __future__ import annotations

import pytest

from writing_guard.language import detect_language
from writing_guard.syllables import (
    count_syllables,
    count_syllables_en,
    count_syllables_pt,
    has_cmudict,
)


def test_detect_language_en_and_pt() -> None:
    en_text = (
        "This paper presents a novel optimization framework for autonomous vehicles. "
        "The results show that the proposed method reduces latency across all benchmarks."
    )
    pt_text = (
        "Este trabalho apresenta uma nova metodologia de otimização para veículos autónomos. "
        "Os resultados mostram que o método proposto reduz a latência em todas as avaliações."
    )
    assert detect_language(en_text) == "en"
    assert detect_language(pt_text) == "pt"
    assert detect_language("") == "en"


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        # Silent u in qu/gu before e/i
        ("guerra", 2),
        ("quente", 2),
        ("queijo", 2),
        ("guitarra", 3),
        ("conseguir", 3),
        ("frequente", 3),
        ("linguística", 4),
        # Diphthongs and triphthongs
        ("caixa", 2),
        ("peixe", 2),
        ("noite", 2),
        ("muito", 2),
        ("causa", 2),
        ("neutro", 2),
        ("pouco", 2),
        ("pão", 1),
        ("mãe", 1),
        ("limões", 2),
        ("história", 3),
        ("série", 2),
        ("estúdio", 3),
        ("água", 2),
        ("ténue", 2),
        ("contínuo", 3),
        ("quais", 1),
        ("uruguai", 3),
        ("saguão", 2),
        # Accented hiatuses & other hiatuses
        ("saúde", 3),
        ("país", 2),
        ("raízes", 3),
        ("conteúdo", 4),
        ("aéreo", 4),
        ("engenharia", 5),
        ("reunir", 3),
        ("reunião", 4),
        ("ainda", 3),
        ("sair", 2),
        # Hyphenated enclitics & compounds
        ("realizou-se", 5),
        ("observa-se", 4),
    ],
)
def test_pt_syllables(word: str, expected: int) -> None:
    assert count_syllables_pt(word) == expected
    assert count_syllables(word, "pt") == expected


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("area", 3),
        ("queue", 1),
        ("science", 2),
        ("temperature", 3),
        ("algorithm", 4),
        ("finite", 2),
        ("surface", 2),
        ("different", 2),
        ("average", 2),
        ("material", 4),
        ("variable", 4),
        ("analysis", 4),
        ("methodology", 5),
        ("equation", 3),
        ("every", 2),
        ("table", 2),
        ("sampled", 2),
        ("tables", 2),
        ("walked", 1),
        ("created", 3),
        ("makes", 1),
        ("boxes", 2),
        ("pages", 2),
        ("quiet", 2),
        ("linear", 3),
        ("continuous", 4),
        ("evaluation", 5),
        ("state-of-the-art", 4),
    ],
)
def test_en_syllables_table_and_rules(word: str, expected: int) -> None:
    assert count_syllables_en(word) == expected
    assert count_syllables(word, "en") == expected


def test_en_fallback_without_cmudict(monkeypatch: pytest.MonkeyPatch) -> None:
    import writing_guard.syllables as syl

    monkeypatch.setattr(syl, "_CMU_LOAD_ATTEMPTED", True)
    monkeypatch.setattr(syl, "_CMU_DICT", None)
    assert has_cmudict() is False
    assert count_syllables_en("algorithm") == 4
    assert count_syllables_en("queue") == 1
    assert count_syllables_en("cat") == 1
    assert count_syllables_en("12345") == 0


def test_alphabetic_words_always_at_least_one_syllable() -> None:
    for w in ("a", "I", "x", "strengths", "rhythms", "b"):
        assert count_syllables(w, "en") >= 1
    for w in ("a", "é", "o", "pão", "x"):
        assert count_syllables(w, "pt") >= 1


def test_invalid_lang_raises() -> None:
    with pytest.raises(ValueError):
        count_syllables("hello", "fr")
