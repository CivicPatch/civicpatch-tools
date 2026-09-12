import pytest
import yaml

from lib import elections


def _write_yaml(tmp_path, data):
    path = tmp_path / "elections.yaml"
    path.write_text(yaml.safe_dump(data))
    return path


@pytest.fixture(autouse=True)
def _clear_cache():
    elections._load_elections.cache_clear()
    yield
    elections._load_elections.cache_clear()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_upcoming_elections_parses_entries(tmp_path, mocker):
    path = _write_yaml(
        tmp_path,
        [{"date": "2026-11-03", "state": "wa", "title": "General Election", "note": "Mayor"}],
    )
    mocker.patch.object(elections, "_ELECTIONS_PATH", path)

    result = await elections.get_upcoming_elections()

    assert len(result) == 1
    assert result[0].state == "wa"
    assert result[0].title == "General Election"
    assert result[0].note == "Mayor"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_upcoming_elections_note_is_optional(tmp_path, mocker):
    path = _write_yaml(tmp_path, [{"date": "2026-11-03", "state": "wa", "title": "General Election"}])
    mocker.patch.object(elections, "_ELECTIONS_PATH", path)

    result = await elections.get_upcoming_elections()

    assert result[0].note is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_upcoming_elections_empty_file(tmp_path, mocker):
    path = _write_yaml(tmp_path, [])
    mocker.patch.object(elections, "_ELECTIONS_PATH", path)

    assert await elections.get_upcoming_elections() == []
