
import os
import uuid
import json
from playwright.sync_api import sync_playwright, Page
from typing import TypedDict

class ScrapeOptions(TypedDict):
    image_dir: str  # Directory to save images

def scrape(website_url, options=None):
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

        flatten_shadow_root(page) 
        html_relative_to_absolute_urls(page)

        if options and options.get('image_dir'):
            # Download images if the option is set
            download_images(page, options.get('image_dir'))

        content = page.content()
        browser.close()

        return content

def flatten_shadow_root(page: Page):
    """
    Flattens the shadow root of the current page using Playwright.

    Args:
        page (Page): The Playwright page object.

    Returns:
        list: A list of all elements inside shadow roots on the page.
    """
    # JavaScript to traverse shadow DOM and return all elements
    js_script = """
    const flattenShadowRoot = (node) => {
        const elements = [];
        const traverse = (root) => {
            if (root.shadowRoot) {
                elements.push(...root.shadowRoot.querySelectorAll('*'));
                root.shadowRoot.querySelectorAll('*').forEach(traverse);
            }
        };
        document.querySelectorAll('*').forEach(traverse);
        return elements.map(el => el.outerHTML);
    };
    flattenShadowRoot(document);
    """
    # Execute the JavaScript on the page
    shadow_elements = page.evaluate(js_script)
    
    return shadow_elements

def html_relative_to_absolute_urls(page: Page):
    """
    Converts all relative URLs in the HTML content of the page to absolute URLs,
    considering the <base> element if it exists.

    Args:
        page (Page): The Playwright page object.
    """
    base_element = page.query_selector("base")
    base_href = base_element.get_attribute("href") if base_element else None
    if base_href:
        # If base_href is relative, resolve it against the page's URL
        from urllib.parse import urljoin
        base_url = urljoin(page.url, base_href)
    else:
        base_url = page.url

    # Pass the base_url directly as an argument to the function
    page.evaluate("""
        (baseUrl) => {
            console.log("Converting html_relative_to_absolute_urls with baseUrl:", baseUrl);
            const elements = document.querySelectorAll('a[href], img[src]');
            elements.forEach((el) => {
                if (el.tagName === 'A' && el.getAttribute('href').startsWith('/')) {
                    el.setAttribute('href', new URL(el.getAttribute('href'), baseUrl).href);
                } else if (el.tagName === 'IMG' && el.getAttribute('src').startsWith('/')) {
                    el.setAttribute('src', new URL(el.getAttribute('src'), baseUrl).href);
                }
            });
        }
    """, base_url)

def download_images(page: Page, image_dir: str):
    """
    Captures screenshots of images from the current page using Playwright,
    renames them to UUIDs, and saves a mapping of original URLs to UUIDs in a JSON file.

    Args:
        page (Page): The Playwright page object.
        image_dir (str): Directory to save the captured images.
    """
    os.makedirs(image_dir, exist_ok=True)

    image_elements = page.query_selector_all("img")
    image_map = {}

    for img in image_elements:
        try:
            src = img.get_attribute("src")
            if not src:
                continue

            image_uuid = str(uuid.uuid4())
            file_name = f"{image_uuid}.png"
            file_path = os.path.join(image_dir, file_name)

            img.screenshot(path=file_path)

            image_map[src] = file_name
        except Exception as e:
            print(f"Failed to capture image {src}: {e}")

    map_file_path = os.path.join(image_dir, "image_map.json")
    with open(map_file_path, "w") as json_file:
        json.dump(image_map, json_file, indent=4)
