import asyncio
from datetime import datetime, timezone
import json
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession, Policy, PolicyParty
from app.db.session import get_db
from app.renewal.config import config_loader
from app.renewal.state_machine import RenewalStateMachine
from app.schemas.renewal import (
    ChatMessageDto,
    CreateRenewalSessionRequest,
    RenewalMessageRequest,
    RenewalQuestion,
    RenewalReport,
    RenewalSessionResponse,
)

router = APIRouter(prefix="/renewal", tags=["renewal"])


def _format_session_response(session: ChatSession, db: Session) -> RenewalSessionResponse:
    policy = db.query(Policy).filter(Policy.id == session.policy_id).first()
    insured_name = None
    if policy:
        party = db.query(PolicyParty).filter(PolicyParty.policy_id == policy.id, PolicyParty.role == "insured").first()
        if party and party.member:
            insured_name = party.member.display_name

    # Parse profile
    profile_data = json.loads(session.profile_json or "{}")

    # Messages
    msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.asc()).all()
    msg_dtos = [
        ChatMessageDto(
            id=m.id,
            role=m.role,  # type: ignore
            content=m.content,
            structured_json=m.structured_json,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in msgs
    ]

    # Current questions (if last message had structured questions)
    current_questions: list[RenewalQuestion] = []
    report: RenewalReport | None = None

    for m in reversed(msgs):
        if m.role == "assistant" and m.structured_json:
            try:
                parsed = json.loads(m.structured_json)
                if isinstance(parsed, list) and not current_questions:
                    current_questions = [RenewalQuestion(**q) for q in parsed]
                elif isinstance(parsed, dict) and "comparison_matrix" in parsed and not report:
                    report = RenewalReport(**parsed)
            except Exception:
                pass

    return RenewalSessionResponse(
        id=session.id,
        kind=session.kind,
        policy_id=session.policy_id,
        policy_name=policy.product_name if policy else None,
        insured_name=insured_name,
        state=session.state,
        profile=profile_data,
        current_questions=current_questions if session.state == "ASK_USER" else [],
        report=report,
        messages=msg_dtos,
        created_at=session.created_at.isoformat() if session.created_at else "",
        updated_at=session.updated_at.isoformat() if session.updated_at else "",
    )


@router.post("/sessions", response_model=RenewalSessionResponse)
async def create_renewal_session(
    req: CreateRenewalSessionRequest,
    db: Session = Depends(get_db),
):
    policy = db.query(Policy).filter(Policy.id == req.policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="基线保单未找到")

    session = ChatSession(
        kind="renewal",
        policy_id=policy.id,
        state="START",
        profile_json="{}",
        scope_json="{}",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Initialize state machine (START -> LOAD_BASELINE -> COLLECT_NEEDS)
    sm = RenewalStateMachine(session, db)
    await sm.initialize()

    return _format_session_response(session, db)


@router.get("/sessions", response_model=list[RenewalSessionResponse])
def list_renewal_sessions(db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.kind == "renewal").order_by(ChatSession.created_at.desc()).all()
    return [_format_session_response(s, db) for s in sessions]


@router.get("/sessions/{session_id}", response_model=RenewalSessionResponse)
def get_renewal_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="续保会话不存在")
    return _format_session_response(session, db)


@router.post("/sessions/{session_id}/messages")
async def send_renewal_message(
    session_id: str,
    req: RenewalMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="续保会话不存在")

    accept_header = request.headers.get("accept", "")
    wants_sse = "text/event-stream" in accept_header or request.query_params.get("stream") == "1"

    sm = RenewalStateMachine(session, db)

    if wants_sse:
        async def event_generator() -> AsyncGenerator[str, None]:
            yield f"event: step\ndata: {json.dumps({'step': session.state, 'progress': 0.2}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.05)

            # Process state machine step
            turn_res = await sm.process_user_turn(
                user_text=req.content,
                answers=req.answers,
                skip=req.skip,
            )

            current_state = turn_res.get("state", session.state)
            yield f"event: step\ndata: {json.dumps({'step': current_state, 'progress': 0.8}, ensure_ascii=False)}\n\n"

            # Stream message token
            content = turn_res.get("content", "")
            if content:
                yield f"event: token\ndata: {json.dumps({'text': content}, ensure_ascii=False)}\n\n"

            # Result event
            session_resp = _format_session_response(session, db)
            yield f"event: result\ndata: {json.dumps(session_resp.model_dump(), ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        # Standard JSON response
        await sm.process_user_turn(
            user_text=req.content,
            answers=req.answers,
            skip=req.skip,
        )
        return _format_session_response(session, db)


@router.get("/sessions/{session_id}/report", response_model=RenewalReport)
def get_renewal_report(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="续保会话不存在")

    msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at.desc()).all()
    for m in msgs:
        if m.role == "assistant" and m.structured_json:
            try:
                parsed = json.loads(m.structured_json)
                if isinstance(parsed, dict) and "comparison_matrix" in parsed:
                    return RenewalReport(**parsed)
            except Exception:
                pass

    raise HTTPException(status_code=404, detail="尚未生成续保对比报告")
