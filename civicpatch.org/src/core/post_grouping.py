"""The response shape for posts: nested under their body, each marked verified or not.

Pure, so the shape is testable without a database. The SQL that feeds it lives in
`database/posts.py` and `database/organizations.py`, which compose it in `list_by_organization`.
"""

# Ours — no civic standard models verification, so it takes the underscore. A consumer that
# drops every `_*` key is left with a conforming record.
VERIFIED_KEY = "_verified"


def mark_verified(rows: list[dict]) -> list[dict]:
    """Rename the `verified` boolean to `_verified`. Present on every row, never inferred.

    Absence is ambiguous — a missing key could mean endorsed, or an older API version — and
    silence must not read as trustworthy on a provenance flag.
    """
    return [
        {
            **{key: value for key, value in row.items() if key != "verified"},
            VERIFIED_KEY: bool(row.get("verified")),
        }
        for row in rows
    ]


def group_by_organization(
    organization_rows: list[dict], post_rows: list[dict]
) -> list[dict]:
    """Posts nested under their body, preserving the order each query returned.

    An empty organization is kept — that is the state every jurisdiction is in before its
    first scrape. An orphaned post is dropped rather than raising; a read should not be the
    thing that discovers a broken FK.
    """
    by_organization: dict[str, list[dict]] = {
        row["id"]: [] for row in organization_rows
    }
    for post in post_rows:
        if post["organization_id"] in by_organization:
            by_organization[post["organization_id"]].append(post)

    return [
        {**organization, "posts": by_organization[organization["id"]]}
        for organization in organization_rows
    ]
