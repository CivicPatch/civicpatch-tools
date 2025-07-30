from bs4 import Tag
from . import entity_extraction

IMAGE_EXTENSIONS_WHITELIST = ["png", "jpg", "jpeg", "webp"]

def process_node(node):
    """Recursively process each node to remove irrelevant content."""
    found_people = []
    found_dates = []
    found_emails = []
    found_phones = []
    found_roles = []
    found_websites = []
    found_images = []
    has_relevant_children = False

    if not node.string:  # Has children
        children_to_remove = []
        for child in list(node.children):
            if hasattr(child, 'name'):  # It's a tag, not text
                child_is_relevant = process_node(child)
                if child_is_relevant:
                    has_relevant_children = True
                else:
                    children_to_remove.append(child)
        
        # Remove irrelevant children after processing all
        for child in children_to_remove:
            child.decompose()

    # Extract text only from this node's direct content (not descendants)
    direct_text = ""
    if node.string:  # Leaf node with direct text
        direct_text = str(node.string).strip()
    elif isinstance(node, Tag):
        # For non-leaf nodes, get only the direct text (not from children)
        direct_text_parts = []
        for content in node.contents:
            if isinstance(content, str):  # Direct text content
                direct_text_parts.append(content.strip())
        direct_text = " ".join(direct_text_parts).strip()
        
    if direct_text:
        found_people, found_dates, found_emails, found_phones, found_roles = entity_extraction.extract_data(direct_text)

    # Check for person-linked websites
    if isinstance(node, Tag):
        if node.name == "img":
            src_clean = node["src"].split("?")[0].lower()
            if src_clean.endswith(tuple(IMAGE_EXTENSIONS_WHITELIST)):
                found_images.append(node["src"])
        # Collect all whitelisted image URLs in this node
        for a in node.find_all("a", href=True, recursive=False):  # Only direct children
            if a.get("href") and a.get("href").startswith("http"):
                link_text = a.get_text().strip()
                if link_text:
                    # Extract people from link text specifically
                    link_people, _, _, _, _ = entity_extraction.extract_data(link_text)
                    if link_people:
                        found_websites.append(a["href"])
                        # Add link people to our found people
                        found_people.extend(link_people)

    # Determine relevance
    is_relevant = bool(
        found_people or found_roles or found_dates or found_emails or 
        found_phones or found_websites or found_images or has_relevant_children
    )
    
    return is_relevant

