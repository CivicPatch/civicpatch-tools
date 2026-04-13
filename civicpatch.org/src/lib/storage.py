import boto3
from typing import BinaryIO
from botocore.client import Config
from fastapi import UploadFile
import zipfile
import os
import tempfile
import shutil
import fnmatch
import yaml
import glob
import json
import lib.files as file_utils
from datetime import datetime, timedelta
from urllib.parse import urlparse
import environment

EXPIRATION_ONE_DAY_IN_SECONDS = 86400

# TODO: Move to redis
_url_cache: dict[str, tuple[str, datetime]] = {}
CACHE_TTL_SECONDS = 3600 * 12  # 12 hours (regenerate before expiry)

def get_client():
    env = environment.get_env_vars()
    storage_endpoint = env["STORAGE_ENDPOINT"]
    storage_access_key_id = env["STORAGE_ACCESS_KEY_ID"]
    storage_secret_access_key = env["STORAGE_SECRET_ACCESS_KEY"]
    if not all([storage_endpoint, storage_access_key_id, storage_secret_access_key]):
        missing_vars = [
            var
            for var, val in {
                "STORAGE_ENDPOINT": storage_endpoint,
                "STORAGE_ACCESS_KEY_ID": storage_access_key_id,
                "STORAGE_SECRET_ACCESS_KEY": storage_secret_access_key,
            }.items()
            if not val
        ]
        print(f"Missing environment variables for storage client: {', '.join(missing_vars)}")
        raise ValueError("One or more required environment variables for storage client are not set.")

    return boto3.client(
        's3',
        endpoint_url=storage_endpoint,
        aws_access_key_id=storage_access_key_id,
        aws_secret_access_key=storage_secret_access_key,
        region_name="auto",
        config=Config(
            signature_version="s3v4", 
            s3={"addressing_style": "virtual"}
        )
    )

async def upload_file_object_to_storage(
    bucket_name: str,
    file: UploadFile,
    key: str,
    with_presigned_url: bool = False
) -> str:
    """
    Upload a FastAPI UploadFile object to S3-compatible storage.
    """
    storage_client = get_client()
    
    try:
        # Upload file with minimal configuration
        storage_client.upload_fileobj(
            file.file,
            bucket_name,
            key
        )

        if with_presigned_url:
            # Generate presigned URL
            presigned_url = storage_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': key
                },
                ExpiresIn=EXPIRATION_ONE_DAY_IN_SECONDS    
            )

            print(f"Successfully uploaded and generated URL for {file.filename}")
            return presigned_url
        else:  # Return the object URL
            object_url = f"{bucket_name}/{key}"
            print(f"Successfully uploaded {file.filename} to {object_url}")
            return object_url
        
    except Exception as e:
        print(f"Error during upload: {str(e)}")
        raise IOError(f"Upload failed: {str(e)}")

async def upload_file_to_storage(
    bucket_name: str,
    file_path: str,
    key: str,
    with_presigned_url: bool = False
) -> str:
    """
    Upload a file to S3-compatible storage using a file path.

    Args:
        bucket_name (str): The name of the S3 bucket.
        file_path (str): The path to the file to upload.
        key (str): The key (path) to use for the file in the bucket.
        with_presigned_url (bool): Whether to generate a presigned URL for the uploaded file.

    Returns:
        str: The URL of the uploaded file or the presigned URL if requested.
    """
    storage_client = get_client()
    env = environment.get_env_vars()
    STORAGE_ENDPOINT = env.get("STORAGE_ENDPOINT")
    
    try:
        # Open the file in binary read mode
        with open(file_path, "rb") as file_obj:
            # Upload file to S3
            storage_client.upload_fileobj(
                file_obj,
                bucket_name,
                key
            )

        if with_presigned_url:
            # Generate presigned URL
            presigned_url = storage_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': key
                },
                ExpiresIn=EXPIRATION_ONE_DAY_IN_SECONDS    
            )

            print(f"Successfully uploaded and generated URL for {file_path}")
            return presigned_url
        else:  # Return the object URL
            object_url = f"{STORAGE_ENDPOINT}/{bucket_name}/{key}"
            print(f"Successfully uploaded {file_path} to {object_url}")
            return object_url
        
    except Exception as e:
        print(f"Error during upload: {str(e)}")
        raise IOError(f"Upload failed: {str(e)}")

def get_presigned_url_cached(
    bucket_name: str,
    key: str,
    expiration: int = EXPIRATION_ONE_DAY_IN_SECONDS
) -> str:
    """
    Get a presigned URL, using cache if available and not expired.
    
    Args:
        bucket_name: The S3 bucket name
        key: The object key
        expiration: URL expiration time in seconds
    
    Returns:
        Presigned URL for the object
    """
    cache_key = f"{bucket_name}/{key}"
    
    # Check cache
    if cache_key in _url_cache:
        url, created_at = _url_cache[cache_key]
        if datetime.now() - created_at < timedelta(seconds=CACHE_TTL_SECONDS):
            return url
    
    # Generate new URL
    storage_client = get_client()
    presigned_url = storage_client.generate_presigned_url(
        ClientMethod='get_object',
        Params={'Bucket': bucket_name, 'Key': key},
        ExpiresIn=expiration
    )
    
    # Cache it
    _url_cache[cache_key] = (presigned_url, datetime.now())
    
    return presigned_url


def get_presigned_url_from_object_url(
    object_url: str,
    expiration: int = EXPIRATION_ONE_DAY_IN_SECONDS
) -> str:
    """
    Generate a presigned URL from a full storage object URL.
    
    Args:
        object_url: Full URL like "https://endpoint.com/bucket/path/to/file.jpg"
        expiration: URL expiration time in seconds
    
    Returns:
        Presigned URL for the object
    """
    
    if not object_url:
        return ""
    
    parsed = urlparse(object_url)
    
    # Path style: https://endpoint.com/bucket-name/key
    path_parts = parsed.path.lstrip('/').split('/', 1)
    if len(path_parts) < 2:
        raise ValueError(f"Invalid object URL format: {object_url}")
    
    bucket_name = path_parts[0]
    key = path_parts[1]
    
    return get_presigned_url_cached(bucket_name, key, expiration)

def get_civicpatch_artifacts_url(key: str) -> str:
    url = "https://civicpatch-artifacts.civicpatch.org"
    return f"{url}/{key}"


def get_presigned_put_url(bucket_name: str, key: str, expiration: int = 3600) -> str:
    return get_client().generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucket_name, "Key": key, "ContentType": "application/json"},
        ExpiresIn=expiration,
    )


def delete_object(bucket_name: str, key: str) -> None:
    get_client().delete_object(Bucket=bucket_name, Key=key)