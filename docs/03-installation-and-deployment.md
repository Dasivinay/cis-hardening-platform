# Installation & Deployment Guide

## Prerequisites

- Docker Desktop (Windows/Mac) or Docker Engine + Compose plugin (Linux)
- ~4GB free disk space (Postgres + Ubuntu target images)
- Ports 5173, 5000, 5432, 6379 free on the host

## First-time setup

```bash
git clone <your-fork-url> secharden
cd secharden

cp .env.example .env
# edit .env: set SECRET_KEY and JWT_SECRET_KEY to long random strings,
# and change SEED_ADMIN_PASSWORD before any non-local use

# Build the Ubuntu scan-target image (not started as a long-running service,
# just needs to exist in the local Docker image cache before targets can be created)
docker compose --profile build-only build scan-target-image-builder

# Bring up the full stack
docker compose up --build
```

On first boot the backend entrypoint automatically:
1. Waits for Postgres to accept connections
2. Runs Alembic migrations (`flask db upgrade`, initializing on first run)
3. Runs `seed.py` — creates the three roles, the default admin user, and a starter remediation library

No manual `flask db init` / `createdb` / seeding step is required.

## Verifying the install

```bash
curl http://localhost:5000/health          # {"status": "ok"}
open http://localhost:5000/api/v1/docs     # Swagger UI
open http://localhost:5173                 # frontend
```

Log in with the admin credentials from `.env` (defaults: `admin@secharden.local` / `ChangeMe123!` — change this immediately in any shared environment).

## Running a first scan end-to-end

1. Sign in → **Targets** → **New target** → name it (e.g. `demo-01`) → Create. This pulls/starts an Ubuntu container with OpenSCAP pre-installed.
2. Click the scan icon on the target row. This queues a scan using the `openscap` engine against the CIS Level 1 Server profile.
3. Watch **Scans** → the row updates from `queued` → `running` → `completed` (poll interval 3s on the detail page while running).
4. Open the completed scan to see pass/fail controls, or export PDF/HTML from the detail page.

## Using CIS-CAT PRO instead of OpenSCAP

1. Obtain a CIS-CAT PRO Assessor license and installation from the Center for Internet Security (not provided by or bundled with this project).
2. Mount it into the target image at `/opt/ciscat` — either bake it into a custom target image extending `targets/ubuntu-scan-target/Dockerfile`, or mount it as a volume when the target container is created (extend `DockerService.create_target` to accept a volume mapping).
3. Trigger a scan with `"engine": "ciscat"` and a `benchmark_id` matching a benchmark XML filename under `/opt/ciscat/benchmarks/`.

## Running tests

```bash
# Backend
cd backend
pip install -r requirements.txt
FLASK_ENV=testing pytest tests/ -v --cov=app

# Frontend unit tests
cd frontend
npm install
npm run test

# Frontend E2E (requires the full stack running via docker compose)
npm run test:e2e
```

## Common issues

| Symptom | Cause | Fix |
|---|---|---|
| `502` on container create | Docker socket not mounted / Docker Desktop not running | Ensure `/var/run/docker.sock` is mounted (already in `docker-compose.yml`) and Docker Desktop is running on the host |
| Scans stay `queued` forever | Celery worker not running or can't reach Redis | `docker compose logs celery-worker` |
| Frontend can't reach API (CORS error) | `CORS_ORIGINS` doesn't include your frontend origin | Add it to `.env` / `docker-compose.yml` backend environment |
| Target image not found | `scan-target-image-builder` profile wasn't built | Run the `--profile build-only build` step above before `docker compose up` |

## Production hardening checklist

- Replace default `SECRET_KEY` / `JWT_SECRET_KEY` / `SEED_ADMIN_PASSWORD`
- Put the stack behind a reverse proxy (nginx/Traefik) terminating TLS
- Restrict the Docker socket mount to a rootless/sysbox-style setup if targets are exposed to less-trusted scan definitions
- Set `FLASK_ENV=production` (already default) and disable Flask debug mode (already off in `ProductionConfig`)
- Point `DATABASE_URL` at a managed Postgres instance with backups, rather than the bundled `db` container, for anything beyond a demo
