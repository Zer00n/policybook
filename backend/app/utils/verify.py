import json
from dataclasses import dataclass, field
from typing import Any, Literal
from app.utils.cn_date import parse_cn_date
from app.utils.cn_money import parse_cn_money
from app.utils.cn_ratio import parse_cn_ratio
from app.utils.text_norm import normalize_with_map


@dataclass
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    def to_dict(self) -> dict[str, float]:
        return {
            "x0": round(self.x0, 2),
            "y0": round(self.y0, 2),
            "x1": round(self.x1, 2),
            "y1": round(self.y1, 2),
        }


@dataclass
class VerifyResult:
    status: Literal["verified", "unverified", "not_found", "conflict"]
    page_no: int
    quote: str
    start: int | None = None
    end: int | None = None
    rects: list[dict[str, float]] = field(default_factory=list)
    page_corrected: bool = False
    conflict_reason: str | None = None


def _extract_bbox(box) -> tuple[float, float, float, float]:
    if isinstance(box, dict) and "bbox" in box:
        b = box["bbox"]
        return float(b[0]), float(b[1]), float(b[2]), float(b[3])
    elif isinstance(box, (list, tuple)):
        if len(box) >= 5:
            return float(box[1]), float(box[2]), float(box[3]), float(box[4])
        elif len(box) == 4:
            return float(box[0]), float(box[1]), float(box[2]), float(box[3])
    return 0.0, 0.0, 0.0, 0.0


def merge_char_rects(char_boxes: list) -> list[dict[str, float]]:
    """
    将相邻同一行的字符框合并为连续矩形块。
    支持 char_boxes 元素为 dict {"c": ..., "bbox": [...]} 或 list/tuple
    """
    if not char_boxes:
        return []

    lines: list[list] = []
    current_line: list = []

    for box in char_boxes:
        bx0, by0, bx1, by1 = _extract_bbox(box)
        if not current_line:
            current_line.append((bx0, by0, bx1, by1))
            continue

        prev_y0 = current_line[-1][1]
        # 若垂直方向差距在 4pt 以内，视为同一行
        if abs(by0 - prev_y0) <= 4.0:
            current_line.append((bx0, by0, bx1, by1))
        else:
            lines.append(current_line)
            current_line = [(bx0, by0, bx1, by1)]

    if current_line:
        lines.append(current_line)

    rects = []
    for line in lines:
        x0 = min(b[0] for b in line)
        y0 = min(b[1] for b in line)
        x1 = max(b[2] for b in line)
        y1 = max(b[3] for b in line)
        rects.append(Rect(x0=x0, y0=y0, x1=x1, y1=y1).to_dict())

    return rects


def check_value_consistency(
    field_name: str | None,
    model_value: str | None,
    quote: str
) -> tuple[bool, str | None]:
    """
    核对模型给出的值与 quote 原文中解析出的一致性。
    若存在矛盾（例如 quote 明确为 20 万元，但模型填了 50 万元），返回 (False, reason)。
    """
    if not model_value or not field_name:
        return True, None

    fname = field_name.lower()

    # 1. 金额类字段
    if any(k in fname for k in ("premium", "sum_insured", "limit", "deductible", "amount")):
        val_money = parse_cn_money(model_value)
        quote_money = parse_cn_money(quote)
        if val_money and quote_money:
            if val_money.cents != quote_money.cents:
                return False, f"金额不一致：模型值 {model_value} ({val_money.cents/100:.2f}元) 与引用原文 {quote} ({quote_money.cents/100:.2f}元) 冲突"

    # 2. 日期类字段
    if any(k in fname for k in ("date", "apply_date", "effective_date", "expiry_date")):
        val_date = parse_cn_date(model_value)
        quote_date = parse_cn_date(quote)
        if val_date and quote_date:
            if val_date != quote_date:
                return False, f"日期不一致：模型值 {val_date} 与引用原文 {quote_date} 冲突"

    # 3. 比例类字段
    if "ratio" in fname:
        val_ratio = parse_cn_ratio(model_value)
        quote_ratio = parse_cn_ratio(quote)
        if val_ratio is not None and quote_ratio is not None:
            if val_ratio != quote_ratio:
                return False, f"比例不一致：模型值 {val_ratio/10:.1f}% 与引用原文 {quote_ratio/10:.1f}% 冲突"

    return True, None


