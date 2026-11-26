"""Core data models for writing_guard."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LineRecord:
    """Single source line or logical unit extracted from a document."""

    file: str
    loc: int
    loc_label: str
    section: str
    raw_text: str
    clean_text: str


@dataclass(slots=True)
class SectionChunk:
    """Contiguous prose section within a parsed document."""

    title: str
    file: str
    start_loc: int
    text: str


@dataclass(slots=True)
class ParsedDocument:
    """Normalized representation of a parsed document or document tree."""

    source_path: str
    files: list[str]
    loc_label: str
    lines: list[LineRecord]
    sections: list[SectionChunk]
    full_clean_text: str


@dataclass(slots=True)
class Finding:
    """Diagnostic finding emitted by style or language guards."""

    rule_id: str
    category: str
    severity: str
    file: str
    loc: int
    loc_label: str
    excerpt: str
    suggestion: str
    explanation: str


@dataclass(slots=True)
class ReadabilityStats:
    """Aggregate Flesch readability metrics and grade band."""

    words: int
    sentences: int
    syllables: int
    avg_words_per_sentence: float
    avg_syllables_per_word: float
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    band_label: str
    band_note: str


@dataclass(slots=True)
class SectionReadability:
    """Readability metrics scoped to a single document section."""

    title: str
    file: str
    start_loc: int
    stats: ReadabilityStats


@dataclass(slots=True)
class SentenceHotspot:
    """Hard-to-read sentence surfaced for revision."""

    file: str
    section: str
    loc: int
    loc_label: str
    words: int
    syllables: int
    avg_syllables_per_word: float
    reading_ease: float
    text: str


@dataclass(slots=True)
class ReadabilityReport:
    """Complete bilingual readability analysis report."""

    lang: str
    syllable_backend: str
    overall: ReadabilityStats
    sections: list[SectionReadability]
    hardest_sentences: list[SentenceHotspot]
