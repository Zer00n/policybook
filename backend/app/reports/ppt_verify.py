import re
from pathlib import Path
from typing import Any
from pptx import Presentation


def extract_all_text_from_ppt(ppt_path: Path) -> list[dict[str, Any]]:
    """
    Extracts all text and shape data from a PPT presentation,
    retaining slide index and shape hierarchy.
    """
    prs = Presentation(str(ppt_path))
    slides_data = []

    for slide_idx, slide in enumerate(prs.slides, start=1):
        slide_texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        slide_texts.append(text)
            elif shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        text = cell.text.strip()
                        if text:
                            slide_texts.append(text)

        slides_data.append({
            "slide_no": slide_idx,
            "texts": slide_texts,
            "full_text": " \n ".join(slide_texts),
        })

    return slides_data


def verify_ppt_numbers(
    ppt_path: Path,
    expected_snapshot: dict[str, Any],
) -> dict[str, Any]:
    """
    Re-reads PPT presentation and checks all numerical data against
    the database snapshot (DEV-GUIDE 8.9 & Red Line 4).
    Outputs mismatches list. If all match, mismatches is empty.
    """
    slides_data = extract_all_text_from_ppt(ppt_path)
    combined_ppt_text = " \n ".join([s["full_text"] for s in slides_data])

    mismatches = []
    checked_count = 0

    # 1. Total policies count
    checked_count += 1
    exp_policies = expected_snapshot.get("total_policies")
    if exp_policies is not None:
        patterns = [
            rf"保单数[：:]\s*{exp_policies}",
            rf"持有总量\s*\n*\s*{exp_policies}",
            rf"保单\s*{exp_policies}\s*份",
            rf"{exp_policies}\s*份有效保单",
        ]
        found = any(re.search(pat, combined_ppt_text) for pat in patterns)
        if not found:
            mismatches.append({
                "field": "total_policies",
                "expected": exp_policies,
                "detail": f"保单总数 {exp_policies} 未在 PPT 概览文本中找到匹配模式",
            })

    # 2. Total premium (yuan)
    checked_count += 1
    exp_premium = expected_snapshot.get("total_premium_yuan")
    if exp_premium is not None:
        # Check either formatted (12,800) or raw (12800)
        formatted = f"{exp_premium:,}"
        raw = str(exp_premium)
        if formatted not in combined_ppt_text and raw not in combined_ppt_text:
            mismatches.append({
                "field": "total_premium_yuan",
                "expected": exp_premium,
                "detail": f"年度保费支出 {exp_premium} (格式化: {formatted}) 未在 PPT 中找到",
            })

    # 3. Total death sum insured (wan yuan)
    checked_count += 1
    exp_death = expected_snapshot.get("total_death_yuan")
    if exp_death is not None:
        wan = exp_death // 10000
        formatted_wan = f"{wan:,}"
        if str(wan) not in combined_ppt_text and formatted_wan not in combined_ppt_text:
            mismatches.append({
                "field": "total_death_yuan",
                "expected": exp_death,
                "detail": f"身故总保额 {wan} 万元 未在 PPT 中找到",
            })

    # 4. Total critical illness sum insured (wan yuan)
    checked_count += 1
    exp_ci = expected_snapshot.get("total_ci_yuan")
    if exp_ci is not None:
        wan = exp_ci // 10000
        formatted_wan = f"{wan:,}"
        if str(wan) not in combined_ppt_text and formatted_wan not in combined_ppt_text:
            mismatches.append({
                "field": "total_ci_yuan",
                "expected": exp_ci,
                "detail": f"重疾总保额 {wan} 万元 未在 PPT 中找到",
            })

    # 5. Member premiums
    for m_name, m_prem in expected_snapshot.get("member_premiums", {}).items():
        checked_count += 1
        if m_prem > 0:
            formatted = f"{m_prem:,}"
            raw = str(m_prem)
            if formatted not in combined_ppt_text and raw not in combined_ppt_text:
                mismatches.append({
                    "field": f"member_premium_{m_name}",
                    "expected": m_prem,
                    "detail": f"成员 {m_name} 保费支出 {m_prem} 未在 PPT 成员专页中找到",
                })

    return {
        "ppt_path": str(ppt_path),
        "slides_count": len(slides_data),
        "total_checked": checked_count,
        "mismatches": mismatches,
        "verified": len(mismatches) == 0,
    }


def tamper_ppt_text(
    input_path: Path,
    output_path: Path,
    target_text: str,
    tampered_text: str,
) -> bool:
    """
    Intentionally replaces a text/number in the PPT presentation to test
    that the verifier catches mismatches accurately (DEV-GUIDE 10.9 acceptance test).
    """
    prs = Presentation(str(input_path))
    replaced = False

    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    if target_text in paragraph.text:
                        paragraph.text = paragraph.text.replace(target_text, tampered_text)
                        replaced = True
            elif shape.has_table:
                for row in shape.table.rows:
                    for cell in row.cells:
                        if target_text in cell.text:
                            cell.text = cell.text.replace(target_text, tampered_text)
                            replaced = True

    prs.save(str(output_path))
    return replaced
