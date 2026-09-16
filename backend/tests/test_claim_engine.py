from datetime import date
from decimal import Decimal
import pytest

from app.claim.engine import (
    ClaimInput,
    MatchedCoverage,
    simulate,
    sub,
    mul,
    cap,
    clamp_zero,
)


def test_interval_arithmetic():
    # sub((a,b),(c,d)) = (max(a-d,0), max(b-c,0))
    res = sub((Decimal("100"), Decimal("120")), (Decimal("20"), Decimal("30")))
    assert res == (Decimal("70"), Decimal("100"))

    # mul((a,b),(r1,r2)) = (a*r1, b*r2)
    res_mul = mul((Decimal("100"), Decimal("200")), (Decimal("0.8"), Decimal("1.0")))
    assert res_mul == (Decimal("80.00"), Decimal("200.00"))

    # cap
    assert cap((Decimal("50"), Decimal("150")), Decimal("100")) == (Decimal("50"), Decimal("100"))

    # clamp zero
    assert clamp_zero((Decimal("-10"), Decimal("50"))) == (Decimal("0"), Decimal("50"))


# Case 1: 无社保 (未经社保比例计算)
def test_claim_no_social_insurance():
    cov = MatchedCoverage(
        id="cov_med_1",
        policy_id="pol_1",
        policy_name="某住院医疗险",
        name="住院医疗费用",
        kind="medical",
        limit=Decimal("10000"),
        deductible=Decimal("100"),
        ratio_with_si=Decimal("1.0"),
        ratio_without_si=Decimal("0.8"),
    )
    inp = ClaimInput(
        event_date=date(2025, 5, 1),
        event_kind="illness",
        total_cost=Decimal("5000"),
        si_reimbursed=Decimal("0"),  # 明确无社保
        matched=[cov],
    )
    result = simulate(inp)

    # 社保报销为 0
    assert result.steps[1].amount == (Decimal("0"), Decimal("0"))
    # (5000 - 100) * 0.8 = 4900 * 0.8 = 3920.00
    med_step = result.steps[2]
    assert med_step.amount == (Decimal("3920.00"), Decimal("3920.00"))
    # 自付 = 5000 - 3920 = 1080.00
    assert result.out_of_pocket == (Decimal("1080.00"), Decimal("1080.00"))
    assert len(result.excluded) == 0


# Case 2: 等待期内出险 (等待期过滤并排除)
def test_claim_within_waiting_period():
    cov = MatchedCoverage(
        id="cov_ci_1",
        policy_id="pol_1",
        policy_name="某重疾险",
        name="重大疾病保险金",
        kind="critical_illness",
        limit=Decimal("300000"),
        deductible=Decimal("0"),
        effective_date=date(2025, 1, 1),
        waiting_days=90,  # 等待期至 2025-04-01
    )
    inp = ClaimInput(
        event_date=date(2025, 2, 15),  # 落在等待期内
        event_kind="illness",
        total_cost=Decimal("20000"),
        si_reimbursed=Decimal("10000"),
        matched=[cov],
    )
    result = simulate(inp)

    # cov 应该被排除
    assert len(result.excluded) == 1
    assert result.excluded[0].coverage_id == "cov_ci_1"
    assert "等待期" in result.excluded[0].reason
    assert len(result.lump_sums) == 0


