"""ADPE-aligned academic writing style guard for English and European Portuguese."""

from __future__ import annotations

import re
from typing import Iterable

from .models import Finding, LineRecord, ParsedDocument

# Common abbreviations that should not trigger sentence splits
_SENTENCE_ABBREVS = {
    "e.g",
    "i.e",
    "et al",
    "p. ex",
    "fig",
    "figs",
    "eq",
    "eqs",
    "sec",
    "tab",
    "cap",
    "dr",
    "prof",
    "mr",
    "mrs",
    "ms",
    "vs",
    "etc",
    "n.º",
    "cf",
    "vol",
    "no",
    "pp",
    "approx",
    "sr",
    "sra",
    "eng",
    "al",
    "ex",
}

_WORD_RE = re.compile(r"\b[\wÀ-ÖØ-öø-ÿ]+(?:[-'’][\wÀ-ÖØ-öø-ÿ]+)*\b")

_ITALIC_LATIN_RE = re.compile(
    r"(?i)"
    r"(?:"
    r"\\(?:textit|emph)\{\s*(e\.g\.|i\.e\.|etc\.|ibid\.|et(?:\s+|~)al\.)\s*\}"
    r"|"
    r"(?<!\w)([*_])(e\.g\.|i\.e\.|etc\.|ibid\.|et\s+al\.)\2(?!\w)"
    r")"
)

_ABBREV_DOUBLE_PERIOD_RE = re.compile(
    r"(?i)\b(?:etc|e\.g|i\.e|et\s+al|vs|cf|ibid|fig|eq|sec|dr|prof|p\.\s*ex)\.\.(?!\.)"
)

_DESTE_POSSESSIVE_RE = re.compile(
    r"(?i)\b(?:o|a|os|as|um|uma|do|da|dos|das|no|na|nos|nas|ao|à|aos|às|pelo|pela|pelos|pelas)"
    r"\s+[a-zA-Zçáéíóúâêôãõàü-]{3,}\s+"
    r"(dest[ea]s?|dess[ea]s?)"
    r"(?=\s*(?:[.,;:!?)]|$|\b(?:é|são|foi|foram|será|serão|era|eram|está|estão|estava|tem|têm|tinha|teve|"
    r"pode|podem|permite|permitem|mostra|mostram|indica|indicam|apresenta|apresentam|"
    r"aumenta|aumentou|diminui|diminuiu|varia|variou|depende|dependem|revela|revelou|"
    r"e|ou|mas|que|para|em|no|na|nos|nas|com|por|sobre|entre|sem|até|após|durante)\b))"
)

_SI_UNIT_SUFFIX_RE = re.compile(
    r"^(?:\s*(?:°\s*[CFK]|%|mm|cm|dm|km|µm|um|nm|m|kg|mg|µg|ug|g|ms|µs|us|ns|min|h|d|s|"
    r"GHz|MHz|kHz|Hz|MW|kW|mW|W|kV|mV|V|mA|µA|uA|A|K|GPa|MPa|kPa|Pa|mbar|bar|"
    r"MJ|kJ|J|kN|N|Nm|N·m|mL|L|mol|rpm|fps|px|bits?|bytes?|GB|MB|KB|dB|rad|deg|°|Ω|kΩ|MΩ|"
    r"vezes|x|×)(?![A-Za-zÀ-ÖØ-öø-ÿ]))"
)

_LABEL_PREFIX_RE = re.compile(
    r"(?i)(?:fig\.?|figura|tabela|tab\.?|quadro|sec\.?|secção|capítulo|cap\.?|"
    r"equação|eq\.?|anexo|apêndice|passo|caso|etapa|fase|nível|tipo|grupo|"
    r"canal|porta|eixo|modelo|versão|ensaio|teste|amostra|sensor|n\.º|nº|no\.|#)\s*$"
)

