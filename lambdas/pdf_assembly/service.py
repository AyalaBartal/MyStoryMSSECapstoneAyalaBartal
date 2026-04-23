"""Pure business logic for pdf_assembly.

Composes a PDF from story text + images using ReportLab. I/O (S3
download, S3 upload, DDB update) goes through injected callables so
tests don't need AWS or network.

No LLM / image-model adapters here — ReportLab is a local Python
library, no remote calls. But the port/adapter shape still holds:
service.py depends on callables, not on boto3.
"""

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, Paragraph


_LAYOUT_PATH = Path(__file__).parent / "layout.json"

EXPECTED_PAGE_COUNT = 5

# Matches the key format produced by image_generation:
#     stories/{story_id}/page_{N}.png
_PAGE_NUM_RE = re.compile(r"page_(\d+)\.png$")


def _load_layout(path: Path = _LAYOUT_PATH) -> dict:
    """Read layout.json. Tests can inject a custom path.

    Production reads once per cold start (handler caches).
    """
    with open(path) as f:
        return json.load(f)


def _s3_key_for_pdf(story_id: str) -> str:
    """Deterministic PDF location — matches retrieval Lambda's contract.

    Idempotent: re-running the Lambda overwrites cleanly.
    """
    return f"stories/{story_id}/final.pdf"


def _page_num_from_key(key: str) -> int:
    """Extract the page number from an image S3 key.

    Parsing the number from the key (rather than trusting list order)
    means the Lambda is robust to event reshuffling. Raises if the key
    doesn't match the expected shape.
    """
    m = _PAGE_NUM_RE.search(key)
    if not m:
        raise ValueError(f"Can't parse page number from image key: {key!r}")
    return int(m.group(1))


def _build_pdf_bytes(
    sorted_pages: List[dict],
    images_by_page_num: Dict[int, bytes],
    layout: dict,
) -> bytes:
    """Compose the PDF: one page per story page, image above text.

    Args:
        sorted_pages:       must be pre-sorted by page_num. assemble_pdf
                            handles the sort; this function is pure
                            composition and assumes the caller has
                            already ordered the pages correctly.
        images_by_page_num: map of page_num -> image bytes.
        layout:             parsed layout.json dict.

    Canvas handles image placement; Platypus (Paragraph + Frame)
    handles text flow so we don't have to measure glyph widths
    ourselves.
    """
    buffer = BytesIO()
    page_w, page_h = letter
    c = canvas.Canvas(buffer, pagesize=letter)

    margin = layout["margin_pt"]
    img_cfg = layout["image"]
    text_cfg = layout["text"]

    paragraph_style = ParagraphStyle(
        name="StoryText",
        fontName=text_cfg["font_name"],
        fontSize=text_cfg["font_size_pt"],
        leading=text_cfg["leading_pt"],
        alignment=TA_CENTER,
    )

    for page in sorted_pages:
        page_num = page["page_num"]
        image_bytes = images_by_page_num[page_num]

        # Image: top of page, horizontally centered.
        img = ImageReader(BytesIO(image_bytes))
        img_x = (page_w - img_cfg["width_pt"]) / 2
        img_y = page_h - img_cfg["top_padding_pt"] - img_cfg["height_pt"]
        c.drawImage(
            img,
            img_x,
            img_y,
            width=img_cfg["width_pt"],
            height=img_cfg["height_pt"],
            preserveAspectRatio=True,
            mask="auto",
        )

        # Text: below image, wrapped inside a Platypus Frame.
        text_top_y = img_y - text_cfg["top_padding_pt"]
        frame = Frame(
            x1=margin,
            y1=margin,
            width=page_w - 2 * margin,
            height=text_top_y - margin,
            showBoundary=0,
        )
        frame.addFromList(
            [Paragraph(page["text"], paragraph_style)], c
        )

        c.showPage()

    c.save()
    return buffer.getvalue()


def assemble_pdf(
    story_id: str,
    pages: List[dict],
    image_s3_keys: List[str],
    s3_downloader: Callable[[str], bytes],
    s3_uploader: Callable[..., None],
    ddb_updater: Callable[[str, str], None],
    layout_loader: Callable[[], dict] = _load_layout,
) -> str:
    """Fetch images, build PDF, upload, mark DDB COMPLETE.

    Args:
        story_id:       UUID for this story run.
        pages:          [{page_num, text}, ...] from story_generation.
                        Order doesn't matter — we sort before composing.
        image_s3_keys:  S3 keys (page_num derived from key, not position).
        s3_downloader:  callable (key) -> bytes.
        s3_uploader:    callable (key, body, content_type) -> None.
        ddb_updater:    callable (story_id, pdf_s3_key) -> None.
                        Sets status=COMPLETE + pdf_s3_key on the record.
        layout_loader:  callable returning layout dict (defaults to
                        the on-disk layout.json).

    Returns:
        The S3 key of the uploaded PDF.

    Raises:
        ValueError: if page count or image key count != 5.

    Ordering guarantee:
        DDB update happens LAST. If it fails, the PDF is still in S3
        but the record stays PROCESSING — Step Functions marks the
        execution FAILED, ops sees the mismatch, either a retry or a
        cleanup job resolves it. We prefer "consistent later" over
        "inconsistent now" — never mark COMPLETE until the artifact
        actually exists.
    """
    if len(pages) != EXPECTED_PAGE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PAGE_COUNT} pages, got {len(pages)}"
        )
    if len(image_s3_keys) != EXPECTED_PAGE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PAGE_COUNT} image keys, "
            f"got {len(image_s3_keys)}"
        )

    # Fetch all images. Sequential is fine for 5 items — complexity of
    # asyncio / threads isn't worth it here.
    images_by_page_num: Dict[int, bytes] = {}
    for key in image_s3_keys:
        page_num = _page_num_from_key(key)
        images_by_page_num[page_num] = s3_downloader(key)

    layout = layout_loader()

    # Sort here so _build_pdf_bytes can stay pure (pure composition,
    # assumes sorted input). Explicit sort also lets tests assert the
    # ordering behavior via a spy on _build_pdf_bytes without parsing
    # the compressed PDF stream.
    sorted_pages = sorted(pages, key=lambda p: p["page_num"])
    pdf_bytes = _build_pdf_bytes(sorted_pages, images_by_page_num, layout)

    pdf_key = _s3_key_for_pdf(story_id)
    s3_uploader(key=pdf_key, body=pdf_bytes, content_type="application/pdf")
    ddb_updater(story_id, pdf_key)

    return pdf_key