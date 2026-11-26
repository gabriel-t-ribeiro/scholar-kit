"""Tests for ADPE writing style guard."""

from __future__ import annotations

from writing_guard.models import LineRecord, ParsedDocument, SectionChunk
from writing_guard.style_adpe import check_adpe_style


def _make_doc(
    lines: list[tuple[int, str, str, str]],
    *,
    file: str = "sample.tex",
    loc_label: str = "Line",
) -> ParsedDocument:
    """Build a ParsedDocument from (loc, section, raw_text, clean_text) tuples."""
    records = [
        LineRecord(
            file=file,
            loc=loc,
            loc_label=loc_label,
            section=sec,
            raw_text=raw,
            clean_text=clean,
        )
        for loc, sec, raw, clean in lines
    ]
    sections = [SectionChunk(title="Body", file=file, start_loc=1, text="\n".join(c for _, _, _, c in lines))]
    return ParsedDocument(
        source_path=file,
        files=[file],
        loc_label=loc_label,
        lines=records,
        sections=sections,
        full_clean_text="\n".join(c for _, _, _, c in lines),
    )


def test_long_sentence_medium_and_high_across_lines():
    # 38 words across two wrapped lines -> MEDIUM
    s_med_1 = "The experimental setup described in this section measures the transient pressure drop across"
    s_med_2 = "the porous medium under steady laminar flow conditions while recording high resolution thermal images from the upper surface of the heated stainless steel plate during testing."
    # 55 words -> HIGH
    s_high = " ".join(["word"] * 54) + "."
    doc = _make_doc([
        (1, "Methods", s_med_1, s_med_1),
        (2, "Methods", s_med_2, s_med_2),
        (3, "Methods", "", ""),
        (4, "Methods", s_high, s_high),
    ])
    findings = check_adpe_style([doc], lang="en")
    long_findings = [f for f in findings if f.rule_id == "LONG_SENTENCE"]
    assert len(long_findings) == 2
    assert long_findings[0].severity == "MEDIUM"
    assert long_findings[0].loc == 1
    assert long_findings[1].severity == "HIGH"
    assert long_findings[1].loc == 4


def test_sentence_splitter_ignores_abbreviations():
    # Should stay one short sentence (< 35 words) despite e.g., Fig., and et al.
    text = "See Fig. 2 and Smith et al. for details, e.g. thermal conductivity."
    doc = _make_doc([(1, "Methods", text, text)])
    findings = check_adpe_style([doc], lang="en")
    assert not any(f.rule_id == "LONG_SENTENCE" for f in findings)


def test_italic_latin_abbrev_latex_and_markdown():
    doc = _make_doc([
        (1, "Intro", r"We tested sensors, \textit{e.g.} thermocouples.", "We tested sensors, e.g. thermocouples."),
        (2, "Intro", r"Other works \emph{et al.} agree.", "Other works et al. agree."),
        (3, "Intro", "Values *i.e.* pressure and _etc._ apply.", "Values i.e. pressure and etc. apply."),
    ])
    findings = check_adpe_style([doc], lang="en")
    italics = [f for f in findings if f.rule_id == "ITALIC_LATIN_ABBREV"]
    assert len(italics) == 4
    assert [f.loc for f in italics] == [1, 2, 3, 3]


def test_abbrev_double_period_ignores_ellipsis():
    doc = _make_doc([
        (1, "Body", "Sensors, valves, etc..", "Sensors, valves, etc.."),
        (2, "Body", "Values were missing...", "Values were missing..."),
        (3, "Body", "For example, i.e.. this case.", "For example, i.e.. this case."),
    ])
    findings = check_adpe_style([doc], lang="en")
    dbl = [f for f in findings if f.rule_id == "ABBREV_DOUBLE_PERIOD"]
    assert len(dbl) == 2
    assert [f.loc for f in dbl] == [1, 3]


def test_pt_deste_overuse():
    doc = _make_doc([
        (1, "Resultados", "A velocidade deste aumentou bastante.", "A velocidade deste aumentou bastante."),
        (2, "Resultados", "Analisou-se o resultado desta.", "Analisou-se o resultado desta."),
        (3, "Resultados", "O objetivo deste trabalho é claro.", "O objetivo deste trabalho é claro."),
    ])
    findings = check_adpe_style([doc], lang="pt")
    deste = [f for f in findings if f.rule_id == "PT_DESTE_OVERUSE"]
    assert len(deste) == 2
    assert [f.loc for f in deste] == [1, 2]


