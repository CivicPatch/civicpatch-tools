import os
import hashlib
import json
from patchright.async_api import async_playwright, Page
from typing import TypedDict
import aiofiles
import asyncio
import aiohttp
import base64
from urllib.parse import urljoin
from runners.people_collector.steps.step_03_scrape_page.scrape.wix import wait_for_wix_content
from runners.people_collector.steps.step_03_scrape_page.scrape_constants import (
    PAGE_DEFAULT_TIMEOUT_MS,
    PAGE_NAVIGATION_TIMEOUT_MS,
    DOM_READY_TIMEOUT_MS,
    LAZY_RENDER_SETTLE_MS,
    POST_LAZY_NETWORKIDLE_TIMEOUT_MS,
    SPA_HYDRATION_TIMEOUT_MS,
    SPA_SETTLE_MS,
    SPA_NETWORKIDLE_TIMEOUT_MS,
    IMAGE_DOWNLOAD_TIMEOUT_S,
)

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

async def inline_iframes(page: Page, logger):
    """
    Replaces each <iframe> in the main document with the body content of its
    corresponding child frame, so downstream processing sees the iframe text.

    Uses Playwright's CDP access, which works cross-origin (e.g. Google Docs).
    Per-frame failures are logged and skipped so one bad iframe can't abort the scrape.
    """
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            frame_url = frame.url
            body_html = await frame.evaluate("document.body.innerHTML")
            await page.evaluate(
                """([url, html]) => {
                    for (const el of document.querySelectorAll('iframe')) {
                        if (el.src === url) {
                            const div = document.createElement('div');
                            div.innerHTML = html;
                            el.parentNode.replaceChild(div, el);
                            break;
                        }
                    }
                }""",
                [frame_url, body_html],
            )
            logger.debug(f"Inlined iframe: {frame_url}")
        except Exception as e:
            logger.warning(f"Could not inline iframe {frame.url}: {e}")


async def scrape(logger, website_url, options=None):
    """
    Fetches the content of a given website URL using Playwright.
    Automatically detects and waits for Wix sites.
    
    Args:
        website_url (str): The URL of the website to scrape.
        options (dict): Optional settings including:
            - scraped_urls (set): URLs already scraped
            - image_directory (str): Path to save images
            - timeout (int): Navigation timeout in ms (default: 30000)
            - headless (bool): Run in headless mode (default: True)
    
    Returns:
        str: The HTML content of the website.
    """
    options = options or {}
    timeout = options.get('timeout', PAGE_DEFAULT_TIMEOUT_MS)
    
    browser = None
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch_persistent_context(
                user_data_dir="",
                channel="chrome",
                headless=False,
                no_viewport=True
            )
            
            try:
                page = await browser.new_page()
                page.set_default_timeout(timeout)
                
                # Navigate with fallback strategy
                response = None
                for wait_until in ["networkidle", "load", "domcontentloaded"]:
                    try:
                        response = await page.goto(website_url, wait_until=wait_until, timeout=PAGE_NAVIGATION_TIMEOUT_MS)  # type: ignore[arg-type]
                        break
                    except Exception as e:
                        logger.warning(f"Warning: navigation to {website_url} with wait_until={wait_until} failed: {e}")
                
                if response is None:
                    raise Exception("Failed to load page with all wait strategies")
                
                # Check if, after redirect, we have already scraped this URL
                scraped_urls = options.get('scraped_urls')
                if scraped_urls and page.url in scraped_urls:
                    logger.info(f"Already scraped url: {website_url}, redirected to: {page.url}")
                    raise ValueError("Already scraped this URL after redirect")
                
                # Check if the page is HTML using document.contentType
                try:
                    content_type = await page.evaluate("document.contentType")
                    if content_type.lower() != "text/html":
                        raise ValueError(f"Content type is not text/html: {content_type}")
                except ValueError:
                    raise
                except:
                    pass  # Continue if we can't check content type
                
                # === AUTO-DETECT AND WAIT FOR WIX CONTENT ===
                await auto_detect_and_wait(page, logger, response)
                
                # Existing processing
                await flatten_shadow_root(page)
                await html_relative_to_absolute_urls(page)
                await inline_iframes(page, logger)

                image_directory = options.get('image_directory')
                if image_directory:
                    await convert_background_divs_to_imgs(page)
                    await download_images(browser, logger, page, image_directory)
                
                content = await page.content()
                return content, page.url

            finally:
                try:
                    await browser.close()
                except Exception:
                    pass  # Already closed

    except Exception as e:
        raise


