import time
from fastapi import FastAPI
from pydantic import BaseModel
import spacy, re
from bs4 import BeautifulSoup, Tag
from spacy.matcher import PhraseMatcher
from markdownify import markdownify as md


class Input(BaseModel):
    text: str

        
@app.post("/extract")

IMAGE_EXTENSIONS_WHITELIST = ["png", "jpg", "jpeg", "webp"]
def extract(input: Input):
    start_time = time.time()
    # Parse the input text as HTML
    soup = BeautifulSoup(input.text, "html.parser")
    people = []
    roles = []
    dates = []
    emails = []
    phones = []
    websites = []
    images = []
    
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

        # First, recursively process child nodes
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
            found_people, found_dates, found_emails, found_phones, found_roles = extract_data(direct_text)

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
                        link_people, _, _, _, _ = extract_data(link_text)
                        if link_people:
                            found_websites.append(a["href"])
                            # Add link people to our found people
                            found_people.extend(link_people)

        # Determine relevance
        is_relevant = bool(
            found_people or found_roles or found_dates or found_emails or 
            found_phones or found_websites or found_images or has_relevant_children
        )
        
        # Add to global lists if relevant
        if is_relevant:
            people.extend(found_people)
            roles.extend(found_roles)
            dates.extend(found_dates)
            emails.extend(found_emails)
            phones.extend(found_phones)
            websites.extend(found_websites)
            images.extend(found_images)
        
        return is_relevant

    # Process all top-level nodes
    nodes_to_remove = []
    for node in soup.find_all(True, recursive=False):
        if not process_node(node):
            nodes_to_remove.append(node)
    
    # Remove irrelevant top-level nodes
    for node in nodes_to_remove:
        node.decompose()

    # Deduplicate the lists while preserving order
    people = list(dict.fromkeys(people))
    roles = list(dict.fromkeys(roles))
    dates = list(dict.fromkeys(dates))
    emails = list(dict.fromkeys(emails))
    phones = list(dict.fromkeys(phones))
    websites = list(dict.fromkeys(websites))
    images = list(dict.fromkeys(images))

    # Return an object with the filtered HTML and extracted data
    end_time = time.time()
    print("People found:", people, "in: ", end_time - start_time, "seconds")
    print("Roles found:", roles)
    print("Dates found:", dates)
    print("Emails found:", emails)
    print("Phones found:", phones)
    print("Websites found:", websites)
    print("Images found:", images)
    return {
        "filtered_content": md(soup.prettify()),
        "people": people,
        "roles": roles,
        "dates": dates,
        "emails": emails,
        "phones": phones,
        "websites": websites,
        "images": images,
        "processing_time_s": (end_time - start_time)
    }
