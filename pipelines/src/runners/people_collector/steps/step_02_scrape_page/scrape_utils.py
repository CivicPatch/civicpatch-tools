import os
import hashlib
import json
from patchright.async_api import async_playwright, Page
from typing import TypedDict
import aiofiles
import asyncio
import httpx
import base64
from urllib.parse import urljoin
from runners.people_collector.steps.step_02_scrape_page.scrape.wix import wait_for_wix_content
from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import NavigationError, NavigationFailureReason
from runners.people_collector.steps.step_02_scrape_page.scrape_constants import (
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
    scraped_urls: list[str]  # List of URLs that have already been scraped
    accordion_keywords: list[str]  # Only expand accordion sections whose text matches one of these keywords

class ImageError(Exception):
    pass

def hash_string(s: str) -> str:
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

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch_persistent_context(
            user_data_dir="",
            channel="chrome",
            headless=False,
            no_viewport=True,
        )

        try:
            page = await browser.new_page()
            page.set_default_timeout(timeout)

            # Navigate with fallback strategy
            response = None
            last_errors: list[str] = []
            for wait_until in ["networkidle", "load", "domcontentloaded"]:
                try:
                    response = await page.goto(website_url, wait_until=wait_until, timeout=PAGE_NAVIGATION_TIMEOUT_MS)  # type: ignore[arg-type]
                    break
                except Exception as e:
                    last_errors.append(str(e))
                    logger.warning(f"Warning: navigation to {website_url} with wait_until={wait_until} failed: {e}")

            if response is None:
                last_error = last_errors[-1] if last_errors else ""
                if "net::ERR_NAME_NOT_RESOLVED" in last_error:
                    reason = NavigationFailureReason.DNS_FAILURE
                elif "net::ERR_CONNECTION_REFUSED" in last_error:
                    reason = NavigationFailureReason.CONNECTION_REFUSED
                elif "Timeout" in last_error and "net::" not in last_error:
                    reason = NavigationFailureReason.NAVIGATION_TIMEOUT
                else:
                    reason = NavigationFailureReason.UNKNOWN
                raise NavigationError(website_url, reason, source=last_error)

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
            except Exception:
                pass  # Continue if we can't check content type

            accordion_keywords = options.get('accordion_keywords')
            await auto_detect_and_wait(page, logger, response, accordion_keywords=accordion_keywords)

            await flatten_shadow_root(page)
            await html_relative_to_absolute_urls(page)
            await inline_iframes(page, logger)

            image_directory = options.get('image_directory')
            if image_directory:
                await download_images(browser, logger, page, image_directory)

            content = await page.content()
            return content, page.url

        finally:
            try:
                await browser.close()
            except Exception:
                pass  # Already closed


async def auto_detect_and_wait(page, logger, response, accordion_keywords=None):
    """
    Auto-detect site type and apply appropriate waiting strategies.
    Currently detects: Wix, React/SPA, static sites
    """
    try:
        url = page.url.lower()
        is_wix_url = 'wix.com' in url or 'wixsite.com' in url

        is_wix_header = False
        if response:
            headers = response.headers
            is_wix_header = (
                'x-wix-request-id' in headers or
                'x-wix-renderer-server' in headers or
                (headers.get('server', '').lower().find('wix') >= 0)
            )

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
            logger.info("Detected Wix site - applying enhanced waiting strategy")
            await wait_for_wix_content(page, logger, site_info['hasWarmupData'])
        elif site_info['isSPA']:
            logger.info("Detected SPA/React site - applying SPA waiting strategy")
            await wait_for_spa_content(page, logger)
        else:
            logger.debug("Standard site - using basic waiting strategy")
            await wait_for_basic_content(page, logger)

        await expand_accordions(page, logger, accordion_keywords)

    except Exception as e:
        logger.warning(f"Error in auto-detection: {e}")


async def wait_for_spa_content(page, logger):
    try:
        logger.debug("Waiting for SPA hydration...")

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
        except Exception:
            pass

        logger.debug("SPA content loaded")

    except Exception as e:
        logger.warning(f"Error in SPA waiting: {e}")


async def wait_for_basic_content(page, logger):
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

        logger.debug("Basic content loaded")

    except Exception as e:
        logger.warning(f"Error in basic waiting: {e}")

async def expand_accordions(page: Page, logger, keywords: list[str] | None = None):
    try:
        collapsed = await page.query_selector_all('[aria-expanded="false"]')
        expanded = 0
        for el in collapsed:
            try:
                if keywords:
                    text = (await el.inner_text()).lower()
                    if not any(kw.lower() in text for kw in keywords):
                        continue
                await el.click()
                await page.wait_for_timeout(300)
                expanded += 1
            except Exception:
                pass
        if expanded:
            logger.debug(f"Expanded {expanded} accordion sections")
    except Exception as e:
        logger.warning(f"Error expanding accordions: {e}")


async def convert_background_divs_to_imgs(page):
    """Inject an <img> for each div's CSS background-image, preserving the div and its children."""
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
                        div.insertBefore(img, div.firstChild);
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
    try:
        base_element = await page.query_selector("base")
        base_href = await base_element.get_attribute("href") if base_element else None
        base_url = urljoin(page.url, base_href) if base_href else page.url

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
    if not src:
        return False
    if any(src.endswith(ext) for ext in IMAGE_EXT_BLACKLIST):
        return False
    if any(blacklisted in src for blacklisted in IMAGE_URL_BLACKLIST):
        return False
    if src.startswith("data:"):
        return False
    return True


async def _download_single_image(page: Page, img, image_dir: str, image_map: dict, logger):
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

        # Strategy 1: direct HTTP download
        try:
            logger.debug(f"Attempting to intercept and save image for: {src}")
            intercepted_image_path = await load_and_save_image(page, image_dir, src, logger, file_name)
            if intercepted_image_path:
                image_map[file_name] = src
                await img.evaluate('(el, name) => el.setAttribute("src", "local://" + name)', file_name)
                return
        except Exception as e:
            logger.warning(f"Failed to intercept and save image for {src}: {e}")

        # Strategy 2: canvas capture
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

        # Strategy 3: element screenshot
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
        try:
            await asyncio.wait_for(_download_single_image(page, img, image_dir, image_map, logger), timeout=timeout_s)
        except asyncio.TimeoutError:
            logger.warning("Timeout processing image, skipping to next.")

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
    os.makedirs(image_dir, exist_ok=True)

    try:
        full_url = urljoin(page.url, img_url)
        logger.debug(f"Loading image from URL: {full_url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(full_url)
            if response.status_code == 200:
                file_path = os.path.join(image_dir, file_name)
                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(response.content)
                logger.info(f"Image saved: {file_path}")
                return file_path
            else:
                logger.warning(f"Failed to load image {full_url}: HTTP {response.status_code}")
    except Exception as e:
        logger.warning(f"Error loading image {img_url}: {e}")

    return None