_BARE_SMALL_INT_RE = re.compile(
    r"(?<![A-Za-zÀ-ÖØ-öø-ÿªº\d.,:/-])([1-9])(?![A-Za-zÀ-ÖØ-öø-ÿªº\d.,:/-])"
)
_BARE_SMALL_ORD_RE = re.compile(r"(?<![\d.,:/-])([1-9]\.?[ªº])(?![\w])")

_EN_CALQUE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(
            r"(?i)\bIt\s+(?:was|is)\s+(?:developed|observed|made|used|obtained|performed|found|created|proposed|implemented)\s+an?\b"
        ),
        "Rewrite with the subject before the verb (e.g., 'A <noun> was developed...' or 'We developed a...').",
        "Literal Portuguese-to-English impersonal 'it was <verb> a...' calque.",
    ),
    (
        re.compile(
            r"(?i)(?<!\bis\s)(?<!\bare\s)(?<!\bwas\s)(?<!\bwere\s)(?<!\bbe\s)(?<!\bbeen\s)"
            r"\b(?:allows?|allowing)\s+to\s+[a-z]{2,}\b"
        ),
        "Use 'allows <object> to <verb>' or 'enables <gerund/noun>' instead of 'allows to <verb>'.",
        "Calque of Portuguese 'permite <infinitivo>' ('allows to <verb>' requires an object in English).",
    ),
    (
        re.compile(r"(?i)\bconsist(?:s|ed|ing)?\s+in\b"),
        "Use 'consists of' (components) or 'involves / comprises'.",
        "Calque of Portuguese 'consiste em' ('consists in' is rare/philosophical in technical English).",
    ),
    (
        re.compile(r"(?i)\bdifferent\s+than\b"),
        "Use 'different from'.",
        "Informal/non-standard comparative; formal technical English prefers 'different from'.",
    ),
    (
        re.compile(r"(?i)\b(?:make|made|making|makes)\s+an\s+analysis\b"),
        "Use 'perform/conduct an analysis' or 'analyze'.",
        "Calque of Portuguese 'fazer uma análise'.",
    ),
]

_EN_WEAK_START_RE = re.compile(r"^(And|But|So)\b(?:\s+|,\s+)")

_FIRST_PERSON_EN_I_RE = re.compile(
    r"(?<!Phase\s)(?<!Section\s)(?<!Type\s)(?<!Model\s)(?<!Part\s)"
    r"(?<!Class\s)(?<!Grade\s)(?<!Table\s)(?<!Figure\s)(?<!Appendix\s)(?<!Chapter\s)"
    r"\bI\b(?!\s*[.)])"
)
_FIRST_PERSON_EN_RE = re.compile(r"\b(we|our)\b", re.IGNORECASE)
_FIRST_PERSON_PT_RE = re.compile(r"\b(eu|nós|nossos?|nossas?)\b", re.IGNORECASE)

_IMPERSONAL_ALLOWED_SECTIONS = (
    "introduction",
    "introdução",
    "conclusion",
    "conclusions",
    "conclusão",
    "conclusões",
)

_STANDARD_ACRONYMS = {
    "PDF", "USB", "CPU", "GPU", "IEEE", "SI", "DNA", "RNA",
    "HTML", "CSS", "JSON", "XML", "CSV", "CLI", "API", "URL",
    "HTTP", "HTTPS", "SQL", "RGB", "HSV", "CAD", "CFD", "RAM",
    "ROM", "SSD", "HDD", "ISO", "DIN", "ASTM", "NASA", "ESA",
    "MIT", "USA", "ROI", "FPS", "CNN", "RNN", "LLM", "NLP",
    "ROS", "GUI", "IDE", "SSH", "TCP", "UDP", "PWM", "ADC",
    "DAC", "PID", "CNC", "FEM", "FEA", "YAML", "UTF",
}

