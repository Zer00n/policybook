import re
import unicodedata

# 常见标点映射统一表
PUNCT_MAP = {
    "：": ":",
    "；": ";",
    "，": ",",
    "。": ".",
    "！": "!",
    "？": "?",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "——": "-",
    "—": "-",
    "–": "-",
    "、": ",",
}


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """
    返回归一化文本，以及每个归一化字符对应原文中的下标索引。
    规则：
    1. NFKC 标准化
    2. 删除所有空白字符 (空格、全角空格、换行符、Tab等)
    3. 全角半角标点统一
    4. 去掉断行产生的连字符 (如 '-\n' 或 trailing '-')
    """
    if not text:
        return "", []

    norm_chars = []
    idx_map = []

    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        # 检查是否为断行连字符，例如 "-\n" 或 "-\r\n"
        if ch in ("-", "—", "–") and i + 1 < n:
            next_ch = text[i + 1]
            if next_ch in ("\r", "\n", " "):
                # 跳过该连字符与紧随的空白
                i += 1
                while i < n and text[i] in ("\r", "\n", " "):
                    i += 1
                continue

        # 过滤所有空白字符
        if ch.isspace() or ch == "\u3000":
            i += 1
            continue

        # NFKC 转换单字符
        norm_ch = unicodedata.normalize("NFKC", ch)
        # 统一标点
        norm_ch = PUNCT_MAP.get(norm_ch, norm_ch)

        for sub_c in norm_ch:
            if not sub_c.isspace():
                norm_chars.append(sub_c)
                idx_map.append(i)

        i += 1

    return "".join(norm_chars), idx_map
