import pytest

from lib.pipeline_artifacts import read_image_map

# --- the image map, read out of the zip ---


@pytest.mark.unit
def test_no_image_map_is_not_an_error(tmp_path):
    """A run that found no photos ships no map. Provenance is simply unknown then."""
    assert read_image_map(str(tmp_path)) == {}


@pytest.mark.unit
def test_the_image_map_is_found_where_the_zip_puts_it(tmp_path):
    """Under `images/`, which is why it arrives at all — the image pattern sweeps that
    directory, so the map ships beside the files it describes."""
    images = tmp_path / "data_source" / "wa" / "local" / "buckley" / "images"
    images.mkdir(parents=True)
    (images / "image_map.json").write_text('{"ann.png": "https://alpha.gov/ann.png"}')

    assert read_image_map(str(tmp_path)) == {"ann.png": "https://alpha.gov/ann.png"}
