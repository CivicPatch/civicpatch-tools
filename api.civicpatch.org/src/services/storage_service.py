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
import utils.file_utils as file_utils

EXPIRATION_ONE_DAY_IN_SECONDS = 86400

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")

def get_client():
    if not all([STORAGE_ENDPOINT, STORAGE_ACCESS_KEY_ID, STORAGE_SECRET_ACCESS_KEY]):
        missing_vars = [
            var
            for var, val in {
                "STORAGE_ENDPOINT": STORAGE_ENDPOINT,
                "STORAGE_ACCESS_KEY_ID": STORAGE_ACCESS_KEY_ID,
                "STORAGE_SECRET_ACCESS_KEY": STORAGE_SECRET_ACCESS_KEY,
            }.items()
            if not val
        ]
        print(f"Missing environment variables for storage client: {', '.join(missing_vars)}")
        raise ValueError("One or more required environment variables for storage client are not set.")

    return boto3.client(
        's3',
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=STORAGE_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(
            signature_version="s3v4", 
            s3={"addressing_style": "virtual"}
        )
    )

async def upload_file_to_storage(
    bucket_name: str,
    file: UploadFile,
    key: str,
    with_presigned_url: bool = False
) -> str:
    """
    Upload a file to S3-compatible storage.
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