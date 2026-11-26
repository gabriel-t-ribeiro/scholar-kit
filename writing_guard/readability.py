"""Bilingual Flesch readability & grade-level analysis (ADPE Slide 18 & 19)."""

from __future__ import annotations

import re

from .language import detect_language
from .models import (
    LineRecord,
    ParsedDocument,
    ReadabilityReport,
    ReadabilityStats,
    SectionReadability,
    SentenceHotspot,
)
from .syllables import count_syllables, syllable_backend_for

_DOT_MASK = "\x00"

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ]+(?:[-'’][A-Za-zÀ-ÿ]+)*")

# Abbreviations whose trailing periods must not trigger sentence boundaries.
_ABBREV_SINGLE_RE = re.compile(
    r"\b("
    r"fig|figs|eq|eqs|sec|secs|dr|prof|vs|cf|ca|approx|"
    r"tab|tabs|ref|refs|vol|no|ch|chap|cap|art|pag|pág|"
    r"sr|sra|eng|inc|ltd|jr|mr|mrs|ms|st|ed|eds|pp"
    r")\.",
    re.IGNORECASE,
)

# `etc.` does not end a sentence unless followed by whitespace + capitalized sentence start.
_ABBREV_ETC_RE = re.compile(r"\betc\.(?!\s+[A-ZÀ-Ý])", re.IGNORECASE)

# ADPE Slide 19 / Flesch Reading Ease band table.
READING_EASE_BANDS: tuple[tuple[float, str, str], ...] = (
    (
        90.0,
        "5th grade",
        "Very easy to read. Easily understood by an average 11-year-old student.",
    ),
    (
        80.0,
        "6th grade",
        "Easy to read. Conversational language for consumers.",
    ),
    (
        70.0,
        "7th grade",
        "Fairly easy to read.",
    ),
    (
        60.0,
        "8th & 9th grade",
        "Plain language. Easily understood by 13- to 15-year-old students.",
    ),
    (
        50.0,
        "10th to 12th grade",
        "Fairly difficult to read.",
    ),
    (
        30.0,
        "College",
        "Difficult to read.",
    ),
    (
        10.0,
        "College graduate",
        "Very difficult to read. Best understood by university graduates.",
    ),
    (
        float("-inf"),
        "Professional",
        "Extremely difficult to read. Best understood by university graduates and domain specialists.",
    ),
)


def classify_reading_ease(score: float) -> tuple[str, str]:
    """Map a Flesch Reading Ease score to its Slide 19 band label and note."""
    for threshold, label, note in READING_EASE_BANDS:
        if score >= threshold:
            return label, note
    return READING_EASE_BANDS[-1][1], READING_EASE_BANDS[-1][2]


def _compute_flesch(asl: float, asw: float, lang: str) -> tuple[float, float]:
    """Compute (FRE, FKGL) using exact ADPE Slide 18 EN and PT formulas."""
    if lang == "pt":
        fre = 226.0 - 1.04 * asl - 72.0 * asw
        fkgl = 0.36 * asl + 10.4 * asw - 18.0
    else:
        fre = 206.835 - 1.015 * asl - 84.6 * asw
        fkgl = 0.39 * asl + 11.8 * asw - 15.59
    return fre, fkgl


def _mask_non_terminal_periods(text: str) -> str:
    """Replace periods that do not end sentences with a sentinel of equal length."""
    chars = list(text)

    def mask_span(start: int, end: int) -> None:
        for i in range(start, end):
            if chars[i] == ".":
                chars[i] = _DOT_MASK

    # Ellipses (.. or ...)
    for m in re.finditer(r"\.{2,}", text):
        mask_span(m.start(), m.end())

    # Decimals and dotted numbers (3.14, 1.2.3)
    for m in re.finditer(r"(?<=\d)\.(?=\d)", text):
        mask_span(m.start(), m.end())

    # Multi-word / dotted abbreviations: e.g., i.e., et al., p. ex., n.º
    for m in re.finditer(
        r"\b(?:e\.g\.|i\.e\.|et\s+al\.|p\.\s*ex\.|n\.\s*[º°o]\.?)",
        text,
        flags=re.IGNORECASE,
    ):
        mask_span(m.start(), m.end())

    # Single-word academic & title abbreviations
    for m in _ABBREV_SINGLE_RE.finditer(text):
        mask_span(m.start(), m.end())

    for m in _ABBREV_ETC_RE.finditer(text):
        mask_span(m.start(), m.end())

    # Single-letter initials before another capitalized word (e.g., A. Einstein)
    for m in re.finditer(r"\b[A-ZÀ-Ý]\.(?=\s+[A-ZÀ-Ý])", text):
        mask_span(m.start(), m.end())

    return "".join(chars)


def split_sentences_with_spans(text: str) -> list[tuple[int, str]]:
    """Split text into sentences while returning (start_char_index, sentence_text)."""
    if not text or not text.strip():
        return []

    masked = _mask_non_terminal_periods(text)
    results: list[tuple[int, str]] = []

    # Split at sentence-ending punctuation followed by whitespace, or blank-line boundaries
    boundary_re = re.compile(r'(?:[.!?]+["\'”’)\]]*)\s+|\n\s*\n+')
    start = 0
    for m in boundary_re.finditer(masked):
        raw_end = m.end()
        # Keep the terminal punctuation in the sentence, split before trailing whitespace
        ws_match = re.search(r"\s+$", m.group(0))
        seg_end = m.start() + (ws_match.start() if ws_match else len(m.group(0)))
        segment = masked[start:seg_end].replace(_DOT_MASK, ".").strip()
        if segment and _WORD_RE.search(segment):
            # Advance start offset past leading whitespace so line lookup is exact
            lead_ws = len(masked[start:seg_end]) - len(masked[start:seg_end].lstrip())
            results.append((start + lead_ws, segment))
        start = raw_end

    if start < len(masked):
        tail = masked[start:].replace(_DOT_MASK, ".").strip()
        if tail and _WORD_RE.search(tail):
            lead_ws = len(masked[start:]) - len(masked[start:].lstrip())
            results.append((start + lead_ws, tail))

    return results


def split_sentences(text: str) -> list[str]:
    """Split text into abbreviation-aware sentences."""
    return [sent for _, sent in split_sentences_with_spans(text)]


def _stats_from_counts(
    words: int,
    sentences: int,
    syllables: int,
    lang: str,
) -> ReadabilityStats:
    if words == 0 or sentences == 0:
        return ReadabilityStats(
            words=words,
            sentences=sentences,
            syllables=syllables,
            avg_words_per_sentence=0.0,
            avg_syllables_per_word=0.0,
            flesch_reading_ease=0.0,
            flesch_kincaid_grade=0.0,
            band_label="N/A",
            band_note="No readable prose found.",
        )

    asl = words / sentences
    asw = syllables / words
    fre, fkgl = _compute_flesch(asl, asw, lang)
    band_label, band_note = classify_reading_ease(fre)

    return ReadabilityStats(
        words=words,
        sentences=sentences,
        syllables=syllables,
        avg_words_per_sentence=round(asl, 2),
        avg_syllables_per_word=round(asw, 3),
        flesch_reading_ease=round(fre, 2),
        flesch_kincaid_grade=round(fkgl, 2),
        band_label=band_label,
        band_note=band_note,
    )


def _iter_doc_blocks(
    doc: ParsedDocument,
) -> list[tuple[str, str, int, list[tuple[int, int, str, int, str]]]]:
    """
    Yield per-section paragraph blocks with line-offset maps.

    Returns list of `(section_title, section_file, section_start_loc, paragraphs)`
    where each paragraph is `(para_text, line_spans)` — actually flattened into
    `(section_title, section_file, section_start_loc, [(text, spans_list), ...])`.
    """
    has_line_prose = any(lr.clean_text.strip() for lr in doc.lines)
    if has_line_prose:
        # Group lines into sections preserving order of appearance
        grouped_sections: list[tuple[str, str, int, list[LineRecord]]] = []
        current_key: tuple[str, str] | None = None
        current_lines: list[LineRecord] = []
        current_start_loc = 1

        for lr in doc.lines:
            key = (lr.section, lr.file)
            if current_key is None:
                current_key = key
                current_start_loc = lr.loc
                current_lines = [lr]
            elif lr.section != current_key[0]:
                grouped_sections.append(
                    (current_key[0], current_key[1], current_start_loc, current_lines)
                )
                current_key = key
                current_start_loc = lr.loc
                current_lines = [lr]
            else:
                current_lines.append(lr)

        if current_key is not None:
            grouped_sections.append(
                (current_key[0], current_key[1], current_start_loc, current_lines)
            )

        out = []
        for sec_title, sec_file, sec_start_loc, sec_lines in grouped_sections:
            # Build paragraphs separated by blank clean_text lines
            paras: list[tuple[str, list[tuple[int, int, LineRecord]]]] = []
            buf: list[str] = []
            spans: list[tuple[int, int, LineRecord]] = []
            cursor = 0
            for lr in sec_lines:
                txt = lr.clean_text.strip()
                if txt:
                    if buf:
                        buf.append(" ")
                        cursor += 1
                    start = cursor
                    buf.append(txt)
                    cursor += len(txt)
                    spans.append((start, cursor, lr))
                elif buf:
                    paras.append(("".join(buf), spans))
                    buf = []
                    spans = []
                    cursor = 0
            if buf:
                paras.append(("".join(buf), spans))

            if paras:
                out.append((sec_title, sec_file, sec_start_loc, paras))
        return out

    if doc.sections:
        out = []
        for sec in doc.sections:
            paras = []
            for chunk in re.split(r"\n\s*\n+", sec.text.strip()):
                cleaned = re.sub(r"\s+", " ", chunk).strip()
                if cleaned:
                    synthetic = LineRecord(
                        file=sec.file,
                        loc=sec.start_loc,
                        loc_label=doc.loc_label,
                        section=sec.title,
                        raw_text=cleaned,
                        clean_text=cleaned,
                    )
                    paras.append((cleaned, [(0, len(cleaned), synthetic)]))
            if paras:
                out.append((sec.title, sec.file, sec.start_loc, paras))
        return out

    if doc.full_clean_text.strip():
        paras = []
        for chunk in re.split(r"\n\s*\n+", doc.full_clean_text.strip()):
            cleaned = re.sub(r"\s+", " ", chunk).strip()
            if cleaned:
                synthetic = LineRecord(
                    file=doc.source_path,
                    loc=1,
                    loc_label=doc.loc_label,
                    section="Document",
                    raw_text=cleaned,
                    clean_text=cleaned,
                )
                paras.append((cleaned, [(0, len(cleaned), synthetic)]))
        if paras:
            return [("Document", doc.source_path, 1, paras)]

    return []


def _lookup_line(
    char_offset: int,
    spans: list[tuple[int, int, LineRecord]],
) -> LineRecord:
    for start, end, lr in spans:
        if start <= char_offset <= end:
            return lr
    return spans[0][2]


def analyze_readability(
    docs: list[ParsedDocument],
    lang: str,
    top_sentences: int = 5,
) -> ReadabilityReport:
    """Compute Flesch Reading Ease, FKGL, per-section breakdown, and sentence hotspots."""
    resolved_lang = lang.lower().strip()
    if resolved_lang == "auto":
        combined = "\n".join(d.full_clean_text for d in docs if d.full_clean_text)
        resolved_lang = detect_language(combined)
    if resolved_lang not in ("en", "pt"):
        raise ValueError(f"Unsupported language: {lang!r}. Expected 'en', 'pt', or 'auto'.")

    total_words = 0
    total_sentences = 0
    total_syllables = 0
    section_results: list[SectionReadability] = []
    hotspots: list[SentenceHotspot] = []

    for doc in docs:
        for sec_title, sec_file, sec_start_loc, paras in _iter_doc_blocks(doc):
            sec_words = 0
            sec_sentences = 0
            sec_syllables = 0

            for para_text, spans in paras:
                for sent_offset, sent_text in split_sentences_with_spans(para_text):
                    tokens = _WORD_RE.findall(sent_text)
                    if not tokens:
                        continue
                    w_count = len(tokens)
                    s_count = sum(count_syllables(tok, resolved_lang) for tok in tokens)

                    sec_words += w_count
                    sec_sentences += 1
                    sec_syllables += s_count

                    if w_count >= 15:
                        asw = s_count / w_count
                        sent_fre, _ = _compute_flesch(float(w_count), asw, resolved_lang)
                        lr = _lookup_line(sent_offset, spans)
                        hotspots.append(
                            SentenceHotspot(
                                file=lr.file,
                                section=sec_title,
                                loc=lr.loc,
                                loc_label=lr.loc_label,
                                words=w_count,
                                syllables=s_count,
                                avg_syllables_per_word=round(asw, 3),
                                reading_ease=round(sent_fre, 2),
                                text=sent_text,
                            )
                        )

            if sec_words > 0:
                sec_stats = _stats_from_counts(
                    sec_words, sec_sentences, sec_syllables, resolved_lang
                )
                section_results.append(
                    SectionReadability(
                        title=sec_title,
                        file=sec_file,
                        start_loc=sec_start_loc,
                        stats=sec_stats,
                    )
                )
                total_words += sec_words
                total_sentences += sec_sentences
                total_syllables += sec_syllables

    overall = _stats_from_counts(
        total_words, total_sentences, total_syllables, resolved_lang
    )
    hotspots.sort(key=lambda h: (h.reading_ease, -h.words))
    limited_hotspots = hotspots[: max(0, top_sentences)]

    return ReadabilityReport(
        lang=resolved_lang,
        syllable_backend=syllable_backend_for(resolved_lang),
        overall=overall,
        sections=section_results,
        hardest_sentences=limited_hotspots,
    )
