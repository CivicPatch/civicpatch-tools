#!/usr/bin/env python3
import subprocess
import sys
import os
from datetime import date
import json

SERVICE = "crudder"  # The main service to build and push
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

IMAGE_PREFIX = "civicpatch"  # e.g. your Docker Hub username or your private registry
REGISTRY = "ghcr.io"

DOCKER_USERNAME = "witch"
DOCKER_PASSWORD = os.getenv("DOCKER_PASSWORD")  # Prefer using access tokens if possible
BUILD_CONTEXT = os.path.join(BASE_DIR, "..")  # The build context is outside the crudder project

# Make call to gitea api for workflow dispatch
GITEA_API_URL = 'https://code.wizards.cafe/api/v1'
GITEA_TOKEN = os.getenv('CRUDDER_REMOTELAB_WORKFLOW_TOKEN')
REPO_OWNER = 'witch'
REPO_NAME = 'remotelab'
WORKFLOW_FILE = 'deploy-crudder.yml'

def run(command, cwd=None, input=None):
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd, input=input, text=True)
    if result.returncode != 0:
        print(f"❌ Command failed: {' '.join(command)}")
        sys.exit(result.returncode)

def docker_login():
    if not DOCKER_USERNAME or not DOCKER_PASSWORD:
        print("❌ DOCKER_USERNAME or DOCKER_PASSWORD env vars not set.")
        sys.exit(1)
    print(f"🔐 Logging into {REGISTRY} as {DOCKER_USERNAME}")
    run(["docker", "login", REGISTRY, "-u", DOCKER_USERNAME, "--password-stdin"], input=DOCKER_PASSWORD)

def build_and_push():
    today_tag = date.today().isoformat()  # e.g., '2025-06-26'
    base_image = f"{REGISTRY}/{IMAGE_PREFIX}/{SERVICE}"
    latest_tag = f"{base_image}:latest"
    date_tag = f"{base_image}:{today_tag}"

    dockerfile_path = os.path.join(BASE_DIR, "Dockerfile")  # go one level up from scripts/

    print(f"🔨 Building {SERVICE} with tags: latest, {today_tag}")
    print(f"Dockerfile: {dockerfile_path}")
    run([
        "docker", "build",
        "-t", latest_tag,
        "-t", date_tag,
        "-f", dockerfile_path,  # Specify the Dockerfile explicitly
        BUILD_CONTEXT  # Pass the build context as the last argument
    ])

    print(f"🚀 Pushing tags for {SERVICE}")
    run(["docker", "push", latest_tag])
    run(["docker", "push", date_tag])

def gitea_deploy():
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'token {GITEA_TOKEN}'
    }
    data = {
        'ref': 'main',  # or the branch you want to trigger
        'inputs': {
            'triggered_by': 'test-workflow'
        }
    }
    url = f"{GITEA_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    try:
        # Serialize the data dictionary to a JSON string
        json_data = json.dumps(data)

        # Use curl to make the API request
        response = subprocess.run(
            [
                'curl', '-X', 'POST', url,
                '-H', f'Authorization: {headers["Authorization"]}',
                '-H', 'Content-Type: application/json',
                '-d', json_data,
                '-w', '\nHTTP_STATUS:%{http_code}'  # Add this to print the HTTP status code
            ],
            check=False,  # Allow the script to continue even if the command fails
            text=True,
            capture_output=True
        )

        # Print stdout and stderr for debugging
        print(f"STDOUT: {response.stdout}")
        print(f"STDERR: {response.stderr}")

        if response.returncode != 0:
            print(f"❌ Failed to trigger workflow. Exit code: {response.returncode}")
            sys.exit(1)
        else:
            print(f"Workflow triggered successfully: {response.stdout}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        sys.exit(1)

def main():
    docker_login()
    build_and_push()
    gitea_deploy()

if __name__ == "__main__":
    main()
