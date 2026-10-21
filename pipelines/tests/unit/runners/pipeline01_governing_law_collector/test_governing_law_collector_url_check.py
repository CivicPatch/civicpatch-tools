import pytest
from runners.pipeline01_governing_law_collector.url_check import ConfigUrl, config_urls
from shared.utils.layered_config import ConfigFile

pytestmark = pytest.mark.unit

_PATH = "vt/local/config.yml"


def _config(governing_law: dict | None) -> ConfigFile:
    return ConfigFile.model_validate({"governing_law": governing_law} if governing_law else {})


def test_the_charter_index_then_each_classifications_general_law_once():
    config = _config({
        "charter_terms": ["Charter"],
        "charter_link_list": {"url": "https://vt.gov/24APPENDIX", "title": "Chapter {*} : {lsad} of {place}"},
        "classifications": {
            "town": {"lsad": ["town"], "governed_by": "charter_or_general_law", "general_law": ["https://vt.gov/17/2646", "https://vt.gov/24/871"]},
            "city": {"lsad": ["city"], "governed_by": "charter"},
            "gore": {"lsad": ["gore"], "governed_by": "general_law", "general_law": ["https://vt.gov/17/2646"]},
        },
    })

    assert [config_url.url for config_url in config_urls(_PATH, config)] == [
        "https://vt.gov/24APPENDIX", "https://vt.gov/17/2646", "https://vt.gov/24/871"
    ]


def test_each_url_names_the_file_it_came_from():
    config = _config({"charter_terms": [], "classifications": {"county": {"lsad": ["county"], "governed_by": "general_law", "general_law": ["https://vt.gov/24/005"]}}})

    assert config_urls(_PATH, config) == [ConfigUrl(config_path=_PATH, url="https://vt.gov/24/005")]


def test_a_file_without_governing_law_names_no_urls():
    assert config_urls(_PATH, _config(None)) == []
