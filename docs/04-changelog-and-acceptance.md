# Repair Changelog — Scan Engine & Security Fixes

## Follow-up pass: stale-target-image self-heal

Every prior fix in this document (parser rewrite, exit-code handling, the
`profiles: [build-only]` compose bug) was real and correct, but none of them
could fix a target container that was **already running** from an older
image build before the fix landed — `docker compose build` rebuilding an
image tag never touches containers already instantiated from the old image
layers. A target created before any of the above fixes would keep silently
scanning its stale container forever, producing well-formed reports that
legitimately score 0 passed / 0 failed / N/A, with no error and no
diagnostic trail distinguishing it from a real parsing bug.

**Fix:** `DockerService.ensure_current_image()` (new) compares a tracked
container's actual `Image` attribute against what its image tag currently
resolves to. `ScanService.execute_scan()` calls this as the very first
pre-flight step, before any other Docker exec. On drift, it transparently
removes the stale container and recreates it (same name, same DB record,
fresh image) before the scan proceeds — so a target that predates a fix no
longer needs to be manually deleted and recreated; the next scan against it
self-heals automatically. On the happy path (image unchanged) it's a no-op.

New tests: `test_ensure_current_image_recreates_stale_container`,
`test_ensure_current_image_noop_when_already_fresh`,
`test_scan_recreates_stale_target_transparently_then_completes`.

**Not verified in this pass** (same limitation as below): no Docker daemon
and no network access to install backend dependencies in this environment,
so this was validated by `py_compile`/AST parsing and careful manual trace
through the mocked test scenarios — not by actually executing
`pytest tests/ -v`. Run that yourself before trusting it in production;
if it fails, tell me the failure and I'll fix it.

---

This document covers the changes made in this pass: merging user-provided fixes for the OpenSCAP scan engine, integrating them with the rest of the codebase, and closing the gaps that merge created.

## Files modified