# Case 3: 两份医疗险叠加 (小额医疗 -> 百万医疗 补偿梯次抵扣)
def test_claim_two_medical_stacking():
    # 小额医疗：免赔 0，限额 10,000，100% 赔付
    cov_small = MatchedCoverage(
        id="cov_small",
        policy_id="pol_small",
        policy_name="小额门急诊医疗险",
        name="意外及疾病小额住院医疗",
        kind="medical",
        limit=Decimal("10000"),
        deductible=Decimal("0"),
        ratio_with_si=Decimal("1.0"),
    )
    # 百万医疗：免赔 10,000，限额 3,000,000，100% 赔付
    cov_million = MatchedCoverage(
        id="cov_million",
        policy_id="pol_million",
        policy_name="尊享百万医疗险",
        name="一般住院医疗",
        kind="medical",
        limit=Decimal("3000000"),
        deductible=Decimal("10000"),
        ratio_with_si=Decimal("1.0"),
    )

    inp = ClaimInput(
        event_date=date(2025, 6, 1),
        event_kind="illness",
        total_cost=Decimal("50000"),
        si_reimbursed=Decimal("20000"),  # 社保报销 20000，剩余 30000
        matched=[cov_million, cov_small],  # 故意乱序传入，验证排序正确性
    )
    result = simulate(inp)

    # step 0: 总费用 50,000
    assert result.steps[0].amount == (Decimal("50000"), Decimal("50000"))
    # step 1: 社保 20,000，剩余 30,000
    assert result.steps[1].amount == (Decimal("20000"), Decimal("20000"))
    assert result.steps[1].remaining == (Decimal("30000"), Decimal("30000"))

    # step 2: 小额医疗先赔：剩余 30,000 抵扣限额 10,000，小额赔 10,000，剩余 20,000
    small_step = result.steps[2]
    assert small_step.coverage_id == "cov_small"
    assert small_step.amount == (Decimal("10000"), Decimal("10000"))
    assert small_step.remaining == (Decimal("20000"), Decimal("20000"))

    # step 3: 百万医疗后赔：剩余 20,000，扣除免赔额 10,000 后赔 10,000，剩余 10,000
    million_step = result.steps[3]
    assert million_step.coverage_id == "cov_million"
    assert million_step.amount == (Decimal("10000"), Decimal("10000"))
    assert million_step.remaining == (Decimal("10000"), Decimal("10000"))

    # 最终自付 = 10,000
    assert result.out_of_pocket == (Decimal("10000"), Decimal("10000"))


# Case 4: 费用低于免赔额
def test_claim_cost_below_deductible():
    cov = MatchedCoverage(
        id="cov_med",
        policy_id="pol_med",
        policy_name="百万医疗",
        name="一般住院医疗",
        kind="medical",
        limit=Decimal("1000000"),
        deductible=Decimal("10000"),
        ratio_with_si=Decimal("1.0"),
    )
    inp = ClaimInput(
        event_date=date(2025, 5, 10),
        event_kind="illness",
        total_cost=Decimal("8000"),
        si_reimbursed=Decimal("3000"),  # 剩余 5000
        matched=[cov],
    )
    result = simulate(inp)

    # 剩余 5000 低于免赔额 10000，扣除免赔额后 base 为 0，赔付 0
    med_step = result.steps[2]
    assert med_step.amount == (Decimal("0"), Decimal("0"))
    assert result.out_of_pocket == (Decimal("5000"), Decimal("5000"))


# Case 5: 给付型与补偿型同时存在 (重疾定额给付 + 医疗补偿独立计算)
def test_claim_lump_sum_and_indemnity_coexist():
    # 医疗险 (补偿型)
    cov_med = MatchedCoverage(
        id="cov_med",
        policy_id="pol_med",
        policy_name="医疗保险",
        name="住院医疗",
        kind="medical",
        limit=Decimal("50000"),
        deductible=Decimal("0"),
        ratio_with_si=Decimal("1.0"),
    )
    # 重疾险 (定额给付型)
    cov_ci = MatchedCoverage(
        id="cov_ci",
        policy_id="pol_ci",
        policy_name="终身重疾险",
        name="恶性肿瘤保险金",
        kind="critical_illness",
        limit=Decimal("500000"),
        deductible=Decimal("0"),
    )

    inp = ClaimInput(
        event_date=date(2025, 7, 1),
        event_kind="illness",
        total_cost=Decimal("40000"),
        si_reimbursed=Decimal("15000"),  # 剩余 25000
        matched=[cov_med, cov_ci],
    )
    result = simulate(inp)

    # 医疗险赔付 25,000，自付为 0
    assert result.steps[2].amount == (Decimal("25000"), Decimal("25000"))
    assert result.out_of_pocket == (Decimal("0"), Decimal("0"))

    # 重疾险独立给付 500,000，不与医疗抵扣
    assert len(result.lump_sums) == 1
    assert result.lump_sums[0].coverage_id == "cov_ci"
    assert result.lump_sums[0].amount == (Decimal("500000"), Decimal("500000"))