async def auto_detect_and_wait(page, logger, response):
    """
    Auto-detect site type and apply appropriate waiting strategies.
    Currently detects: Wix, React/SPA, static sites
    """
    try:
        # Quick pre-check: URL-based detection
        url = page.url.lower()
        is_wix_url = 'wix.com' in url or 'wixsite.com' in url
        
        # Check response headers for Wix
        is_wix_header = False
        if response:
            headers = response.headers
            is_wix_header = (
                'x-wix-request-id' in headers or
                'x-wix-renderer-server' in headers or
                (headers.get('server', '').lower().find('wix') >= 0)
            )
        
        # Check DOM for Wix indicators
        site_info = await page.evaluate("""() => {
            return {
                isWix: !!(
                    document.getElementById('wix-warmup-data') ||
                    document.querySelector('meta[name="generator"][content*="Wix"]')
                ),
                isSPA: !!(
                    window.React ||
                    window.Vue ||
                    window.angular ||
                    window.__NEXT_DATA__ ||
                    window.__NUXT__
                ),
                hasWarmupData: !!document.getElementById('wix-warmup-data')
            };
        }""")
        
        is_wix = is_wix_url or is_wix_header or site_info['isWix']
        
        if is_wix:
            logger.info("🎯 Detected Wix site - applying enhanced waiting strategy")
            await wait_for_wix_content(page, logger, site_info['hasWarmupData'])
        elif site_info['isSPA']:
            logger.info("⚛️  Detected SPA/React site - applying SPA waiting strategy")
            await wait_for_spa_content(page, logger)
        else:
            logger.debug("📄 Standard site - using basic waiting strategy")
            await wait_for_basic_content(page, logger)
        
    except Exception as e:
        logger.warning(f"Error in auto-detection: {e}")
        # Don't fail the whole scrape

async def wait_for_spa_content(page, logger):
    """
    Wait for SPA/React content to hydrate and render.
    """
    try:
        logger.debug("Waiting for SPA hydration...")
        
        # Wait for framework to be ready
        await page.wait_for_function(
            """() => {
                return document.readyState === 'complete' &&
                       (!window.React || document.querySelector('[data-reactroot], #__next, #root'));
            }""",
            timeout=SPA_HYDRATION_TIMEOUT_MS
        )

        await page.wait_for_timeout(SPA_SETTLE_MS)

        try:
            await page.wait_for_load_state('networkidle', timeout=SPA_NETWORKIDLE_TIMEOUT_MS)
        except:
            pass
        
        logger.debug("✓ SPA content loaded")
        
    except Exception as e:
        logger.warning(f"Error in SPA waiting: {e}")


async def wait_for_basic_content(page, logger):
    """
    Basic waiting for standard websites.
    """
    try:
        await page.wait_for_function(
            "document.readyState === 'complete'",
            timeout=DOM_READY_TIMEOUT_MS
        )

        # Scroll to bottom to trigger intersection-observer-based lazy rendering
        # (e.g. Avada/Fusion Builder defers section HTML until viewport entry)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(LAZY_RENDER_SETTLE_MS)

        try:
            await page.wait_for_load_state('networkidle', timeout=POST_LAZY_NETWORKIDLE_TIMEOUT_MS)
        except Exception:
            pass

        logger.debug("✓ Basic content loaded")

    except Exception as e:
        logger.warning(f"Error in basic waiting: {e}")

async def convert_background_divs_to_imgs(page):
    """Convert divs with background images to img tags in the page"""
    try:
        await page.evaluate("""
            () => {
                const divs = document.querySelectorAll('div[style*="url("]');
                divs.forEach(div => {
                    const style = div.getAttribute('style');
                    const match = style.match(/url\\(['"]?([^'"()]+)['"]?\\)/);
                    if (match) {
                        const img = document.createElement('img');
                        img.src = match[1];
                        div.replaceWith(img);
                    }
                });
            }
        """)
    except Exception:
        pass  # DOM too large/complex, skip

async def flatten_shadow_root(page: Page):
    """
    Moves all shadow DOM content into the main DOM for scraping.
    """
    js_script = """
    (() => {
        function flatten(node) {
            if (node.shadowRoot) {
                node.append(...Array.from(node.shadowRoot.childNodes).map(n => n.cloneNode(true)));
                node.shadowRoot.querySelectorAll('*').forEach(flatten);
            }
        }
        document.querySelectorAll('*').forEach(flatten);
    })();
    """
    try:
        await page.evaluate(js_script)
    except Exception:
        pass  # DOM too large/complex, skip

async def html_relative_to_absolute_urls(page: Page):
    """
    Converts all relative URLs in the HTML content of the page to absolute URLs,
    considering the <base> element if it exists.

    Args:
        page (Page): The Playwright page object.
    """
    try:
        base_element = await page.query_selector("base")
        base_href = await base_element.get_attribute("href") if base_element else None
        if base_href:
            from urllib.parse import urljoin
            base_url = urljoin(page.url, base_href)
        else:
            base_url = page.url

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
    except Exception:
        pass  # DOM too large/complex, skip

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
    if src.startswith("data:"):
        return False
    return True

