import re
from typing import Any
from sqlalchemy.orm import Session

from app.db.models import Coverage, Policy, SourceRecord
from app.schemas.renewal import (
    ComparisonCell,
    ComparisonMatrix,
    ComparisonRow,
    ProductColumn,
)

# Ordered dimension keys for accident insurance comparison
ACCIDENT_DIMENSION_ORDER = [
    ("death", "意外身故及伤残"),
    ("accident_medical", "意外医疗额度"),
    ("deductible", "意外医疗免赔额"),
    ("reimbursement_ratio", "意外医疗报销比例"),
    ("sudden_death", "猝死保障"),
    ("transport_extra", "交通意外额外给付"),
    ("hospital_allowance", "意外住院津贴"),
    ("exclusions", "重点免责约定"),
]

FORBIDDEN_PHRASE_REPLACEMENTS = [
    (r"强烈推荐", "值得重点关注的方案"),
    (r"推荐购买", "与你的需求更匹配的维度"),
    (r"最适合", "匹配度较高的"),
    (r"最划算", "费率相对较低的"),
    (r"性价比最高", "综合保障相对均衡的"),
    (r"一定能赔", "通常在保障责任范围内的"),
    (r"保证赔付", "符合条款约定时予以给付"),
    (r"绝对保证", "严格按照条款约定"),
    (r"百分之百报销", "依条款全额补偿"),
    (r"无条件给付", "依约定标准给付"),
]


def format_cents_to_display(cents: int | None) -> str:
    if cents is None:
        return "条款中未找到"
    if cents == 0:
        return "0 元 / 0 免赔"
    # 1 万元 = 10,000 元 = 1,000,000 分
    if cents >= 1000000 and cents % 1000000 == 0:
        return f"{cents // 1000000} 万元"
    if cents >= 1000000 and cents % 100000 == 0:
        return f"{cents / 1000000:.1f} 万元"
    if cents >= 100 and cents % 100 == 0:
        return f"{cents // 100} 元"
    return f"{cents / 100:.2f} 元"


def get_dimension_value_from_coverages(
    coverages: list[Coverage], dimension_key: str
) -> ComparisonCell:
    """
    Extracts structured comparison cell value for a given dimension
    from a product's coverages list.
    """
    if dimension_key == "death":
        covs = [c for c in coverages if c.kind in ("death", "disability")]
        if covs:
            max_limit = max([c.limit_cents or 0 for c in covs])
            return ComparisonCell(
                value=f"最高 {format_cents_to_display(max_limit)}",
                status="covered",
                quote=covs[0].name,
            )
        return ComparisonCell(value="条款中未找到", status="not_found")

    elif dimension_key == "accident_medical":
        covs = [c for c in coverages if c.kind in ("accident_medical", "medical")]
        if covs:
            max_limit = max([c.limit_cents or 0 for c in covs])
            return ComparisonCell(
                value=format_cents_to_display(max_limit),
                status="covered",
                quote=covs[0].name,
            )
        return ComparisonCell(value="条款中未找到", status="missing")

    elif dimension_key == "deductible":
        covs = [c for c in coverages if c.kind in ("accident_medical", "medical")]
        if covs and covs[0].deductible_cents is not None:
            val = format_cents_to_display(covs[0].deductible_cents)
            return ComparisonCell(value=val, status="covered")
        return ComparisonCell(value="0 元免赔", status="covered")

    elif dimension_key == "reimbursement_ratio":
        covs = [c for c in coverages if c.kind in ("accident_medical", "medical")]
        if covs and covs[0].ratio_with_si:
            with_si = f"社保后 {covs[0].ratio_with_si // 10}%"
            without_si = f"未经社保 {covs[0].ratio_without_si // 10}%" if covs[0].ratio_without_si else ""
            return ComparisonCell(
                value=f"{with_si} {without_si}".strip(),
                status="covered",
            )
        return ComparisonCell(value="条款中未找到", status="not_found")

    elif dimension_key == "sudden_death":
        covs = [c for c in coverages if c.kind == "sudden_death"]
        if covs:
            limit = covs[0].limit_cents
            return ComparisonCell(
                value=format_cents_to_display(limit),
                status="covered",
                quote=covs[0].name,
            )
        return ComparisonCell(value="不含猝死责任", status="missing")

    elif dimension_key == "transport_extra":
        covs = [c for c in coverages if c.kind == "transport_extra"]
        if covs:
            parts = [f"{c.name}: {format_cents_to_display(c.limit_cents)}" for c in covs[:2]]
            return ComparisonCell(
                value="; ".join(parts),
                status="covered",
            )
        return ComparisonCell(value="无额外给付", status="missing")

    elif dimension_key == "hospital_allowance":
        covs = [c for c in coverages if c.kind == "hospital_allowance"]
        if covs:
            limit = covs[0].limit_cents
            return ComparisonCell(
                value=f"{format_cents_to_display(limit)} / 天",
                status="covered",
            )
        return ComparisonCell(value="无津贴责任", status="missing")

    elif dimension_key == "exclusions":
        return ComparisonCell(
            value="高风险运动、高危职业、无证驾驶免责",
            status="covered",
        )

    return ComparisonCell(value="条款中未找到", status="not_found")


