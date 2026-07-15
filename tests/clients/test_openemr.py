import unittest

from backend.domain.errors import SimulatorValidationError
from backend.lab_store import (
    OpenEMRProcedureOrderSource,
    map_openemr_procedure_order_to_gdt_order,
)


class FakeCursor:
    def __init__(self, rows=(), error=None):
        self.rows = rows
        self.error = error
        self.query = ""
        self.params = ()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params):
        self.query = query
        self.params = params
        if self.error:
            raise self.error

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows=(), error=None):
        self.cursor_value = FakeCursor(rows, error)
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True


def source(factory=None, **overrides):
    values = dict(host="db", user="openemr", password="secret", database="openemr",
                  allowed_procedure_codes=("1001",), connection_factory=factory)
    values.update(overrides)
    return OpenEMRProcedureOrderSource(**values)


class OpenEmrClientCharacterizationTests(unittest.TestCase):
    def test_configuration_status_and_unconfigured_list(self):
        item = source(host="")
        self.assertFalse(item.status()["configured"])
        with self.assertRaisesRegex(SimulatorValidationError, "not configured"):
            item.list_orders()

    def test_list_get_query_parameters_mapping_and_connection_closure(self):
        row = {"procedure_order_id": 7, "procedure_order_seq": 2,
               "procedure_code": "1001", "procedure_name": "ECG",
               "pubpid": "MRN-7", "patient_fname": "Avery",
               "patient_lname": "Morgan", "patient_dob": "1985-04-12 00:00:00",
               "patient_sex": "female", "provider_fname": "Amy",
               "provider_lname": "Wang"}
        connection = FakeConnection([row])
        item = source(lambda: connection)
        listed = item.list_orders()
        self.assertEqual(listed[0]["patient"]["gender"], "F")
        self.assertEqual(listed[0]["patient"]["dob"], "1985-04-12")
        self.assertEqual(item.get_order(7, 2), listed[0])
        self.assertEqual(connection.cursor_value.params, ("1001",))
        self.assertIn("procedure_order", connection.cursor_value.query)
        self.assertTrue(connection.closed)

    def test_missing_schema_connection_failure_and_verification(self):
        missing = Exception(1146, "Table 'openemr.procedure_order' doesn't exist")
        missing_connection = FakeConnection(error=missing)
        item = source(lambda: missing_connection)
        self.assertEqual(item.list_orders(), [])
        self.assertTrue(missing_connection.closed)
        verification_connection = FakeConnection([{"procedure_order_id": 1}])
        result = source(lambda: verification_connection).verify_order_query()
        self.assertEqual(result["orders"]["count"], 1)
        self.assertTrue(verification_connection.closed)
        failed = source(lambda: (_ for _ in ()).throw(OSError("unavailable"))).verify_order_query()
        self.assertEqual(failed["connection"]["status"], "Down")

    def test_domain_mapping_is_deterministic(self):
        row = {"procedure_order_id": 1, "procedure_order_seq": 1, "patient_id": 2}
        self.assertEqual(map_openemr_procedure_order_to_gdt_order(row),
                         map_openemr_procedure_order_to_gdt_order(row))


if __name__ == "__main__":
    unittest.main()
