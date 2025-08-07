import time
from bs4 import Tag, BeautifulSoup
from . import entity_extraction

IMAGE_EXTENSIONS_WHITELIST = ["png", "jpg", "jpeg", "webp"]

def count_nodes(node: Tag):
    count = 1 if isinstance(node, Tag) else 0
    for child in getattr(node, "children", []):
        if isinstance(child, Tag):
            count += count_nodes(child)
    return count

def filter_content(input_html: str, progress_log_interval: int = 10) -> str:
    soup = BeautifulSoup(input_html, "html.parser")
    total_nodes = count_nodes(soup)
    state = {
        "processed": 0,
        "total": total_nodes,
        "last_progress_time": time.time(),
        "progress_log_interval": progress_log_interval
    }
    filter_node_content(soup, state)
    print()  # Newline after progress
    return str(soup)

def filter_node_content(node: Tag, state):
    # Process children first
    for child in list(node.children):
        if isinstance(child, Tag):
            filter_node_content(child, state)

    # Check direct relevance
    found_people = []
    found_dates = []
    found_emails = []
    found_phones = []
    found_roles = []
    found_divisions = []
    found_websites = []
    found_images = []

    if node.name == "img":
        src_clean = node.get("src", "").split("?")[0].lower()
        if src_clean.endswith(tuple(IMAGE_EXTENSIONS_WHITELIST)):
            found_images.append(node["src"])
    elif node.name == "a" and node.get("href", "").startswith("http"):
        link_text = node.get_text().strip()
        if link_text:
            link_people, _, _, _, _, _ = entity_extraction.extract_data(link_text)
            if link_people:
                found_websites.append(node["href"])
                found_people.extend(link_people)
    elif node.string:
        text_content = node.string.strip()
        if text_content:
            people, dates, emails, phones, roles, divisions = entity_extraction.extract_data(text_content)
            found_people.extend(people)
            found_dates.extend(dates)
            found_emails.extend(emails)
            found_phones.extend(phones)
            found_roles.extend(roles)
            found_divisions.extend(divisions)

    is_directly_relevant = any([
        found_people, found_roles, found_divisions, found_dates,
        found_emails, found_phones, found_websites, found_images
    ])

    has_relevant_children = any(isinstance(child, Tag) for child in node.children)
    if node.name in {"document", "html", "body"}:
        return

    if not is_directly_relevant and not has_relevant_children:
        node.decompose()

    # --- Progress logging ---
    state["processed"] += 1
    now = time.time()
    if now - state["last_progress_time"] >= state["progress_log_interval"]:
        percent = int(100 * state["processed"] / state["total"])
        print(f"Progress: {percent}% ({state['processed']}/{state['total']})")
        state["last_progress_time"] = now
    # ------------------------

