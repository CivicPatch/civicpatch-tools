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
    
    # Process all top-level nodes
    nodes_to_remove = []
    for node in soup.find_all(True, recursive=False):
        if not prlevant:
            people.extend(found_people)
            roles.extend(found_roles)
            dates.extend(found_dates)
            emails.extend(found_emails)
            phones.extend(found_phones)
            websites.extend(found_websites)
            images.extend(ocess_node(node):
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
