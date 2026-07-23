"""Application-facing typed settings bootstrap, mutation, and effective reads."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Mapping, Protocol

from backend.domain.integration_settings import (
    DCM4CHEE_PROFILE_TYPE,
    DCM4CHEE_SECRET_FIELDS,
    MEDPLUM_PROFILE_TYPE,
    PROFILE_SECRET_FIELDS,
    SecretMutation,
    SettingsValidationIssue,
    TypedSettingsValidationError,
    dcm4chee_bootstrap_candidate,
    medplum_bootstrap_candidate,
    preserve_secret,
    remove_secret,
    replace_secret,
    validate_profile,
)
from backend.domain.gdt_bridge_profile import (
    GDT_BRIDGE_PROFILE_TYPE,
    gdt_bridge_bootstrap_candidate,
)
from backend.domain.errors import SimulatorValidationError
from backend.services.oie_settings import OieSettingsService

OIE_PROFILE_TYPE = "oie"
OIE_PUBLIC_FIELDS = frozenset(
    {
        "profileName",
        "managementApi",
        "resultListener",
        "managedChannels",
        "createdAt",
        "updatedAt",
    }
)
OIE_MANAGEMENT_FIELDS = frozenset(
    {"baseUrl", "username", "passwordConfigured", "tlsVerify", "timeoutSeconds"}
)
OIE_RESULT_LISTENER_FIELDS = frozenset(
    {"host", "port", "mllpFraming", "autoStart"}
)
OIE_MANAGED_CHANNEL_FIELDS = frozenset(
    {
        "logicalType",
        "channelId",
        "channelName",
        "templateVersion",
        "lastKnownRevision",
        "sourceHost",
        "sourcePort",
        "destinationHost",
        "destinationPort",
        "timeoutSeconds",
        "queueEnabled",
        "retryCount",
        "retryIntervalMs",
    }
)


class IntegrationSettingsRepositoryPort(Protocol):
    def migrate_medplum_profile(self) -> bool: ...
    def create_if_missing(self, profile, *, secrets, bootstrap_source, actor="startup-bootstrap") -> bool: ...
    def get_private(self, profile_type: str) -> dict[str, Any]: ...
    def list_audits(self, profile_type: str) -> list[dict[str, Any]]: ...
    def replace(self, profile, *, secret_mutations, actor="local-operator") -> dict[str, Any]: ...
    def has_dcm4chee_dependencies(self) -> bool: ...


class OieSettingsAdapter:
    """Adapt the specialized OIE profile without replacing its persistence model."""

    def __init__(self, service: OieSettingsService, repository: Any) -> None:
        self._service = service
        self._repository = repository

    def get_public(self) -> dict[str, Any]:
        profile = self._service.get_profile()
        management = profile.get("managementApi", {})
        configured = bool(management.get("passwordConfigured"))
        return {
            "profileType": OIE_PROFILE_TYPE,
            "profileName": profile.get("profileName", "local-oie"),
            "schemaVersion": 1,
            "fields": profile,
            "secrets": {"managementApi.password": {"configured": configured}},
        }

    def get_effective(self) -> dict[str, Any]:
        return {
            "profileType": OIE_PROFILE_TYPE,
            "managementApi": dict(
                self._repository.get_management_api_configuration()
            ),
            "resultListener": dict(
                self._repository.get_result_listener_configuration()
            ),
            "managedChannels": self._service.get_profile().get(
                "managedChannels", []
            ),
        }

    def replace(
        self,
        fields: Mapping[str, Any],
        *,
        secret_replacements: Mapping[str, Any],
    ) -> dict[str, Any]:
        field_issues = _unknown_oie_field_issues(fields)
        unknown_secrets = sorted(
            set(secret_replacements) - {"managementApi.password"}
        )
        if field_issues or unknown_secrets:
            raise TypedSettingsValidationError(
                field_issues
                + [
                    SettingsValidationIssue(
                        f"secrets.{field}",
                        "unknown_field",
                        "The secret field is not supported.",
                    )
                    for field in unknown_secrets
                ]
            )
        payload = dict(fields)
        management = dict(payload.get("managementApi") or {})
        replacement = secret_replacements.get("managementApi.password")
        if replacement is not None and str(replacement).strip():
            management["password"] = str(replacement)
        else:
            management.pop("password", None)
        payload["managementApi"] = management
        try:
            self._service.update_profile(payload)
        except SimulatorValidationError as exc:
            raise _typed_oie_validation_error(str(exc)) from exc
        return self.get_public()

    def remove_secret(self, field: str) -> dict[str, Any]:
        if field != "managementApi.password":
            raise TypedSettingsValidationError(
                [
                    SettingsValidationIssue(
                        f"secrets.{field}",
                        "unknown_field",
                        "The secret field is not supported.",
                    )
                ]
            )
        self._service.remove_management_api_password()
        return self.get_public()


def _unknown_oie_field_issues(
    fields: Mapping[str, Any],
) -> list[SettingsValidationIssue]:
    paths = [str(field) for field in set(fields) - OIE_PUBLIC_FIELDS]
    management = fields.get("managementApi")
    if isinstance(management, Mapping):
        paths.extend(
            f"managementApi.{field}"
            for field in set(management) - OIE_MANAGEMENT_FIELDS
        )
    listener = fields.get("resultListener")
    if isinstance(listener, Mapping):
        paths.extend(
            f"resultListener.{field}"
            for field in set(listener) - OIE_RESULT_LISTENER_FIELDS
        )
    channels = fields.get("managedChannels")
    if isinstance(channels, list):
        for index, channel in enumerate(channels):
            if not isinstance(channel, Mapping):
                continue
            paths.extend(
                f"managedChannels[{index}].{field}"
                for field in set(channel) - OIE_MANAGED_CHANNEL_FIELDS
            )
    return [
        SettingsValidationIssue(
            path,
            "unknown_field",
            "The field is not supported.",
        )
        for path in sorted(paths)
    ]


def _typed_oie_validation_error(message: str) -> TypedSettingsValidationError:
    field = "fields"
    mappings = (
        ("baseUrl", "managementApi.baseUrl"),
        ("username", "managementApi.username"),
        ("password", "managementApi.password"),
        ("timeoutSeconds", "managementApi.timeoutSeconds"),
        ("tlsVerify", "managementApi.tlsVerify"),
        ("resultListener host", "resultListener.host"),
        ("resultListener port", "resultListener.port"),
        ("mllpFraming", "resultListener.mllpFraming"),
        ("autoStart", "resultListener.autoStart"),
        ("managedChannels", "managedChannels"),
        ("managementApi", "managementApi"),
    )
    channel_path = re.search(r"managedChannels\[\d+\](?:\.[A-Za-z]+)?", message)
    if channel_path:
        field = channel_path.group(0)
    else:
        for token, path in mappings:
            if token in message:
                field = path
                break
    return TypedSettingsValidationError(
        [
            SettingsValidationIssue(
                field,
                "invalid_value",
                "The field value is invalid.",
            )
        ]
    )


@dataclass(frozen=True, repr=False)
class MedplumEffectiveSettings:
    base_url: str
    web_ui_url: str
    client_id: str
    client_secret: str
    scope: str
    token_url: str
    auth_grace_seconds: int
    timeout_seconds: int
    enabled: bool

    def __repr__(self) -> str:
        return (
            "MedplumEffectiveSettings("
            f"base_url={self.base_url!r}, web_ui_url={self.web_ui_url!r}, "
            f"client_id={self.client_id!r}, "
            f"client_secret_configured={bool(self.client_secret)!r}, "
            f"scope={self.scope!r}, token_url={self.token_url!r}, "
            f"auth_grace_seconds={self.auth_grace_seconds!r}, "
            f"timeout_seconds={self.timeout_seconds!r}, enabled={self.enabled!r})"
        )


@dataclass(frozen=True)
class GdtBridgeEffectiveSettings:
    enabled: bool
    bridge_path: str
    receiver_id: str
    sender_id: str
    filename_profile: str
    success_mode: str
    poll_seconds: float
    stable_seconds: float


@dataclass(frozen=True, repr=False)
class Dcm4cheeEffectiveSettings:
    profile: dict[str, Any]
    secrets: dict[str, str]

    @property
    def enabled(self) -> bool:
        return bool(self.profile["enabled"])

    @property
    def uid_root(self) -> str:
        return str(self.profile["uidRoot"])

    def __repr__(self) -> str:
        return (
            "Dcm4cheeEffectiveSettings("
            f"profile_name={self.profile.get('profileName')!r}, "
            f"enabled={self.enabled!r}, "
            f"configured_secrets={sorted(key for key, value in self.secrets.items() if value)!r})"
        )


class IntegrationSettingsService:
    def __init__(
        self,
        repository: IntegrationSettingsRepositoryPort,
        *,
        oie_adapter: OieSettingsAdapter | None = None,
    ) -> None:
        self._repository = repository
        self._oie = oie_adapter

    def bootstrap_medplum(self, configuration: Mapping[str, Any]) -> bool:
        self._repository.migrate_medplum_profile()
        profile = medplum_bootstrap_candidate(configuration)
        return self._repository.create_if_missing(
            profile,
            secrets={"clientSecret": str(configuration.get("MEDPLUM_CLIENT_SECRET", ""))},
            bootstrap_source="legacy-environment-and-inventory",
        )

    def bootstrap_gdt_bridge(self, configuration: Mapping[str, Any]) -> bool:
        return self._repository.create_if_missing(
            gdt_bridge_bootstrap_candidate(configuration),
            secrets={},
            bootstrap_source="legacy-environment",
        )

    def bootstrap_dcm4chee(self, configuration: Mapping[str, Any]) -> bool:
        secret_names = {
            "password": "DCM4CHEE_PASSWORD",
            "token": "DCM4CHEE_TOKEN",
            "clientSecret": "DCM4CHEE_CLIENT_SECRET",
        }
        return self._repository.create_if_missing(
            dcm4chee_bootstrap_candidate(configuration),
            secrets={
                field: str(configuration.get(config_name, ""))
                for field, config_name in secret_names.items()
                if str(configuration.get(config_name, ""))
            },
            bootstrap_source="legacy-environment",
        )

    def has_operator_configuration(self, profile_type: str) -> bool:
        if profile_type == OIE_PROFILE_TYPE:
            return True
        return any(
            item["operation"] != "bootstrap"
            for item in self._repository.list_audits(profile_type)
        )

    def get_public(self, profile_type: str) -> dict[str, Any]:
        if profile_type == OIE_PROFILE_TYPE and self._oie is not None:
            return self._oie.get_public()
        private = self._repository.get_private(profile_type)
        public = {
            "profileType": private["profileType"],
            "profileName": private["profileName"],
            "schemaVersion": private["schemaVersion"],
            "fields": private["fields"],
            "secrets": {
                field: {"configured": bool(private["secrets"].get(field))}
                for field in sorted(PROFILE_SECRET_FIELDS[profile_type])
            },
        }
        if profile_type == DCM4CHEE_PROFILE_TYPE:
            security = private["fields"].get("security", {})
            public["references"] = {
                field: self._mounted_reference_projection(security.get(field))
                for field in ("certificatePath", "privateKeyPath")
            }
        return public

    @staticmethod
    def _mounted_reference_projection(value: Any) -> dict[str, bool]:
        path = str(value or "").strip()
        return {
            "configured": bool(path),
            "readable": bool(path and os.path.isfile(path) and os.access(path, os.R_OK)),
        }

    def get_effective(self, profile_type: str) -> Any:
        if profile_type == OIE_PROFILE_TYPE and self._oie is not None:
            return self._oie.get_effective()
        if profile_type == GDT_BRIDGE_PROFILE_TYPE:
            private = self._repository.get_private(profile_type)
            fields = private["fields"]
            return GdtBridgeEffectiveSettings(
                enabled=bool(fields["enabled"]),
                bridge_path=str(fields["applicationPath"]),
                receiver_id=str(fields["receiverId"]),
                sender_id=str(fields["senderId"]),
                filename_profile=str(fields["filenameProfile"]),
                success_mode=str(fields["importSuccessMode"]),
                poll_seconds=float(fields["pollSeconds"]),
                stable_seconds=float(fields["stableSeconds"]),
            )
        if profile_type == DCM4CHEE_PROFILE_TYPE:
            private = self._repository.get_private(profile_type)
            return Dcm4cheeEffectiveSettings(
                profile=dict(private["fields"]),
                secrets={
                    field: str(private["secrets"].get(field, ""))
                    for field in DCM4CHEE_SECRET_FIELDS
                },
            )
        if profile_type != MEDPLUM_PROFILE_TYPE:
            raise KeyError(profile_type)
        private = self._repository.get_private(profile_type)
        fields = private["fields"]
        return MedplumEffectiveSettings(
            base_url=str(fields["baseUrl"]),
            web_ui_url=str(fields["webUiUrl"]),
            client_id=str(fields["clientId"]),
            client_secret=str(private["secrets"].get("clientSecret", "")),
            scope=str(fields["scope"]),
            token_url=str(fields["tokenUrl"]),
            auth_grace_seconds=int(fields["authGraceSeconds"]),
            timeout_seconds=int(fields["timeoutSeconds"]),
            enabled=bool(fields["enabled"]),
        )

    def replace(
        self,
        profile_type: str,
        fields: Mapping[str, Any],
        *,
        secret_replacements: Mapping[str, Any] | None = None,
        actor: str = "local-operator",
    ) -> dict[str, Any]:
        if profile_type == OIE_PROFILE_TYPE and self._oie is not None:
            return self._oie.replace(
                fields, secret_replacements=secret_replacements or {}
            )
        profile = validate_profile(profile_type, fields)
        if profile_type == DCM4CHEE_PROFILE_TYPE:
            self._validate_dcm4chee_mutation(profile.fields, secret_replacements or {})
        mutations: dict[str, SecretMutation] = (
            {"clientSecret": preserve_secret()}
            if profile_type == MEDPLUM_PROFILE_TYPE
            else {}
        )
        for field, value in (secret_replacements or {}).items():
            mutations[field] = replace_secret(value)
        self._repository.replace(
            profile, secret_mutations=mutations, actor=actor
        )
        return self.get_public(profile_type)

    def _validate_dcm4chee_mutation(
        self,
        fields: Mapping[str, Any],
        replacements: Mapping[str, Any],
    ) -> None:
        previous = self._repository.get_private(DCM4CHEE_PROFILE_TYPE)
        previous_fields = previous["fields"]
        identity_paths = (
            ("profileName",),
            ("uidRoot",),
            ("hl7", "patientAssigningAuthority"),
        )
        changed_identity = any(
            self._nested_value(previous_fields, path) != self._nested_value(fields, path)
            for path in identity_paths
        )
        if changed_identity and self._repository.has_dcm4chee_dependencies():
            raise TypedSettingsValidationError(
                [
                    SettingsValidationIssue(
                        "profileName",
                        "identity_migration_required",
                        "Profile identity cannot change while dependent DICOM records exist.",
                    )
                ]
            )
        effective_secrets = dict(previous["secrets"])
        effective_secrets.update(
            {
                field: str(value)
                for field, value in replacements.items()
                if str(value).strip()
            }
        )
        auth_mode = str(fields.get("security", {}).get("authMode", "none"))
        security = fields.get("security", {})
        for field in ("certificatePath", "privateKeyPath"):
            reference = str(security.get(field, "")).strip()
            if reference and not (
                os.path.isfile(reference) and os.access(reference, os.R_OK)
            ):
                raise TypedSettingsValidationError(
                    [
                        SettingsValidationIssue(
                            f"security.{field}",
                            "unreadable_mounted_reference",
                            "The mounted reference is not readable by the application.",
                        )
                    ]
                )
        required_secret = {
            "basic": "password",
            "bearer": "token",
            "oauth2": "clientSecret",
        }.get(auth_mode)
        if required_secret and not effective_secrets.get(required_secret):
            raise TypedSettingsValidationError(
                [
                    SettingsValidationIssue(
                        f"secrets.{required_secret}",
                        "required_for_auth_mode",
                        "A configured secret is required for the selected authentication mode.",
                    )
                ]
            )
        for field in replacements:
            if field not in DCM4CHEE_SECRET_FIELDS:
                raise TypedSettingsValidationError(
                    [
                        SettingsValidationIssue(
                            f"secrets.{field}",
                            "unknown_field",
                            "The secret field is not supported.",
                        )
                    ]
                )

    @staticmethod
    def _nested_value(values: Mapping[str, Any], path: tuple[str, ...]) -> Any:
        value: Any = values
        for part in path:
            value = value.get(part) if isinstance(value, Mapping) else None
        return value

    def remove_secret(
        self,
        profile_type: str,
        field: str,
        *,
        actor: str = "local-operator",
    ) -> dict[str, Any]:
        if profile_type == OIE_PROFILE_TYPE:
            if self._oie is None:
                raise KeyError(profile_type)
            return self._oie.remove_secret(field)
        private = self._repository.get_private(profile_type)
        profile = validate_profile(profile_type, private["fields"])
        self._repository.replace(
            profile,
            secret_mutations={field: remove_secret()},
            actor=actor,
        )
        return self.get_public(profile_type)
