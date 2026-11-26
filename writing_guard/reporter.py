"""Terminal, JSON, and Markdown report formatters for writing_guard."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from .models import Finding, ParsedDocument, ReadabilityReport

_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _severity_counts(findings: list[Finding]) -> dict[str, int]:
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        sev = f.severity.upper()
        counts[sev] = counts.get(sev, 0) + 1
    return counts


def _format_severity_summary(counts: dict[str, int]) -> str:
    parts = [f"{k}={v}" for k, v in counts.items() if v > 0 or k in ("HIGH", "MEDIUM", "LOW")]
    return ", ".join(parts)


def _sorted_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (_SEVERITY_ORDER.get(f.severity.upper(), 9), f.file, f.loc, f.rule_id),
    )


def _truncate(text: str, limit: int = 120) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3] + "..."


def build_report_payload(
    *,
    target: str,
    lang: str,
    mode: str,
    docs: list[ParsedDocument],
    readability: ReadabilityReport | None,
    findings: list[Finding],
    show_sections: bool = True,
    gate_failures: list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable report dictionary."""
    all_files: list[str] = []
    for doc in docs:
        for f in doc.files:
            if f not in all_files:
                all_files.append(f)

    readability_dict: dict[str, Any] | None = None
    if readability is not None:
        readability_dict = asdict(readability)
        if not show_sections:
            readability_dict["sections"] = []

    ordered_findings = _sorted_findings(findings)
    counts = _severity_counts(ordered_findings)

    return {
        "target": target,
        "lang": lang,
        "mode": mode,
        "files": all_files,
        "readability": readability_dict,
        "findings": [asdict(f) for f in ordered_findings],
        "summary": {
            "total_findings": len(ordered_findings),
            "severity_counts": counts,
            "gate_failures": list(gate_failures or []),
            "passed": not bool(gate_failures),
        },
    }


def format_json_report(
    *,
    target: str,
    lang: str,
    mode: str,
    docs: list[ParsedDocument],
    readability: ReadabilityReport | None,
    findings: list[Finding],
    show_sections: bool = True,
    gate_failures: list[str] | None = None,
) -> str:
    """Render report as formatted JSON."""
    payload = build_report_payload(
        target=target,
        lang=lang,
        mode=mode,
        docs=docs,
        readability=readability,
        findings=findings,
        show_sections=show_sections,
        gate_failures=gate_failures,
    )
    return json.dumps(payload, indent=2, ensure_ascii=False)


def format_terminal_report(
    *,
    target: str,
    lang: str,
    mode: str,
    docs: list[ParsedDocument],
    readability: ReadabilityReport | None,
    findings: list[Finding],
    show_sections: bool = True,
    gate_failures: list[str] | None = None,
) -> str:
    """Render human-friendly terminal report with Slide 19 bands, sections, and findings."""
    all_files: list[str] = []
    for doc in docs:
        for f in doc.files:
            if f not in all_files:
                all_files.append(f)

    lines: list[str] = []
    bar = "=" * 76
    lines.append(bar)
    backend_info = f"  |  Syllables: {readability.syllable_backend}" if readability else ""
    lines.append(
        f"scholar-kit / writecheck  |  Language: {lang.upper()}  |  Mode: {mode}{backend_info}"
    )
    lines.append(f"Source: {target} ({len(all_files)} file{'s' if len(all_files) != 1 else ''})")
    lines.append(bar)

    if readability is not None:
        ov = readability.overall
        lines.append("Readability (Overall)")
        lines.append(
            f"  Words: {ov.words}  |  Sentences: {ov.sentences}  |  Syllables: {ov.syllables}"
        )
        lines.append(
            f"  ASL: {ov.avg_words_per_sentence:.2f} words/sent  |  "
            f"ASW: {ov.avg_syllables_per_word:.2f} syl/word"
        )
        lines.append(
            f"  Flesch Reading Ease: {ov.flesch_reading_ease:.1f} ({ov.band_label} — {ov.band_note})"
        )
        lines.append(f"  Flesch-Kincaid Grade: {ov.flesch_kincaid_grade:.1f}")

        if show_sections and readability.sections:
            lines.append("")
            lines.append("Per-Section Breakdown")
            header = (
                f"  {'Section':<28} {'Words':>6} {'Sents':>6} "
                f"{'ASL':>7} {'ASW':>6} {'FRE':>6} {'FKGL':>6}  Band"
            )
            lines.append(header)
            lines.append("  " + "-" * 78)
            for sec in readability.sections:
                st = sec.stats
                title = sec.title if len(sec.title) <= 27 else sec.title[:24] + "..."
                lines.append(
                    f"  {title:<28} {st.words:>6} {st.sentences:>6} "
                    f"{st.avg_words_per_sentence:>7.2f} {st.avg_syllables_per_word:>6.2f} "
                    f"{st.flesch_reading_ease:>6.1f} {st.flesch_kincaid_grade:>6.1f}  "
                    f"{st.band_label}"
                )

        if readability.hardest_sentences:
            lines.append("")
            lines.append(f"Hardest Sentences (top {len(readability.hardest_sentences)})")
            for idx, hs in enumerate(readability.hardest_sentences, start=1):
                lines.append(
                    f"  {idx}. [{hs.file}:{hs.loc} | {hs.section} | "
                    f"{hs.words} words | FRE {hs.reading_ease:.1f}]"
                )
                lines.append(f"     \"{_truncate(hs.text, 140)}\"")

    if mode in ("all", "style", "spelling"):
        ordered = _sorted_findings(findings)
        counts = _severity_counts(ordered)
        lines.append("")
        lines.append(f"Findings ({len(ordered)} total: {_format_severity_summary(counts)})")
        if not ordered:
            lines.append("  No style or language issues detected.")
        else:
            for f in ordered:
                sev = f"[{f.severity.upper()}]"
                lines.append(f"  {sev:<10} {f.file}:{f.loc} ({f.loc_label}) {f.rule_id} [{f.category}]")
                lines.append(f"           Excerpt:    {_truncate(f.excerpt, 100)}")
                if f.suggestion:
                    lines.append(f"           Suggestion: {f.suggestion}")
                if f.explanation:
                    lines.append(f"           Why:        {f.explanation}")

    if gate_failures:
        lines.append("")
        lines.append("Quality Gate Failures")
        for msg in gate_failures:
            lines.append(f"  FAIL: {msg}")

    lines.append(bar)
    return "\n".join(lines)


