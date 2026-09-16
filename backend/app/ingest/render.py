from dataclasses import dataclass
import json
from pathlib import Path
import unicodedata
import fitz  # PyMuPDF
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()


@dataclass
class RenderedPage:
    page_no: int
    image_path: Path
    char_map_path: Path
    is_ocr: bool
    raw_text: str
    width_pt: float
    height_pt: float
    width_px: int
    height_px: int


def is_scanned_page(text: str, min_chars: int = 40) -> bool:
    """如果有效字符数（去除空白与标点）低于阈值，判定为扫描页"""
    valid_chars = 0
    for ch in text:
        cat = unicodedata.category(ch)
        # 排除空白(Z*)与标点(P*)与控制符(C*)
        if not (cat.startswith("Z") or cat.startswith("P") or cat.startswith("C")):
            valid_chars += 1
    return valid_chars < min_chars


def render_file_to_pages(file_path: Path, out_dir: Path) -> list[RenderedPage]:
    """将 PDF 或图片文件渲染为 144 DPI PNG，并提取字符级坐标 JSON"""
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = file_path.suffix.lower()

    temp_pdf = None
    if suffix in [".jpg", ".jpeg", ".png", ".heic", ".bmp", ".webp"]:
        # 图片转为单页 PDF 处理
        temp_pdf = out_dir / "_temp_image.pdf"
        img = Image.open(file_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(temp_pdf, "PDF", resolution=144.0)
        doc = fitz.open(temp_pdf)
    else:
        doc = fitz.open(file_path)

    rendered_pages: list[RenderedPage] = []

    try:
        for page_idx in range(len(doc)):
            page_no = page_idx + 1
            page = doc[page_idx]

            # 144 DPI 渲染
            pix = page.get_pixmap(dpi=144)
            img_path = out_dir / f"p{page_no:03d}.png"
            pix.save(img_path)

            width_pt = page.rect.width
            height_pt = page.rect.height
            width_px = pix.width
            height_px = pix.height

            # 提取字符级坐标
            rawdict = page.get_text("rawdict")
            chars: list[dict] = []
            full_text_parts = []

            for block in rawdict.get("blocks", []):
                if "lines" not in block:
                    continue
                for line in block.get("lines", []):
                    line_chars = []
                    for span in line.get("spans", []):
                        for ch in span.get("chars", []):
                            c = ch["c"]
                            bbox = ch["bbox"]  # [x0, y0, x1, y1] in pt
                            chars.append({
                                "c": c,
                                "bbox": [round(v, 2) for v in bbox],
                            })
                            line_chars.append(c)
                    chars.append({
                        "c": "\n",
                        "bbox": [round(v, 2) for v in line.get("bbox", [0, 0, 0, 0])],
                    })
                    full_text_parts.append("".join(line_chars))

            raw_text = "\n".join(full_text_parts)
            is_ocr = is_scanned_page(raw_text)

            char_map_data = {
                "page_no": page_no,
                "width_pt": width_pt,
                "height_pt": height_pt,
                "width_px": width_px,
                "height_px": height_px,
                "chars": chars,
            }
            char_map_path = out_dir / f"p{page_no:03d}_chars.json"
            char_map_path.write_text(json.dumps(char_map_data, ensure_ascii=False), encoding="utf-8")

            rendered_pages.append(RenderedPage(
                page_no=page_no,
                image_path=img_path,
                char_map_path=char_map_path,
                is_ocr=is_ocr,
                raw_text=raw_text,
                width_pt=width_pt,
                height_pt=height_pt,
                width_px=width_px,
                height_px=height_px,
            ))
    finally:
        doc.close()
        if temp_pdf and temp_pdf.exists():
            temp_pdf.unlink(missing_ok=True)

    return rendered_pages