def test_pt_bare_small_numeral():
    doc = _make_doc([
        (1, "Métodos", "Foram testados 3 modelos na 2ª fase.", "Foram testados 3 modelos na 2ª fase."),
        (2, "Métodos", "A espessura foi de 5 mm a 20 °C e 4%.", "A espessura foi de 5 mm a 20 °C e 4%."),
        (3, "Métodos", "Como ilustrado na Fig. 2 e Tabela 3.", "Como ilustrado na Fig. 2 e Tabela 3."),
        (4, "Métodos", "Usou-se um modelo 3D com 12 amostras.", "Usou-se um modelo 3D com 12 amostras."),
    ])
    findings = check_adpe_style([doc], lang="pt")
    nums = [f for f in findings if f.rule_id == "PT_BARE_SMALL_NUMERAL"]
    assert len(nums) == 2
    assert all(f.loc == 1 for f in nums)


def test_en_pt_translation_calque_and_weak_conj():
    doc = _make_doc([
        (1, "Methods", "It was developed a new sensor.", "It was developed a new sensor."),
        (2, "Methods", "This allows to reduce noise.", "This allows to reduce noise."),
        (3, "Methods", "The setup consists in two pumps and is different than before.", "The setup consists in two pumps and is different than before."),
        (4, "Methods", "We make an analysis. And the error dropped. But it stayed.", "We make an analysis. And the error dropped. But it stayed."),
        (5, "Methods", "Each node is allowed to transmit.", "Each node is allowed to transmit."),
    ])
    findings = check_adpe_style([doc], lang="en")
    calques = [f for f in findings if f.rule_id == "EN_PT_TRANSLATION_CALQUE"]
    weak = [f for f in findings if f.rule_id == "EN_WEAK_START_CONJ"]
    assert len(calques) == 5
    assert len(weak) == 2


def test_first_person_check_strict_impersonal():
    doc_en = _make_doc([
        (1, "Introduction", "In this work we present a method.", "In this work we present a method."),
        (2, "Methodology", "First, I calibrated our camera.", "First, I calibrated our camera."),
        (3, "Methodology", "Phase I tests were nominal.", "Phase I tests were nominal."),
        (4, "Conclusions", "We conclude that accuracy improved.", "We conclude that accuracy improved."),
    ])
    assert not any(f.rule_id == "FIRST_PERSON_CHECK" for f in check_adpe_style([doc_en], lang="en", strict_impersonal=False))
    fp_en = [f for f in check_adpe_style([doc_en], lang="en", strict_impersonal=True) if f.rule_id == "FIRST_PERSON_CHECK"]
    assert len(fp_en) == 2
    assert all(f.loc == 2 for f in fp_en)

    doc_pt = _make_doc([
        (1, "Introdução", "Nós apresentamos o sistema.", "Nós apresentamos o sistema."),
        (2, "Metodologia", "O nosso ensaio foi repetido por nós.", "O nosso ensaio foi repetido por nós."),
        (3, "Conclusões", "Concluímos que o nosso método funciona.", "Concluímos que o nosso método funciona."),
    ])
    fp_pt = [f for f in check_adpe_style([doc_pt], lang="pt", strict_impersonal=True) if f.rule_id == "FIRST_PERSON_CHECK"]
    assert len(fp_pt) == 2
    assert all(f.loc == 2 for f in fp_pt)


def test_undefined_acronym_and_whitelist():
    doc = _make_doc([
        (1, "Intro", "The Digital Twin (DTW) model runs fast.", "The Digital Twin (DTW) model runs fast."),
        (2, "Intro", "Later, DTW predicts wear.", "Later, DTW predicts wear."),
        (3, "Methods", "We used XRF and PDF data.", "We used XRF and PDF data."),
        (4, "Methods", "Then XRF and PDF were compared with XYZ and XYZ.", "Then XRF and PDF were compared with XYZ and XYZ."),
    ])
    findings = check_adpe_style([doc], lang="en", whitelist={"XYZ"})
    acrs = [f for f in findings if f.rule_id == "UNDEFINED_ACRONYM"]
    assert len(acrs) == 1
    assert acrs[0].excerpt == "XRF"
    assert acrs[0].loc == 3
