import os
import uuid
import json
from playwright.async_api import async_playwright, Page
from typing import TypedDict

IMAGE_URL_BLACKLIST = ["https://google.com"]
IMAGE_EXT_BLACKLIST = [".svg", ".gif"]

class ScrapeOptions(TypedDict):
    image_dir: str  # Directory to save images

class ImageError(Exception):
    pass

async def scrape(website_url, options=None):
    """
    Fetches the content of a given website URL using Playwright.

    Args:
        website_url (str): The URL of the website to scrape.

    Returns:
        str: The HTML content of the website.
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(website_url)

        await flatten_shadow_root(page) 
        await html_relative_to_absolute_urls(page)

        if options and options.get('image_directory'):
            # Download images if the option is set
            await download_images(page, options.get('image_directory'))

        content = await page.content()
        await browser.close()

        return content

async def flatten_shadow_root(page: Page):
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
    shadow_elements = await page.evaluate(js_script)
    
    return shadow_elements

async def html_relative_to_absolute_urls(page: Page):
    """
    Converts all relative URLs in the HTML content of the page to absolute URLs,
    considering the <base> element if it exists.

    Args:
        page (Page): The Playwright page object.
    """
    base_element = await page.query_selector("base")
    base_href = base_element.get_attribute("href") if base_element else None
    if base_href:
        from urllib.parse import urljoin
        base_url = urljoin(page.url, base_href)
    else:
        base_url = page.url

    # Improved: convert all non-absolute URLs, not just those starting with /
    await page.evaluate("""
        (baseUrl) => {
            function isAbsolute(url) {
                return /^(?:[a-z]+:)?\\/\\//i.test(url);
            }
            const elements = document.querySelectorAll('a[href], img[src]');
            elements.forEach((el) => {
                if (el.tagName === 'A') {
                    const href = el.getAttribute('href');
                    if (href && !isAbsolute(href)) {
                        el.setAttribute('href', new URL(href, baseUrl).href);
                    }
                } else if (el.tagName === 'IMG') {
                    const src = el.getAttribute('src');
                    if (src && !isAbsolute(src)) {
                        el.setAttribute('src', new URL(src, baseUrl).href);
                    }
                }
            });
        }
    """, base_url)

async def download_images(page: Page, image_dir: str):
    """
    Captures screenshots of images from the current page using Playwright,
    renames them to UUIDs, and saves a mapping of original URLs to UUIDs in a JSON file.

    Args:
        page (Page): The Playwright page object.
        image_dir (str): Directory to save the captured images.
    """
    os.makedirs(image_dir, exist_ok=True)

    image_elements = await page.query_selector_all("img")
    image_map = {}

    for img in image_elements:
        try:
            if not await img.is_visible():
                raise ImageError("Image is not visible")
            src = await img.get_attribute("src")
            if not src:
                raise ImageError("No src in image")
            
            if any(src.endswith(ext) for ext in IMAGE_EXT_BLACKLIST):
                # TODO: raise error
                raise ImageError("Image is under blacklisted")

            image_uuid = str(uuid.uuid4())
            file_name = f"{image_uuid}.png"
            file_path = os.path.join(image_dir, file_name)

            await img.screenshot(path=file_path)

            image_map[src] = file_name
        except Exception as e:
            print(f"Failed to capture image {src}: {e}")
            # Remove image from page
            await page.evaluate("""(img) => {
                img.parentNode.removeChild(img);
            }""", img)

    map_file_path = os.path.join(image_dir, "image_map.json")

    # Append to existing map if it exists, otherwise create new
    if os.path.exists(map_file_path):
        with open(map_file_path, "r") as f:
            existing_map = json.load(f)
        existing_map.update(image_map)
        image_map = existing_map

    with open(map_file_path, "w") as f:
        json.dump(image_map, f, indent=4)

