import time
import random
import asyncio

from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(
    title="Observability Demo API",
    version="1.0.0",
)

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

    return response


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
