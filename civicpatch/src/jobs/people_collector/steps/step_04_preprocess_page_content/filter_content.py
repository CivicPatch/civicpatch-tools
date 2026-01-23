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
    """Check if text contains any relevant content including emails and phones."""
    if not text.strip():
        return False
    
    people, dates, emails, phones, keywords = entity_extraction.extract_data(text, government_type)
    # Flatten both keys & values of identities for checking

    flattened_names = [canonical_name for canonical_name in identities.keys()]
    flattened_aliases = [item for sublist in identities.values() for item in sublist]
    for name in flattened_names + flattened_aliases:
        if name in text:
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

def filter_node_content(logger, identities: Dict[str, List[str]], node: Tag, state, government_type):
    # Handle images - Always keep images (check this FIRST, before anything else)
    if node.name == "img":
        return  # Do not remove or modify images
    
    # Skip processing if this node is inside a kept table
    if node.find_parent("table") and hasattr(node.find_parent("table"), '_keep_table'):
        return  # Don't process nodes inside tables that are marked to keep
    
    # Recursively process children first
    for child in list(node.children):  # Use list() to avoid modifying the iterator during traversal
        if isinstance(child, Tag):  # Ensure the child is a Tag (not a string or comment)
            filter_node_content(logger, identities, child, state, government_type)

    # Process the parent node after all its children
    state["processed"] += 1
    now = time.time()
    if now - state["last_progress_time"] >= state["progress_log_interval"]:
        percent = int(100 * state["processed"] / state["total"])
        logger.info(f"-> PREPROCESS_PAGE_CONTENT Page Progress: {percent}% ({state['processed']}/{state['total']})")
        state["last_progress_time"] = now
    
    # Handle tables - evaluate the entire table content
    if node.name == "table":
        table_text = " ".join(cell.get_text(strip=True) for cell in node.find_all(["td", "th"]))
        if table_text.strip():
            # people, dates, emails, phones, keywords = entity_extraction.extract_data(table_text, government_type)
            is_relevant = has_relevant_content(identities, table_text, government_type)
            # if any([people, keywords]):  # Keep original logic - only check people and keywords for tables
            if is_relevant:
                # Mark this table to keep ALL its content (including images)
                node._keep_table = True
                return
        
        # Table is not relevant - extract images before removing
        images = node.find_all("img")
        if images and node.parent and hasattr(node.parent, 'name'):
            for img in images:
                node.insert_before(img.extract())
        
        node.decompose()  # Remove irrelevant tables
        return
    
    # If we're inside a kept table, don't remove anything
    parent_table = node.find_parent("table")
    if parent_table and hasattr(parent_table, '_keep_table'):
        return  # Keep all content inside marked tables
    
    # Handle links - be more selective about which links to keep
    if node.name == "a":
        href = node.get("href", "")
        link_text = node.get_text(strip=True)
        
        # Always keep mailto links
        if href.startswith("mailto:"):
            return
        
        # For other http links, check content relevance
        if href.startswith("http") and link_text:
            if has_relevant_content(identities, link_text, government_type):
                return
        
        # Before removing/replacing the link, extract and preserve any images
        images = node.find_all("img")
        if images and node.parent and hasattr(node.parent, 'name'):
            for img in images:
                node.insert_before(img.extract())
        
        # If link is not relevant, replace with just the text content
        if link_text:
            node.replace_with(link_text)
        else:
            node.decompose()
        return
    
    # For text nodes and other elements, check content but don't be too aggressive
    if node and node.name:
        node_text = node.get_text(strip=True)
        if node_text:
            if has_relevant_content(identities, node_text, government_type):
                return  # Keep nodes with relevant content
    
    # Handle specific structural elements more carefully
    if node.name in ["div", "span", "p", "section", "article", "main", "header", "footer"]:
        # Check if this element or its children contain relevant content FIRST
        descendant_text = node.get_text(strip=True)
        if descendant_text:
            if has_relevant_content(identities, descendant_text, government_type):
                return  # Keep structural elements that contain relevant content (including images)
        
        # Only extract images if we're going to remove this element
        images = node.find_all("img")
        if images and node.parent and hasattr(node.parent, 'name'):
            for img in images:
                node.insert_before(img.extract())
        
        # If no relevant content and no parent, just return
        if not node.parent:
            return
        
        # If no relevant content, decompose to remove it and its text content
        node.decompose()
        return
    
    # For other elements without relevant content, extract images before removing
    if node.parent and node.name not in ["html", "body", "head", "title", "meta"]:
        images = node.find_all("img")
        if images and hasattr(node.parent, 'name'):
            for img in images:
                node.insert_before(img.extract())
        
        node.decompose()