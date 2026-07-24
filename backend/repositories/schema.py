"""Healthcare Lab application schema and additive SQLite migrations."""

from __future__ import annotations

import sqlite3

from backend.domain.patient import CANONICAL_MRN_PATTERN
from backend.repositories.database import Migration

TABLE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lab_servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    server_type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    host TEXT NOT NULL DEFAULT '',
    port INTEGER,
    base_url TEXT NOT NULL DEFAULT '',
    protocol TEXT NOT NULL DEFAULT 'None',
    enabled INTEGER NOT NULL DEFAULT 1,
    version TEXT NOT NULL DEFAULT '',
    check_config_json TEXT NOT NULL DEFAULT '{}',
    control_type TEXT NOT NULL DEFAULT '',
    backing_service TEXT NOT NULL DEFAULT '',
    supported_actions_json TEXT NOT NULL DEFAULT '[]',
    operation_timeout_seconds INTEGER NOT NULL DEFAULT 60,
    smoke_profile TEXT NOT NULL DEFAULT '',
    overall_status TEXT NOT NULL DEFAULT 'Unknown',
    process_status TEXT NOT NULL DEFAULT 'Unknown',
    application_status TEXT NOT NULL DEFAULT 'Unknown',
    protocol_status TEXT NOT NULL DEFAULT 'Unknown',
    last_check_at TEXT NOT NULL DEFAULT '',
    recent_error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lab_operation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    server_id INTEGER,
    service_name TEXT NOT NULL,
    action TEXT NOT NULL,
    operator TEXT NOT NULL,
    result TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    progress_json TEXT NOT NULL DEFAULT '[]',
    error_text TEXT NOT NULL DEFAULT '',
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    FOREIGN KEY(server_id) REFERENCES lab_servers(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS local_identifier_sequences (
    name TEXT PRIMARY KEY,
    next_value INTEGER NOT NULL CHECK(next_value > 0)
);
CREATE TABLE IF NOT EXISTS local_patient_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_patient_number TEXT NOT NULL UNIQUE,
    protocol_version TEXT NOT NULL,
    message_type TEXT NOT NULL,
    mrn TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    middle_name TEXT NOT NULL DEFAULT '',
    dob TEXT NOT NULL,
    sex TEXT NOT NULL,
    address TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    fhir_active INTEGER NOT NULL DEFAULT 1,
    address_line TEXT NOT NULL DEFAULT '',
    address_city TEXT NOT NULL DEFAULT '',
    address_state TEXT NOT NULL DEFAULT '',
    address_postal_code TEXT NOT NULL DEFAULT '',
    address_country TEXT NOT NULL DEFAULT '',
    managing_organization_reference TEXT NOT NULL DEFAULT '',
    managing_organization_display TEXT NOT NULL DEFAULT '',
    visit_number TEXT NOT NULL,
    patient_class TEXT NOT NULL DEFAULT 'O',
    assigned_location TEXT NOT NULL DEFAULT '',
    attending_provider TEXT NOT NULL DEFAULT '',
    account_number TEXT NOT NULL DEFAULT '',
    validation_status TEXT NOT NULL,
    validation_messages_json TEXT NOT NULL DEFAULT '[]',
    payload_hl7 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_order_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_order_number TEXT NOT NULL UNIQUE,
    patient_record_id INTEGER NOT NULL,
    protocol_version TEXT NOT NULL,
    message_type TEXT NOT NULL,
    order_status TEXT NOT NULL,
    mrn TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    middle_name TEXT NOT NULL DEFAULT '',
    dob TEXT NOT NULL,
    sex TEXT NOT NULL,
    visit_id TEXT NOT NULL,
    patient_class TEXT NOT NULL DEFAULT 'O',
    assigned_location TEXT NOT NULL DEFAULT '',
    account_number TEXT NOT NULL DEFAULT '',
    placer_order_number TEXT NOT NULL,
    filler_order_number TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'R',
    requested_at TEXT NOT NULL,
    scheduled_at TEXT NOT NULL DEFAULT '',
    ordering_provider TEXT NOT NULL,
    clinical_indication TEXT NOT NULL DEFAULT '',
    order_code TEXT NOT NULL,
    order_code_text TEXT NOT NULL,
    alternate_code TEXT NOT NULL DEFAULT '',
    alternate_code_text TEXT NOT NULL DEFAULT '',
    alternate_code_system TEXT NOT NULL DEFAULT '',
    validation_status TEXT NOT NULL,
    validation_messages_json TEXT NOT NULL DEFAULT '[]',
    payload_hl7 TEXT NOT NULL,
    ack_code TEXT NOT NULL DEFAULT '',
    ack_control_id TEXT NOT NULL DEFAULT '',
    ack_text TEXT NOT NULL DEFAULT '',
    ack_payload TEXT NOT NULL DEFAULT '',
    transport_error TEXT NOT NULL DEFAULT '',
    last_sent_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS oie_result_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_control_id TEXT NOT NULL DEFAULT '',
    message_type TEXT NOT NULL,
    patient_mrn TEXT NOT NULL DEFAULT '',
    placer_order_number TEXT NOT NULL DEFAULT '',
    filler_order_number TEXT NOT NULL DEFAULT '',
    matched_patient_record_id INTEGER,
    matched_order_record_id INTEGER,
    match_status TEXT NOT NULL,
    duplicate_of_id INTEGER,
    parse_status TEXT NOT NULL,
    error_text TEXT NOT NULL DEFAULT '',
    payload_hl7 TEXT NOT NULL,
    received_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(matched_patient_record_id) REFERENCES local_patient_records(id) ON DELETE SET NULL,
    FOREIGN KEY(matched_order_record_id) REFERENCES local_order_records(id) ON DELETE SET NULL,
    FOREIGN KEY(duplicate_of_id) REFERENCES oie_result_records(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS oie_settings_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL UNIQUE,
    management_api_base_url TEXT NOT NULL,
    management_api_username TEXT NOT NULL,
    management_api_password TEXT NOT NULL,
    management_api_tls_verify INTEGER NOT NULL DEFAULT 0,
    management_api_timeout_seconds REAL NOT NULL,
    result_listener_host TEXT NOT NULL,
    result_listener_port INTEGER NOT NULL,
    result_listener_mllp_framing INTEGER NOT NULL DEFAULT 1,
    result_listener_auto_start INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS oie_managed_channel_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    logical_type TEXT NOT NULL,
    oie_channel_id TEXT NOT NULL DEFAULT '',
    channel_name TEXT NOT NULL,
    template_version TEXT NOT NULL DEFAULT '',
    last_known_revision TEXT NOT NULL DEFAULT '',
    desired_config_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES oie_settings_profiles(id) ON DELETE CASCADE,
    UNIQUE(profile_id, logical_type)
);
CREATE TABLE IF NOT EXISTS oie_managed_channel_lifecycle_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    operation_id TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'local-operator',
    operation TEXT NOT NULL,
    logical_type TEXT NOT NULL,
    oie_channel_id TEXT NOT NULL DEFAULT '',
    before_revision TEXT NOT NULL DEFAULT '',
    after_revision TEXT NOT NULL DEFAULT '',
    classification TEXT NOT NULL DEFAULT '',
    outcome TEXT NOT NULL,
    error_category TEXT NOT NULL DEFAULT '',
    changed_fields_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES oie_settings_profiles(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS oie_settings_mutation_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    actor TEXT NOT NULL DEFAULT 'local-operator',
    operation TEXT NOT NULL,
    changed_fields_json TEXT NOT NULL DEFAULT '[]',
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES oie_settings_profiles(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS integration_settings_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_type TEXT NOT NULL UNIQUE,
    profile_name TEXT NOT NULL,
    schema_version INTEGER NOT NULL CHECK(schema_version > 0),
    public_payload_json TEXT NOT NULL,
    bootstrap_source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS integration_settings_secrets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    secret_value TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES integration_settings_profiles(id) ON DELETE CASCADE,
    UNIQUE(profile_id, field_name)
);
CREATE TABLE IF NOT EXISTS integration_settings_mutation_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    actor TEXT NOT NULL,
    operation TEXT NOT NULL,
    changed_fields_json TEXT NOT NULL DEFAULT '[]',
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES integration_settings_profiles(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ap_device_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key TEXT NOT NULL UNIQUE,
    profile_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    environment TEXT NOT NULL,
    enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
    is_default INTEGER NOT NULL DEFAULT 0 CHECK(is_default IN (0, 1)),
    schema_version INTEGER NOT NULL DEFAULT 1 CHECK(schema_version > 0),
    payload_json TEXT NOT NULL,
    bootstrap_source TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ap_device_profile_audits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    actor TEXT NOT NULL DEFAULT 'local-operator',
    operation TEXT NOT NULL,
    changed_fields_json TEXT NOT NULL DEFAULT '[]',
    outcome TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES ap_device_profiles(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS ap_device_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    protocol TEXT NOT NULL,
    direction TEXT NOT NULL,
    outcome_code TEXT NOT NULL,
    correlation_key TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES ap_device_profiles(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS local_gdt_order_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_gdt_order_number TEXT NOT NULL UNIQUE,
    patient_record_id INTEGER NOT NULL,
    gdt_patient_context_id INTEGER,
    protocol_version TEXT NOT NULL,
    message_type TEXT NOT NULL,
    order_status TEXT NOT NULL,
    mrn TEXT NOT NULL,
    gdt_patient_number TEXT NOT NULL DEFAULT '',
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    middle_name TEXT NOT NULL DEFAULT '',
    dob TEXT NOT NULL,
    sex TEXT NOT NULL,
    visit_number TEXT NOT NULL DEFAULT '',
    gdt_test_code TEXT NOT NULL,
    gdt_test_label TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    ordering_provider TEXT NOT NULL DEFAULT '',
    clinical_indication TEXT NOT NULL DEFAULT '',
    attachment_url TEXT NOT NULL DEFAULT '',
    payload_gdt TEXT NOT NULL,
    patient_snapshot_json TEXT NOT NULL DEFAULT '{}',
    order_snapshot_json TEXT NOT NULL DEFAULT '{}',
    export_path TEXT NOT NULL DEFAULT '',
    error_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(gdt_patient_context_id) REFERENCES local_gdt_patient_contexts(id) ON DELETE SET NULL,
    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS local_gdt_patient_contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_record_id INTEGER NOT NULL UNIQUE,
    generated_gdt_patient_number TEXT NOT NULL UNIQUE,
    gdt_patient_number_override TEXT NOT NULL DEFAULT '',
    effective_gdt_patient_number TEXT NOT NULL UNIQUE,
    patient_snapshot_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS local_gdt_message_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_record_id INTEGER,
    patient_context_id INTEGER,
    direction TEXT NOT NULL,
    message_type TEXT NOT NULL,
    raw_gdt_text TEXT NOT NULL,
    parsed_fields_json TEXT NOT NULL DEFAULT '{}',
    canonical_json TEXT NOT NULL DEFAULT '{}',
    parse_status TEXT NOT NULL,
    match_status TEXT NOT NULL DEFAULT '',
    error_text TEXT NOT NULL DEFAULT '',
    generated_at TEXT NOT NULL DEFAULT '',
    received_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(order_record_id) REFERENCES local_gdt_order_records(id) ON DELETE SET NULL,
    FOREIGN KEY(patient_context_id) REFERENCES local_gdt_patient_contexts(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS local_gdt_attachment_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_record_id INTEGER,
    message_record_id INTEGER,
    role TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    path TEXT NOT NULL DEFAULT '',
    reference TEXT NOT NULL DEFAULT '',
    content_type TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    source_file TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    filename TEXT NOT NULL DEFAULT '',
    checksum TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(order_record_id) REFERENCES local_gdt_order_records(id) ON DELETE SET NULL,
    FOREIGN KEY(message_record_id) REFERENCES local_gdt_message_records(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS local_gdt_workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_record_id INTEGER,
    patient_context_id INTEGER,
    message_record_id INTEGER,
    attachment_record_id INTEGER,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(order_record_id) REFERENCES local_gdt_order_records(id) ON DELETE SET NULL,
    FOREIGN KEY(patient_context_id) REFERENCES local_gdt_patient_contexts(id) ON DELETE SET NULL,
    FOREIGN KEY(message_record_id) REFERENCES local_gdt_message_records(id) ON DELETE SET NULL,
    FOREIGN KEY(attachment_record_id) REFERENCES local_gdt_attachment_records(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS local_fhir_workflow_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    local_fhir_record_number TEXT NOT NULL UNIQUE,
    local_source_type TEXT NOT NULL,
    local_source_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    identifier_system TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    resource_json TEXT NOT NULL,
    dependency_json TEXT NOT NULL DEFAULT '[]',
    medplum_resource_id TEXT NOT NULL DEFAULT '',
    medplum_resource_reference TEXT NOT NULL DEFAULT '',
    sync_status TEXT NOT NULL,
    sync_error TEXT NOT NULL DEFAULT '',
    operation_outcome_json TEXT NOT NULL DEFAULT '{}',
    last_sync_at TEXT NOT NULL DEFAULT '',
    sync_started_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_fhir_sync_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fhir_record_id INTEGER NOT NULL,
    method TEXT NOT NULL,
    request_url TEXT NOT NULL,
    request_payload_json TEXT NOT NULL DEFAULT '{}',
    http_status INTEGER,
    response_payload_json TEXT NOT NULL DEFAULT '{}',
    operation_outcome_json TEXT NOT NULL DEFAULT '{}',
    error_text TEXT NOT NULL DEFAULT '',
    attempted_at TEXT NOT NULL,
    FOREIGN KEY(fhir_record_id) REFERENCES local_fhir_workflow_records(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS local_dcm4chee_mwl_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mapping_id INTEGER,
    operation_type TEXT NOT NULL DEFAULT 'create',
    order_record_id INTEGER NOT NULL,
    profile_name TEXT NOT NULL,
    server_identity TEXT NOT NULL,
    mwl_ae_title TEXT NOT NULL,
    scheduled_station_ae_title TEXT NOT NULL,
    local_dcm4chee_order_number TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    requested_procedure_id TEXT NOT NULL,
    scheduled_procedure_step_id TEXT NOT NULL,
    study_instance_uid TEXT NOT NULL,
    uid_root TEXT NOT NULL,
    request_url TEXT NOT NULL,
    request_payload_json TEXT NOT NULL DEFAULT '{}',
    http_status INTEGER,
    response_body TEXT NOT NULL DEFAULT '',
    attempt_status TEXT NOT NULL,
    error_type TEXT NOT NULL DEFAULT '',
    error_text TEXT NOT NULL DEFAULT '',
    attempted_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(mapping_id) REFERENCES local_dcm4chee_mwl_mappings(id) ON DELETE SET NULL,
    FOREIGN KEY(order_record_id) REFERENCES local_order_records(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS local_dcm4chee_mwl_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_record_id INTEGER NOT NULL UNIQUE,
    profile_name TEXT NOT NULL,
    server_identity TEXT NOT NULL,
    mwl_ae_title TEXT NOT NULL,
    scheduled_station_ae_title TEXT NOT NULL,
    local_dcm4chee_order_number TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    issuer_of_patient_id TEXT NOT NULL,
    accession_number TEXT NOT NULL,
    requested_procedure_id TEXT NOT NULL,
    scheduled_procedure_step_id TEXT NOT NULL,
    study_instance_uid TEXT NOT NULL,
    worklist_label TEXT NOT NULL,
    uid_root TEXT NOT NULL,
    sync_status TEXT NOT NULL,
    last_sync_at TEXT NOT NULL DEFAULT '',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_id INTEGER,
    last_http_status INTEGER,
    last_response_body TEXT NOT NULL DEFAULT '',
    last_error_type TEXT NOT NULL DEFAULT '',
    last_error_text TEXT NOT NULL DEFAULT '',
    last_error_payload_json TEXT NOT NULL DEFAULT '{}',
    latest_request_payload_json TEXT NOT NULL DEFAULT '{}',
    latest_readback_payload_json TEXT NOT NULL DEFAULT '{}',
    verification_status TEXT NOT NULL DEFAULT 'not_verified',
    last_verification_at TEXT NOT NULL DEFAULT '',
    last_verification_method TEXT NOT NULL DEFAULT '',
    last_verification_attempt_id INTEGER,
    last_verification_query_json TEXT NOT NULL DEFAULT '{}',
    last_verification_match_json TEXT NOT NULL DEFAULT '{}',
    last_verification_error_type TEXT NOT NULL DEFAULT '',
    last_verification_error_text TEXT NOT NULL DEFAULT '',
    last_verification_error_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(order_record_id) REFERENCES local_order_records(id) ON DELETE CASCADE,
    FOREIGN KEY(last_attempt_id) REFERENCES local_dcm4chee_mwl_attempts(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS local_dcm4chee_result_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_key TEXT NOT NULL UNIQUE,
    patient_record_id INTEGER,
    order_record_id INTEGER,
    mapping_id INTEGER,
    profile_name TEXT NOT NULL DEFAULT '',
    server_identity TEXT NOT NULL DEFAULT '',
    source_ae_title TEXT NOT NULL DEFAULT '',
    study_instance_uid TEXT NOT NULL DEFAULT '',
    series_instance_uid TEXT NOT NULL DEFAULT '',
    sop_instance_uid TEXT NOT NULL DEFAULT '',
    accession_number TEXT NOT NULL DEFAULT '',
    patient_id TEXT NOT NULL DEFAULT '',
    issuer_of_patient_id TEXT NOT NULL DEFAULT '',
    requested_procedure_id TEXT NOT NULL DEFAULT '',
    scheduled_procedure_step_id TEXT NOT NULL DEFAULT '',
    modality TEXT NOT NULL DEFAULT '',
    study_datetime TEXT NOT NULL DEFAULT '',
    series_datetime TEXT NOT NULL DEFAULT '',
    instance_datetime TEXT NOT NULL DEFAULT '',
    viewer_url TEXT NOT NULL DEFAULT '',
    study_retrieve_url TEXT NOT NULL DEFAULT '',
    series_retrieve_url TEXT NOT NULL DEFAULT '',
    instance_retrieve_url TEXT NOT NULL DEFAULT '',
    reconciliation_status TEXT NOT NULL DEFAULT '',
    match_method TEXT NOT NULL DEFAULT '',
    match_strength TEXT NOT NULL DEFAULT '',
    query_url TEXT NOT NULL DEFAULT '',
    query_payload_json TEXT NOT NULL DEFAULT '{}',
    diagnostic_payload_json TEXT NOT NULL DEFAULT '{}',
    raw_metadata_json TEXT NOT NULL DEFAULT '{}',
    refresh_generation TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_refreshed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE SET NULL,
    FOREIGN KEY(order_record_id) REFERENCES local_order_records(id) ON DELETE SET NULL,
    FOREIGN KEY(mapping_id) REFERENCES local_dcm4chee_mwl_mappings(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS local_dcm4chee_result_refresh_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_record_id INTEGER NOT NULL,
    refresh_generation TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT '',
    results_snapshot_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE CASCADE,
    UNIQUE(patient_record_id, refresh_generation)
);
CREATE TABLE IF NOT EXISTS local_dcm4chee_patient_syncs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_record_id INTEGER NOT NULL,
    profile_name TEXT NOT NULL,
    server_identity TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    issuer_of_patient_id TEXT NOT NULL,
    hl7_host TEXT NOT NULL,
    hl7_port INTEGER NOT NULL,
    receiving_application TEXT NOT NULL,
    receiving_facility TEXT NOT NULL,
    sync_status TEXT NOT NULL,
    last_sync_at TEXT NOT NULL DEFAULT '',
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_attempt_id INTEGER,
    last_ack_code TEXT NOT NULL DEFAULT '',
    last_ack_control_id TEXT NOT NULL DEFAULT '',
    last_ack_text TEXT NOT NULL DEFAULT '',
    last_response_payload TEXT NOT NULL DEFAULT '',
    last_error_type TEXT NOT NULL DEFAULT '',
    last_error_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE CASCADE,
    FOREIGN KEY(last_attempt_id) REFERENCES local_dcm4chee_patient_sync_attempts(id) ON DELETE SET NULL,
    UNIQUE(patient_record_id, profile_name, server_identity)
);
CREATE TABLE IF NOT EXISTS local_dcm4chee_patient_sync_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_sync_id INTEGER,
    operation_type TEXT NOT NULL,
    patient_record_id INTEGER NOT NULL,
    profile_name TEXT NOT NULL,
    server_identity TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    issuer_of_patient_id TEXT NOT NULL,
    request_url TEXT NOT NULL,
    request_payload TEXT NOT NULL DEFAULT '',
    response_payload TEXT NOT NULL DEFAULT '',
    ack_code TEXT NOT NULL DEFAULT '',
    ack_control_id TEXT NOT NULL DEFAULT '',
    ack_text TEXT NOT NULL DEFAULT '',
    attempt_status TEXT NOT NULL,
    error_type TEXT NOT NULL DEFAULT '',
    error_text TEXT NOT NULL DEFAULT '',
    attempted_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(patient_sync_id) REFERENCES local_dcm4chee_patient_syncs(id) ON DELETE SET NULL,
    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE CASCADE
);
"""

INDEX_SCHEMA_SQL = """
CREATE UNIQUE INDEX IF NOT EXISTS idx_oie_result_control_id
ON oie_result_records(message_control_id)
WHERE message_control_id != '';
CREATE INDEX IF NOT EXISTS idx_oie_managed_channel_profile
ON oie_managed_channel_mappings(profile_id, logical_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_oie_managed_channel_profile_channel
ON oie_managed_channel_mappings(profile_id, oie_channel_id)
WHERE oie_channel_id != '';
CREATE INDEX IF NOT EXISTS idx_oie_lifecycle_audit_profile_created
ON oie_managed_channel_lifecycle_audits(profile_id, created_at, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_oie_lifecycle_audit_operation
ON oie_managed_channel_lifecycle_audits(profile_id, operation_id);
CREATE INDEX IF NOT EXISTS idx_integration_settings_audit_profile_created
ON integration_settings_mutation_audits(profile_id, created_at, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ap_device_default_environment
ON ap_device_profiles(environment) WHERE is_default = 1;
CREATE INDEX IF NOT EXISTS idx_ap_device_environment
ON ap_device_profiles(environment, enabled, profile_name);
CREATE INDEX IF NOT EXISTS idx_ap_device_audit_profile_created
ON ap_device_profile_audits(profile_id, created_at, id);
CREATE INDEX IF NOT EXISTS idx_ap_device_observation_profile_created
ON ap_device_observations(profile_id, observed_at, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fhir_record_identifier
ON local_fhir_workflow_records(resource_type, identifier_system, identifier_value);
CREATE INDEX IF NOT EXISTS idx_fhir_record_source
ON local_fhir_workflow_records(local_source_type, local_source_id);
CREATE INDEX IF NOT EXISTS idx_fhir_record_sync_status
ON local_fhir_workflow_records(sync_status);
CREATE INDEX IF NOT EXISTS idx_fhir_attempt_record
ON local_fhir_sync_attempts(fhir_record_id, attempted_at);
CREATE INDEX IF NOT EXISTS idx_dcm4chee_mwl_attempt_order
ON local_dcm4chee_mwl_attempts(order_record_id, attempted_at);
CREATE INDEX IF NOT EXISTS idx_dcm4chee_mwl_mapping_study_uid
ON local_dcm4chee_mwl_mappings(study_instance_uid)
WHERE study_instance_uid != '';
CREATE INDEX IF NOT EXISTS idx_dcm4chee_mwl_mapping_accession
ON local_dcm4chee_mwl_mappings(profile_name, server_identity, accession_number)
WHERE accession_number != '';
CREATE INDEX IF NOT EXISTS idx_dcm4chee_mwl_mapping_procedure
ON local_dcm4chee_mwl_mappings(
    profile_name, server_identity, requested_procedure_id, scheduled_procedure_step_id
)
WHERE requested_procedure_id != '' AND scheduled_procedure_step_id != '';
CREATE INDEX IF NOT EXISTS idx_dcm4chee_result_patient
ON local_dcm4chee_result_records(patient_record_id, last_refreshed_at);
CREATE INDEX IF NOT EXISTS idx_dcm4chee_result_mapping
ON local_dcm4chee_result_records(mapping_id);
CREATE INDEX IF NOT EXISTS idx_dcm4chee_result_generation
ON local_dcm4chee_result_records(patient_record_id, refresh_generation)
WHERE refresh_generation != '';
CREATE INDEX IF NOT EXISTS idx_dcm4chee_result_refresh_run_patient
ON local_dcm4chee_result_refresh_runs(patient_record_id, id);
CREATE INDEX IF NOT EXISTS idx_dcm4chee_patient_sync_patient
ON local_dcm4chee_patient_syncs(patient_record_id);
CREATE INDEX IF NOT EXISTS idx_dcm4chee_patient_sync_identifier
ON local_dcm4chee_patient_syncs(profile_name, server_identity, patient_id, issuer_of_patient_id);
CREATE INDEX IF NOT EXISTS idx_dcm4chee_patient_sync_attempt_patient
ON local_dcm4chee_patient_sync_attempts(patient_record_id, attempted_at);
"""

ADDITIVE_COLUMNS = (
    ("local_order_records", "scheduled_at", "TEXT NOT NULL DEFAULT ''"),
    ("oie_managed_channel_mappings", "desired_config_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("lab_servers", "control_type", "TEXT NOT NULL DEFAULT ''"),
    ("lab_servers", "backing_service", "TEXT NOT NULL DEFAULT ''"),
    ("lab_servers", "supported_actions_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("lab_servers", "operation_timeout_seconds", "INTEGER NOT NULL DEFAULT 60"),
    ("lab_servers", "smoke_profile", "TEXT NOT NULL DEFAULT ''"),
    ("local_dcm4chee_mwl_attempts", "mapping_id", "INTEGER"),
    ("local_dcm4chee_mwl_attempts", "operation_type", "TEXT NOT NULL DEFAULT 'create'"),
    ("local_dcm4chee_mwl_mappings", "verification_status", "TEXT NOT NULL DEFAULT 'not_verified'"),
    ("local_dcm4chee_mwl_mappings", "last_verification_at", "TEXT NOT NULL DEFAULT ''"),
    ("local_dcm4chee_mwl_mappings", "last_verification_method", "TEXT NOT NULL DEFAULT ''"),
    ("local_dcm4chee_mwl_mappings", "last_verification_attempt_id", "INTEGER"),
    ("local_dcm4chee_mwl_mappings", "last_verification_query_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("local_dcm4chee_mwl_mappings", "last_verification_match_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("local_dcm4chee_mwl_mappings", "last_verification_error_type", "TEXT NOT NULL DEFAULT ''"),
    ("local_dcm4chee_mwl_mappings", "last_verification_error_text", "TEXT NOT NULL DEFAULT ''"),
    ("local_dcm4chee_mwl_mappings", "last_verification_error_payload_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("local_dcm4chee_result_records", "refresh_generation", "TEXT NOT NULL DEFAULT ''"),
    ("local_dcm4chee_result_refresh_runs", "completed_at", "TEXT NOT NULL DEFAULT ''"),
    ("local_dcm4chee_result_refresh_runs", "results_snapshot_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("local_patient_records", "email", "TEXT NOT NULL DEFAULT ''"),
    ("local_patient_records", "fhir_active", "INTEGER NOT NULL DEFAULT 1"),
    ("local_patient_records", "address_line", "TEXT NOT NULL DEFAULT ''"),
    ("local_patient_records", "address_city", "TEXT NOT NULL DEFAULT ''"),
    ("local_patient_records", "address_state", "TEXT NOT NULL DEFAULT ''"),
    ("local_patient_records", "address_postal_code", "TEXT NOT NULL DEFAULT ''"),
    ("local_patient_records", "address_country", "TEXT NOT NULL DEFAULT ''"),
    ("local_patient_records", "managing_organization_reference", "TEXT NOT NULL DEFAULT ''"),
    ("local_patient_records", "managing_organization_display", "TEXT NOT NULL DEFAULT ''"),
    ("local_gdt_order_records", "gdt_patient_context_id", "INTEGER"),
    ("local_gdt_order_records", "gdt_patient_number", "TEXT NOT NULL DEFAULT ''"),
    ("local_gdt_order_records", "patient_snapshot_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("local_gdt_order_records", "order_snapshot_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("local_gdt_attachment_records", "reference", "TEXT NOT NULL DEFAULT ''"),
    ("local_gdt_attachment_records", "description", "TEXT NOT NULL DEFAULT ''"),
    ("local_gdt_attachment_records", "source_file", "TEXT NOT NULL DEFAULT ''"),
    ("local_gdt_attachment_records", "status", "TEXT NOT NULL DEFAULT ''"),
    ("local_gdt_attachment_records", "details_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("local_fhir_workflow_records", "dependency_json", "TEXT NOT NULL DEFAULT '[]'"),
    ("local_fhir_workflow_records", "sync_started_at", "TEXT NOT NULL DEFAULT ''"),
)


def execute_sql_script(connection: sqlite3.Connection, script: str) -> None:
    """Execute complete statements without sqlite3.executescript implicit commits."""
    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            sql = statement.strip()
            if sql:
                connection.execute(sql)
            statement = ""
    if statement.strip():
        raise ValueError("Schema script ended with an incomplete SQL statement.")


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name in columns:
        return
    try:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
        )
    except sqlite3.OperationalError as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def create_application_tables(connection: sqlite3.Connection) -> None:
    execute_sql_script(connection, TABLE_SCHEMA_SQL)


def add_legacy_columns(connection: sqlite3.Connection) -> None:
    for table_name, column_name, definition in ADDITIVE_COLUMNS:
        ensure_column(connection, table_name, column_name, definition)


def create_application_indexes(connection: sqlite3.Connection) -> None:
    execute_sql_script(connection, INDEX_SCHEMA_SQL)


def ensure_application_schema(connection: sqlite3.Connection) -> None:
    """Repair missing application objects even when a legacy ledger exists."""
    create_application_tables(connection)
    add_legacy_columns(connection)
    create_application_indexes(connection)


def enforce_normalized_patient_mrn_uniqueness(connection: sqlite3.Connection) -> None:
    duplicates = connection.execute(
        """
        SELECT UPPER(TRIM(mrn)) AS normalized_mrn,
               GROUP_CONCAT(id) AS patient_ids,
               GROUP_CONCAT(mrn, ' | ') AS stored_values
        FROM local_patient_records
        GROUP BY UPPER(TRIM(mrn))
        HAVING COUNT(*) > 1
        ORDER BY normalized_mrn
        """
    ).fetchall()
    if duplicates:
        details = "; ".join(
            f"{row['normalized_mrn']} (patient ids {row['patient_ids']}: {row['stored_values']})"
            for row in duplicates
        )
        raise RuntimeError(
            "Cannot enforce canonical Patient MRN uniqueness; resolve normalized duplicates: "
            + details
        )
    rows = connection.execute("SELECT id, mrn FROM local_patient_records").fetchall()
    for row in rows:
        stored_mrn = str(row["mrn"] or "")
        normalized_mrn = stored_mrn.strip().upper()
        if (
            normalized_mrn != stored_mrn
            and CANONICAL_MRN_PATTERN.fullmatch(normalized_mrn)
        ):
            connection.execute(
                "UPDATE local_patient_records SET mrn = ? WHERE id = ?",
                (normalized_mrn, row["id"]),
            )
    connection.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_patient_mrn_normalized
        ON local_patient_records(UPPER(TRIM(mrn)))
        """
    )


APPLICATION_MIGRATIONS = (
    Migration(1, "create-application-tables", create_application_tables),
    Migration(2, "add-legacy-columns", add_legacy_columns),
    Migration(3, "create-application-indexes", create_application_indexes),
    Migration(4, "add-oie-managed-channel-lifecycle-audits", ensure_application_schema),
    Migration(5, "add-oie-managed-channel-desired-config", ensure_application_schema),
    Migration(6, "add-order-scheduled-time", ensure_application_schema),
    Migration(7, "enforce-normalized-patient-mrn-uniqueness", enforce_normalized_patient_mrn_uniqueness),
    Migration(8, "add-oie-bootstrap-operational-status", ensure_application_schema),
    Migration(9, "add-typed-integration-settings", ensure_application_schema),
    Migration(10, "add-ap-external-device-profiles", ensure_application_schema),
)
