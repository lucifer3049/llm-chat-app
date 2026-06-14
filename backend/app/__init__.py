"""Application factory (apiflask).

Day 1 wires the skeleton: config, OpenAPI `/docs`, and the health blueprint.
Auth / RBAC / chat / admin blueprints are registered here as they land in later
phases.
"""
from __future__ import annotations

from apiflask import APIFlask

from app.infrastructure.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> APIFlask:
    settings = settings or get_settings()

    app = APIFlask(
        __name__,
        title="LLM Chat API",
        version="0.1.0",
        docs_path="/docs",
    )
    app.config["DESCRIPTION"] = "Multi-user LLM chat web application API."
    app.config["AUTO_404_RESPONSE"] = True

    _register_blueprints(app)

    return app


def _register_blueprints(app: APIFlask) -> None:
    from app.interface.api.health import health_bp

    app.register_blueprint(health_bp)
