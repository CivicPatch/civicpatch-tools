import spacy
import re
from spacy.matcher import PhraseMatcher
import utils.config_utils as config_utils

# Other global variables
_nlp = None
_keyword_matchers = {}

def get_nlp():
    """Lazy load the SpaCy model with only needed components."""
    global _nlp
    if _nlp is None:
        # Use smaller model and disable unnecessary components
        _nlp = spacy.load("en_core_web_sm", 
                         disable=["lemmatizer", "textcat", "attribute_ruler"])
    return _nlp

def extract_keywords(doc, government_type):
    """
    Extract keywords using a PhraseMatcher, similar to roles/divisions.
    """
    if not government_type:
        return []
    matcher = get_keyword_matcher(government_type)
    matches = matcher(doc)
    return [doc[start:end].text for match_id, start, end in matches]

def setup_keyword_entities(government_type):
    """
    Setup function to initialize the keyword matcher for the given government type.
    """
    nlp = get_nlp()
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    if government_type:
        context_keywords = config_utils.get_context_keywords(government_type)
        patterns = [nlp.make_doc(kw.lower()) for kw in context_keywords]
        matcher.add("KEYWORD", patterns)
    return matcher

def get_keyword_matcher(government_type):
    """
    Returns a cached PhraseMatcher for the given government_type.
    """
    if government_type not in _keyword_matchers:
        _keyword_matchers[government_type] = setup_keyword_entities(government_type)
    return _keyword_matchers[government_type]

def extract_with_context(pattern, text):
    return [
        match.group().rstrip(".")  # Remove trailing dots from the match
        for match in re.finditer(pattern, text)
    ]

# Check if the node contains relevant data
def extract_data(text, government_type):
    """Extract relevant data from the given text."""
    nlp = get_nlp()
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
    phone_pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    found_phones = extract_with_context(phone_pattern, text)

    # Extract keywords using PhraseMatcher
    keywords = extract_keywords(doc, government_type)
    return found_people, found_dates, found_emails, found_phones, keywords


