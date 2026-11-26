"""Integration and unit tests for `writing_guard.cli` and `writing_guard.reporter`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from writing_guard import pt_guard
from writing_guard.cli import main, scholar_kit_main

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO_ROOT = Path(__file__).resolve().parent.parent


def test_cli_json_en_markdown_fixture(capsys):
    rc = main([str(FIXTURES / "sample_en.md"), "--lang", "auto", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["lang"] == "en"
    assert data["readability"]["overall"]["words"] > 50
    assert len(data["readability"]["sections"]) >= 3
    rule_ids = {f["rule_id"] for f in data["findings"]}
    assert "LONG_SENTENCE" in rule_ids
    assert "ITALIC_LATIN_ABBREV" in rule_ids
    assert "EN_PT_TRANSLATION_CALQUE" in rule_ids
    assert "UNDEFINED_ACRONYM" in rule_ids


def test_cli_json_pt_markdown_fixture(capsys):
    rc = main([str(FIXTURES / "sample_pt.md"), "--lang", "auto", "--json"])
    assert rc == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["lang"] == "pt"
    rule_ids = {f["rule_id"] for f in data["findings"]}
    assert "PT_AI_ISM" in rule_ids
    assert "PT_BR_LEXICON" in rule_ids
    assert "PT_GERUNDIO" in rule_ids


def test_cli_latex_recursive_and_no_recursive(capsys):
    rc_rec = main([str(FIXTURES / "sample_en.tex"), "--json"])
    assert rc_rec == 0
    rec_data = json.loads(capsys.readouterr().out)
    assert len(rec_data["files"]) == 2

    rc_norec = main([str(FIXTURES / "sample_en.tex"), "--no-recursive", "--json"])
    assert rc_norec == 0
    norec_data = json.loads(capsys.readouterr().out)
    assert len(norec_data["files"]) == 1


def test_cli_include_references_flag(capsys):
    rc_default = main([str(FIXTURES / "sample_en.tex"), "--json"])
    assert rc_default == 0
    d1 = json.loads(capsys.readouterr().out)

    rc_refs = main([str(FIXTURES / "sample_en.tex"), "--include-references", "--json"])
    assert rc_refs == 0
    d2 = json.loads(capsys.readouterr().out)
    assert d2["readability"]["overall"]["words"] >= d1["readability"]["overall"]["words"]


def test_cli_docx_and_markdown_output(capsys, tmp_path):
    out_md = tmp_path / "report.md"
    rc = main(
        [
            str(FIXTURES / "sample_en.docx"),
            "--markdown",
            "--output",
            str(out_md),
        ]
    )
    assert rc == 0
    stdout = capsys.readouterr().out
    assert "Report written to" in stdout
    content = out_md.read_text(encoding="utf-8")
    assert "# Writing Guard Report" in content
    assert "## Readability (ADPE Slide 18 & 19)" in content
    assert "## Findings" in content


def test_cli_no_sections_and_top_sentences(capsys):
    rc = main(
        [
            str(FIXTURES / "sample_en.md"),
            "--no-sections",
            "--top-sentences",
            "1",
            "--json",
        ]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["readability"]["sections"] == []
    assert len(data["readability"]["hardest_sentences"]) <= 1


def test_cli_modes_and_strict_impersonal(capsys, tmp_path):
    sample = tmp_path / "impersonal.md"
    sample.write_text(
        "# Methodology\nWe evaluated the pump controller in three scenarios.\n",
        encoding="utf-8",
    )
    rc_style = main([str(sample), "--lang", "en", "--mode", "style", "--strict-impersonal", "--json"])
    assert rc_style == 0
    data = json.loads(capsys.readouterr().out)
    assert data["readability"] is None
    assert any(f["rule_id"] == "FIRST_PERSON_CHECK" for f in data["findings"])

    rc_read = main([str(sample), "--lang", "en", "--mode", "readability", "--json"])
    assert rc_read == 0
    data_read = json.loads(capsys.readouterr().out)
    assert data_read["readability"] is not None
    assert data_read["findings"] == []


def test_cli_threshold_exit_codes(capsys, tmp_path):
    clean_doc = tmp_path / "clean.txt"
    clean_doc.write_text(
        "The cat sat on the mat. The sun is warm. Birds fly high.",
        encoding="utf-8",
    )
    assert main([str(clean_doc), "--lang", "en", "--fail-on-issues"]) == 0
    capsys.readouterr()

    assert main([str(FIXTURES / "sample_en.md"), "--min-ease", "95"]) == 1
    capsys.readouterr()

    assert main([str(FIXTURES / "sample_en.md"), "--max-grade", "2"]) == 1
    capsys.readouterr()

    assert main([str(FIXTURES / "sample_en.md"), "--fail-on-issues"]) == 1
    capsys.readouterr()


def test_cli_whitelist_add(monkeypatch, tmp_path, capsys):
    wl = tmp_path / "whitelist.txt"
    wl.write_text("CAD\n", encoding="utf-8")
    monkeypatch.setattr(pt_guard, "WHITELIST_FILE", str(wl))

    orig_add = pt_guard.add_to_whitelist
    monkeypatch.setattr(
        "writing_guard.cli.add_to_whitelist",
        lambda word: orig_add(word, whitelist_path=str(wl)),
    )

    rc = main(["--whitelist-add", "Polyflow"])
    assert rc == 0
    assert "Added 'Polyflow'" in capsys.readouterr().out
    assert "Polyflow" in wl.read_text(encoding="utf-8")


def test_scholar_kit_subcommands(capsys):
    assert scholar_kit_main(["--help"]) == 0
    assert "scholar-kit check" in capsys.readouterr().out

    rc_check = scholar_kit_main(["check", str(FIXTURES / "sample_pt.tex"), "--json"])
    assert rc_check == 0
    data = json.loads(capsys.readouterr().out)
    assert data["lang"] == "pt"

    rc_vault = scholar_kit_main(["vault", "--help"])
    assert rc_vault == 0

    rc_bad = scholar_kit_main(["nonexistent"])
    assert rc_bad == 2
    capsys.readouterr()


def test_python_m_writing_guard_subprocess():
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "writing_guard",
            str(FIXTURES / "sample_en.md"),
            "--lang",
            "en",
            "--json",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    assert data["lang"] == "en"
    assert data["readability"]["overall"]["words"] > 0
