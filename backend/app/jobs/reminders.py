import json
from datetime import datetime, date, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session

from app.db.models import Policy, Member, Reminder, PolicyParty


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


def generate_daily_reminders(db: Session, current_date: Optional[date] = None) -> List[Reminder]:
    today = current_date or date.today()
    created_reminders: List[Reminder] = []

    policies = db.query(Policy).all()

    for pol in policies:
        exp = parse_date(pol.expiry_date)
        eff = parse_date(pol.effective_date)
        
        # Find insured member
        insured_party = next((p for p in pol.parties if p.role == "insured"), None)
        member_id = insured_party.member_id if insured_party else None
        member_name = insured_party.member.display_name if (insured_party and insured_party.member) else "被保人"

        # 1. Expiry reminders (60d, 30d, 7d)
        if exp:
            days_until_exp = (exp - today).days
            
            # Check 7 days
            if 0 <= days_until_exp <= 7:
                kind = "expiring_7d"
                title = f"保单即将到期 (剩 {days_until_exp} 天)：{pol.product_name}"
                content = f"{member_name} 的 {pol.product_name} 将于 {format_date(exp)} 到期，仅剩 {days_until_exp} 天，请尽快完成续保避免脱保！"
                _upsert_reminder(db, pol.id, member_id, kind, format_date(exp), title, content, created_reminders)

            # Check 30 days
            elif 8 <= days_until_exp <= 30:
                kind = "expiring_30d"
                title = f"保单到期提醒 (剩 {days_until_exp} 天)：{pol.product_name}"
                content = f"{member_name} 的 {pol.product_name} 将于 {format_date(exp)} 到期，建议提前查看续保方案与健康告知要求。"
                _upsert_reminder(db, pol.id, member_id, kind, format_date(exp), title, content, created_reminders)

            # Check 60 days
            elif 31 <= days_until_exp <= 60:
                kind = "expiring_60d"
                title = f"保单 60 天内到期预警：{pol.product_name}"
                content = f"{member_name} 的 {pol.product_name} 将于 {format_date(exp)} 到期。"
                _upsert_reminder(db, pol.id, member_id, kind, format_date(exp), title, content, created_reminders)

        # 2. Waiting period end reminder
        if eff and pol.waiting_days and pol.waiting_days > 0:
            wait_end = eff + timedelta(days=pol.waiting_days)
            days_to_wait_end = (wait_end - today).days
            if -1 <= days_to_wait_end <= 1:
                kind = "waiting_end"
                title = f"保单等待期结束正式生效：{pol.product_name}"
                content = f"{member_name} 的 {pol.product_name} {pol.waiting_days} 天等待期已于 {format_date(wait_end)} 届满，所有保障责任即日起全面生效！"
                _upsert_reminder(db, pol.id, member_id, kind, format_date(wait_end), title, content, created_reminders)

        # 3. Annual payment due reminder
        if eff and pol.term_type == "long_term" and (pol.pay_mode or "").startswith("年"):
            try:
                # Due date in current year
                this_year_due = date(today.year, eff.month, eff.day)
            except ValueError:  # leap year Feb 29
                this_year_due = date(today.year, eff.month, eff.day - 1)

            days_to_pay = (this_year_due - today).days
            if 0 <= days_to_pay <= 30:
                kind = f"payment_due_{today.year}"
                prem_display = f"{pol.premium_cents / 100:.2f} 元" if pol.premium_cents else "保费"
                title = f"保单年缴续期提醒：{pol.product_name}"
                content = f"{member_name} 的 {pol.product_name} 应缴保费 {prem_display}，续期缴费日为 {format_date(this_year_due)}，请确保关联扣款账户余额充足。"
                _upsert_reminder(db, pol.id, member_id, kind, format_date(this_year_due), title, content, created_reminders)

    db.commit()
    return created_reminders


def _upsert_reminder(
    db: Session,
    policy_id: str,
    member_id: Optional[str],
    kind: str,
    due_date: str,
    title: str,
    content: str,
    created_reminders: List[Reminder]
):
    existing = db.query(Reminder).filter(
        Reminder.policy_id == policy_id,
        Reminder.kind == kind,
        Reminder.due_date == due_date
    ).first()

    if not existing:
        rem = Reminder(
            policy_id=policy_id,
            member_id=member_id,
            kind=kind,
            due_date=due_date,
            title=title,
            content=content,
            status="pending"
        )
        db.add(rem)
        created_reminders.append(rem)
