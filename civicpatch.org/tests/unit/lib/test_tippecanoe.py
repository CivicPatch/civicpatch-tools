from unittest.mock import MagicMock, patch

import pytest

from lib.tippecanoe import run_tippecanoe

pytestmark = pytest.mark.unit


def test_calls_tippecanoe_with_named_layers(tmp_path):
    states = tmp_path / "states.geojson"
    counties = tmp_path / "counties.geojson"
    output = tmp_path / "co.pmtiles"
    states.write_text("{}")
    counties.write_text("{}")

    mock_proc = MagicMock()
    mock_proc.stderr = iter(["94.1%  14/3702/6902\n"])
    mock_proc.returncode = 0
    mock_proc.wait.return_value = 0

    with patch("lib.tippecanoe.subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock_proc
        run_tippecanoe(
            [("states", states, 0), ("counties", counties, 5)],
            output,
            label="co",
        )

    args = mock_popen.call_args[0][0]
    assert args[0] == "tippecanoe"
    assert "-o" in args
    assert str(output) in args
    assert "--no-feature-limit" in args
    full_cmd = " ".join(args)
    assert '"layer": "states"' in full_cmd
    assert '"layer": "counties"' in full_cmd
    assert '"minzoom": 0' in full_cmd
    assert '"minzoom": 5' in full_cmd


def test_raises_on_nonzero_exit(tmp_path):
    states = tmp_path / "states.geojson"
    output = tmp_path / "co.pmtiles"
    states.write_text("{}")

    mock_proc = MagicMock()
    mock_proc.stderr = iter([])
    mock_proc.returncode = 1
    mock_proc.wait.return_value = 1

    with patch("lib.tippecanoe.subprocess.Popen") as mock_popen:
        mock_popen.return_value = mock_proc
        with pytest.raises(Exception):
            run_tippecanoe([("states", states, 0)], output)


class _ImmediateTimer:
    """Fires its callback synchronously on start() instead of waiting — lets the
    timeout path be tested without a real multi-minute sleep."""

    def __init__(self, interval, function):
        self._function = function

    def start(self):
        self._function()

    def cancel(self):
        pass


def test_kills_and_raises_timeout_error_when_wedged(tmp_path):
    states = tmp_path / "states.geojson"
    output = tmp_path / "co.pmtiles"
    states.write_text("{}")

    mock_proc = MagicMock()
    mock_proc.stderr = iter([])
    mock_proc.returncode = -9
    mock_proc.wait.return_value = -9

    with (
        patch("lib.tippecanoe.subprocess.Popen") as mock_popen,
        patch("lib.tippecanoe.threading.Timer", _ImmediateTimer),
    ):
        mock_popen.return_value = mock_proc
        with pytest.raises(TimeoutError):
            run_tippecanoe([("states", states, 0)], output)

    mock_proc.kill.assert_called_once()
