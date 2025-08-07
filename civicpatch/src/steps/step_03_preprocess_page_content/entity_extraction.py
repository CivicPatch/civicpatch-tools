import spacy
import re
from spacy.matcher import PhraseMatcher
import utils.config_utils as config_utils

nlp = spacy.load("en_core_web_trf")

# Global variables to store the matchers
division_matcher = None
role_matcher = None

def setup_division_entities():
    """
    Setup function to initialize the division entities.
    """
    matcher = PhraseMatcher(nlp.vocab)
    divisions = config_utils.get_divisions()
    division_patterns = []

    for division_key, division_details in divisions.items():
        aliases = division_details.get("aliases", [])
        division_patterns.append(division_key)
        division_patterns += aliases  # Flatten aliases into the list

    # Convert patterns to Doc objects
    patterns = [nlp.make_doc(pattern) for pattern in division_patterns]
    matcher.add("DIVISION", patterns)
    return matcher

def setup_role_entities():
    """
    Setup function to initialize the role entities.
    """
    matcher = PhraseMatcher(nlp.vocab)
    government_types = config_utils.get_government_types()
    role_patterns = []

    for government_type_key, government_type_details in government_types.items():
        roles = government_type_details.get("roles", [])
        for role_item in roles:
            role_name = role_item.get("role")
            aliases = role_item.get("aliases", [])
            role_patterns.append(role_name)
            role_patterns += aliases  # Flatten aliases into the list

    # Convert patterns to Doc objects
    patterns = [nlp.make_doc(pattern) for pattern in role_patterns]
    matcher.add("ROLE", patterns)
    return matcher

def get_division_matcher():
    """
    Lazy initialization for the division matcher.
    """
    global division_matcher
    if division_matcher is None:
        division_matcher = setup_division_entities()
    return division_matcher

def get_role_matcher():
    """
    Lazy initialization for the role matcher.
    """
    global role_matcher
    if role_matcher is None:
        role_matcher = setup_role_entities()
    return role_matcher

def extract_with_context(pattern, text):
    return [
        match.group().rstrip(".")  # Remove trailing dots from the match
        for match in re.finditer(pattern, text)
    ]

# Extract titles using the matcher
def extract_roles(doc):
    """
    Extract roles using the role matcher.
    """
    matcher = get_role_matcher()
    matches = matcher(doc)
    return [doc[start:end].text for match_id, start, end in matches]

def extract_divisions(doc):
    """
    Extract divisions using the division matcher.
    """
    matcher = get_division_matcher()
    matches = matcher(doc)
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
    found_divisions = extract_divisions(doc)

    return found_people, found_dates, found_emails, found_phones, found_roles, found_divisions


