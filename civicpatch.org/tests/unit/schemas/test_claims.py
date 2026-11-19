import pytest
from pydantic import ValidationError

from core.organization_derivation import ROLES_FIELD
from schemas.claims import ClaimKind, ClaimRequest, EntityType

pytestmark = pytest.mark.unit


def _organization_role_claim(value: object) -> ClaimRequest:
    return ClaimRequest(
        entity_type=EntityType.ORGANIZATION,
        entity_id="org-1",
        field_path=ROLES_FIELD,
        kind=ClaimKind.REJECT,
        value=value,
        sources=[{"url": "https://example.gov/town-meeting-minutes"}],
    )


def test_a_claim_on_an_organization_s_roles_is_a_role_and_its_label():
    assert _organization_role_claim({"role": "lister", "label": "Lister"}).value == {"role": "lister", "label": "Lister"}


def test_a_claim_on_an_organization_s_roles_without_a_label_is_refused():
    with pytest.raises(ValidationError):
        _organization_role_claim({"role": "lister"})
