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

EXPIRATION_ONE_DAY_IN_SECONDS = 86400

async def process_and_upload_artifacts(
    zip_upload_file: UploadFile,
    storage_endpoint: str,
    storage_access_key_id: str,
    storage_secret_access_key: str,
    file_suffix: str,
    with_presigned_url: bool = False,
) -> dict:
    """
    Unzip, filter, re-zip, and upload artifacts to S3-compatible storage.
    Returns:
        {
            zip_to_commit: <url or presigned url>,
            debug_files: [<url or presigned url>, ...]
        }
    """
    patterns = [
        "cache/*",
        "images/*",
        "workflow.log",
    ]
    temp_dir = tempfile.mkdtemp()
    extracted_dir = os.path.join(temp_dir, "extracted")
    filtered_dir = os.path.join(temp_dir, "filtered")
    debug_dir = os.path.join(temp_dir, "debug")
    os.makedirs(extracted_dir, exist_ok=True)
    os.makedirs(filtered_dir, exist_ok=True)
    os.makedirs(debug_dir, exist_ok=True)

    # Save uploaded zip to temp file
    zip_path = os.path.join(temp_dir, "upload.zip")
    with open(zip_path, "wb") as f:
        f.write(await zip_upload_file.read())

    # Extract all files
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extracted_dir)

    # Move relevant files to data_source debug_dir, rest to filtered_dir 
    for root, dirs, files in os.walk(extracted_dir):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), extracted_dir)
            # Check if matches any pattern
            if any(fnmatch.fnmatch(rel_path, f"data_source/*/local/*/{pat}") for pat in patterns):
                dest_path = os.path.join(debug_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.move(os.path.join(root, file), dest_path)
            else:
                dest_path = os.path.join(filtered_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.move(os.path.join(root, file), dest_path)

    # ---- Ensure only one .yml file under data/ ----
    data_yml_files = glob.glob(os.path.join(filtered_dir, "data", "**", "*.yml"), recursive=True)
    if len(data_yml_files) != 1:
        raise Exception(f"Expected exactly one .yml file under data/, found {len(data_yml_files)}: {data_yml_files}")
    data_yml_path = data_yml_files[0]

    # ---- Ensure image_map.json exists under data_source/ ----
    image_map_files = glob.glob(os.path.join(debug_dir, "data_source", "**", "image_map.json"), recursive=True)
    if len(image_map_files) != 1:
        raise Exception(f"Expected exactly one image_map.json under data_source/, found {len(image_map_files)}: {image_map_files}")
    image_map_path = image_map_files[0]

    # ---- Update the YAML file before zipping ----
    with open(data_yml_path, "r") as f:
        data = yaml.safe_load(f)
    with open(image_map_path, "r") as f:
        image_map = json.load(f)

    # Zip debug_dir (relevant files)
    debug_zip_path = os.path.join(temp_dir, "debug_artifacts.zip")
    with zipfile.ZipFile(debug_zip_path, "w") as zip_out:
        for root, _, files in os.walk(debug_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, debug_dir)
                zip_out.write(file_path, arcname)

    # Upload each file in debug_dir
    workflow_context_url = None
    image_filename_to_cloudflare_url = {}
    for root, _, files in os.walk(debug_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, debug_dir)
            with open(file_path, "rb") as f:
                upload_file = UploadFile(filename=f"open-data/{arcname}", file=f)
                base_filename = os.path.basename(arcname)
                is_log = arcname.endswith("workflow.log")
                is_image = base_filename.endswith(".png") 

                should_presign_url = is_log  # Only presign workflow.log for now

                url = await upload_file_to_storage(
                    storage_endpoint,
                    storage_access_key_id,
                    storage_secret_access_key,
                    "civicpatch-artifacts",
                    upload_file,
                    should_presign_url
                )
                if is_log:
                    log_url = url
                if is_image:
                    image_filename_to_cloudflare_url[base_filename] = url

    await process_images_and_update_data(
        data_file_path=data_yml_path,
        data=data,
        image_map=image_map,
        image_filename_to_cloudflare_url=image_filename_to_cloudflare_url 
    )

    # Zip filtered_dir (rest of the files)
    filtered_zip_path = os.path.join(temp_dir, f"filtered_artifacts_{file_suffix}")
    with zipfile.ZipFile(filtered_zip_path, "w") as zip_out:
        for root, _, files in os.walk(filtered_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, filtered_dir)
                zip_out.write(file_path, arcname)

    # Upload filtered zip (zip_to_commit)
    with open(filtered_zip_path, "rb") as f:
        filtered_upload_file = UploadFile(filename=f"filtered_artifacts_{file_suffix}", file=f)
        zip_to_commit = await upload_file_to_storage(
            storage_endpoint,
            storage_access_key_id,
            storage_secret_access_key,
            "civicpatch-artifacts", # Commit zip
            filtered_upload_file,
            with_presigned_url
        )

    shutil.rmtree(temp_dir)
    return {
        "zip_to_commit": zip_to_commit,
        "log_url": log_url
    }

async def process_images_and_update_data(
    data_file_path: str, # Local path to YAML file
    data: list,
    image_map: dict, # Map of URL to local file base name
    image_filename_to_cloudflare_url: dict # Map of local file base name to Cloudflare URL
): 
    # Update data with CDN URLs
    print(f"Processing images for data file {data_file_path}")
    for person in data:
        if person.get("image") and person["image"] in image_map:
            local_filename = image_map[person["image"]]
            print(f"Mapping original image URL {person['image']} to local filename {local_filename}")
            if local_filename in image_filename_to_cloudflare_url:
                person["cdn_image"] = image_filename_to_cloudflare_url[local_filename]

    # Save updated data back to file
    with open(data_file_path, "w") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)

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