"""A state's posts as spreadsheet rows — the seats, held or not.

Its own tab because the roster is one row per membership and cannot show an empty seat, which
is what stops "Selectboard Member" being minted beside "Select Board Member".

Keys in are not header names here: they come from `list_page_for_state`, which
`/api/v1/posts/bulk` also serves, so its projection is not ours to rename.
"""

HEADERS = [
    "jurisdiction_ocdid",
    "post_id",
    "post_label",
    "post_role_id",
    "post_division_ocdid",
    # A post is a group of interchangeable seats, so this is how many the body has.
    "post_headcount",
]

# `_is_verified` and `_is_tracked` are absent: review-queue state, not facts about the seat.


def _text(value) -> str:
    return "" if value is None else str(value)


def to_row(post: dict) -> list[str]:
    return [
        _text(post.get("jurisdiction_ocdid")),
        _text(post.get("id")),
        _text(post.get("label")),
        _text(post.get("role_id")),
        _text(post.get("division_ocdid")),
        _text(post.get("_headcount")),
    ]


def to_rows(posts: list[dict]) -> list[list[str]]:
    return [to_row(post) for post in posts]
