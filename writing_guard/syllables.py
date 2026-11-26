"""Bilingual EN/PT syllable counter with optional cmudict and zero-dep fallbacks."""

from __future__ import annotations

import re

_ALPHA_RE = re.compile(r"[A-Za-zÀ-ÿ]")
_EN_WORD_CLEAN_RE = re.compile(r"[^a-z]")
_PT_WORD_CLEAN_RE = re.compile(r"[^a-záéíóúâêôàãõüç]")

_CMU_DICT: dict[str, list[list[str]]] | None = None
_CMU_LOAD_ATTEMPTED = False

# Curated irregular & academic English words (minimum canonical syllable count).
_EN_IRREGULAR_SYLLABLES: dict[str, int] = {
    # Academic & engineering core
    "area": 3,
    "areas": 3,
    "queue": 1,
    "queues": 1,
    "queued": 1,
    "science": 2,
    "sciences": 2,
    "scientific": 4,
    "temperature": 3,
    "temperatures": 3,
    "algorithm": 4,
    "algorithms": 4,
    "algorithmic": 4,
    "finite": 2,
    "infinite": 3,
    "surface": 2,
    "surfaces": 3,
    "different": 2,
    "difference": 2,
    "differences": 3,
    "average": 2,
    "averages": 3,
    "material": 4,
    "materials": 4,
    "variable": 4,
    "variables": 4,
    "analysis": 4,
    "analyses": 4,
    "methodology": 5,
    "methodologies": 5,
    "equation": 3,
    "equations": 3,
    "every": 2,
    "everything": 3,
    "everyone": 3,
    "everywhere": 3,
    "various": 3,
    "continuous": 4,
    "continuously": 5,
    "discrete": 2,
    "linear": 3,
    "nonlinear": 4,
    "matrix": 2,
    "matrices": 3,
    "vertex": 2,
    "vertices": 3,
    "index": 2,
    "indices": 3,
    "radius": 3,
    "radii": 3,
    "axis": 2,
    "axes": 2,
    "phenomenon": 4,
    "phenomena": 4,
    "criterion": 4,
    "criteria": 4,
    "hypothesis": 4,
    "hypotheses": 4,
    "parameter": 4,
    "parameters": 4,
    "geometry": 4,
    "geometries": 4,
    "geometric": 4,
    "velocity": 4,
    "acceleration": 5,
    "equilibrium": 5,
    "coefficient": 4,
    "coefficients": 4,
    "polynomial": 5,
    "derivative": 4,
    "integral": 3,
    "gradient": 3,
    "convergence": 3,
    "divergence": 3,
    "optimization": 5,
    "simulation": 4,
    "validation": 4,
    "calibration": 4,
    "architecture": 4,
    "pipeline": 2,
    "baseline": 2,
    "framework": 2,
    "evaluation": 5,
    "experiment": 4,
    "experimental": 5,
    "statistical": 4,
    "theoretical": 5,
    "empirical": 4,
    "numerical": 4,
    "analytical": 5,
    "computational": 5,
    "efficiency": 4,
    "accuracy": 4,
    "precision": 3,
    "robustness": 3,
    "performance": 3,
    "throughput": 2,
    "latency": 3,
    "reliability": 6,
    "stability": 4,
    "complexity": 4,
    "scalability": 5,
    "variance": 3,
    "covariance": 4,
    "probability": 5,
    "distribution": 4,
    "stochastic": 3,
    "deterministic": 5,
    "eigenvalue": 4,
    "eigenvector": 4,
    "quaternion": 4,
    "jacobian": 4,
    "hessian": 3,
    "fourier": 3,
    "gaussian": 3,
    "bayesian": 3,
    "euclidean": 4,
    "lagrangian": 4,
    "hamiltonian": 5,
    "element": 3,
    "elements": 3,
    "complement": 3,
    "supplement": 3,
    "implement": 3,
    "literature": 4,
    "library": 3,
    "february": 4,
    "wednesday": 2,
    "business": 2,
    "interesting": 4,
    "comfortable": 4,
    "vegetable": 4,
    "chocolate": 3,
    "camera": 3,
    "separate": 3,
    "separately": 4,
    "approximately": 5,
    "immediately": 5,
    "usually": 4,
    "actually": 4,
    "generally": 4,
    "specifically": 5,
    "especially": 4,
    "essentially": 4,
    # Irregular silent-e / non-silent-e / hiatuses
    "recipe": 3,
    "epitome": 4,
    "hyperbole": 4,
    "simile": 3,
    "catastrophe": 4,
    "apostrophe": 4,
    "finale": 3,
    "coyote": 3,
    "karate": 3,
    "peony": 3,
    "cafe": 2,
    "maybe": 2,
    "resume": 2,
    "cliche": 2,
    "facade": 2,
    "plateau": 2,
    "bureau": 2,
    "genre": 2,
    "gauge": 1,
    "vague": 1,
    "plague": 1,
    "league": 1,
    "tongue": 1,
    "colleague": 2,
    "dialogue": 3,
    "catalogue": 3,
    "technique": 2,
    "unique": 2,
    "critique": 2,
    "oblique": 2,
    "antique": 2,
    "fatigue": 2,
    "intrigue": 2,
    "vehicle": 3,
    "vehicles": 3,
    "bicycle": 3,
    "people": 2,
    "isle": 1,
    "aisle": 1,
    "choir": 1,
    "hour": 1,
    "hours": 1,
    "our": 1,
    "ours": 1,
    "fire": 1,
    "wire": 1,
    "tire": 1,
    "entire": 2,
    "desire": 2,
    "require": 2,
    "acquire": 2,
    "quiet": 2,
    "quietly": 3,
    "create": 2,
    "created": 3,
    "creates": 2,
    "creation": 3,
    "creative": 3,
    "poem": 2,
    "poems": 2,
    "poet": 2,
    "poetry": 3,
    "chaos": 2,
    "idea": 3,
    "ideas": 3,
    "ideal": 3,
    "real": 1,
    "really": 2,
    "reality": 4,
    "realize": 3,
    "fluid": 2,
    "fluids": 2,
    "dual": 2,
    "fuel": 2,
    "cruel": 2,
    "trial": 2,
    "trials": 2,
    "prior": 2,
    "ratio": 3,
    "ratios": 3,
    "period": 3,
    "periods": 3,
    "scenario": 4,
    "scenarios": 4,
    "video": 3,
    "stereo": 3,
    "theory": 3,
    "theories": 3,
    "biology": 4,
    "value": 2,
    "values": 2,
    "valued": 2,
    "issue": 2,
    "issues": 2,
    "issued": 2,
    "continue": 3,
    "continued": 3,
    "continues": 3,
    "argue": 2,
    "argued": 2,
    "rescue": 2,
    "true": 1,
    "blue": 1,
    "due": 1,
    "view": 1,
    "views": 1,
    "review": 2,
    "through": 1,
    "though": 1,
    "although": 2,
    "thought": 1,
    "enough": 2,
    "tough": 1,
    "rough": 1,
    "naked": 2,
    "wicked": 2,
    "sacred": 2,
    "crooked": 2,
    "ragged": 2,
    "rugged": 2,
    "beloved": 3,
    "learned": 2,
    "aged": 1,
    "does": 1,
    "goes": 1,
    "shoe": 1,
    "shoes": 1,
    "eye": 1,
    "eyes": 1,
    "once": 1,
    "one": 1,
    "none": 1,
    "some": 1,
    "come": 1,
    "done": 1,
    "gone": 1,
    "have": 1,
    "give": 1,
    "live": 1,
    "love": 1,
    "move": 1,
    "prove": 1,
    "whose": 1,
    "where": 1,
    "there": 1,
    "here": 1,
    "were": 1,
    "are": 1,
    "the": 1,
    "they": 1,
}

