from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple

from app.schemas.overview import (
    TimelineSegment,
    PolicyTimelineBand,
    MemberTimeline,
    OverviewMetrics,
    TodoItem,
)


def parse_date(d_str: Optional[str]) -> Optional[date]:
    if not d_str:
        return None
    try:
        clean = d_str.strip().split("T")[0]
        return datetime.strptime(clean, "%Y-%m-%d").date()
    except Exception:
        return None


def format_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def build_member_timeline(
    member: Any,
    policies: List[Any],
    current_date: Optional[date] = None
) -> MemberTimeline:
    today = current_date or date.today()
    bands: List[PolicyTimelineBand] = []
    
    # Sort policies by effective_date ascending
    dated_policies = []
    for pol in policies:
        eff = parse_date(pol.effective_date)
        if eff:
            exp = parse_date(pol.expiry_date) or (eff + timedelta(days=365))
            dated_policies.append((eff, exp, pol))
    
    dated_policies.sort(key=lambda x: x[0])

    for eff, exp, pol in dated_policies:
        segments: List[TimelineSegment] = []
        waiting_days = pol.waiting_days or 0
        
        if waiting_days > 0 and exp > eff:
            wait_end = eff + timedelta(days=waiting_days)
            if wait_end > exp:
                wait_end = exp

            segments.append(
                TimelineSegment(
                    segment_type="waiting",
                    start_date=format_date(eff),
                    end_date=format_date(wait_end),
                    label=f"等待期 ({waiting_days}天)",
                    policy_id=pol.id,
                    policy_name=pol.product_name,
                    color=member.color or "#2A8F82"
                )
            )
            if exp > wait_end:
                segments.append(
                    TimelineSegment(
                        segment_type="effective",
                        start_date=format_date(wait_end),
                        end_date=format_date(exp),
                        label="保障生效",
                        policy_id=pol.id,
                        policy_name=pol.product_name,
                        color=member.color or "#2A8F82"
                    )
                )
        else:
            segments.append(
                TimelineSegment(
                    segment_type="effective",
                    start_date=format_date(eff),
                    end_date=format_date(exp),
                    label="保障生效",
                    policy_id=pol.id,
                    policy_name=pol.product_name,
                    color=member.color or "#2A8F82"
                )
            )

        bands.append(
            PolicyTimelineBand(
                policy_id=pol.id,
                product_name=pol.product_name,
                category=pol.category or "other",
                insurer=pol.insurer or "保险公司",
                start_date=format_date(eff),
                end_date=format_date(exp),
                segments=segments
            )
        )

    # Detect gaps: check per-category consecutive policies as well as overall
    gap_segments: List[TimelineSegment] = []
    
    # 1. Per-category gap detection (e.g. accident, medical, critical_illness)
    cat_policies: Dict[str, List[Any]] = {}
    for eff, exp, pol in dated_policies:
        cat = pol.category or "other"
        cat_policies.setdefault(cat, []).append((eff, exp, pol))

    seen_gaps = set()
    for cat, p_list in cat_policies.items():
        p_list.sort(key=lambda x: x[0])
        for i in range(len(p_list) - 1):
            c_eff, c_exp, c_pol = p_list[i]
            n_eff, n_exp, n_pol = p_list[i + 1]
            if c_exp < n_eff:
                gap_days = (n_eff - c_exp).days
                if gap_days > 1:
                    gap_key = (format_date(c_exp), format_date(n_eff))
                    if gap_key not in seen_gaps:
                        seen_gaps.add(gap_key)
                        gap_segments.append(
                            TimelineSegment(
                                segment_type="gap",
                                start_date=format_date(c_exp),
                                end_date=format_date(n_eff),
                                label=f"断保空档 ({gap_days}天)",
                                policy_name=f"{c_pol.product_name} 与 {n_pol.product_name} 之间"
                            )
                        )

    # 2. Overall consecutive policies check
    if dated_policies:
        for i in range(len(dated_policies) - 1):
            curr_eff, curr_exp, curr_pol = dated_policies[i]
            next_eff, next_exp, next_pol = dated_policies[i + 1]
            if curr_exp < next_eff:
                gap_days = (next_eff - curr_exp).days
                gap_key = (format_date(curr_exp), format_date(next_eff))
                if gap_days > 1 and gap_key not in seen_gaps:
                    seen_gaps.add(gap_key)
                    gap_segments.append(
                        TimelineSegment(
                            segment_type="gap",
                            start_date=format_date(curr_exp),
                            end_date=format_date(next_eff),
                            label=f"断保空档 ({gap_days}天)",
                            policy_name=f"{curr_pol.product_name} 与 {next_pol.product_name} 之间"
                        )
                    )

        # 3. Check if any expired policy in a category has not been renewed as of today
        for cat, p_list in cat_policies.items():
            last_eff, last_exp, last_pol = p_list[-1]
            if last_exp < today:
                gap_days = (today - last_exp).days
                gap_key = (format_date(last_exp), format_date(today))
                if gap_days > 1 and gap_key not in seen_gaps:
                    seen_gaps.add(gap_key)
                    gap_segments.append(
                        TimelineSegment(
                            segment_type="gap",
                            start_date=format_date(last_exp),
                            end_date=format_date(today),
                            label=f"已断保 ({gap_days}天)",
                            policy_name=last_pol.product_name
                        )
                    )

    has_gap = len(gap_segments) > 0

    return MemberTimeline(
        member_id=member.id,
        member_name=member.display_name,
        member_color=member.color or "#2A8F82",
        relation=member.relation or "本人",
        has_gap=has_gap,
        bands=bands,
        gap_segments=gap_segments
    )


