import pytest
from shared.schemas import GovernmentForm
from shared.utils.government_forms import describe_government_form, name_suffix


@pytest.mark.parametrize("form", list(GovernmentForm))
def test_every_form_has_a_description(form):
    assert describe_government_form(form).startswith(form.value.replace("_", " ") + " (")


def test_the_suffix_is_the_last_word_of_the_name():
    assert name_suffix("Millbury town") == "town"
    assert name_suffix("") == ""
