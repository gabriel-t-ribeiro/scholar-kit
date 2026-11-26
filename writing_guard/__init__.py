"""scholar-kit writing_guard core bilingual readability, parsing, and style engine."""

from __future__ import annotations

from .language import detect_language
from .models import (
    Finding,
    LineRecord,
    ParsedDocument,
    ReadabilityReport,
    ReadabilityStats,
    SectionChunk,
    SectionReadability,
    SentenceHotspot,
)
from .parser import parse_path
from .readability import analyze_readability, classify_reading_ease, split_sentences
from .syllables import (
    count_syllables,
    count_syllables_en,
    count_syllables_pt,
    has_cmudict,
)

__all__ = [
    "Finding",
    "LineRecord",
    "ParsedDocument",
    "ReadabilityReport",
    "ReadabilityStats",
    "SectionChunk",
    "SectionReadability",
    "SentenceHotspot",
    "analyze_readability",
    "classify_reading_ease",
    "count_syllables",
    "count_syllables_en",
    "count_syllables_pt",
    "detect_language",
    "has_cmudict",
    "parse_path",
    "split_sentences",
]
