import re
from decimal import Decimal, InvalidOperation
from typing import NamedTuple


class ParsedMoney(NamedTuple):
    amount: Decimal
    cents: int
    raw: str


# 大写与小写中文字符映射
CN_DIGITS = {
    "零": 0, "〇": 0,
    "一": 1, "壹": 1,
    "二": 2, "贰": 2, "两": 2,
    "三": 3, "叁": 3,
    "四": 4, "肆": 4,
    "五": 5, "伍": 5,
    "六": 6, "陆": 6,
    "七": 7, "柒": 7,
    "八": 8, "捌": 8,
    "九": 9, "玖": 9,
}

CN_UNITS = {
    "十": 10, "拾": 10,
    "百": 100, "佰": 100,
    "千": 1000, "仟": 1000,
    "万": 10000, "萬": 10000,
    "亿": 100000000, "億": 100000000,
}


def _chinese_to_number(cn_str: str) -> Decimal:
    """将如 '伍拾万'、'五万三千' 纯中文数字转换为数值"""
    total = Decimal(0)
    section = Decimal(0)
    number = Decimal(0)

    for ch in cn_str:
        if ch in CN_DIGITS:
            number = Decimal(CN_DIGITS[ch])
        elif ch in ("亿", "億"):
            section = (section + number) if number != 0 or section == 0 else section
            total += section * Decimal(100000000)
            section = Decimal(0)
            number = Decimal(0)
        elif ch in ("万", "萬"):
            section = (section + number) if number != 0 or section == 0 else section
            total += section * Decimal(10000)
            section = Decimal(0)
            number = Decimal(0)
        elif ch in CN_UNITS:
            unit = Decimal(CN_UNITS[ch])
            if number == 0:
                number = Decimal(1)
            section += number * unit
            number = Decimal(0)

    section += number
    total += section
    return total


def parse_cn_money(text: str | None) -> ParsedMoney | None:
    """
    解析中文或通用金额表达式，返回 Decimal 与整数分。
    覆盖：
    - 50万元
    - 伍拾万元整
    - 500,000.00元
    - 人民币 50 万
    - 0元
    - 1万元/年
    - 首年保费 1,280 元
    - 300元/天
    """
    if not text:
        return None

    cleaned = text.strip()
    # 移除前缀货币符号与干扰词
    cleaned = re.sub(r"^(?:人民币|保费|保额|限额|￥|¥|RMB|CNY|首年保费|基本保额)[\s:：]*", "", cleaned).strip()

    # 1. 尝试匹配阿拉伯数字 + 可选单位（如 500,000.00元, 50万元, 1,280 元, 1280元）
    arabic_pattern = re.compile(
        r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*(万|亿|元|分|角)?"
    )
    match = arabic_pattern.search(cleaned)
    if match:
        num_str, unit = match.groups()
        num_clean = num_str.replace(",", "")
        try:
            val = Decimal(num_clean)
            if unit == "万":
                val *= Decimal(10000)
            elif unit == "亿":
                val *= Decimal(100000000)
            cents = int((val * Decimal(100)).quantize(Decimal("1")))
            return ParsedMoney(amount=val, cents=cents, raw=text)
        except InvalidOperation:
            pass

    # 2. 尝试匹配纯中文数字（如 伍拾万元整, 五十万）
    cn_pattern = re.compile(r"([零〇一壹二贰两三叁四肆五伍六陆七柒八捌九玖十拾百佰千仟万萬亿億]+)(?:元|圆)?")
    cn_match = cn_pattern.search(cleaned)
    if cn_match:
        cn_num = cn_match.group(1)
        try:
            val = _chinese_to_number(cn_num)
            cents = int((val * Decimal(100)).quantize(Decimal("1")))
            return ParsedMoney(amount=val, cents=cents, raw=text)
        except Exception:
            pass

    return None
