from urllib.parse import urlparse


def _owner_repo(open_data_repo_url: str) -> str:
    parsed = urlparse(open_data_repo_url)
    path = parsed.path.rstrip("/")
    if not path.startswith("/repos/"):
        raise ValueError(
            f"Expected a GitHub API URL of the form https://api.github.com/repos/<owner>/<repo>, "
            f"got: {open_data_repo_url!r}"
        )
    return path[len("/repos/"):]


def derive_git_clone_url(open_data_repo_url: str) -> str:
    return f"https://github.com/{_owner_repo(open_data_repo_url)}.git"


def derive_raw_base_url(open_data_repo_url: str, ref: str = "refs/heads/main") -> str:
    return f"https://raw.githubusercontent.com/{_owner_repo(open_data_repo_url)}/{ref}"
