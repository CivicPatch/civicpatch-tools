import boto3
from botocore.client import Config
import sys
import os

def main():
    if len(sys.argv) != 2:
        print("Usage: python one-off-generate-file-url.py <key>")
        sys.exit(1)

    key = sys.argv[1]
    bucket = "crudder"

    endpoint_url = os.environ.get("STORAGE_ENDPOINT")
    aws_access_key_id = os.environ.get("STORAGE_ACCESS_KEY_ID")
    aws_secret_access_key = os.environ.get("STORAGE_SECRET_ACCESS_KEY")

    if not all([endpoint_url, aws_access_key_id, aws_secret_access_key]):
        print("Please set STORAGE_ENDPOINT, STORAGE_ACCESS_KEY_ID, and STORAGE_SECRET_ACCESS_KEY environment variables.")
        sys.exit(1)

    session = boto3.session.Session()
    s3 = session.client(
        service_name="s3",
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        endpoint_url=endpoint_url,
        config=Config(signature_version="s3v4"),
    )

    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=86400  # 1 day in seconds
    )

    print(url)

if __name__ == "__main__":
    main()