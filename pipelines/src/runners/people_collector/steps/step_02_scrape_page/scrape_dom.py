from urllib.parse import urljoin
from patchright.async_api import Page
from typing import List


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


async def expand_accordions(page: Page, logger, keywords: List[str] | None = None):
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


async def flatten_shadow_root(page: Page):
    """Moves all shadow DOM content into the main DOM for scraping."""
    try:
        await page.evaluate("""
        (() => {
            function flatten(node) {
                if (node.shadowRoot) {
                    node.append(...Array.from(node.shadowRoot.childNodes).map(n => n.cloneNode(true)));
                    node.shadowRoot.querySelectorAll('*').forEach(flatten);
                }
            }
            document.querySelectorAll('*').forEach(flatten);
        })();
        """)
    except Exception:
        pass


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
        pass
