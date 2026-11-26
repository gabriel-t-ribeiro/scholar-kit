"""Zero-dependency EN/PT language detection."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-zA-ZçáéíóúâêôãõàüÁÉÍÓÚÂÊÔÃÕÀÜ]+")

_EN_STOPWORDS = frozenset({
    "the", "and", "of", "to", "is", "it", "its", "that", "this", "these", "those",
    "for", "with", "from", "are", "was", "were", "be", "been", "being", "by", "as",
    "an", "or", "in", "on", "at", "have", "has", "had", "not", "but", "can", "will",
    "would", "should", "could", "may", "might", "their", "they", "them", "we", "our",
    "you", "your", "he", "she", "his", "her", "which", "who", "whom", "where", "when",
    "while", "what", "how", "why", "also", "however", "therefore", "moreover",
    "furthermore", "between", "through", "into", "about", "after", "before", "under",
    "over", "such", "each", "other", "both", "than", "then", "only", "most", "more",
    "using", "used", "based", "shown", "results", "figure", "section", "method",
})

_PT_STOPWORDS = frozenset({
    "que", "não", "com", "para", "uma", "um", "uns", "umas", "por", "mais", "menos",
    "como", "dos", "das", "nos", "nas", "ao", "aos", "à", "às", "do", "da", "os", "as",
    "é", "são", "foi", "foram", "ser", "será", "está", "estão", "estava", "ou", "mas",
    "entre", "sobre", "através", "este", "esta", "estes", "estas", "isto", "esse",
    "essa", "esses", "essas", "isso", "aquele", "aquela", "aquilo", "seu", "sua",
    "seus", "suas", "nosso", "nossa", "nossos", "nossas", "também", "ainda", "quando",
    "onde", "porque", "pelo", "pela", "pelos", "pelas", "pode", "podem", "assim",
    "portanto", "contudo", "todavia", "entretanto", "embora", "além", "apenas",
    "deste", "desta", "destes", "destas", "desse", "dessa", "mesmo", "mesma", "cada",
    "todos", "todas", "então", "devido", "conforme", "segundo", "durante", "enquanto",
    "figura", "tabela", "secção", "seção", "resultados", "análise", "método", "trabalho",
    "apresenta", "utilizando", "sendo", "tendo", "fazendo", "num", "numa", "neste", "nesta",
})

_PT_UNIQUE_CHARS = frozenset("ãõçÃÕÇ")
_PT_ACCENT_CHARS = frozenset("áéíóúâêôàÁÉÍÓÚÂÊÔÀ")


def detect_language(text: str) -> str:
    """Detect whether text is primarily English ('en') or Portuguese ('pt')."""
    if not text or not text.strip():
        return "en"

    tokens = _WORD_RE.findall(text.lower())
    if not tokens:
        return "en"

    en_score = 0.0
    pt_score = 0.0

    for tok in tokens:
        if tok in _EN_STOPWORDS:
            en_score += 2.0
        if tok in _PT_STOPWORDS:
            pt_score += 2.0

        if any(ch in _PT_UNIQUE_CHARS for ch in tok):
            pt_score += 3.0
        elif any(ch in _PT_ACCENT_CHARS for ch in tok):
            pt_score += 1.0

        if tok.endswith(("ção", "ções", "mente", "agem", "igem", "dade", "dades")):
            pt_score += 1.5
        elif tok.endswith(("tion", "tions", "ment", "ments", "ness", "ing", "ough")):
            en_score += 1.0

    if pt_score > en_score:
        return "pt"
    return "en"
