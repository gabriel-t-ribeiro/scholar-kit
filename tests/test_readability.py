"""Unit tests for Flesch readability formulas, bands, and sentence splitting."""

from __future__ import annotations

import pytest

from writing_guard.models import LineRecord, ParsedDocument, SectionChunk
from writing_guard.readability import (
    analyze_readability,
    classify_reading_ease,
    split_sentences,
)


def test_abbreviation_and_decimal_sentence_splitter() -> None:
    text = (
        "See Fig. 2 and Eq. (3), e.g., for x = 3.14, as reported by Smith et al. (2024). "
        "In Sec. 4, Prof. Silva and Dr. Costa tested n.º 5, p. ex. 2,71 cm, vs. baseline, etc. "
        "Next, we evaluate the final controller!"
    )
    sents = split_sentences(text)
    assert len(sents) == 3
    assert sents[0].startswith("See Fig. 2")
    assert sents[1].startswith("In Sec. 4")
    assert sents[2] == "Next, we evaluate the final controller!"

    mid_etc = split_sentences("We tested steel, aluminum, etc., and copper.")
    assert len(mid_etc) == 1


def test_slide_19_reading_ease_bands() -> None:
    assert classify_reading_ease(95.0)[0] == "5th grade"
    assert classify_reading_ease(85.0)[0] == "6th grade"
    assert classify_reading_ease(75.0)[0] == "7th grade"
    assert classify_reading_ease(65.0)[0] == "8th & 9th grade"
    assert classify_reading_ease(55.0)[0] == "10th to 12th grade"
    assert classify_reading_ease(40.0)[0] == "College"
    assert classify_reading_ease(20.0)[0] == "College graduate"
    assert classify_reading_ease(5.0)[0] == "Professional"


def test_exact_en_slide_18_formulas() -> None:
    # 10 one-syllable words across 2 sentences => ASL = 5.0, ASW = 1.0
    text = "Cat sat on mat now. Dog ran to big tree."
    doc = ParsedDocument(
        source_path="en.txt",
        files=["en.txt"],
        loc_label="line",
        lines=[LineRecord("en.txt", 1, "line", "Intro", text, text)],
        sections=[SectionChunk("Intro", "en.txt", 1, text)],
        full_clean_text=text,
    )
    report = analyze_readability([doc], lang="en")
    expected_fre = round(206.835 - 1.015 * 5.0 - 84.6 * 1.0, 2)
    expected_fkgl = round(0.39 * 5.0 + 11.8 * 1.0 - 15.59, 2)

    assert report.lang == "en"
    assert report.overall.words == 10
    assert report.overall.sentences == 2
    assert report.overall.syllables == 10
    assert report.overall.avg_words_per_sentence == 5.0
    assert report.overall.avg_syllables_per_word == 1.0
    assert report.overall.flesch_reading_ease == pytest.approx(expected_fre, abs=1e-2)
    assert report.overall.flesch_kincaid_grade == pytest.approx(expected_fkgl, abs=1e-2)
    assert report.overall.band_label == "5th grade"


def test_exact_pt_slide_18_formulas() -> None:
    # 7 one-syllable PT words across 2 sentences => ASL = 3.5, ASW = 1.0
    text = "O sol vem. O pão é bom."
    doc = ParsedDocument(
        source_path="pt.txt",
        files=["pt.txt"],
        loc_label="line",
        lines=[LineRecord("pt.txt", 1, "line", "Resumo", text, text)],
        sections=[SectionChunk("Resumo", "pt.txt", 1, text)],
        full_clean_text=text,
    )
    report = analyze_readability([doc], lang="pt")
    expected_fre = round(226.0 - 1.04 * 3.5 - 72.0 * 1.0, 2)
    expected_fkgl = round(0.36 * 3.5 + 10.4 * 1.0 - 18.0, 2)

    assert report.lang == "pt"
    assert report.syllable_backend == "phonetic_pt"
    assert report.overall.words == 7
    assert report.overall.sentences == 2
    assert report.overall.syllables == 7
    assert report.overall.flesch_reading_ease == pytest.approx(expected_fre, abs=1e-2)
    assert report.overall.flesch_kincaid_grade == pytest.approx(expected_fkgl, abs=1e-2)


def test_sections_and_hardest_sentences_ranking() -> None:
    easy_sec = "We run fast tests. They give good scores."
    hard_sec = (
        "Consequently, multidimensional thermo-mechanical finite-element characterization "
        "demonstrates substantial microstructural heterogeneity across anisotropic composite "
        "interfaces under cyclic loading conditions. "
        "Short line here."
    )
    lines = [
        LineRecord("paper.md", 2, "line", "Intro", easy_sec, easy_sec),
        LineRecord("paper.md", 6, "line", "Analysis", hard_sec, hard_sec),
    ]
    doc = ParsedDocument(
        source_path="paper.md",
        files=["paper.md"],
        loc_label="line",
        lines=lines,
        sections=[
            SectionChunk("Intro", "paper.md", 2, easy_sec),
            SectionChunk("Analysis", "paper.md", 6, hard_sec),
        ],
        full_clean_text=f"{easy_sec}\n\n{hard_sec}",
    )
    report = analyze_readability([doc], lang="en", top_sentences=3)
    assert len(report.sections) == 2
    assert report.sections[0].title == "Intro"
    assert report.sections[1].title == "Analysis"
    assert report.sections[0].stats.flesch_reading_ease > report.sections[1].stats.flesch_reading_ease

    assert len(report.hardest_sentences) == 1
    hotspot = report.hardest_sentences[0]
    assert hotspot.section == "Analysis"
    assert hotspot.loc == 6
    assert hotspot.words >= 15
    assert hotspot.reading_ease < 20.0


def test_empty_document_returns_zero_stats() -> None:
    doc = ParsedDocument("empty.txt", ["empty.txt"], "line", [], [], "")
    report = analyze_readability([doc], lang="en")
    assert report.overall.words == 0
    assert report.overall.sentences == 0
    assert report.overall.band_label == "N/A"
    assert report.hardest_sentences == []
