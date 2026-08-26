"""The key order of a person in a rendered data file, and the one string that is not flat.

Nothing here imports a model. `PERSON_FIELD_ORDER` was `tuple(Official.model_fields)` until
2026-08-25, which made the layout of every file in open-data a side effect of declaration
order in a class that is on its way out. It is a contract with the files, so it is written
as one.

A field added to a model and not listed here still renders — `order_person_fields` keeps
undeclared keys — it just lands at the end until someone places it deliberately.
"""

# Changing this order rewrites the key order of every person in every data file.
PERSON_FIELD_ORDER = (
    "name",
    "other_names",
    "phones",
    "emails",
    "urls",
    "start_date",
    "end_date",
    "office",
    "image",
    "jurisdiction_ocdid",
    "cdn_image",
    "source_urls",
    "updated_at",
    "id",
)


# Reorders only — values are the originals, so ruamel's preserved quoting survives.
def order_person_fields(entry: dict) -> dict:
    ordered = {key: entry[key] for key in PERSON_FIELD_ORDER if key in entry}
    undeclared = {key: value for key, value in entry.items() if key not in ordered}
    return {**ordered, **undeclared}
