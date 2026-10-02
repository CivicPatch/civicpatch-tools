"""Candidate officials eval cases, one roster page at a time, in the three ways a prompt can
describe a body's offices: titles found before, suggestions from the form of government, or none.

Offline: no network, no LLM, no cost. Writes to `datasets/candidates/municipal_officials/` for a
person to review and move into `datasets/local/municipal_officials/`; nothing here is trusted.

A form with two or more organizations is scoped to each in turn, as production runs it; a
one-organization form (a county, a council-manager city, a township) runs unscoped, with the
titles as `known_roles`. A form the config cannot decide is tried as each form allowed.
A roster page is one published people cite; its expected people are those people, each filed
under the organization whose `role_labels` hold their role. A case already staged is never
overwritten, since it may have been reviewed.

    uv run python -m tests.prompts.tests.evals.generate_officials_cases --open-data ../open-data
"""

import argparse
import glob
import os
import re
from enum import Enum

import yaml
from pydantic import BaseModel
from shared.schemas import GovernmentForm, JurisdictionLevel
from shared.utils.id_utils import parse_jurisdiction_ocdid
from shared.utils.layered_config import (
    ConfigFile,
    allowed_government_forms,
    derived_organizations,
    jurisdiction_config,
    resolve_government_form,
)
from shared.utils.government_forms import DerivedOrganization
from shared.utils import divisions
from shared.utils.label_parser import parse_label
from shared.utils.taxonomy import Taxonomy, build_taxonomy, lookup_key
from shared.utils.url_utils import canonical_url
from tests.prompts.tests.evals.eval_utils import GENERATED_KEY
from tests.prompts.tests.evals.generate_relevance_cases import (
    SavedRun,
    read_jurisdiction_configs,
    read_saved_runs,
)

CANDIDATES = "tests/prompts/datasets/candidates/municipal_officials"
# A page at least this many published people cite is a roster, not one person's page.
MIN_CITING_PEOPLE = 2
MAX_JURISDICTIONS_PER_FORM = 3
_TOWN_FORMS = {GovernmentForm.OPEN_TOWN_MEETING, GovernmentForm.REPRESENTATIVE_TOWN_MEETING}


class Variant(Enum):
    KNOWN_TITLES = "known_titles"
    SUGGESTED_TITLES = "suggested_titles"
    NO_TITLES = "no_titles"


class PublishedPerson(BaseModel):
    name: str
    role_names: list[str]
    phones: list[str] = []
    emails: list[str] = []
    urls: list[str] = []
    source_urls: list[str] = []


class CandidateCase(BaseModel):
    case_id: str
    input_path: str
    government_form: GovernmentForm
    form_was_decided: bool
    organization: DerivedOrganization
    # Production scopes the prompt to a body only when the form has more than one.
    scoped: bool
    variant: Variant
    role_labels: list[str]
    divisions: list[str]
    people: list[PublishedPerson]


# --- Reading ---


def read_published_people(open_data: str) -> dict[str, list[PublishedPerson]]:
    """Every published person, under each jurisdiction they hold a role in, with those roles."""
    people: dict[str, list[PublishedPerson]] = {}
    for path in glob.glob(os.path.join(open_data, "data", "**", "*.yml"), recursive=True):
        with open(path) as f:
            rows = yaml.safe_load(f) or []
        for row in rows:
            roles_by_jurisdiction: dict[str, list[str]] = {}
            for role in row.get("roles") or []:
                roles_by_jurisdiction.setdefault(role["jurisdiction_ocdid"], []).append(role["name"])
            for jurisdiction_ocdid, role_names in roles_by_jurisdiction.items():
                people.setdefault(jurisdiction_ocdid, []).append(
                    PublishedPerson(
                        name=row["name"],
                        role_names=role_names,
                        phones=row.get("phones") or [],
                        emails=row.get("emails") or [],
                        urls=row.get("urls") or [],
                        source_urls=row.get("source_urls") or [],
                    )
                )
    return people


# --- Deciding (pure) ---


def forms_to_try(configs: dict[str, ConfigFile], run: SavedRun) -> list[tuple[GovernmentForm, bool]]:
    """(form, whether the config decided it), for every form that derives an organization."""
    parsed = parse_jurisdiction_ocdid(run.jurisdiction_ocdid)
    if parsed.level == JurisdictionLevel.STATE:
        return []
    config = jurisdiction_config(configs, parsed.state, parsed.level)
    decided = resolve_government_form(config, run.jurisdiction_name, None)
    if decided is not None:
        forms = [decided]
    else:
        forms = [
            form
            for form in allowed_government_forms(config, run.jurisdiction_name)
            if _plausible(form, run.jurisdiction_name, config.state_government_forms, parsed.level)
        ]
    return [(form, decided is not None) for form in forms if derived_organizations(config, form)]


