"""Pure business logic for pdf_assembly.

Composes a square picture-book PDF: cover page + 5 full-bleed story
pages with text overlaid in a cream band at the bottom. Text size
adapts to the reader's age.
"""

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Callable, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Frame, KeepInFrame, Paragraph


_LAYOUT_PATH = Path(__file__).parent / "layout.json"
EXPECTED_PAGE_COUNT = 5
_PAGE_NUM_RE = re.compile(r"page_(\d+)\.png$")


def _load_layout(path: Path = _LAYOUT_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def _s3_key_for_pdf(story_id: str) -> str:
    return f"stories/{story_id}/final.pdf"


def _page_num_from_key(key: str) -> int:
    m = _PAGE_NUM_RE.search(key)
    if not m:
        raise ValueError(f"Can't parse page number from image key: {key!r}")
    return int(m.group(1))


def _bucket_for_age(age: str, layout: dict) -> dict:
    age_str = str(age)
    for bucket in layout["age_buckets"].values():
        if age_str in bucket["ages"]:
            return bucket
    return layout["age_buckets"]["middle"]


def _hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16) / 255,
        int(hex_color[2:4], 16) / 255,
        int(hex_color[4:6], 16) / 255,
    )


def _humanize(value: str) -> str:
    return value.replace("_", " ")


def _draw_cover_page(c: canvas.Canvas, layout: dict, name: str, theme: str,
                     page_size: int, cover_image_bytes: bytes = b"") -> None:
    """Draw cover page: theme card as background (if available),
    big title, italic subtitle."""
    cover = layout["cover"]

    if cover_image_bytes:
        # Theme illustration as cover background
        img = ImageReader(BytesIO(cover_image_bytes))
        c.drawImage(
            img, 0, 0, width=page_size, height=page_size,
            preserveAspectRatio=False, mask="auto",
        )
        # Soft white wash so the title stays readable on top
        c.saveState()
        c.setFillColorRGB(
            1, 1, 1,
            alpha=cover.get("image_wash_opacity", 0.45),
        )
        c.rect(0, 0, page_size, page_size, fill=1, stroke=0)
        c.restoreState()
    else:
        # Plain cream background fallback
        bg_rgb = _hex_to_rgb(cover["background_color"])
        c.setFillColorRGB(*bg_rgb)
        c.rect(0, 0, page_size, page_size, fill=1, stroke=0)

    # Title — vertically centered, slightly above center
    title = f"{name}'s Story"
    title_rgb = _hex_to_rgb(cover["title_color"])
    c.setFillColorRGB(*title_rgb)
    c.setFont(cover["title_font_name"], cover["title_font_size_pt"])
    c.drawCentredString(page_size / 2, page_size / 2 + 20, title)

    # Subtitle
    subtitle = f"A {_humanize(theme)} adventure"
    sub_rgb = _hex_to_rgb(cover["subtitle_color"])
    c.setFillColorRGB(*sub_rgb)
    c.setFont(cover["subtitle_font_name"], cover["subtitle_font_size_pt"])
    c.drawCentredString(page_size / 2, page_size / 2 - 30, subtitle)

    # Decorative flourish
    c.setFont(cover["subtitle_font_name"], 28)
    c.drawCentredString(page_size / 2, page_size / 2 - 90, "✦ ✦ ✦")

    c.showPage()


def _build_pdf_bytes(
    sorted_pages: List[dict],
    images_by_page_num: Dict[int, bytes],
    layout: dict,
    age: str,
    name: str = "",
    theme: str = "",
    cover_image_bytes: bytes = b"",
) -> bytes:
    """Compose the full picture-book PDF: cover + 5 illustrated pages."""
    page_size = layout["page_size_pt"]
    page_w = page_h = page_size

    bucket = _bucket_for_age(age, layout)
    text_cfg = layout["text_band"]

    bg_rgb = _hex_to_rgb(text_cfg["background_color"])
    text_color = HexColor(text_cfg["text_color"])

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(page_w, page_h))

    # Cover page (only when name + theme provided — keeps tests clean)
    if name and theme:
        _draw_cover_page(c, layout, name, theme, page_size, cover_image_bytes)

    paragraph_style = ParagraphStyle(
        name="StoryText",
        fontName=text_cfg["font_name"],
        fontSize=bucket["font_size_pt"],
        leading=bucket["leading_pt"],
        alignment=TA_CENTER,
        textColor=text_color,
    )

    for page in sorted_pages:
        page_num = page["page_num"]
        image_bytes = images_by_page_num[page_num]

        # 1. Full-bleed illustration
        img = ImageReader(BytesIO(image_bytes))
        c.drawImage(
            img, 0, 0,
            width=page_w, height=page_h,
            preserveAspectRatio=False, mask="auto",
        )

        # 2. Cream band at bottom
        band_h = bucket["band_height_pt"]
        c.saveState()
        c.setFillColorRGB(*bg_rgb, alpha=text_cfg["background_opacity"])
        c.rect(0, 0, page_w, band_h, fill=1, stroke=0)
        c.restoreState()

        # 3. Text inside the band
        h_pad = text_cfg["horizontal_padding_pt"]
        v_pad = text_cfg["vertical_padding_pt"]
        text_frame = Frame(
            x1=h_pad,
            y1=v_pad,
            width=page_w - 2 * h_pad,
            height=band_h - 2 * v_pad,
            showBoundary=0,
        )
        # KeepInFrame with mode="shrink" auto-shrinks text to fit the
        # available band space instead of silently dropping the whole
        # Paragraph when it overflows. Belt-and-suspenders for cases
        # where the LLM generates longer prose than the band can hold.
        text_content = KeepInFrame(
            maxWidth=page_w - 2 * h_pad,
            maxHeight=band_h - 2 * v_pad,
            content=[Paragraph(page["text"], paragraph_style)],
            mode="shrink",
        )
        text_frame.addFromList([text_content], c)

        c.showPage()

    c.save()
    return buffer.getvalue()


def assemble_pdf(
    story_id: str,
    pages: List[dict],
    image_s3_keys: List[str],
    age: str,
    s3_downloader: Callable[[str], bytes],
    s3_uploader: Callable[..., None],
    ddb_updater: Callable[[str, str], None],
    name: str = "",
    theme: str = "",
    cover_image_bytes: bytes = b"",
    layout_loader: Callable[[], dict] = _load_layout,
) -> str:
    if len(pages) != EXPECTED_PAGE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PAGE_COUNT} pages, got {len(pages)}"
        )
    if len(image_s3_keys) != EXPECTED_PAGE_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_PAGE_COUNT} image keys, "
            f"got {len(image_s3_keys)}"
        )

    images_by_page_num: Dict[int, bytes] = {}
    for key in image_s3_keys:
        page_num = _page_num_from_key(key)
        images_by_page_num[page_num] = s3_downloader(key)

    layout = layout_loader()
    sorted_pages = sorted(pages, key=lambda p: p["page_num"])
    pdf_bytes = _build_pdf_bytes(
        sorted_pages, images_by_page_num, layout, age,
        name=name, theme=theme,
        cover_image_bytes=cover_image_bytes,
    )

    pdf_key = _s3_key_for_pdf(story_id)
    s3_uploader(key=pdf_key, body=pdf_bytes, content_type="application/pdf")
    ddb_updater(story_id, pdf_key)

    return pdf_key