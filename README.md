# Terraform Observability Stack

A Terraform-provisioned observability stack — Prometheus, Grafana, and Alertmanager — monitoring a metrics-instrumented app, with a live control panel for triggering failure scenarios and a documented incident response to one.

## Overview

This project demonstrates the full observability lifecycle: instrumenting an application, collecting and storing its metrics, visualizing them, alerting on them, and responding to a simulated incident — all provisioned as code, not click-ops.

Rather than deploying monitoring tools against someone else's demo app, the app itself is purpose-built here to expose real request metrics (count, latency, status) and to include endpoints that deliberately misbehave on demand, so the entire alerting pipeline can be exercised end-to-end, repeatably.

## What this demonstrates

- **Infrastructure as Code** — the entire stack (five services, their networking, volumes, and configuration) is defined in Terraform and reproducible with `terraform apply` on any machine with Docker installed
- **Application instrumentation** — custom Prometheus metrics (`http_requests_total`, `http_request_duration_seconds`) added via middleware, not bolted on afterward
- **Alert design** — threshold-based alert rules for error rate, latency, availability, and host resource usage, each tuned with a sustained-duration window to avoid false positives on brief blips
- **Dashboards as code** — Grafana data sources and dashboard panels auto-provisioned on startup, no manual configuration
- **Incident response** — a real, evidence-backed postmortem (see [`docs/incidents/`](docs/incidents/)) documenting detection, timeline, root cause, and resolution for a simulated production failure
- **Operational tooling** — a custom control panel UI for triggering scenarios live, rather than relying on terminal scripts for every demo

## Architecture

```
                         ┌─────────────────────┐
                         │   Control Panel UI   │
                         │  (served by the app) │
                         └──────────┬───────────┘
                                    │ triggers
                                    ▼
┌──────────────┐  scrapes  ┌───────────────┐  evaluates  ┌───────────────┐
│     App       │◄─────────│  Prometheus   │────────────►│ Alertmanager  │
│ (FastAPI +    │  /metrics │               │   alerts    │               │
│  Prom client) │           └───────┬───────┘             └───────────────┘
└──────────────┘                   │
                                    │ queried by
                                    ▼
                         ┌─────────────────────┐
                         │       Grafana        │
                         │   (dashboards)        │
                         └─────────────────────┘

┌──────────────────┐
│   node-exporter    │── scraped by Prometheus for host CPU/memory metrics
└──────────────────┘

All five services run as Docker containers on a shared network,
provisioned entirely by Terraform (kreuzwerker/docker provider).
```

## Technology stack

| Category | Technology |
|---|---|
| Infrastructure as Code | Terraform (`kreuzwerker/docker` provider) |
| Containerization | Docker |
| Application | Python, FastAPI |
| Metrics | Prometheus, `prometheus_client` |
| Dashboards | Grafana |
| Alerting | Alertmanager |
| Host metrics | node-exporter |
| Control panel UI | Vanilla HTML/CSS/JS, served by the app itself |

## Repository structure

```
observability-stack/
│
├── main.tf                     # All Docker-provisioned resources
├── variables.tf                 # Configurable ports, credentials
├── outputs.tf                   # URLs for each service
│
├── app/
│   ├── main.py                  # FastAPI app, metrics middleware, stats API
│   ├── requirements.txt
│   ├── Dockerfile
│   └── static/
│       └── index.html           # Control panel UI
│
├── config/
│   ├── prometheus.yml           # Scrape config
│   ├── alert.rules.yml          # Alert rule definitions
│   ├── alertmanager.yml         # Alert routing
│   └── grafana/
│       ├── datasources/         # Auto-provisioned Prometheus data source
│       └── dashboards/          # Auto-provisioned dashboard JSON
│
└── docs/
    └── incidents/                # Documented incident postmortems
```

## Getting started

### Prerequisites
- Docker Desktop
- Terraform

### Run it

```bash
terraform init
terraform apply
```

This builds nothing itself for the app image — see the note below — but provisions all five containers and wires their networking, volumes, and config.

### Build the app image

Because of a build-context issue with the Docker provider on some platforms, the app image is built manually rather than by Terraform:

```bash
cd app
docker build -t observability-demo-app:latest .
cd ..
terraform apply
```

### Access each service

| Service | URL |
|---|---|
| Control panel | http://localhost:8000 |
| Grafana | http://localhost:3000 |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |

Grafana login defaults to `admin` / the password set in `variables.tf` — change this before using the project beyond local experimentation.

### Stop everything

```bash
terraform destroy
```

## The control panel

Rather than triggering failure scenarios via `curl` loops in a terminal, the app serves its own control panel at `/`. It provides:

- One-click triggers for each failure scenario (error storm, slow responses, CPU spike), each labeled with the exact alert threshold it's designed to trip
- Live telemetry (request count, error rate, average latency, uptime) polling the app's own `/api/stats` endpoint every two seconds
- A status indicator that reflects the same thresholds as the Prometheus alert rules
- A scrolling activity log of every scenario run

This makes the whole pipeline — app, metrics, alerting — demonstrable in under a minute without any terminal commands.

## Alert rules

| Alert | Condition | Sustained for |
|---|---|---|
| `HighErrorRate` | 5xx rate exceeds 5% of total requests | 2 minutes |
| `HighLatency` | p95 request latency exceeds 1 second | 2 minutes |
| `AppDown` | Prometheus cannot scrape the app | 1 minute |
| `HighCPUUsage` | Host CPU exceeds 85% | 5 minutes |
| `HighMemoryUsage` | Host memory exceeds 90% | 5 minutes |

Each rule requires its condition to hold for a sustained window before firing, specifically to avoid alerting on single brief spikes — a deliberate design choice, not an oversight.

## Incident documentation

This project doesn't just alert — it demonstrates responding to what the alerts find. See [`docs/incidents/001-high-error-rate.md`](docs/incidents/001-high-error-rate.md) for a full postmortem of a simulated error-rate incident, including the exact timeline from detection through to `FIRING` and resolution, backed by screenshots of the alert state transitions in Prometheus and Alertmanager.

## Known limitations / design notes

- The app's image is built manually rather than via Terraform's `docker_image` build block, due to a build-context checksum issue (`unpigz`/corrupted data) with the `kreuzwerker/docker` provider on some platforms. `docker_image.app` references the pre-built local image instead.
- Alertmanager currently routes to a placeholder webhook. A real Slack/Discord webhook can be substituted in `config/alertmanager.yml`.
- Everything runs locally via the Docker provider — no cloud account or billing required to run this project.

## Roadmap

- [x] Terraform-provisioned Prometheus, Grafana, Alertmanager, node-exporter
- [x] Instrumented FastAPI app exposing Prometheus metrics
- [x] Auto-provisioned Grafana dashboard
- [x] Alert rules for error rate, latency, availability, host resources
- [x] End-to-end alert firing confirmed (Prometheus → Alertmanager)
- [x] Documented incident postmortem
- [x] Custom control panel UI
- [ ] Real Slack/Discord alert routing
- [ ] Additional documented incidents (latency, availability)
- [ ] Log aggregation (Loki + Promtail)
- [ ] SLO / error budget tracking panel
- [ ] CI pipeline validating Terraform (`fmt`, `validate`, `plan`)
