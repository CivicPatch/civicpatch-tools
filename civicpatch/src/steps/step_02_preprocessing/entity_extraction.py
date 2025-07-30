import spacy
import re
from spacy.matcher import PhraseMatcher

nlp = spacy.load("en_core_web_trf")

# TODO: load from config
TITLES = ["mayor", "council member", "councilwoman", "councilman", "representative"]

# Initialize the PhraseMatcher
role_matcher = PhraseMatcher(nlp.vocab)
patterns = [nlp.make_doc(title) for title in TITLES]
role_matcher.add("TITLES", patterns)

def extract_with_context(pattern, text):
    return [
        match.group().rstrip(".")  # Remove trailing dots from the match
        for match in re.finditer(pattern, text)
    ]

# Extract titles using the matcher
def extract_roles(doc):
    matches = role_matcher(doc)
    return [doc[start:end].text for match_id, start, end in matches]

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
    
    found_emails = [token.text for token in doc if token.like_email] 

    # Prepare patterns for phones
    # TODO: add regex to nlp
    phone_pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    found_phones = extract_with_context(phone_pattern, text)

    found_roles = extract_roles(doc)

    return found_people, found_dates, found_emails, found_phones, found_roles


