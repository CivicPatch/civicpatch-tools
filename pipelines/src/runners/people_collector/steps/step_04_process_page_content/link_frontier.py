import re
import copy
from dataclasses import dataclass
from typing import List, Dict, Optional, Set, Tuple
from runners.people_collector.schemas import Link, LinkStatus, LLMPerson, RecordsByLLM
from shared.utils import url_utils, name_utils

# URL patterns that are deterministic dead ends. Matched against the full URL
# before adding to the crawl frontier, so the LLM never wastes a scrape on them.
# Add new patterns here rather than trying to teach the LLM to filter them.
LINK_PATTERNS_BLACKLIST = {
    # CivicPlus
    ## Calendar — generic
    r"/calendar/\d{4}\b":              "calendar: year-indexed archive",
    r"[Cc]alendar\.aspx":              "calendar: CivicPlus calendar page",
    r"\?.*\bEID=":                     "calendar: CivicPlus event instance",
    r"\?.*\bview=list\b":              "calendar: CivicPlus list view",
    r"\?.*\bCID=":                     "calendar: CivicPlus category filter",

    r"DocumentCenter/View/":           "document: CivicPlus document viewer",

    r"\.pdf\b":                        "document: PDF file",
    r"\.docx?\b":                      "document: Word document",
    r"\.xlsx?\b":                      "document: Excel spreadsheet",
    r"\.pptx?\b":                      "document: PowerPoint presentation",
}

# URL keywords that strongly indicate a governance page. Links matching any of
# these are sorted to the top of the crawl frontier, ahead of num_references.
# TODO: should probably move this into config
LINK_KEYWORDS_WHITELIST = [
    "council",
    "mayor",
    "board",
    "government",
    "commission",
    "aldermen",
    "official",
    "elected",
    "representative",
    "selectmen",
    "directory"
]

IGNORE_WEBSITES = [
    "facebook.com",
    "twitter.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com"
]


def _blacklist_match(url: str) -> Optional[str]:
    for pattern, comment in LINK_PATTERNS_BLACKLIST.items():
        if re.search(pattern, url):
            return comment
    return None


@dataclass
class LinkSignals:
    keyword: Optional[str]     # matched keyword from LINK_KEYWORDS_WHITELIST
    role: Optional[str]        # matched role from known_roles or name_lsad_suffix
    designation: Optional[str] # matched designation token from url or text
    name: Optional[str]        # matched person name token from url


def _compute_link_signals(
    url: str,
    text: str,
    designations: List[str],
    names: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
) -> LinkSignals:
    path = url_utils.get_path(url)
    return LinkSignals(
        # substring match: keywords are stems ("council") that embed in longer words ("councilmember")
        keyword=_keyword_match(path, LINK_KEYWORDS_WHITELIST) or _keyword_match(text, LINK_KEYWORDS_WHITELIST),
        role=_keyword_match(path, roles) or _keyword_match(text, roles),
        # token match: avoids mid-word false positives (e.g. "ward" should not match "/edward/")
        designation=_match_any_token(url, designations) or _match_any_token(text, designations),
        # token match on last name alone is meaningful — url may be "/mayor-smith/" with no first name
        name=_match_any_token(url, names or []) or _match_any_token(text, names or []),
    )


def _signals_to_comment(signals: LinkSignals) -> Optional[str]:
    parts = []
    if signals.keyword:
        parts.append(f"keyword:{signals.keyword}")
    if signals.role:
        parts.append(f"role:{signals.role}")
    if signals.designation:
        parts.append(f"designation:{signals.designation}")
    return ("heuristic backfill: " + ", ".join(parts)) if parts else None


def _keyword_match(text: str, keywords: Optional[List[str]] = None) -> Optional[str]:
    if not keywords:
        return None
    text_lower = text.lower()
    for kw in keywords:
        if kw in text_lower:
            return kw
    return None


def _extract_links_from_markdown(content: str) -> List[Tuple[str, str]]:
    """Returns (text, url) pairs for all markdown links with http(s) URLs."""
    return re.findall(r'\[([^\]]*)\]\((https?://[^)]+)\)', content)


def jurisdiction_name_suffix(name: Optional[str]) -> List[str]:
    name = (name or "").strip()
    return [name.split()[-1].lower()] if name else []


def find_heuristic_urls(content: str, designations: List[str], roles: Optional[List[str]] = None) -> Dict[str, Tuple[str, str]]:
    """Returns url → (comment, link text) for links that pass heuristic signals."""
    result = {}
    for text, url in _extract_links_from_markdown(content):
        if _blacklist_match(url):
            continue
        signals = _compute_link_signals(url, text, designations, roles=roles)
        comment = _signals_to_comment(signals)
        if comment:
            result[url] = (comment, text)
    return result


def _tokenize(text: str) -> Set[str]:
    return set(re.split(r'[^a-z0-9]', text.lower()))


def _match_any_token(text: str, terms: List[str], min_len: int = 4) -> Optional[str]:
    """Returns the first matched token if any significant token (len >= min_len) from any term appears in text."""
    text_tokens = _tokenize(text)
    for term in terms:
        significant = {t for t in _tokenize(name_utils.normalize_text_for_search(term)) if len(t) >= min_len}
        matched = significant & text_tokens
        if matched:
            return next(iter(matched))
    return None


