from fastapi import APIRouter, HTTPException
from app.llm.manager import model_manager
from app.schemas.settings import ModelTestRequest, ModelTestResponse, SettingsSummaryResponse
from app.settings import settings

router = APIRouter(prefix="/settings", tags=["Settings"])


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
