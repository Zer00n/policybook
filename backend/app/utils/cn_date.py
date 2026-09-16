import re
from datetime import datetime


def parse_cn_date(text: str | None) -> str | None:
    """
    解析各种中英文日期表达，统一返回 'YYYY-MM-DD' 格式。
    支持：
    - 2025年03月15日 / 2025年3月15日
    - 2025-03-15 / 2025-3-15
    - 2025/03/15 / 2025/3/15
    - 2025.03.15 / 2025.3.15
    - 2025年03月16日零时
    """
    if not text:
        return None

    cleaned = text.strip()

    # 1. 匹配 YYYY年MM月DD日
    m_cn = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?", cleaned)
    if m_cn:
        year, month, day = int(m_cn.group(1)), int(m_cn.group(2)), int(m_cn.group(3))
        try:
            d = datetime(year, month, day)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # 2. 匹配 YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    m_sep = re.search(r"(\d{4})[-/. ](\d{1,2})[-/. ](\d{1,2})", cleaned)
    if m_sep:
        year, month, day = int(m_sep.group(1)), int(m_sep.group(2)), int(m_sep.group(3))
        try:
            d = datetime(year, month, day)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return None
