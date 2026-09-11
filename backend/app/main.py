import logging
import sys
import time

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import PlainTextResponse

from app.config import assert_safe_settings, settings
from app.routers import auth, public, verify

assert_safe_settings()


def setup_logging():
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )


setup_logging()
log = structlog.get_logger()

REQUEST_COUNT = Counter("odr_requests_total", "Total requests", ["method", "path", "status"])
REQUEST_DURATION = Histogram("odr_request_duration_seconds", "Request duration", ["method", "path"])

app = FastAPI(title=settings.app_name, version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    if request.url.path.startswith("/api"):
        REQUEST_COUNT.labels(request.method, request.url.path, response.status_code).inc()
        REQUEST_DURATION.labels(request.method, request.url.path).observe(duration)
    log.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration * 1000, 1),
        ip=request.client.host if request.client else None,
    )
    return response


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(), media_type="text/plain")


@app.get("/api/v1/healthz")
async def healthz():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(public.router)
app.include_router(verify.router)
