import time
import random
import asyncio
from collections import deque
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(
    title="Observability Demo API",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Lightweight in-memory stats for the control panel UI.
# Separate from the Prometheus metrics below — this is just a cheap JSON
# summary so the front end doesn't need to parse Prometheus's text format.
# Paths in POLL_PATHS are excluded so the dashboard's own polling doesn't
# pollute the request rate it's trying to display.
# ---------------------------------------------------------------------------
POLL_PATHS = {"/", "/api/stats", "/favicon.ico"}
START_TIME = time.time()
STATS = {"total_requests": 0, "error_count": 0}
RECENT_LATENCIES = deque(maxlen=100)
RECENT_REQUESTS = deque(maxlen=15)

# ---------------------------------------------------------------------------
# Prometheus metrics
# Names match what's referenced in config/alert.rules.yml — if you rename
# these, update the alert rules too.
# ---------------------------------------------------------------------------
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)


@app.middleware("http")
async def track_metrics(request: Request, call_next):
    method = request.method
    endpoint = request.url.path
    start_time = time.time()

    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        # Still record the failure as a 500 even if an unhandled exception
        # bubbles up, so the error-rate alert can see it.
        status = 500
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(time.time() - start_time)
        raise

    duration = time.time() - start_time
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    # Feed the lightweight control-panel stats, skipping the panel's own
    # polling traffic so it doesn't inflate the numbers it's displaying.
    if endpoint not in POLL_PATHS:
        STATS["total_requests"] += 1
        if status >= 500:
            STATS["error_count"] += 1
        RECENT_LATENCIES.append(duration)
        RECENT_REQUESTS.appendleft({
            "time": time.strftime("%H:%M:%S"),
            "endpoint": endpoint,
            "status": status,
            "duration_ms": round(duration * 1000, 1),
        })

    return response


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/stats")
def get_stats():
    latencies = list(RECENT_LATENCIES)
    avg_latency_ms = round((sum(latencies) / len(latencies)) * 1000, 1) if latencies else 0
    total = STATS["total_requests"]
    errors = STATS["error_count"]
    error_rate = round((errors / total) * 100, 2) if total else 0

    return {
        "total_requests": total,
        "total_errors": errors,
        "error_rate_percent": error_rate,
        "avg_latency_ms": avg_latency_ms,
        "uptime_seconds": round(time.time() - START_TIME),
        "recent_requests": list(RECENT_REQUESTS),
    }


@app.get("/")
def control_panel():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


# ---------------------------------------------------------------------------
# Normal endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/api/message")
def get_message():
    return {"message": "Hello from the Observability Demo API!"}


@app.get("/api/version")
def get_version():
    return {"version": "1.0.0"}


# ---------------------------------------------------------------------------
# Deliberately-breakable endpoints — use these to trigger each alert in
# config/alert.rules.yml and watch Prometheus/Alertmanager/Grafana react.
# ---------------------------------------------------------------------------
@app.get("/api/slow")
async def slow_endpoint():
    """
    Simulates a slow dependency (e.g. a bad DB query).
    Hit this repeatedly to push p95 latency over the HighLatency
    alert threshold (1s) for 2+ minutes.
    """
    delay = random.uniform(1.5, 3.5)
    await asyncio.sleep(delay)
    return {"message": "that took a while", "delay_seconds": round(delay, 2)}


@app.get("/api/error")
def error_endpoint():
    """
    Always returns a 500.
    Hit this repeatedly (relative to total traffic) to push the
    error rate over the HighErrorRate alert threshold (5%) for 2+ minutes.
    """
    return Response(content='{"error": "simulated failure"}', status_code=500, media_type="application/json")


@app.get("/api/cpu-spike")
def cpu_spike_endpoint():
    """
    Burns CPU for a few seconds on purpose.
    Hit this repeatedly/concurrently to push host CPU over the
    HighCPUUsage alert threshold (85%) for 5+ minutes.
    Note: FastAPI's default worker is single-process, so for a real
    CPU spike you may want to hit this endpoint with several concurrent
    requests (e.g. using a tool like `hey` or `ab`).
    """
    end_time = time.time() + 3
    x = 0
    while time.time() < end_time:
        x += 1  # busy loop — deliberately wasteful
    return {"message": "cpu spike complete", "iterations": x}