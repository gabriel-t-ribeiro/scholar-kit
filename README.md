# scholar-kit

[![CI](https://github.com/gabriel-t-ribeiro/scholar-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/gabriel-t-ribeiro/scholar-kit/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Zero Core Dependencies](https://img.shields.io/badge/core%20dependencies-0-brightgreen.svg)](#installation)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A local-first, zero-token toolkit for academic writing quality (`writing_guard`) and university knowledge-base automation (`uni_vault`).**

`scholar-kit` helps researchers, MSc/PhD students, and AI-assisted writers produce clearer scientific documents without spending AI tokens or API credits. It parses full academic manuscripts (`.tex`, `.pdf`, `.md`, `.docx`, `.txt`, or directories) in under a second to measure **English & Portuguese readability**, catch **scientific-writing anti-patterns**, eliminate **LLM translation calques and `pt-BR` interference** in European Portuguese (`pt-PT`), and automate lecture-to-notes workflows in Obsidian.

---

## Table of Contents

- [What's Inside](#whats-inside)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [How `writing_guard` Works](#how-writing_guard-works)
  - [1. Academic Document Parsing & Noise Stripping](#1-academic-document-parsing--noise-stripping)
  - [2. Bilingual Readability & Hotspots (`EN` + `pt-PT`)](#2-bilingual-readability--hotspots-en--pt-pt)
  - [3. ADPE Scientific Style & Portuguese Guard Rules](#3-adpe-scientific-style--portuguese-guard-rules)
- [Common Workflows & Recipes](#common-workflows--recipes)
- [Sample Output](#sample-output)
- [CLI Reference (`writecheck` & `scholar-kit`)](#cli-reference-writecheck--scholar-kit)
- [`uni_vault` — Obsidian University Workflow](#uni_vault--obsidian-university-workflow)
- [Project Structure](#project-structure)
- [CI & Development](#ci--development)
- [License](#license)

---

## What's Inside

`scholar-kit` is organized into two independent modules under one CLI (`scholar-kit`):

| Module | CLI Entrypoint | Purpose | Dependencies |
| :--- | :--- | :--- | :--- |
| **`writing_guard/`** | `writecheck` / `scholar-kit check` | Bilingual (`en` & `pt`) readability analyzer, ADPE style linter, and 2M+-inflection `pt-PT` spellcheck/AI-ism guard | **0 mandatory** (pure Python stdlib); optional `pypdf` + `cmudict` |
| **`uni_vault/`** | `scholar-kit vault` / `uni_vault/uni.py` | Real-time lecture watcher, Apple Silicon `mlx-whisper` transcription, slide extraction, vault hygiene, and Anki sync | Optional `[vault]` extra (macOS / Apple Silicon for local Whisper) |

---

## Installation

### 1. Zero-dependency core (works immediately on any Python 3.10+ environment)

```bash
git clone https://github.com/gabriel-t-ribeiro/scholar-kit.git
cd scholar-kit
pip install -e .
```

You can also run `writing_guard` without even installing the package:

```bash
python3 -m writing_guard path/to/paper.tex
```

### 2. Recommended writing setup (`.pdf` parsing + exact English `cmudict` syllables + dev tools)

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e ".[writing,dev]"
```

### 3. Optional dependency groups

| Extra | Packages | When to install |
| :--- | :--- | :--- |
| `[pdf]` | `pypdf>=6.0` | Inspecting compiled `.pdf` manuscripts (outputs page numbers) |
| `[en-exact]` | `cmudict>=1.0` | Upgrading English syllable counting from built-in heuristics to CMUdict (~99%+ accuracy) |
| `[writing]` | `pypdf>=6.0`, `cmudict>=1.0` | Full `writing_guard` capabilities |
| `[vault]` | `mlx-whisper`, `tqdm`, `matplotlib`, `python-dotenv`, `groq`, `google-genai` | Using `uni_vault` audio transcription & study automation |
| `[dev]` | `pytest>=8.0`, `ruff>=0.6` | Running the test suite and linter |

---

## Quick Start

```bash
# 1. Check a multi-file LaTeX thesis or report (auto-detects EN/PT & follows \input/\include)
writecheck main.tex

# 2. Check a Portuguese PDF or Markdown draft explicitly in PT mode
writecheck report.pdf --lang pt

# 3. Check a Word (.docx) document or a whole directory of chapters
writecheck chapters/ --top-sentences 10

# 4. Enforce readability & style gates in CI or pre-commit hooks
writecheck paper.tex --min-ease 30 --max-grade 15 --fail-on-issues

# 5. Export structured output for scripts or AI agents
writecheck draft.md --json --output review.json
writecheck draft.md --markdown --output review.md

# 6. Whitelist a domain-specific term or acronym
writecheck --whitelist-add "multieixos"
```

---

## How `writing_guard` Works

### 1. Academic Document Parsing & Noise Stripping

Standard readability tools break on academic papers because citations, LaTeX commands, equations, tables, and reference lists inflate word and syllable counts. `writing_guard/parser.py` extracts **only actual prose** while keeping exact line/page locations for every finding:

| Input Format | What Gets Extracted & Cleaned |
| :--- | :--- |
| **LaTeX (`.tex`, `.latex`)** | Recursively resolves `\input{...}` and `\include{...}` (with cycle protection); skips preambles before `\begin{document}`; strips comments, `$...$` / `$$...$$` / `\[...\]` / `\(...\)`, non-prose environments (`equation`, `align`, `tabular`, `tikzpicture`, `picture`, `lstlisting`, `minted`, `thebibliography`), citations/refs (`\cite*`, `\ref`, `\autoref`), and font/color wrappers (`\textcolor{red}{text}` → `text`, `\SI{5}{\milli\metre}` → `5 mm`), while preserving `\chapter`/`\section`/`\subsection` boundaries. |
| **PDF (`.pdf`)** | Extracts per-page prose via optional `pypdf`, re-joins hyphenated line breaks (`de-\nsenvolvimento` → `desenvolvimento`), removes `[1, 2]` citations and isolated page numbers, and excludes `References` / `Referências` / `Bibliografia` unless `--include-references` is passed. *(Tip: when `.tex` sources are available, run `writecheck` on `.tex` directly to avoid `pdfTeX` kerning/space-merging artifacts.)* |
| **Markdown (`.md`)** | Strips YAML frontmatter, fenced/inline code, math blocks, and Obsidian image embeds (`![[...]]`); converts wikilinks (`[[target\|alias]]` → `alias`) and links (`[text](url)` → `text`); splits sections by `#` headings. |
| **Word (`.docx`)** | Zero-dependency stdlib `zipfile` + `xml.etree.ElementTree` parser reading `word/document.xml` and grouping sections by `Heading1` / `Heading2` styles. |
| **Plain Text & Folders** | Reads `.txt` files directly or recursively walks directories (skipping `.git`, `.venv`, `build`, `dist`, `__pycache__`, `node_modules`). |

### 2. Bilingual Readability & Hotspots (`EN` + `pt-PT`)

Grounded in the *Disseminação e Escrita Científica (ADPE)* methodology and [`legibilidade.com`](https://legibilidade.com/sobre#flesch), `writing_guard` uses **distinct, calibrated formulas** for English and Portuguese (since Portuguese words naturally average more syllables than English equivalents).

Let $\text{ASL} = \frac{\text{words}}{\text{sentences}}$ (Average Sentence Length) and $\text{ASW} = \frac{\text{syllables}}{\text{words}}$ (Average Syllables per Word):

| Language | Flesch Reading Ease (FRE) | Flesch–Kincaid Grade Level (FKGL) | Syllable Backend |
| :--- | :--- | :--- | :--- |
| **English (`en`)** | `206.835 - 1.015 * ASL - 84.6 * ASW` | `0.39 * ASL + 11.8 * ASW - 15.59` | `cmudict` when installed; built-in irregular/academic table + rule fallback otherwise |
| **Portuguese (`pt`)** | `226.0 - 1.04 * ASL - 72.0 * ASW` | `0.36 * ASL + 10.4 * ASW - 18.0` | Pure-Python phonetic syllabifier (diphthongs, triphthongs, `qu`/`gu`, accented hiatuses, enclitic hyphens) |

#### Reading Ease Interpretation Bands (ADPE Slide 19)

| FRE Score | School Level | Meaning for Scientific Writing |
| :---: | :--- | :--- |
| **90–100** | 5th grade | Very easy to read (11-year-old level) |
| **80–90** | 6th grade | Easy conversational prose |
| **70–80** | 7th grade | Fairly easy to read |
| **60–70** | 8th & 9th grade | Plain language |
| **50–60** | 10th to 12th grade | Fairly difficult to read |
| **30–50** | College | Difficult to read — typical sweet spot for clear engineering/scientific prose |
| **10–30** | College graduate | Very difficult — consider splitting long sentences and simplifying phrasing |
| **< 10** | Professional | Extremely dense — check the **Hardest Sentences** hotspot list first |

Beyond global averages, `writing_guard` reports:
- **Per-section breakdown:** Spot immediately which chapter or subsection drags readability down.
- **Top $N$ hardest sentences:** Ranks sentences ($\ge 15$ words) by lowest sentence-level FRE so you know the exact lines to rewrite first.

### 3. ADPE Scientific Style & Portuguese Guard Rules

#### Bilingual & English Style Rules (`style_adpe.py`)

| Rule ID | Applies To | Severity | What It Catches & Why |
| :--- | :--- | :--- | :--- |
| `LONG_SENTENCE` | `en`, `pt` | `MEDIUM` / `HIGH` | Sentences exceeding **35 words** (`MEDIUM`) or **50 words** (`HIGH`) — the #1 driver of low readability |
| `ITALIC_LATIN_ABBREV` | `en`, `pt` | `LOW` | Latin abbreviations styled in italics (`\textit{e.g.}`, `\emph{i.e.}`, `*etc.*`, `*et al.*`, `*ibid.*`) |
| `ABBREV_DOUBLE_PERIOD` | `en`, `pt` | `LOW` | Double trailing period after abbreviations (`etc..`, `e.g..`, `i.e..`) |
| `UNDEFINED_ACRONYM` | `en`, `pt` | `MEDIUM` | All-caps acronyms ($\ge 3$ letters, $\ge 2$ occurrences) never defined in parentheses on first use |
| `EN_PT_TRANSLATION_CALQUE` | `en` | `MEDIUM` | Literal PT→EN translation errors: `It was developed a...`, `allows to <verb>`, `consists in`, `different than`, `make an analysis` |
| `EN_WEAK_START_CONJ` | `en` | `LOW` | Sentences starting with informal coordinating conjunctions (`And `, `But `, `So `) |
| `FIRST_PERSON_CHECK` | `en`, `pt` | `LOW` | First-person pronouns (`I`, `we`, `our`, `eu`, `nós`, `nosso`) outside Intro/Conclusions (opt-in via `--strict-impersonal`) |

#### European Portuguese (`pt-PT`) Style & Spelling Guards (`style_adpe.py` + `pt_guard.py`)

| Rule ID | Severity | What It Catches & Examples |
| :--- | :--- | :--- |
| `PT_AI_ISM` | `CRITICAL` / `MEDIUM` | LLM false friends & calques from `rules/ai_isms.json` (e.g., `escopo` → *âmbito*, `acurácia` → *exatidão*, `alavancar` → *potenciar*, `customizar` → *personalizar*, `performar` → *desempenhar*) |
| `PT_BR_LEXICON` / `PT_BR_PHRASE` / `PT_BR_CONSONANT` | `HIGH` | Brazilian Portuguese vocabulary and silent-consonant variants from `rules/pt_br_lexicon.json` (e.g., `usuário` → *utilizador*, `tela` → *ecrã*, `arquivo` → *ficheiro*, `usinagem` → *maquinagem*, `contatar` → *contactar*) |
| `PT_GERUNDIO` | `MEDIUM` | Gerunds (`-ando`, `-endo`, `-indo`, `-ondo`, verified against `pt_PT.dic` verbs) uncommon in formal `pt-PT` (suggests `a + infinitivo`, `ao + infinitivo`, `para + infinitivo`) |
| `PT_VERB_REPETITION` | `MEDIUM` | Same verb/deverbal stem repeated inside the same sentence (e.g., `permitir ... permitindo`) |
| `PT_DESTE_OVERUSE` | `LOW` | Possessive-like `deste`/`desse`/`desta`/`dessa` (`o desempenho desta` → `o seu desempenho`) |
| `PT_BARE_SMALL_NUMERAL` | `LOW` | Bare digits `1`–`9` or ordinals `1ª`/`2º` in prose without SI units or figure/table labels (`2 métodos` → `dois métodos`, while allowing `5 mm`, `45 m`, `12 %`, `Fig. 2`) |
| `PT_SPELLING_UNKNOWN` | `LOW` | Words absent from the compiled 2M+-inflection `pt-PT` dictionary (Hunspell Natura + Porto Editora lemmas) and `writing_guard/whitelist.txt` |

---

## Common Workflows & Recipes

### Simplify a dense thesis or report before submission

Run `writecheck` on your root `.tex` file to see section-level Flesch–Kincaid scores and the exact sentences dragging your score down:

```bash
writecheck main.tex --top-sentences 8
```

Focus first on sections marked `Professional` / `College graduate` and split any `LONG_SENTENCE` (`HIGH`) or top-ranked hardest sentences.

### Run fast quality checks inside an AI coding agent loop

Because `writecheck` costs **0 LLM tokens** and runs locally in under a second, you can point Claude Code, Cursor, or Antigravity at `--json` output so the agent fixes `PT_AI_ISM`, `PT_GERUNDIO`, `EN_PT_TRANSLATION_CALQUE`, and `LONG_SENTENCE` findings deterministically:

```bash
writecheck report/main.tex --json
```

### Enforce writing quality in GitHub Actions CI

Add a check step to any paper/thesis LaTeX repository:

```yaml
- name: Check manuscript readability & style
  run: |
    pip install git+https://github.com/gabriel-t-ribeiro/scholar-kit.git
    writecheck main.tex --min-ease 25 --max-grade 16 --fail-on-issues
```

---

## Sample Output

Running `writecheck tests/fixtures/sample_en.tex --lang en` produces:

```text
============================================================================
scholar-kit / writecheck  |  Language: EN  |  Mode: all  |  Syllables: cmudict
Source: tests/fixtures/sample_en.tex (2 files)
============================================================================
Readability (Overall)
  Words: 132  |  Sentences: 10  |  Syllables: 276
  ASL: 13.20 words/sent  |  ASW: 2.09 syl/word
  Flesch Reading Ease: 16.6 (College graduate — Very difficult to read. Best understood by university graduates.)
  Flesch-Kincaid Grade: 14.2

Per-Section Breakdown
  Section                       Words  Sents     ASL    ASW    FRE   FKGL  Band
  ------------------------------------------------------------------------------
  Introduction                     39      3   13.00   2.15   11.4   14.9  College graduate
  Methodology                      27      2   13.50   1.89   33.3   12.0  College
  Experimental Setup               56      4   14.00   2.07   17.4   14.3  College graduate
  Conclusions                      10      1   10.00   2.50  -14.8   17.8  Professional

Hardest Sentences (top 1)
  1. [.../tests/fixtures/sample_chapter.tex:7 | Experimental Setup | 31 words | FRE -10.2]
     "And the WSS module updates setpoints every fifteen minutes while logging reservoir levels, hydraulic heads, energy consumption, and valve..."

Findings (8 total: HIGH=0, MEDIUM=5, LOW=3)
  [MEDIUM]   .../sample_chapter.tex:2 (line) EN_PT_TRANSLATION_CALQUE [EN Style / Calque]
           Excerpt:    It was developed a
           Suggestion: Rewrite with the subject before the verb (e.g., 'A <noun> was developed...' or 'We developed a...').
           Why:        Literal Portuguese-to-English impersonal 'it was <verb> a...' calque.
  [MEDIUM]   .../sample_chapter.tex:6 (line) UNDEFINED_ACRONYM [Acronyms]
           Excerpt:    WSS
           Suggestion: Define 'WSS' in parentheses on first use (e.g., 'Full Term (WSS)').
           Why:        Acronym 'WSS' appears 2 times without being defined in parentheses at its first occurrence.
  [LOW]      .../sample_chapter.tex:8 (line) ITALIC_LATIN_ABBREV [ADPE Formatting]
           Excerpt:    \textit{etc.}
           Suggestion: Write 'etc.' in roman (upright) text without italics.
           Why:        Established Latin abbreviations (e.g., i.e., etc., et al., ibid.) should not be italicized.
============================================================================
```

---

## CLI Reference (`writecheck` & `scholar-kit`)

Both `writecheck` and `scholar-kit check` share the exact same options:

| Flag | Default | Description |
| :--- | :--- | :--- |
| `target` | — | File (`.tex`, `.latex`, `.pdf`, `.md`, `.docx`, `.txt`) or directory to analyze |
| `--lang auto\|en\|pt` | `auto` | Auto-detect language or force English / Portuguese formulas & rules |
| `--mode all\|readability\|style\|spelling` | `all` | Run all checks or isolate readability, ADPE style, or `pt-PT` spelling |
| `--sections` / `--no-sections` | `--sections` | Show or hide the per-section readability breakdown table |
| `--top-sentences N` | `5` | Number of hardest sentences to display |
| `--no-recursive` | `False` | Do not follow LaTeX `\input`/`\include` or traverse subdirectories |
| `--include-references` | `False` | Include bibliography/references sections in readability stats |
| `--strict-impersonal` | `False` | Flag first-person pronouns (`I`, `we`, `our`, `eu`, `nós`, `nosso`) outside Intro/Conclusions |
| `--json` / `--markdown` | terminal text | Export structured JSON or GitHub-flavored Markdown |
| `--output PATH` | stdout | Write the report to a file |
| `--min-ease FLOAT` | `None` | Exit with code `1` if overall Flesch Reading Ease is below threshold |
| `--max-grade FLOAT` | `None` | Exit with code `1` if overall Flesch–Kincaid Grade Level exceeds threshold |
| `--fail-on-issues` | `False` | Exit with code `1` if any style or spelling findings are present |
| `--whitelist-add WORD` | — | Append a domain term or acronym to `writing_guard/whitelist.txt` |

Unified hub usage:

```bash
scholar-kit check <target> [options]    # Runs writing_guard
scholar-kit vault <command> [args]      # Delegates to uni_vault/uni.py
```

---

## `uni_vault` — Obsidian University Workflow

`uni_vault/` automates day-to-day university knowledge management against an Obsidian vault connected through a local `uni_vault/vault` symlink (gitignored, keeping heavy media & Google Drive files out of Git):

- **`watcher.py`**: Watches the vault root during live lectures, renames new `.m4a`/`.pdf` files to ISO-week `snake_case` (`w42_ppfm_a1.m4a`), moves them into course folders, and launches transcription.
- **`transcribe.py` / `transcription_pipeline.py`**: Offline Apple Silicon transcription via `mlx-whisper` with domain vocabulary prompts and `[MM:SS]` timestamps.
- **`organise_media.py`**: Batch-organizes loose notes and media files (`--dry-run` supported).
- **`vault_tidy.py`**: Enforces `snake_case` naming conventions (`check`, `plan`, `apply`, `undo`) and updates Obsidian wikilinks safely.
- **`make_ai_note.py` / `enrich_note.py` / `anki_inject.py`**: Slide text extraction, consolidated AI study note scaffolding, and AnkiConnect flashcard syncing.

See [uni_vault/README.md](uni_vault/README.md) for script-by-script examples.

---

## Project Structure

```text
scholar-kit/
├── pyproject.toml                 # PEP 621 packaging, optional extras, & CLI scripts
├── requirements.txt               # Full local dev & Apple Silicon vault environment
├── .github/workflows/ci.yml       # Ruff + pytest on Python 3.11 & 3.12 (with & without cmudict)
├── writing_guard/                 # Portable bilingual readability, ADPE style & pt-PT guard
│   ├── models.py                  # Shared dataclasses (ParsedDocument, Finding, ReadabilityReport)
│   ├── language.py                # Zero-dep EN / PT heuristic detector
│   ├── syllables.py               # PT phonetic syllabifier + EN cmudict / rule fallback
│   ├── parser.py                  # .tex (\input/\include), .pdf, .md, .docx, .txt parsers
│   ├── readability.py             # ADPE Slide 18 formulas, Slide 19 bands & sentence hotspots
│   ├── style_adpe.py              # ADPE scientific writing & PT->EN calque rules
│   ├── pt_guard.py                # pt-PT spellcheck, pt-BR lexicon, gerund & AI-ism guards
│   ├── vocab_builder.py           # Hunspell + Porto Editora morphological vocabulary compiler
│   ├── reporter.py                # Terminal, JSON & Markdown formatters
│   ├── cli.py                     # writecheck & scholar-kit CLI entrypoints
│   ├── rules/                     # ai_isms.json, pt_br_lexicon.json
│   ├── dictionaries/              # pt_PT / pt_BR Hunspell, Porto Editora lemmas, compiled cache
│   └── whitelist.txt              # Project/domain-approved terminology whitelist
├── uni_vault/                     # Obsidian university vault automation suite
│   ├── README.md                  # Vault script reference
│   ├── uni.py                     # Unified vault CLI hub
│   └── ...                        # watcher, transcribe, organise_media, vault_tidy, anki_inject
└── tests/                         # Unit, fixture, and CLI integration test suite (107 tests)
    └── fixtures/                  # EN & PT .md, .tex (with \input), and .docx samples
```

---

## CI & Development

Run the full test and lint suite locally:

```bash
.venv/bin/pytest -v
.venv/bin/ruff check writing_guard tests
```

GitHub Actions (`.github/workflows/ci.yml`) validates every push and pull request across Python **3.11** and **3.12**, testing both the **zero-dependency** English syllabifier fallback (`without cmudict`) and exact **`cmudict`** lookup (`with cmudict`).

> [!NOTE]
> **Dictionary Licensing Note:** `writing_guard/dictionaries/pt_PT.{aff,dic}` and `pt_BR.dic` come from open-source Natura/LibreOffice Hunspell dictionaries, while `porto_editora_lemmas.txt` is a local headword list retained for personal `pt-PT` coverage. Before making a private fork public, remove or `.gitignore` `porto_editora_lemmas.txt` and rebuild the cache from Hunspell alone if strictly open-licensed assets are required.

---

## License

MIT License — see [LICENSE](LICENSE).
