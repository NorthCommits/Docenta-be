import logging
from typing import List, Dict

import pdfplumber

from app.extraction.parsers.base import BaseParser

logger = logging.getLogger("docenta.extraction.parser.pdf")

# Words whose top edges are within this many points are treated as one line.
LINE_TOLERANCE = 3.0
# Lines separated by more than this multiple of the line height start a new block.
BLOCK_GAP_MULTIPLIER = 1.6
# A horizontal gap wider than this (points) marks a column break within a row.
COLUMN_GAP_PT = 24.0


class PDFParser(BaseParser):
    """PDF parser built on pdfplumber (MIT licensed).

    Produces the same normalized block dicts as the other parsers: words are
    grouped into lines, lines into blocks, each block carrying text, bbox,
    a dominant font size, and a bold flag. Tables and images are emitted as
    their own blocks.
    """

    def get_format(self) -> str:
        return "pdf"

    def extract_pages(self) -> List[Dict]:
        logger.info(f"[PDFParser] Opening file: {self.file_path}")
        pages = []

        try:
            pdf = pdfplumber.open(self.file_path)
        except Exception as e:
            logger.error(f"[PDFParser] Failed to open file: {e}")
            raise

        with pdf:
            logger.info(f"[PDFParser] Total pages: {len(pdf.pages)}")

            for page_index, page in enumerate(pdf.pages):
                page_number = page_index + 1
                page_width = float(page.width)
                page_height = float(page.height)

                blocks = []

                # Text blocks, grouped from words.
                text_blocks = self._extract_text_blocks(page, page_width, page_height)
                blocks.extend(text_blocks)

                # Tables, rendered to markdown.
                table_blocks = self._extract_tables(page, page_width, page_height)
                if table_blocks:
                    logger.info(f"[PDFParser] Page {page_number} -- {len(table_blocks)} table(s) found")
                    blocks.extend(table_blocks)

                # Images, captured as position-only blocks.
                image_blocks = self._extract_images(page, page_width, page_height)
                blocks.extend(image_blocks)

                blocks = self.filter_empty_blocks(blocks)
                self.log_page_summary(page_number, blocks)

                pages.append({
                    "page_number": page_number,
                    "page_width": page_width,
                    "page_height": page_height,
                    "blocks": blocks,
                })

        logger.info(f"[PDFParser] Extraction complete -- {len(pages)} pages processed")
        return pages

    def _extract_text_blocks(self, page, page_width: float, page_height: float) -> List[dict]:
        """Turn words into blocks, respecting columns.

        Words are grouped into lines, each line is split at wide horizontal
        gaps (so a left-column line and a right-column line at the same height
        never merge), lines are clustered into columns, and finally each
        column's lines are grouped into paragraph blocks. Keeping blocks inside
        a single column is what lets the layout stage see the gutter and read
        the columns in the right order.
        """
        try:
            words = page.extract_words(extra_attrs=["size", "fontname"])
        except Exception as e:
            logger.warning(f"[PDFParser] Word extraction failed: {e}")
            return []

        if not words:
            return []

        # Find the column gutter (if any), then split each row at that x so the
        # two columns become separate lines and, in turn, separate blocks.
        rows = self._group_words_into_rows(words)
        split_x = self._find_column_split(rows, page_width)

        full_lines, left_lines, right_lines, single_lines = [], [], [], []
        for row in rows:
            if split_x is None:
                single_lines.append(self._build_line(row))
                continue
            # A word crossing the gutter means this is a full-width line
            # (title, heading, footnote) -- keep it whole.
            if any(w["x0"] <= split_x <= w["x1"] for w in row):
                full_lines.append(self._build_line(row))
                continue
            left = [w for w in row if (w["x0"] + w["x1"]) / 2 < split_x]
            right = [w for w in row if (w["x0"] + w["x1"]) / 2 >= split_x]
            if left:
                left_lines.append(self._build_line(left))
            if right:
                right_lines.append(self._build_line(right))

        if split_x is None:
            columns = [single_lines]
        else:
            columns = [full_lines, left_lines, right_lines]

        results = []
        for col_lines in columns:
            col_lines = sorted(col_lines, key=lambda l: l["bbox"][1])
            for block in self._group_lines_into_blocks(col_lines):
                text = block["text"].strip()
                if not text:
                    continue
                block_type = self._classify_text_block(
                    block["font_size"], block["is_bold"], text, page_height
                )
                results.append(self.make_block(
                    text=text,
                    bbox=block["bbox"],
                    block_type=block_type,
                    font_size=block["font_size"],
                    font_name=block["font_name"],
                    is_bold=block["is_bold"],
                    page_width=page_width,
                    page_height=page_height,
                ))
        return results

    def _group_words_into_rows(self, words: List[dict]) -> List[List[dict]]:
        """Cluster words into rows by shared top edge."""
        words_sorted = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
        rows = []
        current = []
        current_top = None
        for w in words_sorted:
            if current_top is None or abs(w["top"] - current_top) <= LINE_TOLERANCE:
                current.append(w)
                current_top = w["top"] if current_top is None else current_top
            else:
                rows.append(current)
                current = [w]
                current_top = w["top"]
        if current:
            rows.append(current)
        return rows

    def _find_column_split(self, rows: List[List[dict]], page_width: float) -> float | None:
        """Return the x of a central vertical gutter, or None for one column.

        For each x-slice, counts how many rows have a word covering it. A true
        column gutter is crossed only by the few full-width lines (title,
        footnotes), so it shows up as a central band of low row-coverage
        flanked by the two high-coverage columns.
        """
        if len(rows) < 6:
            return None

        res = 200
        bucket = page_width / res
        col_count = [0] * res
        for row in rows:
            hit = set()
            for w in row:
                start = int(w["x0"] / bucket)
                end = int(w["x1"] / bucket)
                for i in range(max(0, start), min(res, end + 1)):
                    hit.add(i)
            for i in hit:
                col_count[i] += 1

        peak = max(col_count) if col_count else 0
        if peak == 0:
            return None

        lo = int(res * 0.30)
        hi = int(res * 0.70)
        threshold = peak * 0.20

        best_run = 0
        best_center = None
        run = 0
        run_start = lo
        for i in range(lo, hi):
            if col_count[i] <= threshold:
                if run == 0:
                    run_start = i
                run += 1
                if run > best_run:
                    best_run = run
                    best_center = (run_start + i) / 2 * bucket
            else:
                run = 0

        # Require a real gutter band and strong columns on both sides.
        left_peak = max(col_count[:lo]) if lo > 0 else 0
        right_peak = max(col_count[hi:]) if hi < res else 0
        if (
            best_run >= max(1, int(res * 0.01))
            and best_center is not None
            and left_peak > peak * 0.4
            and right_peak > peak * 0.4
        ):
            return best_center
        return None

    def _build_line(self, words: List[dict]) -> dict:
        """Merge a run of words into one line with bbox and font info."""
        words = sorted(words, key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in words)
        x0 = min(w["x0"] for w in words)
        y0 = min(w["top"] for w in words)
        x1 = max(w["x1"] for w in words)
        y1 = max(w["bottom"] for w in words)
        sizes = [w.get("size", 0) for w in words if w.get("size")]
        font_size = max(sizes) if sizes else None
        font_name = words[0].get("fontname") if words else None
        is_bold = self._detect_bold(words)
        return {
            "text": text,
            "bbox": (x0, y0, x1, y1),
            "font_size": font_size,
            "font_name": font_name,
            "is_bold": is_bold,
        }

    def _group_lines_into_blocks(self, lines: List[dict]) -> List[dict]:
        """Merge consecutive lines into blocks.

        A new block starts when there is a large vertical gap, or when the
        font size or bold flag changes, so that a title in a larger or bold
        font is not merged into the body paragraph beneath it.
        """
        if not lines:
            return []

        blocks = []
        current = [lines[0]]

        for prev, line in zip(lines, lines[1:]):
            line_height = (prev["font_size"] or 11.0)
            gap = line["bbox"][1] - prev["bbox"][3]

            prev_size = prev["font_size"] or 0
            line_size = line["font_size"] or 0
            size_changed = (
                prev_size > 0 and line_size > 0
                and abs(line_size - prev_size) / prev_size > 0.15
            )
            bold_changed = line["is_bold"] != prev["is_bold"]

            if gap > line_height * BLOCK_GAP_MULTIPLIER or size_changed or bold_changed:
                blocks.append(self._merge_lines(current))
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(self._merge_lines(current))

        return blocks

    def _merge_lines(self, lines: List[dict]) -> dict:
        """Combine a run of lines into a single block."""
        text = "\n".join(l["text"] for l in lines)
        x0 = min(l["bbox"][0] for l in lines)
        y0 = min(l["bbox"][1] for l in lines)
        x1 = max(l["bbox"][2] for l in lines)
        y1 = max(l["bbox"][3] for l in lines)
        sizes = [l["font_size"] for l in lines if l["font_size"]]
        font_size = max(sizes) if sizes else None
        font_name = lines[0]["font_name"]
        is_bold = sum(1 for l in lines if l["is_bold"]) > len(lines) / 2
        return {
            "text": text,
            "bbox": (x0, y0, x1, y1),
            "font_size": font_size,
            "font_name": font_name,
            "is_bold": is_bold,
        }

    def _extract_tables(self, page, page_width: float, page_height: float) -> List[dict]:
        """Render detected tables to markdown blocks."""
        results = []
        try:
            found = page.find_tables()
        except Exception as e:
            logger.warning(f"[PDFParser] Table detection failed: {e}")
            return results

        for table in found:
            try:
                rows = table.extract()
            except Exception:
                continue
            markdown = self._rows_to_markdown(rows)
            if not markdown:
                continue
            bbox = table.bbox  # (x0, top, x1, bottom)
            results.append(self.make_block(
                text=markdown,
                bbox=bbox,
                block_type="table",
                page_width=page_width,
                page_height=page_height,
            ))
        return results

    def _rows_to_markdown(self, rows: List[List]) -> str:
        """Turn a list of row-lists into a markdown table string."""
        clean_rows = []
        for row in rows:
            cells = [(c or "").replace("\n", " ").strip() for c in row]
            if any(cells):
                clean_rows.append(" | ".join(cells))
        if not clean_rows:
            return ""
        header = clean_rows[0]
        separator = " | ".join(["---"] * len(clean_rows[0].split(" | ")))
        return "\n".join([header, separator] + clean_rows[1:])

    def _extract_images(self, page, page_width: float, page_height: float) -> List[dict]:
        """Capture image positions as image-type blocks."""
        results = []
        for img in getattr(page, "images", []) or []:
            try:
                bbox = (img["x0"], img["top"], img["x1"], img["bottom"])
            except KeyError:
                continue
            results.append(self.make_block(
                text="[IMAGE]",
                bbox=bbox,
                block_type="image",
                page_width=page_width,
                page_height=page_height,
            ))
        return results

    def _detect_bold(self, words: List[dict]) -> bool:
        """Detect bold from font names across a run of words."""
        if not words:
            return False
        bold = sum(1 for w in words if "bold" in (w.get("fontname", "") or "").lower())
        return bold > len(words) / 2

    def _classify_text_block(self, font_size, is_bold, text, page_height) -> str:
        """Heuristic block classification, mirroring the original PDF parser."""
        if font_size is None:
            return "text"
        relative_size = font_size / page_height if page_height > 0 else 0
        if relative_size > 0.04 and is_bold:
            return "title"
        elif relative_size > 0.025 and is_bold:
            return "heading"
        elif relative_size < 0.012:
            return "footer" if len(text) < 100 else "text"
        else:
            return "text"
