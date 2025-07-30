from playwright.sync_api import sync_playwright
from . import utils

def get_website_content(website_url, options=None):
    """
    Fetches the content of a given website URL using Playwright.

    Args:
        website_url (str): The URL of the website to scrape.

    Returns:
        str: The HTML content of the website.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto(website_url)

        utils.flatten_shadow_root(page) 
        utils.html_relative_to_absolute_urls(page)

        if options and options.get('image_dir', False):
            # Download images if the option is set
            utils.download_images(page, options.get('image_dir'))

        content = page.content()
        browser.close()

        return content
