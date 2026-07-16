import inspect
import ast
from dataclasses import replace
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET

from backend.domain.errors import ValidationError
from backend.domain.oie_channels import (
    InitialState,
    ManagedChannelType,
    QueuePolicy,
    UTF8_WIRE_VALUE,
)
from backend.templates.oie_channels import (
    __all__ as public_template_api,
    compile_managed_routes,
    compile_orm_to_ap,
    compile_oru_to_hlab,
    normalized_state,
    normalized_state_from_payload,
    orm_to_ap_config,
    oru_to_hlab_config,
    sanitized_canonical,
)


ROOT = Path(__file__).resolve().parents[2]


class ManagedOieChannelTemplateTests(unittest.TestCase):
    def test_exports_are_oie_452_and_differ_only_in_inventory_fields(self):
        orm = ET.parse(ROOT / "docs" / "Dashboard_to_OIE_to_AP.xml").getroot()
        oru = ET.parse(ROOT / "docs" / "AP_RESULT_TO_LAB.xml").getroot()
        self.assertEqual("4.5.2", orm.get("version"))
        self.assertEqual("4.5.2", oru.get("version"))
        differing_paths = _differing_leaf_paths(orm, oru)
        self.assertEqual(
            {
                "channel/id", "channel/name", "channel/revision",
                "channel/sourceConnector/properties/listenerConnectorProperties/port",
                "channel/destinationConnectors/connector/properties/remoteAddress",
                "channel/destinationConnectors/connector/properties/remotePort",
                "channel/exportData/metadata/lastModified/time",
            },
            differing_paths,
        )

    def test_sanitized_canonical_removes_environment_identity(self):
        payload = sanitized_canonical(ManagedChannelType.ORM_TO_AP)
        for leaked in ("250307ab", "192.168.30.15", "1783931727806", "<userId>", "<lastModified>"):
            self.assertNotIn(leaked, payload)
        self.assertIn("HLAB_ORM_TO_AP", payload)

    def test_generated_payload_preserves_complete_canonical_structure(self):
        canonical = ET.parse(ROOT / "docs" / "Dashboard_to_OIE_to_AP.xml").getroot()
        generated = ET.fromstring(compile_orm_to_ap("ap.internal"))
        self.assertEqual(_structure(canonical), _structure(generated))

    def test_orm_payload_preserves_fixed_topology_and_explicit_utf8(self):
        root = ET.fromstring(compile_orm_to_ap("ap.internal"))
        self.assertEqual("HLAB_ORM_TO_AP", root.findtext("name"))
        self.assertEqual("6600", root.findtext("sourceConnector/properties/listenerConnectorProperties/port"))
        destination = root.find("destinationConnectors/connector")
        self.assertIsNotNone(destination)
        self.assertEqual("ap.internal", destination.findtext("properties/remoteAddress"))
        self.assertEqual("6671", destination.findtext("properties/remotePort"))
        self.assertEqual("false", destination.findtext("properties/destinationConnectorProperties/queueEnabled"))
        self.assertEqual({UTF8_WIRE_VALUE}, {node.text for node in root.findall(".//charsetEncoding")})
        self.assertEqual("TCP Listener", root.findtext("sourceConnector/transportName"))
        self.assertEqual("TCP Sender", destination.findtext("transportName"))

    def test_oru_payload_has_indefinite_ten_second_queue(self):
        root = ET.fromstring(compile_oru_to_hlab())
        destination = root.find("destinationConnectors/connector")
        queue = destination.find("properties/destinationConnectorProperties")
        self.assertEqual("lab-app", destination.findtext("properties/remoteAddress"))
        self.assertEqual("6665", destination.findtext("properties/remotePort"))
        self.assertEqual("true", queue.findtext("queueEnabled"))
        self.assertEqual("10000", queue.findtext("retryIntervalMillis"))
        self.assertEqual("0", queue.findtext("retryCount"))
        self.assertEqual("1000", queue.findtext("queueBufferSize"))
        self.assertEqual("true", destination.findtext("properties/queueOnResponseTimeout"))
        self.assertEqual("5000", destination.findtext("properties/sendTimeout"))
        self.assertEqual("5000", destination.findtext("properties/responseTimeout"))

    def test_public_interfaces_do_not_accept_generic_payload_extensions(self):
        forbidden = {"connectors", "destinations", "filters", "transformers", "scripts", "credentials", "payload", "xml"}
        self.assertNotIn("render_channel", public_template_api)
        for compiler in (compile_orm_to_ap, compile_oru_to_hlab, compile_managed_routes):
            parameters = set(inspect.signature(compiler).parameters)
            self.assertFalse(parameters & forbidden)
            self.assertNotIn("config", parameters)
        with self.assertRaises(TypeError):
            compile_orm_to_ap("ap.internal", scripts=["return true"])
        with self.assertRaises(TypeError):
            compile_oru_to_hlab(destination_host="attacker.internal")
        with self.assertRaises(TypeError):
            compile_oru_to_hlab(queue_enabled=False)

    def test_route_pair_compilation_checks_listener_conflicts(self):
        with self.assertRaisesRegex(ValueError, "listener.port conflict"):
            compile_managed_routes("ap.internal", listener_port=6661)

    def test_normalization_ignores_server_metadata(self):
        payload = compile_orm_to_ap("ap.internal")
        root = ET.fromstring(payload)
        expected = normalized_state_from_payload(payload)
        root.find("id").text = "server-assigned-id"
        root.find("revision").text = "99"
        ET.SubElement(root, "exportData").text = "timestamp/user metadata"
        self.assertEqual(expected, normalized_state_from_payload(ET.tostring(root, encoding="unicode")))

    def test_normalization_exposes_each_owned_change(self):
        base_config = oru_to_hlab_config()
        baseline = normalized_state(base_config)
        variants = {
            "listener": replace(base_config, listener=replace(base_config.listener, port=6662)),
            "destination": replace(base_config, destination=replace(base_config.destination, port=6666)),
            "timeouts_ms": replace(base_config, send_timeout_ms=6000),
            "queue": replace(base_config, queue=QueuePolicy(enabled=False)),
            "enabled": replace(base_config, enabled=False),
            "initial_state": replace(base_config, initial_state=InitialState.STOPPED),
        }
        for expected_key, variant in variants.items():
            with self.subTest(field=expected_key):
                changed = normalized_state(variant)
                self.assertEqual(
                    {expected_key},
                    {key for key in baseline if baseline[key] != changed[key]},
                )

    def test_payload_normalization_exposes_identity_charset_and_protocol_drift(self):
        payload = compile_oru_to_hlab()
        baseline = normalized_state_from_payload(payload)
        mutations = {
            "template_version": ("description", "Managed by Healthcare Lab; logical_type=hlab-oru-to-hlab; template_version=2"),
            "charset": ("sourceConnector/properties/charsetEncoding", "ISO-8859-1"),
            "source_mode": ("sourceConnector/properties/transmissionModeProperties/pluginPointName", "BASIC_TCP"),
            "source_type": ("sourceConnector/transformer/inboundDataType", "XML"),
        }
        for label, (path, value) in mutations.items():
            with self.subTest(field=label):
                root = ET.fromstring(payload)
                root.find(path).text = value
                changed = normalized_state_from_payload(ET.tostring(root, encoding="unicode"))
                self.assertNotEqual(baseline, changed)

    def test_payload_normalization_preserves_nonmanaged_marker_as_drift(self):
        payload = compile_oru_to_hlab()
        baseline = normalized_state_from_payload(payload)
        root = ET.fromstring(payload)
        root.find("description").text = (
            "Not managed; logical_type=hlab-oru-to-hlab; template_version=1"
        )
        changed = normalized_state_from_payload(ET.tostring(root, encoding="unicode"))
        self.assertNotEqual(baseline, changed)
        self.assertEqual("Not managed; logical_type=hlab-oru-to-hlab; template_version=1", changed["marker"])

    def test_payload_and_normalized_state_are_secret_free_and_deterministic(self):
        payload = compile_orm_to_ap("ap.internal")
        normalized = normalized_state_from_payload(payload)
        self.assertEqual(normalized, normalized_state_from_payload(payload))
        combined = (payload + repr(normalized)).lower()
        for secret_word in ("password", "authorization", "cookie", "username", "192.168.30.15"):
            self.assertNotIn(secret_word, combined)

    def test_validation_errors_do_not_echo_credential_bearing_input(self):
        secret = "operator:super-secret@ap.internal"
        with self.assertRaises(ValidationError) as raised:
            orm_to_ap_config(secret)
        self.assertNotIn(secret, str(raised.exception))
        self.assertNotIn("super-secret", str(raised.exception))

    def test_domain_and_template_modules_have_no_runtime_or_io_dependencies(self):
        forbidden = {"flask", "sqlite3", "requests", "socket", "subprocess"}
        for relative in ("backend/domain/oie_channels.py", "backend/templates/oie_channels.py"):
            source = (ROOT / relative).read_text(encoding="utf-8")
            imported = {
                node.module.split(".", 1)[0]
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.ImportFrom) and node.module
            }
            imported.update(
                alias.name.split(".", 1)[0]
                for node in ast.walk(ast.parse(source))
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            self.assertFalse(imported & forbidden, relative)
            self.assertNotIn("backend.clients", source)
            self.assertNotIn("backend.repositories", source)
            self.assertNotIn("backend.runtime", source)


def _differing_leaf_paths(left: ET.Element, right: ET.Element, path: str = "channel") -> set[str]:
    differences = set()
    if (left.text or "").strip() != (right.text or "").strip():
        differences.add(path)
    for index, (left_child, right_child) in enumerate(zip(list(left), list(right))):
        child_path = f"{path}/{left_child.tag}"
        if left_child.tag != right_child.tag:
            differences.add(f"{child_path}[{index}]")
        else:
            differences.update(_differing_leaf_paths(left_child, right_child, child_path))
    return differences


def _structure(element: ET.Element):
    return (
        element.tag,
        tuple(sorted(element.attrib.items())),
        tuple(
            _structure(child)
            for child in element
            if child.tag not in {"lastModified", "userId"}
        ),
    )


if __name__ == "__main__":
    unittest.main()
