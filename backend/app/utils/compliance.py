"""合规表述过滤（红线8）：禁止购买建议/核保结论/理赔承诺类措辞。

供问答（qa.py）、理赔模拟（claim.py）、续保顾问（renewal/comparator.py）
等所有面向模型自由生成文本的接口在返回给用户前调用。
"""
import re

FORBIDDEN_PHRASE_REPLACEMENTS = [
    (r"强\s*烈\s*推\s*荐", "值得重点关注的方案"),
    (r"强\s*烈\s*建\s*议", "建议关注"),
    (r"推\s*荐\s*购\s*买", "与你的需求更匹配的维度"),
    (r"最\s*适\s*合", "匹配度较高的"),
    (r"最\s*划\s*算", "费率相对较低的"),
    (r"性\s*价\s*比\s*最\s*高", "综合保障相对均衡的"),
    (r"一\s*定\s*能\s*赔", "通常在保障责任范围内的"),
    (r"保\s*证\s*赔\s*付", "符合条款约定时予以给付"),
    (r"绝\s*对\s*保\s*证", "严格按照条款约定"),
    (r"百\s*分\s*之\s*百\s*报\s*销", "依条款全额补偿"),
    (r"无\s*条\s*件\s*给\s*付", "依约定标准给付"),
    (r"闭\s*眼\s*(?:入|冲)", "可优先了解"),
    (r"无\s*脑\s*冲", "可优先了解"),
]


def filter_forbidden_phrases(text: str) -> tuple[str, list[str]]:
    """
    Substitutes marketing / compliance forbidden phrases with neutral wording
    (Red Line 8 & DEV-GUIDE 8.7). Returns (sanitized_text, hit_phrases).
    每条模式字符间允许插入空白（含全角空格），防止用空格分隔字符绕过字面量匹配。
    """
    if not text:
        return "", []

    hits: list[str] = []
    sanitized = text

    for pattern, replacement in FORBIDDEN_PHRASE_REPLACEMENTS:
        matches = re.findall(pattern, sanitized)
        if matches:
            hits.extend(matches)
            sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized, hits
