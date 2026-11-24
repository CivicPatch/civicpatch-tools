# OCR for scanned charters

Pipeline 1 reads a PDF's own text layer (`pypdfium2`, `pipelines/src/runners/pipeline01_governing_law_collector/converters/pdf.py`)
and has no OCR, so a scanned charter reads as empty and is skipped. Two known cases: Gold Beach, Oregon
(`CityCharter2014.pdf`, 16 pages, a clean photocopy with a "COPY" stamp) and Washburn, Maine (`washburn-charter.pdf`,
5 pages, an older, noisier scan). Both have a text layer of 0 characters on every page.

## Candidates

What published comparisons say (secondary sources, mostly blogs; none tested charters):

- **Tesseract** is the strongest CPU-only engine on clean printed pages in an independent 22-engine comparison, and
  best on multi-column layouts (71% of multi-column tests against 6% for PaddleOCR and RapidOCR)
  ([withinnoise.dev](https://withinnoise.dev/blog/posts/ocr-benchmark/)). On 14 scanned book pages it had a lower
  character error rate than RapidOCR (0.177 against 0.458) at 3.7 s a page against 29.5 s, the gap mostly RapidOCR
  reading across both pages of a spread
  ([ibrahimsalman.vercel.app](https://ibrahimsalman.vercel.app/blog/rapidocr-vs-tesseract-document-intelligence-benchmark)).
  Apache-2.0. Needs the `tesseract-ocr` system package.
- **RapidOCR** runs PaddleOCR's models through ONNX Runtime on CPU, pip only: `pip install rapidocr onnxruntime`
  (`rapidocr-onnxruntime` is the older package). Apache-2.0 code; models derived from PaddleOCR's
  ([RapidOCR README](https://github.com/RapidAI/RapidOCR)).
- **OCRmyPDF** adds a Tesseract text layer to the PDF itself, which would let the existing converter read it
  unchanged. MPL-2.0, but it requires Ghostscript, which is AGPLv3
  ([PyPI](https://pypi.org/project/ocrmypdf/)). Not tested: it is Tesseract underneath.
- **PaddleOCR proper, docTR, EasyOCR, Surya, docling**: PyTorch or PaddlePaddle, hundreds of MB; PaddleOCR
  effectively needs a GPU ([withinnoise.dev](https://withinnoise.dev/blog/posts/ocr-benchmark/)); Surya is GPL-3.0.
  Not tested.

## Measured on the two charters (2026-11-23)

Pages rendered at 300 dpi with `pypdfium2`, as pipeline 1 would. Tesseract 5.3.0 from Debian bookworm in a throwaway
container; RapidOCR from PyPI (PP-OCRv6 small models) in a throwaway venv, 372 MB installed with its dependencies.
Outputs: `~/plans/civicpatch-tools/research/organizations-from-the-law/ocr/`.

| | Gold Beach, 16 pages | Washburn, 5 pages |
|---|---|---|
| Tesseract, default layout (`--psm 3`) | 43 s; clean text, a few stray marks from margin specks | 14 s; most of each page lost |
| Tesseract, one text block (`--psm 6`) | 45 s; the "COPY" stamp is read into the lines beside it | 23 s; clean text |
| RapidOCR | 128 s; clean, but one line dropped ("(2) The council may remove any appointed of-") | 41 s; clean text, a few garbled lines |

Phrases that decide pipeline 2's answer, found in each output (hyphenated line ends joined):

- Gold Beach, 8 present in the charter: Tesseract `--psm 3` 8, RapidOCR 7, Tesseract `--psm 6` 6.
- Washburn, 8 present: Tesseract `--psm 6` 8, RapidOCR 8, Tesseract `--psm 3` 7.

## What it shows

No one setting wins both: Tesseract's default reads the clean scan best and loses the poor one; its single-block
mode and RapidOCR read the poor scan and stumble on the clean one's stamp or a line. Every engine read the
governing-body clauses of both charters (Gold Beach's council, councilors and mayor; Washburn's councillors and
chairman) well enough to quote, which is what pipeline 2 needs. Two charters are thin evidence; the choice should be
re-checked as more scanned charters turn up.
