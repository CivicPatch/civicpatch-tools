from bs4 import BeautifulSoup

def clean_html(logger, input_html: str) -> str:
    """Normalize HTML content by:
    - Pulling images out of headers
    - Moving images to be direct children of their table cells
    """
    soup = BeautifulSoup(input_html, "html.parser")

    # Remove all span tags but keep their content
    for span in soup.find_all("span"):
        span.unwrap()
    
    # Remove all div tags but keep their content
    for div in soup.find_all("div"):
        div.unwrap()

    # Pull images out of headers
    for header_tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        images = header_tag.find_all("img")
        for img in images:
            # Move image to be a sibling after the header
            header_tag.insert_after(img.extract())

    # Move images to be direct children of their table cells
    for cell in soup.find_all(["td", "th"]):
        images = cell.find_all("img")
        for img in images:
            # If image is not already a direct child of the cell, move it
            if img.parent != cell:
                cell.insert(0, img.extract())

    return soup.prettify()