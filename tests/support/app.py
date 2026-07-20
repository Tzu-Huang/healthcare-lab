import tempfile
import unittest
from pathlib import Path

from backend.app_factory import create_app
from backend.application_composition import assemble_application_dependencies
from backend.lab_composition import LabApplicationRepository
from backend.services.oie_workflow import OieInventoryCoordination


class DisposableAppCase(unittest.TestCase):
    """Create an isolated Flask app and database for one test method."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        app = create_app(
            str(temp_root / "app.db"),
            dependency_receiver=lambda dependencies: setattr(
                self, "dependencies", dependencies
            ),
            order_coordination_receiver=lambda coordination: setattr(
                self, "order_coordination", coordination
            ),
        )
        app.config.update(
            TESTING=True,
            GDT_BRIDGE_PATH=str(temp_root / "gdt-bridge"),
            MEDPLUM_CLIENT_ID="demo-client",
            MEDPLUM_CLIENT_SECRET="demo-secret",
            MEDPLUM_SCOPE="openid",
            MEDPLUM_TOKEN_URL="",
            OIE_MLLP_ORDER_HOST="localhost",
            DCM4CHEE_DIMSE_HOST="127.0.0.1",
            DCM4CHEE_HL7_HOST="127.0.0.1",
            DCM4CHEE_DICOMWEB_BASE_URL=(
                "http://127.0.0.1:8082/dcm4chee-arc/aets/WORKLIST/rs"
            ),
            DCM4CHEE_QIDO_RS_URL=(
                "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs"
            ),
            DCM4CHEE_WADO_RS_URL=(
                "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs"
            ),
            DCM4CHEE_STOW_RS_URL=(
                "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs"
            ),
        )
        self.app = app
        self.client = app.test_client()
        self.lab_repository_view = LabApplicationRepository(
            self.dependencies.lab_repository,
            gdt_inventory=self.dependencies.gdt_repository.list_gdt_orders,
        )

    def tearDown(self):
        self.temp_dir.cleanup()


class DisposableStoreCase(unittest.TestCase):
    """Create explicit disposable application dependencies below a temp root."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.dependencies = assemble_application_dependencies(
            Path(self.directory.name) / "lab.db"
        )
        self.lab_repository_view = LabApplicationRepository(
            self.dependencies.lab_repository,
            gdt_inventory=self.dependencies.gdt_repository.list_gdt_orders,
        )
        self.oie_coordination = OieInventoryCoordination(
            self.dependencies.patient_repository,
            self.dependencies.order_repository,
            patient_protocol="HL7 v2.5.1",
            order_protocol="2.5.1",
        )

    def tearDown(self):
        self.directory.cleanup()