def extract_names_and_designations(records_by_llm: RecordsByLLM) -> Tuple[List[str], List[str]]:
    names = []
    seen_names = set()
    designations = []
    seen_designations = set()
    for people_by_name in records_by_llm.values():
        for name, person_list in people_by_name.items():
            normalized = name_utils.normalize_text_for_search(name) if name else None
            if normalized and normalized not in seen_names:
                seen_names.add(normalized)
                names.append(name)
            for person in person_list:
                for d in (person.designations or []):
                    if d and d not in seen_designations:
                        seen_designations.add(d)
                        designations.append(d)
    return names, designations


def _pending_sort_key(link: Link, names: List[str], designations: List[str]) -> tuple:
    signals = _compute_link_signals(link.url, link.text or "", designations, names=names)
    return (
        -int(signals.keyword is not None),
        -link.num_references,
        -int(signals.name is not None),
        -int(signals.designation is not None),
        -int(signals.role is not None),
        len(url_utils.get_path(link.url).split("/")),
    )


def _find_link(links: List[Link], url: str):
    return next((link for link in links if url_utils.same_url(link.url, url)), None)


def _sort_pending(links: List[Link], names: List[str], designations: List[str]) -> List[Link]:
    pending = [l for l in links if l.status == LinkStatus.PENDING.value]
    non_pending = [l for l in links if l.status != LinkStatus.PENDING.value]
    pending.sort(key=lambda l: _pending_sort_key(l, names, designations))
    return pending + non_pending


def add_relevant_urls(urls: List[str], existing_links: List[Link], domain: str, names: Optional[List[str]] = None, designations: Optional[List[str]] = None, logger=None, url_comments: Optional[Dict[str, Tuple[str, str]]] = None) -> List[Link]:
    """Add LLM-identified relevant URLs as pending links, restricted to the same domain."""
    names = names or []
    designations = designations or []
    updated_links = copy.deepcopy(existing_links)
    for link_url in urls:
        if not url_utils.same_domain(domain, link_url):
            continue
        formatted_link_url = url_utils.format_url(link_url)
        existing_link = _find_link(updated_links, formatted_link_url)
        if existing_link:
            if existing_link.status == LinkStatus.PENDING.value:
                existing_link.num_references += 1
            continue
        blacklist_comment = _blacklist_match(formatted_link_url)
        if blacklist_comment:
            if logger:
                logger.info(f"Dropping blacklisted URL ({blacklist_comment}): {formatted_link_url}")
            continue
        link_text = None
        if url_comments is not None:
            entry = url_comments.get(formatted_link_url) or url_comments.get(link_url)
            if isinstance(entry, tuple):
                comment, link_text = entry
            else:
                comment = entry or "heuristic backfill"
        else:
            kw = _keyword_match(url_utils.get_path(formatted_link_url))
            comment = f"whitelisted: {kw}" if kw else None
        updated_links.append(Link(
            url=formatted_link_url,
            status=LinkStatus.PENDING.value,
            folder_name="",
            num_references=1,
            comment=comment,
            text=link_text,
        ))
    return _sort_pending(updated_links, names, designations)


def mark_link_as_terminating_status(link_url: str, existing_links: List[Link], status: LinkStatus) -> List[Link]:
    updated_links = copy.deepcopy(existing_links)
    existing_link = next((link for link in updated_links if url_utils.same_url(link.url, link_url)), None)
    if existing_link:
        existing_link.status = status.value
        updated_links.append(updated_links.pop(updated_links.index(existing_link)))
    return updated_links


def has_role_and_contact_info(roles: List[str], records: List[LLMPerson]) -> bool:
    people = [LLMPerson.model_validate(r) if not isinstance(r, LLMPerson) else r for r in records]

    contact_types = set()
    for p in people:
        for field, value in [("image", p.image), ("url", p.url), ("phone", p.phone), ("email", p.email)]:
            if value:
                contact_types.add(field)
    has_contact = any(p.phone or p.email for p in people) and len(contact_types) >= 3

    all_roles = {
        r.strip().lower()
        for p in people
        for r in (p.roles or [])
        if r and r.strip()
    }
    has_role = bool(all_roles & set(roles))

    return has_contact and has_role


def extract_websites_from_processed_data(logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[str]:
    found_websites = []
    for people_by_name in records_by_llm.values():
        for person_name, person_list in people_by_name.items():
            if has_role_and_contact_info(roles, person_list):
                logger.debug(f"Skipping adding websites for person with role and contact info: {person_name}")
                continue
            for person_record in person_list:
                url = person_record.url
                if url and url not in found_websites:
                    domain = url_utils.extract_domain(url)
                    if domain and not any(ignore in domain for ignore in IGNORE_WEBSITES):
                        found_websites.append(url)
    return found_websites


def update_website_links(logger, domain, roles, existing_links: List[Link], records_by_llm: RecordsByLLM) -> List[Link]:
    found_websites = extract_websites_from_processed_data(logger, roles, records_by_llm)
    names, designations = extract_names_and_designations(records_by_llm)
    return add_relevant_urls(found_websites, existing_links, domain, names, designations + roles, logger)


def update_links(domain, context_links: List[Link], processed_page: Link, logger, roles: List[str], records_by_llm: RecordsByLLM) -> List[Link]:
    """Update processed page status and add new website links."""
    updated_links = mark_link_as_terminating_status(processed_page.url, context_links, LinkStatus.DONE)
    return update_website_links(logger, domain, roles, updated_links, records_by_llm)
