import secrets
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from icalendar import Calendar, Event

from app.db.session import get_db
from app.db.models import Policy, Member, Reminder, AppSetting, PolicyParty
from app.schemas.calendar import (
    ReminderDto,
    CalendarSettingsResponse,
    ResetTokenResponse,
)
from app.jobs.reminders import generate_daily_reminders

router = APIRouter(tags=["Calendar"])


def get_or_create_calendar_token(db: Session) -> str:
    setting = db.query(AppSetting).filter(AppSetting.key == "calendar_token").first()
    if not setting or not setting.value:
        token = secrets.token_urlsafe(24)
        if not setting:
            setting = AppSetting(key="calendar_token", value=token)
            db.add(setting)
        else:
            setting.value = token
        db.commit()
    return setting.value


def parse_date(d_str: Optional[str]) -> Optional[date]:
    if not d_str:
        return None
    try:
        clean = d_str.strip().split("T")[0]
        return datetime.strptime(clean, "%Y-%m-%d").date()
    except Exception:
        return None


@router.get("/calendar/{token}.ics")
@router.get("/api/calendar/{token}.ics")
def get_calendar_ics(token: str, db: Session = Depends(get_db)):
    """
    Public endpoint protected by unique random token (Red Line 11).
    Outputs RFC 5545 iCalendar stream for iPhone/Android/Outlook calendar sync.
    """
    valid_token = get_or_create_calendar_token(db)
    if not token or token != valid_token:
        raise HTTPException(status_code=404, detail="Invalid calendar subscription token")

    # Refresh reminders before export
    generate_daily_reminders(db)

    cal = Calendar()
    cal.add("prodid", "-//PolicyBook//CN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "保单簿 - 家庭保单日历")
    cal.add("x-wr-caldesc", "保单到期提醒、等待期届满与续期缴费日程")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    policies = db.query(Policy).all()

    for pol in policies:
        exp = parse_date(pol.expiry_date)
        eff = parse_date(pol.effective_date)
        
        insured_party = next((p for p in pol.parties if p.role == "insured"), None)
        member_name = insured_party.member.display_name if (insured_party and insured_party.member) else "被保人"

        # 1. Expiry event
        if exp:
            ev = Event()
            ev.add("summary", f"【保单到期】{member_name} - {pol.product_name}")
            ev.add("dtstart", exp)
            ev.add("dtend", exp + timedelta(days=1))
            ev.add("uid", f"pol-exp-{pol.id}@policybook")
            ev.add("description", f"承保公司：{pol.insurer}\n被保险人：{member_name}\n保单到期日：{pol.expiry_date}\n请提前确认续保方案。")
            cal.add_component(ev)

        # 2. Waiting period end
        if eff and pol.waiting_days and pol.waiting_days > 0:
            wait_end = eff + timedelta(days=pol.waiting_days)
            ev = Event()
            ev.add("summary", f"【等待期届满】{member_name} - {pol.product_name}")
            ev.add("dtstart", wait_end)
            ev.add("dtend", wait_end + timedelta(days=1))
            ev.add("uid", f"pol-wait-{pol.id}@policybook")
            ev.add("description", f"承保公司：{pol.insurer}\n被保险人：{member_name}\n{pol.waiting_days}天等待期今日届满，所有保障责任正式生效。")
            cal.add_component(ev)

        # 3. Annual payment due
        if eff and pol.term_type == "long_term" and (pol.pay_mode or "").startswith("年"):
            today = date.today()
            for yr in range(today.year - 1, today.year + 3):
                try:
                    pay_date = date(yr, eff.month, eff.day)
                except ValueError:
                    pay_date = date(yr, eff.month, eff.day - 1)
                
                ev = Event()
                ev.add("summary", f"【续期缴费】{member_name} - {pol.product_name}")
                ev.add("dtstart", pay_date)
                ev.add("dtend", pay_date + timedelta(days=1))
                ev.add("uid", f"pol-pay-{pol.id}-{yr}@policybook")
                prem = f"{pol.premium_cents / 100:.2f}元" if pol.premium_cents else "详见合同"
                ev.add("description", f"承保公司：{pol.insurer}\n应缴保费：{prem}\n缴费日：{pay_date}\n请确保银行扣款账户资金充足。")
                cal.add_component(ev)

    ics_bytes = cal.to_ical()
    return Response(
        content=ics_bytes,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=\"policybook.ics\"",
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )


@router.get("/api/reminders", response_model=List[ReminderDto])
def list_reminders(status: Optional[str] = None, db: Session = Depends(get_db)):
    # Refresh reminders
    generate_daily_reminders(db)

    query = db.query(Reminder)
    if status:
        query = query.filter(Reminder.status == status)
    reminders = query.order_by(Reminder.due_date.asc(), Reminder.created_at.desc()).all()

    result = []
    for r in reminders:
        m_name = r.member.display_name if r.member else None
        p_name = r.policy.product_name if r.policy else None
        result.append(
            ReminderDto(
                id=r.id,
                policy_id=r.policy_id,
                member_id=r.member_id,
                member_name=m_name,
                product_name=p_name,
                kind=r.kind,
                due_date=r.due_date,
                title=r.title,
                content=r.content,
                status=r.status,
                created_at=r.created_at.isoformat() if r.created_at else ""
            )
        )
    return result


@router.patch("/api/reminders/{reminder_id}/dismiss")
def dismiss_reminder(reminder_id: str, db: Session = Depends(get_db)):
    rem = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not rem:
        raise HTTPException(status_code=404, detail="Reminder not found")
    rem.status = "dismissed"
    db.commit()
    return {"ok": True, "id": reminder_id, "status": "dismissed"}
