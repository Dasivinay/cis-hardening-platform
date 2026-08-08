import os
from flask import Flask

from app.config import config_by_name
from app.extensions import db, jwt, cors, migrate, limiter, make_celery
from app.utils.errors import register_error_handlers


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "production")
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})
    migrate.init_app(app, db)
    limiter.init_app(app)
    make_celery(app)

    from app.api import api_bp
    app.register_blueprint(api_bp)

    register_error_handlers(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
