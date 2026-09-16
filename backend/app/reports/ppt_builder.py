from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
from sqlalchemy.orm import Session
from ulid import ULID

from app.db.models import Coverage, Member, Policy, PolicyParty
from app.settings import settings

# 16:9 Dimensions
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)

# Color Palette (DEV-GUIDE 7.3)
COLOR_POOL = RGBColor(0x14, 0x23, 0x3A)       # #14233A 深潭色 (主文本)
COLOR_CELADON = RGBColor(0x2A, 0x8F, 0x82)   # #2A8F82 青瓷色 (已核验/主强调)
COLOR_APRICOT = RGBColor(0xC9, 0x82, 0x17)   # #C98217 杏黄色 (待确认/提示)
COLOR_CINNABAR = RGBColor(0xC8, 0x44, 0x3B)  # #C8443B 朱砂色 (风险/缺口)
COLOR_PAPER = RGBColor(0xF7, 0xF5, 0xEF)     # #F7F5EF 浅米纸面
COLOR_WHITE = RGBColor(0xFF, 0xFF, 0xFF)     # #FFFFFF 白色
COLOR_MUTED = RGBColor(0x6B, 0x72, 0x80)     # #6B7280 辅助灰
COLOR_BORDER = RGBColor(0xE5, 0xE7, 0xEB)    # #E5E7EB 浅边框


def format_cents(cents: int | None) -> str:
    if cents is None or cents == 0:
        return "0"
    if cents >= 100000000 and cents % 1000000 == 0:
        return f"{cents // 1000000}万"
    if cents >= 1000000 and cents % 1000000 == 0:
        return f"{cents // 1000000}万"
    return f"{cents // 100}"


def add_bg(slide):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_WIDTH, SLIDE_HEIGHT)
    bg.fill.solid()
    bg.fill.fore_color.rgb = COLOR_PAPER
    bg.line.fill.background()
    return bg


def add_header(slide, title_text: str, subtitle_text: str = "保单簿 PolicyBook 全家保单检视报告"):
    tx_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.7), Inches(1.0))
    tf = tx_box.text_frame
    tf.word_wrap = True
    
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(22)
    p.font.bold = True
    p.font.color.rgb = COLOR_POOL
    
    p2 = tf.add_paragraph()
    p2.text = subtitle_text
    p2.font.size = Pt(11)
    p2.font.color.rgb = COLOR_MUTED


