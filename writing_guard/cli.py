"""CLI entrypoints for `writecheck` and `scholar-kit`."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .language import detect_language
from .models import Finding, ParsedDocument, ReadabilityReport
from .parser import parse_path
from .pt_guard import add_to_whitelist, check_pt_document, load_whitelist
from .readability import analyze_readability
from .reporter import format_json_report, format_markdown_report, format_terminal_report
from .style_adpe import check_adpe_style


def build_check_parser(prog: str = "writecheck") -> argparse.ArgumentParser:
    """Create the argument parser for `writecheck` / `scholar-kit check`."""
    parser = argparse.ArgumentParser(
        prog=prog,
        description=(
            "Zero-token bilingual (EN / pt-PT) readability, ADPE scientific style, "
            "and Portuguese spelling checker."
        ),
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Path to a .tex, .pdf, .md, .docx, .txt file or directory to check.",
    )
    parser.add_argument(
        "--lang",
        choices=["auto", "en", "pt"],
        default="auto",
        help="Document language ('auto', 'en', or 'pt'). Default: auto.",
    )
    parser.add_argument(
        "--mode",
        choices=["all", "readability", "style", "spelling"],
        default="all",
        help="Checks to run ('all', 'readability', 'style', or 'spelling'). Default: all.",
    )
    parser.add_argument(
        "--sections",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include per-section readability breakdown (default: enabled).",
    )
    parser.add_argument(
        "--top-sentences",
        type=int,
        default=5,
        help="Number of hardest sentences to list (default: 5).",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        default=False,
        help="Do not follow LaTeX \\input/\\include or traverse directories recursively.",
    )
    parser.add_argument(
        "--include-references",
        action="store_true",
        default=False,
        help="Include bibliography / references sections in the analysis.",
    )
    parser.add_argument(
        "--strict-impersonal",
        action="store_true",
        default=False,
        help="Flag first-person pronouns (I, we, our, eu, nós, nosso) outside Intro/Conclusions.",
    )
    output_fmt = parser.add_mutually_exclusive_group()
    output_fmt.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON report.",
    )
    output_fmt.add_argument(
        "--markdown",
        action="store_true",
        dest="markdown_output",
        help="Emit GitHub-flavored Markdown report.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write the report to this file path instead of stdout.",
    )
    parser.add_argument(
        "--min-ease",
        type=float,
        default=None,
        help="Exit non-zero if overall Flesch Reading Ease is below this value.",
    )
    parser.add_argument(
        "--max-grade",
        type=float,
        default=None,
        help="Exit non-zero if overall Flesch-Kincaid Grade Level exceeds this value.",
    )
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        default=False,
        help="Exit non-zero if any style or spelling findings are reported.",
    )
    parser.add_argument(
        "--whitelist-add",
        type=str,
        default=None,
        help="Add an approved term to writing_guard/whitelist.txt.",
    )
    return parser


def _resolve_lang(docs: list[ParsedDocument], requested_lang: str) -> str:
    if requested_lang in ("en", "pt"):
        return requested_lang
    combined = "\n".join(doc.full_clean_text for doc in docs if doc.full_clean_text)
    return detect_language(combined)


def _evaluate_gates(
    *,
    readability: ReadabilityReport | None,
    findings: list[Finding],
    min_ease: float | None,
    max_grade: float | None,
    fail_on_issues: bool,
) -> list[str]:
    failures: list[str] = []
    if readability is not None:
        if min_ease is not None and readability.overall.flesch_reading_ease < min_ease:
            failures.append(
                f"Flesch Reading Ease {readability.overall.flesch_reading_ease:.1f} "
                f"is below --min-ease {min_ease:.1f}"
            )
        if max_grade is not None and readability.overall.flesch_kincaid_grade > max_grade:
            failures.append(
                f"Flesch-Kincaid Grade {readability.overall.flesch_kincaid_grade:.1f} "
                f"exceeds --max-grade {max_grade:.1f}"
            )
    if fail_on_issues and findings:
        failures.append(f"{len(findings)} style/spelling finding(s) reported (--fail-on-issues)")
    return failures


def run_check_args(args: argparse.Namespace) -> int:
    """Execute a parsed `writecheck` / `scholar-kit check` invocation."""
    if args.whitelist_add:
        wl_path = add_to_whitelist(args.whitelist_add)
        if not args.target:
            if args.json_output:
                print(json.dumps({"whitelist_added": args.whitelist_add, "path": wl_path}))
            else:
                print(f"Added '{args.whitelist_add.strip()}' to whitelist: {wl_path}")
            return 0

    if not args.target:
        print("Error: target path is required unless using --whitelist-add.", file=sys.stderr)
        return 2

    try:
        docs = parse_path(
            args.target,
            recursive=not args.no_recursive,
            include_references=args.include_references,
        )
    except (FileNotFoundError, ImportError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    resolved_lang = _resolve_lang(docs, args.lang)
    whitelist = load_whitelist()

    readability: ReadabilityReport | None = None
    if args.mode in ("all", "readability"):
        readability = analyze_readability(
            docs,
            lang=resolved_lang,
            top_sentences=max(0, args.top_sentences),
        )

    findings: list[Finding] = []
    if args.mode in ("all", "style"):
        findings.extend(
            check_adpe_style(
                docs,
                lang=resolved_lang,
                strict_impersonal=args.strict_impersonal,
                whitelist=whitelist,
            )
        )
    if args.mode in ("all", "spelling") and resolved_lang == "pt":
        findings.extend(check_pt_document(docs))

    gate_failures = _evaluate_gates(
        readability=readability,
        findings=findings,
        min_ease=args.min_ease,
        max_grade=args.max_grade,
        fail_on_issues=args.fail_on_issues,
    )

    if args.json_output:
        rendered = format_json_report(
            target=args.target,
            lang=resolved_lang,
            mode=args.mode,
            docs=docs,
            readability=readability,
            findings=findings,
            show_sections=args.sections,
            gate_failures=gate_failures,
        )
    elif args.markdown_output:
        rendered = format_markdown_report(
            target=args.target,
            lang=resolved_lang,
            mode=args.mode,
            docs=docs,
            readability=readability,
            findings=findings,
            show_sections=args.sections,
            gate_failures=gate_failures,
        )
    else:
        rendered = format_terminal_report(
            target=args.target,
            lang=resolved_lang,
            mode=args.mode,
            docs=docs,
            readability=readability,
            findings=findings,
            show_sections=args.sections,
            gate_failures=gate_failures,
        )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Report written to {out_path}")
    else:
        print(rendered)

    return 1 if gate_failures else 0


def main(argv: list[str] | None = None) -> int:
    """Entrypoint for `writecheck` and `python -m writing_guard`."""
    parser = build_check_parser(prog="writecheck")
    args = parser.parse_args(argv)
    if not args.target and not args.whitelist_add:
        parser.print_help(sys.stderr)
        return 2
    return run_check_args(args)


def _print_scholar_kit_help() -> None:
    print(
        """scholar-kit: Bilingual scientific writing guard & Obsidian vault toolkit