| File | What changed |
|---|---|
| `backend/app/api/auth.py` | **Security fix**: `/auth/register` no longer accepts a client-supplied `role`. Previously any unauthenticated request could self-register as `admin`. Every self-registration is now forced to `viewer`; role elevation requires an authenticated admin via `PATCH /users/<id>`. |
| `backend/app/services/docker_service.py` | `exec_in_target` gained a `demux` parameter (separate stdout/stderr capture). `create_target` now detects and self-heals from orphaned Docker containers (a container that exists in Docker but isn't tracked in the DB) instead of failing with a raw 409. |
| `backend/app/services/scan_service.py` | Complete rewrite of the pre-flight sequence: verifies `oscap` exists, auto-detects the installed SCAP datastream (instead of a hardcoded path), and validates the requested profile actually exists in that datastream — all *before* running the real scan. Fixed the core bug: `oscap` exit code 1 (a real evaluation error) was previously treated as success; only 0 and 2 are now treated as "the scan ran." |
| `backend/app/services/parser/openscap_parser.py` | Rewritten to match on XML local-name instead of a fixed namespace/wrapper shape, so it correctly parses plain XCCDF results, ARF-wrapped results, and both XCCDF 1.1/1.2 content. Uses `itertext()` instead of `.text` so mixed-content descriptions aren't silently truncated. |
| `backend/app/services/parser/ciscat_parser.py` | Updated `build_scan_command` signature to accept the now-standard `datastream_path` parameter (unused by CIS-CAT, kept for interface compatibility). |
| `backend/app/services/parser/base.py` | Added `ParsedReport.failed_by_severity`. Updated the abstract `build_scan_command` signature. |
| `backend/app/models/scan.py` | Replaced the single `command_log` field with `datastream_path`, `oscap_stdout`, `oscap_stderr` — stdout and stderr are now captured and stored separately, on every run, not just on failure. |
| `backend/app/tasks.py` | `run_scheduled_scans` now rolls back and retries on the next tick if the Celery broker is unreachable when enqueuing, instead of leaving an orphaned `queued` scan with no task behind it. |
| `backend/tests/conftest.py` | `admin_token` fixture promotes a user to admin via direct DB update (matching the new production RBAC flow) instead of self-declaring `role: admin` at registration, which the security fix above no longer allows. |
| `backend/tests/test_scan_pipeline_hardening.py` | Rewritten to cover the new multi-step pre-flight pipeline: datastream auto-detection (including a regression test for picking the wrong/oldest datastream when multiple versions are present), profile validation, and the exit-code-1 vs exit-code-2 distinction. |
| `docker-compose.yml` | **Critical fix**: `scan-target-image-builder` was gated behind `profiles: [build-only]`, which Compose skips by default. `docker compose up --build` never built the target image, so every "Create Target" would fail with image-not-found unless the operator separately remembered to run a second build command. That gate is removed — the image now builds automatically as part of a normal `docker compose up --build`. |
| `frontend/src/api/scans.ts`, `frontend/src/pages/ScanDetailPage.tsx` | Updated to the new `datastream_path`/`oscap_stdout`/`oscap_stderr` fields; a failed scan now shows the actual error and captured oscap output in the UI instead of a generic "check container logs" message. |

## New files

- `backend/migrations/versions/e6cb39ff374f_init.py` — regenerated migration reflecting all model changes above, generated against and applied to a real PostgreSQL instance (not just SQLite).

## Root causes found and fixed this pass

1. **`oscap` exit code 1 misreported as "report missing."** Confirmed against 8 independent official man pages: 0 = pass, 1 = real evaluation error, 2 = findings present (normal). The pipeline now surfaces the real oscap error in these cases instead of a generic downstream symptom.
2. **Hardcoded datastream path.** Replaced with runtime auto-detection (`find` inside the target + `/etc/os-release` matching when multiple candidates exist). Regression-tested against a reproduction of the exact failure a naive "first match" approach would hit.
3. **`docker compose up --build` never built the target image.** The `profiles: [build-only]` gate meant Compose silently skipped it. This alone would explain every "Create Target" failure on a fresh clone using only the documented command.
4. **Self-registration privilege escalation.** `/auth/register` accepted a client-supplied `role`, allowing anyone to create an `admin` account with no authentication at all.
5. **Profile-listing brittleness.** `oscap info` output format isn't stable across builds (tab-delimited, colon-delimited, or bare-token-with-indented-title). Real output observed from this exact build is colon-delimited (`id:Title`) — the old assumption of a single delimiter would have broken on it. Replaced with a pattern-match on the self-delimiting SSG profile-id token itself.

## Real end-to-end verification performed

I do not have a Docker daemon in this environment, so I could not run `docker compose up --build` itself — that is the one thing that still needs confirming on your end. What I *did* verify for real, not by inspection:

- Installed the actual `openscap-scanner` package and the real `ComplianceAsCode/content` v0.1.81 Ubuntu 24.04 datastream in this sandbox (which itself runs Ubuntu 24.04 — the same OS the target container uses).
- Ran the complete `ScanService.execute_scan()` pipeline — every pre-flight check, the real `oscap` invocation, report wait, extraction, XML validation, parsing, and persistence — against a real PostgreSQL database, with `exec_in_target` substituted for a local subprocess call (since it runs the exact same commands the real Docker exec would).
- **Result: a real, correct benchmark score of 87.42% (132 passed / 19 failed / 2 error / 648 total), persisted to Postgres, correctly aggregated by the dashboard service, including a real severity breakdown (`{"low": 1, "medium": 18}`).**
- Confirmed the real `oscap info --profiles` output format and verified the new profile-parsing logic against it directly.
- Regenerated and applied the Alembic migration against real PostgreSQL (not SQLite) after all model changes.
- 33/33 backend tests pass; frontend type-checks and production-builds cleanly.

## Acceptance criteria

| Criterion | Status | Evidence |
|---|---|---|
| Docker Compose builds successfully | **Not verified** | No Docker daemon in this environment. Fixed the `profiles: [build-only]` bug that would have broken this; syntax-validated the compose file. |
| All containers become healthy | **Not verified** | Same limitation. |
| Database migrations succeed | ✅ Verified | Applied to a real PostgreSQL 16 instance from a dropped/recreated database. |
| Admin account created | ✅ Verified | Seed script run against real Postgres; confirmed via query. |
| Login / JWT works | ✅ Verified | Real HTTP round-trip against a running Flask app + real Postgres in an earlier pass of this audit; unit-tested here. |
| Users / Targets / Scans / Controls / Audit / Scheduling pages work | **Partially verified** | Backend APIs unit-tested and exercised directly; frontend builds cleanly and calls the correct endpoints. Did not render pages in a browser (no browser in this environment). |
| Target container launches | **Not verified** | Requires Docker. `DockerService.create_target` unit-tested with mocked Docker client; orphan-recovery logic reviewed and is straightforward Docker SDK usage. |
| OpenSCAP executes successfully | ✅ Verified | Real `oscap` run against real content in this sandbox, through the actual project code. |
| XML / report generated | ✅ Verified | Real 8MB+ XCCDF results file produced and parsed. |
| XML parser extracts controls correctly | ✅ Verified | 648 real controls parsed with correct pass/fail/error/notapplicable classification. |
| Benchmark score calculated correctly | ✅ Verified | 87.42% — hand-checked as 132/(132+19). |
| Dashboard displays benchmark score | ✅ Verified (service layer) | `DashboardService.summary()` called directly against real persisted data; frontend renders this field and builds cleanly, but wasn't visually rendered in a browser. |
| Reports downloadable (PDF/HTML) | ✅ Verified | Real PDF magic-byte check and real HTML content assertions, from an earlier pass; unaffected by this pass's changes. |
| Scheduled scans work | **Partially verified** | Enqueue/rollback logic unit-tested; Celery Beat itself (the periodic trigger) requires a running worker, not verified here. |
| No Docker conflicts / no orphan containers | **Partially verified** | Orphan-detection logic added and code-reviewed; not exercised against a real Docker daemon. |
| No unhandled Python exceptions (proper status codes) | ✅ Verified | Regression-tested in an earlier pass of this audit (flask-restx error handler fix), unaffected by this pass. |
| No frontend runtime errors | **Not verified** | No browser in this environment. Type-checks and production build are clean, which rules out an entire class of runtime errors but not all of them. |
| No placeholder implementations / no TODOs | ✅ Verified | `grep -rn "TODO\|FIXME\|placeholder" backend/app frontend/src` returns nothing. |

## Commands to run and verify

```bash
# Run
cp .env.example .env   # set SECRET_KEY / JWT_SECRET_KEY / SEED_ADMIN_PASSWORD
docker compose up --build -d
# wait for containers to report healthy, then:

# Verify
curl http://localhost:5000/health
open http://localhost:5000/api/v1/docs
open http://localhost:5173

# Backend tests
cd backend && FLASK_ENV=testing pytest tests/ -v

# Frontend
cd frontend && npm run build
```
