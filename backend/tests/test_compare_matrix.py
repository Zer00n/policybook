import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ulid import ULID

from app.db.models import Base, Coverage, Policy, SourceRecord
from app.renewal.comparator import (
    build_comparison_matrix,
    filter_forbidden_phrases,
    format_cents_to_display,
    get_dimension_value_from_coverages,
    verify_url_provenance,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_format_cents_to_display():
    assert format_cents_to_display(None) == "条款中未找到"
    assert format_cents_to_display(0) == "0 元 / 0 免赔"
    assert format_cents_to_display(100000000) == "100 万元"
    assert format_cents_to_display(5000000) == "5 万元"
    assert format_cents_to_display(15000) == "150 元"


def test_filter_forbidden_phrases():
    text = "我们为您强烈推荐购买平安综合意外险，这是目前市场上最适合您的方案，也是最划算的产品。只要出险，保险公司一定能赔，并且绝对保证赔付。"
    sanitized, hits = filter_forbidden_phrases(text)

    # All forbidden phrases replaced
    assert "强烈推荐" not in sanitized
    assert "推荐购买" not in sanitized
    assert "最适合" not in sanitized
    assert "最划算" not in sanitized
    assert "一定能赔" not in sanitized
    assert "保证赔付" not in sanitized

    # Neutral replacements applied
    assert "值得重点关注的方案" in sanitized or "与你的需求更匹配的维度" in sanitized
    assert "匹配度较高的" in sanitized
    assert "费率相对较低的" in sanitized
    assert "通常在保障责任范围内的" in sanitized
    assert "符合条款约定时予以给付" in sanitized

    assert len(hits) >= 5


def test_verify_url_provenance(db_session):
    session_id = str(ULID())
    url_valid = "https://www.pingan.com/product/accident.html"
    url_fake = "https://malicious-fabricated-site.com/fake.html"

    # Add valid URL to source_record
    rec = SourceRecord(
        session_id=session_id,
        url=url_valid,
        domain="pingan.com",
        title="平安官方条款",
        via="search",
    )
    db_session.add(rec)
    db_session.commit()

    narrative = (
        f"该产品的条款已在中国平安官网披露（详情见 {url_valid}）。"
        f"据第三方分析，该保单在某论坛有额外优惠（详情见 {url_fake}）。"
        "总体来看，两款产品的身故伤残责任均在百万额度。"
    )

    cleaned, removed_count = verify_url_provenance(narrative, session_id, db_session)

    # Fake URL sentence must be removed
    assert url_fake not in cleaned
    assert "某论坛有额外优惠" not in cleaned

    # Valid URL sentence and normal sentences kept
    assert url_valid in cleaned
    assert "两款产品的身故伤残责任均在百万额度" in cleaned
    assert removed_count == 1


def test_build_comparison_matrix():
    baseline = Policy(
        id=str(ULID()),
        product_name="现有保单A",
        premium_cents=29900,
    )
    cov1 = Coverage(
        id=str(ULID()),
        name="意外身故及伤残",
        kind="death",
        limit_cents=50000000,  # 50万
    )
    cov2 = Coverage(
        id=str(ULID()),
        name="意外伤害医疗",
        kind="accident_medical",
        limit_cents=2000000,  # 2万
        deductible_cents=10000,  # 100元
        ratio_with_si=1000,
    )
    baseline.coverages = [cov1, cov2]

    cand_covs = [
        Coverage(
            id=str(ULID()),
            name="意外身故及伤残",
            kind="death",
            limit_cents=100000000,  # 100万
        ),
        Coverage(
            id=str(ULID()),
            name="猝死保险金",
            kind="sudden_death",
            limit_cents=30000000,  # 30万
        ),
    ]

    candidate_data = [
        {
            "id": "cand_pingan",
            "product_name": "平安综合意外2025",
            "premium_text": "288 元/年",
            "url": "https://www.pingan.com/product/accident.html",
            "coverages": cand_covs,
        }
    ]

    matrix = build_comparison_matrix(baseline, candidate_data)

    assert len(matrix.products) == 2
    assert matrix.products[0].is_baseline is True
    assert matrix.products[1].is_baseline is False
    assert "平安综合意外2025" in matrix.products[1].name

    # Check death row
    death_row = next(r for r in matrix.rows if r.dimension_key == "death")
    assert "50 万元" in death_row.baseline_cell.value
    assert "100 万元" in death_row.candidate_cells["cand_pingan"].value

    # Check sudden death row: baseline missing, candidate covered
    sudden_row = next(r for r in matrix.rows if r.dimension_key == "sudden_death")
    assert sudden_row.baseline_cell.status == "missing"
    assert "30 万元" in sudden_row.candidate_cells["cand_pingan"].value


def test_deductible_dimension_does_not_fabricate_when_no_medical_coverage():
    """候选产品完全没有医疗类责任项时，不应凭空返回“0 元免赔 / covered”，
    必须如实标注“不含医疗责任 / missing”。"""
    coverages_without_medical = [
        Coverage(id=str(ULID()), name="意外身故及伤残", kind="death", limit_cents=50000000),
    ]
    cell = get_dimension_value_from_coverages(coverages_without_medical, "deductible")
    assert cell.status == "missing"
    assert cell.value == "不含医疗责任"


def test_deductible_dimension_reports_actual_value_when_present():
    coverages_with_medical = [
        Coverage(id=str(ULID()), name="意外医疗", kind="accident_medical",
                  limit_cents=2000000, deductible_cents=10000),
    ]
    cell = get_dimension_value_from_coverages(coverages_with_medical, "deductible")
    assert cell.status == "covered"
    assert cell.value != "不含医疗责任"
