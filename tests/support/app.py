import tempfile
import unittest
from pathlib import Path

from app import create_app
from backend.lab_store import DemoStore


class DisposableAppCase(unittest.TestCase):
    """Create an isolated Flask app and database for one test method."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        app = create_app(str(temp_root / "app.db"))
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

    def tearDown(self):
        self.temp_dir.cleanup()


class DisposableStoreCase(unittest.TestCase):
    """Create a disposable DemoStore database below an explicit temp root."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = DemoStore(Path(self.directory.name) / "lab.db")

    def tearDown(self):
        self.directory.cleanup()
