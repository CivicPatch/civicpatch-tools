"""`core/` is the functional core: no I/O, no clock, no randomness.

The convention already holds for imports and has never been enforced. It is enforced here
because the projection refactor makes it load-bearing: `derive_roster(facts, as_of)` must give
the same roster for the same facts, at publish, in the history loop and in a rebuild, or
`membership_terms` and the projection can disagree with each other (R6).

Parsing rather than importing: an import would run module-level code and would only catch a
forbidden call if a test happened to reach that line.
"""

import ast
import os

import pytest

_CORE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src",
    "core",
)

# Everything the imperative shell owns. `shared` is absent on purpose: it holds pure helpers
# (name, phone, url, taxonomy) that `core/` is meant to use.
FORBIDDEN_IMPORTS = ("database", "lib", "services", "psycopg", "psycopg_pool", "environment")

# Ambient inputs. A resolver takes time as a parameter and mints ids deterministically, so any
# of these means a function's answer depends on when it ran.
FORBIDDEN_CALLS = (
    "datetime.now",
    "datetime.utcnow",
    "date.today",
    "time.time",
    "uuid.uuid1",
    "uuid.uuid4",
    "os.getenv",
    "get_env_vars",
    "random.random",
    "random.choice",
)

FORBIDDEN_ATTRIBUTES = ("os.environ",)

# The one live violation, with the step that deletes it. `people_derivation` stamps
# `updated_at` on the person it builds; `people.updated_at` is dropped by step 19 of
# `.scratch/2026-09-17-plan-projector-refactor.md`, and this entry goes with it.
ALLOWED = {("people_derivation.py", "datetime.now")}


def _core_files() -> list[str]:
    found = []
    for directory, _, filenames in os.walk(_CORE):
        for filename in filenames:
            if filename.endswith(".py"):
                found.append(os.path.join(directory, filename))
    return sorted(found)


def _dotted(node: ast.AST) -> str:
    """"datetime.now" for `datetime.now`, "get_env_vars" for a bare name, "" for anything else."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return ""


def _violations(path: str) -> list[str]:
    relative = os.path.relpath(path, _CORE)
    with open(path) as handle:
        tree = ast.parse(handle.read(), filename=path)

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    found.append(f"imports {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                found.append(f"imports from {node.module}")
        elif isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name in FORBIDDEN_CALLS and (os.path.basename(relative), name) not in ALLOWED:
                found.append(f"calls {name}")
        elif isinstance(node, ast.Attribute):
            name = _dotted(node)
            if name in FORBIDDEN_ATTRIBUTES:
                found.append(f"reads {name}")
    return found


@pytest.mark.unit
@pytest.mark.parametrize("path", _core_files(), ids=lambda p: os.path.relpath(p, _CORE))
def test_core_module_is_pure(path):
    found = _violations(path)
    assert not found, (
        f"{os.path.relpath(path, _CORE)} is in the functional core and "
        f"{', '.join(found)}. Move the I/O or the clock to services/ and pass the "
        f"result in as an argument."
    )


@pytest.mark.unit
def test_the_allow_list_only_names_live_violations():
    """An entry that no longer matches anything is an entry someone will trust later."""
    for filename, call in sorted(ALLOWED):
        path = os.path.join(_CORE, filename)
        assert os.path.exists(path), f"{filename} is allow-listed but does not exist"
        with open(path) as handle:
            tree = ast.parse(handle.read(), filename=path)
        calls = [_dotted(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)]
        assert call in calls, f"{filename} no longer calls {call}; drop it from ALLOWED"
