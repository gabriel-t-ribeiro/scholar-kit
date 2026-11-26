"""Tests for European Portuguese guard (writing_guard.pt_guard)."""

from __future__ import annotations

from writing_guard.models import LineRecord, ParsedDocument, SectionChunk
from writing_guard.pt_guard import (
    DIC_FILE,
    add_to_whitelist,
    check_pt_document,
    detect_gerund_infinitive,
    load_verb_gerund_lookup,
    load_whitelist,
)


def _make_pt_doc(lines: list[tuple[int, str]], file: str = "relatorio.tex") -> ParsedDocument:
    records = [
        LineRecord(
            file=file,
            loc=loc,
            loc_label="Line",
            section="Corpo",
            raw_text=txt,
            clean_text=txt,
        )
        for loc, txt in lines
    ]
    return ParsedDocument(
        source_path=file,
        files=[file],
        loc_label="Line",
        lines=records,
        sections=[SectionChunk(title="Corpo", file=file, start_loc=1, text="\n".join(t for _, t in lines))],
        full_clean_text="\n".join(t for _, t in lines),
    )


def test_ai_isms_pt_br_consonants_and_enclitics(tmp_path):
    wl = tmp_path / "whitelist.txt"
    wl.write_text("# custom whitelist\n", encoding="utf-8")

    doc = _make_pt_doc([
        (1, "No escopo deste projeto, a acurácia do modelo foi elevada."),
        (2, "O usuário guardou o arquivo no ecrã e vai contatar a equipa."),
        (3, "Na faixa de pedestres realizou-se a validação."),
    ])
    findings = check_pt_document([doc], whitelist_path=str(wl))
    by_rule = {}
    for f in findings:
        by_rule.setdefault(f.rule_id, []).append(f)

    ai_words = {f.excerpt.lower(): f for f in by_rule.get("PT_AI_ISM", [])}
    assert "escopo" in ai_words and ai_words["escopo"].severity == "CRITICAL"
    assert "acurácia" in ai_words and ai_words["acurácia"].severity == "CRITICAL"

    br_words = {f.excerpt.lower() for f in by_rule.get("PT_BR_LEXICON", [])}
    assert {"usuário", "arquivo"}.issubset(br_words)

    br_phrases = {f.excerpt.lower() for f in by_rule.get("PT_BR_PHRASE", [])}
    assert "faixa de pedestres" in br_phrases

    cons_words = {f.excerpt.lower() for f in by_rule.get("PT_BR_CONSONANT", [])}
    assert "contatar" in cons_words

    unknown = {f.excerpt.lower() for f in by_rule.get("PT_SPELLING_UNKNOWN", [])}
    assert "realizou-se" not in unknown


def test_gerund_detection_preserves_uncommitted_rule(tmp_path):
    wl = tmp_path / "whitelist.txt"
    wl.write_text("", encoding="utf-8")

    verbs, irregular = load_verb_gerund_lookup(DIC_FILE)
    assert "fazer" in verbs
    assert detect_gerund_infinitive("fazendo", verbs, irregular, {"mestrando"}) == "fazer"
    assert detect_gerund_infinitive("fazendo-se", verbs, irregular, set()) == "fazer"
    assert detect_gerund_infinitive("mestrando", verbs, irregular, {"mestrando"}) is None

    doc = _make_pt_doc([
        (1, "O mestrando está analisando os dados e desenvolvendo-se bem."),
    ])
    findings = check_pt_document([doc], whitelist_path=str(wl))
    gerunds = [f.excerpt.lower() for f in findings if f.rule_id == "PT_GERUNDIO"]
    assert "analisando" in gerunds
    assert "desenvolvendo-se" in gerunds
    assert "mestrando" not in gerunds


def test_same_sentence_verb_stem_repetition(tmp_path):
    wl = tmp_path / "whitelist.txt"
    wl.write_text("", encoding="utf-8")

    doc = _make_pt_doc([
        (1, "O sistema apresentou os dados durante a apresentação preliminar."),
        (2, "A maquinagem de precisão permite maquinar a peça."),
    ])
    findings = check_pt_document([doc], whitelist_path=str(wl))
    reps = [f for f in findings if f.rule_id == "PT_VERB_REPETITION"]
    assert len(reps) == 1
    assert reps[0].loc == 1
    assert "apresentou" in reps[0].excerpt and "apresentação" in reps[0].excerpt


def test_whitelist_load_and_add(tmp_path):
    wl = tmp_path / "whitelist.txt"
    wl.write_text("# comment\nXyzTerm\n", encoding="utf-8")

    loaded = load_whitelist(str(wl))
    assert loaded == {"xyzterm"}

    doc = _make_pt_doc([(1, "O termo FooBarTecnico não existe no dicionário.")])
    before = check_pt_document([doc], whitelist_path=str(wl))
    assert any(f.rule_id == "PT_SPELLING_UNKNOWN" and f.excerpt == "FooBarTecnico" for f in before)

    out_path = add_to_whitelist("FooBarTecnico", whitelist_path=str(wl))
    assert out_path == str(wl)
    # Adding again is idempotent
    add_to_whitelist("foobartecnico", whitelist_path=str(wl))
    assert wl.read_text(encoding="utf-8").count("FooBarTecnico") == 1

    after = check_pt_document([doc], whitelist_path=str(wl))
    assert not any(f.excerpt == "FooBarTecnico" for f in after)
