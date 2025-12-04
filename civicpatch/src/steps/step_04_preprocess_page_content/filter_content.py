import time
from bs4 import Tag, BeautifulSoup, NavigableString
from steps.step_04_preprocess_page_content import entity_extraction

BLACKLISTED_CLASSES = [ # Warning -- these need to be carefully curated
    "language" # Google Translate
]

def count_nodes(node: Tag):
    count = 1 if isinstance(node, Tag) else 0
    for child in getattr(node, "children", []):
        if isinstance(child, Tag):
            count += count_nodes(child)
    return count

def has_relevant_content(text: str, government_type) -> bool:
    """Check if text contains any relevant content including emails and phones."""
    if not text.strip():
        return False
    
    people, dates, emails, phones, keywords = entity_extraction.extract_data(text, government_type)
    # Include emails and phones in relevance check
    return any([people, dates, emails, phones, keywords])

def filter_content(logger, input_html: str, government_type, progress_log_interval: int = 10) -> str:
    soup = BeautifulSoup(input_html, "html.parser")
    total_nodes = count_nodes(soup)
    state = {
        "processed": 0,
        "total": total_nodes,
        "last_progress_time": time.time(),
        "progress_log_interval": progress_log_interval
    }
    filter_node_content(logger, soup, state, government_type)

    if not soup.find_all():  # No tags left in the tree
        return ""
    filtered_content = soup.prettify()
    return filtered_content

def filter_node_content(logger, node: Tag, state, government_type):
    # Skip processing if this node is inside a kept table
    if node.find_parent("table") and hasattr(node.find_parent("table"), '_keep_table'):
        return  # Don't process nodes inside tables that are marked to keep
    
    # Recursively process children first
    for child in list(node.children):  # Use list() to avoid modifying the iterator during traversal
        if isinstance(child, Tag):  # Ensure the child is a Tag (not a string or comment)
            filter_node_content(logger, child, state, government_type)

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
            people, dates, emails, phones, keywords = entity_extraction.extract_data(table_text, government_type)
            if any([people, keywords]):  # Keep original logic - only check people and keywords for tables
                # Mark this table to keep ALL its content
                node._keep_table = True
                return  # Keep the entire table structure intact
        node.decompose()  # Remove irrelevant tables
        return
    
    # If we're inside a kept table, don't remove anything
    parent_table = node.find_parent("table")
    if parent_table and hasattr(parent_table, '_keep_table'):
        return  # Keep all content inside marked tables
    
    # Handle images
    if node.name == "img":
        return
    
    # Handle links - be more selective about which links to keep
    if node.name == "a":
        href = node.get("href", "")
        link_text = node.get_text(strip=True)
        
        # Always keep mailto links
        if href.startswith("mailto:"):
            return
        
        # For other http links, check content relevance
        if href.startswith("http") and link_text:
            if has_relevant_content(link_text, government_type):  # Use the fixed function
                return
        
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
            if has_relevant_content(node_text, government_type):  # Use the fixed function
                return  # Keep nodes with relevant content
    
    # Handle specific structural elements more carefully
    if node.name in ["div", "span", "p", "section", "article", "main", "header", "footer"]:
        # Check if this element or its children contain relevant content
        descendant_text = node.get_text(strip=True)
        if descendant_text:
            if has_relevant_content(descendant_text, government_type):  # Use the fixed function
                return  # Keep structural elements that contain relevant content
        
        # If no relevant content, unwrap instead of removing completely
        if node.parent:
            node.unwrap()
        return
    
    # For other elements without relevant content, remove them
    if node.parent and node.name not in ["html", "body", "head", "title", "meta"]:
        node.decompose()