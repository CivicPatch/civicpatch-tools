import re
import time
from bs4 import Tag, BeautifulSoup
from jobs.people_collector.steps.step_04_preprocess_page_content import entity_extraction
from typing import Dict, List

BLACKLISTED_CLASSES = [ # Warning -- these need to be carefully curated
    "language" # Google Translate
]

def count_nodes(node: Tag):
    count = 1 if isinstance(node, Tag) else 0
    for child in getattr(node, "children", []):
        if isinstance(child, Tag):
            count += count_nodes(child)
    return count

def has_relevant_content(identities: Dict[str, List[str]], text: str, government_type) -> bool:
    """Check if text contains any relevant content including emails and phones.
    Match identity names by individual name tokens (word-by-word, case-insensitive).
    """
    # Normalize input: accept a bs4.Tag or any value and coerce to a plain string
    if isinstance(text, Tag):
        text = text.get_text(" ", strip=True)
    else:
        text = str(text or "")

    if not text.strip():
        return False

    people, dates, emails, phones, keywords = entity_extraction.extract_data(text, government_type)

    # Flatten both keys & values of identities for checking
    flattened_names = [canonical_name for canonical_name in identities.keys()]
    flattened_aliases = [item for sublist in identities.values() for item in sublist]

    text_lc = text.lower()

    # Tokenize each identity name and match tokens as whole words in the text.
    for name in flattened_names + flattened_aliases:
        if not name:
            continue
        name_lc = name.strip().lower()
        if not name_lc:
            continue

        tokens = re.split(r'\W+', name_lc)  # split on non-word chars
        for token in tokens:
            token = token.strip()
            if len(token) < 3:  # require at least 3 chars to reduce false positives
                continue
            if re.search(r'\b' + re.escape(token) + r'\b', text_lc):
                return True
    return any([people, dates, emails, phones, keywords])

def filter_content(logger, identities: Dict[str, List[str]], input_html: str, government_type, progress_log_interval: int = 10) -> str:
    soup = BeautifulSoup(input_html, "html.parser")
    total_nodes = count_nodes(soup)
    state = {
        "processed": 0,
        "total": total_nodes,
        "last_progress_time": time.time(),
        "progress_log_interval": progress_log_interval
    }
    filter_node_content(logger, identities, soup, state, government_type)

    if not soup.find_all():  # No tags left in the tree
        return ""
    filtered_content = soup.prettify()
    return filtered_content

def filter_node_content(logger, identities: Dict[str, List[str]], node: Tag, state, government_type) -> bool:
    """
    Process node tree. Returns True if this node (or any descendant) should be kept,
    False if the node was removed.
    """
    # Handle images - Always keep images (check this FIRST, before anything else)
    if node.name == "img":
        return True  # Do not remove or modify images

    # Handle links - always keep
    if node.name == "a":
        return True

    # Skip processing if this node is inside a kept table
    if node.find_parent("table") and hasattr(node.find_parent("table"), '_keep_table'):
        return True  # Don't process nodes inside tables that are marked to keep

    # Handle tables - evaluate the entire table content
    if node.name == "table":
        table_text = " ".join(cell.get_text(strip=True) for cell in node.find_all(["td", "th"]))
        if table_text.strip():
            is_relevant = has_relevant_content(identities, table_text, government_type)
            if is_relevant:
                # Mark this table to keep ALL its content (including images)
                node._keep_table = True
                return True

        # Table is not relevant - extract images before removing
        images = node.find_all("img")
        if images and node.parent and hasattr(node.parent, 'name'):
            for img in images:
                node.insert_before(img.extract())

        node.decompose()
        return False

    # Recursively process children first; if any child is kept, mark that
    any_child_kept = False
    for child in list(node.children):  # Use list() to avoid modifying the iterator during traversal
        if isinstance(child, Tag):  # Ensure the child is a Tag (not a string or comment)
            child_kept = filter_node_content(logger, identities, child, state, government_type)
            any_child_kept = any_child_kept or bool(child_kept)

    # Process the parent node after all its children
    state["processed"] += 1
    now = time.time()
    if now - state["last_progress_time"] >= state["progress_log_interval"]:
        percent = int(100 * state["processed"] / state["total"])
        logger.info(f"-> PREPROCESS_PAGE_CONTENT Page Progress: {percent}% ({state['processed']}/{state['total']})")
        state["last_progress_time"] = now

    # If we're inside a kept table, don't remove anything
    parent_table = node.find_parent("table")
    if parent_table and hasattr(parent_table, '_keep_table'):
        return True  # Keep all content inside marked tables

    # If any descendant was kept, keep this node (do not decompose)
    if any_child_kept:
        return True

    # For text nodes and other elements, check content but don't be too aggressive
    if node and node.name:
        # pass the Tag so has_relevant_content can inspect attributes/descendants if implemented
        if has_relevant_content(identities, node, government_type):
            return True  # Keep nodes with relevant content

    # Handle specific structural elements more carefully
    if node.name in ["p", "section", "article", "main", "header", "footer", "h1", "h2", "h3", "h4", "h5", "h6"]:
        # pass Tag to has_relevant_content so it can check attributes/descendants
        if has_relevant_content(identities, node, government_type):
            return True  # Keep structural elements that contain relevant content (including images)

        # Only extract images and <a> links if we're going to remove this element
        images = node.find_all("img")
        links = node.find_all("a")
        if images and node.parent and hasattr(node.parent, 'name'):
            for img in images:
                node.insert_before(img.extract())
        if links and node.parent and hasattr(node.parent, 'name'):
            for link in links:
                node.insert_before(link.extract())

        # If no relevant content and no parent, just return (nothing to remove)
        if not node.parent:
            return True

        # If no relevant content, decompose to remove it and its text content
        node.decompose()
        return False

    # For other elements without relevant content, extract images before removing
    if node.parent and node.name not in ["html", "body", "head", "title", "meta"]:
        images = node.find_all("img")
        if images and hasattr(node.parent, 'name'):
            for img in images:
                node.insert_before(img.extract())

        node.decompose()
        return False

    return True