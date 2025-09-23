import pytest
from steps.step_04_preprocess_page_content.entity_extraction import extract_data

def test_extract_phone_numbers():
    """Test extraction of phone numbers in various formats"""
    text = "Contact me at (123) 456-7890 or 987-654-3210."
    people, dates, emails, phones, keywords = extract_data(text, "mayor_council")
    assert "(123) 456-7890" in phones
    assert "987-654-3210" in phones

def test_extract_emails():
    """Test extraction of email addresses"""
    text = "You can reach me at example@test.com or admin@test.org."
    people, dates, emails, phones, keywords = extract_data(text, "mayor_council")
    assert "example@test.com" in emails
    assert "admin@test.org" in emails

def test_combined_contact_info():
    """Test extraction of combined contact information"""
    text = """
    Contact Information:
    Name: Jane Smith
    Phone: (555) 123-4567
    Email: jane.smith@council.gov
    Start Date: January 15, 2024
    """
    people, dates, emails, phones, keywords = extract_data(text, "mayor_council")
    assert any("Jane Smith" in p for p in people)
    assert "(555) 123-4567" in phones
    assert "jane.smith@council.gov" in emails
    assert any("2024" in d for d in dates)

@pytest.mark.parametrize("contact_info", [
    # Standard formats
    ("(123) 456-7890", "(123) 456-7890"),
    ("123.456.7890", "123.456.7890"),
    ("123-456-7890", "123-456-7890"),
    ("1234567890", "1234567890"),
  
    # With country code
    ("+1 (123) 456-7890", "+1 (123) 456-7890"),
    ("1-123-456-7890", "1-123-456-7890"),
    ("1.123.456.7890", "1.123.456.7890"),
  
    # With extensions (should extract without extension)
    ("(123) 456-7890 x123", "(123) 456-7890"),
    ("123-456-7890 ext. 123", "123-456-7890"),
    ("123.456.7890 extension 123", "123.456.7890"),
  
    # Alternative separators
    ("123 456 7890", "123 456 7890"),
    ("123 456-7890", "123 456-7890"),
  
    # Invalid formats (should not be extracted)
    ("123-456", None),  # Too short
    ("12345678901234", None),  # Too long
    ("123-45-678", None),  # Wrong grouping
    ("(123)4567890", None),  # Missing space after area code
    ("123-456-789", None),  # Missing digit
    ("12345", None),  # Too short
    ("abc-def-ghij", None),  # Non-numeric
])
def test_phone_number_validation(contact_info):
    """Test validation of different phone number formats"""
    number, expected_extracted = contact_info
    text = f"Contact at {number}"
    people, dates, emails, phones, keywords = extract_data(text, "mayor_council")
    
    if expected_extracted is not None:
        # Should extract the phone number
        assert expected_extracted in phones, \
            f"Failed to extract phone number: {number}. Expected: {expected_extracted}, Got: {phones}"
    else:
        # Should not extract anything
        assert len(phones) == 0, \
            f"Should not extract invalid phone number: {number}, but got: {phones}"

@pytest.mark.parametrize("email", [
    ("valid@council.gov", True),
    ("test.name@city.gov", True),
    ("invalid@", False),
    ("not.an.email", False),
])
def test_email_validation(email):
    """Test validation of email addresses"""
    address, should_pass = email
    text = f"Email: {address}"
    people, dates, emails, phones, keywords = extract_data(text, "mayor_council")
    assert (address in emails) == should_pass

def test_extract_with_keywords():
    """Test extraction with government-specific keywords"""
    text = """
    District 5 Representative Bob Johnson
    City Hall, Room 204
    Phone: 555-123-4567
    """
    people, dates, emails, phones, keywords = extract_data(text, "mayor_council")
    assert any("Bob Johnson" in p for p in people)
    assert "555-123-4567" in phones
    assert "District" in keywords
    assert "Representative" in keywords

# Add a new test for multiple phone numbers in complex text
def test_multiple_phone_formats():
    """Test extraction of multiple phone numbers in various formats from complex text"""
    text = """
    Main Office: (123) 456-7890
    Direct Line: +1 987-654-3210
    Fax: 123.456.7890
    After Hours: 1-800-555-1234 ext. 567
    Mobile: 123 456 7890
    International: +1 (555) 123-4567
    Invalid numbers: 123-456 or 12345 or abc-def-ghij
    """
    people, dates, emails, phones, keywords = extract_data(text, "mayor_council")
    
    # Manually specify exactly what should be extracted (based on your regex patterns)
    expected_phones = {
        "(123) 456-7890",           # From: (123) 456-7890
        "+1 987-654-3210",          # From: +1 987-654-3210  
        "123.456.7890",             # From: 123.456.7890
        "1-800-555-1234",           # From: 1-800-555-1234 ext. 567 (extension removed)
        "123 456 7890",             # From: 123 456 7890
        "+1 (555) 123-4567"         # From: +1 (555) 123-4567
    }
    
    # Convert to sets for comparison
    found_phones_set = set(phones)
    
    assert found_phones_set == expected_phones, \
        f"Expected {expected_phones}, but found {found_phones_set}"