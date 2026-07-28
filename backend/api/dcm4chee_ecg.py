"""Result-scoped DICOM ECG HTTP routes."""

from __future__ import annotations

from typing import Any, Protocol

from flask import Blueprint, Response, jsonify

from backend.services.dcm4chee_ecg import Dcm4cheeEcgServiceError


class Dcm4cheeEcgPort(Protocol):
    def metadata(self, result_id: int) -> dict[str, Any]: ...
    def render(self, result_id: int) -> Any: ...


def create_dcm4chee_ecg_blueprint(service: Dcm4cheeEcgPort) -> Blueprint:
    blueprint = Blueprint("dcm4chee_ecg", __name__)

    def failure(exc: Dcm4cheeEcgServiceError):
        return (
            jsonify(
                {
                    "success": False,
                    "error": {"code": exc.code, "message": exc.summary},
                }
            ),
            exc.http_status,
        )

    @blueprint.get("/api/dcm4chee/results/<int:result_id>/ecg")
    def get_ecg_metadata(result_id: int):
        try:
            item = service.metadata(result_id)
        except Dcm4cheeEcgServiceError as exc:
            return failure(exc)
        return jsonify({"success": True, "item": item})

    @blueprint.get("/api/dcm4chee/results/<int:result_id>/ecg/render.svg")
    def render_ecg_svg(result_id: int):
        try:
            rendered = service.render(result_id)
        except Dcm4cheeEcgServiceError as exc:
            return failure(exc)
        return Response(rendered.svg_bytes, status=200, content_type=rendered.media_type)

    return blueprint
