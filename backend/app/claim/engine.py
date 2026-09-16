from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal


@dataclass
class MatchedCoverage:
    id: str
    policy_id: str
    policy_name: str
    name: str
    kind: str  # death, disability, critical_illness, medical, accident_medical, hospital_allowance, transport_extra, sudden_death, other
    limit: Decimal | None
    deductible: Decimal | None
    deductible_scope: Literal["annual", "per_claim", "none", "unknown"] = "none"
    ratio_with_si: Decimal | None = None
    ratio_without_si: Decimal | None = None
    effective_date: date | None = None
    waiting_days: int | None = None
    is_rider: bool = False
    evidence_ids: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass
class ClaimInput:
    event_date: date
    event_kind: Literal["illness", "accident", "death", "other"]
    total_cost: Decimal
    si_covered_cost: Decimal | None = None       # 社保范围内费用
    si_reimbursed: Decimal | None = None         # 用户填写的实际社保报销
    si_ratio_range: tuple[Decimal, Decimal] | None = None  # 城市报销比例区间 (low, high)
    matched: list[MatchedCoverage] = field(default_factory=list)  # 由模型匹配、代码补全参数


@dataclass
class Step:
    label: str
    amount: tuple[Decimal, Decimal]
    remaining: tuple[Decimal, Decimal]
    coverage_id: str | None
    evidence_ids: list[str]
    note: str | None = None


@dataclass
class LumpSum:
    coverage_id: str
    coverage_name: str
    policy_name: str
    amount: tuple[Decimal, Decimal]
    evidence_ids: list[str]
    note: str | None = None


@dataclass
class ExcludedCoverage:
    coverage_id: str
    coverage_name: str
    policy_name: str
    reason: str
    evidence_ids: list[str]


@dataclass
class ClaimResult:
    steps: list[Step]
    lump_sums: list[LumpSum]
    excluded: list[ExcludedCoverage]
    out_of_pocket: tuple[Decimal, Decimal]