_HEADING_CAPS_SKIP = {
    "INTRODUCTION", "CONCLUSION", "CONCLUSIONS", "ABSTRACT", "METHODOLOGY",
    "RESULTS", "DISCUSSION", "REFERENCES", "APPENDIX", "ACKNOWLEDGEMENTS",
    "INTRODUÇÃO", "CONCLUSÃO", "CONCLUSÕES", "RESUMO", "METODOLOGIA",
    "RESULTADOS", "DISCUSSÃO", "REFERÊNCIAS", "ANEXO", "FIGURA", "TABELA",
    "QUADRO", "CAPÍTULO", "THE", "AND", "FOR",
}

_ROMAN_NUMERAL_RE = re.compile(r"^(?=[IVX]{3,}$)(?:X{0,3}(?:IX|IV|V?I{0,3}))$")
_ACRONYM_RE = re.compile(r"\b([A-Z]{3,})\b")


def _truncate(text: str, limit: int = 120) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def _is_sentence_boundary(text: str, dot_pos: int) -> bool:
    """Return True if the punctuation at dot_pos ends a sentence."""
    ch = text[dot_pos]
    if ch in ("!", "?"):
        return True

    before = text[:dot_pos]
    # Check ellipsis
    if before.endswith(".") or (dot_pos + 1 < len(text) and text[dot_pos + 1] == "."):
        return False

    # Extract preceding phrase / token
    m_prev = re.search(r"([A-Za-zÀ-ÖØ-öø-ÿ0-9.º]+)$", before)
    if not m_prev:
        return False
    token = m_prev.group(1)

    # Known abbreviations (including two-word 'et al' or 'p. ex')
    tail_low = before.lower()
    for abbrev in _SENTENCE_ABBREVS:
        if tail_low.endswith(abbrev) and (
            len(tail_low) == len(abbrev) or not tail_low[-len(abbrev) - 1].isalpha()
        ):
            return False

    # Leading list/section number like "1." at start of line/chunk
    if token.isdigit() and (len(before) == len(token) or before[-len(token) - 1].isspace()):
        return False

    # Single uppercase initial (e.g. "J. Smith")
    if len(token) == 1 and token.isupper():
        return False

    return True


def _split_sentences_with_offsets(text: str) -> list[tuple[int, int, str]]:
    """Split text into (start, end, sentence_text) spans."""
    spans: list[tuple[int, int, str]] = []
    start = 0
    for m in re.finditer(r"([.!?]+)(?=\s+|$)", text):
        punct_start = m.start()
        if not _is_sentence_boundary(text, punct_start):
            continue
        end = m.end()
        chunk = text[start:end].strip()
        if chunk:
            lead_ws = len(text[start:end]) - len(text[start:end].lstrip())
            spans.append((start + lead_ws, end, chunk))
        start = end
    tail = text[start:].strip()
    if tail:
        lead_ws = len(text[start:]) - len(text[start:].lstrip())
        spans.append((start + lead_ws, len(text), tail))
    return spans


def _iter_paragraphs_with_lines(
    lines: Iterable[LineRecord],
) -> Iterable[tuple[str, list[tuple[int, int, LineRecord]]]]:
    """Group consecutive non-empty lines in the same (file, section) into paragraphs."""
    buf: list[LineRecord] = []
    current_key: tuple[str, str] | None = None

    def flush() -> tuple[str, list[tuple[int, int, LineRecord]]] | None:
        if not buf:
            return None
        parts: list[str] = []
        offsets: list[tuple[int, int, LineRecord]] = []
        pos = 0
        for idx, rec in enumerate(buf):
            txt = rec.clean_text.strip()
            if idx > 0:
                parts.append(" ")
                pos += 1
            start = pos
            parts.append(txt)
            pos += len(txt)
            offsets.append((start, pos, rec))
        return "".join(parts), offsets

    for rec in lines:
        txt = rec.clean_text.strip()
        key = (rec.file, rec.section)
        if not txt:
            flushed = flush()
            if flushed is not None:
                yield flushed
            buf = []
            current_key = None
            continue
        if current_key is not None and key != current_key:
            flushed = flush()
            if flushed is not None:
                yield flushed
            buf = []
        buf.append(rec)
        current_key = key

    flushed = flush()
    if flushed is not None:
        yield flushed


