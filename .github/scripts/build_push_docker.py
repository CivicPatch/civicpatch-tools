import os
import subprocess
import sys
from datetime import datetime

def run_command(command, input_data=None):
    """Run a shell command and handle errors."""
    try:
        print(f"Running: {' '.join(command)}")
        subprocess.run(command, input=input_data, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: Command {' '.join(command)} failed with exit code {e.returncode}")
        sys.exit(e.returncode)

def build_and_push_docker_image_with_compose(compose_file, service_name, tags):
    """
    Build and push a Docker image using Docker Compose.

    Args:
        compose_file (str): Path to the Docker Compose file.
        service_name (str): The name of the service in the Compose file.
        tags (list): A list of tags for the Docker image (e.g., ["latest", "2025-09-16"]).
    """
    build_command = ["docker", "compose", "-f", compose_file, "build", service_name]
    run_command(build_command)

    # Push the Docker image for each tag
    for tag in tags:
        push_command = ["docker", "compose", "-f", compose_file, "push", f"{service_name}:{tag}"]
        run_command(push_command)

def main():
    compose_file = "civicpatch/docker-compose.build.yml"  
    service_name = "civicpatch"
    tag_latest = "latest"
    tag_date = datetime.now().strftime("%Y-%m-%d")

    DOCKER_USERNAME = os.getenv("DOCKER_USERNAME")
    DOCKER_PASSWORD = os.getenv("DOCKER_PASSWORD")

    if not DOCKER_USERNAME or not DOCKER_PASSWORD:
        print("Error: DOCKER_USERNAME and DOCKER_PASSWORD environment variables must be set.")
        sys.exit(1)

    print("Logging in to GitHub Container Registry...")
    run_command(["docker", "login", "ghcr.io", "-u", DOCKER_USERNAME, "--password-stdin"], input_data=DOCKER_PASSWORD)

    build_and_push_docker_image_with_compose(compose_file, service_name, [tag_latest, tag_date])

if __name__ == "__main__":
    main()