"""eCode360's print page holds a whole law. Its header is dropped: it carries today's date, which
would change the text's hash every day."""

from urllib.parse import urlparse

from bs4 import BeautifulSoup
from . import html

HOST = "ecode360.com"
PRINT_PATH = "/print/"
CONTENT_ID = "content"
HEADER_CLASS = "printHeader"


def is_print_page(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.") == HOST and parsed.path.startswith(PRINT_PATH)


def to_markdown(body: bytes) -> str:
    soup = BeautifulSoup(body, "html.parser")
    for header in soup.find_all(class_=HEADER_CLASS):
        header.decompose()
    content = soup.find(id=CONTENT_ID)
    return html.to_markdown(f"<html><body>{content}</body></html>".encode() if content else body)
