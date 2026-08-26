"""The key order of a person in a rendered data file.

Written out rather than derived from a model: it is a contract with the files. An unlisted
field still renders, at the end.
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
