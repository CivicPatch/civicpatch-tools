"""The response shape for posts: nested under the body that holds them.

Pure, so the shape is testable without a database. The SQL that feeds it lives in
`database/posts.py` and `database/organizations.py`, which compose it in `list_by_organization`.

The `_`-prefixed keys marking our non-standard fields are aliased in that query, beside the
values they name, rather than renamed in a second pass here.
"""


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
