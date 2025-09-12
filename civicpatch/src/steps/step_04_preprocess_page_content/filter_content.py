import time
from bs4 import Tag, BeautifulSoup
from steps.step_04_preprocess_page_content import entity_extraction

IMAGE_EXTENSIONS_WHITELIST = ["png", "jpg", "jpeg", "webp"]
ROLE_WHITELIST = {"mayor"}

def count_nodes(node: Tag):
    count = 1 if isinstance(node, Tag) else 0
    for child in getattr(node, "children", []):
        if isinstance(child, Tag):
            count += count_nodes(child)
    return count

def filter_content(input_html: str, government_type, progress_log_interval: int = 10) -> str:
    soup = BeautifulSoup(input_html, "html.parser")
    total_nodes = count_nodes(soup)
    state = {
        "processed": 0,
        "total": total_nodes,
        "last_progress_time": time.time(),
        "progress_log_interval": progress_log_interval
    }
    filter_node_content(soup, state, government_type)

    if not soup.find_all():  # No tags left in the tree
        return ""
    filtered_content = str(soup)
    return filtered_content

def filter_node_content(node: Tag, state, government_type):
    # Special handling for tables: keep if any cell contains a person or whitelisted keyword (case-insensitive, substring match)
    if node.name == "table":
        keep_table = False
        for cell in node.find_all(["td", "th"]):
            cell_text = cell.get_text(strip=True)
            if cell_text:
                people, dates, emails, phones, keywords = entity_extraction.extract_data(cell_text, government_type)
                if people or keywords:
                    keep_table = True
                    break
        if keep_table:
            return  # Do not decompose this table or its children

    # Recursively process children
    for child in node.children:
        if isinstance(child, Tag):
            filter_node_content(child, state, government_type)

    # Check direct relevance
    found_people = []
    found_dates = []
    found_emails = []
    found_phones = []
    found_keywords = []
    found_websites = []
    found_images = []

    if node.name == "img":
        src_clean = node.get("src", "").split("?")[0].lower()
        if src_clean.endswith(tuple(IMAGE_EXTENSIONS_WHITELIST)):
            found_images.append(node["src"])
    elif node.name == "a" and node.get("href", "").startswith("http"):
        link_text = node.get_text().strip()
        if link_text:
            link_people, _, _, _, keywords = entity_extraction.extract_data(link_text, government_type)
            if link_people:
                found_websites.append(node["href"])
                found_people.extend(link_people)
            found_keywords.extend(keywords)
    else:
    # elif node.string:
        text_content = node.get_text(strip=True)
        if text_content:
            people, dates, emails, phones, keywords = entity_extraction.extract_data(text_content, government_type)
            found_people.extend(people)
            found_dates.extend(dates)
            found_emails.extend(emails)
            found_phones.extend(phones)
            found_keywords.extend(keywords)

    is_directly_relevant = any([
        found_people, found_dates, found_emails, found_phones, found_keywords, found_websites, found_images
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
        print(f"-> Progress: {percent}% ({state['processed']}/{state['total']})")
        state["last_progress_time"] = now
    # ------------------------

