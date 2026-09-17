from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.health import router as health_router
from app.api.settings import router as settings_router
from app.api.members import router as members_router
from app.api.imports import router as imports_router
from app.api.documents import router as documents_router
from app.api.review import router as review_router
from app.api.policies import router as policies_router
from app.api.qa import router as qa_router
from app.api.claim import router as claim_router
from app.api.overview import router as overview_router
from app.api.coverage import router as coverage_router
from app.api.calendar import router as calendar_router
from app.api.renewal import router as renewal_router
from app.api.reports import router as reports_router
from app.api.eval import router as eval_router

from app.db.init_db import init_db
from app.jobs.queue import worker
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure data and models directories exist
    settings.abs_data_dir.mkdir(parents=True, exist_ok=True)
    settings.abs_models_dir.mkdir(parents=True, exist_ok=True)
    (settings.abs_data_dir / "llm_raw").mkdir(parents=True, exist_ok=True)
    init_db()
    import os
    import sys
    if not os.environ.get("PYTEST_CURRENT_TEST") and "pytest" not in sys.modules:
        worker.start()
        start_scheduler()
    yield
    worker.stop()
    stop_scheduler()



app = FastAPI(
    title="保单簿 PolicyBook API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Standard Error Format: {"error": {"code": "...", "message": "..."}}
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "details": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
            }
        },
    )


# Mount routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(members_router, prefix="/api")
app.include_router(imports_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(review_router, prefix="/api")
app.include_router(policies_router, prefix="/api")
app.include_router(qa_router, prefix="/api")
app.include_router(claim_router, prefix="/api")
app.include_router(overview_router, prefix="/api")
app.include_router(coverage_router, prefix="/api")
app.include_router(calendar_router)
app.include_router(renewal_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(eval_router, prefix="/api")

# Serve frontend static assets if available (Docker /app/static or frontend/dist)
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

static_candidates = [
    Path("/app/static"),
    settings.project_root / "frontend" / "dist",
]
static_dir = next((p for p in static_candidates if p.exists() and (p / "index.html").exists()), None)

if static_dir:
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    fonts_dir = static_dir / "fonts"
    if fonts_dir.exists():
        app.mount("/fonts", StaticFiles(directory=str(fonts_dir)), name="fonts")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("calendar/"):
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        target_file = static_dir / full_path
        if target_file.is_file():
            return FileResponse(target_file)
        return FileResponse(static_dir / "index.html")



