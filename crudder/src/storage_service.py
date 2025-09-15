import os
import shutil
import boto3
import zipfile
import tempfile
from typing import BinaryIO
from botocore.client import Config
from fastapi import UploadFile
import posixpath

EXPIRATION_ONE_DAY_IN_SECONDS = 86400

def upload_file_to_storage(
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str,
    file_name: str,
    bucket_name: str,
    file: BinaryIO,
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
        # Reset file pointer
        file.seek(0)
        
        # Upload file with minimal configuration
        storage_client.upload_fileobj(
            file,
            bucket_name,
            file_name
        )

        if with_presigned_url:
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
        else: # Return the object URL
            object_url = f"{storage_endpoint}/{bucket_name}/{file_name}"
            print(f"Successfully uploaded {file_name} to {object_url}")
            return object_url
        
    except Exception as e:
        print(f"Error during upload: {str(e)}")
        raise IOError(f"Upload failed: {str(e)}")

async def process_zip_file(
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str,
    upload_file: UploadFile
) -> dict:
    """Process a zip file: extract, remove images, re-zip, and upload to Cloudflare R2."""
    uploaded_urls = []
    zip_url = ""
    
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
                
                        # Remove everything under the images directory
                        shutil.rmtree(images_dir)

        except zipfile.BadZipFile:
            raise ValueError("Corrupted zip file")
        except Exception as e:
            raise IOError(f"Failed to process zip file: {str(e)}")
        finally:
            await upload_file.close()
    
        # Re-zip contents, now without images
        zip_file_name = f"processed_{upload_file.filename}"
        zip_file_path = os.path.join(temp_dir, zip_file_name)

        try:
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Exclude the new zip file itself
                        if file_path == zip_file_path:
                            continue
                        # Preserve directory structure
                        zipf.write(file_path, arcname=os.path.relpath(file_path, temp_dir))
                
        except Exception as e:
            raise IOError(f"Failed to create zip file: {str(e)}")

        # Upload the re-zipped file to Cloudflare R2
        try:
            with open(zip_file_path, 'rb') as zip_file:
                zip_url = upload_file_to_storage(
                    storage_endpoint,
                    storage_access_key_id,
                    storage_secret_access_key,
                    zip_file_name,
                    "crudder",
                    zip_file,
                    with_presigned_url=True
                )
        except Exception as e:
            raise IOError(f"Failed to upload re-zipped file to Cloudflare R2: {str(e)}")

    print(uploaded_urls)
    print(f"Re-zipping completed: {zip_file_path}")
    return {"uploaded_urls": uploaded_urls, "zip_url": zip_url}

async def process_images_directory(
    images_dir: str,
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str
) -> list[str]:
    """Process images directory and return list of uploaded file URLs"""
    uploaded_urls = []
    print(f"Processing images in directory: {images_dir}")
    images_dir_parts = images_dir.split("data_source")

    if len(images_dir_parts) < 2:
        print("No 'data_source' in path, cannot determine parent directory.")
        return uploaded_urls

    municipality_path = images_dir_parts[1].lstrip(os.sep)
    dest_prefix_path = posixpath.normpath(posixpath.join("open-data", municipality_path))

    # Remove all files with prefix first
    delete_files_with_prefix(
        storage_endpoint=storage_endpoint,
        storage_access_key_id=storage_access_key_id,
        storage_secret_access_key=storage_secret_access_key,
        bucket_name="civicpatch",
        prefix=dest_prefix_path
    )

    # Process all files in images directory
    for filename in os.listdir(images_dir):
        file_path = os.path.join(images_dir, filename)
        if os.path.isfile(file_path):
            try:
                # Create S3 key with format: open-data/{municipality}/images/{filename}
                dest_path = posixpath.join(dest_prefix_path, filename)

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
            except Exception as e:
                print(f"Error uploading {filename}: {str(e)}")
                continue
    
    return uploaded_urls

def delete_files_with_prefix(
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str,
    bucket_name: str,
    prefix: str
) -> int:
    """
    Delete all objects in bucket with given prefix
    
    Returns:
        int: Number of objects deleted
    """
    s3 = boto3.resource(
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
        bucket = s3.Bucket(bucket_name)
        response = bucket.objects.filter(Prefix=prefix).delete()

        if not response:
            print(f"No objects found with prefix '{prefix}' to delete.")
            return 0
        
        # Response is a list of deleted objects
        deleted_count = len(response[0].get('Deleted', []))
        if deleted_count > 0:
            print(f"Deleted {deleted_count} objects with prefix '{prefix}'")
            
        return deleted_count
        
    except Exception as e:
        raise IOError(f"Deletion failed: {str(e)}")