def _plausible(
    form: GovernmentForm, jurisdiction_name: str, state_forms, level: JurisdictionLevel
) -> bool:
    """For a form the config leaves open. A county may have any its state allows. A town meeting
    only where the state's own config lists it (Massachusetts): a Census "town" in Tennessee or
    California has none. A township board only for a township. Otherwise a city."""
    if level == JurisdictionLevel.COUNTIES:
        return True
    if form in _TOWN_FORMS:
        return form in state_forms
    if form is GovernmentForm.TOWNSHIP_BOARD:
        return jurisdiction_name.endswith(" township")
    return jurisdiction_name.endswith(" city")


def roster_page(run: SavedRun, people: list[PublishedPerson]) -> str | None:
    """The run's most-cited saved page, if enough people cite it to call it a roster."""
    citing: dict[str, int] = {}
    for person in people:
        for url in {canonical_url(url) for url in person.source_urls}:
            citing[url] = citing.get(url, 0) + 1
    best = None
    for page in run.pages:
        count = citing.get(canonical_url(page.url), 0)
        if count >= MIN_CITING_PEOPLE and (best is None or count > best[0]):
            best = (count, page.input_path)
    return best[1] if best else None


def people_in(
    organization: DerivedOrganization,
    organizations: list[DerivedOrganization],
    people: list[PublishedPerson],
    page_url_key: str,
) -> list[PublishedPerson]:
    """People this page lists, with the roles filed under this organization. A role no
    organization of the form lists ("Clerk", "Alderman") goes to the first, its main board."""
    listed = {lookup_key(label) for other in organizations for label in other.role_labels}
    held = {lookup_key(label) for label in organization.role_labels}
    is_main_board = organization == organizations[0]

    def filed_here(name: str) -> bool:
        key = lookup_key(name)
        return key in held or (is_main_board and key not in listed)

    return [
        person.model_copy(update={"role_names": [name for name in person.role_names if filed_here(name)]})
        for person in people
        if page_url_key in {canonical_url(url) for url in person.source_urls}
        and any(filed_here(name) for name in person.role_names)
    ]


def roles_and_divisions(listed: list[PublishedPerson], taxonomy: Taxonomy) -> tuple[list[str], list[str]]:
    """What we have published for this body, parsed apart the way research is: its roles, and the
    divisions they sit in."""
    roles, found = [], []
    for name in (name for person in listed for name in person.role_names):
        parsed = parse_label(name, taxonomy)
        roles.extend(parsed.roles)
        if parsed.division:
            found.extend(divisions.filter_divisions([f"{parsed.division.designation} {parsed.division.value}"]))
    return list(dict.fromkeys(roles)), list(dict.fromkeys(found))


def case_id(
    run_folder: str, form: GovernmentForm, organization: str, variant: Variant, scoped: bool
) -> str:
    """An unscoped run's known titles and its absence of titles are the same whatever form is
    assumed, so those two ids leave the form out and the second form's copy is "already staged"."""
    if not scoped and variant is not Variant.SUGGESTED_TITLES:
        raw = f"{run_folder}__unscoped__{variant.value}"
    else:
        raw = f"{run_folder}__{form.value}__{organization}__{variant.value}"
    return re.sub(r"[^a-z0-9_-]", "_", raw.lower())


def prompt_inputs(case: CandidateCase) -> dict[str, object]:
    """What the eval hands the prompt besides the page, in the shape production uses: a scoped
    body under `organization`, an unscoped run's roles as `known_roles` beside its `divisions`."""
    if case.scoped:
        return {"organization": _scoped_organization(case)}
    if case.variant is Variant.KNOWN_TITLES:
        return {"known_roles": case.role_labels, **({"divisions": case.divisions} if case.divisions else {})}
    if case.variant is Variant.SUGGESTED_TITLES:
        return {"government_form_role_labels": case.organization.role_labels}
    return {}


def _scoped_organization(case: CandidateCase) -> dict[str, object]:
    organization: dict[str, object] = {"name": case.organization.name}
    if case.variant is Variant.KNOWN_TITLES:
        organization["role_labels"] = case.role_labels
        if case.divisions:
            organization["divisions"] = case.divisions
    elif case.variant is Variant.SUGGESTED_TITLES:
        organization["government_form_role_labels"] = case.organization.role_labels
    return organization


