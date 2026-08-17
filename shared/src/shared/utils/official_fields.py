from shared.schemas import Official

# Changing this order rewrites the key order of every person in every data file.
OFFICIAL_FIELD_ORDER = tuple(Official.model_fields)


# Reorders only — values are the originals, so ruamel's preserved quoting survives.
# Fields not declared on `Official` keep their relative order at the end.
def order_official_fields(entry: dict) -> dict:
    ordered = {key: entry[key] for key in OFFICIAL_FIELD_ORDER if key in entry}
    undeclared = {key: value for key, value in entry.items() if key not in ordered}
    return {**ordered, **undeclared}


def office_name_to_labels(office_name: str) -> list[str]:
    """Split a rendered office name back into the labels it was joined from.

    Every part is kept, not just the ones resolving to a role: an unrecognised label is
    exactly what the candidate path needs to see.
    """
    if not office_name or office_name == "Unknown Office":
        return []
    return [part.strip() for part in office_name.split(" - ") if part.strip()]
