"""Фабрика Flask-приложения для варианта 27."""

import tomllib
from hmac import compare_digest
from pathlib import Path

from flask import Flask, current_app, request
from werkzeug.exceptions import HTTPException

from .jobs import Renderer
from .routes import api
from .service import Service, ServiceError
from .store import TinyStore
from .xml_api import error_xml

UNAUTHORIZED = 401


def create_app(config_path="config.toml"):
    """Загрузить TOML и создать HTTP API с файловой базой TinyDB."""
    with Path(config_path).open("rb") as stream:
        config = tomllib.load(stream)
    settings = config["service"]
    app = Flask(__name__)
    app.config.update(
        API_USER=config["auth"]["username"],
        API_PASSWORD=config["auth"]["password"],
        MAX_CONTENT_LENGTH=settings["max_xml_bytes"],
    )
    store = TinyStore(settings["database"])
    jobs = Service(
        store, Renderer(settings["test_mode"], settings["timeout"]),
        Path(settings["output_dir"]).resolve(), settings["workers"],
    )
    jobs.resume()
    app.extensions["jobs"] = jobs
    app.register_blueprint(api)
    app.before_request(authenticate)
    app.register_error_handler(ServiceError, service_error)
    app.register_error_handler(HTTPException, http_error)
    return app


def authenticate():
    """Проверить HTTP Basic credentials до обработки маршрута."""
    auth = request.authorization
    conf = current_app.config
    if auth and auth.type == "basic":
        user_ok = _equal(auth.username, conf["API_USER"])
        password_ok = _equal(auth.password, conf["API_PASSWORD"])
        if user_ok and password_ok:
            return None
    response = error_xml("Требуется HTTP Basic-аутентификация", UNAUTHORIZED)
    response.headers["WWW-Authenticate"] = (
        'Basic realm="EAN-13", charset="UTF-8"'
    )
    return response


def _equal(value, expected):
    return compare_digest((value or "").encode(), expected.encode())


def service_error(error):
    """Вернуть прикладную ошибку в XML."""
    return error_xml(str(error), error.status)


def http_error(error):
    """Вернуть стандартную ошибку Flask в XML."""
    return error_xml(error.name, error.code)
