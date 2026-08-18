"""Raw label -> role, division, other designations, unmatched text.

A longest-match gazetteer cascade: match spans against the known alias tables, consume what
matched, and let the next pass see only what survives. Designations run before roles because
they are a closed vocabulary requiring a value, so they are the hardest to be wrong about. Nothing is invented and nothing is discarded — text
the parser cannot classify survives as `unmatched` so triage can act on it later, rather than being dropped the way `normalize_designations` drops
"(North)" today.

Lives in `shared` because cp.org does the decomposing; the pipeline calls it transiently to
make crawl/keep decisions and throws the result away.
"""

import re
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel

from shared.utils import config_utils
from shared.utils.divisions import (
    format_division,
    jurisdiction_ocdid_to_division_ocdid,
)
from shared.utils.taxonomy import Taxonomy, lookup_key, normalize_word, role_sort_key

_EDGE_PUNCTUATION = re.compile(r"^\W+|\W+$")

# Wards and districts are named by direction as often as by number, in either word order
# ("Ward East", "North Ward"). A closed set, so it can be trusted before the key where an
# open-ended rule cannot.
_CARDINALS = frozenset(
    {
        "north",
        "south",
        "east",
        "west",
        "northeast",
        "northwest",
        "southeast",
        "southwest",
        "central",
    }
)


class Division(BaseModel):
    designation: str  # canonical designation key, e.g. "ward"
    value: str  # e.g. "3", "east"


class ParsedLabel(BaseModel):
    # The highest-priority of `roles`, or None when nothing in the text resolves to a known
    # role. Priority, not position: a label naming two offices must give the same answer
    # whichever order they appear in.
    role: Optional[str] = None
    # Every role the label names, in the order the text gives them. A well-formed label names
    # one — two means the extractor did not split a person's offices into separate records,
    # and the loser must survive here rather than be dropped, since whether it becomes a
    # second post is still an open question.
    roles: List[str] = []
    # The primary of `divisions`. None means the label names no geographic area, which is
    # what at-large means. Turning that into an ocdid needs the jurisdiction, so it is
    # `division_ocdid`'s job, not this one's: most callers only ask boolean questions and
    # have no jurisdiction to hand.
    division: Optional[Division] = None
    # Every area the label names, in the order the text gives them. A label naming two is
    # usually one area under two names ("District 1 (East Ward)"), and the loser is kept
    # because the local name is still evidence for matching records.
    divisions: List[Division] = []
    # Designations that name no area — "Place 3", "Position 2", "At-Large A". They pick out
    # one office within a body, so they belong on `posts.label`, not the division.
    other_designations: List[str] = []
    # Text that matched no alias, in original case — vocabulary we do not have yet. Named
    # for what the parser established, not for what happens next: triage promotes some to a
    # role or a post and marks others `excluded` ("City Attorney" is not a role we are
    # missing), and the text alone cannot say which. Empty means the label was understood.
    unmatched: List[str] = []


class _Word(BaseModel):
    key: str  # normalized, for matching
    token: int  # index of the original whitespace-token it came from


def _words(label: str) -> List[_Word]:
    """Match-keys paired with the original token they came from.

    One token can yield two keys ("At-Large" -> "at", "large") because `lookup_key` turns
    hyphens into spaces, so the mapping is many-to-one and the token index is what lets
    unmatched be rebuilt from the untouched original text.
    """
    words: List[_Word] = []
    for index, token in enumerate(label.split()):
        cleaned = _EDGE_PUNCTUATION.sub("", token)
        for key in lookup_key(cleaned).split():
            words.append(_Word(key=key, token=index))
    return words


def _find_alias(
    words: List[_Word], aliases: Dict[str, str], start: int = 0
) -> Optional[Tuple[str, int, int]]:
    """Longest alias match at or after `start`, as (canonical, first_word, last_word)."""
    for first in range(start, len(words)):
        for last in range(len(words), first, -1):
            key = " ".join(w.key for w in words[first:last])
            if key in aliases:
                return (aliases[key], first, last - 1)
    return None


def _value_index(
    words: List[_Word],
    first: int,
    last: int,
    taxonomy: Taxonomy,
    aliases: Dict[str, str],
) -> Optional[int]:
    """Index of the single word acting as the designation's value, if there is one.

    Exactly one word: "Ward 3" and "Ward East" are divisions, "Ward 3 President" is not —
    trailing text belongs to the role or to unmatched, never to the identifier.

    Either side of the key, because "3rd Ward" and "North Ward" are as real as "Ward 3".
    Before wins the tie: "Place 2 (West Ward) and Mayor Pro-Tem" would otherwise read the
    conjunction as the value, which cost `ward:west` on real model output.
    """
    before = first - 1
    if before >= 0 and _is_value(words[before].key):
        return before

    after = last + 1
    if after < len(words):
        key = words[after].key
        if _is_value(key) and key not in aliases and key not in taxonomy.role_aliases:
            return after
    return None


