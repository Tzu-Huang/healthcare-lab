from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional in minimal test envs
    def load_dotenv(*_args, **_kwargs):
        return False

from backend.config import (
    DCM4CHEE_AUTH_MODES,
    DCM4CHEE_PROFILE_NAME,
    MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS,
    coerce_config_bool,
    coerce_config_int,
    dcm4chee_archive_dicomweb_url_from_base,
    dcm4chee_profile_from_config,
    load_application_config,
    normalize_gdt_bridge_success_mode,
    normalize_gdt_filename_profile,
    parse_app_host,
    parse_app_port,
    parse_config_bool,
)
from backend.clients.medplum import (
    MedplumAccessToken,
    MedplumAuthManager,
    derive_medplum_token_url,
    normalize_fhir_base_url,
    request_fhir_json,
    request_fhir_raw,
)
from backend.clients import dcm4chee as dcm4chee_client
from backend.clients import oie as oie_client
from backend.clients.openemr import OpenEMRProcedureOrderSource
from backend.clients.health import (
    DOCKER_COMPOSE_APPLICATION_URLS,
    run_http_smoke,
    run_lab_application_check,
    run_tcp_smoke,
    smoke_step,
)
from backend.api.oie import create_oie_blueprint
from backend.api.lab_servers import create_lab_servers_blueprint
from backend.api.dashboard import create_dashboard_blueprint
from backend.api.dcm4chee import create_dcm4chee_profile_blueprint
from backend.api.patients import create_patients_blueprint
from backend.api.orders import create_orders_blueprint
from backend.api.fhir import create_fhir_blueprint
from backend.api.gdt import create_gdt_blueprint
from backend.api.home import create_home_blueprint
from backend.services.patient_workflow import (
    PatientWorkflowService,
    dcm4chee_result_refresh_generation as _dcm4chee_result_refresh_generation,
    refresh_patient_dcm4chee_results,
    sync_patient_to_dcm4chee,
)
from backend.services.order_workflow import (
    OrderWorkflowService,
    dcm4chee_patient_payload_from_mwl_payload,
    ensure_dcm4chee_patient_for_mwl_payload,
    sync_order_to_dcm4chee_mwl,
    verify_order_dcm4chee_mwl,
)
from backend.services.oie_workflow import (
    OieWorkflowService,
    accept_oie_result_payload,
    build_hl7_ack,
    mllp_frame,
    mllp_unframe,
    parse_hl7_ack,
    parse_oru_summary,
)
from backend.services.gdt_workflow import (
    GdtWorkflowService,
    discover_gdt_inbound_candidates,
    gdt_collision_safe_path,
    gdt_file_is_stable,
    gdt_filename_binding_matches,
    gdt_has_supported_exchange_extension,
    gdt_inbound_sort_key,
    gdt_is_internal_or_temp_file,
    gdt_path_status,
    import_gdt_bridge_files,
)
from backend.services.fhir_workflow import (
    FhirWorkflowService,
    MEDPLUM_INVENTORY_RESOURCE_TYPES,
    fetch_fhir_diagnostic_report_bundle,
    fetch_fhir_service_requests,
    first_fhir_bundle_resource,
    medplum_inventory_record,
    medplum_create_resource_url,
    medplum_identifier_search_url,
    medplum_reference_resource_url,
    medplum_resource_reference,
    medplum_update_resource_url,
    sync_fhir_workflow_record_to_medplum,
)
from backend.domain.errors import UpstreamDcm4cheeError, UpstreamFhirError, ValidationError
from backend.domain.validation import require_http_url
from backend.domain.dicom import validate_dcm4chee_profile
from backend.domain import fhir as fhir_domain
from backend.runtime.gdt_bridge_watcher import GdtBridgeInboundWatcher as RuntimeGdtBridgeInboundWatcher
from backend.runtime.oie_result_listener import OieResultListener as RuntimeOieResultListener
from backend.services.oie_settings import OieSettingsService
from backend.services.lab_workflow import (
    DashboardWorkflowService,
    LabServerWorkflowService,
    dashboard_all_group_items,
    dashboard_child_item,
    dashboard_events,
    dashboard_group_item,
    decorate_lab_operation_availability,
    derive_lab_overall_status,
    resolve_lab_operator,
    run_dashboard_group_health_check,
    run_lab_operation,
    run_lab_server_health_check,
    run_lab_smoke_check,
)
from backend.lab_store import (
    DCM4CHEE_MWL_OPERATION_CREATE,
    DCM4CHEE_MWL_OPERATION_VERIFY,
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    DCM4CHEE_PATIENT_SYNC_OPERATION_PREFLIGHT,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
    DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS,
    DCM4CHEE_MWL_VERIFICATION_FAILED,
    DCM4CHEE_MWL_VERIFICATION_VERIFIED,
    DCM4CHEE_MWL_OPERATION_READBACK,
    DCM4CHEE_RESULT_STATUS_DUPLICATE,
    DCM4CHEE_RESULT_STATUS_NO_RESULT,
    DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
    DemoStore,
    LAB_OPERATION_ACTIONS,
    LAB_HEALTH_STATUSES,
    LAB_SERVER_PROTOCOLS,
    LAB_SERVER_TYPES,
    HL7_V2_MSH_SUFFIX,
    FHIR_SYNC_STATUS_FAILED,
    FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCED,
    OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ERROR,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_TRANSPORT_ERROR,
    SimulatorValidationError,
    ensure_gdt_bridge_dirs,
    parse_openemr_allowed_procedure_codes,
    validate_gdt_bridge_dirs,
)
from backend.lab_operations import (
    DockerComposeLabOperationAdapter,
    DockerSocketLabOperationAdapter,
    LabOperationError,
)
from backend.dashboard_services import (
    LAB_DASHBOARD_SERVICE_GROUPS,
    collect_dashboard_resource_snapshot,
    dashboard_action_for_group,
    dashboard_child_for_group,
    dashboard_health_rank,
    dashboard_operation_services,
    dashboard_servers_for_group,
    dashboard_summary,
    derive_dashboard_group_status,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

# Compatibility exports for existing integrations and test patch seams.
OieResultListener = RuntimeOieResultListener
GdtBridgeInboundWatcher = RuntimeGdtBridgeInboundWatcher
send_hl7_mllp_message = oie_client.send_hl7_mllp_message
operation_outcome_from_payload = fhir_domain.operation_outcome_from_payload
operation_outcome_from_error = fhir_domain.operation_outcome_from_error
http_status_from_upstream_error = fhir_domain.http_status_from_upstream_error


def dcm4chee_result_refresh_generation() -> str:
    """Compatibility wrapper for callers that patch the legacy app module."""
    return _dcm4chee_result_refresh_generation(
        clock=datetime.now,
        identifier_factory=uuid.uuid4,
    )


# Compatibility exports: implementation ownership is in ``backend.clients``.
request_dcm4chee_mwl_create = dcm4chee_client.request_dcm4chee_mwl_create
dcm4chee_archive_rs_base_url = dcm4chee_client.dcm4chee_archive_rs_base_url
request_dcm4chee_patient_search = dcm4chee_client.request_dcm4chee_patient_search
request_dcm4chee_patient_create = dcm4chee_client.request_dcm4chee_patient_create
request_dcm4chee_mwl_readback = dcm4chee_client.request_dcm4chee_mwl_readback
request_dcm4chee_mwl_verification = dcm4chee_client.request_dcm4chee_mwl_verification
request_dcm4chee_qido = dcm4chee_client.request_dcm4chee_qido




def create_app(database_path: str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "frontend" / "templates"),
        static_folder=str(PROJECT_ROOT / "frontend" / "static"),
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.config.update(load_application_config(app.instance_path, database_path))
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    store = DemoStore(app.config["DATABASE_PATH"])
    gdt_bridge_watcher = GdtBridgeInboundWatcher(
        store,
        app.config["GDT_BRIDGE_PATH"],
        import_gdt_bridge_files,
        poll_seconds=app.config["GDT_BRIDGE_WATCH_POLL_SECONDS"],
        success_mode=app.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"],
        filename_profile=app.config["GDT_BRIDGE_FILENAME_PROFILE"],
        receiver_id=app.config["GDT_BRIDGE_RECEIVER_ID"],
        sender_id=app.config["GDT_BRIDGE_SENDER_ID"],
        stable_seconds=app.config["GDT_BRIDGE_STABLE_SECONDS"],
    )
    openemr_source = OpenEMRProcedureOrderSource(
        host=app.config["OPENEMR_DB_HOST"],
        port=app.config["OPENEMR_DB_PORT"],
        user=app.config["OPENEMR_DB_USER"],
        password=app.config["OPENEMR_DB_PASSWORD"],
        database=app.config["OPENEMR_DB_NAME"],
        allowed_procedure_codes=app.config["OPENEMR_GDT_PROCEDURE_CODES"],
    )
    app.extensions["demo_store"] = store
    app.extensions["openemr_procedure_order_source"] = openemr_source
    app.extensions["oie_result_listener"] = OieResultListener(
        store.oie_repository, accept_oie_result_payload
    )
    app.extensions["gdt_bridge_watcher"] = gdt_bridge_watcher
    app.extensions["oie_settings_service"] = OieSettingsService(store.oie_settings_repository)
    app.extensions["oie_workflow_service"] = OieWorkflowService(
        store.oie_repository,
        store,
        app.config,
        app.extensions["oie_result_listener"],
        result_handler=accept_oie_result_payload,
        ack_parser=parse_hl7_ack,
        order_sender_provider=lambda: send_hl7_mllp_message,
    )
    app.register_blueprint(
        create_oie_blueprint(
            app.extensions["oie_settings_service"],
            app.extensions["oie_workflow_service"],
        )
    )
    app.register_blueprint(
        create_lab_servers_blueprint(
            LabServerWorkflowService(
                app,
                store.lab_repository,
                health_checker=lambda target_store, server_id: run_lab_server_health_check(
                    target_store, server_id
                ),
                availability_decorator=decorate_lab_operation_availability,
                operation_runner=lambda **values: run_lab_operation(**values),
                operator_resolver=lambda: resolve_lab_operator(),
            )
        )
    )
    app.register_blueprint(
        create_dashboard_blueprint(
            DashboardWorkflowService(
                app,
                store,
                health_check=lambda target_store, service_id: run_dashboard_group_health_check(
                    target_store,
                    service_id,
                    health_checker=lambda health_store, server_id: run_lab_server_health_check(
                        health_store, server_id
                    ),
                ),
                operation_runner=lambda **values: run_lab_operation(**values),
            )
        )
    )
    def get_auth_manager() -> MedplumAuthManager:
        return MedplumAuthManager(
            client_id=app.config["MEDPLUM_CLIENT_ID"],
            client_secret=app.config["MEDPLUM_CLIENT_SECRET"],
            scope=app.config["MEDPLUM_SCOPE"],
            token_url=app.config["MEDPLUM_TOKEN_URL"],
            refresh_grace_seconds=app.config["MEDPLUM_AUTH_GRACE_SECONDS"],
        )

    def get_openemr_source() -> OpenEMRProcedureOrderSource:
        return app.extensions["openemr_procedure_order_source"]

    def configured_medplum_base_url() -> str:
        medplum = next(
            (item for item in store.list_lab_servers() if item["name"] == "Medplum"),
            None,
        )
        return str((medplum or {}).get("baseUrl") or "").strip()

    def configured_dicom_patient_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return sync_patient_to_dcm4chee(
            *args,
            sender=send_hl7_mllp_message,
            **kwargs,
        )

    def configured_dicom_order_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return sync_order_to_dcm4chee_mwl(
            *args,
            patient_syncer=configured_dicom_patient_sync,
            **kwargs,
        )

    app.register_blueprint(
        create_dcm4chee_profile_blueprint(
            app.config,
            profile_builder=dcm4chee_profile_from_config,
            profile_validator=validate_dcm4chee_profile,
        )
    )
    app.register_blueprint(
        create_patients_blueprint(
            PatientWorkflowService(
                store,
                app.config,
                medplum_base_url=configured_medplum_base_url,
                auth_manager=get_auth_manager,
                fhir_sync=sync_fhir_workflow_record_to_medplum,
                dicom_patient_sync=configured_dicom_patient_sync,
                dcm_result_refresh=refresh_patient_dcm4chee_results,
                dcm_profile=dcm4chee_profile_from_config,
            )
        )
    )
    app.register_blueprint(
        create_orders_blueprint(
            OrderWorkflowService(
                store,
                app.config,
                medplum_base_url=configured_medplum_base_url,
                auth_manager=get_auth_manager,
                fhir_sync=sync_fhir_workflow_record_to_medplum,
                dcm_sync=configured_dicom_order_sync,
                dcm_verify=verify_order_dcm4chee_mwl,
                dcm_profile=dcm4chee_profile_from_config,
            )
        )
    )
    app.register_blueprint(
        create_fhir_blueprint(
            FhirWorkflowService(
                store,
                inventory_types=MEDPLUM_INVENTORY_RESOURCE_TYPES,
                medplum_base_url=configured_medplum_base_url,
                auth_manager=get_auth_manager,
                inventory_mapper=medplum_inventory_record,
                diagnostic_fetcher=fetch_fhir_diagnostic_report_bundle,
                base_url_normalizer=normalize_fhir_base_url,
                reference_url_builder=medplum_reference_resource_url,
                json_request=request_fhir_json,
                operation_outcome=operation_outcome_from_payload,
                upstream_status=http_status_from_upstream_error,
                record_sync=sync_fhir_workflow_record_to_medplum,
            )
        )
    )
    app.register_blueprint(
        create_gdt_blueprint(
            GdtWorkflowService(
                store,
                app.config,
                app.extensions["gdt_bridge_watcher"],
                is_internal_file=gdt_is_internal_or_temp_file,
                has_supported_extension=gdt_has_supported_exchange_extension,
                filename_binding_matches=gdt_filename_binding_matches,
                bridge_importer=import_gdt_bridge_files,
            )
        )
    )
    app.register_blueprint(create_home_blueprint(app.config))

    return app


app = create_app()


def main() -> None:
    app.run(host=parse_app_host(), port=parse_app_port(), debug=False)


if __name__ == "__main__":
    main()
