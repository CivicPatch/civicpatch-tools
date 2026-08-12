"""Direct tests for the trust-ladder primitives in schemas/common.py.

These pin down the ladder's most security-relevant behaviors:
- Unknown role strings cannot elevate above default.
- None (no identity / anonymous) ranks below default.
- The cascade is monotonic (admin >= maintainer >= contributor >= default).
"""
import pytest

from schemas.common import UserRole, role_rank, has_at_least


@pytest.mark.unit
def test_role_rank_known_roles_in_ladder_order():
    assert role_rank(UserRole.DEFAULT.value) == 0
    assert role_rank(UserRole.CONTRIBUTORS.value) == 1
    assert role_rank(UserRole.MAINTAINERS.value) == 2
    assert role_rank(UserRole.ADMINS.value) == 3


@pytest.mark.unit
def test_role_rank_none_is_below_default():
    """Anonymous / unauthenticated callers rank below default."""
    assert role_rank(None) == -1


@pytest.mark.unit
def test_role_rank_unknown_string_does_not_elevate():
    """A user with an unrecognized role string is treated as default-rank,
    NEVER higher. This is the defense-in-depth: even if some path stored
    'super_admin' in users.role, the ladder check would not let them up."""
    assert role_rank("super_admin") == 0
    assert role_rank("hacker") == 0
    assert role_rank("") == 0


@pytest.mark.unit
def test_has_at_least_exact_match():
    assert has_at_least(UserRole.DEFAULT.value, UserRole.DEFAULT) is True
    assert has_at_least(UserRole.ADMINS.value, UserRole.ADMINS) is True


@pytest.mark.unit
def test_has_at_least_cascade_admin_inherits_all():
    """Admin should pass every required-role check."""
    assert has_at_least(UserRole.ADMINS.value, UserRole.MAINTAINERS) is True
    assert has_at_least(UserRole.ADMINS.value, UserRole.CONTRIBUTORS) is True
    assert has_at_least(UserRole.ADMINS.value, UserRole.DEFAULT) is True


@pytest.mark.unit
def test_has_at_least_cascade_maintainer_inherits_lower():
    assert has_at_least(UserRole.MAINTAINERS.value, UserRole.CONTRIBUTORS) is True
    assert has_at_least(UserRole.MAINTAINERS.value, UserRole.DEFAULT) is True
    assert has_at_least(UserRole.MAINTAINERS.value, UserRole.ADMINS) is False


@pytest.mark.unit
def test_has_at_least_cascade_contributor_inherits_default():
    assert has_at_least(UserRole.CONTRIBUTORS.value, UserRole.DEFAULT) is True
    assert has_at_least(UserRole.CONTRIBUTORS.value, UserRole.MAINTAINERS) is False
    assert has_at_least(UserRole.CONTRIBUTORS.value, UserRole.ADMINS) is False


@pytest.mark.unit
def test_has_at_least_default_does_not_elevate():
    assert has_at_least(UserRole.DEFAULT.value, UserRole.CONTRIBUTORS) is False


@pytest.mark.unit
def test_has_at_least_none_fails_every_check():
    """Anonymous callers can't pass any non-PUBLIC gate via the ladder."""
    assert has_at_least(None, UserRole.DEFAULT) is False
    assert has_at_least(None, UserRole.CONTRIBUTORS) is False
    assert has_at_least(None, UserRole.MAINTAINERS) is False
    assert has_at_least(None, UserRole.ADMINS) is False


@pytest.mark.unit
def test_has_at_least_unknown_role_fails_elevated_checks():
    """If somehow an unknown role string ends up on a user (e.g. from a
    future addition that hasn't been deployed everywhere), it CANNOT elevate."""
    assert has_at_least("hacker", UserRole.DEFAULT) is True  # same rank as default
    assert has_at_least("hacker", UserRole.CONTRIBUTORS) is False
    assert has_at_least("hacker", UserRole.MAINTAINERS) is False
    assert has_at_least("hacker", UserRole.ADMINS) is False
