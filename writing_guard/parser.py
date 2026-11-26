"""Multi-format document parser for .tex, .pdf, .md, .docx, and .txt."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
import zipfile

from .models import LineRecord, ParsedDocument, SectionChunk

try:
    import pypdf  # type: ignore[import-not-found]
except ImportError:
    pypdf = None

SUPPORTED_EXTENSIONS = frozenset({
    ".tex",
    ".latex",
    ".pdf",
    ".md",
    ".markdown",
    ".docx",
    ".txt",
})

_SKIP_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
})

_REFERENCE_TITLES = frozenset({
    "references",
    "bibliography",
    "referências",
    "referencias",
    "referências bibliográficas",
    "referencias bibliograficas",
    "bibliografia",
})

_TEX_STRIP_ENVS = frozenset({
    "equation",
    "equation*",
    "align",
    "align*",
    "gather",
    "gather*",
    "eqnarray",
    "eqnarray*",
    "multline",
    "multline*",
    "flalign",
    "flalign*",
    "alignat",
    "alignat*",
    "displaymath",
    "math",
    "tabular",
    "tabular*",
    "tabularx",
    "longtable",
    "tikzpicture",
    "picture",
    "lstlisting",
    "minted",
    "verbatim",
    "verbatim*",
    "bibliography",
})

_TEX_DROP_ARG_CMDS = frozenset({
    "cite",
    "citep",
    "citet",
    "citeauthor",
    "citeyear",
    "citealp",
    "citealt",
    "textcite",
    "parencite",
    "autocite",
    "nocite",
    "ref",
    "autoref",
    "pageref",
    "eqref",
    "cref",
    "Cref",
    "label",
    "url",
    "includegraphics",
    "bibliography",
    "bibliographystyle",
    "addbibresource",
    "input",
    "include",
    "usepackage",
    "documentclass",
    "vspace",
    "hspace",
    "setlength",
    "newcommand",
    "renewcommand",
    "providecommand",
    "pagestyle",
    "thispagestyle",
    "hypersetup",
    "sisetup",
    "unit",
    "si",
    "color",
    "pagecolor",
    "rule",
})

_SI_TOKEN_MAP = {
    "milli": "m",
    "centi": "c",
    "deci": "d",
    "kilo": "k",
    "mega": "M",
    "giga": "G",
    "micro": "µ",
    "nano": "n",
    "metre": "m",
    "meter": "m",
    "gram": "g",
    "second": "s",
    "minute": "min",
    "hour": "h",
    "newton": "N",
    "pascal": "Pa",
    "bar": "bar",
    "watt": "W",
    "volt": "V",
    "ampere": "A",
    "kelvin": "K",
    "celsius": "°C",
    "hertz": "Hz",
    "joule": "J",
    "percent": "%",
    "litre": "L",
    "liter": "L",
    "rpm": "rpm",
    "degree": "°",
    "per": "/",
    "squared": "2",
    "cubed": "3",
}


def _render_si_unit(unit_tex: str) -> str:
    """Convert common siunitx unit macros like \\milli\\metre into compact unit text."""
    tokens = re.findall(r"\\([a-zA-Z]+)|([A-Za-z%/°]+)", unit_tex)
    parts: list[str] = []
    for cmd, lit in tokens:
        if cmd:
            parts.append(_SI_TOKEN_MAP.get(cmd, cmd))
        elif lit:
            parts.append(lit)
    rendered = "".join(parts).strip()
    return rendered or "unit"


def _has_odd_preceding_backslashes(text: str, idx: int) -> bool:
    """Return True if text[idx] is immediately preceded by an odd number of backslashes."""
    bs = 0
    j = idx - 1
    while j >= 0 and text[j] == "\\":
        bs += 1
        j -= 1
    return (bs % 2) == 1

_TEX_UNWRAP_CMDS = frozenset({
    "textbf",
    "textit",
    "emph",
    "underline",
    "textrm",
    "textsf",
    "texttt",
    "textsc",
    "caption",
    "title",
    "subtitle",
    "footnote",
    "enquote",
    "mbox",
    "text",
    "mathrm",
    "num",
})

_TEX_SECTION_CMDS = ("chapter", "section", "subsection")

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _normalize_ws(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text


def _join_clean_lines(clean_lines: list[str]) -> str:
    """Join per-line clean_text values, preserving paragraph breaks on blank lines."""
    paragraphs: list[str] = []
    current: list[str] = []
    for line in clean_lines:
        stripped = line.strip()
        if stripped:
            current.append(stripped)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _finalize_sections(
    lines: list[LineRecord],
    section_starts: list[tuple[str, str, int, int]],
) -> list[SectionChunk]:
    """Build SectionChunk objects from recorded section boundaries."""
    sections: list[SectionChunk] = []
    for idx, (title, sec_file, start_loc, start_line_idx) in enumerate(section_starts):
        end_line_idx = (
            section_starts[idx + 1][3]
            if idx + 1 < len(section_starts)
            else len(lines)
        )
        chunk_lines = [lr.clean_text for lr in lines[start_line_idx:end_line_idx]]
        chunk_text = _join_clean_lines(chunk_lines)
        if chunk_text:
            sections.append(
                SectionChunk(
                    title=title,
                    file=sec_file,
                    start_loc=start_loc,
                    text=chunk_text,
                )
            )
    return sections


def _is_reference_title(title: str) -> bool:
    normalized = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", title.strip()).lower()
    return normalized in _REFERENCE_TITLES


# ---------------------------------------------------------------------------
# LaTeX helpers
# ---------------------------------------------------------------------------


def _strip_tex_comments(line: str) -> str:
    """Remove unescaped % comments while preserving escaped \\%."""
    return re.sub(r"((?:^|[^\\])(?:\\\\)*)%.*$", r"\1", line)


def _read_braced(text: str, pos: int) -> tuple[str | None, int]:
    """Read a balanced {...} group starting at pos (skipping leading whitespace)."""
    n = len(text)
    while pos < n and text[pos].isspace():
        pos += 1
    if pos >= n or text[pos] != "{":
        return None, pos
    depth = 0
    start = pos + 1
    i = pos
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i], i + 1
        i += 1
    return text[start:], n


def _skip_optional_bracket(text: str, pos: int) -> int:
    """Skip an optional [...] argument starting at pos."""
    n = len(text)
    while pos < n and text[pos].isspace():
        pos += 1
    if pos >= n or text[pos] != "[":
        return pos
    depth = 0
    i = pos
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _extract_tex_sections_and_inputs(
    uncommented: str,
) -> tuple[list[str], list[str]]:
    """Find section headings and \\input/\\include paths on a single LaTeX line."""
    sections: list[str] = []
    inputs: list[str] = []
    for m in re.finditer(r"\\(chapter|section|subsection|input|include)(\*?)", uncommented):
        cmd = m.group(1)
        pos = m.end()
        if cmd in _TEX_SECTION_CMDS:
            pos = _skip_optional_bracket(uncommented, pos)
            arg, _ = _read_braced(uncommented, pos)
            if arg is not None:
                clean_title = _clean_tex_inline(arg)
                if clean_title:
                    sections.append(clean_title)
        elif cmd in ("input", "include"):
            arg, _ = _read_braced(uncommented, pos)
            if arg is not None and arg.strip():
                inputs.append(arg.strip())
    return sections, inputs


def _clean_tex_inline(text: str) -> str:
    """Clean LaTeX commands and inline math from a single line or title."""
    # Remove inline math \( ... \) and $ ... $
    text = re.sub(r"\\\(.*?\\\)", " ", text)
    text = re.sub(r"\$\$.*?\$\$", " ", text)
    text = re.sub(r"(?<!\\)\$[^$]*?(?<!\\)\$", " ", text)

    # Remove \begin{env}[opt]{arg} and \end{env} tags
    text = re.sub(
        r"\\begin\{[^}]*\}(?:\[[^\]]*\])?(?:\{[^}]*\})?",
        " ",
        text,
    )
    text = re.sub(r"\\end\{[^}]*\}", " ", text)

    # Iteratively handle structured commands (commands with balanced braces)
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\\" and i + 1 < n and text[i + 1].isalpha():
            m = re.match(r"\\([a-zA-Z]+)(\*?)", text[i:])
            if m:
                cmd = m.group(1)
                after = i + len(m.group(0))

                if cmd in _TEX_SECTION_CMDS:
                    after = _skip_optional_bracket(text, after)
                    arg, end_pos = _read_braced(text, after)
                    if arg is not None:
                        i = end_pos
                        continue

                if cmd in ("href", "textcolor"):
                    after = _skip_optional_bracket(text, after)
                    _, pos_after_first = _read_braced(text, after)
                    inner_text, end_pos = _read_braced(text, pos_after_first)
                    if inner_text is not None:
                        out.append(" ")
                        out.append(_clean_tex_inline(inner_text))
                        out.append(" ")
                        i = end_pos
                        continue

                if cmd in ("fontsize",):
                    _, pos_after_first = _read_braced(text, after)
                    _, end_pos = _read_braced(text, pos_after_first)
                    i = end_pos
                    continue

                if cmd == "addcontentsline":
                    _, pos1 = _read_braced(text, after)
                    _, pos2 = _read_braced(text, pos1)
                    _, end_pos = _read_braced(text, pos2)
                    i = end_pos
                    continue

                if cmd in ("SI", "qty"):
                    after = _skip_optional_bracket(text, after)
                    val, pos_after_val = _read_braced(text, after)
                    unit_arg, end_pos = _read_braced(text, pos_after_val)
                    if val is not None:
                        out.append(" ")
                        out.append(_clean_tex_inline(val))
                        if unit_arg is not None:
                            out.append(" ")
                            out.append(_render_si_unit(unit_arg))
                        out.append(" ")
                        i = end_pos
                        continue

                if cmd in _TEX_DROP_ARG_CMDS:
                    after = _skip_optional_bracket(text, after)
                    arg, end_pos = _read_braced(text, after)
                    if arg is not None:
                        i = end_pos
                        continue
                    i = after
                    continue

                if cmd in _TEX_UNWRAP_CMDS:
                    after = _skip_optional_bracket(text, after)
                    arg, end_pos = _read_braced(text, after)
                    if arg is not None:
                        out.append(" ")
                        out.append(_clean_tex_inline(arg))
                        out.append(" ")
                        i = end_pos
                        continue
                    i = after
                    continue

                if cmd == "item":
                    after = _skip_optional_bracket(text, after)
                    out.append(" ")
                    i = after
                    continue

                # Any other \command: strip command name (leave braced content if any)
                after = _skip_optional_bracket(text, after)
                out.append(" ")
                i = after
                continue

        out.append(text[i])
        i += 1

    cleaned = "".join(out)
    # Escaped characters & LaTeX punctuation
    cleaned = cleaned.replace(r"\%", "%")
    cleaned = cleaned.replace(r"\&", "&")
    cleaned = cleaned.replace(r"\$", "$")
    cleaned = cleaned.replace(r"\#", "#")
    cleaned = cleaned.replace(r"\_", "_")
    cleaned = cleaned.replace(r"\\", " ")
    cleaned = re.sub(r"\\[,;:!\s]", " ", cleaned)
    cleaned = cleaned.replace("~", " ")
    cleaned = cleaned.replace("``", '"').replace("''", '"')
    cleaned = cleaned.replace("---", " — ").replace("--", " – ")
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    # Remove empty parens/brackets left after citation stripping, e.g. "()" or "[]"
    cleaned = re.sub(r"\(\s*\)|\[\s*\]", " ", cleaned)
    return _normalize_ws(cleaned)


def _resolve_tex_include(base_file: str, rel_target: str) -> str | None:
    base_dir = os.path.dirname(os.path.abspath(base_file))
    candidates = [os.path.join(base_dir, rel_target)]
    if not os.path.splitext(rel_target)[1]:
        candidates.append(os.path.join(base_dir, rel_target + ".tex"))
    for cand in candidates:
        if os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


def _parse_tex_file(
    file_path: str,
    recursive: bool,
    include_references: bool,
) -> ParsedDocument:
    abs_root = os.path.abspath(file_path)
    files: list[str] = []
    lines: list[LineRecord] = []
    visited: set[str] = set()
    section_starts: list[tuple[str, str, int, int]] = []
    state = {"section": "Document", "in_ref_section": False}

    strip_envs = set(_TEX_STRIP_ENVS)
    if not include_references:
        strip_envs.add("thebibliography")

    def ensure_section_started(sec_file: str, loc: int) -> None:
        if not section_starts:
            section_starts.append((state["section"], sec_file, loc, len(lines)))

    def process_file(current_path: str, is_root: bool) -> None:
        real = os.path.realpath(current_path)
        if real in visited:
            return
        visited.add(real)
        files.append(current_path)

        with open(current_path, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = f.readlines()

        # Check if this file has a \begin{document} (outside comments)
        has_begin_doc = False
        for rl in raw_lines:
            if r"\begin{document}" in _strip_tex_comments(rl):
                has_begin_doc = True
                break

        in_body = not has_begin_doc
        ended = False
        env_stack: list[str] = []
        in_dollar_math = False
        in_bracket_math = False

        for idx, raw_line in enumerate(raw_lines, start=1):
            raw_no_nl = raw_line.rstrip("\r\n")
            if ended:
                lines.append(
                    LineRecord(
                        file=current_path,
                        loc=idx,
                        loc_label="line",
                        section=state["section"],
                        raw_text=raw_no_nl,
                        clean_text="",
                    )
                )
                continue

            uncommented = _strip_tex_comments(raw_no_nl)

            if not in_body:
                m_begin = re.search(r"\\begin\{document\}", uncommented)
                if m_begin:
                    in_body = True
                    uncommented = uncommented[m_begin.end() :]
                else:
                    lines.append(
                        LineRecord(
                            file=current_path,
                            loc=idx,
                            loc_label="line",
                            section="Preamble" if is_root else state["section"],
                            raw_text=raw_no_nl,
                            clean_text="",
                        )
                    )
                    continue

            m_end_doc = re.search(r"\\end\{document\}", uncommented)
            if m_end_doc:
                ended = True
                uncommented = uncommented[: m_end_doc.start()]

            # Handle multi-line skip environments
            active_text = uncommented
            if env_stack:
                # Check if top environment closes on this line
                top_env = env_stack[-1]
                end_pat = re.compile(rf"\\end\{{{re.escape(top_env)}\}}")
                m_close = end_pat.search(active_text)
                while m_close and _has_odd_preceding_backslashes(active_text, m_close.start()):
                    m_close = end_pat.search(active_text, m_close.end())
                if m_close:
                    env_stack.pop()
                    active_text = active_text[m_close.end() :]
                    if env_stack:
                        active_text = ""
                else:
                    active_text = ""

            # Process new skip environments opening (and possibly closing) on this line
            if active_text:
                cleaned_parts: list[str] = []
                pos = 0
                while pos < len(active_text):
                    if in_dollar_math:
                        close_idx = active_text.find("$$", pos)
                        while close_idx != -1 and _has_odd_preceding_backslashes(active_text, close_idx):
                            close_idx = active_text.find("$$", close_idx + 2)
                        if close_idx == -1:
                            pos = len(active_text)
                            break
                        in_dollar_math = False
                        pos = close_idx + 2
                        continue

                    if in_bracket_math:
                        close_idx = active_text.find(r"\]", pos)
                        while close_idx != -1 and _has_odd_preceding_backslashes(active_text, close_idx):
                            close_idx = active_text.find(r"\]", close_idx + 2)
                        if close_idx == -1:
                            pos = len(active_text)
                            break
                        in_bracket_math = False
                        pos = close_idx + 2
                        continue

                    # Look for next $$, \[, or \begin{skip_env}
                    m_next = re.search(r"\$\$|\\\[|\\begin\{([^}]+)\}", active_text[pos:])
                    if not m_next:
                        cleaned_parts.append(active_text[pos:])
                        break

                    match_start = pos + m_next.start()
                    abs_end = pos + m_next.end()
                    token = m_next.group(0)

                    # Ignore escaped \$$ or \\[optional] linebreak spacing (where \ is second slash of \\)
                    if _has_odd_preceding_backslashes(active_text, match_start):
                        cleaned_parts.append(active_text[pos:abs_end])
                        pos = abs_end
                        continue

                    cleaned_parts.append(active_text[pos:match_start])

                    if token == "$$":
                        in_dollar_math = True
                        pos = abs_end
                    elif token == r"\[":
                        in_bracket_math = True
                        pos = abs_end
                    else:
                        env_name = m_next.group(1).strip()
                        if env_name in strip_envs:
                            end_pat = re.compile(rf"\\end\{{{re.escape(env_name)}\}}")
                            m_close = end_pat.search(active_text, abs_end)
                            while m_close and _has_odd_preceding_backslashes(active_text, m_close.start()):
                                m_close = end_pat.search(active_text, m_close.end())
                            if m_close:
                                pos = m_close.end()
                            else:
                                env_stack.append(env_name)
                                pos = len(active_text)
                                break
                        else:
                            cleaned_parts.append(token)
                            pos = abs_end

                active_text = "".join(cleaned_parts)

            # Update sections and collect \input / \include
            new_sections, include_targets = _extract_tex_sections_and_inputs(active_text)
            for title in new_sections:
                state["section"] = title
                state["in_ref_section"] = (not include_references) and _is_reference_title(title)
                section_starts.append((title, current_path, idx, len(lines)))

            ensure_section_started(current_path, idx)

            clean_text = "" if state["in_ref_section"] else _clean_tex_inline(active_text)
            lines.append(
                LineRecord(
                    file=current_path,
                    loc=idx,
                    loc_label="line",
                    section=state["section"],
                    raw_text=raw_no_nl,
                    clean_text=clean_text,
                )
            )

            if recursive and include_targets:
                for inc in include_targets:
                    resolved = _resolve_tex_include(current_path, inc)
                    if resolved is not None:
                        process_file(resolved, is_root=False)

    process_file(abs_root, is_root=True)
    sections = _finalize_sections(lines, section_starts)
    full_clean = "\n\n".join(sec.text for sec in sections)
    return ParsedDocument(
        source_path=abs_root,
        files=files,
        loc_label="line",
        lines=lines,
        sections=sections,
        full_clean_text=full_clean,
    )


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------


def _clean_md_inline(text: str) -> str:
    # Remove HTML comments and inline code
    text = re.sub(r"<!--.*?-->", " ", text)
    text = re.sub(r"`[^`]+`", " ", text)
    # Remove inline math $...$
    text = re.sub(r"(?<!\\)\$[^$\n]+?(?<!\\)\$", " ", text)
    # Strip Obsidian embeds ![[...]] and Markdown images ![alt](url)
    text = re.sub(r"!\[\[[^\]]*\]\]", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    # Convert Obsidian wikilinks [[target|alias]] -> alias, [[target]] -> target
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # Convert Markdown links [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Strip blockquote / list prefixes and emphasis markers
    text = re.sub(r"^\s*(?:>\s*)+", "", text)
    text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", text)
    text = re.sub(r"[*_~]{1,3}", "", text)
    return _normalize_ws(text)


def _parse_md_file(file_path: str, include_references: bool) -> ParsedDocument:
    abs_path = os.path.abspath(file_path)
    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_lines = f.readlines()

    lines: list[LineRecord] = []
    section_starts: list[tuple[str, str, int, int]] = []
    current_section = "Document"
    in_ref_section = False

    # Detect YAML frontmatter at top of file
    frontmatter_end = -1
    if raw_lines and raw_lines[0].strip() == "---":
        for idx in range(1, len(raw_lines)):
            if raw_lines[idx].strip() in ("---", "..."):
                frontmatter_end = idx
                break

    in_code_fence = False
    fence_char = ""
    in_math_block = False

    for idx, raw_line in enumerate(raw_lines, start=1):
        raw_no_nl = raw_line.rstrip("\r\n")
        stripped = raw_no_nl.strip()

        if idx - 1 <= frontmatter_end:
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=idx,
                    loc_label="line",
                    section=current_section,
                    raw_text=raw_no_nl,
                    clean_text="",
                )
            )
            continue

        if not section_starts:
            section_starts.append((current_section, abs_path, idx, len(lines)))

        # Fenced code blocks
        m_fence = re.match(r"^(```+|~~~+)", stripped)
        if m_fence:
            marker_char = m_fence.group(1)[0]
            if not in_code_fence:
                in_code_fence = True
                fence_char = marker_char
            elif marker_char == fence_char:
                in_code_fence = False
                fence_char = ""
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=idx,
                    loc_label="line",
                    section=current_section,
                    raw_text=raw_no_nl,
                    clean_text="",
                )
            )
            continue

        if in_code_fence:
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=idx,
                    loc_label="line",
                    section=current_section,
                    raw_text=raw_no_nl,
                    clean_text="",
                )
            )
            continue

        # Multi-line $$ math blocks
        if stripped.startswith("$$"):
            if stripped == "$$" or not stripped.endswith("$$") or len(stripped) == 2:
                in_math_block = not in_math_block
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=idx,
                    loc_label="line",
                    section=current_section,
                    raw_text=raw_no_nl,
                    clean_text="",
                )
            )
            continue

        if in_math_block:
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=idx,
                    loc_label="line",
                    section=current_section,
                    raw_text=raw_no_nl,
                    clean_text="",
                )
            )
            continue

        # Horizontal rules
        if re.match(r"^\s*[-*_]{3,}\s*$", raw_no_nl):
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=idx,
                    loc_label="line",
                    section=current_section,
                    raw_text=raw_no_nl,
                    clean_text="",
                )
            )
            continue

        # Markdown headings
        m_head = re.match(r"^\s*(#{1,6})\s+(.+?)\s*#*\s*$", raw_no_nl)
        if m_head:
            title = _clean_md_inline(m_head.group(2))
            if title:
                current_section = title
                in_ref_section = (not include_references) and _is_reference_title(title)
                section_starts.append((current_section, abs_path, idx, len(lines)))
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=idx,
                    loc_label="line",
                    section=current_section,
                    raw_text=raw_no_nl,
                    clean_text="",
                )
            )
            continue

        clean_text = "" if in_ref_section else _clean_md_inline(raw_no_nl)
        lines.append(
            LineRecord(
                file=abs_path,
                loc=idx,
                loc_label="line",
                section=current_section,
                raw_text=raw_no_nl,
                clean_text=clean_text,
            )
        )

    sections = _finalize_sections(lines, section_starts)
    full_clean = "\n\n".join(sec.text for sec in sections)
    return ParsedDocument(
        source_path=abs_path,
        files=[abs_path],
        loc_label="line",
        lines=lines,
        sections=sections,
        full_clean_text=full_clean,
    )


# ---------------------------------------------------------------------------
# PDF parser
# ---------------------------------------------------------------------------

_PDF_PAGE_NUM_RE = re.compile(
    r"^\s*(?:[-–—]?\s*\d{1,4}\s*[-–—]?|[Pp]age\s+\d+(?:\s+of\s+\d+)?|[Pp]ág\.?\s+\d+)\s*$"
)
_PDF_REF_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+)?(?:References|Bibliography|Referências(?:\s+Bibliográficas)?|Bibliografia)\s*$",
    re.IGNORECASE,
)
_PDF_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\.?\s+[A-ZÀ-Ý][^\n]{2,60}|"
    r"Abstract|Resumo|Introduction|Introdução|Methodology|Metodologia|"
    r"Results|Resultados|Discussion|Discussão|Conclusion|Conclusions|Conclusão|Conclusões)\s*$"
)


def _parse_pdf_file(file_path: str, include_references: bool) -> ParsedDocument:
    if pypdf is None:
        raise RuntimeError(
            "pypdf is required to parse PDF files. "
            "Install it via: pip install 'scholar-kit[pdf]' (or pip install pypdf)."
        )

    abs_path = os.path.abspath(file_path)
    reader = pypdf.PdfReader(abs_path)

    lines: list[LineRecord] = []
    section_starts: list[tuple[str, str, int, int]] = []
    current_section = "Document"
    truncated_at_refs = False

    for page_num, page in enumerate(reader.pages, start=1):
        raw_page = page.extract_text() or ""
        # De-hyphenate line breaks within page
        dehyphenated = re.sub(
            r"([A-Za-zÀ-ÿ])-\s*\n\s*([A-Za-zÀ-ÿ])",
            r"\1\2",
            raw_page,
        )
        for raw_line in dehyphenated.splitlines():
            raw_no_nl = raw_line.rstrip("\r\n")
            if not section_starts:
                section_starts.append((current_section, abs_path, page_num, len(lines)))

            if truncated_at_refs:
                lines.append(
                    LineRecord(
                        file=abs_path,
                        loc=page_num,
                        loc_label="page",
                        section=current_section,
                        raw_text=raw_no_nl,
                        clean_text="",
                    )
                )
                continue

            stripped = raw_no_nl.strip()
            if not include_references and _PDF_REF_HEADING_RE.match(stripped):
                truncated_at_refs = True
                lines.append(
                    LineRecord(
                        file=abs_path,
                        loc=page_num,
                        loc_label="page",
                        section=current_section,
                        raw_text=raw_no_nl,
                        clean_text="",
                    )
                )
                continue

            if _PDF_PAGE_NUM_RE.match(stripped):
                lines.append(
                    LineRecord(
                        file=abs_path,
                        loc=page_num,
                        loc_label="page",
                        section=current_section,
                        raw_text=raw_no_nl,
                        clean_text="",
                    )
                )
                continue

            if (
                _PDF_HEADING_RE.match(stripped)
                and not stripped.endswith((".", ",", ";", ":"))
            ):
                current_section = _normalize_ws(stripped)
                section_starts.append((current_section, abs_path, page_num, len(lines)))
                lines.append(
                    LineRecord(
                        file=abs_path,
                        loc=page_num,
                        loc_label="page",
                        section=current_section,
                        raw_text=raw_no_nl,
                        clean_text="",
                    )
                )
                continue

            # Strip numeric bracket citations [1], [1, 2], [1-3]
            cleaned = re.sub(r"\[\s*\d+(?:\s*[-–,;]\s*\d+)*\s*\]", " ", raw_no_nl)
            cleaned = _normalize_ws(cleaned)
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=page_num,
                    loc_label="page",
                    section=current_section,
                    raw_text=raw_no_nl,
                    clean_text=cleaned,
                )
            )

    sections = _finalize_sections(lines, section_starts)
    full_clean = "\n\n".join(sec.text for sec in sections)
    return ParsedDocument(
        source_path=abs_path,
        files=[abs_path],
        loc_label="page",
        lines=lines,
        sections=sections,
        full_clean_text=full_clean,
    )


# ---------------------------------------------------------------------------
# DOCX parser
# ---------------------------------------------------------------------------


def _docx_paragraph_text(p_elem: ET.Element) -> str:
    parts: list[str] = []
    for elem in p_elem.iter():
        tag = elem.tag
        if tag == f"{{{_W_NS}}}t" and elem.text:
            parts.append(elem.text)
        elif tag in (f"{{{_W_NS}}}tab", f"{{{_W_NS}}}br"):
            parts.append(" ")
    return "".join(parts)


def _docx_paragraph_style(p_elem: ET.Element) -> str:
    ppr = p_elem.find(f"{{{_W_NS}}}pPr")
    if ppr is None:
        return ""
    pstyle = ppr.find(f"{{{_W_NS}}}pStyle")
    if pstyle is None:
        return ""
    return pstyle.attrib.get(f"{{{_W_NS}}}val", "")


def _parse_docx_file(file_path: str, include_references: bool) -> ParsedDocument:
    abs_path = os.path.abspath(file_path)
    with zipfile.ZipFile(abs_path, "r") as zf:
        if "word/document.xml" not in zf.namelist():
            raise ValueError(f"Invalid .docx archive (missing word/document.xml): {abs_path}")
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    body = root.find(f"{{{_W_NS}}}body")
    paragraphs = body.findall(f"{{{_W_NS}}}p") if body is not None else root.findall(f".//{{{_W_NS}}}p")

    lines: list[LineRecord] = []
    section_starts: list[tuple[str, str, int, int]] = []
    current_section = "Document"
    in_ref_section = False

    for idx, p_elem in enumerate(paragraphs, start=1):
        raw_text = _docx_paragraph_text(p_elem)
        style = _docx_paragraph_style(p_elem).strip().lower().replace(" ", "")

        if not section_starts:
            section_starts.append((current_section, abs_path, idx, len(lines)))

        if style in ("heading1", "heading2", "título1", "título2", "titulo1", "titulo2"):
            heading_title = _normalize_ws(raw_text)
            if heading_title:
                current_section = heading_title
                in_ref_section = (not include_references) and _is_reference_title(heading_title)
                section_starts.append((current_section, abs_path, idx, len(lines)))
            lines.append(
                LineRecord(
                    file=abs_path,
                    loc=idx,
                    loc_label="paragraph",
                    section=current_section,
                    raw_text=raw_text,
                    clean_text="",
                )
            )
            continue

        clean_text = "" if in_ref_section else _normalize_ws(raw_text)
        lines.append(
            LineRecord(
                file=abs_path,
                loc=idx,
                loc_label="paragraph",
                section=current_section,
                raw_text=raw_text,
                clean_text=clean_text,
            )
        )

    sections = _finalize_sections(lines, section_starts)
    full_clean = "\n\n".join(sec.text for sec in sections)
    return ParsedDocument(
        source_path=abs_path,
        files=[abs_path],
        loc_label="paragraph",
        lines=lines,
        sections=sections,
        full_clean_text=full_clean,
    )


# ---------------------------------------------------------------------------
# Plain text parser
# ---------------------------------------------------------------------------


def _parse_txt_file(file_path: str) -> ParsedDocument:
    abs_path = os.path.abspath(file_path)
    with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_lines = f.readlines()

    lines: list[LineRecord] = []
    for idx, raw_line in enumerate(raw_lines, start=1):
        raw_no_nl = raw_line.rstrip("\r\n")
        lines.append(
            LineRecord(
                file=abs_path,
                loc=idx,
                loc_label="line",
                section="Document",
                raw_text=raw_no_nl,
                clean_text=_normalize_ws(raw_no_nl),
            )
        )

    section_starts = [("Document", abs_path, 1, 0)] if lines else []
    sections = _finalize_sections(lines, section_starts)
    full_clean = "\n\n".join(sec.text for sec in sections)
    return ParsedDocument(
        source_path=abs_path,
        files=[abs_path],
        loc_label="line",
        lines=lines,
        sections=sections,
        full_clean_text=full_clean,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _parse_single_file(
    file_path: str,
    recursive: bool,
    include_references: bool,
) -> ParsedDocument:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".tex", ".latex"):
        return _parse_tex_file(file_path, recursive=recursive, include_references=include_references)
    if ext == ".pdf":
        return _parse_pdf_file(file_path, include_references=include_references)
    if ext in (".md", ".markdown"):
        return _parse_md_file(file_path, include_references=include_references)
    if ext == ".docx":
        return _parse_docx_file(file_path, include_references=include_references)
    if ext == ".txt":
        return _parse_txt_file(file_path)
    raise ValueError(f"Unsupported file format: {ext!r} ({file_path})")


def _collect_directory_files(dir_path: str, recursive: bool) -> list[str]:
    collected: list[str] = []
    if recursive:
        for root, dirs, filenames in os.walk(dir_path):
            dirs[:] = sorted(
                d for d in dirs if d not in _SKIP_DIRS and not d.endswith(".egg-info")
            )
            for fname in sorted(filenames):
                ext = os.path.splitext(fname)[1].lower()
                if ext in SUPPORTED_EXTENSIONS:
                    collected.append(os.path.abspath(os.path.join(root, fname)))
    else:
        for fname in sorted(os.listdir(dir_path)):
            full = os.path.join(dir_path, fname)
            if os.path.isfile(full) and os.path.splitext(fname)[1].lower() in SUPPORTED_EXTENSIONS:
                collected.append(os.path.abspath(full))
    return collected


def _has_begin_document(tex_path: str) -> bool:
    try:
        with open(tex_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if r"\begin{document}" in _strip_tex_comments(line):
                    return True
    except OSError:
        return False
    return False


def parse_path(
    target: str,
    recursive: bool = True,
    include_references: bool = False,
) -> list[ParsedDocument]:
    """Parse a file or directory into normalized ParsedDocument objects."""
    if not os.path.exists(target):
        raise FileNotFoundError(f"Path not found: {target}")

    if os.path.isfile(target):
        return [_parse_single_file(target, recursive=recursive, include_references=include_references)]

    candidates = _collect_directory_files(target, recursive=recursive)
    if not candidates:
        return []

    # Parse root .tex documents (containing \begin{document}) first when recursive=True
    # so \input/\include child files aren't duplicated as standalone documents.
    tex_files = [p for p in candidates if os.path.splitext(p)[1].lower() in (".tex", ".latex")]
    root_tex = [p for p in tex_files if _has_begin_document(p)]

    docs_by_path: dict[str, ParsedDocument] = {}
    included_tex_reals: set[str] = set()

    if recursive and root_tex:
        for p in root_tex:
            doc = _parse_single_file(p, recursive=True, include_references=include_references)
            docs_by_path[p] = doc
            for included in doc.files[1:]:
                included_tex_reals.add(os.path.realpath(included))

    for p in candidates:
        if p in docs_by_path:
            continue
        if os.path.realpath(p) in included_tex_reals:
            continue
        docs_by_path[p] = _parse_single_file(
            p, recursive=recursive, include_references=include_references
        )

    return [docs_by_path[p] for p in candidates if p in docs_by_path]
