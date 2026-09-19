"""What a scrape is looking for: its organizations' names, their posts' labels, how the site
labelled their members, and its roles.

One source, two shapes. `search_phrases` keeps them as written, for text matched by substring
(accordion buttons, page sections). `as_tokens` breaks phrases into distinctive words, for URL
paths matched token by token (the frontier). A post label already carries its role and division
("Council Member, District 3"), so the organizations cover roles without a separate list.
"""

import re
from typing import List

from shared.schemas import KnownOrganization, Membership
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


def organization_phrases(
    organizations: List[KnownOrganization], memberships: List[Membership]
) -> List[str]:
    """Each organization's name, its posts' labels, and its memberships' labels — the one a
    human set, and the site's own wording (`source_labels`, e.g. "Councilmember Pos. 8")."""
    phrases: List[str] = []
    for organization in organizations:
        phrases.append(organization.name)
        phrases.extend(post.label for post in organization.posts)
        for membership in memberships:
            if membership.organization_id == organization.id:
                phrases.append(membership.label or "")
                phrases.extend(membership.source_labels)
    return list(dict.fromkeys(phrase for phrase in phrases if phrase))


def search_phrases(
    organizations: List[KnownOrganization],
    memberships: List[Membership],
    known_roles: List[str],
) -> List[str]:
    return list(dict.fromkeys(organization_phrases(organizations, memberships) + known_roles))


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
