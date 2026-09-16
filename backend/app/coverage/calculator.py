import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple

DIMENSIONS = [
    {"key": "death", "name": "身故"},
    {"key": "critical_illness", "name": "重疾"},
    {"key": "medical", "name": "医疗"},
    {"key": "accident", "name": "意外"},
    {"key": "income_loss", "name": "收入中断"},
    {"key": "pension", "name": "养老"},
]

DEFAULT_REFERENCES = {
    "death": 1000000,            # 100万
    "critical_illness": 500000,    # 50万
    "medical": 3000000,           # 300万
    "accident": 1000000,          # 100万
    "income_loss": 200000,        # 20万
    "pension": 500000,            # 50万
}


def format_cents_to_display(cents: int) -> str:
    yuan = cents / 100.0
    if yuan <= 0:
        return "0元"
    if yuan >= 10000:
        wan = yuan / 10000.0
        if wan == int(wan):
            return f"{int(wan)}万"
        return f"{wan:.1f}万"
    return f"{int(yuan)}元"


def format_yuan_to_display(yuan: float) -> str:
    if yuan <= 0:
        return "0元"
    if yuan >= 10000:
        wan = yuan / 10000.0
        if wan == int(wan):
            return f"{int(wan)}万"
        return f"{wan:.1f}万"
    return f"{int(yuan)}元"


def parse_iso_date(d_str: Optional[str]) -> Optional[date]:
    if not d_str:
        return None
    try:
        clean = d_str.strip().split("T")[0]
        return datetime.strptime(clean, "%Y-%m-%d").date()
    except Exception:
        return None


def calculate_effective_coverages(
    policies: List[Any],
    current_date: Optional[date] = None
) -> Dict[str, Dict[str, Any]]:
    """
    DEV-GUIDE 8.8:
    每位成员每个维度的有效保额 = 该维度下所有生效且不在等待期的责任项保额之和
    （医疗类取最高单一限额，不累加）。
    """
    today = current_date or date.today()
    
    dim_cents: Dict[str, List[int]] = {d["key"]: [] for d in DIMENSIONS}
    dim_policies: Dict[str, List[Tuple[str, str]]] = {d["key"]: [] for d in DIMENSIONS}

    for policy in policies:
        # Check active status & dates
        eff = parse_iso_date(policy.effective_date)
        exp = parse_iso_date(policy.expiry_date)
        
        # If expired before today, skip
        if exp and exp < today:
            continue
        # If effective after today, skip
        if eff and eff > today:
            continue
            
        policy_waiting = policy.waiting_days or 0
        policy_in_waiting = False
        if eff and policy_waiting > 0:
            waiting_end = eff + timedelta(days=policy_waiting)
            if today < waiting_end:
                policy_in_waiting = True

        policy_cat = policy.category or ""
        
        # 1. Process coverages if present
        has_matched_coverage = False
        if hasattr(policy, "coverages") and policy.coverages:
            for cov in policy.coverages:
                c_wait = cov.waiting_days or policy_waiting
                if eff and c_wait > 0:
                    cov_end = eff + timedelta(days=c_wait)
                    if today < cov_end:
                        continue  # in waiting period
                elif policy_in_waiting:
                    continue

                cents = cov.limit_cents or 0
                if cents <= 0:
                    continue

                kind = cov.kind or ""
                pol_tuple = (policy.id, policy.product_name)

                if kind in ("death", "sudden_death"):
                    dim_cents["death"].append(cents)
                    dim_policies["death"].append(pol_tuple)
                    has_matched_coverage = True
                elif kind == "critical_illness":
                    dim_cents["critical_illness"].append(cents)
                    dim_policies["critical_illness"].append(pol_tuple)
                    has_matched_coverage = True
                elif kind in ("medical", "accident_medical"):
                    dim_cents["medical"].append(cents)
                    dim_policies["medical"].append(pol_tuple)
                    has_matched_coverage = True
                elif kind in ("disability", "transport_extra"):
                    dim_cents["accident"].append(cents)
                    dim_policies["accident"].append(pol_tuple)
                    has_matched_coverage = True
                elif kind == "hospital_allowance":
                    dim_cents["income_loss"].append(cents)
                    dim_policies["income_loss"].append(pol_tuple)
                    has_matched_coverage = True

        # 2. Fallback to policy category & sum_insured_cents if no coverage or extra
        if not policy_in_waiting and policy.sum_insured_cents and policy.sum_insured_cents > 0:
            cents = policy.sum_insured_cents
            pol_tuple = (policy.id, policy.product_name)

            if policy_cat in ("term_life", "whole_life") and not has_matched_coverage:
                dim_cents["death"].append(cents)
                dim_policies["death"].append(pol_tuple)
            elif policy_cat == "critical_illness" and not has_matched_coverage:
                dim_cents["critical_illness"].append(cents)
                dim_policies["critical_illness"].append(pol_tuple)
            elif policy_cat == "medical" and not has_matched_coverage:
                dim_cents["medical"].append(cents)
                dim_policies["medical"].append(pol_tuple)
            elif policy_cat == "accident" and not has_matched_coverage:
                dim_cents["accident"].append(cents)
                dim_policies["accident"].append(pol_tuple)
            elif policy_cat in ("annuity", "endowment_whole_life", "whole_life"):
                dim_cents["pension"].append(cents)
                dim_policies["pension"].append(pol_tuple)

    result = {}
    for d in DIMENSIONS:
        k = d["key"]
        cents_list = dim_cents[k]
        if k == "medical":
            # DEV-GUIDE 8.8: 医疗类取最高单一限额，不累加
            effective_cents = max(cents_list) if cents_list else 0
        else:
            effective_cents = sum(cents_list)

        unique_pols = []
        seen = set()
        for pid, pname in dim_policies[k]:
            if pid not in seen:
                seen.add(pid)
                unique_pols.append((pid, pname))

        result[k] = {
            "effective_cents": effective_cents,
            "effective_yuan": effective_cents / 100.0,
            "policies": unique_pols
        }

    return result


