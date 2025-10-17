import pytest
from unittest.mock import patch, MagicMock
from pipeline import Pipeline, PipelineState
import json

@pytest.fixture
def mock_context_path(tmp_path):
    """
    Fixture to mock `data_path_utils.get_pipeline_context_file_path`.
    """
    with patch("utils.data_path_utils.get_pipeline_context_file_path") as mock_get_context_path:
        # Set up a temporary file path for the mocked context
        mock_context_file_path = tmp_path / "mock_pipeline_context.json"
        mock_get_context_path.return_value = str(mock_context_file_path)
        yield mock_get_context_path, mock_context_file_path

@patch("pipeline.collect.collect")
@patch("pipeline.preprocess.preprocess")
@patch("pipeline.process.process")
@patch("pipeline.validate.validate")
@patch("pipeline.submit.submit")
@patch("pipeline.report.report")
def test_pipeline_run(mock_report, mock_submit, mock_validate, mock_process, mock_preprocess, mock_collect, mock_context_path):
    mock_get_context_path, mock_context_file_path = mock_context_path

    # Mock the behavior of each step with JSON-serializable data
    mock_collect.return_value = {"collected_data": "some_data"}
    mock_preprocess.return_value = {"preprocessed_data": "some_preprocessed_data"}
    mock_process.return_value = {"processed_data": "some_processed_data"}
    mock_validate.return_value = {"is_valid": True} # Boolean is JSON-serializable
    mock_report.return_value = {"logs": []}
    mock_submit.return_value = {"logs": []}

    # Initialize the pipeline
    pipeline = Pipeline()
    pipeline.set_state(PipelineState.INIT)

    # Run the pipeline
    pipeline.run(state="wa", geoid="5363000")

    # Verify the state transitions and method calls
    assert pipeline.state == PipelineState.DONE
    assert pipeline.context["data"]["collected"] == {"collected_data": "some_data"}
    assert pipeline.context["data"]["preprocessed"] == {"preprocessed_data": "some_preprocessed_data"}
    assert pipeline.context["data"]["processed"] == {"processed_data": "some_processed_data"}
    assert pipeline.context["data"]["validated"] == {"is_valid": True}
    assert pipeline.context["data"]["reported"] == {"logs": []}
    assert pipeline.context["data"]["submitted"] == {"logs": []}

    mock_collect.assert_called_once_with("wa", "5363000")
    mock_preprocess.assert_called_once_with({"collected_data": "some_data"})
    mock_process.assert_called_once_with({"preprocessed_data": "some_preprocessed_data"})
    mock_validate.assert_called_once_with({"processed_data": "some_processed_data"})
    mock_report.assert_called_once_with({"is_valid": True})
    mock_submit.assert_called_once_with({"logs": []})

    # Verify the context file was created
    assert mock_context_file_path.exists()
    with open(mock_context_file_path, "r") as f:
        saved_context = json.load(f)
    assert saved_context == pipeline.context

