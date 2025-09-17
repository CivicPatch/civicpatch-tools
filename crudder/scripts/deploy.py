#!/usr/bin/env python3
import subprocess
import sys
import os
import json

SERVICE = "crudder"  # The main service to push

# Make call to gitea api for workflow dispatch
GITEA_API_URL = 'https://code.wizards.cafe/api/v1'
GITEA_TOKEN = os.getenv('REMOTELAB_WORKFLOW_TOKEN')
REPO_OWNER = 'witch'
REPO_NAME = 'remotelab'
WORKFLOW_FILE = f'deploy-{SERVICE}.yml'

def run(command, cwd=None, input=None):
    print(f"$ {' '.join(command)}")
    result = subprocess.run(command, cwd=cwd, input=input, text=True)
    if result.returncode != 0:
        print(f"❌ Command failed: {' '.join(command)}")
        sys.exit(result.returncode)

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
    gitea_deploy()

if __name__ == "__main__":
    main()
