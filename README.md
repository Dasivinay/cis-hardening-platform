# SecHarden — CIS Benchmarking & Linux Hardening Platform

Enterprise-style web platform for running CIS Benchmark scans against Docker-managed Ubuntu targets, tracking results over time, and surfacing remediation guidance — built as a portfolio-grade reference implementation.

## Stack

- **Backend:** Python 3.12, Flask, Flask-RESTX (Swagger), SQLAlchemy, Flask-JWT-Extended, Celery + Redis
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Recharts
- **Database:** PostgreSQL
- **Scan engines:** OpenSCAP (bundled, works out of the box) and CIS-CAT PRO (adapter only — bring your own license)
- **Infra:** Docker Compose

## Quick start

```bash
cp .env.example .env        # edit SECRET_KEY / JWT_SECRET_KEY before any real deployment
docker compose --profile build-only build scan-target-image-builder
docker compose up --build
```

- Frontend: http://localhost:5173
- API + Swagger docs: http://localhost:5000/api/v1/docs
- Default admin login: `admin@secharden.local` / `ChangeMe123!` (set via `.env`, change immediately after first login)

The database schema is created and the admin account seeded automatically on first boot — no manual setup required.

## Architecture

```
Browser → React (Vite/Tailwind) → REST API (Flask-RESTX) → Service layer → Repository layer → PostgreSQL
                                          │
                                          ├─ Docker SDK ──→ Ubuntu target containers (scan targets only)
                                          └─ Celery + Redis → async scan execution & scheduling
```

Layering follows repository → service → API resource, so business logic never touches raw SQLAlchemy queries directly and API resources never touch Docker/DB directly. See `docs/01-requirements.md` for the full requirements analysis this was built against.

## Security boundaries (read before extending)

- The platform only ever executes commands inside containers it created and tracks in the `containers` table (`DockerService`). There is no path to arbitrary host command execution.
- Remediation guidance (`Remediation` model) is advisory text, displayed to the user. Nothing in the codebase auto-applies a remediation command.
- CIS-CAT PRO is not bundled — `CISCATAdapter` drives an operator-supplied, licensed installation mounted at `/opt/ciscat` in the target image.

## Scan engines

| Engine | Status | Requirements |
|---|---|---|
| `openscap` | Fully functional | None — baked into the target image |
| `ciscat` | Adapter only | Licensed CIS-CAT PRO Assessor, mounted by the operator into `/opt/ciscat` |

## Repository layout

```
backend/    Flask API, services, repositories, Celery tasks, tests
frontend/   React + Vite + TS SPA
targets/    Ubuntu scan-target Docker image (OpenSCAP pre-installed)
docs/       Requirements analysis and architecture notes
```

## Running tests

```bash
cd backend && FLASK_ENV=testing pytest tests/ -v
cd frontend && npm run build   # type-checks + production build
```

## Roles

| Role | Access |
|---|---|
| `admin` | Full access: users, targets, scans, audit log |
| `analyst` | Targets, scans, remediation — no user management |
| `viewer` | Read-only |

## Audit & repair log (verified against real infrastructure, not assumed)

This section documents bugs found during a full engineering audit — each verified against real tooling (actual Ubuntu package archives, a real PostgreSQL instance, a real `oscap` binary, and real HTTP requests), not assumed correct from reading the code.

