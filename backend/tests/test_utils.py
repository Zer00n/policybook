import pytest
from decimal import Decimal
from app.utils.cn_money import parse_cn_money
from app.utils.cn_date import parse_cn_date
from app.utils.cn_ratio import parse_cn_ratio
from app.utils.text_norm import normalize_with_map
from app.utils.verify import verify_quote, merge_char_rects


def test_cn_money_all_variants():
    # 50万元
    res = parse_cn_money("50万元")
    assert res is not None
    assert res.cents == 50000000
    assert res.amount == Decimal("500000")

    # 伍拾万元整
    res = parse_cn_money("伍拾万元整")
    assert res is not None
    assert res.cents == 50000000

    # 500,000.00元
    res = parse_cn_money("500,000.00元")
    assert res is not None
    assert res.cents == 50000000

    # 人民币 50 万
    res = parse_cn_money("人民币 50 万")
    assert res is not None
    assert res.cents == 50000000

    # 0元
    res = parse_cn_money("0元")
    assert res is not None
    assert res.cents == 0

    # 1万元/年
    res = parse_cn_money("1万元/年")
    assert res is not None
    assert res.cents == 1000000

    # 首年保费 1,280 元
    res = parse_cn_money("首年保费 1,280 元")
    assert res is not None
    assert res.cents == 128000


def test_cn_date_parsing():
    assert parse_cn_date("2025年03月15日") == "2025-03-15"
    assert parse_cn_date("2025年3月5日") == "2025-03-05"
    assert parse_cn_date("2025-03-15") == "2025-03-15"
    assert parse_cn_date("2025/3/15") == "2025-03-15"
    assert parse_cn_date("2025.03.15") == "2025-03-15"
    assert parse_cn_date("2025年03月16日零时") == "2025-03-16"
    assert parse_cn_date("无效日期文本") is None


def test_cn_ratio_parsing():
    assert parse_cn_ratio("100%") == 1000
    assert parse_cn_ratio("百分之八十") == 800
    assert parse_cn_ratio("80%（经社保）") == 800
    assert parse_cn_ratio("百分之百") == 1000
    assert parse_cn_ratio("0%") == 0
    assert parse_cn_ratio("无相关") is None


def test_normalize_with_map():
    text = "投保 人 姓 名 ： 张 伟 明"
    norm, idx_map = normalize_with_map(text)
    assert norm == "投保人姓名:张伟明"
    assert len(norm) == len(idx_map)
    # Check that indices point to valid characters in original
    for norm_c, orig_idx in zip(norm, idx_map):
        assert text[orig_idx] in (norm_c, "：", ":")


def test_verify_quote_exact_and_page_correction():
    page1 = "家庭人身意外伤害保险合同\n基本保额：500,000.00元\n生效日期：2025年03月16日零时"
    page2 = "第二条 意外医疗保障\n意外医疗限额为 20,000 元，免赔额 0 元，赔付比例 100%。"
    pages = {1: page1, 2: page2}

    # 1. 目标页命中
    res1 = verify_quote(
        pages_text=pages,
        target_page=1,
        quote="基本保额：500,000.00元",
        field_name="sum_insured",
        model_value="50万元",
    )
    assert res1.status == "verified"
    assert res1.page_no == 1
    assert res1.page_corrected is False
    assert res1.start is not None and res1.end is not None

    # 2. 跨页自动纠偏（模型以为在第 1 页，但实际在第 2 页）
    res2 = verify_quote(
        pages_text=pages,
        target_page=1,
        quote="意外医疗限额为 20,000 元",
        field_name="limit",
        model_value="2万元",
    )
    assert res2.status == "verified"
    assert res2.page_no == 2
    assert res2.page_corrected is True

    # 3. 编造不存在的引用 -> not_found
    res3 = verify_quote(
        pages_text=pages,
        target_page=1,
        quote="本保单涵盖全球所有极端危险运动全额赔付条款",
        field_name="limit",
        model_value="100万",
    )
    assert res3.status == "not_found"

    # 4. 数值冲突检测 -> conflict
    res4 = verify_quote(
        pages_text=pages,
        target_page=1,
        quote="基本保额：500,000.00元",
        field_name="sum_insured",
        model_value="100万元",  # 故意给出不一致的保额
    )
    assert res4.status == "conflict"
    assert "金额不一致" in res4.conflict_reason