def compute_overview_metrics(
    all_policies: List[Any],
    member_timelines: List[MemberTimeline],
    current_date: Optional[date] = None
) -> OverviewMetrics:
    today = current_date or date.today()
    in_30d = today + timedelta(days=30)

    total_premium_cents = 0
    active_count = 0
    expiring_30d_count = 0

    for pol in all_policies:
        exp = parse_date(pol.expiry_date)
        eff = parse_date(pol.effective_date)

        # Active check: effective <= today and (exp is None or exp >= today)
        is_active = True
        if eff and eff > today:
            is_active = False
        if exp and exp < today:
            is_active = False

        if is_active:
            active_count += 1
            # Premium
            p_cents = pol.premium_cents or 0
            pay_mode = pol.pay_mode or "年交"
            if "月" in pay_mode:
                total_premium_cents += p_cents * 12
            else:
                total_premium_cents += p_cents

        if exp and today <= exp <= in_30d:
            expiring_30d_count += 1

    gap_member_count = sum(1 for m in member_timelines if m.has_gap)

    return OverviewMetrics(
        total_annual_premium_cents=total_premium_cents,
        total_annual_premium_yuan=round(total_premium_cents / 100.0, 2),
        active_policy_count=active_count,
        expiring_30d_count=expiring_30d_count,
        gap_member_count=gap_member_count
    )


def build_overview_todos(
    all_policies: List[Any],
    review_jobs: List[Any],
    member_timelines: List[MemberTimeline],
    current_date: Optional[date] = None
) -> List[TodoItem]:
    today = current_date or date.today()
    in_30d = today + timedelta(days=30)
    in_60d = today + timedelta(days=60)

    todos: List[TodoItem] = []

    # 1. Draft review jobs
    for job in review_jobs:
        todos.append(
            TodoItem(
                id=f"job-{job.id}",
                kind="review_draft",
                title="保单草稿待核对",
                description=f"上传任务 #{job.id[:8]} 抽取完成，请核对责任项与免责条款并确认入库",
                link=f"/import/{job.id}",
                severity="info",
                date=format_date(job.created_at.date()) if hasattr(job.created_at, "date") else None
            )
        )

    # 2. Expiring policies
    for pol in all_policies:
        exp = parse_date(pol.expiry_date)
        if exp and today <= exp <= in_60d:
            days_left = (exp - today).days
            sev = "urgent" if days_left <= 7 else ("warning" if days_left <= 30 else "info")
            todos.append(
                TodoItem(
                    id=f"exp-{pol.id}",
                    kind="expiring_soon",
                    title=f"保单到期提醒：{pol.product_name}",
                    description=f"{pol.insurer} 的 {pol.product_name} 将于 {format_date(exp)} 到期（剩余 {days_left} 天），建议及时办理续保",
                    link=f"/policies/{pol.id}",
                    severity=sev,
                    date=format_date(exp)
                )
            )

    # 3. Gaps
    for mt in member_timelines:
        if mt.has_gap:
            for g in mt.gap_segments:
                todos.append(
                    TodoItem(
                        id=f"gap-{mt.member_id}-{g.start_date}",
                        kind="coverage_gap",
                        title=f"保障空档预警：{mt.member_name}",
                        description=f"{mt.member_name} 在 {g.start_date} 至 {g.end_date} 存在 {g.label}，期间出险无法获赔",
                        link="/overview",
                        severity="warning",
                        date=g.start_date
                    )
                )

    # Sort: urgent > warning > info
    severity_order = {"urgent": 0, "warning": 1, "info": 2}
    todos.sort(key=lambda t: severity_order.get(t.severity, 3))

    return todos
