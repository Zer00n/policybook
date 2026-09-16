from datetime import date, timedelta
from types import SimpleNamespace
from app.coverage.calculator import (
    calculate_effective_coverages,
    compute_radar_data,
    compute_heatmap_cell,
    format_cents_to_display,
    format_yuan_to_display,
    DEFAULT_REFERENCES,
)


def test_effective_coverage_medical_max_rule():
    """
    DEV-GUIDE 8.8: 医疗类取最高单一限额，不累加。
    """
    today = date(2026, 9, 16)
    
    cov1 = SimpleNamespace(kind="medical", limit_cents=100000000, waiting_days=30)  # 100万
    cov2 = SimpleNamespace(kind="medical", limit_cents=300000000, waiting_days=30)  # 300万
    cov3 = SimpleNamespace(kind="medical", limit_cents=20000000, waiting_days=30)   # 20万
    
    p1 = SimpleNamespace(
        id="p1",
        product_name="百万医疗险A",
        category="medical",
        effective_date="2026-01-01",
        expiry_date="2027-01-01",
        waiting_days=30,
        sum_insured_cents=None,
        coverages=[cov1, cov2, cov3]
    )

    result = calculate_effective_coverages([p1], current_date=today)
    
    # Must equal 300万 (300000000 cents), NOT 420万
    assert result["medical"]["effective_cents"] == 300000000
    assert result["medical"]["effective_yuan"] == 3000000.0


def test_waiting_period_exclusion():
    """
    出险日期或当前日期在等待期内，不计入有效保额。
    """
    today = date(2026, 9, 16)
    
    # Effective 5 days ago, waiting 30 days -> still in waiting period
    cov = SimpleNamespace(kind="critical_illness", limit_cents=50000000, waiting_days=30)
    p = SimpleNamespace(
        id="p_waiting",
        product_name="等待期重疾险",
        category="critical_illness",
        effective_date="2026-09-11",
        expiry_date="2036-09-11",
        waiting_days=30,
        sum_insured_cents=50000000,
        coverages=[cov]
    )

    result = calculate_effective_coverages([p], current_date=today)
    assert result["critical_illness"]["effective_cents"] == 0


def test_radar_capping_at_120_percent():
    """
    PRD 3.11: 每维为「有效保额 / 参考保额」，封顶 120% 显示。
    """
    effective_map = {
        "critical_illness": {"effective_cents": 100000000, "effective_yuan": 1000000.0},  # 100万
    }
    # Reference is 50万, 100万 / 50万 = 200%, must cap at 120%
    custom_refs = {"critical_illness": 500000}
    
    dims = compute_radar_data(effective_map, custom_refs)
    ci_dim = next(d for d in dims if d["key"] == "critical_illness")
    
    assert ci_dim["ratio"] == 1.20
    assert ci_dim["score_pct"] == 120
    assert ci_dim["has_reference"] is True


def test_unconfigured_reference():
    """
    未设置参考值时，标记 has_reference = False，展示「未设置参考值」。
    """
    effective_map = {
        "pension": {"effective_cents": 50000000, "effective_yuan": 500000.0}
    }
    custom_refs = {"pension": 0}  # 0 or None
    
    dims = compute_radar_data(effective_map, custom_refs)
    pension_dim = next(d for d in dims if d["key"] == "pension")
    
    assert pension_dim["has_reference"] is False
    assert pension_dim["reference_display"] == "未设置参考值"
    assert pension_dim["ratio"] == 0.0


def test_heatmap_cell_statuses():
    """
    热力图状态：none, partial, full
    """
    # None
    cell_none = compute_heatmap_cell(0, 500000, [])
    assert cell_none["status"] == "none"

    # Partial: 20万 / 50万 = 40%
    cell_partial = compute_heatmap_cell(20000000, 500000, [("p1", "重疾险")])
    assert cell_partial["status"] == "partial"
    assert cell_partial["ratio"] == 0.4

    # Full: 60万 / 50万 = 120%
    cell_full = compute_heatmap_cell(60000000, 500000, [("p1", "重疾险")])
    assert cell_full["status"] == "full"
    assert cell_full["ratio"] == 1.2
