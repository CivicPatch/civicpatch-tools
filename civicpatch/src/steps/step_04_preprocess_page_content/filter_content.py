import time
from bs4 import Tag, BeautifulSoup, NavigableString
from steps.step_04_preprocess_page_content import entity_extraction

IMAGE_EXTENSIONS_WHITELIST = ["png", "jpg", "jpeg", "webp"]
BLACKLISTED_CLASSES = [ # Warning -- these need to be carefully curated
    "language" # Google Translate
]

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
    filtered_content = soup.prettify()
    return filtered_content

def filter_node_content(node: Tag, state, government_type):
    # Recursively process children first
    for child in list(node.children):  # Use list() to avoid modifying the iterator during traversal
        if isinstance(child, Tag):  # Ensure the child is a Tag (not a string or comment)
            filter_node_content(child, state, government_type)

    # Process the parent node after all its children
    state["processed"] += 1
    now = time.time()
    if now - state["last_progress_time"] >= state["progress_log_interval"]:
        percent = int(100 * state["processed"] / state["total"])
        print(f"-> Progress: {percent}% ({state['processed']}/{state['total']})")
        state["last_progress_time"] = now

    # Example logic for processing the parent node
    if node.name == "table":
        table_text = " ".join(cell.get_text(strip=True) for cell in node.find_all(["td", "th"]))
        if table_text.strip():
            people, dates, emails, phones, keywords = entity_extraction.extract_data(table_text, government_type)
            if any([people, keywords]):  # Keep the table only if it contains relevant content
                return
        node.decompose()  # Remove irrelevant tables
        return

    if node.name == "img":
        src_clean = node.get("src", "").split("?")[0].lower()
        if src_clean.endswith(tuple(IMAGE_EXTENSIONS_WHITELIST)):
            return  # Keep whitelisted images
        node.decompose()  # Remove non-whitelisted images
        return

    if node.name == "a" and node.get("href", "").startswith("http"):
        link_text = node.get_text(strip=True)
        if link_text:
            link_people, _, _, _, keywords = entity_extraction.extract_data(link_text, government_type)
            if link_people or keywords:  # Keep the link only if it has relevant people or keywords
                return
        node.decompose()  # Remove irrelevant links
        return
    
    if node:
        text_content = str(node.string).strip()
        if text_content:
            text_people, _, _, _, text_keywords = entity_extraction.extract_data(text_content, government_type)
            if text_people or text_keywords:
                return  # Keep nodes with relevant text content

    # Remove all other nodes
    if node.parent:
        for child in list(node.children):
            if isinstance(child, NavigableString):  # Check if the child is direct text
                child.extract()  # Remove the direct text content

        # Unwrap the node, keeping only child nodes
        node.unwrap()
    else:
        print(f"Skipping unwrap for node: {node.name}, as it has no parent")