def _designation_value(word: str) -> str:
    """The stored form of a designation's value.

    Leading zeros are dropped because the value composes a published ocdid: "Ward 03"
    and "Ward 3" are one division, and minting both leaves two ids nothing can tell
    apart afterwards. `normalize_word` handles ordinals and roman numerals but not
    this, since it also builds match keys where "03" and "3" are already the same.
    """
    value = normalize_word(word)
    if not value.isdigit():
        return value
    stripped = value.lstrip("0")
    return stripped or "0"


def _is_value(key: str) -> bool:
    """A number, a cardinal direction, or a single letter — the three closed sets a real
    designation value comes from ("Ward 3", "District IV", "North Ward", "At-Large A").

    Deliberately closed. Accepting any word instead read "District Attorney" as
    `district:attorney` and published it as an OCD division id for a county prosecutor.
    """
    return (
        normalize_word(key).isdigit()
        or key in _CARDINALS
        or (len(key) == 1 and key.isalpha())
    )


def _unmatched(label: str, used_tokens: set) -> List[str]:
    """Contiguous runs of unmatched original tokens, in order and in original case.

    Runs rather than one joined string: "Foo Ward 3 Bar" leaves two unrelated fragments, and
    joining them would produce one nonsense term instead of two real ones.

    Pure punctuation ends a run without joining it: a separator left behind by removing what
    it separated ("Council Member - Place 3" -> "-") is not surviving text.
    """
    runs: List[str] = []
    current: List[str] = []
    for index, token in enumerate(label.split()):
        if index not in used_tokens and _EDGE_PUNCTUATION.sub("", token):
            current.append(token)
            continue
        if current:
            runs.append(" ".join(current))
            current = []
    if current:
        runs.append(" ".join(current))
    return runs


def parse_label(label: str, taxonomy: Taxonomy) -> ParsedLabel:
    words = _words(label)
    designation_aliases = taxonomy.designation_aliases
    configs = config_utils.get_designations()

    used: set = set()
    divisions: List[Division] = []
    other_designations: List[str] = []

    found = _find_alias(words, designation_aliases)
    while found:
        canonical, first, last = found
        value_index = _value_index(words, first, last, taxonomy, designation_aliases)
        span = list(range(first, last + 1))
        if value_index is not None:
            span.append(value_index)
            value = _designation_value(words[value_index].key)
            if configs.get(canonical, {}).get("is_division"):
                found_division = Division(designation=canonical, value=value)
                if found_division not in divisions:
                    divisions.append(found_division)
            else:
                other_designations.append(f"{canonical.title()} {value.title()}")
        elif configs.get(canonical, {}).get("is_valueless"):
            # Consumed and recorded nowhere, deliberately. A valueless designation says
            # only that the post covers the whole jurisdiction, which the division
            # already carries — keeping "At-Large" would put it in the post label and
            # split one seat into two posts. "At-Large A" takes the branch above, where
            # the value is the thing that tells two posts apart.
            pass
        else:
            # A keyword with no valid value is not a designation. Leaving the tokens
            # unconsumed sends them to `unmatched`, where an unknown office belongs.
            found = _find_alias(words, designation_aliases, start=last + 1)
            continue
        used.update(words[i].token for i in span)
        found = _find_alias(words, designation_aliases, start=max(span) + 1)

    roles: List[str] = []
    role_match = _find_alias(words, taxonomy.role_aliases)
    while role_match:
        canonical, first, last = role_match
        if canonical not in roles:
            roles.append(canonical)
        used.update(words[i].token for i in range(first, last + 1))
        role_match = _find_alias(words, taxonomy.role_aliases, start=last + 1)

    return ParsedLabel(
        role=_highest_priority(roles, taxonomy),
        roles=roles,
        division=_primary_division(divisions),
        divisions=divisions,
        other_designations=other_designations,
        unmatched=_unmatched(label, used),
    )


def _primary_division(divisions: List[Division]) -> Optional[Division]:
    """A numbered area wins over a named one: "District 1 (East Ward)" is one area under an
    official identifier and a local nickname, and the number is the identifier. An ocdid
    needs a single answer, and taking the last one found made it depend on word order.

    Ties keep page order, where the primary is normally stated first.
    """
    if not divisions:
        return None
    return next(
        (division for division in divisions if division.value.isdigit()), divisions[0]
    )


def _highest_priority(roles: List[str], taxonomy: Taxonomy) -> Optional[str]:
    """Lowest priority index wins: Mayor Pro Tem outranks Council Member wherever each sits
    in the string. `role_sort_key` already ranks unknown roles last and breaks ties by name,
    so the answer does not depend on dict ordering."""
    if not roles:
        return None
    return min(roles, key=lambda role: role_sort_key(role, taxonomy))


def division_ocdid(parsed: ParsedLabel, jurisdiction_ocdid: str) -> str:
    """Never empty: a label naming no area belongs to the jurisdiction's own division."""
    base = jurisdiction_ocdid_to_division_ocdid(jurisdiction_ocdid)
    if not parsed.division:
        return base
    return format_division(base, parsed.division.designation, parsed.division.value)
