#!/usr/bin/env python3
import subprocess
import sys
import os
from datetime import date

SSH_USER=os.environ['SSH_USER']
SSH_FILE_PATH=os.environ['SSH_FILE_PATH']
SSH_KEY_PATH=os.path.expanduser(SSH_FILE_PATH)
DROPLET_IP=os.environ['DROPLET_IP']
MOUNTED_VOLUME=f"/home/{SSH_USER}"

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

SERVICES = ["caddy", "web1", "web2"]
IMAGE_PREFIX = "witch"  # e.g. your Docker Hub username or your private registry
REGISTRY = "code.wizards.cafe"   # or custom registry like ghcr.io, etc.

DOCKER_USERNAME = os.getenv("DOCKER_USERNAME")
DOCKER_PASSWORD = os.getenv("DOCKER_PASSWORD")  # Prefer using access tokens if possible

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

def build_and_push(service):
    today_tag = date.today().isoformat()  # e.g., '2025-06-26'
    base_image = f"{REGISTRY}/{IMAGE_PREFIX}/{service}"
    latest_tag = f"{base_image}:latest"
    date_tag = f"{base_image}:{today_tag}"

    dockerfile_path = os.path.join(BASE_DIR, "services", service)  # go one level up from scripts/

    print(f"🔨 Building {service} with tags: latest, {today_tag}")
    print(f"Dockerfile: {dockerfile_path}")
    run(["docker", "build", "-t", latest_tag, "-t", date_tag, dockerfile_path])

    print(f"🚀 Pushing tags for {service}")
    run(["docker", "push", latest_tag])
    run(["docker", "push", date_tag])

def push_to_ssh_server(local_dir, remote_user, remote_host, remote_path, ssh_key_path):
    command = [
        "rsync", "-avz",
        "-e", f"ssh -i {ssh_key_path}",
        local_dir,
        f"{remote_user}@{remote_host}:{remote_path}"
    ]
    try:
        print(f"📡 Syncing {local_dir} → {remote_user}@{remote_host}:{remote_path}")
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to sync files: {e}")
        sys.exit(1)

def docker_cleanup():
    print("🧹 Cleaning up unused Docker images, containers, and volumes...")
    run(["docker", "system", "prune", "-af", "--volumes"])

def main():
    docker_login()
    docker_cleanup()
    for service in SERVICES:
        build_and_push(service)

    local_dir = os.path.join(BASE_DIR, "server")
    push_to_ssh_server(local_dir, SSH_USER, DROPLET_IP, MOUNTED_VOLUME, SSH_KEY_PATH)

if __name__ == "__main__":
    main()