def build_comparison_matrix(
    baseline_policy: Policy,
    candidate_products_data: list[dict[str, Any]],
) -> ComparisonMatrix:
    """
    Aligns baseline policy and candidate products by dimensions strictly in code (Red Line 4).
    Produces a row-dimension, column-product matrix.
    """
    # Columns
    products: list[ProductColumn] = [
        ProductColumn(
            id="baseline",
            name=f"现有基线: {baseline_policy.product_name or '原保单'}",
            is_baseline=True,
            premium_text=format_cents_to_display(baseline_policy.premium_cents) + "/年" if baseline_policy.premium_cents else None,
        )
    ]

    for idx, cand in enumerate(candidate_products_data):
        products.append(
            ProductColumn(
                id=cand.get("id", f"cand_{idx}"),
                name=cand.get("product_name", f"候选方案 {idx+1}"),
                is_baseline=False,
                premium_text=cand.get("premium_text", "官方费率核算中"),
                url=cand.get("url"),
            )
        )

    rows: list[ComparisonRow] = []
    baseline_coverages = baseline_policy.coverages or []

    for dim_key, dim_label in ACCIDENT_DIMENSION_ORDER:
        baseline_cell = get_dimension_value_from_coverages(baseline_coverages, dim_key)
        candidate_cells: dict[str, ComparisonCell] = {}

        for idx, cand in enumerate(candidate_products_data):
            cand_id = cand.get("id", f"cand_{idx}")
            cand_coverages = cand.get("coverages", [])
            cand_cell = get_dimension_value_from_coverages(cand_coverages, dim_key)
            cand_cell.source_url = cand.get("url")
            candidate_cells[cand_id] = cand_cell

        rows.append(
            ComparisonRow(
                dimension_key=dim_key,
                dimension_label=dim_label,
                baseline_cell=baseline_cell,
                candidate_cells=candidate_cells,
            )
        )

    return ComparisonMatrix(products=products, rows=rows)


def verify_url_provenance(
    text: str, session_id: str, db: Session
) -> tuple[str, int]:
    """
    Checks all URLs present in the text against source_record for this session.
    Any sentence containing a URL not recorded in source_record is completely removed (Red Line 6).
    Returns (cleaned_text, removed_sentence_count).
    """
    if not text:
        return "", 0

    # Retrieve all verified URLs recorded for this session
    records = db.query(SourceRecord.url).filter(SourceRecord.session_id == session_id).all()
    valid_urls = {r[0].strip() for r in records}

    # Split into sentences while preserving separators
    sentence_pattern = re.compile(r"([^。！？\n]+[。！？\n]?)")
    raw_sentences = sentence_pattern.findall(text)
    if not raw_sentences:
        raw_sentences = [text]

    cleaned_sentences = []
    removed_count = 0
    url_regex = re.compile(r"https?://[^\s()\[\]{}<>'\"`“”‘’（）【】《》]+", re.IGNORECASE)

    for sentence in raw_sentences:
        urls = url_regex.findall(sentence)
        if not urls:
            cleaned_sentences.append(sentence)
            continue

        # Check if every URL in this sentence exists in source_record
        all_proven = True
        for u in urls:
            clean_u = u.rstrip(".,;:!?，。；：！？）)]}>\"'”’")
            if clean_u not in valid_urls:
                all_proven = False
                break

        if all_proven:
            cleaned_sentences.append(sentence)
        else:
            removed_count += 1

    return "".join(cleaned_sentences).strip(), removed_count


def filter_forbidden_phrases(text: str) -> tuple[str, list[str]]:
    """
    Substitutes marketing / compliance forbidden phrases with neutral wording
    (Red Line 8 & DEV-GUIDE 8.7). Returns (sanitized_text, hit_phrases).
    """
    if not text:
        return "", []

    hits: list[str] = []
    sanitized = text

    for pattern, replacement in FORBIDDEN_PHRASE_REPLACEMENTS:
        matches = re.findall(pattern, sanitized)
        if matches:
            hits.extend(matches)
            sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized, hits
