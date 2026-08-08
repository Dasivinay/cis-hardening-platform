# Phase 1 — Requirement Analysis
## Enterprise CIS Benchmarking & Linux Security Hardening Platform

**Document owner:** Technical Project Manager
**Reviewers:** Chief Software Architect, Principal Cybersecurity Engineer, Principal DevSecOps Engineer
**Status:** Draft v1.0

---

## 1. Project Charter

| Field | Value |
|---|---|
| Project Name | SecHarden — CIS Benchmarking & Linux Hardening Platform |
| Sponsor | Portfolio / Academic Major Project |
| Target Users | Security engineers, sysadmins, compliance auditors, DevSecOps teams |
| Deployment Model | Self-hosted, Docker Compose, on-prem or single cloud VM |
| Primary Value Proposition | Automate CIS Benchmark scanning of Ubuntu targets, centralize findings, track remediation over time, and produce audit-ready reports — without hand-parsing raw scanner output |

## 2. Problem Statement

Organizations running CIS Benchmark assessments today typically run a scanner (CIS-CAT PRO or OpenSCAP) manually per host, and end up with a folder of disconnected HTML/XML reports. There is no persistent history, no trend visibility across scans, no centralized remediation tracking, and no multi-user access control. This platform closes that gap for Linux (Ubuntu) fleets managed as Docker targets.

## 3. Scope

### 3.1 In Scope
- Web-based platform (React frontend + Flask REST API backend)
- Docker-managed Ubuntu target containers (create/start/stop/exec/delete, via Docker SDK only — no host shell execution)
- Pluggable scan engine: **CIS-CAT PRO Assessor** adapter (bring-your-own license/jar) and **OpenSCAP** adapter (open source, works out of the box)
- Parsing of scan output (XCCDF/ARF XML for OpenSCAP; HTML/XML for CIS-CAT) into normalized DB records
- Benchmark scoring, pass/fail control breakdown, severity classification
- Remediation guidance library mapped to control IDs (informational — commands are *displayed*, never auto-executed against the host)
- Multi-user auth (JWT), role-based access control (Admin / Analyst / Viewer)
- Scan scheduling (Celery + Redis)
- Historical trend tracking across scans per target
- Analytics dashboard (Recharts)
- Audit logging of all user actions
- Report export (PDF/HTML)
- Full OpenAPI/Swagger documentation
- Dockerized, one-command local deployment

### 3.2 Out of Scope (v1)
- Non-Ubuntu OS targets (RHEL/Windows benchmarks) — architecture will allow adding adapters later, not built in v1
- Auto-remediation / auto-patching of hosts
- Agent-based (non-container) scanning of bare-metal or cloud VM fleets
- SSO/SAML (JWT-based local auth only in v1; documented as a v2 extension point)
- Multi-tenancy (single organization per deployment in v1)

## 4. Actors & Roles

| Role | Permissions |
|---|---|
| **Admin** | Full access: user management, container management, all scans, settings, audit log |
| **Analyst** | Create/run scans, manage targets, view reports, view remediation, cannot manage users |
| **Viewer** | Read-only: dashboards, reports, history |

## 5. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | User can register/login via JWT-based auth with bcrypt password hashing | Must |
| FR-02 | Admin can manage users and assign roles | Must |
| FR-03 | User can create/start/stop/delete an Ubuntu Docker container as a scan target | Must |
| FR-04 | User can trigger a CIS Benchmark scan against a target container | Must |
| FR-05 | System parses scan report and stores controls, results, severity, scores in DB | Must |
| FR-06 | User can view dashboard with aggregate score, pass/fail counts, severity breakdown | Must |
| FR-07 | User can drill into a single scan to see every control with status and remediation | Must |
| FR-08 | User can view historical trend of a target's score across multiple scans | Must |
| FR-09 | User can schedule recurring scans | Should |
| FR-10 | User can export a scan report as PDF | Should |
| FR-11 | System logs every state-changing action to an audit log, viewable by Admin | Must |
| FR-12 | User receives in-app notifications on scan completion/failure | Should |
| FR-13 | User can search/filter/sort/paginate controls, scans, and targets | Must |
| FR-14 | System supports both CIS-CAT PRO and OpenSCAP as interchangeable scan engines | Must |

## 6. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | All API endpoints require JWT auth except `/auth/login`, `/auth/register`, `/health` |
| NFR-02 | Passwords hashed with bcrypt, never logged or returned by API |
| NFR-03 | All container/exec actions scoped to Docker-managed containers only — no host OS command execution |
| NFR-04 | API responses paginated by default (page size configurable, max enforced) |
| NFR-05 | All list endpoints support filtering and sorting via query params |
| NFR-06 | System must start from `docker compose up` with zero manual DB setup (auto-migration on boot) |
| NFR-07 | Backend test coverage target ≥ 80% on service layer |
| NFR-08 | API documented via OpenAPI/Swagger, available at `/api/docs` |
| NFR-09 | Secrets (JWT secret, DB creds) loaded from environment variables, never hardcoded |
| NFR-10 | Rate limiting applied to auth endpoints to mitigate brute force |

## 7. Assumptions & Constraints

- Target hosts are **Ubuntu Docker containers** managed by this platform, not arbitrary external servers, for both safety and demo simplicity.
- CIS-CAT PRO requires a commercial license from the Center for Internet Security; the platform ships with the OpenSCAP adapter enabled by default so it is fully runnable without one.
- Remediation guidance is advisory. The platform will never modify a host automatically; a user must explicitly confirm any change, and that change is applied only inside the scoped target container, never the platform host.

## 8. High-Level Success Criteria

- Fresh clone → `docker compose up` → login → create target → run scan → view scored dashboard, in under 15 minutes, no manual steps.
- Codebase demonstrates layered architecture (repository/service/API layers), documented and tested to a standard defensible in an interview or thesis defense.

---
**Next:** Phase 2 — Software Architecture (component diagram, layering, deployment topology).
