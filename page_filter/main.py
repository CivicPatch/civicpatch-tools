from fastapi import FastAPI
from pydantic import BaseModel
import spacy, re
from bs4 import BeautifulSoup
from spacy.matcher import PhraseMatcher

app = FastAPI()
nlp = spacy.load("en_core_web_sm")

class Input(BaseModel):
    text: str

# Config for titles (can be loaded from a file if needed)
TITLES = ["mayor", "council member", "councilwoman", "councilman", "representative"]

# Initialize the PhraseMatcher
matcher = PhraseMatcher(nlp.vocab)
patterns = [nlp.make_doc(title) for title in TITLES]
matcher.add("TITLES", patterns)

def extract_with_context(pattern, text):
    return [
        match.group().rstrip(".")  # Remove trailing dots from the match
        for match in re.finditer(pattern, text)
    ]

# Extract titles using the matcher
def extract_roles(doc):
    matches = matcher(doc)
    return [doc[start:end].text for match_id, start, end in matches]

@app.post("/extract")
def extract(input: Input):
    # Parse the input text as HTML
    soup = BeautifulSoup(input.text, "html.parser")
    people = []
    roles = []
    dates = []
    emails = []
    phones = []
    websites = []
    
    # Prepare patterns for emails, phones, and websites
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    phone_pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    website_pattern = r"https?://[^\s]+"

    def process_node(node):
        """Recursively process each node to remove irrelevant content."""
        # Recursively process child nodes first
        for child in list(node.find_all(True, recursive=False)):
            process_node(child)

        # Check if the node contains relevant data
        def extract_data(text):
            """Extract relevant data from the given text."""
            doc = nlp(text)
            found_people = []
            found_dates = []
            for ent in doc.ents:
                if ent.label_ == "PERSON" and len(ent.text.split()) > 1:  # Ensure it's a full name
                    found_people.append(ent.text)
                elif ent.label_ == "DATE":
                    found_dates.append(ent.text)
            
            found_emails = extract_with_context(email_pattern, text)
            found_phones = extract_with_context(phone_pattern, text)
            found_roles = extract_roles(doc)
            found_websites = extract_with_context(website_pattern, text)
            return found_people, found_dates, found_emails, found_phones, found_roles, found_websites

        # Extract data for the node's text
        node_text = node.get_text(strip=True)
        found_people, found_dates, found_emails, found_phones, found_roles, found_websites = extract_data(node_text)

        # Check if the node contains any <a> tags (links)
        has_links = bool(node.find("a"))

        # Check if the node contains any <img> tags with whitelisted extensions
        has_images = any(
            img["src"].lower().endswith((".png", ".jpeg", ".jpg", ".gif", ".webp"))
            for img in node.find_all("img", src=True)
        )

        # If the node itself is irrelevant and has no relevant children, remove it
        if not (found_people or found_roles or found_dates or found_emails or found_phones or found_websites or has_links or has_images):
            node.decompose()  # Remove the node
        else:
            # If relevant data is found, add it to the lists
            people.extend(found_people)
            roles.extend(found_roles)
            dates.extend(found_dates)
            emails.extend(found_emails)
            phones.extend(found_phones)
            websites.extend(found_websites)

            # Remove irrelevant text directly under this node
            for content in list(node.contents):
                if isinstance(content, str) and not content.strip():
                    continue  # Skip empty strings
                if isinstance(content, str):
                    content_people, content_dates, content_emails, content_phones, content_roles, content_websites = extract_data(content.strip())
                    if not any([content_people, content_dates, content_emails, content_phones, content_roles, content_websites]):
                        content.extract()  # Remove irrelevant text

    # Process all top-level nodes
    for node in soup.find_all(True, recursive=False):
        process_node(node)

    # Deduplicate the lists while preserving order
    people = list(dict.fromkeys(people))
    roles = list(dict.fromkeys(roles))
    dates = list(dict.fromkeys(dates))
    emails = list(dict.fromkeys(emails))
    phones = list(dict.fromkeys(phones))
    websites = list(dict.fromkeys(websites))

    # Return an object with the filtered HTML and extracted data
    return {
        "filtered_html": soup.prettify(),
        "people": people,
        "roles": roles,
        "dates": dates,
        "emails": emails,
        "phones": phones,
        "websites": websites
    }
