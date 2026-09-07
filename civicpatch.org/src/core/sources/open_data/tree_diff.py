from pydantic import BaseModel


class TreeDiff(BaseModel):
    changed: list[str]
    deleted: list[str]


# {path: sha}
def diff_tree(current: dict[str, str], stored: dict[str, str]):
    changed: list[str] = []
    deleted: list[str] = []
    for current_path, current_sha in current.items():
        stored_sha = stored.get(current_path)
        if current_sha != stored_sha:
            changed.append(current_path)

    for stored_path, stored_sha in stored.items():
        if current.get(stored_path) is None:
            deleted.append(stored_path)

    return TreeDiff(changed=changed, deleted=deleted)