# Portuguese vowel definitions
_PT_VOWELS = frozenset("aeiouáéíóúâêôàãõü")
_PT_ACCENTED_VOWELS = frozenset("áéíóúâêôà")
_PT_ALL_ACCENTED = frozenset("áéíóúâêôàãõ")

_PT_FALLING_DIPHTHONGS = frozenset({
    "ai", "ei", "oi", "ui", "au", "eu", "ou",
    "ái", "éi", "ói", "úi", "áu", "éu", "óu",
    "ão", "ãe", "õe",
})
_PT_RISING_DIPHTHONGS = frozenset({"ia", "ie", "io", "ua", "ue", "uo"})
_PT_TRIPHTHONGS = frozenset({"uai", "uei", "uiu", "uou", "uão", "uõe", "uam"})


def has_cmudict() -> bool:
    """Return True if the optional `cmudict` package is installed and loadable."""
    global _CMU_DICT, _CMU_LOAD_ATTEMPTED
    if not _CMU_LOAD_ATTEMPTED:
        _CMU_LOAD_ATTEMPTED = True
        try:
            import cmudict  # type: ignore[import-not-found]

            _CMU_DICT = cmudict.dict()
        except Exception:
            _CMU_DICT = None
    return _CMU_DICT is not None


def _get_cmudict() -> dict[str, list[list[str]]] | None:
    has_cmudict()
    return _CMU_DICT


