import pytest
from unittest.mock import MagicMock, patch
from steps.step_03_preprocessing.entity_extraction import (
    extract_data,
    extract_roles,
    extract_divisions,
    extract_with_context,
    get_division_matcher,
    get_role_matcher,
)
import spacy

@pytest.fixture
def nlp():
    """Fixture to load a blank Spacy NLP pipeline."""
    return spacy.blank("en")

@pytest.fixture
def mock_doc(nlp):
    """Fixture to mock a Spacy Doc object."""
    doc = nlp("This is a test document.")
    doc.ents = []
    return doc

def test_extract_with_context():
    """
    Test extract_with_context to ensure it extracts matches using regex.
    """
    text = "Call us at (123) 456-7890 or 123-456-7890."
    pattern = r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
    matches = extract_with_context(pattern, text)

    assert matches == ["(123) 456-7890", "123-456-7890"]

@patch("steps.step_02_preprocessing.entity_extraction.get_role_matcher")
def test_extract_roles(mock_get_role_matcher, nlp):
    """
    Test extract_roles to ensure it extracts roles using the role matcher.
    """
    mock_matcher = MagicMock()
    mock_matcher.return_value = [(1, 3, 5)]  # Mocked match (match_id, start, end)
    mock_get_role_matcher.return_value = mock_matcher

    doc = nlp("John Doe is a council member.")
    roles = extract_roles(doc)

    assert roles == ["council member"]
    mock_get_role_matcher.assert_called_once()

@patch("steps.step_02_preprocessing.entity_extraction.get_division_matcher")
def test_extract_divisions(mock_get_division_matcher, nlp):
    """
    Test extract_divisions to ensure it extracts divisions using the division matcher.
    """
    mock_matcher = MagicMock()
    mock_matcher.return_value = [(1, 3, 5)]  # Mocked match (match_id, start, end)
    mock_get_division_matcher.return_value = mock_matcher

    doc = nlp("This is the at-large division.")
    divisions = extract_divisions(doc)

    assert divisions == ["at-large"]
    mock_get_division_matcher.assert_called_once()

@patch("steps.step_02_preprocessing.entity_extraction.extract_roles")
@patch("steps.step_02_preprocessing.entity_extraction.extract_divisions")
def test_extract_data(mock_extract_divisions, mock_extract_roles, nlp):
    """
    Test extract_data to ensure it extracts all relevant data from text.
    """
    mock_extract_roles.return_value = ["council member"]
    mock_extract_divisions.return_value = ["at-large"]

    text = "John Doe is a council member in the at-large division. Contact: john.doe@example.com or (123) 456-7890."
    doc = nlp(text)
    doc.ents = [
        spacy.tokens.Span(doc, 0, 2, label=doc.vocab.strings["PERSON"]),  # "John Doe"
        spacy.tokens.Span(doc, 9, 12, label=doc.vocab.strings["DATE"]),   # "January 1, 2023"
    ]

    with patch("steps.step_02_preprocessing.entity_extraction.nlp", return_value=doc):
        found_people, found_dates, found_emails, found_phones, found_roles, found_divisions = extract_data(text)

    assert found_people == ["John Doe"]
    assert found_dates == []
    assert found_emails == ["john.doe@example.com"]
    assert found_phones == ["(123) 456-7890"]
    assert found_roles == ["council member"]
    assert found_divisions == ["at-large"]
    mock_extract_roles.assert_called_once_with(doc)
    mock_extract_divisions.assert_called_once_with(doc)