import json
import secrets
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import AppSetting
from app.llm.manager import model_manager
from app.schemas.settings import ModelTestRequest, ModelTestResponse, SettingsSummaryResponse
from app.schemas.calendar import (
    CalendarSettingsResponse,
    ResetTokenResponse,
    ReferenceConfigRequest,
    ReferenceConfigResponse,
)
from app.settings import settings
from app.coverage.calculator import DEFAULT_REFERENCES

router = APIRouter(prefix="/settings", tags=["Settings"])


def _get_or_create_token(db: Session) -> str:
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


@router.get("", response_model=SettingsSummaryResponse)
def get_settings_summary():
    return SettingsSummaryResponse(
        app_host=settings.app_host,
        app_port=settings.app_port,
        data_dir=str(settings.data_dir),
        eval_mode=settings.eval_mode,
        models=model_manager.get_models_info(),
        ark_configured=bool(settings.ark_api_key),
    )


@router.post("/models/test", response_model=ModelTestResponse)
async def test_model(req: ModelTestRequest | None = None):
    model_key = req.model_key if req else None
    try:
        provider = model_manager.get_provider(model_key)
        res = await provider.test_connection()
        return ModelTestResponse(
            ok=res.get("ok", False),
            model_id=res.get("model_id", ""),
            display_name=res.get("display_name", ""),
            latency_ms=res.get("latency_ms", 0),
            reply=res.get("reply"),
            error=res.get("error"),
            usage=res.get("usage", {}),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/calendar", response_model=CalendarSettingsResponse)
def get_calendar_settings(db: Session = Depends(get_db)):
    token = _get_or_create_token(db)
    ics_url = f"/api/calendar/{token}.ics"
    return CalendarSettingsResponse(
        token=token,
        ics_url=ics_url,
        enabled=True
    )


@router.post("/calendar/reset-token", response_model=ResetTokenResponse)
def reset_calendar_token(db: Session = Depends(get_db)):
    new_token = secrets.token_urlsafe(24)
    setting = db.query(AppSetting).filter(AppSetting.key == "calendar_token").first()
    if not setting:
        setting = AppSetting(key="calendar_token", value=new_token)
        db.add(setting)
    else:
        setting.value = new_token
    db.commit()

    return ResetTokenResponse(
        token=new_token,
        ics_url=f"/api/calendar/{new_token}.ics"
    )


@router.get("/coverage-reference", response_model=ReferenceConfigResponse)
def get_coverage_references(db: Session = Depends(get_db)):
    setting = db.query(AppSetting).filter(AppSetting.key == "coverage_references").first()
    if setting and setting.value:
        try:
            data = json.loads(setting.value)
            return ReferenceConfigResponse(references=data)
        except Exception:
            pass
    return ReferenceConfigResponse(references={"default": DEFAULT_REFERENCES})


@router.put("/coverage-reference", response_model=ReferenceConfigResponse)
def update_coverage_references(req: ReferenceConfigRequest, db: Session = Depends(get_db)):
    setting = db.query(AppSetting).filter(AppSetting.key == "coverage_references").first()
    current_data = {}
    if setting and setting.value:
        try:
            current_data = json.loads(setting.value)
        except Exception:
            current_data = {}

    current_data[req.member_id] = req.references

    val_json = json.dumps(current_data, ensure_ascii=False)
    if not setting:
        setting = AppSetting(key="coverage_references", value=val_json)
        db.add(setting)
    else:
        setting.value = val_json
    db.commit()

    return ReferenceConfigResponse(references=current_data)
