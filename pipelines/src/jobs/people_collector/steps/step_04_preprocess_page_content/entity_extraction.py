import spacy
import re
from spacy.matcher import PhraseMatcher
import shared.utils.config_utils as config_utils
import json
from typing import Dict, List

# Global variables
_nlp = None
keyword_matchers = {}

def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_md")
        _nlp.max_length = 2000000  # Increase max length if needed
    return _nlp

# This belongs under search_links
def sort_urls_by_keyword_similarity(keywords, urls):
    nlp = get_nlp()
    pattern_docs = [nlp(k) for k in keywords]
    pattern_vectors = [doc.vector for doc in pattern_docs]  # Precompute vectors for keywords
    sorted_urls = []

    for url, text in urls:
        doc = nlp(f"{url} {text}")
        doc_vector = doc.vector  # Precompute vector for the current document
        # Compute similarity scores using dot product
        score = max(doc_vector.dot(pattern_vector) for pattern_vector in pattern_vectors)
        sorted_urls.append((url, float(score)))  # Convert score to Python float

    sorted_by_score = sorted(sorted_urls, key=lambda x: x[1], reverse=True)
    #with open("sorted_urls_debug.txt", "w") as f:
    #    # Convert scores to float for JSON serialization
    #    json.dump({"keywords": keywords, "sorted_urls": [(url, float(score)) for url, score in sorted_by_score]}, f, indent=2)
    return [url for url, _score in sorted_by_score]

def extract_keywords(doc):
    """Extract keywords using a PhraseMatcher."""
    matcher = setup_keyword_entities()
    matches = matcher(doc)
    return [doc[start:end].text for match_id, start, end in matches]

def setup_keyword_entities():
    """Setup function to initialize the keyword matcher."""
    nlp = get_nlp()
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
    context_keywords = config_utils.get_keywords()
    patterns = [nlp.make_doc(kw.lower()) for kw in context_keywords]
    matcher.add("KEYWORD", patterns)
    return matcher

def is_valid_phone_number(phone_text):
    """Validate phone number format and reject invalid patterns."""
    # Remove extensions for validation
    clean_phone = re.sub(r'\s*(?:x|ext\.?|extension).*$', '', phone_text, flags=re.IGNORECASE).strip()
    
    # Reject (XXX)XXXXXXX pattern (no space/separator after closing paren)
    if re.match(r'.*\(\d{3}\)\d{7}', clean_phone):
        return False
    
    # Extract only digits
    digits_only = re.sub(r'\D', '', clean_phone)
    
    # Handle country code
    if digits_only.startswith('1') and len(digits_only) == 11:
        digits_only = digits_only[1:]
    
    # Must be exactly 10 digits
    if len(digits_only) != 10:
        return False
    
    # Reject obvious invalid patterns
    if digits_only == '0000000000':
        return False
    
    return True

def extract_phones_with_regex(text):
    found_phones = []
    
    if not text:
        return found_phones
    
    # Process patterns in order of specificity (most specific first)
    patterns = [
        r'\+1\s+\([0-9]{3}\)\s+[0-9]{3}-[0-9]{4}',  # +1 (123) 456-7890
        r'\+1\s+[0-9]{3}-[0-9]{3}-[0-9]{4}',        # +1 987-654-3210 (with space)
        r'\+1[0-9]{3}-[0-9]{3}-[0-9]{4}',           # +1987-654-3210 (no space) - ADD THIS
        r'\b1-[0-9]{3}-[0-9]{3}-[0-9]{4}\b',        # 1-123-456-7890  
        r'\b1\.[0-9]{3}\.[0-9]{3}\.[0-9]{4}\b',     # 1.123.456.7890
        r'\([0-9]{3}\)\s+[0-9]{3}-[0-9]{4}',        # (123) 456-7890
        r'\b[0-9]{3}\.[0-9]{3}\.[0-9]{4}\b',        # 123.456.7890
        r'\b[0-9]{3}-[0-9]{3}-[0-9]{4}\b',          # 123-456-7890
        r'\b[0-9]{3}\s+[0-9]{3}\s+[0-9]{4}\b',      # 123 456 7890
        r'\b[0-9]{3}\s+[0-9]{3}-[0-9]{4}\b',        # 123 456-7890
        r'\b[0-9]{10}\b',                           # 1234567890
    ] 
    
    # Track which parts of text we've already matched
    used_positions = set()
    
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            start, end = match.span()
            # Skip if this overlaps with already matched text
            if any(pos in range(start, end) for pos in used_positions):
                continue
                
            phone = match.group().strip()
            if phone not in found_phones:
                found_phones.append(phone)
                # Mark these positions as used
                used_positions.update(range(start, end))
    
    return found_phones

def extract_data(text):
    """Extract relevant data from the given text."""
    nlp = get_nlp()
    doc = nlp(text)
    
    found_people = []
    found_dates = []
    found_emails = []
    
    # PRIMARY: Extract phone numbers using regex (no spaCy interference)
    found_phones = extract_phones_with_regex(text)
    
    # Extract other entities using spaCy
    for ent in doc.ents:
        if ent.label_ == "PERSON" and len(ent.text.split()) > 1:
            found_people.append(ent.text)
        elif ent.label_ == "DATE":
            found_dates.append(ent.text)
    
    # Extract emails
    found_emails = [token.text for token in doc if token.like_email]
    
    # Extract keywords
    keywords = extract_keywords(doc)
    
    return found_people, found_dates, found_emails, found_phones, keywords