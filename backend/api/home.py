"""Dashboard shell route and template helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, render_template


def create_home_blueprint(configuration: Mapping[str, Any]) -> Blueprint:
    blueprint = Blueprint("home", __name__)

    @blueprint.app_context_processor
    def inject_asset_helpers():
        def static_asset_version(filename: str) -> str:
            asset_path = Path(current_app.static_folder or "") / filename
            try:
                return str(asset_path.stat().st_mtime_ns)
            except OSError:
                return "0"

        return {"asset_version": static_asset_version}

    @blueprint.get("/")
    def index():
        return render_template(
            "index.html",
            project_mode=configuration["PROJECT_MODE"],
            oie_order_host=configuration["OIE_MLLP_ORDER_HOST"],
            oie_order_port=configuration["OIE_MLLP_ORDER_PORT"],
            oie_result_host=configuration["OIE_MLLP_RESULT_HOST"],
            oie_result_port=configuration["OIE_MLLP_RESULT_PORT"],
        )

    return blueprint
