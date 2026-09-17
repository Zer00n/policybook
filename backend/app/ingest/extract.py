import json
from pathlib import Path
from typing import Any
from jinja2 import Template
from sqlalchemy.orm import Session

from app.db.models import Document, Job, Page
from app.llm.base import TextItem
from app.llm.manager import model_manager
from app.schemas.extract import (
    CoverageExtraction,
    PageTypes,
    PolicyExtraction,
)
from app.settings import settings
from app.utils.verify import verify_quote


PROMPTS_DIR = settings.project_root / "backend" / "app" / "llm" / "prompts"


def _read_prompt_template(filename: str) -> Template:
    p = PROMPTS_DIR / filename
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    return Template(content)


async def run_document_extraction(
    db: Session,
    document_id: str,
    job: Job,
    on_step_callback=None,
    on_log_callback=None,
) -> dict[str, Any]:
    """
    执行 PRD 3.3 步骤 5-10：
    步骤 5: 文档页面分类 (classify_pages)
    步骤 6: 字段抽取 (extract_policy)
    步骤 7: 责任项与免责抽取 (extract_coverages)
    步骤 8: 引用精确子串校验与坐标回算
    步骤 9: 数值一致性校验与冲突判定
    步骤 10: 组装核对草稿并标记 review_ready
    """
    async def emit_log(msg: str, level: str = "info"):
        if on_log_callback:
            await on_log_callback(msg, level)

    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    pages = db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_no.asc()).all()
    if not pages:
        raise ValueError(f"No pages found for document {document_id}")

    pages_text: dict[int, str] = {}
    char_maps: dict[int, list] = {}
    pages_meta = []

    for p in pages:
        txt = p.text_masked or ""
        pages_text[p.page_no] = txt

        cmap = []
        if p.char_map_path and Path(p.char_map_path).exists():
            try:
                with open(p.char_map_path, "r", encoding="utf-8") as f:
                    raw_cmap = json.load(f)
                    cmap = raw_cmap.get("chars", raw_cmap) if isinstance(raw_cmap, dict) else raw_cmap
            except Exception:
                cmap = []
        char_maps[p.page_no] = cmap

        pages_meta.append({
            "page_no": p.page_no,
            "width": p.width,
            "height": p.height,
            "image_url": f"/api/documents/{document_id}/pages/{p.page_no}/image?masked=0",
            "masked_image_url": f"/api/documents/{document_id}/pages/{p.page_no}/image?masked=1",
        })

    provider = model_manager.get_provider()

    # ==================== 步骤 5: 文档分类 ====================
    if on_step_callback:
        await on_step_callback("classify", 0.86)
    await emit_log(f"提交 {len(pages)} 页脱敏页面摘要至火山方舟大模型执行页面分类...")

    classify_tmpl = _read_prompt_template("classify_pages.md")
    pages_summary_lines = []
    for pno, ptxt in pages_text.items():
        snippet = ptxt[:300].replace("\n", " ")
        pages_summary_lines.append(f"--- 第 {pno} 页 ---\n{snippet}")
    pages_summary_str = "\n".join(pages_summary_lines)

    classify_prompt = classify_tmpl.render(pages_summary=pages_summary_str)
    try:
        classify_res = await provider.respond(
            task_kind="classify_pages",
            instructions="你是一个资深的保险核保与保单分类助手。请严格输出结构化 JSON。",
            inputs=[TextItem(classify_prompt)],
            output_schema=PageTypes,
        )
        page_types_obj: PageTypes = classify_res.parsed or PageTypes()
        await emit_log(
            f"页面分类完成：识别出主险合同 {len(page_types_obj.policy_pages)} 页，"
            f"保险责任条款 {len(page_types_obj.liability_pages)} 页，"
            f"免责条款 {len(page_types_obj.exclusion_pages)} 页"
        )
    except Exception as e:
        page_types_obj = PageTypes()
        await emit_log(f"页面分类提示：分类模型调用异常 ({e})，使用全页备选策略", level="warn")

    # ==================== 步骤 6: 字段抽取 ====================
    if on_step_callback:
        await on_step_callback("extract_policy", 0.90)
    await emit_log("调用火山方舟大模型抽取保单核心基本信息（险种、投保人、被保人、保费保额、起止日期）...")

    policy_tmpl = _read_prompt_template("extract_policy.md")
    # 组装保单文本（限制适量长度）
    policy_pages_content = []
    for pno, ptxt in pages_text.items():
        policy_pages_content.append(f"=== 第 {pno} 页 ===\n{ptxt}")
    policy_content_str = "\n\n".join(policy_pages_content)

    policy_prompt = policy_tmpl.render(pages_content=policy_content_str)
    try:
        policy_res = await provider.respond(
            task_kind="extract_policy",
            instructions="你是一个保险条款深度结构化抽取助手。所有 quote 必须严格逐字从原文复制。输出符合要求的 JSON。",
            inputs=[TextItem(policy_prompt)],
            output_schema=PolicyExtraction,
        )
        policy_data: PolicyExtraction = policy_res.parsed or PolicyExtraction()
        p_name = policy_data.product_name.value if policy_data.product_name else "未知险种"
        p_ins = policy_data.insurer.value if policy_data.insurer else "未知保司"
        p_si = policy_data.sum_insured.value if policy_data.sum_insured else "未标明"
        await emit_log(f"基本信息抽取完成：{p_ins}《{p_name}》，基本保额: {p_si}")
    except Exception as e:
        policy_data = PolicyExtraction()
        await emit_log(f"基本信息抽取提示：模型抽取异常 ({e})", level="warn")

    # ==================== 步骤 7: 责任项抽取 ====================
    if on_step_callback:
        await on_step_callback("extract_coverages", 0.94)
    await emit_log("调用火山方舟大模型抽取保障责任清单、赔付比例与免责条款...")

    cov_tmpl = _read_prompt_template("extract_coverages.md")
    cov_prompt = cov_tmpl.render(pages_content=policy_content_str)
    try:
        cov_res = await provider.respond(
            task_kind="extract_coverages",
            instructions="你是一个保险保障责任与免责条款抽取助手。所有 quote 必须严格逐字从原文复制。输出符合要求的 JSON。",
            inputs=[TextItem(cov_prompt)],
            output_schema=CoverageExtraction,
        )
        cov_data: CoverageExtraction = cov_res.parsed or CoverageExtraction()
        await emit_log(f"责任与免责条款抽取完成：共提取 {len(cov_data.coverages)} 项保障责任，{len(cov_data.exclusions)} 条责任免除")
    except Exception as e:
        cov_data = CoverageExtraction()
        await emit_log(f"责任与免责条款抽取提示：模型抽取异常 ({e})", level="warn")

    # ==================== 步骤 8 & 9: 引用精确校验与数值核对 ====================
    if on_step_callback:
        await on_step_callback("verify", 0.98)
    await emit_log("执行引用精确子串校验、原文坐标回算与数值一致性判定...")

    review_fields = {}
    conflict_count = 0
    verified_count = 0
    unverified_count = 0
    not_found_count = 0

    def verify_field_item(field_key: str, label: str, field_val):
        nonlocal conflict_count, verified_count, unverified_count, not_found_count
        val = field_val.value if field_val else None
        ev = field_val.evidence if field_val else None

        if ev and ev.quote:
            v_res = verify_quote(
                pages_text=pages_text,
                target_page=ev.page,
                quote=ev.quote,
                field_name=field_key,
                model_value=val,
                char_maps=char_maps,
            )
            st = v_res.status
            rects = v_res.rects
            pno = v_res.page_no
            reason = v_res.conflict_reason
            quote = v_res.quote
        else:
            st = "unverified" if val else "not_found"
            rects = []
            pno = 1
            reason = None
            quote = None

        if st == "verified":
            verified_count += 1
        elif st == "conflict":
            conflict_count += 1
        elif st == "not_found":
            not_found_count += 1
        else:
            unverified_count += 1

        return {
            "key": field_key,
            "label": label,
            "value": val,
            "original_model_value": val,
            "quote": quote,
            "page_no": pno,
            "status": st,
            "rects": rects,
            "conflict_reason": reason,
            "is_human_modified": False,
        }

    # 抽取基本字段
    field_defs = [
        ("insurer", "保险公司", policy_data.insurer),
        ("product_name", "产品名称", policy_data.product_name),
        ("subcategory", "险种细类", policy_data.subcategory),
        ("sum_insured", "基本保额", policy_data.sum_insured),
        ("premium", "首期/年交保费", policy_data.premium),
        ("pay_mode", "交费方式", policy_data.pay_mode),
        ("pay_years", "交费期间", policy_data.pay_years),
        ("apply_date", "投保日期", policy_data.apply_date),
        ("effective_date", "生效日期", policy_data.effective_date),
        ("expiry_date", "保险期间届满日", policy_data.expiry_date),
        ("cooling_days", "犹豫期", policy_data.cooling_days),
        ("waiting_days", "等待期", policy_data.waiting_days),
        ("guaranteed_renewal", "保证续保", policy_data.guaranteed_renewal),
    ]

    for fkey, flabel, fval in field_defs:
        review_fields[fkey] = verify_field_item(fkey, flabel, fval)

    # 关系人信息
    parties = {
        "applicant": verify_field_item("applicant", "投保人", policy_data.applicant),
        "insureds": [
            verify_field_item(f"insured_{idx+1}", f"被保险人{idx+1}", item)
            for idx, item in enumerate(policy_data.insureds)
        ],
        "beneficiaries": [
            verify_field_item(f"beneficiary_{idx+1}", f"受益人{idx+1}", item)
            for idx, item in enumerate(policy_data.beneficiaries)
        ],
    }

    # 责任项校验
    review_coverages = []
    for c_idx, cov in enumerate(cov_data.coverages):
        limit_v = verify_field_item(f"cov_{c_idx}_limit", "保额/限额", cov.limit)
        deduct_v = verify_field_item(f"cov_{c_idx}_deductible", "免赔额", cov.deductible)
        ratio_si_v = verify_field_item(f"cov_{c_idx}_ratio_with_si", "经社保比例", cov.ratio_with_si)
        ratio_no_si_v = verify_field_item(f"cov_{c_idx}_ratio_without_si", "未经社保比例", cov.ratio_without_si)

        # 责任适用条件证据
        cond_evidences = []
        for cond in cov.conditions:
            if cond.quote:
                cond_res = verify_quote(
                    pages_text=pages_text,
                    target_page=cond.page,
                    quote=cond.quote,
                    char_maps=char_maps,
                )
                cond_evidences.append({
                    "quote": cond_res.quote,
                    "page_no": cond_res.page_no,
                    "status": cond_res.status,
                    "rects": cond_res.rects,
                })

        review_coverages.append({
            "id": f"cov_{c_idx+1}",
            "name": cov.name,
            "kind": cov.kind,
            "limit": limit_v,
            "deductible": deduct_v,
            "deductible_scope": cov.deductible_scope,
            "ratio_with_si": ratio_si_v,
            "ratio_without_si": ratio_no_si_v,
            "conditions": cond_evidences,
            "is_rider": cov.is_rider,
        })

    # 免责条款校验
    review_exclusions = []
    for e_idx, excl in enumerate(cov_data.exclusions):
        ex_res = verify_quote(
            pages_text=pages_text,
            target_page=excl.evidence.page,
            quote=excl.evidence.quote,
            char_maps=char_maps,
        )
        review_exclusions.append({
            "id": f"excl_{e_idx+1}",
            "quote": ex_res.quote,
            "page_no": ex_res.page_no,
            "status": ex_res.status,
            "rects": ex_res.rects,
            "plain_explanation": excl.plain_explanation,
        })

    # 汇总审核数据
    review_draft = {
        "document_id": document_id,
        "document_name": doc.original_name,
        "category": policy_data.category,
        "term_type": policy_data.term_type.value or "long_term",
        "pages": pages_meta,
        "fields": review_fields,
        "parties": parties,
        "coverages": review_coverages,
        "exclusions": review_exclusions,
        "summary": {
            "total_fields": len(review_fields),
            "verified_count": verified_count,
            "unverified_count": unverified_count,
            "not_found_count": not_found_count,
            "conflict_count": conflict_count,
        },
    }

    await emit_log(
        f"核验完成：已核验 {verified_count} 项，待确认 {unverified_count} 项，"
        f"未找到依据 {not_found_count} 项，冲突 {conflict_count} 项"
    )
    await emit_log("核对草稿已组装就绪，可以前往核对入库！", level="success")

    return review_draft
