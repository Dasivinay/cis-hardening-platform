import os
from datetime import timedelta


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-prod")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-prod-too")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://cis_user:cis_password@db:5432/cis_platform",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)

    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

    # Default scan engine: 'openscap' works out of the box (no license needed).
    # 'ciscat' requires a licensed CIS-CAT PRO Assessor jar mounted into the target.
    DEFAULT_SCAN_ENGINE = os.environ.get("DEFAULT_SCAN_ENGINE", "openscap")

    DOCKER_TARGET_IMAGE = os.environ.get("DOCKER_TARGET_IMAGE", "cis-platform/ubuntu-scan-target:latest")
    DOCKER_NETWORK = os.environ.get("DOCKER_NETWORK", "cis-platform_default")

    RATELIMIT_STORAGE_URI = REDIS_URL

    PAGINATION_DEFAULT_PAGE_SIZE = 20
    PAGINATION_MAX_PAGE_SIZE = 100


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///dev.db")


class ProductionConfig(BaseConfig):
    DEBUG = False


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
