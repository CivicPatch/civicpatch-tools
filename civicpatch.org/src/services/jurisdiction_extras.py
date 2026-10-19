"""cp.org's own fields on a jurisdiction, saved at once and never a pull request: each field sent
goes to its own setter, which checks and records it."""

import services.extras_organizations as extras_organizations_service
import services.governing_law as governing_law_service
import services.government_form as government_form_service
from shared.schemas import FoundBy, JurisdictionExtras

# Each setter raises its own; the route answers all of them alike.
UNKNOWN_JURISDICTION = (
    government_form_service.UnknownJurisdiction,
    governing_law_service.UnknownJurisdiction,
    extras_organizations_service.UnknownJurisdiction,
)


async def save_jurisdiction_extras(jurisdiction_ocdid: str, extras: JurisdictionExtras, user_id: str | None) -> None:
    """Field by field, so a caller sends one field at a time to have it all or nothing. `user_id`
    is None for the service key."""
    if extras.extras_government_form is not None:
        await government_form_service.set_government_form(jurisdiction_ocdid, extras.extras_government_form, user_id)
    if extras.extras_governing_law is not None:
        await governing_law_service.set_governing_law(jurisdiction_ocdid, extras.extras_governing_law, user_id)
    if extras.extras_organizations is not None:
        await extras_organizations_service.set_extras_organizations(jurisdiction_ocdid, extras.extras_organizations, user_id)


def with_maintainer_as_finder(extras: JurisdictionExtras) -> JurisdictionExtras:
    """A person's governing law is recorded as theirs, whatever the body claims found it."""
    if extras.extras_governing_law is None:
        return extras
    governing_law = extras.extras_governing_law.model_copy(update={"found_by": FoundBy.MAINTAINER})
    return extras.model_copy(update={"extras_governing_law": governing_law})