def _line_for_offset(offsets: list[tuple[int, int, LineRecord]], char_pos: int) -> LineRecord:
    for _start, end, rec in offsets:
        if char_pos <= end:
            return rec
    return offsets[-1][2]


def _is_section_impersonal_exempt(section: str) -> bool:
    sec_low = (section or "").lower()
    return any(tok in sec_low for tok in _IMPERSONAL_ALLOWED_SECTIONS)


def _is_defined_at_first_use(line_text: str, start: int, end: int) -> bool:
    before = line_text[:start].rstrip()
    after = line_text[end:].lstrip()
    # Pattern 1: Long Form (ACR)
    if before.endswith("(") and after.startswith((")", ",", ";")):
        return True
    # Pattern 2: ACR (Long Form with >= 2 alphabetic words)
    m_after = re.match(r"^\(([^)]{3,})\)", after)
    if m_after:
        words = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}", m_after.group(1))
        if len(words) >= 2:
            return True
    return False


def check_adpe_style(
    docs: list[ParsedDocument],
    lang: str,
    strict_impersonal: bool = False,
    whitelist: set[str] | None = None,
) -> list[Finding]:
    """Run ADPE academic style checks over parsed documents."""
    norm_lang = (lang or "en").lower()
    is_pt = norm_lang.startswith("pt")
    is_en = not is_pt
    wl_lower = {w.lower() for w in (whitelist or set())}

    findings: list[Finding] = []

    for doc in docs:
        # Paragraph-level rules: LONG_SENTENCE and EN_WEAK_START_CONJ
        for para_text, line_offsets in _iter_paragraphs_with_lines(doc.lines):
            for s_start, _s_end, sent in _split_sentences_with_offsets(para_text):
                rec = _line_for_offset(line_offsets, s_start)
                words = _WORD_RE.findall(sent)
                n_words = len(words)
                if n_words > 50:
                    findings.append(
                        Finding(
                            rule_id="LONG_SENTENCE",
                            category="Style / Sentence Length",
                            severity="HIGH",
                            file=rec.file,
                            loc=rec.loc,
                            loc_label=rec.loc_label,
                            excerpt=_truncate(sent),
                            suggestion="Split into two or more concise sentences (target <= 30 words).",
                            explanation=f"Sentence has {n_words} words (exceeds 50-word ADPE maximum threshold).",
                        )
                    )
                elif n_words > 35:
                    findings.append(
                        Finding(
                            rule_id="LONG_SENTENCE",
                            category="Style / Sentence Length",
                            severity="MEDIUM",
                            file=rec.file,
                            loc=rec.loc,
                            loc_label=rec.loc_label,
                            excerpt=_truncate(sent),
                            suggestion="Consider splitting or tightening phrasing (target <= 30 words).",
                            explanation=f"Sentence has {n_words} words (exceeds 35-word ADPE readability threshold).",
                        )
                    )

                if is_en:
                    m_conj = _EN_WEAK_START_RE.match(sent)
                    if m_conj:
                        conj = m_conj.group(1)
                        findings.append(
                            Finding(
                                rule_id="EN_WEAK_START_CONJ",
                                category="EN Style",
                                severity="LOW",
                                file=rec.file,
                                loc=rec.loc,
                                loc_label=rec.loc_label,
                                excerpt=_truncate(sent, 80),
                                suggestion="Replace with 'Furthermore,', 'However,', or 'Therefore,' or join with the previous clause.",
                                explanation=f"Formal academic English avoids starting sentences with informal '{conj}'.",
                            )
                        )

        # Acronym tracking per document
        acronym_hits: dict[str, list[tuple[LineRecord, int, int]]] = {}

        # Line-level rules
        for line in doc.lines:
            raw = line.raw_text or ""
            clean = line.clean_text or ""

            # 2. ITALIC_LATIN_ABBREV (inspect raw_text)
            for m in _ITALIC_LATIN_RE.finditer(raw):
                abbrev = (m.group(1) or m.group(3) or "").strip()
                findings.append(
                    Finding(
                        rule_id="ITALIC_LATIN_ABBREV",
                        category="ADPE Formatting",
                        severity="LOW",
                        file=line.file,
                        loc=line.loc,
                        loc_label=line.loc_label,
                        excerpt=m.group(0),
                        suggestion=f"Write '{abbrev}' in roman (upright) text without italics.",
                        explanation="Established Latin abbreviations (e.g., i.e., etc., et al., ibid.) should not be italicized.",
                    )
                )

            if not clean.strip():
                continue

            # 3. ABBREV_DOUBLE_PERIOD
            for m in _ABBREV_DOUBLE_PERIOD_RE.finditer(clean):
                findings.append(
                    Finding(
                        rule_id="ABBREV_DOUBLE_PERIOD",
                        category="Punctuation",
                        severity="MEDIUM",
                        file=line.file,
                        loc=line.loc,
                        loc_label=line.loc_label,
                        excerpt=m.group(0),
                        suggestion=f"Remove the duplicate period: '{m.group(0)[:-1]}'.",
                        explanation="An abbreviation ending a clause or sentence takes only a single trailing period.",
                    )
                )

            # 4 & 5. PT-only rules
            if is_pt:
                for m in _DESTE_POSSESSIVE_RE.finditer(clean):
                    findings.append(
                        Finding(
                            rule_id="PT_DESTE_OVERUSE",
                            category="PT Style",
                            severity="LOW",
                            file=line.file,
                            loc=line.loc,
                            loc_label=line.loc_label,
                            excerpt=m.group(0),
                            suggestion="Consider replacing '<noun> deste/a' with 'o seu/a sua <noun>' or naming the referent.",
                            explanation="Possessive-like use of 'deste/desta/desse/dessa' can often be replaced by 'seu/sua' for cleaner academic Portuguese.",
                        )
                    )

                if not re.match(r"^\s*[1-9][.)]\s+", clean):
                    for m in _BARE_SMALL_INT_RE.finditer(clean):
                        prefix = clean[: m.start()]
                        suffix = clean[m.end() :]
                        if _LABEL_PREFIX_RE.search(prefix) or _SI_UNIT_SUFFIX_RE.match(suffix):
                            continue
                        findings.append(
                            Finding(
                                rule_id="PT_BARE_SMALL_NUMERAL",
                                category="PT Style",
                                severity="LOW",
                                file=line.file,
                                loc=line.loc,
                                loc_label=line.loc_label,
                                excerpt=_truncate(clean[max(0, m.start() - 15) : m.end() + 15], 60),
                                suggestion="Write small integers (1-9) in full in prose (e.g., 'três', 'cinco').",
                                explanation="Small numerals 1-9 without SI units or figure/table labels should be written out in formal prose.",
                            )
                        )
                    for m in _BARE_SMALL_ORD_RE.finditer(clean):
                        prefix = clean[: m.start()]
                        if _LABEL_PREFIX_RE.search(prefix):
                            continue
                        findings.append(
                            Finding(
                                rule_id="PT_BARE_SMALL_NUMERAL",
                                category="PT Style",
                                severity="LOW",
                                file=line.file,
                                loc=line.loc,
                                loc_label=line.loc_label,
                                excerpt=m.group(0),
                                suggestion="Write small ordinals (1.º-9.º) in full in prose (e.g., 'primeiro', 'segunda').",
                                explanation="Small ordinals in running prose should be written out in formal Portuguese.",
                            )
                        )

            # 6. EN-only calques
            if is_en:
                for pat, suggestion, explanation in _EN_CALQUE_PATTERNS:
                    for m in pat.finditer(clean):
                        findings.append(
                            Finding(
                                rule_id="EN_PT_TRANSLATION_CALQUE",
                                category="EN Style / Calque",
                                severity="MEDIUM",
                                file=line.file,
                                loc=line.loc,
                                loc_label=line.loc_label,
                                excerpt=m.group(0),
                                suggestion=suggestion,
                                explanation=explanation,
                            )
                        )

            # 8. FIRST_PERSON_CHECK
            if strict_impersonal and not _is_section_impersonal_exempt(line.section):
                if is_en:
                    for m in _FIRST_PERSON_EN_I_RE.finditer(clean):
                        findings.append(
                            Finding(
                                rule_id="FIRST_PERSON_CHECK",
                                category="Impersonal Voice",
                                severity="MEDIUM",
                                file=line.file,
                                loc=line.loc,
                                loc_label=line.loc_label,
                                excerpt=m.group(0),
                                suggestion="Use passive voice or third-person phrasing (e.g., 'this study', 'the proposed method').",
                                explanation="First-person pronouns are discouraged outside Introduction/Conclusions under strict impersonal mode.",
                            )
                        )
                    for m in _FIRST_PERSON_EN_RE.finditer(clean):
                        findings.append(
                            Finding(
                                rule_id="FIRST_PERSON_CHECK",
                                category="Impersonal Voice",
                                severity="MEDIUM",
                                file=line.file,
                                loc=line.loc,
                                loc_label=line.loc_label,
                                excerpt=m.group(0),
                                suggestion="Use passive voice or third-person phrasing (e.g., 'this work', 'the authors').",
                                explanation="First-person pronouns are discouraged outside Introduction/Conclusions under strict impersonal mode.",
                            )
                        )
                else:
                    for m in _FIRST_PERSON_PT_RE.finditer(clean):
                        findings.append(
                            Finding(
                                rule_id="FIRST_PERSON_CHECK",
                                category="Impersonal Voice",
                                severity="MEDIUM",
                                file=line.file,
                                loc=line.loc,
                                loc_label=line.loc_label,
                                excerpt=m.group(0),
                                suggestion="Use reflexive passive ('desenvolveu-se') or third person ('este trabalho').",
                                explanation="First-person pronouns are discouraged outside Introduction/Conclusions under strict impersonal mode.",
                            )
                        )

            # 9. Collect acronyms (skip predominantly uppercase lines like ALL-CAPS headers)
            alpha_chars = [c for c in clean if c.isalpha()]
            is_all_caps_line = (
                len(alpha_chars) >= 8
                and sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars) > 0.75
                and len(clean.split()) >= 2
            )
            if not is_all_caps_line:
                for m in _ACRONYM_RE.finditer(clean):
                    acr = m.group(1)
                    if (
                        acr in _STANDARD_ACRONYMS
                        or acr in _HEADING_CAPS_SKIP
                        or acr.lower() in wl_lower
                        or _ROMAN_NUMERAL_RE.match(acr)
                    ):
                        continue
                    acronym_hits.setdefault(acr, []).append((line, m.start(), m.end()))

        for acr, hits in acronym_hits.items():
            if len(hits) < 2:
                continue
            first_line, f_start, f_end = hits[0]
            if not _is_defined_at_first_use(first_line.clean_text, f_start, f_end):
                findings.append(
                    Finding(
                        rule_id="UNDEFINED_ACRONYM",
                        category="Acronyms",
                        severity="MEDIUM",
                        file=first_line.file,
                        loc=first_line.loc,
                        loc_label=first_line.loc_label,
                        excerpt=acr,
                        suggestion=f"Define '{acr}' in parentheses on first use (e.g., 'Full Term ({acr})').",
                        explanation=f"Acronym '{acr}' appears {len(hits)} times without being defined in parentheses at its first occurrence.",
                    )
                )

    return findings
