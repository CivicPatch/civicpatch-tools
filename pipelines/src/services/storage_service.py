import io

import boto3
from botocore.client import Config

from pipelines_environment import get_env_vars

PAUSED_CONTEXT_BUCKET = "civicpatch-artifacts"


def _get_client():
    env = get_env_vars()
    return boto3.client(
        "s3",
        endpoint_url=env["STORAGE_ENDPOINT"],
        aws_access_key_id=env["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=env["STORAGE_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def upload_paused_context(request_id: str, context_json: str) -> str:
    key = f"{request_id}/paused_context.json"
    client = _get_client()
    client.put_object(
        Bucket=PAUSED_CONTEXT_BUCKET,
        Key=key,
        Body=context_json.encode("utf-8"),
        ContentType="application/json",
    )
    return key


def download_paused_context(request_id: str) -> str:
    key = f"{request_id}/paused_context.json"
    client = _get_client()
    response = client.get_object(Bucket=PAUSED_CONTEXT_BUCKET, Key=key)
    return response["Body"].read().decode("utf-8")


def delete_paused_context(request_id: str) -> None:
    key = f"{request_id}/paused_context.json"
    client = _get_client()
    client.delete_object(Bucket=PAUSED_CONTEXT_BUCKET, Key=key)
