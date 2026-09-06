import asyncio
import base64
import hashlib
import json
import os
from urllib.parse import urljoin

import aiofiles
import httpx
from patchright.async_api import Page

from runners.people_collector.steps.step_02_scrape_page.scrape_constants import IMAGE_DOWNLOAD_TIMEOUT_S


IMAGE_URL_BLACKLIST = ["https://google.com"]
IMAGE_EXT_BLACKLIST = [".svg", ".gif"]


class ImageError(Exception):
    pass


def hash_string(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()[:12]


def hash_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:12]


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


async def convert_background_divs_to_imgs(page: Page):
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
        pass


async def remove_image_from_dom(page: Page, img, logger):
    try:
        await page.evaluate("""(img) => {
                if (img && img.parentNode) {
                    img.parentNode.removeChild(img);
                }
            }""", img)
    except Exception:
        pass


async def load_and_save_image(page: Page, image_dir: str, img_url: str, logger, file_name: str):
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


async def _register_image(img, image_dir: str, temp_path: str, image_map: dict, src: str) -> None:
    """Name the file after its bytes. Hashing the source url instead let a jurisdiction that
    swaps the photo at a stable url overwrite the old one on the permanent CDN key."""
    file_name = f"{hash_file(temp_path)}.png"
    os.replace(temp_path, os.path.join(image_dir, file_name))
    image_map[file_name] = src
    await img.evaluate('(el, name) => el.setAttribute("src", "local://" + name)', file_name)


async def _download_single_image(page: Page, img, image_dir: str, image_map: dict, logger):
    src = None
    temp_path = None
    try:
        src = await img.get_attribute("src")
        if not is_valid_image(src):
            log_src = src[:80] + "..." if src and len(src) > 80 else src
            logger.debug(f"Skipping blacklisted or invalid image: {log_src}")
            return
        src = urljoin(page.url, src)
        temp_name = f"{hash_string(src)}.tmp"
        temp_path = os.path.join(image_dir, temp_name)

        try:
            logger.debug(f"Attempting to intercept and save image for: {src}")
            intercepted_image_path = await load_and_save_image(page, image_dir, src, logger, temp_name)
            if intercepted_image_path:
                await _register_image(img, image_dir, temp_path, image_map, src)
                return
        except Exception as e:
            logger.warning(f"Failed to intercept and save image for {src}: {e}")

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
            with open(temp_path, "wb") as f:
                f.write(base64.b64decode(encoded))
            logger.debug(f"Image saved from canvas: {src}")
            await _register_image(img, image_dir, temp_path, image_map, src)
            return
        except Exception as e:
            logger.warning(f"Failed to create canvas for image: {src} - {e}")

        try:
            logger.debug(f"Attempting to screenshot image element: {src}")
            await img.screenshot(path=temp_path)
            logger.debug(f"Image captured via element screenshot: {src}")
            await _register_image(img, image_dir, temp_path, image_map, src)
        except Exception as e:
            logger.warning(f"Failed to screenshot image element: {src} - {e}")

    except Exception as e:
        logger.warning(f"Failed to process image: {src} - {e}")
        await remove_image_from_dom(page, img, logger)
    finally:
        # A capture that failed part-way through writing must not leave a .tmp for the zip.
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


async def download_images(browser, logger, page: Page, image_dir: str, timeout_s: int = IMAGE_DOWNLOAD_TIMEOUT_S):
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
