"""A scanned PDF's text, read off its pages: what `pdf` cannot give when the file carries photos of its pages.
RapidOCR, chosen by measurement (`.docs/2026-11-23-research-ocr-for-scanned-charters.md`)."""

import re
from functools import lru_cache
from typing import List, Sequence, Tuple

import numpy
import pypdfium2
from rapidocr import RapidOCR
from rapidocr.utils.output import RapidOCROutput

PAGE_BREAK = "\n\n"
# Pages are drawn at 4 times 72 dpi, near the 300 dpi the measurement used: the renderer takes a whole number.
RENDER_SCALE = 4
# Text boxes whose tops lie within this many pixels are one line, read left to right.
LINE_HEIGHT_PX = 25

Box = Sequence[Sequence[float]]
# A word a scanned page broke at its line end: "com-" then "mences". Quotes write it whole.
_SPLIT_WORD = re.compile(r"(\w)-\n(\w)")


@lru_cache(maxsize=1)
def _engine() -> RapidOCR:
    # Built once and only when a scan turns up: loading its models takes seconds.
    return RapidOCR()


def to_markdown(body: bytes) -> str:
    document = pypdfium2.PdfDocument(body)
    return PAGE_BREAK.join(rejoined_words(_page_text(page)) for page in document)


def rejoined_words(text: str) -> str:
    return _SPLIT_WORD.sub(r"\1\2", text)


def _page_text(page: pypdfium2.PdfPage) -> str:
    image = numpy.asarray(page.render(scale=RENDER_SCALE).to_pil().convert("RGB"))
    result = _engine()(image)
    if not isinstance(result, RapidOCROutput) or result.txts is None or result.boxes is None:
        return ""
    return reading_order(list(zip(result.boxes, result.txts)))


def reading_order(boxes: List[Tuple[Box, str]]) -> str:
    """Top to bottom, then left to right, by each box's top-left corner."""
    ordered = sorted(boxes, key=lambda item: (round(item[0][0][1] / LINE_HEIGHT_PX), item[0][0][0]))
    return "\n".join(text for _, text in ordered)
