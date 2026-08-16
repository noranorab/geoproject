"""Structured logging + Prometheus metrics, shared by the API and the wfw CLI.

The API is a long-running process scraped directly by Prometheus (see
api/main.py). `wfw ingest`/`wfw process` are short-lived batch jobs instead, so
they push their metrics to a Pushgateway on exit rather than being scraped.
"""

from __future__ import annotations

import logging
import sys

import structlog
from prometheus_client import CollectorRegistry, Counter, Histogram, push_to_gateway

from wildfirewatch.config import get_settings

_logging_configured = False


def configure_logging() -> None:
    """Idempotent: safe to call from both a CLI command and any module it imports."""
    global _logging_configured
    if _logging_configured:
        return
    _logging_configured = True

    settings = get_settings()
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


# Batch-job metrics for `wfw ingest` / `wfw process`, pushed to the Pushgateway
# (each CLI invocation is a fresh process, so a module-level registry never
# accumulates state across runs).
registry = CollectorRegistry()

scenes_ingested_total = Counter(
    "wfw_scenes_ingested_total",
    "Sentinel-2 scenes ingested by wfw ingest",
    ["status"],
    registry=registry,
)
processing_jobs_total = Counter(
    "wfw_processing_jobs_total",
    "wfw process invocations",
    ["status"],
    registry=registry,
)
processing_duration_seconds = Histogram(
    "wfw_processing_duration_seconds",
    "Time to compute dNBR and vectorize burn-severity polygons for one scene pair",
    registry=registry,
)
detections_stored_total = Counter(
    "wfw_detections_stored_total",
    "Burn-severity polygons stored by wfw process",
    registry=registry,
)


def push_metrics(job: str) -> None:
    """Best-effort push to the Prometheus Pushgateway; never raises."""
    settings = get_settings()
    if not settings.pushgateway_url:
        return
    try:
        push_to_gateway(settings.pushgateway_url, job=job, registry=registry, timeout=5)
    except Exception:  # noqa: BLE001 -- a monitoring outage must never fail the pipeline
        get_logger(__name__).warning("pushgateway_unreachable", pushgateway_url=settings.pushgateway_url)
