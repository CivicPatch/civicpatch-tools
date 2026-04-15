"""
One-off migration script: rename artifact files in R2 from the old workflow.*
naming convention to the new pipeline_run.* naming convention.

Old → New:
  .../workflow.log            → .../pipeline_run.log
  .../workflow_context.json   → .../pipeline_run_context.json

Usage:
  uv run python scripts/migrate_artifact_filenames.py [--dry-run]

Required env vars:
  R2_ACCOUNT_ID
  R2_ACCESS_KEY_ID
  R2_SECRET_ACCESS_KEY
  R2_BUCKET_NAME  (default: civicpatch-artifacts)
"""
import argparse
import os
import sys

import boto3
from botocore.config import Config

RENAMES = {
    "/workflow.log": "/pipeline_run.log",
    "/workflow_context.json": "/pipeline_run_context.json",
}


def get_client():
    account_id = os.environ["R2_ACCOUNT_ID"]
    access_key = os.environ["R2_ACCESS_KEY_ID"]
    secret_key = os.environ["R2_SECRET_ACCESS_KEY"]
    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def new_key(old_key: str) -> str | None:
    for suffix, replacement in RENAMES.items():
        if old_key.endswith(suffix):
            return old_key[: -len(suffix)] + replacement
    return None


def migrate(dry_run: bool) -> None:
    bucket = os.environ.get("R2_BUCKET_NAME", "civicpatch-artifacts")
    client = get_client()

    paginator = client.get_paginator("list_objects_v2")
    renamed = 0
    skipped = 0

    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            old = obj["Key"]
            target = new_key(old)
            if target is None:
                continue

            print(f"{'[DRY RUN] ' if dry_run else ''}Renaming: {old!r} → {target!r}")
            if not dry_run:
                client.copy_object(
                    Bucket=bucket,
                    CopySource={"Bucket": bucket, "Key": old},
                    Key=target,
                )
                client.delete_object(Bucket=bucket, Key=old)
            renamed += 1

    print(f"\nDone. Renamed: {renamed}, Skipped (no match): {skipped}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate artifact filenames in R2")
    parser.add_argument("--dry-run", action="store_true", help="List changes without applying them")
    args = parser.parse_args()

    for var in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not os.environ.get(var):
            print(f"Error: missing required env var {var}", file=sys.stderr)
            sys.exit(1)

    migrate(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
