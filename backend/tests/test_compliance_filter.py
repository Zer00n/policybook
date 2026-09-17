from app.utils.compliance import filter_forbidden_phrases
from app.renewal.comparator import filter_forbidden_phrases as comparator_filter


def test_filters_literal_forbidden_phrase():
    text = "这款产品强烈推荐购买，一定能赔。"
    sanitized, hits = filter_forbidden_phrases(text)
    assert "强烈推荐" not in sanitized
    assert "一定能赔" not in sanitized
    assert len(hits) >= 2


def test_filters_whitespace_inserted_bypass_attempt():
    # 半角空格与全角空格插入尝试绕过字面量匹配
    text = "这款 强 烈 推 荐，闭　眼　入 就对了。"
    sanitized, hits = filter_forbidden_phrases(text)
    assert "强" not in sanitized or "值得重点关注" in sanitized
    assert "闭" not in sanitized or "可优先了解" in sanitized
    assert len(hits) >= 2


def test_no_false_positive_on_neutral_text():
    text = "该责任项的免赔额为500元，赔付比例为80%。"
    sanitized, hits = filter_forbidden_phrases(text)
    assert sanitized == text
    assert hits == []


def test_comparator_reexports_same_function():
    """app.renewal.comparator 必须继续可以导入 filter_forbidden_phrases（向后兼容，
    tests/test_compare_matrix.py 直接依赖这个导入路径）。"""
    assert comparator_filter is filter_forbidden_phrases
