import pytest
from unittest.mock import patch, MagicMock
from services.storage_service import upload_file_to_storage

@pytest.fixture
def mock_get_client(mocker):
    return mocker.patch("services.storage_service.get_client")

@patch("builtins.open", new_callable=MagicMock)
def test_upload_file_to_storage(mock_open, mock_get_client):
    # Mock the S3 client
    mock_s3_client = MagicMock()
    mock_get_client.return_value = mock_s3_client

    # Mock the presigned URL generation
    mock_s3_client.generate_presigned_url.return_value = "http://example.com/presigned_url"

    # Mock the file upload
    mock_s3_client.upload_fileobj = MagicMock()

    # Call the function
    file_path = "/path/to/file.txt"
    bucket_name = "test-bucket"
    key = "test/file.txt"
    with open(file_path, "wb") as f:
        f.write(b"test content")
    with open(file_path, "rb") as f:
        result = pytest.run(upload_file_to_storage(bucket_name, f, key, with_presigned_url=True))

    # Assertions
    mock_s3_client.upload_fileobj.assert_called_once()
    mock_s3_client.generate_presigned_url.assert_called_once_with(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=86400,
    )
    assert result == "http://example.com/presigned_url"