def syllable_backend_for(lang: str) -> str:
    """Return a human-readable identifier for the active syllable backend."""
    if lang == "pt":
        return "phonetic_pt"
    return "cmudict" if has_cmudict() else "fallback_en"


def _count_syllables_en_rules(word: str) -> int:
    """Zero-dependency rule-based + irregular-table English syllable counter."""
    w = _EN_WORD_CLEAN_RE.sub("", word.lower())
    if not w:
        return 0

    if w in _EN_IRREGULAR_SYLLABLES:
        return _EN_IRREGULAR_SYLLABLES[w]

    if len(w) <= 3:
        return 1

    # Normalize qu -> kw so 'u' in 'qu' is not treated as a vowel nucleus
    w = re.sub(r"qu([aeiouy])", r"kw\1", w)

    # Leading or intervocalic 'y' acts as a consonant (yes, beyond, layer, royal)
    chars = list(w)
    for idx, ch in enumerate(chars):
        if ch == "y":
            next_is_vowel = idx + 1 < len(chars) and chars[idx + 1] in "aeiou"
            if idx == 0 or next_is_vowel:
                chars[idx] = "j"
    w = "".join(chars)

    if w in _EN_IRREGULAR_SYLLABLES:
        return _EN_IRREGULAR_SYLLABLES[w]

    # Handle -ed endings
    if w.endswith("ed") and len(w) > 3:
        if re.search(r"[^aeiouyl]led$", w):
            # e.g., sampled, handled -> sample, handle
            w = w[:-1]
        elif not w.endswith(("ted", "ded")):
            w = w[:-2]

    # Handle -es endings
    if w.endswith("es") and len(w) > 3:
        if re.search(r"(?:ches|shes|sses|xes|zes|ces|ges)$", w):
            pass
        elif re.search(r"[^aeiouy]les$", w):
            w = w[:-1]
        elif re.search(r"[bcdfghjklmnpqrstvwxz]es$", w) and not w.endswith("ies"):
            w = w[:-2]

    # Remove silent internal 'e' before -ly, -ment, -ness, -ful, -less
    w = re.sub(
        r"([aeiouy][^aeiouyl])e(ly|ment|ness|ful|less)$",
        r"\1\2",
        w,
    )

    # Handle silent trailing -e (keep consonant+le, consonant+re, and -ee/-oe/-ie/-ye/-ue)
    if w.endswith("e") and len(w) > 2:
        if re.search(r"[^aeiouy][lr]e$", w):
            pass
        elif w[-2] in "aeioy":
            pass
        elif w.endswith("ue") and len(w) >= 3 and w[-3] not in "qg":
            # e.g., value, issue, continue -> keep 'u' nucleus, drop silent trailing e
            w = w[:-1]
        else:
            w = w[:-1]

    # Count contiguous vowel groups
    groups = re.findall(r"[aeiouy]+", w)
    count = len(groups)

    # Add hiatus splits for adjacent vowels that are normally two syllables in English
    # Exclude -tion/-sion/-cion/-xion and [cstg]ia/[cstg]io/[cstg]ie patterns
    hiatus_matches = re.finditer(r"[aeiouy]{2,}", w)
    for m in hiatus_matches:
        seq = m.group(0)
        start = m.start()
        prev_ch = w[start - 1] if start > 0 else ""
        if len(seq) == 2:
            if seq in ("io", "ia", "ie") and prev_ch in "cstgx":
                continue
            if seq in ("ia", "io", "iu", "ua", "uo", "eo", "ii", "ao"):
                count += 1
            elif seq == "ea" and prev_ch == "r" and start == 1:
                # e.g., react, reaction
                count += 1
            elif seq == "ea" and w[start : start + 3] in ("ear",) and prev_ch == "l":
                # e.g., linear, nuclear handled when ending in -ear? (Note 'clear' = 1)
                if w.endswith(("near", "lear")) and len(w) >= 5:
                    count += 1
        elif len(seq) >= 3:
            # Sequences of 3+ vowels (e.g., quietus, continuous, evaluation)
            if seq not in ("eau", "ieu", "iou"):
                count += 1

    return max(1, count)