async def download_images(browser, logger, page: Page, image_dir: str, timeout_s: int = IMAGE_DOWNLOAD_TIMEOUT_S):
    """
    Downloads images from the current page using a fallback strategy.
    If processing any image takes longer than `timeout` seconds, skip to the next image.
    """
    await convert_background_divs_to_imgs(page)

    os.makedirs(image_dir, exist_ok=True)
    image_map = {}

    try:
        imgs = await page.query_selector_all("img")
    except Exception as e:
        logger.warning(f"Could not query images (DOM too large/complex): {e}")
        imgs = []

    for img in imgs:
        async def process_image(img):
            src = None
            try:
                src = await img.get_attribute("src")
                if not is_valid_image(src):
                    log_src = src[:80] + "..." if src and len(src) > 80 else src
                    logger.debug(f"Skipping blacklisted or invalid image: {log_src}")
                    return
                src = urljoin(page.url, src)
                image_hash = hash_string(src)
                file_name = f"{image_hash}.png"
                file_path = os.path.join(image_dir, file_name)

                # Try downloading images directly
                try:
                    logger.debug(f"Attempting to intercept and save image for: {src}")
                    intercepted_image_path = await load_and_save_image(page, image_dir, src, logger, file_name)
                    if intercepted_image_path:
                        image_map[file_name] = src
                        await img.evaluate('(el, name) => el.setAttribute("src", "local://" + name)', file_name)
                        return
                except Exception as e:
                    logger.warning(f"Failed to intercept and save image for {src}: {e}")

                # Fallback 2: Create a canvas and load the image into it
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
                    logger.debug(f"Image saved from canvas: {file_name}")
                    image_map[file_name] = src
                    await img.evaluate('(el, name) => el.setAttribute("src", "local://" + name)', file_name)
                    return
                except Exception as e:
                    logger.warning(f"Failed to create canvas for image: {src} - {e}")

                # Fallback 3: Screenshot the image element
                try:
                    logger.debug(f"Attempting to screenshot image element: {src}")
                    await img.screenshot(path=file_path)
                    logger.debug(f"Image captured via element screenshot: {file_name}")
                    image_map[file_name] = src
                    await img.evaluate('(el, name) => el.setAttribute("src", "local://" + name)', file_name)
                except Exception as e:
                    logger.warning(f"Failed to screenshot image element: {src} - {e}")

            except Exception as e:
                logger.warning(f"Failed to process image: {src} - {e}")
                await remove_image_from_dom(page, img, logger)

        try:
            await asyncio.wait_for(process_image(img), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout processing image, skipping to next.")

    # Load/create image map if it and update the image map
    map_file_path = os.path.join(image_dir, "image_map.json")
    if os.path.exists(map_file_path):
        with open(map_file_path, "r") as f:
            existing_map = json.load(f)
    else:
        existing_map = {}

    image_map.update(existing_map)
    with open(map_file_path, "w") as f:
        json.dump(image_map, f, indent=2)

async def remove_image_from_dom(page: Page, img, logger):
    try:
        await page.evaluate("""(img) => {
                if (img && img.parentNode) {
                    img.parentNode.removeChild(img);
                }
            }""", img)
    except Exception:
        pass  # DOM too large/complex, skip

async def load_and_save_image(page: Page, image_dir: str, img_url: str, logger, file_name: str):
    """
    Loads an image directly from the given URL and saves it to the specified directory.

    Args:
        page (Page): The Playwright page object.
        image_dir (str): Directory to save the image.
        img_url (str): The URL of the image to load and save.
        logger: Logger for debugging.

    Returns:
        str: The file path of the saved image, or None if the image could not be saved.
    """
    from urllib.parse import urljoin

    os.makedirs(image_dir, exist_ok=True)

    try:
        # Resolve the full URL in case it's relative
        full_url = urljoin(page.url, img_url)
        logger.debug(f"Loading image from URL: {full_url}")

        # Fetch the image data
        async with aiohttp.ClientSession() as session:
            async with session.get(full_url) as response:
                if response.status == 200:
                    file_path = os.path.join(image_dir, file_name)

                    # Save the image data to disk
                    async with aiofiles.open(file_path, "wb") as f:
                        await f.write(await response.read())

                    logger.info(f"Image saved: {file_path}")
                    return file_path
                else:
                    logger.warning(f"Failed to load image {full_url}: HTTP {response.status}")
    except Exception as e:
        logger.warning(f"Error loading image {img_url}: {e}")

    return None