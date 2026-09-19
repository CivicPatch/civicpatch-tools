"""What a scrape is looking for: its organizations' names, their posts' labels, the roles of
the memberships it expects to find, and their designations ("Position 1").

One source, two shapes. `search_phrases` keeps them as written, for text matched by substring
(accordion buttons, page sections). `as_tokens` breaks phrases into distinctive words, for URL
paths matched token by token (the frontier). A post label already carries its role and division
("Council Member, District 3"), so the organizations cover roles without a separate list.
"""

import re
from typing import List

from runners.people_collector.schemas import ExpectedMembership
from shared.schemas import KnownOrganization
from shared.utils import name_utils

# Words in an organization's name that every municipal site uses somewhere, so matching on them ranks
# `/clerks-office` and `/city-hall-hours` alongside the roster. Dropped rather than the whole
# name, because what is left is what distinguishes one organization from another: "School Board" keeps
# `school`, "Office of the Mayor" keeps `mayor`.
_GENERIC_ORGANIZATION_TOKENS = frozenset(
    {
        "city",
        "town",
        "village",
        "borough",
        "township",
        "county",
        "government",
        "municipal",
        "office",
        "offices",
        "department",
        "departments",
        "administration",
        "public",
        "general",
    }
)


def organization_phrases(organizations: List[KnownOrganization]) -> List[str]:
    phrases: List[str] = []
    for organization in organizations:
        phrases.append(organization.name)
        phrases.extend(post.label for post in organization.posts)
    return list(dict.fromkeys(phrase for phrase in phrases if phrase))


def expected_roles(memberships: List[ExpectedMembership]) -> List[str]:
    return list(dict.fromkeys(membership.role_label for membership in memberships))


def expected_designations(memberships: List[ExpectedMembership]) -> List[str]:
    return list(
        dict.fromkeys(
            designation for membership in memberships for designation in membership.designations
        )
    )


def search_phrases(
    organizations: List[KnownOrganization], memberships: List[ExpectedMembership]
) -> List[str]:
    return list(
        dict.fromkeys(
            organization_phrases(organizations)
            + expected_roles(memberships)
            + expected_designations(memberships)
        )
    )


def as_tokens(phrases: List[str]) -> List[str]:
    """The distinctive words of these phrases: four characters or more, generic words dropped.

    In source order rather than through a set: this feeds a sort key, and a term list that
    reorders between runs makes a queue that cannot be replayed.
    """
    tokens: List[str] = []
    for phrase in phrases:
        for token in re.split(r"[^a-z0-9]", name_utils.normalize_text_for_search(phrase).lower()):
            if len(token) >= 4 and token not in _GENERIC_ORGANIZATION_TOKENS and token not in tokens:
                tokens.append(token)
    return tokens