def format_markdown_report(
    *,
    target: str,
    lang: str,
    mode: str,
    docs: list[ParsedDocument],
    readability: ReadabilityReport | None,
    findings: list[Finding],
    show_sections: bool = True,
    gate_failures: list[str] | None = None,
) -> str:
    """Render report as GitHub-flavored Markdown."""
    all_files: list[str] = []
    for doc in docs:
        for f in doc.files:
            if f not in all_files:
                all_files.append(f)

    lines: list[str] = [
        "# Writing Guard Report",
        "",
        f"- **Source:** `{target}` ({len(all_files)} file{'s' if len(all_files) != 1 else ''})",
        f"- **Language:** `{lang.upper()}`",
        f"- **Mode:** `{mode}`",
    ]
    if readability is not None:
        lines.append(f"- **Syllable backend:** `{readability.syllable_backend}`")

    if readability is not None:
        ov = readability.overall
        lines.extend(
            [
                "",
                "## Readability (ADPE Slide 18 & 19)",
                "",
                "| Metric | Value |",
                "| :--- | :--- |",
                f"| Words | {ov.words} |",
                f"| Sentences | {ov.sentences} |",
                f"| Syllables | {ov.syllables} |",
                f"| Avg. Words / Sentence (ASL) | {ov.avg_words_per_sentence:.2f} |",
                f"| Avg. Syllables / Word (ASW) | {ov.avg_syllables_per_word:.2f} |",
                f"| Flesch Reading Ease (FRE) | **{ov.flesch_reading_ease:.1f}** ({ov.band_label}) |",
                f"| Flesch-Kincaid Grade (FKGL) | **{ov.flesch_kincaid_grade:.1f}** |",
                "",
                f"> {ov.band_note}",
            ]
        )

        if show_sections and readability.sections:
            lines.extend(
                [
                    "",
                    "### Per-Section Breakdown",
                    "",
                    "| Section | File | Words | Sentences | ASL | ASW | FRE | FKGL | Band |",
                    "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
                ]
            )
            for sec in readability.sections:
                st = sec.stats
                safe_title = sec.title.replace("|", "\\|")
                lines.append(
                    f"| {safe_title} | `{sec.file}:{sec.start_loc}` | {st.words} | {st.sentences} | "
                    f"{st.avg_words_per_sentence:.2f} | {st.avg_syllables_per_word:.2f} | "
                    f"{st.flesch_reading_ease:.1f} | {st.flesch_kincaid_grade:.1f} | {st.band_label} |"
                )

        if readability.hardest_sentences:
            lines.extend(["", "### Hardest Sentences", ""])
            for idx, hs in enumerate(readability.hardest_sentences, start=1):
                lines.append(
                    f"{idx}. **`{hs.file}:{hs.loc}`** ({hs.section}, {hs.words} words, "
                    f"FRE `{hs.reading_ease:.1f}`): \"{_truncate(hs.text, 180)}\""
                )

    if mode in ("all", "style", "spelling"):
        ordered = _sorted_findings(findings)
        counts = _severity_counts(ordered)
        lines.extend(
            [
                "",
                f"## Findings ({len(ordered)} total)",
                "",
                f"- {_format_severity_summary(counts).replace(', ', ' | ')}",
                "",
            ]
        )
        if not ordered:
            lines.append("No style or language issues detected.")
        else:
            lines.extend(
                [
                    "| Severity | Location | Rule | Excerpt | Suggestion |",
                    "| :--- | :--- | :--- | :--- | :--- |",
                ]
            )
            for f in ordered:
                exc = _truncate(f.excerpt, 60).replace("|", "\\|")
                sug = f.suggestion.replace("|", "\\|")
                lines.append(
                    f"| {f.severity} | `{f.file}:{f.loc}` | `{f.rule_id}` | {exc} | {sug} |"
                )

    if gate_failures:
        lines.extend(["", "## Quality Gate Failures", ""])
        for msg in gate_failures:
            lines.append(f"- **FAIL:** {msg}")

    lines.append("")
    return "\n".join(lines)
