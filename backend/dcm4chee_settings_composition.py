"""Composition helpers for persisted dcm4chee settings and diagnostics."""

from __future__ import annotations

from typing import Any, Callable

from backend.api.dcm4chee_ecg import create_dcm4chee_ecg_blueprint
from backend.clients.dcm4chee_wado import retrieve_dicom_instance
from backend.services.dcm4chee_ecg import Dcm4cheeEcgService
from backend.services.dcm4chee_diagnostics import diagnose_dcm4chee


def dcm4chee_settings_operations(
    settings: Any,
) -> tuple[Callable[..., dict[str, Any]], Callable[[], dict[str, Any]]]:
    def profile(_configuration=None) -> dict[str, Any]:
        return settings.get_effective("dcm4chee").runtime_profile()

    def diagnostics() -> dict[str, Any]:
        current = profile()
        if not current.get("enabled"):
            return {"state": "disabled", "checks": []}
        return diagnose_dcm4chee(current)

    return profile, diagnostics


def dcm4chee_ecg_operations(result_repository: Any, profile_getter: Callable):
    service = Dcm4cheeEcgService(
        result_getter=result_repository.get_dcm4chee_result_record,
        profile_getter=lambda _profile_name: profile_getter(),
        retriever=lambda profile, identifiers: retrieve_dicom_instance(
            profile,
            study_instance_uid=identifiers.study_instance_uid,
            series_instance_uid=identifiers.series_instance_uid,
            sop_instance_uid=identifiers.sop_instance_uid,
        ),
    )
    return create_dcm4chee_ecg_blueprint(service)
