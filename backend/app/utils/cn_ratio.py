import re


CN_RATIO_WORDS = {
    "百": 100,
    "十": 10,
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


def parse_cn_ratio(text: str | None) -> int | None:
    """
    解析比例/百分比，统一返回千分比整数 (1000 = 100%, 800 = 80%)。
    支持：
    - 100%
    - 80% (经社保)
    - 百分之八十
    - 百分之百
    - 0%
    """
    if not text:
        return None

    cleaned = text.strip()

    # 1. 阿拉伯数字百分比，如 100%, 80.5%
    m_pct = re.search(r"(\d+(?:\.\d+)?)\s*%", cleaned)
    if m_pct:
        try:
            val = float(m_pct.group(1))
            return int(round(val * 10))
        except ValueError:
            pass

    # 2. 中文百分比，如 百分之八十, 百分之百
    m_cn = re.search(r"百分之([零〇一壹二贰两三叁四肆五伍六陆七柒八捌九玖十百]+)", cleaned)
    if m_cn:
        cn_part = m_cn.group(1)
        if cn_part in ("百", "一百", "壹佰"):
            return 1000
        # 八十 -> 80
        val = 0
        if "十" in cn_part:
            parts = cn_part.split("十")
            tens = CN_RATIO_WORDS.get(parts[0], 1) if parts[0] else 1
            units = CN_RATIO_WORDS.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
            val = tens * 10 + units
        else:
            val = CN_RATIO_WORDS.get(cn_part, 0)
        return int(val * 10)

    return None
