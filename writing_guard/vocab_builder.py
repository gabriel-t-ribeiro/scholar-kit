"""
Vocabulary builder for pt-PT spellchecker.
Combines:
1. LibreOffice / Natura pt_PT Hunspell affixes and dictionary (1.4+ million inflected forms).
2. Porto Editora Grande Dicionário da Língua Portuguesa lemmas (110k+ official headwords).
3. Automatic morphological expansions for Porto Editora lemmas:
   - Plural formation (e.g. -o -> -os, -ão -> -ões, -al -> -ais, etc.)
   - Feminine formation (e.g. -o -> -a/-as, -or -> -ora/-oras)
   - Regular verb inflection paradigms (-ar, -er, -ir) for infinitive lemmas.
Saves a compiled gzip pickle cache (pt_PT_vocab.pkl.gz) for sub-second loading.
"""

import gzip
import os
import pickle
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AFF_FILE = os.path.join(BASE_DIR, "dictionaries", "pt_PT.aff")
DIC_FILE = os.path.join(BASE_DIR, "dictionaries", "pt_PT.dic")
PORTO_FILE = os.path.join(BASE_DIR, "dictionaries", "porto_editora_lemmas.txt")
CACHE_FILE = os.path.join(BASE_DIR, "dictionaries", "pt_PT_vocab.pkl.gz")

AR_ENDINGS = [
    "o", "as", "a", "amos", "ais", "am",
    "ei", "aste", "ou", "ámos", "astes", "aram",
    "ava", "avas", "ávamos", "áveis", "avam",
    "ara", "aras", "áramos", "áreis", "aram",
    "arei", "arás", "ará", "aremos", "areis", "arão",
    "aria", "arias", "aríamos", "aríeis", "ariam",
    "e", "es", "emos", "eis", "em",
    "asse", "asses", "ássemos", "ásseis", "assem",
    "ar", "ares", "armos", "ardes", "arem",
    "ando", "ado", "ada", "ados", "adas"
]

ER_ENDINGS = [
    "o", "es", "e", "emos", "eis", "em",
    "i", "este", "eu", "emos", "estes", "eram",
    "ia", "ias", "íamos", "íeis", "iam",
    "era", "eras", "êramos", "êreis", "eram",
    "erei", "erás", "erá", "eremos", "ereis", "erão",
    "eria", "erias", "eríamos", "eríeis", "eriam",
    "a", "as", "amos", "ais", "am",
    "esse", "esses", "êssemos", "êsseis", "essem",
    "er", "eres", "ermos", "erdes", "erem",
    "endo", "ido", "ida", "idos", "idas"
]

IR_ENDINGS = [
    "o", "es", "e", "imos", "is", "em",
    "i", "iste", "iu", "imos", "istes", "iram",
    "ia", "ias", "íamos", "íeis", "iam",
    "ira", "iras", "íramos", "íreis", "iram",
    "irei", "irás", "irá", "iremos", "ireis", "irão",
    "iria", "irias", "iríamos", "iríeis", "iriam",
    "a", "as", "amos", "ais", "am",
    "isse", "isses", "íssemos", "ísseis", "issem",
    "ir", "ires", "irmos", "irdes", "irem",
    "indo", "ido", "ida", "idos", "idas"
]


def parse_aff(aff_path):
    prefixes = {}
    suffixes = {}
    if not os.path.exists(aff_path):
        return prefixes, suffixes

    with open(aff_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] in ("PFX", "SFX"):
                kind = parts[0]
                flag = parts[1]
                if len(parts) == 4 and parts[2] in ("Y", "N"):
                    continue
                if len(parts) >= 5:
                    strip = parts[2] if parts[2] != "0" else ""
                    add = parts[3].split("/")[0] if parts[3] != "0" else ""
                    cond = parts[4] if len(parts) > 4 else "."
                    target = prefixes if kind == "PFX" else suffixes
                    if flag not in target:
                        target[flag] = []
                    target[flag].append((strip, add, cond))
    return prefixes, suffixes


