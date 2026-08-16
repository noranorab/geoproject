import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from wildfirewatch.api.routers import detections, scenes
from wildfirewatch.observability import configure_logging, get_logger

configure_logging()
log = get_logger(__name__)

app = FastAPI(title="WildfireWatch API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    log.info(
        "request_handled",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round((time.perf_counter() - started) * 1000, 2),
    )
    return response


Instrumentator().instrument(app).expose(app)

app.include_router(scenes.router)
app.include_router(detections.router)


@app.get("/health")
def health():
    return {"status": "ok"}