def compute_radar_data(
    effective_map: Dict[str, Dict[str, Any]],
    user_references: Optional[Dict[str, int]] = None
) -> List[Dict[str, Any]]:
    dims_data = []
    refs = user_references or DEFAULT_REFERENCES

    for d in DIMENSIONS:
        k = d["key"]
        name = d["name"]
        eff = effective_map.get(k, {"effective_cents": 0, "effective_yuan": 0.0})
        eff_cents = eff["effective_cents"]
        eff_yuan = eff["effective_yuan"]

        ref_yuan = refs.get(k)
        if ref_yuan is not None and ref_yuan > 0:
            ref_cents = int(ref_yuan * 100)
            ratio = eff_yuan / float(ref_yuan)
            capped_ratio = min(ratio, 1.20)
            score_pct = int(round(capped_ratio * 100))
            has_ref = True
            ref_display = format_yuan_to_display(float(ref_yuan))
        else:
            ref_cents = None
            ref_yuan = None
            ratio = 0.0
            capped_ratio = 0.0
            score_pct = 0
            has_ref = False
            ref_display = "未设置参考值"

        dims_data.append({
            "key": k,
            "name": name,
            "effective_cents": eff_cents,
            "effective_yuan": eff_yuan,
            "effective_display": format_cents_to_display(eff_cents),
            "reference_cents": ref_cents,
            "reference_yuan": ref_yuan,
            "reference_display": ref_display,
            "ratio": round(capped_ratio if has_ref else 0.0, 3),
            "score_pct": score_pct,
            "has_reference": has_ref
        })

    return dims_data


def compute_heatmap_cell(
    effective_cents: int,
    ref_yuan: Optional[int],
    policies: List[Tuple[str, str]]
) -> Dict[str, Any]:
    eff_yuan = effective_cents / 100.0
    pol_ids = [p[0] for p in policies]
    pol_names = [p[1] for p in policies]

    if effective_cents <= 0:
        return {
            "status": "none",
            "effective_yuan": 0.0,
            "effective_display": "无保障",
            "ratio": 0.0,
            "policy_ids": [],
            "policy_names": []
        }

    target_yuan = float(ref_yuan) if (ref_yuan and ref_yuan > 0) else 100000.0
    ratio = eff_yuan / target_yuan

    if ratio >= 1.0:
        status = "full"
    else:
        status = "partial"

    return {
        "status": status,
        "effective_yuan": eff_yuan,
        "effective_display": format_cents_to_display(effective_cents),
        "ratio": round(min(ratio, 1.20), 3),
        "policy_ids": pol_ids,
        "policy_names": pol_names
    }
