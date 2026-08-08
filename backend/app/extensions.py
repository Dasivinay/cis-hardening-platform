"""
Centralized Flask extension instances.
Instantiated here (unbound) and initialized via init_app() in the app factory,
so services/repositories can import `db`, `jwt`, etc. without circular imports.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery import Celery
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
jwt = JWTManager()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """
    SQLite does not enforce foreign key constraints (including ON DELETE
    CASCADE) unless explicitly told to per-connection — unlike PostgreSQL,
    which enforces them by default. The test suite runs against SQLite
    (see config.TestingConfig), so without this, cascade-delete behavior
    could pass in tests while silently not being enforced, or vice versa.
    This is a no-op for non-SQLite connections (e.g. production Postgres).
    """
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

cors = CORS()
migrate = Migrate()
limiter = Limiter(key_func=get_remote_address)
celery_app = Celery(__name__)


def make_celery(app):
    celery_app.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
    )

    class ContextTask(celery_app.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = ContextTask
    return celery_app
