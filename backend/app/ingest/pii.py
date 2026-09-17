import json
from pathlib import Path
import re
from typing import NamedTuple
from PIL import Image, ImageDraw

ID_RE = re.compile(
    r"(?<![0-9A-Za-z])[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9A-Za-z])"
)
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d(?:\s*|-)?\d{4}(?:\s*|-)?\d{4}(?!\d)")
CARD_RE = re.compile(r"(?<!\d)(?:\d{4}[\s-]?){3,4}\d{1,4}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
POLICY_NO_RE = re.compile(r"(?:保单号(?:码)?|保险单号|合同编号|投保单号)(?:为|是)?[:：\s]*([0-9A-Za-z-]{6,30})")
ADDRESS_RE = re.compile(r"(?:家庭住址|联系地址|通讯地址|详细地址|住址)(?:为|是)?[:：\s]*([^\n\r,，。;；]{6,50})")


CARD_CONTEXT_WORDS = ("账号", "卡号", "银行", "账户")


def verify_id_checksum(id_str: str) -> bool:
    """GB 11643-1999 中华人民共和国公民身份号码校验位计算"""
    clean_id = id_str.strip()
    if len(clean_id) != 18:
        return False
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = "10X98765432"
    try:
        s = sum(int(clean_id[i]) * weights[i] for i in range(17))
        return check_codes[s % 11].upper() == clean_id[17].upper()
    except (ValueError, IndexError):
        return False


def verify_luhn(card_str: str) -> bool:
    """Luhn 模 10 算法校验银行卡号"""
    digits = [int(ch) for ch in card_str if ch.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


class MatchSpan(NamedTuple):
    start: int
    end: int
    kind: str
    original_value: str


class DeidentifyResult(NamedTuple):
    masked_text: str
    mappings: list[dict[str, str]]  # [{kind, placeholder, value}]
    spans: list[MatchSpan]
    pii_status: str  # success / failed


class PiiDeidentifier:
    def __init__(self, registered_members: list[dict] | None = None):
        """
        registered_members: [{"real_name": str, "placeholder": str}]
        """
        self.registered_members = registered_members or []
        # 按真实姓名长度倒序，避免短名字优先匹配覆盖长名字
        self.registered_members.sort(key=lambda m: len(m.get("real_name", "")), reverse=True)

        # 映射缓存（同一文档内保持占位符稳定）
        self.val_to_placeholder: dict[str, str] = {}
        self.kind_counters: dict[str, int] = {
            "id_card": 1,
            "phone": 1,
            "bank_card": 1,
            "email": 1,
            "policy_no": 1,
            "address": 1,
        }

    def _get_placeholder(self, kind: str, value: str) -> str:
        clean_val = value.strip()
        if clean_val in self.val_to_placeholder:
            return self.val_to_placeholder[clean_val]

        if kind == "id_card":
            ph = f"〔证件{self.kind_counters[kind]}〕"
            self.kind_counters[kind] += 1
        elif kind == "phone":
            ph = f"〔电话{self.kind_counters[kind]}〕"
            self.kind_counters[kind] += 1
        elif kind == "bank_card":
            ph = f"〔卡号{self.kind_counters[kind]}〕"
            self.kind_counters[kind] += 1
        elif kind == "email":
            ph = f"〔邮箱{self.kind_counters[kind]}〕"
            self.kind_counters[kind] += 1
        elif kind == "policy_no":
            ph = "〔保单号〕"
        elif kind == "address":
            ph = "〔地址〕"
        else:
            ph = f"〔信息{len(self.val_to_placeholder) + 1}〕"

        self.val_to_placeholder[clean_val] = ph
        return ph

    def find_spans(self, text: str) -> list[MatchSpan]:
        spans: list[MatchSpan] = []

        # 1. 成员真实姓名精确匹配（按长度倒序）
        for m in self.registered_members:
            real_name = m.get("real_name")
            if not real_name or len(real_name) < 2:
                continue
            idx = 0
            while True:
                pos = text.find(real_name, idx)
                if pos == -1:
                    break
                spans.append(MatchSpan(pos, pos + len(real_name), "name", real_name))
                idx = pos + len(real_name)

        # 2. 身份证号码（严格验证 GB 11643 校验位）
        for m in ID_RE.finditer(text):
            val = m.group()
            if verify_id_checksum(val):
                spans.append(MatchSpan(m.start(), m.end(), "id_card", val))

        # 3. 手机号码
        for m in PHONE_RE.finditer(text):
            val = m.group()
            digits = re.sub(r"\D", "", val)
            if len(digits) == 11 and digits.startswith(("13", "14", "15", "16", "17", "18", "19")):
                spans.append(MatchSpan(m.start(), m.end(), "phone", val))

        # 4. 银行卡号（严格验证 Luhn + 20字内上下文）
        for m in CARD_RE.finditer(text):
            val = m.group()
            digits = re.sub(r"\D", "", val)
            if verify_luhn(digits):
                # 检查前后 20 字符上下文
                ctx_start = max(0, m.start() - 20)
                ctx_end = min(len(text), m.end() + 20)
                ctx = text[ctx_start:ctx_end]
                if any(w in ctx for w in CARD_CONTEXT_WORDS):
                    spans.append(MatchSpan(m.start(), m.end(), "bank_card", val))

        # 5. 邮箱
        for m in EMAIL_RE.finditer(text):
            val = m.group()
            spans.append(MatchSpan(m.start(), m.end(), "email", val))

        # 6. 保单号
        for m in POLICY_NO_RE.finditer(text):
            val = m.group(1)
            spans.append(MatchSpan(m.start(1), m.end(1), "policy_no", val))

        # 7. 地址
        for m in ADDRESS_RE.finditer(text):
            val = m.group(1)
            spans.append(MatchSpan(m.start(1), m.end(1), "address", val))

        # 去重与解决重叠区间（优先长区间）
        spans.sort(key=lambda s: (s.start, -(s.end - s.start)))
        non_overlapping: list[MatchSpan] = []
        last_end = -1
        for s in spans:
            if s.start >= last_end:
                non_overlapping.append(s)
                last_end = s.end
        return non_overlapping

    def deidentify_text(self, text: str) -> DeidentifyResult:
        spans = self.find_spans(text)
        mappings = []

        # 从后往前替换，保持前面偏移量不变
        spans_rev = sorted(spans, key=lambda s: s.start, reverse=True)
        masked = text

        for s in spans_rev:
            if s.kind == "name":
                # 找对应的成员占位符
                ph = None
                for m in self.registered_members:
                    if m.get("real_name") == s.original_value:
                        ph = m.get("placeholder")
                        break
                if not ph:
                    ph = "〔家庭成员〕"
            else:
                ph = self._get_placeholder(s.kind, s.original_value)

            mappings.append({
                "kind": s.kind,
                "placeholder": ph,
                "value": s.original_value,
            })
            masked = masked[: s.start] + ph + masked[s.end :]

        # 二次安全校验：在脱敏后的文本上再次运行敏感正则
        secondary_hits = self._check_residual_pii(masked)
        status = "failed" if secondary_hits > 0 else "success"

        return DeidentifyResult(
            masked_text=masked,
            mappings=mappings,
            spans=spans,
            pii_status=status,
        )

    def _check_residual_pii(self, text: str) -> int:
        hits = 0
        for m in ID_RE.finditer(text):
            if verify_id_checksum(m.group()):
                hits += 1
        for m in PHONE_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group())
            if len(digits) == 11 and digits.startswith(("13", "14", "15", "16", "17", "18", "19")):
                hits += 1
        for m in CARD_RE.finditer(text):
            digits = re.sub(r"\D", "", m.group())
            if verify_luhn(digits):
                ctx_start = max(0, m.start() - 20)
                ctx_end = min(len(text), m.end() + 20)
                if any(w in text[ctx_start:ctx_end] for w in CARD_CONTEXT_WORDS):
                    hits += 1
        return hits


def apply_visual_masking(
    image_path: Path,
    char_map_path: Path,
    spans: list[MatchSpan],
    out_masked_image_path: Path,
) -> None:
    """根据脱敏命中区间与字符级坐标，在 144 DPI 页图上绘制实心遮盖块"""
    if not image_path.exists() or not char_map_path.exists():
        return

    char_map_data = json.loads(char_map_path.read_text(encoding="utf-8"))
    width_pt = char_map_data.get("width_pt", 595.0)
    height_pt = char_map_data.get("height_pt", 842.0)
    chars = char_map_data.get("chars", [])

    img = Image.open(image_path).convert("RGBA")
    draw = ImageDraw.Draw(img)

    img_w, img_h = img.size
    scale_x = img_w / width_pt if width_pt > 0 else 1.0
    scale_y = img_h / height_pt if height_pt > 0 else 1.0

    mask_color = (20, 35, 58, 255)  # 深潭色实心色块

    for s in spans:
        # 在 chars 数组中获取 start..end 对应的 bbox
        if s.start < len(chars) and s.end <= len(chars):
            matched_chars = chars[s.start : s.end]
            for ch in matched_chars:
                bbox = ch.get("bbox")
                if bbox and len(bbox) == 4:
                    x0, y0, x1, y1 = bbox
                    px0 = max(0, int(x0 * scale_x) - 1)
                    py0 = max(0, int(y0 * scale_y) - 1)
                    px1 = min(img_w, int(x1 * scale_x) + 1)
                    py1 = min(img_h, int(y1 * scale_y) + 1)
                    draw.rectangle([px0, py0, px1, py1], fill=mask_color)

    img.convert("RGB").save(out_masked_image_path, "PNG")