Usage:
  scholar-kit check <target> [options]   Run readability, ADPE style, and pt-PT checks
  scholar-kit vault <command> [args]     Run Obsidian vault automation (uni_vault/uni.py)

Examples:
  scholar-kit check paper.tex --strict-impersonal --min-ease 35
  scholar-kit check report.md --lang pt --markdown --output report.md
  scholar-kit vault watch ppfm
  scholar-kit vault organize --dry-run

Run `scholar-kit check --help` or `scholar-kit vault --help` for subcommand details."""
    )


def scholar_kit_main(argv: list[str] | None = None) -> int:
    """Entrypoint for `scholar-kit` unified CLI."""
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0] in ("-h", "--help", "help"):
        _print_scholar_kit_help()
        return 0

    subcmd = args_list[0]
    rest = args_list[1:]

    if subcmd == "check":
        parser = build_check_parser(prog="scholar-kit check")
        parsed = parser.parse_args(rest)
        if not parsed.target and not parsed.whitelist_add:
            parser.print_help(sys.stderr)
            return 2
        return run_check_args(parsed)

    if subcmd == "vault":
        repo_root = Path(__file__).resolve().parent.parent
        uni_py = repo_root / "uni_vault" / "uni.py"
        if not uni_py.exists():
            print(f"Error: uni_vault/uni.py not found at {uni_py}", file=sys.stderr)
            return 2
        res = subprocess.run([sys.executable, str(uni_py), *rest], check=False)
        return res.returncode

    print(f"Unknown subcommand: '{subcmd}'", file=sys.stderr)
    _print_scholar_kit_help()
    return 2
