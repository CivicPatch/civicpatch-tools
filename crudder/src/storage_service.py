import boto3
from botocore.client import Config
from fastapi import UploadFile

EXPIRATION_ONE_DAY_IN_SECONDS = 86400

def upload_file_to_storage(storage_endpoint, storage_access_key_id, storage_secret_access_key, file_name: str, bucket_name: str, file: UploadFile):
    storage_client = boto3.client(
        's3',
        endpoint_url=storage_endpoint,
        aws_access_key_id=storage_access_key_id,
        aws_secret_access_key=storage_secret_access_key,
        config=Config(signature_version='s3v4')
    )
    
    # Upload file
    storage_client.upload_fileobj(
        file.file,  # UploadFile exposes a file-like object
        bucket_name,
        file_name,
    )

    # Generate a pre-signed URL valid for 1 day (86400 seconds)
    presigned_url = storage_client.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': bucket_name,
            'Key': filename
        },
        ExpiresIn=EXPIRATION_ONE_DAY_IN_SECONDS
    )

    return presigned_url