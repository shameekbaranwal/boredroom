"""JSON errors: `fail(404, "no such board")` anywhere in a request."""
from __future__ import annotations

from typing import NoReturn

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


class ApiError(HTTPException):
    def __init__(self, status: int, message: str):
        super().__init__(description=message)
        self.code = status


def fail(status: int, message: str) -> NoReturn:
    raise ApiError(status, message)


def register(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def _json(e: HTTPException):
        return jsonify({"error": e.description}), e.code
