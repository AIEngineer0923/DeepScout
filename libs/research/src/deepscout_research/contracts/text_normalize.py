"""Small multilingual normalization layer for deterministic research matching."""

from __future__ import annotations

import re
import unicodedata

_PREFIX_ALIASES = {
    "anni": "year",
    "biodivers": "biodiversity",
    "compar": "compare",
    "composiz": "composition",
    "contribut": "contribution",
    "densit": "density",
    "esperiment": "experiment",
    "global": "global",
    "incerte": "uncertainty",
    "limit": "limitation",
    "misur": "measurement",
    "modell": "model",
    "observ": "observed",
    "osserv": "observed",
    "recuper": "recovery",
    "recover": "recovery",
    "risultat": "result",
    "sedimentaz": "sedimentation",
    "stud": "study",
    "trattament": "treatment",
}

_EXACT_ALIASES = {
    "metodi": "method",
    "methods": "method",
    "offerta": "supply",
    "organismi": "organism",
    "riser": "riser",
    "ruolo": "role",
    "stato": "status",
    "tecnologie": "technology",
    "years": "year",
}


def normalized_research_tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(character for character in folded if not unicodedata.combining(character))
    raw = re.findall(r"[a-z0-9]{3,}", ascii_text)
    normalized: set[str] = set()
    for token in raw:
        exact = _EXACT_ALIASES.get(token)
        if exact:
            normalized.add(exact)
            continue
        alias = next(
            (value for prefix, value in _PREFIX_ALIASES.items() if token.startswith(prefix)),
            None,
        )
        normalized.add(alias or token)
    return normalized
