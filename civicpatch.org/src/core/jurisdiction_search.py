"""The two halves of jurisdiction search. Pure — no I/O.

Search is one match between a stored haystack and a typed needle, and this module builds
both ends:

    write time, once per sync    build_search_text  ->  "seattle city wa washington"
    read time, once per keystroke build_tsquery      ->  "seattle:* & wa:*"

    ... WHERE to_tsvector('simple', search_text) @@ to_tsquery('simple', <tsquery>)

They live together because they share one contract — both lowercase, both treat
punctuation as a separator. If the two ever disagreed on normalization, search would
quietly match nothing, and no test of either function alone would notice.

Putting the state name and code into the stored text is what lets the query stay
literal: "seattle wa" and "seattle washington" both hit because the row carries both
forms, so nothing has to parse a state qualifier out of what the user typed.
"""

import re

SEARCH_TEXT_FIELDS = ("name", "display_name")

# Two characters before searching: a single letter matches most of the corpus and the
# result set is meaningless until the second keystroke.
MIN_QUERY_LENGTH = 2

_TOKEN_SEPARATOR = re.compile(r"[^0-9a-z]+")


def _tokenize(query: str) -> list[str]:
    if len(query.strip()) < MIN_QUERY_LENGTH:
        return []
    return [token for token in _TOKEN_SEPARATOR.split(query.lower()) if token]


def build_tsquery(query: str) -> str:
    # Tokens are rebuilt from scratch rather than escaped, so no tsquery operator a user
    # types (& | ! <-> parens) can survive into the query. Empty means "do not search".
    tokens = _tokenize(query)
    return " & ".join(f"{token}:*" for token in tokens)


def build_fuzzy_tokens(query: str) -> list[str]:
    # Tier 2 matches each token separately, ANDed — not the query as one string.
    # word_similarity matches a single continuous extent, so "seatle wa" as one unit
    # matches nothing, while "seatle" AND "wa" finds Seattle. Same tokenizer as tier 1 so
    # both tiers agree on what a token is. Empty means "do not search".
    return _tokenize(query)


def build_search_text(entry: dict, state: str, state_name: str | None) -> str:
    # Must stay equivalent to migration 104's backfill expression, or a row's
    # search_text depends on whether it was backfilled or synced.
    parts = [entry.get(field) for field in SEARCH_TEXT_FIELDS]
    parts += [state, state_name]
    return " ".join(part.strip() for part in parts if part and part.strip()).lower()
