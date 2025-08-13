import pytest
from steps.step_04_preprocess_page_content.entity_extraction import extract_divisions, nlp

def test_extract_divisions_basic():
    doc = nlp("She represents ward 5 and at-large districts.")
    divisions = extract_divisions(doc)
    assert "ward" in divisions
    assert "at-large" in divisions

def test_extract_divisions_aliases():
    doc = nlp("He is the council member for council ward 2 and citywide.")
    divisions = extract_divisions(doc)
    assert "council ward" in divisions or "ward" in divisions
    assert "citywide" in divisions

def test_extract_divisions_multiple():
    doc = nlp("District east and ward 3 are both represented.")
    divisions = extract_divisions(doc)
    # Only "ward" will match unless "district east" is in your config
    assert "ward" in divisions