def expected_yaml(case: CandidateCase) -> str:
    form_note = "decided by the config" if case.form_was_decided else "one of several allowed, so assumed"
    scope_note = f"scoped to {case.organization.name}" if case.scoped else f"unscoped, its one body {case.organization.name}"
    thought = (
        f"GENERATED, review before moving into the dataset. Form {case.government_form.value} "
        f"({form_note}); {case.variant.value}, {scope_note}. People are the published "
        "roster's, filed by role (a role no organization lists goes to the main board): check titles, dates and anyone the page lists that the roster lacks."
    )
    expected = {
        GENERATED_KEY: True,
        **prompt_inputs(case),
        "people": [
            {
                "name": person.name,
                "label": " and ".join(person.role_names),
                "phone": person.phones[0] if person.phones else None,
                "email": person.emails[0] if person.emails else None,
                "url": person.urls[0] if person.urls else None,
                "start_date": None,
                "end_date": None,
                "image": None,
            }
            for person in case.people
        ],
        "thought": thought,
    }
    return yaml.safe_dump(expected, sort_keys=False)


def candidate_cases(
    configs: dict[str, ConfigFile],
    run: SavedRun,
    people: list[PublishedPerson],
) -> list[CandidateCase]:
    input_path = roster_page(run, people)
    if input_path is None:
        return []
    page_url_key = canonical_url(next(page.url for page in run.pages if page.input_path == input_path))
    parsed = parse_jurisdiction_ocdid(run.jurisdiction_ocdid)
    config = jurisdiction_config(configs, parsed.state, parsed.level)
    taxonomy = build_taxonomy(config.roles)
    cases = []
    for form, form_was_decided in forms_to_try(configs, run):
        organizations = derived_organizations(config, form)
        scoped = len(organizations) >= 2
        for organization in organizations:
            listed = people_in(organization, organizations, people, page_url_key)
            role_labels, found_divisions = roles_and_divisions(listed, taxonomy)
            for variant in Variant:
                cases.append(
                    CandidateCase(
                        case_id=case_id(run.folder, form, organization.name, variant, scoped),
                        input_path=input_path,
                        government_form=form,
                        form_was_decided=form_was_decided,
                        organization=organization,
                        scoped=scoped,
                        variant=variant,
                        role_labels=role_labels,
                        divisions=found_divisions,
                        people=listed,
                    )
                )
    return cases


def a_variety(cases_by_run: list[tuple[str, list[CandidateCase]]]) -> list[CandidateCase]:
    """Per form, at most one jurisdiction per state and `MAX_JURISDICTIONS_PER_FORM` in all, so
    one state cannot fill it. Takes (state, that run's cases)."""
    states_per_form: dict[GovernmentForm, set[str]] = {}
    chosen = []
    for state, run_cases in cases_by_run:
        for form in dict.fromkeys(case.government_form for case in run_cases):
            states = states_per_form.setdefault(form, set())
            if state in states or len(states) == MAX_JURISDICTIONS_PER_FORM:
                continue
            states.add(state)
            chosen.extend(case for case in run_cases if case.government_form is form)
    return chosen


# --- Writing ---


def write_case(case: CandidateCase) -> bool:
    """False, writing nothing, when the case is already staged: it may have been reviewed."""
    case_dir = os.path.join(CANDIDATES, case.case_id)
    if os.path.exists(case_dir):
        return False
    os.makedirs(case_dir)
    with open(case.input_path) as source, open(os.path.join(case_dir, "input.md"), "w") as target:
        target.write(source.read())
    with open(os.path.join(case_dir, "expected.yml"), "w") as f:
        f.write(expected_yaml(case))
    return True


# --- Entry point ---


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--open-data", required=True, help="path to the open-data repo checkout")
    open_data = parser.parse_args().open_data

    configs = read_jurisdiction_configs(open_data)
    people = read_published_people(open_data)
    runs = sorted(read_saved_runs(), key=lambda run: run.jurisdiction_ocdid)
    cases = a_variety(
        [
            (
                parse_jurisdiction_ocdid(run.jurisdiction_ocdid).state,
                candidate_cases(configs, run, people.get(run.jurisdiction_ocdid, [])),
            )
            for run in runs
        ]
    )
    written = [case for case in cases if write_case(case)]

    for form in GovernmentForm:
        count = len([case for case in written if case.government_form is form])
        if count:
            print(f"{count:4d}  {form.value}")
    print(f"{len(written)} new cases written to {CANDIDATES}; {len(cases) - len(written)} already staged")


if __name__ == "__main__":
    main()
