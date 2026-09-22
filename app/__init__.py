"""LogiSight application package."""
import logging

from flask import Flask, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from app.config import get_config

db = SQLAlchemy()
migrate = Migrate()


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app.logger.info("LogiSight starting (env=%s)", app.config.get("ENV"))


def create_app(config_object=None) -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_object or get_config())

    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    _configure_logging(app)
    _register_error_handlers(app)
    _register_blueprints(app)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def _register_blueprints(app: Flask) -> None:
    import app.models as _models  # noqa: F401 — ensure models are registered with SQLAlchemy

    from app.routes.main import main_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify(
            success=False,
            error={"code": "BAD_REQUEST", "message": str(error.description if hasattr(error, "description") else error)},
        ), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(
            success=False,
            error={"code": "NOT_FOUND", "message": "Ressource introuvable."},
        ), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify(
            success=False,
            error={"code": "METHOD_NOT_ALLOWED", "message": "Méthode non autorisée."},
        ), 405

    @app.errorhandler(422)
    def unprocessable(error):
        return jsonify(
            success=False,
            error={"code": "VALIDATION_ERROR", "message": str(error.description)},
        ), 422

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unhandled server error")
        return jsonify(
            success=False,
            error={"code": "INTERNAL_ERROR", "message": "Erreur interne du serveur."},
        ), 500