def build_family_ppt(
    db: Session,
    report_id: str | None = None,
    custom_summary: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    """
    Builds a 16:9 family insurance PPT report strictly following PRD 3.12 and DEV-GUIDE 8.9.
    All calculations are deterministic code (Red Line 4).
    Returns (output_file_path, numerical_snapshot_dict).
    """
    report_id = report_id or str(ULID())
    out_dir = settings.abs_data_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"family_report_{report_id}.pptx"

    prs = Presentation()
    prs.slide_width = SLIDE_WIDTH
    prs.slide_height = SLIDE_HEIGHT
    blank_layout = prs.slide_layouts[6]

    # Gather data from DB
    members = db.query(Member).all()
    policies = db.query(Policy).filter(Policy.status != "candidate").all()
    
    total_policies = len(policies)
    total_premium_cents = sum([p.premium_cents or 0 for p in policies])
    
    # Calculate death and CI coverages
    death_covs = db.query(Coverage).filter(Coverage.kind == "death").all()
    ci_covs = db.query(Coverage).filter(Coverage.kind == "critical_illness").all()
    medical_covs = db.query(Coverage).filter(Coverage.kind.in_(["medical", "accident_medical"])).all()

    total_death_cents = sum([c.limit_cents or 0 for c in death_covs])
    total_ci_cents = sum([c.limit_cents or 0 for c in ci_covs])
    max_medical_cents = max([c.limit_cents or 0 for c in medical_covs]) if medical_covs else 0

    snapshot = {
        "report_id": report_id,
        "total_policies": total_policies,
        "total_members": len(members),
        "total_premium_yuan": total_premium_cents // 100,
        "total_death_yuan": total_death_cents // 100,
        "total_ci_yuan": total_ci_cents // 100,
        "max_medical_yuan": max_medical_cents // 100,
        "member_counts": {},
        "member_premiums": {},
    }

    # -------------------------------------------------------------
    # SLIDE 1: 封面 (Cover)
    # -------------------------------------------------------------
    s1 = prs.slides.add_slide(blank_layout)
    add_bg(s1)

    # Accent decorative bar
    bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.8), Inches(0.15), Inches(3.2))
    bar.fill.solid()
    bar.fill.fore_color.rgb = COLOR_CELADON
    bar.line.fill.background()

    # Cover Title Box
    c_box = s1.shapes.add_textbox(Inches(1.2), Inches(1.8), Inches(10.5), Inches(3.2))
    ctf = c_box.text_frame
    ctf.word_wrap = True

    cp1 = ctf.paragraphs[0]
    cp1.text = "家庭保单全景档案与保障检视报告"
    cp1.font.size = Pt(32)
    cp1.font.bold = True
    cp1.font.color.rgb = COLOR_POOL

    cp2 = ctf.add_paragraph()
    cp2.text = "PolicyBook Family Insurance Portfolio & Comprehensive Review"
    cp2.font.size = Pt(14)
    cp2.font.color.rgb = COLOR_MUTED

    cp3 = ctf.add_paragraph()
    today_str = datetime.now(timezone.utc).strftime("%Y年%m月%d日")
    member_names = "、".join([m.display_name for m in members]) if members else "家庭全体成员"
    cp3.text = f"\n检视对象：{member_names}   |   归档保单数：{total_policies} 份   |   生成日期：{today_str}"
    cp3.font.size = Pt(13)
    cp3.font.color.rgb = COLOR_CELADON

    # -------------------------------------------------------------
    # SLIDE 2: 全家概览 (Family Overview)
    # -------------------------------------------------------------
    s2 = prs.slides.add_slide(blank_layout)
    add_bg(s2)
    add_header(s2, "全家保障核心指标总览", "基于当前已生效保单由纯代码确定性汇总计算")

    # 4 Indicator Cards
    cards_data = [
        ("保单持有总量", f"{total_policies}", "份有效保单", COLOR_POOL),
        ("年度保费支出", f"{total_premium_cents // 100:,}", "元 / 年", COLOR_APRICOT),
        ("家庭总身故保额", f"{total_death_cents // 1000000:,}", "万元最高给付", COLOR_CELADON),
        ("重大疾病保额", f"{total_ci_cents // 1000000:,}", "万元给付型", COLOR_CINNABAR),
    ]

    card_width = Inches(2.7)
    card_height = Inches(2.2)
    card_top = Inches(1.8)

    for i, (label, val, unit, color) in enumerate(cards_data):
        left = Inches(0.8) + i * Inches(2.95)
        # Card Background
        card_bg = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, card_top, card_width, card_height)
        card_bg.fill.solid()
        card_bg.fill.fore_color.rgb = COLOR_WHITE
        card_bg.line.color.rgb = COLOR_BORDER
        card_bg.line.width = Pt(1)

        # Content
        c_tf = card_bg.text_frame
        c_tf.word_wrap = True
        
        p1 = c_tf.paragraphs[0]
        p1.text = label
        p1.font.size = Pt(13)
        p1.font.color.rgb = COLOR_MUTED
        p1.alignment = PP_ALIGN.CENTER

        p2 = c_tf.add_paragraph()
        p2.text = f"\n{val}"
        p2.font.size = Pt(30)
        p2.font.bold = True
        p2.font.color.rgb = color
        p2.alignment = PP_ALIGN.CENTER

        p3 = c_tf.add_paragraph()
        p3.text = unit
        p3.font.size = Pt(11)
        p3.font.color.rgb = COLOR_MUTED
        p3.alignment = PP_ALIGN.CENTER

    # Summary commentary block (PRD: max 90 chars)
    commentary = custom_summary or (
        f"全家目前持有保单 {total_policies} 份，年缴保费共计 {total_premium_cents // 100} 元。"
        f"家庭身故保额达 {total_death_cents // 1000000} 万元，重大疾病保额达 {total_ci_cents // 1000000} 万元。"
        f"整体保障覆盖较健全，建议定期检视到期排期并关注免赔额与等待期。"
    )
    if len(commentary) > 90:
        commentary = commentary[:87] + "..."

    summary_box = s2.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(4.4), Inches(11.6), Inches(1.8))
    summary_box.fill.solid()
    summary_box.fill.fore_color.rgb = COLOR_WHITE
    summary_box.line.color.rgb = COLOR_CELADON
    summary_box.line.width = Pt(1.5)

    s_tf = summary_box.text_frame
    s_tf.word_wrap = True
    sp1 = s_tf.paragraphs[0]
    sp1.text = "顾问核心简评（系统生成）"
    sp1.font.size = Pt(12)
    sp1.font.bold = True
    sp1.font.color.rgb = COLOR_CELADON

    sp2 = s_tf.add_paragraph()
    sp2.text = f"\n{commentary}"
    sp2.font.size = Pt(13)
    sp2.font.color.rgb = COLOR_POOL

    # -------------------------------------------------------------
    # SLIDE 3..N: 成员专页 (Member Slides)
    # -------------------------------------------------------------
    for member in members:
        # Find policies for this member
        parties = db.query(PolicyParty).filter(PolicyParty.member_id == member.id).all()
        member_policy_ids = {p.policy_id for p in parties}
        member_policies = [p for p in policies if p.id in member_policy_ids]
        m_premium_cents = sum([p.premium_cents or 0 for p in member_policies])
        m_prem_yuan = m_premium_cents // 100

        snapshot["member_counts"][member.display_name] = len(member_policies)
        snapshot["member_premiums"][member.display_name] = m_prem_yuan

        s_m = prs.slides.add_slide(blank_layout)
        add_bg(s_m)
        add_header(
            s_m,
            f"家庭成员专页：{member.display_name} ({member.relation})",
            f"归档证件身份标记：{member.placeholder}   |   参保身份：{member.social_insurance or '未填写'}   |   年保费支出：{m_prem_yuan:,} 元",
        )

        # Member policy table
        rows_count = max(2, len(member_policies) + 1)
        table_shape = s_m.shapes.add_table(rows_count, 5, Inches(0.8), Inches(1.8), Inches(11.6), Inches(4.5))
        table = table_shape.table
        table.columns[0].width = Inches(3.2)
        table.columns[1].width = Inches(2.6)
        table.columns[2].width = Inches(1.8)
        table.columns[3].width = Inches(2.0)
        table.columns[4].width = Inches(2.0)

        # Header row
        headers = ["产品名称", "承保公司", "保障类型", "保费 (元/年)", "到期日"]
        for col_idx, h_text in enumerate(headers):
            cell = table.cell(0, col_idx)
            cell.text = h_text
            cell.fill.solid()
            cell.fill.fore_color.rgb = COLOR_POOL
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(11)
                p.font.bold = True
                p.font.color.rgb = COLOR_WHITE

        if not member_policies:
            cell = table.cell(1, 0)
            cell.text = "暂无独立归档保单"
        else:
            for row_idx, pol in enumerate(member_policies, start=1):
                p_cents = pol.premium_cents or 0
                exp = str(pol.expiry_date) if pol.expiry_date else "终身/长期"
                row_data = [
                    pol.product_name,
                    pol.insurer,
                    pol.category,
                    f"{p_cents // 100:,}",
                    exp,
                ]
                for col_idx, val_text in enumerate(row_data):
                    cell = table.cell(row_idx, col_idx)
                    cell.text = val_text
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = COLOR_WHITE
                    for p in cell.text_frame.paragraphs:
                        p.font.size = Pt(10)
                        p.font.color.rgb = COLOR_POOL

    # -------------------------------------------------------------
    # SLIDE Last-1: 待确认问题与顾问提醒 (Action Items)
    # -------------------------------------------------------------
    s_action = prs.slides.add_slide(blank_layout)
    add_bg(s_action)
    add_header(s_action, "保单管理待确认与跟进建议", "续保节点、就诊须知与资料保管要点")

    tips = [
        "1. 意外险按年到期续保提醒：意外险通常为 1 年期非保证续保，建议在保单到期前 30 天提前规划。",
        "2. 医疗险就诊医院等级要求：报销通常限定二级及以上公立医院普通部，急诊就近就医后请注意保留病历与首诊发票。",
        "3. 重疾险身故责任重叠排查：排查家庭成员多份保单是否存在相同重疾等待期或免责冲突，避免重复缴费。",
        "4. 银行扣款账户资金充足：年缴保单建议在扣款日前 7 天确认签约银行卡余额充足，享有 60 天宽限期保障。",
    ]

    for idx, tip in enumerate(tips):
        top_y = Inches(1.8) + idx * Inches(1.1)
        tip_box = s_action.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), top_y, Inches(11.6), Inches(0.9))
        tip_box.fill.solid()
        tip_box.fill.fore_color.rgb = COLOR_WHITE
        tip_box.line.color.rgb = COLOR_BORDER
        t_tf = tip_box.text_frame
        t_tf.word_wrap = True
        tp = t_tf.paragraphs[0]
        tp.text = tip
        tp.font.size = Pt(12)
        tp.font.color.rgb = COLOR_POOL

    # -------------------------------------------------------------
    # SLIDE Last: 免责说明 (Disclaimer)
    # -------------------------------------------------------------
    s_end = prs.slides.add_slide(blank_layout)
    add_bg(s_end)
    add_header(s_end, "法律声明与免责提示", "固定免责条款（Red Line 9）")

    disc_box = s_end.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.5), Inches(2.2), Inches(10.2), Inches(3.0))
    disc_box.fill.solid()
    disc_box.fill.fore_color.rgb = COLOR_WHITE
    disc_box.line.color.rgb = COLOR_CELADON
    disc_box.line.width = Pt(1.5)

    d_tf = disc_box.text_frame
    d_tf.word_wrap = True

    dp1 = d_tf.paragraphs[0]
    dp1.text = "【重要法律声明】"
    dp1.font.size = Pt(14)
    dp1.font.bold = True
    dp1.font.color.rgb = COLOR_CELADON
    dp1.alignment = PP_ALIGN.CENTER

    dp2 = d_tf.add_paragraph()
    dp2.text = (
        "\n保单簿根据你上传的合同文本整理信息，帮助你理解条款和估算大致范围。\n"
        "所有结论以保险公司的核定和合同原文为准，本工具不构成投保建议、核保意见或理赔承诺。\n\n"
        "本文件所有数字由确定性代码从数据库提取，不代表保险公司的最终赔付给付核定结果。"
    )
    dp2.font.size = Pt(13)
    dp2.font.color.rgb = COLOR_POOL
    dp2.alignment = PP_ALIGN.CENTER

    prs.save(str(out_file))
    return out_file, snapshot
