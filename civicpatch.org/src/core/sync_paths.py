def classify_path(path: str):
    if (
        path.startswith("data_source/")
        and path.endswith("/jurisdictions.yml")
        and path.count("/") == 3
    ):
        return "jurisdictions"
    if path.startswith("data/") and path.endswith(".yml") and path.count("/") == 3:
        return "people"
    else:
        return None
