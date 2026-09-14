"""Extraction orchestrator.

Runs the deterministic pipeline (parse, detect layout, order by reading order)
and returns an ExtractedDocument. There is no LLM in this path: the semantic
work happens later in the script-generation stage. Supported formats are PDF,
PPTX, DOCX, HTML, and plain text.
"""

import logging
import os
import re
from typing import Dict

# Matches a "real" word: three or more letters in a row.
_WORD_RE = re.compile(r"[A-Za-z]{3,}")


def _looks_like_noise(text: str) -> bool:
    """Heuristic: is this block a scattered fragment rather than real content?

    Blocks with at least one real word are always kept. Blocks with no real
    word are dropped when they are short or mostly symbols -- the kind of
    debris that comes from rotated tables, plotted charts, and stray axis
    labels, e.g. "j j j", "- . . .", "0 . 2", "K".
    """
    t = text.strip()
    if not t:
        return True
    if _WORD_RE.search(t):
        return False
    compact = t.replace(" ", "").replace("\n", "")
    if len(compact) <= 8:
        return True
    letters = sum(c.isalpha() for c in compact)
    return letters / len(compact) < 0.3

from app.extraction.detector import detect_all_pages
from app.extraction.extractor import extract_all_pages
from app.extraction.parsers.base import BaseParser
from app.extraction.parsers.docx import DOCXParser
from app.extraction.parsers.html import HTMLParser
from app.extraction.parsers.pdf import PDFParser
from app.extraction.parsers.pptx import PPTXParser
from app.extraction.parsers.txt import TXTParser
from app.schemas.pipeline import ExtractedDocument, ExtractedPage, ExtractionRegion

logger = logging.getLogger("docenta.extraction.orchestrator")

_PARSERS: Dict[str, type[BaseParser]] = {
    "pdf": PDFParser,
    "pptx": PPTXParser,
    "docx": DOCXParser,
    "html": HTMLParser,
    "txt": TXTParser,
}

SUPPORTED_FORMATS = tuple(_PARSERS.keys())


def _detect_format(file_path: str) -> str:
    ext = os.path.splitext(file_path)[-1].lower().lstrip(".")
    if ext == "htm":
        ext = "html"
    if ext not in _PARSERS:
        raise ValueError(
            f"Unsupported file format: .{ext}. Supported: {', '.join(SUPPORTED_FORMATS)}"
        )
    return ext


def run_extraction(file_path: str, filename: str) -> ExtractedDocument:
    """Parse, detect layout, order, and return a structured ExtractedDocument."""
    file_format = _detect_format(file_path)
    logger.info(f"[Extraction] Starting -- file={filename} format={file_format}")

    parser = _PARSERS[file_format](file_path)
    raw_pages = parser.extract_pages()
    detected_pages = detect_all_pages(raw_pages)
    extracted_pages = extract_all_pages(detected_pages)

    pages = []
    for page in extracted_pages:
        regions = []
        kept_texts = []
        seq = 0
        for block in page.get("ordered_blocks", []):
            block_type = block.get("block_type", "unknown")
            text = block.get("text", "")
            # Keep tables and images as-is; drop fragmentary noise from the rest.
            if block_type not in ("table", "image") and _looks_like_noise(text):
                continue
            seq += 1
            regions.append(ExtractionRegion(type=block_type, text=text, sequence=seq))
            kept_texts.append(text)

        pages.append(ExtractedPage(
            page_number=page["page_number"],
            layout_type=page.get("layout_type", "unknown"),
            regions=regions,
            full_text="\n\n".join(t for t in kept_texts if t.strip()),
        ))

    full_text = "\n\n".join(p.full_text for p in pages if p.full_text)

    logger.info(
        f"[Extraction] Complete -- file={filename} pages={len(pages)} "
        f"chars={len(full_text)}"
    )

    return ExtractedDocument(
        source_filename=filename,
        format=file_format,
        page_count=len(pages),
        pages=pages,
        text=full_text,
    )