def verify_quote(
    pages_text: dict[int, str],
    target_page: int,
    quote: str | None,
    field_name: str | None = None,
    model_value: str | None = None,
    char_maps: dict[int, list] | None = None,
) -> VerifyResult:
    """
    根据 DEV-GUIDE 8.2 执行引用子串校验与坐标回算。
    1. 在 target_page 上精确匹配归一化子串；
    2. 找不到时跨页回退搜索，命中则修正页码并标记 page_corrected=True；
    3. 仍找不到标记为 not_found；
    4. 回算 start/end 字符下标及对应 PDF 坐标框 rects；
    5. 执行数值一致性复查，若冲突标记为 conflict。
    """
    if not quote or len(quote.strip()) < 4:
        return VerifyResult(
            status="not_found",
            page_no=target_page,
            quote=quote or "",
            conflict_reason="引用内容过短或缺失，无法核验",
        )

    norm_quote, _ = normalize_with_map(quote)
    if len(norm_quote) < 4:
        return VerifyResult(
            status="not_found",
            page_no=target_page,
            quote=quote,
            conflict_reason="归一化后有效字符不足 4 个，不接受核验",
        )

    matched_page = target_page
    page_corrected = False
    hit_pos = -1
    matched_idx_map: list[int] = []
    matched_page_text = ""

    # 先在目标页找
    if target_page in pages_text:
        ptxt = pages_text[target_page]
        norm_page, idx_map = normalize_with_map(ptxt)
        hit_pos = norm_page.find(norm_quote)
        if hit_pos != -1:
            matched_idx_map = idx_map
            matched_page_text = ptxt

    # 目标页找不到，跨所有页搜索
    if hit_pos == -1:
        for pno, ptxt in sorted(pages_text.items()):
            if pno == target_page:
                continue
            norm_page, idx_map = normalize_with_map(ptxt)
            pos = norm_page.find(norm_quote)
            if pos != -1:
                hit_pos = pos
                matched_page = pno
                matched_idx_map = idx_map
                matched_page_text = ptxt
                page_corrected = True
                break

    if hit_pos == -1:
        return VerifyResult(
            status="not_found",
            page_no=target_page,
            quote=quote,
            conflict_reason="在文档各页面中均未匹配到该原文引用",
        )

    # 计算原文字符下标范围
    start = matched_idx_map[hit_pos]
    end = matched_idx_map[hit_pos + len(norm_quote) - 1] + 1

    # 计算坐标矩形
    rects: list[dict[str, float]] = []
    if char_maps and matched_page in char_maps:
        page_boxes = char_maps[matched_page]
        if isinstance(page_boxes, dict):
            page_boxes = page_boxes.get("chars", [])
        # 截取 start..end 范围内的字符坐标
        if page_boxes and len(page_boxes) > start:
            matched_boxes = page_boxes[start:min(end, len(page_boxes))]
            rects = merge_char_rects(matched_boxes)

    # 检查数值一致性
    consistent, reason = check_value_consistency(field_name, model_value, quote)
    if not consistent:
        return VerifyResult(
            status="conflict",
            page_no=matched_page,
            quote=quote,
            start=start,
            end=end,
            rects=rects,
            page_corrected=page_corrected,
            conflict_reason=reason,
        )

    return VerifyResult(
        status="verified",
        page_no=matched_page,
        quote=quote,
        start=start,
        end=end,
        rects=rects,
        page_corrected=page_corrected,
    )
