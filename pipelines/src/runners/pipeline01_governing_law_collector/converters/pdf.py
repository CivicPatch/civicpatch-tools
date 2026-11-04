"""A PDF's own text, page by page. A scan carries none and comes out nearly empty, which the
collector skips as it skips any empty page: no OCR here."""

import pypdfium2

PAGE_BREAK = "\n\n"


class UnreadablePdf(Exception):
    pass


def to_markdown(body: bytes) -> str:
    try:
        document = pypdfium2.PdfDocument(body)
        return PAGE_BREAK.join(page.get_textpage().get_text_range() for page in document)
    except pypdfium2.PdfiumError as error:
        raise UnreadablePdf(str(error)) from error
