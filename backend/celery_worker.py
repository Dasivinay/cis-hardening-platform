import os
from app import create_app
from app.extensions import celery_app

flask_app = create_app(os.environ.get("FLASK_ENV", "production"))
flask_app.app_context().push()

# Celery Beat schedule for recurring scans (FR-09)
celery_app.conf.beat_schedule = {
    "check-scheduled-scans-every-minute": {
        "task": "tasks.run_scheduled_scans",
        "schedule": 60.0,
    },
}

import app.tasks  # noqa: registers tasks with celery_app
