import os
import boto3
import zipfile
import tempfile
from typing import BinaryIO
from botocore.client import Config
from fastapi import UploadFile

EXPIRATION_ONE_DAY_IN_SECONDS = 86400

def upload_file_to_storage(
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str,
    file_name: str,
    bucket_name: str,
    file: BinaryIO
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
        # Debug print
        print(f"Uploading to bucket: {bucket_name}, key: {file_name}")
        
        # Reset file pointer
        file.seek(0)
        
        # Upload file with minimal configuration
        storage_client.upload_fileobj(
            file,
            bucket_name,
            file_name
        )

        # Generate presigned URL
        presigned_url = storage_client.generate_presigned_url(
            ClientMethod='get_object',
            Params={
                'Bucket': bucket_name,
                'Key': file_name
            },
            ExpiresIn=EXPIRATION_ONE_DAY_IN_SECONDS    
        )
        
        print(f"Successfully uploaded and generated URL for {file_name}")
        return presigned_url
        
    except Exception as e:
        print(f"Error during upload: {str(e)}")
        raise IOError(f"Upload failed: {str(e)}")

async def process_zip_file(
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str,
    upload_file: UploadFile
) -> dict:
    """Process a zip file: extract and upload image contents to storage."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_zip_path = os.path.join(temp_dir, upload_file.filename)
        
        try:
            # Read content and save to temp file
            content = await upload_file.read()
            with open(temp_zip_path, 'wb') as temp_file:
                temp_file.write(content)
            
            # Verify zip file is valid before processing
            if not zipfile.is_zipfile(temp_zip_path):
                raise ValueError("Invalid zip file format")

            # Open and process zip file
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                # Check for images directory
                has_images = any('images' in name.lower() for name in zip_ref.namelist())
                if not has_images:
                    return {"uploaded_urls": [], "zip_url": ""}
                    
                # Extract and process files
                zip_ref.extractall(temp_dir)
                
                # Walk through extracted contents
                uploaded_urls = []
                for root, dirs, files in os.walk(temp_dir):
                    if 'images' in dirs:
                        images_dir = os.path.join(root, 'images')
                        urls = await process_images_directory(
                            images_dir,
                            storage_endpoint,
                            storage_access_key_id,
                            storage_secret_access_key
                        )
                        uploaded_urls.extend(urls)
                        
        except zipfile.BadZipFile:
            raise ValueError("Corrupted zip file")
        except Exception as e:
            raise IOError(f"Failed to process zip file: {str(e)}")
        finally:
            await upload_file.close()

    print("uploaded url")
    print(uploaded_urls)
    return {"uploaded_urls": uploaded_urls, "zip_url": ""}

async def process_images_directory(
    images_dir: str,
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str
) -> list[str]:
    """Process images directory and return list of uploaded file URLs"""
    uploaded_urls = []
    for img_root, _, img_files in os.walk(images_dir):
        for filename in img_files:
            file_path = os.path.join(img_root, filename)
            try:
                # Get parts of the path after 'data_source'
                parts = file_path.split('data_source/')
                if len(parts) != 2:
                    continue
                    
                # Use the second part as the relative path
                rel_path = parts[1]
                # Normalize the path to remove any .. or . components
                clean_path = os.path.normpath(rel_path).replace('\\', '/')
                dest_path = f"open-data/{clean_path}"
                
                with open(file_path, 'rb') as img_file:
                    url = upload_file_to_storage(
                        storage_endpoint,
                        storage_access_key_id,
                        storage_secret_access_key,
                        dest_path,
                        "civicpatch",
                        img_file
                    )
                    uploaded_urls.append(url)
            except (ValueError, IndexError):
                continue
    
    return uploaded_urls
