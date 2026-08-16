"""Every eval module must still import, and its fixtures must still parse.

This exists because four separate breakages shipped unnoticed:

  - `people_utils.normalize_roles` moved to `taxonomy.py` and gained an argument, so both
    the officials eval and the role-normalization eval died on AttributeError
  - migration 109 renamed `role`/`kind` to `id`/`label`/`status`, so
    `role_normalization/taxonomy.yml` no longer validated against `Role`
  - `validate_cases` still read `entry.kind` and `entry.role`

None were caught, because evals need API keys and money and so are not part of
`mise run tpipes`. But *importing* them needs neither. Every failure above was an
import-time or fixture-parse error — this file would have caught all four in the fast loop.

It deliberately does not score anything or make a network call. It asserts only that the
modules load and their fixtures validate.
"""

import importlib.util
import pathlib
import sys

import pytest
import yaml

pytestmark = pytest.mark.unit

EVALS = pathlib.Path("tests/prompts/tests/evals")
EVAL_MODULES = [
    EVALS / "accuracy.py",
    EVALS / "scoring.py",
    EVALS / "eval_utils.py",
    EVALS / "audit_fixtures.py",
    EVALS / "dashboard_data.py",
    EVALS / "visualize.py",
    EVALS / "test_local_municipal_officials_eval.py",
    EVALS / "test_local_relevant_page_eval.py",
    EVALS / "test_find_jurisdiction_url_eval.py",
]


@pytest.fixture(scope="module", autouse=True)
def _eval_dir_on_path():
    """The eval package relies on its own conftest inserting this; unit tests get no such
    conftest, so do it here rather than making the modules importable some other way."""
    path = str(EVALS.resolve())
    sys.path.insert(0, path)
    yield
    sys.path.remove(path)


@pytest.mark.parametrize("module_path", EVAL_MODULES, ids=lambda p: p.name)
def test_eval_module_imports(module_path):
    assert module_path.exists(), f"{module_path} is gone — update EVAL_MODULES"
    # A distinct module name keeps pytest from collecting these a second time.
    spec = importlib.util.spec_from_file_location(f"_loadcheck_{module_path.stem}", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def test_role_normalization_fixtures_validate():
    """The migration-109 break: `taxonomy.yml` still used `role:`/`kind:` against a `Role`
    model requiring `id`/`label`, and nothing noticed. The test that consumes these now
    lives in tests/unit, so a break there fails directly — this only guards the fixtures."""
    # imported lazily: needs the sys.path fixture above
    from shared.schemas import RoleConfig

    directory = pathlib.Path("tests/unit/utils/role_normalization")
    taxonomy = RoleConfig.model_validate(
        yaml.safe_load((directory / "taxonomy.yml").read_text(encoding="utf-8"))
    )
    assert taxonomy.roles, "taxonomy.yml parsed to zero roles"
    assert yaml.safe_load((directory / "cases.yml").read_text(encoding="utf-8"))


def test_officials_eval_role_aliases_fixture_validates():
    from accuracy import build_eval_taxonomy

    taxonomy = build_eval_taxonomy()
    assert taxonomy.role_aliases, "role_aliases.yml produced an empty taxonomy"
