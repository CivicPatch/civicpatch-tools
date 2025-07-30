import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from steps.step_01_scraping.utils import flatten_shadow_root, html_relative_to_absolute_urls, download_images

def test_flatten_shadow_root():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Set up a page with shadow DOM
        page.set_content("""
        <div id="host"></div>
        <script>
            const host = document.querySelector('#host');
            const shadowRoot = host.attachShadow({ mode: 'open' });
            shadowRoot.innerHTML = '<p>Inside Shadow DOM</p>';
        </script>
        """)

        # Test flatten_shadow_root
        shadow_elements = flatten_shadow_root(page)
        assert any("Inside Shadow DOM" in el for el in shadow_elements)

        browser.close()

def test_flatten_shadow_root_with_nested_shadow_dom():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Set up a page with nested shadow DOM (open and closed)
        page.set_content("""
        <div id="host1"></div>
        <script>
            const host1 = document.querySelector('#host1');
            const shadowRoot1 = host1.attachShadow({ mode: 'open' });
            shadowRoot1.innerHTML = `
                <p>Inside Open Shadow DOM 1</p>
                <div id="nested-host"></div>
            `;

            const nestedHost = shadowRoot1.querySelector('#nested-host');
            const nestedShadowRoot = nestedHost.attachShadow({ mode: 'open' });
            nestedShadowRoot.innerHTML = '<p>Inside Nested Open Shadow DOM</p>';

            const closedHost = document.createElement('div');
            closedHost.id = 'closed-host';
            document.body.appendChild(closedHost);
            const closedShadowRoot = closedHost.attachShadow({ mode: 'closed' });
            closedShadowRoot.innerHTML = '<p>Inside Closed Shadow DOM</p>';
        </script>
        """)

        # Test flatten_shadow_root
        shadow_elements = flatten_shadow_root(page)

        # Verify that elements from open shadow DOMs are included
        assert any("Inside Open Shadow DOM 1" in el for el in shadow_elements)
        assert any("Inside Nested Open Shadow DOM" in el for el in shadow_elements)

        # Verify that elements from closed shadow DOMs are not included
        assert not any("Inside Closed Shadow DOM" in el for el in shadow_elements)

        browser.close()

def test_html_relative_to_absolute_urls():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Use headless=False to see logs in the browser console
        page = browser.new_page()

        # Set up a page with relative URLs
        page.set_content("""
        <base href="https://example.com/">
        <a href="/relative-link">Link</a>
        <img src="/relative-image.jpg">
        """)

        # Test html_relative_to_absolute_urls
        html_relative_to_absolute_urls(page)

        # Verify that URLs have been converted to absolute
        link_href = page.query_selector("a").get_attribute("href")
        img_src = page.query_selector("img").get_attribute("src")

        assert link_href == "https://example.com/relative-link"
        assert img_src == "https://example.com/relative-image.jpg"

        browser.close()

def test_download_images(tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Set up a page with images
        page.set_content("""
        <img src="https://via.placeholder.com/150" alt="Placeholder">
        """)

        # Test download_images
        image_dir = tmp_path / "images"
        download_images(page, str(image_dir))

        # Verify that images are saved
        saved_images = list(image_dir.glob("*.png"))
        assert len(saved_images) == 1

        # Verify that the mapping file is created
        map_file = image_dir / "image_map.json"
        assert map_file.exists()

        with open(map_file, "r") as f:
            image_map = json.load(f)
            assert "https://via.placeholder.com/150" in image_map
            assert Path(image_dir / f"{image_map['https://via.placeholder.com/150']}").exists()

        browser.close()