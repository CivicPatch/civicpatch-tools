import os
import boto3
import pytest
from botocore.client import Config
from botocore.exceptions import ClientError

@pytest.fixture
def s3_client():
    """Fixture to create S3 client with credentials from environment"""
    storage_endpoint = os.getenv("STORAGE_ENDPOINT")
    storage_access_key_id = os.getenv("STORAGE_ACCESS_KEY_ID")
    storage_secret_access_key = os.getenv("STORAGE_SECRET_ACCESS_KEY")
    
    # Verify all required variables are present
    if not all([storage_endpoint, storage_access_key_id, storage_secret_access_key]):
        pytest.skip("Missing required environment variables")
    
    client = boto3.client(
        's3',
        endpoint_url=storage_endpoint,
        aws_access_key_id=storage_access_key_id,
        aws_secret_access_key=storage_secret_access_key,
        region_name='auto',
        config=Config(
            signature_version='s3v4',
            s3={'addressing_style': 'virtual'}
        )
    )
    
    return client

@pytest.mark.parametrize("bucket_name", ['civicpatch', 'crudder'])
def test_bucket_access(s3_client, bucket_name: str):
    """Test if we can list objects in specific buckets"""
    try:
        # Try to list objects (max 1) to test access
        s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        print(f"✓ Successfully accessed bucket: {bucket_name}")
        assert True
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        print(f"✗ Cannot access bucket {bucket_name}: {error_code}")
        pytest.fail(f"Failed to access bucket {bucket_name}: {error_code}")