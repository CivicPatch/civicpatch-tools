async def wait_for_wix_content(page, logger, warmup_already_present=False):
    """
    Wait for Wix-specific content to load, including warmup data.
    """
    try:
        # Step 1: Wait for warmup data script to appear (if not already there)
        if not warmup_already_present:
            logger.debug("Waiting for wix-warmup-data...")
            warmup_loaded = False
            
            for attempt in range(20):  # Try for up to 20 seconds
                has_warmup = await page.evaluate("""() => {
                    const script = document.getElementById('wix-warmup-data');
                    return script && script.textContent && script.textContent.length > 100;
                }""")
                
                if has_warmup:
                    logger.info(f"✓ Wix warmup data loaded after {attempt + 1} seconds")
                    warmup_loaded = True
                    break
                
                await page.wait_for_timeout(1000)
            
            if not warmup_loaded:
                logger.warning("⚠ Wix warmup data did not appear within 20 seconds")
        else:
            logger.debug("Wix warmup data already present")
        
        # Step 2: Wait for Wix containers
        logger.debug("Waiting for Wix containers...")
        try:
            await page.wait_for_selector(
                '#SITE_CONTAINER, [data-mesh-id], main',
                timeout=5000,
                state='attached'
            )
            logger.debug("✓ Wix containers found")
        except:
            logger.debug("Wix containers not found (continuing anyway)")
        
        # Step 3: Wait for Wix runtime to initialize
        try:
            await page.wait_for_function(
                """() => {
                    return window.rendered === true ||
                           window.wixBiSession !== undefined ||
                           document.readyState === 'complete';
                }""",
                timeout=5000
            )
            logger.debug("✓ Wix runtime initialized")
        except:
            logger.debug("Wix runtime check timeout (continuing anyway)")
        
        # Step 4: Additional wait for dynamic content
        await page.wait_for_timeout(2000)
        
        # Step 5: Scroll to trigger lazy loading
        logger.debug("Scrolling to trigger lazy content...")
        await scroll_page_smart(page)
        
        # Step 6: Wait for network to settle after scroll
        try:
            await page.wait_for_load_state('networkidle', timeout=10000)
            logger.debug("✓ Network settled")
        except:
            logger.debug("Network still active (continuing anyway)")
        
        # Step 7: Final wait
        await page.wait_for_timeout(1000)
        
        # Step 8: Final verification
        final_check = await page.evaluate("""() => {
            const script = document.getElementById('wix-warmup-data');
            return {
                exists: !!script,
                hasContent: script ? script.textContent.length > 100 : false,
                hasGalleryData: script ? script.textContent.includes('galleryData') : false,
                contentLength: script ? script.textContent.length : 0
            };
        }""")
        
        if final_check['exists'] and final_check['hasContent']:
            logger.info(f"✓ Wix content verified: {final_check['contentLength']} chars, gallery: {final_check['hasGalleryData']}")
        else:
            logger.warning(f"⚠ Wix content verification failed: {final_check}")
        
    except Exception as e:
        logger.warning(f"Error in Wix waiting: {e}")

async def scroll_page_smart(page):
    """
    Smart scrolling that triggers lazy-loaded content.
    """
    try:
        await page.evaluate("""
            async () => {
                const distance = 300;
                const delay = 200;
                const totalHeight = Math.max(
                    document.body.scrollHeight,
                    document.documentElement.scrollHeight
                );
                
                // Scroll down in steps
                for (let y = 0; y < totalHeight; y += distance) {
                    window.scrollTo(0, y);
                    await new Promise(resolve => setTimeout(resolve, delay));
                }
                
                // Scroll back to top
                window.scrollTo(0, 0);
                await new Promise(resolve => setTimeout(resolve, 300));
            }
        """)
    except Exception as e:
        # Scrolling errors are non-critical
        pass