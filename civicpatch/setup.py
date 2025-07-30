import subprocess

def post_install():
    """
    Runs Playwright browser installation after Poetry install.
    """
    try:
        subprocess.run(["poetry", "run", "playwright", "install", "chromium"], check=True)
    except Exception as e:
        print(f"Error during Playwright installation: {e}")

if __name__ == "__main__":
    post_install()