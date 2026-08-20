"""The shape the roster screen renders: posts nested under the body they sit in.

Pure, so the shape is testable without a database. The SQL that feeds it lives in
`database/posts.py` and `database/organizations.py`; the orchestration in `services/posts.py`.
"""


def group_by_organization(
    organization_rows: list[dict], post_rows: list[dict]
) -> list[dict]:
    """Posts nested under their body, preserving the order each query returned.

    An organization with no posts is kept: a body that exists with nothing in it is a real
    state worth showing, and it is the state every jurisdiction is in before its first scrape.

    A post whose organization is missing is dropped rather than raising — a read should not be
    the thing that discovers a broken FK.
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
