# Phase 2–4 — Architecture, System Design & Database Design

## 1. Component Diagram

```
                        ┌─────────────────────────┐
                        │   React SPA (Vite/TS)   │
                        │  Dashboard / Targets /  │
                        │  Scans / Controls / ...  │
                        └────────────┬─────────────┘
                                     │ HTTPS (JWT bearer)
                        ┌────────────▼─────────────┐
                        │   Flask REST API          │
                        │   (flask-restx, Swagger)  │
                        │   auth · users · containers│
                        │   scans · controls · audit │
                        │   remediation · reports    │
                        │   notifications · scheduling│
                        └──┬──────────┬─────────┬────┘
                           │          │         │
              ┌────────────▼──┐  ┌────▼───┐ ┌───▼────────┐
              │ Service layer  │  │ Docker │ │ Celery task│
              │ (business logic)│  │  SDK   │ │  queue     │
              └────────┬───────┘  └───┬────┘ └───┬────────┘
                       │              │           │
              ┌────────▼───────┐      │    ┌──────▼──────┐
              │ Repository layer│      │    │ Redis broker │
              │ (SQLAlchemy)    │      │    └──────┬──────┘
              └────────┬───────┘      │           │
                       │              │    ┌──────▼──────┐
              ┌────────▼───────┐      │    │Celery worker/│
              │  PostgreSQL     │      │    │Celery beat   │
              └────────────────┘      │    └──────────────┘
                                       │
                              ┌────────▼─────────┐
                              │ Ubuntu target      │
                              │ containers          │
                              │ (OpenSCAP/CIS-CAT)   │
                              └────────────────────┘
```

**Layering rule enforced throughout the codebase:** API resources (`app/api/*.py`) never touch SQLAlchemy or Docker directly — they call a service. Services never build raw queries — they call a repository. This is what makes the RBAC decorator, error handling, and audit logging consistent everywhere instead of duplicated per-endpoint.

## 2. Sequence Diagram — Triggering and Running a Scan

```
User        Frontend        API             Celery Worker      Docker (target)     DB
 │  click      │               │                   │                  │            │
 │──"Scan"────▶│               │                   │                  │            │
 │             │─POST /scans──▶│                   │                  │            │
 │             │               │─create Scan(queued)───────────────────────────────▶│
 │             │               │─enqueue run_scan_task.delay()─▶│                  │
 │             │◀──202 queued──│                   │                  │            │
 │             │               │                   │─exec oscap cmd──▶│            │
 │             │               │                   │◀─exit code───────│            │
 │             │               │                   │─get_archive(report)──────────▶│
 │             │               │                   │◀─raw XML──────────│            │
 │             │               │                   │─parse + persist Controls──────▶│
 │             │               │                   │─update Scan(completed)────────▶│
 │             │               │                   │─notify(user)──────────────────▶│
 │  poll/refresh (3s while running)                │                  │            │
 │◀────────────│◀──GET /scans/:id (completed)──────│                  │            │
```

## 3. Entity-Relationship Diagram

```
 Role 1───* User 1───* Container 1───* Scan 1───* ScanResultControl *───1 Control 1───1 Remediation
                                        │                                    ▲
                                        │                                    │
                                   ScheduledScan ───────────────────────────┘ (rule_id lookup on parse)

 User 1───* AuditLog
 User 1───* Notification
```

| Table | Key relationships |
|---|---|
| `roles` | referenced by `users.role_id` |
| `users` | owns containers, scans, audit_logs, notifications |
| `containers` | Docker-tracked target; owns scans |
| `scans` | belongs to a container; owns scan_result_controls |
| `controls` | master catalog, deduplicated by `rule_id`; has one `remediation` |
| `scan_result_controls` | join table: per-scan status for a control |
| `scheduled_scans` | recurring scan definition, references container |
| `audit_logs` | append-only, references user (nullable for system events) |
| `notifications` | per-user, read/unread |

This is a fully normalized (3NF) schema: control metadata lives once in `controls` regardless of how many scans reference it; per-scan results live in the join table `scan_result_controls`, not duplicated onto `controls`.

## 4. Deployment Topology

Single Docker Compose stack, 7 services: `db` (Postgres), `redis`, `backend` (Gunicorn/Flask), `celery-worker`, `celery-beat`, `frontend` (nginx serving the Vite build), and a one-shot `scan-target-image-builder` profile that builds the Ubuntu target image. The backend and celery containers mount the Docker socket to manage target containers — this is the one place the platform touches Docker directly, and it's isolated to `DockerService`.

## 5. Class-Level Design (backend)

- **Repository pattern**: `BaseRepository` + per-model subclasses (`UserRepository`, `ContainerRepository`, `ScanRepository`, ...) — isolates SQLAlchemy from business logic.
- **Service layer**: `AuthService`, `DockerService`, `ScanService`, `RemediationService`, `DashboardService`, `AuditService`, `NotificationService`, `SchedulingService`, `ExportService` — one responsibility each, all unit-testable independent of Flask request context (used directly in tests).
- **Adapter pattern**: `ScanEngineAdapter` (abstract) → `OpenSCAPAdapter`, `CISCATAdapter` — this is what satisfies FR-14 (interchangeable scan engines) without `ScanService` knowing which engine it's talking to.
- **Centralized error handling**: `AppError` hierarchy + `register_error_handlers()` — every service raises typed exceptions (`NotFoundError`, `ValidationError`, `ConflictError`, `ForbiddenError`, `ExternalServiceError`), and the API layer never has to individually try/except each one.