def count_syllables_en(word: str) -> int:
    """Count syllables in an English word using cmudict if available, else fallback."""
    if not _ALPHA_RE.search(word):
        return 0

    parts = [p for p in re.split(r"[-/—–]", word.strip()) if _ALPHA_RE.search(p)]
    if len(parts) > 1:
        return max(1, sum(count_syllables_en(p) for p in parts))

    cleaned = word.strip().lower()
    if cleaned.endswith(("'s", "’s")):
        cleaned = cleaned[:-2]
    elif cleaned.endswith(("'", "’")):
        cleaned = cleaned[:-1]
    cleaned = _EN_WORD_CLEAN_RE.sub("", cleaned)
    if not cleaned:
        return 0

    cmu = _get_cmudict()
    if cmu is not None:
        prons = cmu.get(cleaned)
        if prons:
            counts = [
                sum(1 for phoneme in pron if phoneme and phoneme[-1].isdigit())
                for pron in prons
            ]
            valid = [c for c in counts if c > 0]
            if valid:
                return min(valid)

    return _count_syllables_en_rules(cleaned)


def _count_pt_part(part: str) -> int:
    """Count syllables in a single hyphenless Portuguese word part."""
    w = _PT_WORD_CLEAN_RE.sub("", part.lower())
    if not w:
        return 0

    # Replace silent 'u' in qu / gu before e, é, ê, i, í (unless ü is used)
    # Mark kept 'u' after q/g (before a, o, ã, õ) with a tag by keeping original string info
    # We transform qu/gu + [eéiêí] -> q/g + vowel so 'u' does not join vowel clusters.
    transformed: list[str] = []
    after_qg_marker: list[bool] = []
    i = 0
    while i < len(w):
        if (
            w[i] in ("q", "g")
            and i + 2 < len(w)
            and w[i + 1] == "u"
            and w[i + 2] in "eéiêí"
        ):
            transformed.append(w[i])
            after_qg_marker.append(False)
            i += 2  # skip silent 'u'
            continue
        transformed.append(w[i])
        after_qg_marker.append(False)
        i += 1

    norm = "".join(transformed)
    has_earlier_accent = False
    syllables = 0
    idx = 0
    n = len(norm)

    while idx < n:
        ch = norm[idx]
        if ch not in _PT_VOWELS:
            idx += 1
            continue

        # Collect contiguous vowel cluster [idx .. end)
        end = idx + 1
        while end < n and norm[end] in _PT_VOWELS:
            end += 1

        cluster = norm[idx:end]
        prev_char = norm[idx - 1] if idx > 0 else ""
        after_qg = prev_char in ("q", "g") and cluster.startswith("u")
        at_word_end = end == n or (end == n - 1 and norm[end] == "s")
        next_tail = norm[end:]

        # Walk within the vowel cluster left-to-right
        c_idx = 0
        c_len = len(cluster)
        while c_idx < c_len:
            rem = cluster[c_idx:]

            # Check triphthongs (only valid after q/g)
            if (
                c_idx == 0
                and after_qg
                and len(rem) >= 3
                and rem[:3] in _PT_TRIPHTHONGS
            ):
                syllables += 1
                if any(c in _PT_ACCENTED_VOWELS for c in rem[:3]):
                    has_earlier_accent = True
                c_idx += 3
                continue

            # Check 2-vowel sequences
            if len(rem) >= 2:
                pair = rem[:2]
                second_is_accented = pair[1] in _PT_ACCENTED_VOWELS

                # Accented second vowel forces a hiatus (e.g., sa-ú-de, pa-ís, ra-í-zes, con-te-ú-do, a-é-reo)
                if second_is_accented:
                    syllables += 1
                    if pair[0] in _PT_ACCENTED_VOWELS:
                        has_earlier_accent = True
                    c_idx += 1
                    continue

                # Falling & nasal diphthongs
                if pair in _PT_FALLING_DIPHTHONGS:
                    # Prefix 're-' before 'un-' forms a hiatus (re-u-nir, re-u-ni-ão)
                    if idx == 1 and c_idx == 0 and norm.startswith("reun"):
                        syllables += 1
                        c_idx += 1
                        continue
                    # Check hiatus before nasal nh or syllable-closing l/m/n/r/z
                    is_final_in_cluster = c_idx + 2 == c_len
                    breaks_to_hiatus = False
                    if (
                        is_final_in_cluster
                        and pair[0] not in _PT_ALL_ACCENTED
                        and pair not in ("ão", "ãe", "õe")
                    ):
                        if next_tail.startswith("nh"):
                            breaks_to_hiatus = True
                        elif next_tail and next_tail[0] in ("l", "m", "n", "r", "z"):
                            # Syllable-closing consonant: at end of word or followed by another consonant
                            if len(next_tail) == 1 or next_tail[1] not in _PT_VOWELS:
                                breaks_to_hiatus = True

                    if breaks_to_hiatus:
                        syllables += 1
                        c_idx += 1
                        continue

                    syllables += 1
                    if pair[0] in _PT_ACCENTED_VOWELS:
                        has_earlier_accent = True
                    c_idx += 2
                    continue

                # Rising diphthongs (ia, ie, io, ua, ue, uo)
                if pair in _PT_RISING_DIPHTHONGS:
                    is_qg_pair = c_idx == 0 and after_qg and pair.startswith("u")
                    is_post_tonic_final = (
                        c_idx + 2 == c_len
                        and at_word_end
                        and has_earlier_accent
                    )
                    if is_qg_pair or is_post_tonic_final:
                        syllables += 1
                        c_idx += 2
                        continue

            # Single vowel (hiatus or single nucleus)
            syllables += 1
            if rem[0] in _PT_ACCENTED_VOWELS:
                has_earlier_accent = True
            c_idx += 1

        idx = end

    return max(1, syllables)


def count_syllables_pt(word: str) -> int:
    """Count syllables in a Portuguese word using phonetic diphthong/hiatus rules."""
    if not _ALPHA_RE.search(word):
        return 0

    parts = [p for p in re.split(r"[-/—–]", word.strip()) if _ALPHA_RE.search(p)]
    if not parts:
        return 0
    return max(1, sum(_count_pt_part(p) for p in parts))


def count_syllables(word: str, lang: str) -> int:
    """Count syllables in a word for the given language ('en' or 'pt')."""
    if lang == "pt":
        return count_syllables_pt(word)
    if lang == "en":
        return count_syllables_en(word)
    raise ValueError(f"Unsupported language: {lang!r}. Expected 'en' or 'pt'.")
