#!/usr/bin/env python3
"""
Main Automation Hub for the Obsidian Vault (0_uni_obsidian).
Central CLI entrypoint for the vault scripts in scholar-kit/uni_vault/
with on-the-fly help documentation and argument forwarding.
"""

import os
import sys
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# All scripts live next to this file (scholar-kit/uni_vault)
UTIL_DIR = SCRIPT_DIR

COMMANDS = {
    "watch": {
        "script": "watcher.py",
        "desc": "Real-time class monitor (detects audio/PDFs/prints, moves to subject folders, triggers Whisper transcription).",
        "usage": "./uni.py watch <discipline>  (e.g., dpe, dissertation, ppfm, savi, ma, sem)"
    },
    "transcribe": {
        "script": "transcribe.py",
        "desc": "Transcribes audio recordings locally with Metal acceleration (Whisper Large-v3) and links to notes.",
        "usage": "./uni.py transcribe <path_to_audio.m4a>"
    },
    "organize": {
        "script": "organise_media.py",
        "desc": "Batch organizes loose notes (.md) and media files (audio/PDF/prints) from the vault root into their respective course folders.",
        "usage": "./uni.py organize [--dry-run]"
    },
    "generate-note": {
        "script": "make_ai_note.py",
        "desc": "Prepares folder structure and context for AI consolidated study notes (AI Notes).",
        "usage": "./uni.py generate-note <path_to_weekly_note.md>"
    },
    "enrich": {
        "script": "enrich_note.py",
        "desc": "Extracts text content and structure from lecture PDF slides.",
        "usage": "./uni.py enrich <path_to_pdf.pdf>"
    },
    "test-cloud": {
        "script": "test_cloud_transcription.py",
        "desc": "Tests audio transcription via cloud APIs (Gemini 2.5 Pro or Groq Whisper).",
        "usage": "./uni.py test-cloud <audio.m4a> [--gemini | --groq]"
    },
    "test-model": {
        "script": "test_transcription_model.py",
        "desc": "Benchmarks transcription with alternative MLX models (e.g., large-v3-turbo).",
        "usage": "./uni.py test-model <audio.m4a> [model_repo] [model_label]"
    }
}

ALIASES = {
    "watcher": "watch",
    "transcrever": "transcribe",
    "transcricao": "transcribe",
    "organizar": "organize",
    "clean": "organize",
    "gerar-nota": "generate-note",
    "note": "generate-note",
    "ai-note": "generate-note",
    "enriquecer": "enrich",
    "pdf": "enrich",
    "teste-cloud": "test-cloud",
    "teste-modelo": "test-model"
}

def print_help():
    print("""🛠️  Vault Automation Hub (uni.py)
--------------------------------------------------
Usage:
  ./uni.py <command> [arguments...]
  python3 uni.py <command> [arguments...]

Available Commands:""")

    for cmd, info in COMMANDS.items():
        print(f"  • {cmd:<14} : {info['desc']}")
        print(f"    {'Usage:':<14}   {info['usage']}")

    print("""
On-the-fly Help:
  ./uni.py <command> --help
  ./uni.py help <command>

Examples:
  ./uni.py watch dpe
  ./uni.py watch ppfm
  ./uni.py organize --dry-run
  ./uni.py transcribe "2m_dissertation/dpe_mp/w40_dpe_topic_introduction.m4a"
  ./uni.py generate-note "2m1s_ppfm/w39_ppfm -- introdução.md"
--------------------------------------------------""")

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        if len(sys.argv) >= 3 and sys.argv[1] == "help":
            target_cmd = sys.argv[2].lower()
            target_cmd = ALIASES.get(target_cmd, target_cmd)
            if target_cmd in COMMANDS:
                script_path = os.path.join(UTIL_DIR, COMMANDS[target_cmd]["script"])
                subprocess.run([sys.executable, script_path, "--help"])
                return
        print_help()
        return

    cmd_raw = sys.argv[1].lower()
    cmd = ALIASES.get(cmd_raw, cmd_raw)

    if cmd not in COMMANDS:
        print(f"❌ Unknown command: '{cmd_raw}'")
        print("Available commands: " + ", ".join(COMMANDS.keys()))
        print("Run './uni.py --help' to view all details.")
        sys.exit(1)

    script_name = COMMANDS[cmd]["script"]
    script_path = os.path.join(UTIL_DIR, script_name)

    if not os.path.exists(script_path):
        print(f"❌ Target script not found at: {script_path}")
        sys.exit(1)

    # Forward all subsequent arguments to target script
    sub_args = sys.argv[2:]
    cmd_to_run = [sys.executable, script_path] + sub_args

    try:
        res = subprocess.run(cmd_to_run)
        sys.exit(res.returncode)
    except KeyboardInterrupt:
        print("\n👋 Process interrupted.")
        sys.exit(0)

if __name__ == "__main__":
    main()
