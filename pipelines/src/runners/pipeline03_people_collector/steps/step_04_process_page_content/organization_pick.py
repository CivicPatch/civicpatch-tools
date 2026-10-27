"""The organization the model picks for each person: one of ours, the default never offered."""

from typing import List, Literal

from pydantic import BaseModel, create_model

from runners.pipeline03_people_collector.schemas import PeopleArrayLLMResponseSchema
from services.open_router.prompts import NO_ORGANIZATION
from shared.schemas import ExtractedPersonRecord, KnownOrganization, PersonSourceRecord


def pick_choices(organizations: List[KnownOrganization]) -> List[str]:
    """The default is our bucket for anyone unplaced; offering it made P4's duplicates."""
    return [organization.name for organization in organizations if not organization.meta_is_default]


def pick_response_schema(choices: List[str]) -> type[BaseModel]:
    """An enum of the choices, so the model cannot name an organization we do not have."""
    if not choices:
        return PeopleArrayLLMResponseSchema
    choice = Literal[tuple([*choices, NO_ORGANIZATION])]  # type: ignore[valid-type]
    person = create_model("PickedPersonRecord", __base__=ExtractedPersonRecord, organization=(choice, ...))
    return create_model("PickedPeopleResponse", people=(List[person], ...))


def picked_name(person: ExtractedPersonRecord) -> str | None:
    """The organization the model picked for this person; the field exists only on the per-run schema."""
    return getattr(person, "organization", None)


def picked_organization_id(picked: str | None, organizations: List[KnownOrganization]) -> str | None:
    """None for "none" or no pick: ingest places the record."""
    ids_by_name = {organization.name: organization.id for organization in organizations}
    return ids_by_name.get(picked) if picked else None


def picked_organization_ids(records: List[PersonSourceRecord]) -> List[str]:
    return list(dict.fromkeys(record.organization_id for record in records if record.organization_id))
