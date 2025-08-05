import pytest
import spacy
from steps.step_03_preprocessing.entity_extraction import extract_data

@pytest.fixture(scope="module")
def nlp():
    """Fixture to load the actual Spacy NLP pipeline."""
    return spacy.load("en_core_web_trf")

def test_extract_data_integration(nlp):
    """
    Integration test for extract_data to ensure it works with real data and configuration.
    """
    # Example text to process
    text = (
        "John Doe is a council member in the at-large division. "
        "Contact: john.doe@example.com or (123) 456-7890."
    )

    # Call the function with real NLP and configuration
    found_people, found_dates, found_emails, found_phones, found_roles, found_divisions = extract_data(text)

    # Assertions
    assert "John Doe" in found_people
    assert found_dates == []  # No dates in the text
    assert "john.doe@example.com" in found_emails
    assert "(123) 456-7890" in found_phones
    assert "council member" in found_roles
    assert "at-large" in found_divisions