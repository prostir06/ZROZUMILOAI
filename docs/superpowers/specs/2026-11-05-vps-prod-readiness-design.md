# VPS Production Readiness — Design

Date: 2026-11-05  
Status: approved / implemented

## Goal

Довести ZrozumiloAI до кампусного продакшену на одному VPS: Docker Compose + Caddy, Ollama на тому ж хості (з caps), без Prometheus на боксі.

## Constraints

- Scale: LMS / Open edX embed, сотні сесій на день
- LLM: Ollama same-VPS, resource-capped; `OLLAMA_BASE_URL` — єдиний upstream (готовий до remote GPU)
- Observability v1: `/api/health/` + JSON logs (`request_id`) + external uptime ping
- Non-goals: K8s, multi-tenant billing, in-VPS Prometheus/Grafana, GPU host split (лише документ)

## Architecture

```
Internet → Caddy (TLS, body limit) → Frontend SPA
                                 ↘ Backend (Gunicorn/gevent)
                                      ├─ Postgres
                                      ├─ Redis (password)
                                      ├─ Celery worker
                                      └─ Ollama (capped)
```

## Decisions

1. Resource limits лише в `docker-compose.prod.yml` (локальний DX без caps).
2. Campus defaults: `OLLAMA_NUM_PARALLEL=1`, host RAM ≥16 GB; Celery concurrency 1; Gunicorn workers 2.
3. Edge: Caddy `request_body max_size 12MB`; rate limit — DRF throttles (stock Caddy без плагіна).
4. Backups: host cron → `manage.py create_backup` → `./backup`; RPO 24h; off-box copy обовʼязковий.
5. Runbook: deploy, health, overload, restore drill, rollback.

## Acceptance

- Prod overlay: mem/cpu + concurrency defaults
- Runbook + README links + hardware / `OLLAMA_BASE_URL` note
- `docker compose … prod config` validates
