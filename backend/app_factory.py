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
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
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
from backend.api.integration_settings import create_integration_settings_blueprint
from backend.api.settings_readiness import create_settings_readiness_blueprint
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
from backend.services.medplum_runtime import MedplumRuntimeProvider
from backend.services.coordination import (
    ConfiguredWorkflowOperations,
    OrderProtocolCoordinator,
    PatientProtocolCoordinator,
)
from backend.services.oie_workflow import (
    OieInventoryCoordination,
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
from backend.domain.errors import SimulatorValidationError, UpstreamDcm4cheeError, UpstreamFhirError, ValidationError
from backend.domain.validation import require_http_url
from backend.domain.dicom import validate_dcm4chee_profile
from backend.domain import dicom as dicom_domain
from backend.domain import fhir as fhir_domain
from backend.templates import dicom as dicom_templates
from backend.runtime.gdt_bridge_watcher import GdtBridgeInboundWatcher as RuntimeGdtBridgeInboundWatcher
from backend.runtime.oie_result_listener import OieResultListener as RuntimeOieResultListener
from backend.runtime.lazy_wsgi import LazyWsgiApplication
from backend.services.oie_settings import OieSettingsService, create_oie_management_client
from backend.services.oie_diagnostics import OieRuntimeDiagnosticService
from backend.settings_readiness_composition import create_settings_readiness_service
from backend.services.oie_channel_lifecycle import OieManagedChannelLifecycleService, PreviewTokenCodec
from backend.services.oie_channel_bootstrap import OieManagedChannelBootstrap
from backend.application_composition import assemble_application_dependencies
from backend.lab_composition import LabApplicationRepository, dashboard_services, lab_server_services
from backend.services.lab_workflow import (
    dashboard_all_group_items,
    dashboard_child_item,
    dashboard_events,
    dashboard_group_item,
    dashboard_summary,
    derive_lab_overall_status,
    decorate_lab_operation_availability,
    run_lab_smoke_check,
    run_lab_operation,
    run_lab_server_health_check,
)
from backend.domain.statuses import (
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
    FHIR_SYNC_STATUS_FAILED,
    FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCED,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ERROR,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_TRANSPORT_ERROR,
)
from backend.domain.gdt import ensure_gdt_bridge_dirs
from backend.domain.lab import LAB_HEALTH_STATUSES, LAB_OPERATION_ACTIONS, LAB_SERVER_PROTOCOLS, LAB_SERVER_TYPES
from backend.domain.openemr import OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES, parse_openemr_allowed_procedure_codes
from backend.domain.order import ORDER_PROTOCOL_VERSION
from backend.domain.patient import PATIENT_MODES
from backend.domain.timestamps import hl7_timestamp, now_iso
from backend.repositories.gdt_bridge_health import validate_gdt_bridge_dirs
from backend.templates.hl7 import HL7_V2_MSH_SUFFIX
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
def create_app(database_path: str | None = None, *, dependency_receiver: Callable[[object], None] | None = None, order_coordination_receiver: Callable[[object], None] | None = None, activate_runtime: bool = True, bootstrap_thread_factory: Callable[..., object] | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "frontend" / "templates"),
        static_folder=str(PROJECT_ROOT / "frontend" / "static"),
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.config.update(load_application_config(app.instance_path, database_path))
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    dependencies = assemble_application_dependencies(
        app.config["DATABASE_PATH"], configuration=dict(app.config)
    )
    if dependency_receiver is not None:
        dependency_receiver(dependencies)
    fhir_ledger = dependencies.fhir_ledger
    patient_fhir = dependencies.patient_fhir
    order_fhir = dependencies.order_fhir
    gdt_workflow = dependencies.gdt_workflow
    patient_coordination = PatientProtocolCoordinator(
        begin_dcm4chee_result_refresh=dependencies.dcm4chee_result_repository.begin_dcm4chee_result_refresh,
        build_dcm4chee_patient_adt_payload=lambda patient, profile, **kwargs: dicom_templates.build_patient_adt_payload(patient, profile, timestamp_factory=hl7_timestamp, **kwargs),
        complete_dcm4chee_result_refresh=dependencies.dcm4chee_result_repository.complete_dcm4chee_result_refresh,
        create_dcm4chee_e2e_demo_fixture=dependencies.dcm4chee_workflow_coordinator.create_dcm4chee_e2e_demo_fixture,
        create_dcm4chee_patient_sync_attempt=dependencies.dcm4chee_patient_sync_repository.create_dcm4chee_patient_sync_attempt,
        create_patient_fhir_workflow_record=patient_fhir.create_patient_fhir_workflow_record,
        dcm4chee_datasets_from_response_body=dicom_domain.datasets_from_response_body,
        dcm4chee_result_metadata_from_dataset=dicom_domain.result_metadata_from_dataset,
        get_dcm4chee_patient_sync_for_patient=dependencies.dcm4chee_patient_sync_repository.get_dcm4chee_patient_sync_for_patient,
        get_patient_record=dependencies.patient_repository.get_patient_record,
        get_fhir_workflow_record=fhir_ledger.get_fhir_workflow_record,
        list_dcm4chee_mwl_mappings_for_patient=dependencies.dcm4chee_mwl_repository.list_dcm4chee_mwl_mappings_for_patient,
        mark_fhir_sync_failure=fhir_ledger.mark_fhir_sync_failure,
        mark_fhir_sync_success=fhir_ledger.mark_fhir_sync_success,
        mark_fhir_syncing=fhir_ledger.mark_fhir_syncing,
        record_fhir_sync_attempt=fhir_ledger.record_fhir_sync_attempt,
        record_dcm4chee_result_refresh_diagnostic=dependencies.dcm4chee_result_repository.record_dcm4chee_result_refresh_diagnostic,
        update_dcm4chee_patient_sync_attempt_result=dependencies.dcm4chee_patient_sync_repository.update_dcm4chee_patient_sync_attempt_result,
        update_dcm4chee_patient_sync_from_attempt=dependencies.dcm4chee_patient_sync_repository.update_dcm4chee_patient_sync_from_attempt,
        upsert_dcm4chee_patient_sync=dependencies.dcm4chee_patient_sync_repository.upsert_dcm4chee_patient_sync,
        upsert_dcm4chee_result_record=dependencies.dcm4chee_result_repository.upsert_dcm4chee_result_record,
    )
    order_coordination = OrderProtocolCoordinator(
        build_dcm4chee_mwl_payload=lambda order, profile, **kwargs: dicom_templates.build_mwl_payload(order, profile, timestamp_factory=hl7_timestamp, **kwargs),
        create_dcm4chee_mwl_attempt=dependencies.dcm4chee_mwl_attempt_coordinator.create_dcm4chee_mwl_attempt,
        create_dcm4chee_mwl_profile_failure_attempt=dependencies.dcm4chee_mwl_repository.create_dcm4chee_mwl_profile_failure_attempt,
        create_dcm4chee_mwl_verification_attempt=dependencies.dcm4chee_mwl_repository.create_dcm4chee_mwl_verification_attempt,
        create_dcm4chee_order_record=dependencies.order_repository.create_dcm4chee_order_record,
        create_fhir_order_record=order_fhir.create_fhir_order_record,
        create_order_service_request_fhir_workflow_record=order_fhir.create_order_service_request_fhir_workflow_record,
        create_simulated_dcm4chee_ap_return=dependencies.dcm4chee_workflow_coordinator.create_simulated_dcm4chee_ap_return,
        dcm4chee_datasets_from_response_body=dicom_domain.datasets_from_response_body,
        dcm4chee_e2e_evidence_for_order=dependencies.dcm4chee_workflow_coordinator.dcm4chee_e2e_evidence_for_order,
        dcm4chee_identifiers_from_dataset=dicom_domain.identifiers_from_dataset,
        dcm4chee_identifiers_from_payload=lambda order, profile, **kwargs: dicom_templates.identifiers_from_payload(order, profile, timestamp_factory=hl7_timestamp, **kwargs),
        dcm4chee_identifiers_from_response_body=dicom_domain.identifiers_from_response_body,
        dcm4chee_mwl_verification_query_from_mapping=dicom_domain.verification_query_from_mapping,
        get_dcm4chee_mwl_mapping_for_order=dependencies.dcm4chee_mwl_repository.get_dcm4chee_mwl_mapping_for_order,
        get_dcm4chee_patient_sync_for_patient=dependencies.dcm4chee_patient_sync_repository.get_dcm4chee_patient_sync_for_patient,
        get_fhir_workflow_record=fhir_ledger.get_fhir_workflow_record,
        get_order_record=dependencies.order_repository.get_order_record,
        get_patient_record=dependencies.patient_repository.get_patient_record,
        list_dcm4chee_mwl_attempts=dependencies.dcm4chee_mwl_repository.list_dcm4chee_mwl_attempts,
        mark_fhir_sync_failure=fhir_ledger.mark_fhir_sync_failure,
        mark_fhir_sync_success=fhir_ledger.mark_fhir_sync_success,
        mark_fhir_syncing=fhir_ledger.mark_fhir_syncing,
        record_fhir_sync_attempt=fhir_ledger.record_fhir_sync_attempt,
        update_dcm4chee_mwl_attempt_result=dependencies.dcm4chee_mwl_repository.update_dcm4chee_mwl_attempt_result,
        update_dcm4chee_mwl_mapping_from_attempt=dependencies.dcm4chee_mwl_repository.update_dcm4chee_mwl_mapping_from_attempt,
        update_dcm4chee_mwl_verification_result=dependencies.dcm4chee_mwl_repository.update_dcm4chee_mwl_verification_result,
        upsert_dcm4chee_mwl_mapping=dependencies.dcm4chee_mwl_repository.upsert_dcm4chee_mwl_mapping,
    )
    if order_coordination_receiver is not None:
        order_coordination_receiver(order_coordination)
    gdt_bridge_watcher = GdtBridgeInboundWatcher(
        gdt_workflow,
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
    lab_operations = LabApplicationRepository(
        dependencies.lab_repository,
        gdt_inventory=dependencies.gdt_repository.list_gdt_orders,
    )
    oie_coordination = OieInventoryCoordination(
        dependencies.patient_repository,
        dependencies.order_repository,
        patient_protocol=PATIENT_MODES["hl7-v2"]["protocol"],
        order_protocol=ORDER_PROTOCOL_VERSION,
    )
    app.extensions["openemr_procedure_order_source"] = openemr_source
    app.extensions["oie_result_listener"] = OieResultListener(
        dependencies.oie_repository, accept_oie_result_payload
    )
    app.extensions["gdt_bridge_watcher"] = gdt_bridge_watcher
    app.extensions["oie_settings_service"] = dependencies.oie_settings_service
    app.extensions["integration_settings_service"] = dependencies.integration_settings_service
    medplum_runtime = MedplumRuntimeProvider(dependencies.integration_settings_service)
    app.extensions["medplum_runtime"] = medplum_runtime
    app.register_blueprint(
        create_integration_settings_blueprint(
            dependencies.integration_settings_service,
            medplum_diagnostics=medplum_runtime.diagnose,
        )
    )
    app.extensions["oie_channel_lifecycle_service"] = OieManagedChannelLifecycleService(
        None, dependencies.oie_settings_repository,
        ap_host=app.config["OIE_MANAGED_AP_HOST"],
        token_codec=PreviewTokenCodec(secrets.token_bytes(32)),
        client_provider=lambda: create_oie_management_client(dependencies.oie_settings_repository),
    )
    app.extensions["oie_channel_bootstrap"] = OieManagedChannelBootstrap(
        app.extensions["oie_channel_lifecycle_service"],
        timeout_seconds=app.config["OIE_BOOTSTRAP_TIMEOUT_SECONDS"],
        retry_interval_seconds=app.config["OIE_BOOTSTRAP_RETRY_INTERVAL_SECONDS"],
    )
    app.extensions["oie_workflow_service"] = OieWorkflowService(
        dependencies.oie_repository,
        oie_coordination,
        app.config,
        app.extensions["oie_result_listener"],
        listener_configuration_source=dependencies.oie_settings_repository,
        result_handler=accept_oie_result_payload,
        ack_parser=parse_hl7_ack,
        order_sender_provider=lambda: send_hl7_mllp_message,
    )
    def managed_oru_channel_id() -> str:
        mappings = dependencies.oie_settings_repository.get().get("managedChannels", [])
        item = next((value for value in mappings if value.get("logicalType") == "hlab-oru-to-hlab"), {})
        return str(item.get("channelId") or "")

    def oie_port_contract() -> dict[str, Any]:
        profile = dependencies.oie_settings_repository.get()
        listener_port = int(profile.get("resultListener", {}).get("port", 6665))
        mappings = profile.get("managedChannels", [])
        source_ports = [int(item["sourcePort"]) for item in mappings if item.get("sourcePort")]
        oru = next((item for item in mappings if item.get("logicalType") == "hlab-oru-to-hlab"), {})
        conflicts = []
        if len(source_ports) != len(set(source_ports)):
            conflicts.append("managed-listener-port-conflict")
        if oru.get("destinationPort") and int(oru["destinationPort"]) != listener_port:
            conflicts.append("oru-destination-listener-mismatch")
        defaults = {"hlab-orm-to-ap": 6600, "hlab-oru-to-hlab": 6661}
        expected_ports = []
        for logical_type, default_port in defaults.items():
            item = next((value for value in mappings if value.get("logicalType") == logical_type), {})
            expected_ports.append({
                "logicalType": logical_type,
                "port": int(item.get("sourcePort") or default_port),
                "channelId": str(item.get("channelId") or ""),
            })
        return {"valid": not conflicts, "conflicts": conflicts, "expectedPorts": expected_ports}

    app.extensions["oie_runtime_diagnostics_service"] = OieRuntimeDiagnosticService(
        management_client=lambda: create_oie_management_client(dependencies.oie_settings_repository),
        listener_status=app.extensions["oie_workflow_service"].listener_status,
        port_contract=oie_port_contract,
        channel_id=managed_oru_channel_id,
    )
    app.extensions["settings_readiness_service"] = create_settings_readiness_service(
        dependencies.integration_settings_service,
        listener_status=app.extensions["oie_workflow_service"].listener_status,
        oie_diagnostics=app.extensions["oie_runtime_diagnostics_service"].diagnose,
    )
    app.register_blueprint(
        create_settings_readiness_blueprint(
            app.extensions["settings_readiness_service"]
        )
    )
    app.register_blueprint(
        create_oie_blueprint(
            app.extensions["oie_settings_service"],
            app.extensions["oie_workflow_service"],
            app.extensions["oie_channel_lifecycle_service"],
            app.extensions["oie_runtime_diagnostics_service"],
        )
    )
    if activate_runtime:
        app.extensions["oie_workflow_service"].auto_start_listener()
        if app.config["OIE_BOOTSTRAP_MODE"] == "create-missing":
            bootstrap_thread = (bootstrap_thread_factory or threading.Thread)(
                target=app.extensions["oie_channel_bootstrap"].run,
                name="oie-managed-channel-bootstrap",
                daemon=True,
            )
            app.extensions["oie_channel_bootstrap_thread"] = bootstrap_thread
            bootstrap_thread.start()
    def configured_lab_health_check(repository, server_id):
        server = repository.get_lab_server(server_id)
        if server.get("name") == "Medplum":
            return run_lab_server_health_check(
                repository,
                server_id,
                medplum_settings_provider=medplum_runtime.settings,
            )
        return run_lab_server_health_check(repository, server_id)

    def configured_lab_inventory(app_context, server):
        item = decorate_lab_operation_availability(app_context, server)
        if item.get("name") == "Medplum":
            settings = medplum_runtime.settings()
            item["baseUrl"] = settings.base_url
            item["webUiUrl"] = settings.web_ui_url
            item["enabled"] = settings.enabled
            item["settingsProfile"] = "medplum"
        return item

    app.register_blueprint(
        create_lab_servers_blueprint(
            *lab_server_services(
                app,
                lab_operations,
                operation_runner=lambda **values: run_lab_operation(
                    **values,
                    medplum_settings_provider=lambda: dependencies.integration_settings_service.get_effective(
                        "medplum"
                    ),
                ),
                health_checker=configured_lab_health_check,
                availability_decorator=configured_lab_inventory,
            )
        )
    )
    app.register_blueprint(
        create_dashboard_blueprint(
            *dashboard_services(
                app,
                lab_operations,
                operation_runner=lambda **values: run_lab_operation(
                    **values,
                    medplum_settings_provider=lambda: dependencies.integration_settings_service.get_effective(
                        "medplum"
                    ),
                ),
                health_checker=configured_lab_health_check,
            )
        )
    )
    def get_auth_manager() -> MedplumAuthManager:
        return medplum_runtime.auth_manager()

    def get_openemr_source() -> OpenEMRProcedureOrderSource:
        return app.extensions["openemr_procedure_order_source"]

    def configured_medplum_base_url() -> str:
        return medplum_runtime.base_url()

    workflow_operations = ConfiguredWorkflowOperations(
        patient=patient_coordination,
        order=order_coordination,
        patient_fhir=patient_fhir,
        order_fhir=order_fhir,
        fhir_ledger=fhir_ledger,
        fhir_sync=sync_fhir_workflow_record_to_medplum,
        patient_sync=sync_patient_to_dcm4chee,
        result_refresh=refresh_patient_dcm4chee_results,
        order_sync=sync_order_to_dcm4chee_mwl,
        order_verify=verify_order_dcm4chee_mwl,
        patient_sender=lambda message, *, host, port, timeout_seconds, framing=True: (
            send_hl7_mllp_message(
                message, host=host, port=port,
                timeout_seconds=timeout_seconds, framing=framing,
            )
        ),
    )

    app.register_blueprint(
        create_dcm4chee_profile_blueprint(
            app.config,
            profile_builder=dcm4chee_profile_from_config,
            profile_validator=validate_dcm4chee_profile,
        )
    )
    patient_service = PatientWorkflowService(
        dependencies.patient_repository,
        app.config,
        fhir_capability=workflow_operations.patient_fhir,
        fixture_capability=workflow_operations.fixture,
        medplum_base_url=configured_medplum_base_url,
        auth_manager=get_auth_manager,
        fhir_sync=workflow_operations.sync_patient_fhir,
        dicom_patient_sync=workflow_operations.sync_patient_dicom,
        dcm_result_refresh=workflow_operations.refresh_results,
        dcm_profile=dcm4chee_profile_from_config,
    )
    app.register_blueprint(create_patients_blueprint(
        patient_service.record_service, patient_service.fhir_sync_service,
        patient_service.result_refresh_service, patient_service.fixture_service,
    ))
    order_service = OrderWorkflowService(
                dependencies.order_repository,
                app.config,
                fhir_capability=workflow_operations.order_fhir,
                dcm_order_capability=workflow_operations.dcm_order,
                evidence_capability=workflow_operations.evidence,
                medplum_base_url=configured_medplum_base_url,
                auth_manager=get_auth_manager,
                fhir_sync=workflow_operations.sync_order_fhir,
                dcm_sync=workflow_operations.sync_order_dicom,
                dcm_verify=workflow_operations.verify_order_dicom,
                dcm_profile=dcm4chee_profile_from_config,
    )
    app.register_blueprint(
        create_orders_blueprint(
            order_service,
            order_service.mwl_sync_service,
            order_service.mwl_verification_service,
            order_service.evidence_service,
        )
    )
    fhir_service = FhirWorkflowService(
                fhir_ledger,
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
    app.register_blueprint(
        create_fhir_blueprint(
            fhir_service.record_service,
            fhir_service.inventory_service,
            fhir_service.preview_service,
            fhir_service.diagnostic_service,
            fhir_service.sync_service,
            fhir_service.operation_outcome,
        )
    )
    gdt_service = GdtWorkflowService(
        gdt_workflow, app.config, app.extensions["gdt_bridge_watcher"],
        is_internal_file=gdt_is_internal_or_temp_file,
        has_supported_extension=gdt_has_supported_exchange_extension,
        filename_binding_matches=gdt_filename_binding_matches,
        bridge_importer=import_gdt_bridge_files,
    )
    app.register_blueprint(create_gdt_blueprint(
        gdt_workflow, gdt_service.bridge_service, gdt_service.result_service,
    ))
    app.register_blueprint(create_home_blueprint(app.config))

    return app


app = LazyWsgiApplication(create_app)


def main() -> None:
    app.run(host=parse_app_host(), port=parse_app_port(), debug=False)


if __name__ == "__main__":
    main()