# 纯区间运算函数
def sub(interval1: tuple[Decimal, Decimal], interval2: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    """
    sub((a,b),(c,d)) = (max(a-d,0), max(b-c,0))
    注意：为保持区间 low <= high，若 low > high 则交换或取 max
    """
    a, b = interval1
    c, d = interval2
    low = max(a - d, Decimal(0))
    high = max(b - c, Decimal(0))
    if low > high:
        low, high = high, low
    return (low, high)


def mul(interval: tuple[Decimal, Decimal], ratios: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    """mul((a,b),(r1,r2)) = (a*r1, b*r2)"""
    a, b = interval
    r1, r2 = ratios
    low = (a * r1).quantize(Decimal("0.01"))
    high = (b * r2).quantize(Decimal("0.01"))
    if low > high:
        low, high = high, low
    return (low, high)


def cap(interval: tuple[Decimal, Decimal], limit: Decimal | None) -> tuple[Decimal, Decimal]:
    """若存在保额/限额，封顶"""
    if limit is None:
        return interval
    a, b = interval
    low = min(a, limit)
    high = min(b, limit)
    if low > high:
        low, high = high, low
    return (low, high)


def clamp_zero(interval: tuple[Decimal, Decimal]) -> tuple[Decimal, Decimal]:
    """确保区间不小于 0"""
    a, b = interval
    return (max(a, Decimal(0)), max(b, Decimal(0)))


def social_insurance_range(inp: ClaimInput) -> tuple[Decimal, Decimal]:
    """计算社保报销区间"""
    # 1. 用户填写了明确的实际社保报销
    if inp.si_reimbursed is not None:
        val = min(inp.si_reimbursed, inp.total_cost)
        return (val, val)

    # 2. 用户填写了社保范围内费用
    if inp.si_covered_cost is not None and inp.si_covered_cost > 0:
        base_cost = min(inp.si_covered_cost, inp.total_cost)
        if inp.si_ratio_range is not None:
            r_low, r_high = inp.si_ratio_range
            return (base_cost * r_low, base_cost * r_high)
        # 未配置时按 0 与常见区间 50%~85% 给出两个端点
        return (Decimal(0), (base_cost * Decimal("0.85")).quantize(Decimal("0.01")))

    # 3. 未发生社保或未知且未填费用
    return (Decimal(0), Decimal(0))


def si_note(inp: ClaimInput) -> str:
    if inp.si_reimbursed is not None:
        return "用户实际填报社保报销额"
    if inp.si_covered_cost is not None:
        if inp.si_ratio_range is not None:
            return f"按设定比例 {inp.si_ratio_range[0]*100:.0f}% ~ {inp.si_ratio_range[1]*100:.0f}% 估算"
        return "未配置社保比例，估算区间为 0% ~ 85%"
    return "未走社保或无社保报销"


def split_by_waiting_period(
    matched: list[MatchedCoverage],
    event_date: date
) -> tuple[list[MatchedCoverage], list[ExcludedCoverage]]:
    """拆分正常责任项与等待期内排除的责任项"""
    active: list[MatchedCoverage] = []
    excluded: list[ExcludedCoverage] = []

    for cov in matched:
        if cov.effective_date and cov.waiting_days and cov.waiting_days > 0:
            waiting_end = cov.effective_date + timedelta(days=cov.waiting_days)
            if event_date < waiting_end:
                excluded.append(
                    ExcludedCoverage(
                        coverage_id=cov.id,
                        coverage_name=cov.name,
                        policy_name=cov.policy_name,
                        reason=f"出险日期 {event_date} 落在等待期内（等待期至 {waiting_end}），通常不予赔付",
                        evidence_ids=cov.evidence_ids,
                    )
                )
                continue
        active.append(cov)

    return active, excluded


def is_indemnity(cov: MatchedCoverage) -> bool:
    """是否为补偿型责任（医疗、意外医疗、住院津贴等）"""
    return cov.kind in ("medical", "accident_medical", "hospital_allowance") or "医疗" in cov.name


def is_lump_sum(cov: MatchedCoverage) -> bool:
    """是否为定额给付型责任（重疾、伤残、身故等）"""
    return cov.kind in ("critical_illness", "death", "disability", "sudden_death", "transport_extra") or "重疾" in cov.name or "身故" in cov.name or "伤残" in cov.name


def order_indemnity(active: list[MatchedCoverage]) -> list[MatchedCoverage]:
    """
    补偿型抵扣顺序：
    小额医疗 (限额 <= 50,000 或名称含小额) → 意外医疗 → 百万医疗 (限额 > 50,000 或名称含百万) → 其他
    """
    indemnities = [c for c in active if is_indemnity(c)]

    def priority(c: MatchedCoverage) -> int:
        name = c.name
        is_small = "小额" in name or (c.limit and c.limit <= Decimal(50000))
        if is_small and c.kind == "medical":
            return 1
        if c.kind == "accident_medical" or "意外医疗" in name:
            return 2
        if "百万" in name or (c.limit and c.limit > Decimal(50000)):
            return 3
        return 4

    return sorted(indemnities, key=priority)


def order_lump_sum(active: list[MatchedCoverage]) -> list[MatchedCoverage]:
    """定额给付型责任清单"""
    return [c for c in active if is_lump_sum(c)]


def apply_deductible(
    remaining: tuple[Decimal, Decimal],
    cov: MatchedCoverage
) -> tuple[Decimal, Decimal]:
    """应用免赔额扣减"""
    if not cov.deductible or cov.deductible <= Decimal(0):
        return remaining

    ded = cov.deductible
    if cov.deductible_scope == "unknown":
        # 共享/单次规则未知时取两端：一端扣减免赔额，一端不扣减（已抵扣完）
        base_low = max(remaining[0] - ded, Decimal(0))
        base_high = remaining[1]
        return (base_low, base_high)

    return sub(remaining, (ded, ded))


def ratio_range(cov: MatchedCoverage, inp: ClaimInput) -> tuple[Decimal, Decimal]:
    """获取经社保或未经社保的赔付比例区间"""
    r_si = cov.ratio_with_si if cov.ratio_with_si is not None else Decimal("1.0")
    r_no_si = cov.ratio_without_si if cov.ratio_without_si is not None else r_si

    # 1. 明确有实际社保报销
    if inp.si_reimbursed is not None and inp.si_reimbursed > 0:
        return (r_si, r_si)

    # 2. 明确无社保或报销为 0
    if inp.si_reimbursed == Decimal(0) and inp.si_covered_cost is None:
        return (r_no_si, r_no_si)

    # 3. 社保报销不确定时，取两端比例
    low = min(r_si, r_no_si)
    high = max(r_si, r_no_si)
    return (low, high)


def lump_sum(cov: MatchedCoverage, inp: ClaimInput) -> LumpSum:
    """计算定额给付型给付额"""
    amt = cov.limit if cov.limit is not None else Decimal(0)
    return LumpSum(
        coverage_id=cov.id,
        coverage_name=cov.name,
        policy_name=cov.policy_name,
        amount=(amt, amt),
        evidence_ids=cov.evidence_ids,
        note="按保额全额定额给付，不抵扣医疗费用",
    )


def simulate(inp: ClaimInput) -> ClaimResult:
    """
    DEV-GUIDE 8.5 纯函数模拟核心入口
    """
    remaining = (inp.total_cost, inp.total_cost)
    steps: list[Step] = []

    # 0. 起始总费用
    steps.append(
        Step(
            label="总医疗费用",
            amount=(inp.total_cost, inp.total_cost),
            remaining=remaining,
            coverage_id=None,
            evidence_ids=[],
            note="本次出险实际产生总费用",
        )
    )

    # 1. 社保报销抵扣
    si = social_insurance_range(inp)
    remaining = sub(remaining, si)
    steps.append(
        Step(
            label="社保报销",
            amount=si,
            remaining=remaining,
            coverage_id=None,
            evidence_ids=[],
            note=si_note(inp),
        )
    )

    # 2. 等待期过滤
    active, excluded = split_by_waiting_period(inp.matched, inp.event_date)

    # 3. 补偿型：按 小额医疗 → 意外医疗 → 百万医疗 → 其他 顺序
    for cov in order_indemnity(active):
        base = apply_deductible(remaining, cov)
        ratios = ratio_range(cov, inp)
        paid = mul(base, ratios)
        paid = cap(paid, cov.limit)
        remaining = sub(remaining, paid)
        note = f"{cov.policy_name} - {cov.name}"
        if cov.deductible and cov.deductible > 0:
            note += f" (扣减免赔额 {cov.deductible}元)"
        steps.append(
            Step(
                label=cov.name,
                amount=paid,
                remaining=remaining,
                coverage_id=cov.id,
                evidence_ids=cov.evidence_ids,
                note=note,
            )
        )

    # 4. 给付型：重疾、伤残、身故，独立计算，不抵扣费用
    lump_sums = [lump_sum(cov, inp) for cov in order_lump_sum(active)]

    return ClaimResult(
        steps=steps,
        lump_sums=lump_sums,
        excluded=excluded,
        out_of_pocket=clamp_zero(remaining),
    )
