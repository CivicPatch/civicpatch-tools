from shared.schemas import Official

# Changing this order rewrites the key order of every person in every data file.
OFFICIAL_FIELD_ORDER = tuple(Official.model_fields)


# Reorders only — values are the originals, so ruamel's preserved quoting survives.
# Fields not declared on `Official` keep their relative order at the end.
def order_official_fields(entry: dict) -> dict:
    ordered = {key: entry[key] for key in OFFICIAL_FIELD_ORDER if key in entry}
    undeclared = {key: value for key, value in entry.items() if key not in ordered}
    return {**ordered, **undeclared}
