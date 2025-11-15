import boto3
from typing import BinaryIO
from botocore.client import Config
from fastapi import UploadFile

EXPIRATION_ONE_DAY_IN_SECONDS = 86400

async def upload_file_to_storage(
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str,
    bucket_name: str,
    file: UploadFile,
    with_presigned_url: bool = False
) -> str:
    """
    Upload a file to S3-compatible storage.
    """
    storage_client = boto3.client(
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
    
    try:
        # Upload file with minimal configuration
        storage_client.upload_fileobj(
            file.file,
            bucket_name,
            file.filename
        )

        if with_presigned_url:
            # Generate presigned URL
            presigned_url = storage_client.generate_presigned_url(
                ClientMethod='get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': file.filename
                },
                ExpiresIn=EXPIRATION_ONE_DAY_IN_SECONDS    
            )

            print(f"Successfully uploaded and generated URL for {file.filename}")
            return presigned_url
        else: # Return the object URL
            object_url = f"{storage_endpoint}/{bucket_name}/{file.filename}"
            print(f"Successfully uploaded {file.filename} to {object_url}")
            return object_url
        
    except Exception as e:
        print(f"Error during upload: {str(e)}")
        raise IOError(f"Upload failed: {str(e)}")
