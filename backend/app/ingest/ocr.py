import json
from pathlib import Path
from rapidocr_onnxruntime import RapidOCR

_ocr_engine: RapidOCR | None = None


def get_ocr_engine() -> RapidOCR:
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


def ocr_page(image_path: Path, char_map_path: Path) -> str:
    """对扫描页进行 OCR 识别，重构文本层并均分近似字符级坐标写入 char_map"""
    engine = get_ocr_engine()
    result, _ = engine(str(image_path))

    if not result:
        return ""

    char_map_data = json.loads(char_map_path.read_text(encoding="utf-8"))
    width_pt = char_map_data["width_pt"]
    height_pt = char_map_data["height_pt"]
    width_px = char_map_data["width_px"]
    height_px = char_map_data["height_px"]

    scale_x = width_pt / width_px if width_px > 0 else 1.0
    scale_y = height_pt / height_px if height_px > 0 else 1.0

    chars = []
    lines = []

    for item in result:
        box, text, score = item[0], item[1], item[2]
        if not text:
            continue
        lines.append(text)

        # box 为 4 个顶点坐标 [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        min_x_px, max_x_px = min(xs), max(xs)
        min_y_px, max_y_px = min(ys), max(ys)

        min_x_pt = min_x_px * scale_x
        max_x_pt = max_x_px * scale_x
        min_y_pt = min_y_px * scale_y
        max_y_pt = max_y_px * scale_y

        # 将行框水平等分给每个字符
        char_count = len(text)
        if char_count > 0:
            char_width_pt = (max_x_pt - min_x_pt) / char_count
            for i, ch in enumerate(text):
                cx0 = min_x_pt + i * char_width_pt
                cx1 = cx0 + char_width_pt
                chars.append({
                    "c": ch,
                    "bbox": [round(cx0, 2), round(min_y_pt, 2), round(cx1, 2), round(max_y_pt, 2)],
                })

        chars.append({
            "c": "\n",
            "bbox": [round(min_x_pt, 2), round(max_y_pt, 2), round(max_x_pt, 2), round(max_y_pt, 2)],
        })

    char_map_data["chars"] = chars
    char_map_path.write_text(json.dumps(char_map_data, ensure_ascii=False), encoding="utf-8")

    return "\n".join(lines)