def inflect_lemma(w, words_set):
    """Add plurals, feminines, and standard regular conjugations for a Portuguese lemma."""
    words_set.add(w)

    # Nouns & Adjectives
    if w.endswith(("o", "a", "e", "i", "u")):
        words_set.add(w + "s")
    if w.endswith("o"):
        fem = w[:-1] + "a"
        words_set.add(fem)
        words_set.add(fem + "s")
    elif w.endswith("or"):
        words_set.add(w + "es")
        words_set.add(w + "a")
        words_set.add(w + "as")
    elif w.endswith("ão"):
        stem = w[:-2]
        words_set.add(stem + "ões")
        words_set.add(stem + "ãos")
        words_set.add(stem + "ães")
    elif w.endswith("al"):
        words_set.add(w[:-1] + "is")
    elif w.endswith("el"):
        words_set.add(w[:-2] + "eis")
    elif w.endswith("ol"):
        words_set.add(w[:-2] + "óis")
    elif w.endswith("il"):
        words_set.add(w[:-1] + "s")
        words_set.add(w[:-2] + "eis")
    elif w.endswith("m"):
        words_set.add(w[:-1] + "ns")
    elif w.endswith(("r", "z")):
        words_set.add(w + "es")

    # Regular verb endings if verb
    if len(w) > 3:
        if w.endswith("ar"):
            stem = w[:-2]
            for ending in AR_ENDINGS:
                words_set.add(stem + ending)
        elif w.endswith("er"):
            stem = w[:-2]
            for ending in ER_ENDINGS:
                words_set.add(stem + ending)
        elif w.endswith("ir"):
            stem = w[:-2]
            for ending in IR_ENDINGS:
                words_set.add(stem + ending)


def build_vocabulary(force_rebuild=False):
    if not force_rebuild and os.path.exists(CACHE_FILE):
        with gzip.open(CACHE_FILE, "rb") as f:
            words = pickle.load(f)
        return words

    print("[writing_guard] Compiling European Portuguese vocabulary cache...")
    t0 = time.time()
    words = set()

    prefixes, suffixes = parse_aff(AFF_FILE)

    # 1. Load Hunspell dictionary + affix expansions
    if os.path.exists(DIC_FILE):
        with open(DIC_FILE, "r", encoding="utf-8", errors="ignore") as f:
            first = True
            for line in f:
                if first:
                    first = False
                    continue
                line = line.strip()
                if not line:
                    continue
                main_part = line.split("\t")[0].strip()
                if not main_part:
                    continue
                if "/" in main_part:
                    base, flags = main_part.split("/", 1)
                else:
                    base, flags = main_part, ""

                base_clean = base.strip().lower()
                if not base_clean:
                    continue
                words.add(base_clean)

                for flag in flags:
                    if flag in suffixes:
                        for strip, add, _ in suffixes[flag]:
                            if strip:
                                if base_clean.endswith(strip):
                                    stem = base_clean[:-len(strip)]
                                    words.add((stem + add).lower())
                            else:
                                words.add((base_clean + add).lower())

    hunspell_count = len(words)
    print(f"[writing_guard] Loaded {hunspell_count} inflections from Hunspell pt_PT.")

    # 2. Load Porto Editora lemmas + morphological inflection
    if os.path.exists(PORTO_FILE):
        with open(PORTO_FILE, "r", encoding="utf-8", errors="ignore") as f:
            pe_lemmas = [line.strip().lower() for line in f if line.strip() and not line.strip().startswith("-")]

        for lemma in pe_lemmas:
            inflect_lemma(lemma, words)
        print(f"[writing_guard] Loaded and inflected {len(pe_lemmas)} lemmas from Porto Editora.")

    print(f"[writing_guard] Total compiled vocabulary: {len(words)} entries in {time.time() - t0:.2f}s.")
    print(f"[writing_guard] Saving cache to {CACHE_FILE}...")
    with gzip.open(CACHE_FILE, "wb") as f:
        pickle.dump(words, f, protocol=pickle.HIGHEST_PROTOCOL)

    return words


if __name__ == "__main__":
    vocab = build_vocabulary(force_rebuild=True)
    print("Compilation successful! Entries:", len(vocab))