| # | Bug | Verification method | Fix |
|---|---|---|---|
| 1 | Target image failed to build: `openscap-scanner` and every `ssg-*` package do not exist for Ubuntu 22.04 in the real Ubuntu archives — the `openscap` source package only ships libraries there | Pointed `apt-cache`/`apt-get --simulate` at the real jammy/noble repos over `archive.ubuntu.com` | Switched target base image to `ubuntu:24.04`, where these are real installable packages. **Superseded by finding #5 below** — the apt-packaged content itself only supports up to Ubuntu 22.04, which turned out to matter |
| 2 | `Create Target` could fail with a Docker 404: `docker-compose.yml` passed a guessed network name (`cis-hardening-platform_default`) to the Docker SDK, which only exists if Compose's project-name-derived default happens to match | Code review of `DockerService.create_target` + Compose's network-naming behavior | Replaced with an explicit named network (`secharden-net`); added a defensive fallback in `DockerService._resolve_network()` so a future mismatch degrades gracefully instead of hard-failing |
| 3 | Misleading 0% scores: a scan could complete with zero pass/fail results and the platform reported that as a 0.0% score | Installed real `openscap-scanner` and ran an actual `oscap xccdf eval` — the 0/0 case is real and reachable (root cause identified precisely in finding #5: a content/OS mismatch, not an inherent container limitation) | `ParsedReport.score` returns `None` ("N/A") instead of `0.0` when nothing was actually scored — kept as a defensive fix regardless of finding #5's root cause, since 0/0 remains reachable for other reasons (e.g. a profile with no rules applicable to a given target); propagated through the dashboard average, PDF/HTML export, notifications, and frontend |
| 4 | **Critical:** every custom error response (`400`/`401`/`403`/`404`/`409`) actually returned a generic `500` in real deployment, despite the backend pytest suite passing | Ran the real Flask app against a real PostgreSQL instance and hit endpoints with `curl` directly — this bypasses a masking effect in Flask's `TESTING=True` mode that pytest relies on, which takes a different exception-propagation path and hid the bug | Root cause: flask-restx's `Api.error_router` intercepts every exception on its own routes *before* Flask's `app.errorhandler` chain ever runs, and only consults handlers registered via the flask-restx-specific `api.errorhandler(...)`. Rewrote error registration to use that mechanism; added 7 regression tests in `tests/test_error_handling.py` that assert on real status codes so this class of bug can't silently reappear |
| 5 | Every scan produced 0 pass / 0 fail — the apt-packaged SSG content only supports up to Ubuntu 22.04 and declares platform applicability as `cpe:/o:canonical:ubuntu_linux:22.04`; scanning a 24.04 target (required by fix #1) with it fails the platform check for every rule | Built `ComplianceAsCode/content` v0.1.81's `ubuntu2404` product from source and scanned a real target: 132 pass / 19 fail / 2 error, versus 0/0 with the old content — isolating content/OS mismatch as the cause, not a container limitation | Target image now multi-stage builds the real `ssg-ubuntu2404-ds.xml` from source at Docker build time, and injects `CPE_NAME="cpe:/o:canonical:ubuntu_linux:24.04"` into `/etc/os-release` — confirmed necessary and sufficient by directly comparing scans with and without it (ComplianceAsCode's own official test-suite Dockerfile does the same) |
| 6 | **Critical:** scans always failed with "report file was never produced," hiding the real cause | `oscap`'s exit codes, confirmed against 8 independent official man pages: 0 = pass, **1 = a real evaluation error**, 2 = findings present (normal). The code's `if exit_code > 2: raise` silently treated exit code 1 as success and proceeded to wait for a report that oscap never wrote because it had already errored out | Fixed to `if exit_code not in (0, 2): raise`, with the full oscap output included in the error. Added a `command_log` column so stdout+stderr is always persisted (not just on failure), and surfaced both in the scan detail UI instead of a generic "check container logs" message |
| 7 | Auto-detecting the installed SCAP datastream (to avoid hardcoding a filename) initially picked the **wrong** file when multiple versions were present | Reproduced directly: with `ssg-ubuntu1604-ds.xml` through `ssg-ubuntu2404-ds.xml` all present, a naive `ls ssg-*-ds.xml \| head -1` picked the oldest (1604) — lexicographic sort, not version order — reproducing the exact "No profile matching suffix... found" / exit code 1 failure from finding #6 | Changed to `sort -V \| tail -n1` (version-aware, highest wins); verified this correctly selects `ssg-ubuntu2404-ds.xml` from the same contaminated directory that broke the naive version |

### Correction to a previous finding

An earlier audit pass concluded that CIS server-hardening scans would legitimately produce 0 pass/0 fail inside any Docker container, and shipped that as a documented "known constraint." **That conclusion was wrong**, and is corrected here rather than left standing.

The actual cause: the apt-packaged `ssg-debderived` content tops out at Ubuntu 22.04 and declares platform applicability as `cpe:/o:canonical:ubuntu_linux:22.04`. Scanning a 24.04 target with it makes the platform-applicability check fail for every rule — a **content/OS version mismatch**, not a container limitation. Confirmed by building `ComplianceAsCode/content` v0.1.81's actual `ubuntu2404` product from source and scanning a real target: **132 pass / 19 fail / 2 error**, a genuine 87.4% benchmark score — once (a) the content version matches the OS being scanned, and (b) `/etc/os-release` has a `CPE_NAME` field, which stock Ubuntu 24.04 images don't set by default (confirmed against ComplianceAsCode's own official test-suite Dockerfile, which sets this explicitly).

The target image now multi-stage builds the real `ssg-ubuntu2404-ds.xml` from source at Docker build time and injects the `CPE_NAME` fix, rather than relying on the outdated apt-packaged content. A handful of rules (GRUB/bootloader, kernel module blacklisting, physical console security) remain legitimately `notapplicable` inside any container — that part of the original finding was accurate — but the overall scan is not doomed to zero signal, and the platform no longer implies that it is.


