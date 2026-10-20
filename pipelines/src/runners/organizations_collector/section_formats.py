"""How each publisher's pages, through plan 1's converter, mark a section and the group it sits in.
By the page's host, since the markdown's shape follows the publisher, not the state. A host not
listed splits into nothing, and its page is read whole. Each new publisher adds an entry, a
fixture and its eval cases."""

import re
from typing import NamedTuple


class SectionFormat(NamedTuple):
    # A line starting a section; its first group is the heading.
    anchor: re.Pattern[str]
    # A line naming the group the next sections sit in: a subchapter, an article.
    group: re.Pattern[str]


SECTION_FORMATS: dict[str, SectionFormat] = {
    # `- **§ 3. Election of Mayor**`, the body on the next line. Numbers vary ("§§ 32-35.",
    # "§ 3-92.", "§ 2.1.") and a long heading wraps, losing its closing `**`.
    "legislature.vermont.gov": SectionFormat(
        anchor=re.compile(r"^- \*\*(§.*?)\**\s*$"),
        group=re.compile(r"^- \*\*\*([^*]+)\*\*\*\s*$"),
    ),
}
