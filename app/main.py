"""Tasveer — application entrypoint.

Wires the routers, security headers, rate limiting, static UI and media
serving. Run with: uvicorn app.main:app --reload
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from app import __version__
from app.config import settings
from app.database import init_db
from app.engine import ASPECT_RATIOS, STYLES
from app.routers import auth, gallery, generations
from app.schemas import HealthOut, StyleOut, valid_aspects
from app.services.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title=f"{settings.app_name} API",
    description=(
        "A Midjourney-style image generation service. Prompt in, a grid of "
        "images out — with styles, seeds, reproducible results and a public gallery."
    ),
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- Rate limiting ---
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests. Slow down and try again shortly."},
        headers={"Retry-After": "60"},
    )


# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# --- Security headers ---
@app.middleware("http")
async def security_headers(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"

    if settings.is_production:
        # Only send HSTS over HTTPS in production; in dev it breaks plain http.
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# --- Routes ---
app.include_router(auth.router)
app.include_router(generations.router)
app.include_router(gallery.router)


@app.get("/api/health", response_model=HealthOut, tags=["meta"])
def health() -> HealthOut:
    return HealthOut(
        status="ok",
        version=__version__,
        environment=settings.environment,
        provider=settings.image_provider,
        styles=len(STYLES),
        aspect_ratios=valid_aspects(),
    )


@app.get("/api/styles", response_model=list[StyleOut], tags=["meta"])
def styles() -> list[StyleOut]:
    """Every style preset the renderer understands."""
    return [StyleOut(key=s.key, label=s.label, palette=list(s.palette)) for s in STYLES.values()]


@app.get("/api/aspect-ratios", tags=["meta"])
def aspect_ratios() -> dict:
    return {"ratios": [{"key": k, "width": w, "height": h} for k, (w, h) in ASPECT_RATIOS.items()]}


# --- Static UI and generated media ---
app.mount("/media", StaticFiles(directory=settings.storage_dir), name="media")

static_dir = settings.static_dir
static_dir.mkdir(parents=True, exist_ok=True)


@app.get("/", include_in_schema=False)
def index():
    index_file = static_dir / "index.html"
    if not index_file.exists():
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "UI not built. See docs/setup.md."},
        )
    return FileResponse(index_file)


app.mount("/static", StaticFiles(directory=static_dir), name="static")
