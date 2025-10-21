import os
import hashlib
import json
from unittest import result
from playwright.async_api import async_playwright, Page
from typing import TypedDict

IMAGE_URL_BLACKLIST = ["https://google.com"]
IMAGE_EXT_BLACKLIST = [".svg", ".gif"]

class ScrapeOptions(TypedDict):
    image_dir: str  # Directory to save images
    scraped_urls: list[str] # List of URLs that have already been scraped

class ImageError(Exception):
    pass

def hash_string(s: str) -> str:
    """Returns a SHA256 hash of the input string."""
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:12]

async def scrape(logger, website_url, options=None):
    """
    Fetches the content of a given website URL using Playwright.

    Args:
        website_url (str): The URL of the website to scrape.

    Returns:
        str: The HTML content of the website.
    """
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False
        )
        # CHROMIUM ARGS
        # 2025-09-29T00:58:37.330Z pw:browser <launching> /opt/google/chrome/chrome --disable-field-trial-config --disable-background-networking --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-back-forward-cache --disable-breakpad --disable-client-side-phishing-detection --disable-component-extensions-with-background-pages --disable-component-update --no-default-browser-check --disable-default-apps --disable-dev-shm-usage --disable-extensions --disable-features=AcceptCHFrame,AvoidUnnecessaryBeforeUnloadCheckSync,DestroyProfileOnBrowserClose,DialMediaRouteProvider,GlobalMediaControls,HttpsUpgrades,LensOverlay,MediaRouter,PaintHolding,ThirdPartyStoragePartitioning,Translate,AutoDeElevate --allow-pre-commit-input --disable-hang-monitor --disable-ipc-flooding-protection --disable-popup-blocking --disable-prompt-on-repost --disable-renderer-backgrounding --force-color-profile=srgb --metrics-recording-only --no-first-run --password-store=basic --use-mock-keychain --no-service-autorun --export-tagged-pdf --disable-search-engine-choice-screen --unsafely-disable-devtools-self-xss-warnings --edge-skip-compat-layer-relaunch --enable-automation --no-sandbox --no-sandbox --disable-crashpad-for-testing --user-data-dir=/tmp/playwright_chromiumdev_profile-9RRDRG --remote-debugging-pipe --no-startup-window 

        context = await browser.new_context() 
        page = await context.new_page()

        for wait_until in ["load", "domcontentloaded"]:
            try:
                await page.goto(website_url, wait_until=wait_until)
                break
            except Exception as e:
                logger.warning(f"Warning: navigation to {website_url} with wait_until={wait_until} failed: {e}")

        # Check if, after redirect, we have already scraped this URL
        if options and options.get('scraped_urls') and page.url in options.get('scraped_urls'):
            logger.info(f"Already scraped url: {website_url}, redirected to: {page.url}")
            await browser.close()
            raise ValueError("Already scraped this URL after redirect")

        # Check if the page is HTML using document.contentType
        content_type = await page.evaluate("document.contentType")
        if content_type.lower() != "text/html":
            await browser.close()
            raise ValueError(f"Content type is not text/html: {content_type}")
    
        await flatten_shadow_root(page)
        await html_relative_to_absolute_urls(page)

        if options and options.get('image_directory'):
            # Download images if the option is set
            await download_images(logger, page, options.get('image_directory'))

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
    base_href = await base_element.get_attribute("href") if base_element else None
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

def is_valid_image(src: str | None) -> bool:
    """
    Checks if the image source is valid based on blacklists and other criteria.

    Args:
        src (str): The image source URL.

    Returns:
        bool: True if the image is valid, False otherwise.
    """
    if not src:
        return False
    if any(src.endswith(ext) for ext in IMAGE_EXT_BLACKLIST):
        return False
    if any(blacklisted in src for blacklisted in IMAGE_URL_BLACKLIST):
        return False
    return True

async def download_images(logger, page: Page, image_dir: str):
    """
    Downloads images from the current page using a fallback strategy:
    1. Direct download by URL.
    2. Visit the link in the browser and screenshot it.
    3. Create a canvas and load the image into it.
    4. Screenshot the image element as a last resort.
    """
    import aiohttp
    import base64
    from urllib.parse import urljoin

    os.makedirs(image_dir, exist_ok=True)
    image_map = {}

    for img in await page.query_selector_all("img"):
        src = None
        try:
            src = await img.get_attribute("src")
            if not is_valid_image(src):
                logger.debug(f"Skipping blacklisted or invalid image: {src}")
                continue
            src = urljoin(page.url, src)
            image_hash = hash_string(src)
            file_path = os.path.join(image_dir, f"{image_hash}.png")

            # Fallback 1: Direct download by URL
            try:
                logger.debug(f"Attempting direct download for image: {src}")
                async with aiohttp.ClientSession() as session:
                    async with session.get(src) as response:
                        if response.status == 200:
                            with open(file_path, "wb") as f:
                                f.write(await response.read())
                            logger.debug(f"Image downloaded directly: {file_path}")
                            image_map[src] = file_path
                            continue
                        else:
                            logger.warning(f"Failed direct download for {src}: HTTP {response.status}")
            except Exception as e:
                logger.warning(f"Direct download failed for {src}: {e}")

            # Fallback 2: Visit the link in the browser and screenshot it
            try:
                logger.debug(f"Attempting to visit and screenshot image: {src}")
                new_page = await page.context.new_page()
                await new_page.goto(src, wait_until="load")
                await new_page.screenshot(path=file_path)
                await new_page.close()
                logger.info(f"Image captured via browser screenshot: {file_path}")
                image_map[src] = file_path
                continue
            except Exception as e:
                logger.warning(f"Failed to visit and screenshot image: {src} - {e}")

            # Fallback 3: Create a canvas and load the image into it
            try:
                logger.debug(f"Attempting to create a canvas and load image: {src}")
                canvas_script = """
                (src) => {
                    return new Promise((resolve, reject) => {
                        const img = new Image();
                        img.crossOrigin = "anonymous";
                        img.onload = () => {
                            const canvas = document.createElement("canvas");
                            canvas.width = img.width;
                            canvas.height = img.height;
                            const ctx = canvas.getContext("2d");
                            ctx.drawImage(img, 0, 0);
                            resolve(canvas.toDataURL("image/png"));
                        };
                        img.onerror = reject;
                        img.src = src;
                    });
                }
                """
                data_url = await page.evaluate(canvas_script, src)
                header, encoded = data_url.split(",", 1)
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(encoded))
                logger.debug(f"Image saved from canvas: {file_path}")
                image_map[src] = file_path
                continue
            except Exception as e:
                logger.warning(f"Failed to create canvas for image: {src} - {e}")

            # Fallback 4: Screenshot the image element
            try:
                logger.debug(f"Attempting to screenshot image element: {src}")
                await img.screenshot(path=file_path)
                logger.debug(f"Image captured via element screenshot: {file_path}")
                image_map[src] = file_path
            except Exception as e:
                logger.warning(f"Failed to screenshot image element: {src} - {e}")

        except Exception as e:
            logger.warning(f"Failed to process image: {src} - {e}")

    # Save the image map
    map_file_path = os.path.join(image_dir, "image_map.json")
    with open(map_file_path, "w") as f:
        json.dump(image_map, f, indent=4)

