"""Unit tests for the multi-format document parser."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from writing_guard.parser import parse_path


def _create_minimal_docx(path: Path) -> None:
    doc_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        "<w:p><w:pPr><w:pStyle w:val=\"Heading1\"/></w:pPr>"
        "<w:r><w:t>Introduction</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>First body paragraph in English.</w:t></w:r></w:p>"
        "<w:p><w:pPr><w:pStyle w:val=\"Heading2\"/></w:pPr>"
        "<w:r><w:t>Methods</w:t></w:r></w:p>"
        "<w:p><w:r><w:t>Second body paragraph with details.</w:t></w:r></w:p>"
        "</w:body>"
        "</w:document>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", doc_xml)


def test_parse_tex_with_input_cycle_and_stripping(tmp_path: Path) -> None:
    chap = tmp_path / "chapter1.tex"
    main = tmp_path / "main.tex"

    chap.write_text(
        r"""\section{Methodology}
We measured \textbf{temperature}~\cite{smith2024} as shown in \autoref{fig:1}.
% This is a comment with ignored text
\begin{equation}
E = m c^2
\end{equation}
\begin{tabular}{cc}
A & B \\
\end{tabular}
\input{main.tex}
The controller achieved \SI{95}{\percent} accuracy \href{https://example.com}{online}.
""",
        encoding="utf-8",
    )

    main.write_text(
        r"""\documentclass{article}
\usepackage{amsmath}
\begin{document}
\section{Introduction}
This work studies polymers ($T_g = 120^\circ$C).
\[
x = y + z
\]
\input{chapter1}
\begin{thebibliography}{9}
\bibitem{smith2024} Smith, 2024.
\end{thebibliography}
\end{document}
""",
        encoding="utf-8",
    )

    docs = parse_path(str(main), recursive=True)
    assert len(docs) == 1
    doc = docs[0]
    assert len(doc.files) == 2
    assert [s.title for s in doc.sections] == ["Introduction", "Methodology"]
    assert "documentclass" not in doc.full_clean_text
    assert "smith2024" not in doc.full_clean_text
    assert "m c^2" not in doc.full_clean_text
    assert "comment" not in doc.full_clean_text
    assert "online" in doc.full_clean_text
    assert "example.com" not in doc.full_clean_text
    assert any(r"\textbf{temperature}" in lr.raw_text for lr in doc.lines)

    # Non-recursive ignores \input
    docs_nonrec = parse_path(str(main), recursive=False)
    assert len(docs_nonrec[0].files) == 1
    assert [s.title for s in docs_nonrec[0].sections] == ["Introduction"]


def test_parse_markdown(tmp_path: Path) -> None:
    md_file = tmp_path / "note.md"
    md_file.write_text(
        """---
title: Test Note
tags: [ai]
---

# Introduction
See [[w40_dpe_note|this note]] and [the paper](https://example.org) with `inline_code` and $x^2$.
![[diagram.png]]

```python
print("ignored code block")
```

## Results
The experiment succeeded.

# References
Smith (2024) ignored by default.
""",
        encoding="utf-8",
    )

    doc = parse_path(str(md_file))[0]
    assert [s.title for s in doc.sections] == ["Introduction", "Results"]
    assert "Test Note" not in doc.full_clean_text
    assert "this note" in doc.full_clean_text
    assert "the paper" in doc.full_clean_text
    assert "inline_code" not in doc.full_clean_text
    assert "ignored code block" not in doc.full_clean_text
    assert "diagram.png" not in doc.full_clean_text
    assert "ignored by default" not in doc.full_clean_text

    doc_with_refs = parse_path(str(md_file), include_references=True)[0]
    assert "ignored by default" in doc_with_refs.full_clean_text


def test_parse_docx(tmp_path: Path) -> None:
    docx_path = tmp_path / "sample.docx"
    _create_minimal_docx(docx_path)

    doc = parse_path(str(docx_path))[0]
    assert doc.loc_label == "paragraph"
    assert [s.title for s in doc.sections] == ["Introduction", "Methods"]
    assert "First body paragraph in English." in doc.sections[0].text
    assert "Second body paragraph with details." in doc.sections[1].text


def test_parse_directory_skips_ignored_dirs_and_dedups_tex(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.txt").write_text("do not read", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "ignored.md").write_text("# Ignore", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("Plain text sentence.", encoding="utf-8")
    (tmp_path / "sub.tex").write_text("\\section{Sub}\nIncluded text.", encoding="utf-8")
    (tmp_path / "main.tex").write_text(
        "\\begin{document}\n\\section{Main}\nRoot text.\n\\input{sub.tex}\n\\end{document}\n",
        encoding="utf-8",
    )

    docs = parse_path(str(tmp_path), recursive=True)
    source_names = sorted(Path(d.source_path).name for d in docs)
    assert source_names == ["main.tex", "notes.txt"]


def test_parse_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_path(str(tmp_path / "does_not_exist.txt"))


def test_parse_pdf_missing_pypdf_raises_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import writing_guard.parser as parser_mod

    pdf_file = tmp_path / "dummy.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(parser_mod, "pypdf", None)

    with pytest.raises(RuntimeError):
        parse_path(str(pdf_file))


def test_tex_linebreak_spacing_and_figure_placement(tmp_path):
    """Ensure \\\\[0.3em] is not treated as display math and [htbp] / \\textcolor / \\SI clean cleanly."""
    sub = tmp_path / "sec.tex"
    sub.write_text(
        "\\section{Introdução}\n"
        "\\begin{figure}[htbp]\n"
        "\\centering\n"
        "\\caption{Protótipo com \\SI{5}{\\milli\\metre} de espessura.}\n"
        "\\end{figure}\n"
        "Texto \\textcolor{red}{importante} após a figura.\n",
        encoding="utf-8",
    )
    root = tmp_path / "main.tex"
    root.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "{\\bfseries Título}\\\\[0.3em]\n"
        "{\\bfseries Subtítulo}\\\\[1.5em]\n"
        "\\input{sec}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    docs = parse_path(str(root))
    assert len(docs) == 1
    doc = docs[0]
    assert len(doc.files) == 2
    assert "importante" in doc.full_clean_text
    assert "red" not in doc.full_clean_text
    assert "htbp" not in doc.full_clean_text
    assert "5 mm" in doc.full_clean_text

