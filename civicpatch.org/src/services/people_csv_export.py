"""The published roster of a state, as a spreadsheet.

One row per active person. It used to export *pending* scrapes as an existing-vs-proposed
diff carrying their review issues; that was a triage report wearing a data export's name, and
the review card is where a diff belongs.
"""

import database.people
import lib.csv as csv_service

_LIST_SEPARATOR = " | "

PEOPLE_CSV_FIELDNAMES = [
    "jurisdiction_ocdid",
    "id",
    "name",
    "other_names",
    "post_label",
    "division_ocdid",
    "phones",
    "emails",
    "urls",
    "source_urls",
    "start_date",
    "end_date",
    "updated_at",
]


def _joined(values: list | None) -> str:
    return _LIST_SEPARATOR.join(values or [])


def _post_labels(person: dict) -> list[str]:
    return [
        membership["post_label"] for membership in person.get("memberships") or []
    ]


def person_row(person: dict) -> dict:
    """One person as a spreadsheet row.

    Every text cell goes through `sanitize` — a name that begins `=` is a formula to Excel,
    and this export is opened in a spreadsheet by definition.
    """
    return {
        "jurisdiction_ocdid": person.get("jurisdiction_ocdid", ""),
        "id": person.get("id", ""),
        "name": csv_service.sanitize(person.get("name") or ""),
        "other_names": csv_service.sanitize(_joined(person.get("other_names"))),
        "post_label": csv_service.sanitize(_joined(_post_labels(person))),
        "division_ocdid": csv_service.sanitize(person.get("division_ocdid") or ""),
        "phones": csv_service.sanitize(_joined(person.get("phones"))),
        "emails": csv_service.sanitize(_joined(person.get("emails"))),
        "urls": csv_service.sanitize(_joined(person.get("urls"))),
        "source_urls": csv_service.sanitize(_joined(person.get("source_urls"))),
        "start_date": csv_service.sanitize(person.get("start_date") or ""),
        "end_date": csv_service.sanitize(person.get("end_date") or ""),
        "updated_at": csv_service.sanitize(person.get("updated_at") or ""),
    }


async def fetch_people_export_rows(state: str) -> list[dict]:
    people = await database.people.get_roster(state=state)
    return [person_row(person) for person in people]
