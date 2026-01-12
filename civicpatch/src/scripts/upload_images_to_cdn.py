import os
import posixpath
from typing import BinaryIO

import boto3
import yaml
from botocore.client import Config

from domain.models import Person
from shared.utils import data_path_utils
from shared.utils import id_utils

STORAGE_ENDPOINT = os.getenv("STORAGE_ENDPOINT")
STORAGE_ACCESS_KEY_ID = os.getenv("STORAGE_ACCESS_KEY_ID")
STORAGE_SECRET_ACCESS_KEY = os.getenv("STORAGE_SECRET_ACCESS_KEY")
FRIENDLY_STORAGE_HOST = os.getenv("FRIENDLY_STORAGE_HOST", "cdn.civicpatch.org")


def upload_images_to_cdn(jurisdiction_ocdid: str):
    jurisdiction_folder_path = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    image_path = data_path_utils.get_images_path(jurisdiction_ocdid)
    image_map_file_path = os.path.join(image_path, "image_map.json")

    people_file_path = data_path_utils.get_data_file_path(jurisdiction_ocdid)

    serialized_people = data_path_utils.get_data(
        jurisdiction_ocdid
    )

    people = [Person(**person) for person in serialized_people]

    with open(image_map_file_path) as f:
        image_map = yaml.safe_load(f)

    # Remove existing images from CDN
    dest_prefix_path = posixpath.normpath(
        posixpath.join("open-data", jurisdiction_folder_path)
    )

    delete_files_with_prefix(bucket_name="civicpatch", prefix=dest_prefix_path)

    for person in people:
        if person.image and person.image in image_map:
            filename = image_map[person.image]
            image_file_path = os.path.join(
                "data_source", jurisdiction_folder_path, "images", filename
            )
            if os.path.exists(image_file_path):
                with open(image_file_path, "rb") as img_file:
                    try:
                        dest_path = posixpath.join(dest_prefix_path, filename)
                        uploaded_url = upload_file_to_storage(
                            file_name=dest_path, bucket_name="civicpatch", file=img_file
                        )
                        print(f"Uploaded {filename} to {uploaded_url}")
                        person.cdn_image = uploaded_url
                    except Exception as e:
                        print(f"Failed to upload {filename}: {str(e)}")
            else:
                print(f"Image file {image_file_path} does not exist.")
        else:
            print(f"No image mapping found for {person.name} or image is missing.")

    # Update people with CDN URLs
    data_path_utils.update_data_for_jurisdiction(
        jurisdiction_ocdid, 
        [person.model_dump() for person in people]
    )


def upload_file_to_storage(file_name: str, bucket_name: str, file: BinaryIO) -> str:
    """
    Upload a file to S3-compatible storage.
    """
    storage_client = boto3.client(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=STORAGE_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )

    try:
        # Reset file pointer
        file.seek(0)

        # Upload file with minimal configuration
        storage_client.upload_fileobj(file, bucket_name, file_name)

        object_url = f"{FRIENDLY_STORAGE_HOST}/{file_name}"
        print(f"Successfully uploaded {file_name} to {object_url}")
        return object_url

    except Exception as e:
        print(f"Error during upload: {str(e)}")
        raise IOError(f"Upload failed: {str(e)}")


def delete_files_with_prefix(bucket_name: str, prefix: str) -> int:
    """
    Delete all objects in bucket with given prefix

    Returns:
        int: Number of objects deleted
    """
    s3 = boto3.resource(
        "s3",
        endpoint_url=STORAGE_ENDPOINT,
        aws_access_key_id=STORAGE_ACCESS_KEY_ID,
        aws_secret_access_key=STORAGE_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )

    try:
        bucket = s3.Bucket(bucket_name)
        response = bucket.objects.filter(Prefix=prefix).delete()

        if not response:
            print(f"No objects found with prefix '{prefix}' to delete.")
            return 0

        # Response is a list of deleted objects
        deleted_count = len(response[0].get("Deleted", []))
        if deleted_count > 0:
            print(f"Deleted {deleted_count} objects with prefix '{prefix}'")

        return deleted_count

    except Exception as e:
        raise IOError(f"Deletion failed: {str(e)}")


def main():
    if len(os.sys.argv) != 2:
        print("Usage: python upload_images_to_cdn.py <municipality_path>")
        os.sys.exit(1)
    elif any(
        [
            STORAGE_ACCESS_KEY_ID is None,
            STORAGE_SECRET_ACCESS_KEY is None,
            STORAGE_ENDPOINT is None,
        ]
    ):
        print(
            "STORAGE_ACCESS_KEY_ID, STORAGE_SECRET_ACCESS_KEY, and STORAGE_ENDPOINT must be set in environment variables."
        )
        os.sys.exit(1)
    elif FRIENDLY_STORAGE_HOST is None:
        print("FRIENDLY_STORAGE_HOST must be set in environment variables.")
        os.sys.exit(1)
    else:
        municipality_path = os.sys.argv[1]
        upload_images_to_cdn(municipality_path)


if __name__ == "__main__":
    main()
