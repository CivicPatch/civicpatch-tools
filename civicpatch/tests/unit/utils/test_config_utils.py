from utils.config_utils import get_context_keywords

def test_get_context_keywords_mayor_council():
    keywords = get_context_keywords('mayor_council')
    # Check that some expected keywords are present (actual config-driven)
    assert 'mayor' in keywords
    assert 'position' in keywords
    # Check for some common aliases or related terms
    assert any(k in keywords for k in ['mayor'])
    assert any(k in keywords for k in ['city council'])
    # Ensure the result is not empty
    assert len(keywords) > 0