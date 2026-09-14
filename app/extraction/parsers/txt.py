import logging
from typing import List, Dict

from app.extraction.parsers.base import BaseParser

logger = logging.getLogger("docenta.extraction.parser.txt")

# Simulated page dimensions (plain text has no layout).
PAGE_WIDTH_PT = 595.0
PAGE_HEIGHT_PT = 842.0
LINE_HEIGHT_PT = 15.0


class TXTParser(BaseParser):
    """Parser for plain .txt files.

    Text has no layout, so each blank-line-separated paragraph becomes one
    body block, with simulated bounding boxes assigned top to bottom so the
    downstream pipeline can treat it like any other single-column page.
    """

    def get_format(self) -> str:
        return "txt"

    def extract_pages(self) -> List[Dict]:
        logger.info(f"[TXTParser] Opening file: {self.file_path}")
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
        except Exception as e:
            logger.error(f"[TXTParser] Failed to read file: {e}")
            raise

        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]

        blocks = []
        cursor_y = 0.0
        for para in paragraphs:
            num_lines = para.count("\n") + 1
            block_height = num_lines * LINE_HEIGHT_PT
            bbox = (0.0, cursor_y, PAGE_WIDTH_PT, cursor_y + block_height)
            blocks.append(self.make_block(
                text=para,
                bbox=bbox,
                block_type="text",
                page_width=PAGE_WIDTH_PT,
                page_height=PAGE_HEIGHT_PT,
            ))
            cursor_y += block_height + LINE_HEIGHT_PT

        blocks = self.filter_empty_blocks(blocks)
        self.log_page_summary(1, blocks)

        return [{
            "page_number": 1,
            "page_width": PAGE_WIDTH_PT,
            "page_height": PAGE_HEIGHT_PT,
            "blocks": blocks,
        }]
