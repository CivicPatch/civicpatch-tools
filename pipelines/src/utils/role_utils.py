from typing import Dict, Optional

from rapidfuzz import fuzz, process


def fuzzy_match_role(role: str, role_aliases: Dict[str, str]) -> Optional[str]:
    def prenorm(role_str):
        return role_str.replace("-", " ").lower()

    candidates = {prenorm(k): v for k, v in role_aliases.items()}
    result = process.extractOne(
        prenorm(role), candidates.keys(), scorer=fuzz.ratio, score_cutoff=85
    )
    if result is None:
        return None
    return candidates[result[0]]
