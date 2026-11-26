"""European Portuguese (pt-PT) spellchecker, pt-BR filter, and AI-ism guard."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from .models import Finding, ParsedDocument

try:
    from .vocab_builder import build_vocabulary
except ImportError:
    from vocab_builder import build_vocabulary

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_DIR = os.path.join(BASE_DIR, "rules")
WHITELIST_FILE = os.path.join(BASE_DIR, "whitelist.txt")
AI_ISMS_FILE = os.path.join(RULES_DIR, "ai_isms.json")
PT_BR_FILE = os.path.join(RULES_DIR, "pt_br_lexicon.json")
DIC_FILE = os.path.join(BASE_DIR, "dictionaries", "pt_PT.dic")

WORD_REGEX = re.compile(r"\b[a-zA-ZçáéíóúâêôãõàüÁÉÍÓÚÂÊÔÃÕÀÜ-]+(?:\b|(?=[.,;!?\s]))")

# Common function words, auxiliaries, and non-verb -ar/-er/-ir nouns/adjectives
# excluded from Option A same-sentence verb-repetition checks.
REPETITION_IGNORE_WORDS = {
    "sobre", "entre", "através", "para", "como", "mais", "menos", "quando",
    "onde", "porque", "mesmo", "mesma", "mesmos", "mesmas", "muito", "muita",
    "muitos", "muitas", "outro", "outra", "outros", "outras", "tanto", "tanta",
    "tantos", "tantas", "assim", "ainda", "também", "apenas", "durante",
    "enquanto", "segundo", "conforme", "sendo", "estar", "estava", "estão",
    "foram", "serão", "seria", "tendo", "tinha", "havia", "houve", "poder",
    "podem", "podendo", "fazer", "fazem", "fazendo", "dever", "devem",
    "lugar", "melhor", "maior", "menor", "superior", "inferior", "anterior",
    "posterior", "exterior", "interior", "particular", "similar", "regular",
    "linear", "circular", "angular", "modular", "familiar", "popular",
    "singular", "tabular", "retangular", "triangular", "perpendicular",
}

VERB_SUFFIXES = (
    "aríamos", "eríamos", "iríamos", "ávamos", "íamos",
    "ariam", "eriam", "iriam", "armos", "ermos", "irmos",
    "arão", "erão", "irão", "ando", "endo", "indo",
    "aram", "eram", "iram", "avam", "aria", "eria", "iria",
    "arei", "erei", "irei", "asse", "esse", "isse",
    "aste", "este", "iste", "amos", "emos", "imos",
    "ará", "erá", "irá", "ara", "era", "ira", "ava",
    "ou", "eu", "iu", "ar", "er", "ir", "am", "em",
)

DEVERBAL_SUFFIXES = (
    "ações", "ições", "ação", "ição", "amento", "imento",
    "ados", "adas", "idos", "idas", "ado", "ada", "ido", "ida",
    "ante", "ente", "inte", "ável", "ível",
)

CLITIC_PRONOUNS = {
    "se", "me", "te", "nos", "vos", "o", "a", "os", "as",
    "lhe", "lhes", "lo", "la", "los", "las",
}

ENCLITIC_PRONOUNS = CLITIC_PRONOUNS | {"no", "na"}

_CACHE: dict[str, Any] = {}


def _load_json(path: str) -> dict[str, Any]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_whitelist(path: str | None = None) -> set[str]:
    """Load lowercase domain whitelist entries from path (or default whitelist.txt)."""
    target = path or WHITELIST_FILE
    whitelist: set[str] = set()
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    whitelist.add(line.lower())
    return whitelist


def add_to_whitelist(word: str, whitelist_path: str | None = None) -> str:
    """Append word to whitelist file if not already present, returning the file path."""
    target = whitelist_path or WHITELIST_FILE
    cleaned = word.strip()
    if not cleaned:
        return target

    existing = load_whitelist(target)
    if cleaned.lower() in existing:
        return target

    needs_newline = False
    if os.path.exists(target) and os.path.getsize(target) > 0:
        with open(target, "rb") as fb:
            fb.seek(-1, os.SEEK_END)
            needs_newline = fb.read(1) != b"\n"

    os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        f.write(f"{cleaned}\n")
    return target


def is_number_or_code(token: str) -> bool:
    if any(c.isdigit() or c in r"_/\<>{}=+*@#$%^&~`|" for c in token):
        return True
    if len(token) == 1 and token.lower() not in ("a", "e", "o", "à", "é"):
        return True
    return False


def _verb_stem_pt(word_lower: str) -> tuple[str | None, bool]:
    """Return (stem, is_verb_form) for Option A same-sentence repetition checks."""
    if len(word_lower) < 5 or "-" in word_lower or word_lower in REPETITION_IGNORE_WORDS:
        return None, False

    # Engineering/abstract nouns ending in -agem / -igem (e.g., maquinagem, fresagem, estampagem)
    if word_lower.endswith(("agem", "igem")):
        return word_lower, False

    for suffix in VERB_SUFFIXES:
        if word_lower.endswith(suffix):
            stem = word_lower[: -len(suffix)]
            if len(stem) >= 4:
                return stem, True

    for suffix in DEVERBAL_SUFFIXES:
        if word_lower.endswith(suffix):
            stem = word_lower[: -len(suffix)]
            if len(stem) >= 4:
                return stem, False

    return word_lower, False


def find_sentence_verb_repetitions(text: str) -> list[tuple[str, list[str]]]:
    """Find repeated verb/deverbal stems within the same sentence (Option A)."""
    repeats: list[tuple[str, list[str]]] = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for sent in sentences:
        if not sent.strip():
            continue
        tokens = re.findall(r"\b[a-zA-ZçáéíóúâêôãõàüÁÉÍÓÚÂÊÔÃÕÀÜ-]+\b", sent)
        by_stem: dict[str, list[tuple[str, bool]]] = {}
        for tok in tokens:
            if is_number_or_code(tok):
                continue
            w_lower = tok.lower()
            stem, is_verb = _verb_stem_pt(w_lower)
            if not stem:
                continue
            by_stem.setdefault(stem, []).append((tok, is_verb))

        for stem, occs in by_stem.items():
            if len(occs) >= 2 and any(is_verb for _, is_verb in occs):
                words = [w for w, _ in occs]
                repeats.append((stem, words))
    return repeats


def load_verb_gerund_lookup(dic_path: str) -> tuple[set[str], dict[str, str]]:
    """Extract pt-PT verb infinitives and irregular T=g gerund forms from pt_PT.dic."""
    verbs: set[str] = set()
    irregular_gerunds: dict[str, str] = {}
    if not os.path.exists(dic_path):
        return verbs, irregular_gerunds

    with open(dic_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if "CAT=v" not in line:
                continue
            parts = line.split("\t", 1)
            w = parts[0].split("/", 1)[0].lower()
            meta = parts[1] if len(parts) > 1 else ""
            if "T=inf" in meta and "$" not in meta and w.endswith(("ar", "er", "ir", "or", "ôr")):
                verbs.add(w)
            if "T=g]" in meta or "T=g," in meta or "T=g " in meta:
                lemma_match = re.search(r"\$([^$]+)\$CAT=v", meta)
                inf = lemma_match.group(1).lower() if lemma_match else (w[:-3] + "r")
                irregular_gerunds[w] = inf

    return verbs, irregular_gerunds


def detect_gerund_infinitive(
    w_lower: str,
    verbs: set[str],
    irregular_gerunds: dict[str, str],
    exceptions: set[str],
) -> str | None:
    """Return verb infinitive if w_lower is a Portuguese gerund (-ando/-endo/-indo/-ondo), else None."""
    if "-" in w_lower:
        parts = w_lower.split("-")
        if not all(p in CLITIC_PRONOUNS for p in parts[1:]):
            return None
        base = parts[0]
    else:
        base = w_lower

    if len(base) < 4 or base in exceptions:
        return None
    if not base.endswith(("ando", "endo", "indo", "ondo")):
        return None
    if base in irregular_gerunds:
        return irregular_gerunds[base]

    cand = base[:-3] + "r"
    if cand in verbs:
        return cand
    if base.endswith("pondo"):
        cand_or = base[:-3] + "ôr"
        if cand_or in verbs:
            return cand_or
    return None


def _get_resources() -> dict[str, Any]:
    """Lazy-load dictionary, verb gerund table, AI-isms, and pt-BR rules on first run."""
    if "vocab" not in _CACHE:
        _CACHE["vocab"] = build_vocabulary(force_rebuild=False)
    if "ai_isms_data" not in _CACHE:
        _CACHE["ai_isms_data"] = _load_json(AI_ISMS_FILE)
    if "pt_br_data" not in _CACHE:
        _CACHE["pt_br_data"] = _load_json(PT_BR_FILE)
    if "gerund_lookup" not in _CACHE:
        gerund_cfg = _CACHE["ai_isms_data"].get("gerundio_rule", {})
        if gerund_cfg.get("enabled", True):
            _CACHE["gerund_lookup"] = load_verb_gerund_lookup(DIC_FILE)
        else:
            _CACHE["gerund_lookup"] = (set(), {})
    return _CACHE


def check_pt_document(
    docs: list[ParsedDocument],
    whitelist_path: str | None = None,
) -> list[Finding]:
    """Check parsed Portuguese documents for AI-isms, pt-BR terms, gerunds, verb repeats, and spelling."""
    res = _get_resources()
    vocab: set[str] = res["vocab"]
    ai_isms_data: dict[str, Any] = res["ai_isms_data"]
    ai_isms: dict[str, Any] = ai_isms_data.get("terms", {})
    gerund_cfg: dict[str, Any] = ai_isms_data.get("gerundio_rule", {})
    gerund_enabled: bool = gerund_cfg.get("enabled", True)
    gerund_exceptions = {w.lower() for w in gerund_cfg.get("accepted_exceptions", [])}
    gerund_explanation: str = gerund_cfg.get(
        "explanation",
        "Uso de gerúndio (-ando, -endo, -indo, -ondo), pouco natural na escrita formal em pt-PT. Prefira 'a + infinitivo', 'ao + infinitivo', 'para + infinitivo' ou uma oração relativa.",
    )
    verbs, irregular_gerunds = res["gerund_lookup"]

    pt_br_data: dict[str, Any] = res["pt_br_data"]
    pt_br_words: dict[str, Any] = pt_br_data.get("word_replacements", {})
    pt_br_consonants: dict[str, str] = pt_br_data.get("consonant_rules", {})
    multiword_phrases = [
        (phrase, info, re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)"))
        for phrase, info in pt_br_words.items()
        if " " in phrase
    ]

    whitelist = load_whitelist(whitelist_path)

    findings: list[Finding] = []
    seen_keys: set[tuple[str, str, int, str]] = set()

    for doc in docs:
        for line in doc.lines:
            text = line.clean_text
            if not text or not text.strip():
                continue

            file = line.file
            loc = line.loc
            loc_label = line.loc_label

            # 0. Same-sentence verb stem repetition check (Option A)
            for stem, rep_words in find_sentence_verb_repetitions(text):
                key = (file, stem, loc, "PT_VERB_REPETITION")
                if key not in seen_keys:
                    seen_keys.add(key)
                    joined = " ... ".join(f"'{w}'" for w in rep_words)
                    findings.append(
                        Finding(
                            rule_id="PT_VERB_REPETITION",
                            category="Style / Repetition",
                            severity="MEDIUM",
                            file=file,
                            loc=loc,
                            loc_label=loc_label,
                            excerpt=" ... ".join(rep_words),
                            suggestion="Variar o verbo ou reestruturar a frase",
                            explanation=f"Repetição do mesmo radical verbal na mesma frase ({joined}).",
                        )
                    )

            # 1. Multi-word phrases in pt-BR lexicon
            text_lower = text.lower()
            for phrase, info, phrase_re in multiword_phrases:
                if phrase in text_lower and phrase_re.search(text_lower):
                    key = (file, phrase, loc, "PT_BR_PHRASE")
                    if key not in seen_keys:
                        seen_keys.add(key)
                        findings.append(
                            Finding(
                                rule_id="PT_BR_PHRASE",
                                category="PT-BR Lexicon",
                                severity="HIGH",
                                file=file,
                                loc=loc,
                                loc_label=loc_label,
                                excerpt=phrase,
                                suggestion=info.get("suggestion") or "",
                                explanation=info.get("explanation") or "",
                            )
                        )

            # 2. Token-level checks
            for w in WORD_REGEX.findall(text):
                w_clean = w.strip("-").strip()
                if not w_clean or is_number_or_code(w_clean):
                    continue

                w_lower = w_clean.lower()
                if w_lower in whitelist:
                    continue

                # Check 1: AI-ism / False Friend
                if w_lower in ai_isms:
                    key = (file, w_lower, loc, "PT_AI_ISM")
                    if key not in seen_keys:
                        seen_keys.add(key)
                        findings.append(
                            Finding(
                                rule_id="PT_AI_ISM",
                                category="AI-ISM / Calque",
                                severity="CRITICAL" if w_lower in ("escopo", "escopos", "acurácia") else "MEDIUM",
                                file=file,
                                loc=loc,
                                loc_label=loc_label,
                                excerpt=w_clean,
                                suggestion=ai_isms[w_lower].get("suggestion") or "",
                                explanation=ai_isms[w_lower].get("explanation") or "",
                            )
                        )
                    continue

                # Check 2: pt-BR Specific Lexicon
                if w_lower in pt_br_words:
                    key = (file, w_lower, loc, "PT_BR_LEXICON")
                    if key not in seen_keys:
                        seen_keys.add(key)
                        findings.append(
                            Finding(
                                rule_id="PT_BR_LEXICON",
                                category="PT-BR Lexicon",
                                severity="HIGH",
                                file=file,
                                loc=loc,
                                loc_label=loc_label,
                                excerpt=w_clean,
                                suggestion=pt_br_words[w_lower].get("suggestion") or "",
                                explanation=pt_br_words[w_lower].get("explanation") or "",
                            )
                        )
                    continue

                # Check 3: pt-BR Consonant dropping
                if w_lower in pt_br_consonants:
                    key = (file, w_lower, loc, "PT_BR_CONSONANT")
                    if key not in seen_keys:
                        seen_keys.add(key)
                        pt_form = pt_br_consonants[w_lower]
                        findings.append(
                            Finding(
                                rule_id="PT_BR_CONSONANT",
                                category="PT-BR Spelling",
                                severity="HIGH",
                                file=file,
                                loc=loc,
                                loc_label=loc_label,
                                excerpt=w_clean,
                                suggestion=pt_form,
                                explanation=f"Grafia brasileira ou consoante muda. Em pt-PT usa-se '{pt_form}'.",
                            )
                        )
                    continue

                # Check 3b: Gerúndio (-ando, -endo, -indo, -ondo) -> AI-ISM / Calque in formal pt-PT
                if gerund_enabled:
                    gerund_inf = detect_gerund_infinitive(
                        w_lower, verbs, irregular_gerunds, gerund_exceptions
                    )
                    if gerund_inf:
                        key = (file, w_lower, loc, "PT_GERUNDIO")
                        if key not in seen_keys:
                            seen_keys.add(key)
                            findings.append(
                                Finding(
                                    rule_id="PT_GERUNDIO",
                                    category="AI-ISM / Calque",
                                    severity="MEDIUM",
                                    file=file,
                                    loc=loc,
                                    loc_label=loc_label,
                                    excerpt=w_clean,
                                    suggestion=f"Evitar gerúndio: 'a {gerund_inf}', 'ao {gerund_inf}', 'para {gerund_inf}' ou 'que + {gerund_inf}'",
                                    explanation=gerund_explanation,
                                )
                            )
                        continue

                # Check 4: Enclitic pronouns in Portuguese (e.g. realizou-se, encontram-se)
                if "-" in w_lower and w_lower not in vocab:
                    parts = w_lower.split("-")
                    base_verb = parts[0]
                    if base_verb in vocab and all(p in ENCLITIC_PRONOUNS for p in parts[1:]):
                        continue

                # Check 5: General pt-PT Vocabulary & Conjugations
                if w_lower not in vocab:
                    key = (file, w_lower, loc, "PT_SPELLING_UNKNOWN")
                    if key not in seen_keys:
                        seen_keys.add(key)
                        findings.append(
                            Finding(
                                rule_id="PT_SPELLING_UNKNOWN",
                                category="Spelling / Unknown",
                                severity="LOW",
                                file=file,
                                loc=loc,
                                loc_label=loc_label,
                                excerpt=w_clean,
                                suggestion="Verificar ortografia ou adicionar a whitelist.txt",
                                explanation=f"A palavra '{w_clean}' não foi encontrada no vocabulário oficial de português europeu (Porto Editora / Natura).",
                            )
                        )

    return findings
