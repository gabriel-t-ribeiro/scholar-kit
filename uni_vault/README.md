# `uni_vault/` — Obsidian University Vault Automation

Scripts for managing and automating the Obsidian university vault (`0_uni_obsidian`) through the `uni_vault/vault` symlink (kept outside Google Drive).

## Scripts

| Script | Purpose |
| :--- | :--- |
| `uni.py` | Unified hub (`./uni.py <command> [args]`), or invoked via `scholar-kit vault <command> [args]` |
| `watcher.py` | Real-time class monitor: detects new audio/PDFs in vault root, renames to ISO-week `snake_case`, moves into course folders, and launches transcription |
| `transcribe.py` | Local Apple Silicon (`mlx-whisper`) audio transcription with course-specific vocabulary prompts and `[MM:SS]` timestamps |
| `organise_media.py` | Batch-organizes loose notes and media files from the vault root (`--dry-run` supported) |
| `make_ai_note.py` | Prepares folder structure and context for consolidated AI study notes |
| `enrich_note.py` | Extracts lecture slide text from PDFs to enrich weekly notes |
| `anki_inject.py` | Syncs validated flashcards into Anki via AnkiConnect |
| `vault_tidy.py` | Enforces vault naming conventions (`check`, `plan`, `apply`, `undo`) and updates wikilinks |

## Usage

```bash
# Unified CLI via scholar-kit
scholar-kit vault watch ppfm
scholar-kit vault organize --dry-run
scholar-kit vault transcribe "2m1s_ppfm/ppfm_mp/w39_ppfm_a1.m4a"

# Or directly via Python
python3 uni_vault/uni.py --help
python3 uni_vault/vault_tidy.py check
```

## Setup

Install the `vault` extra (Apple Silicon recommended for `mlx-whisper`):

```bash
pip install -e ".[vault]"
```
