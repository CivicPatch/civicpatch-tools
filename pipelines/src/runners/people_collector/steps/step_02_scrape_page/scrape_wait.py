from runners.people_collector.steps.step_02_scrape_page.scrape.wix import wait_for_wix_content
from runners.people_collector.steps.step_02_scrape_page.scrape_constants import (
    DOM_READY_TIMEOUT_MS,
    LAZY_RENDER_SETTLE_MS,
    POST_LAZY_NETWORKIDLE_TIMEOUT_MS,
    SPA_HYDRATION_TIMEOUT_MS,
    SPA_SETTLE_MS,
    SPA_NETWORKIDLE_TIMEOUT_MS,
)


async def auto_detect_and_wait(page, logger, response):
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
