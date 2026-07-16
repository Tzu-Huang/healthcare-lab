import unittest

from backend.mappers.types import RowMapping


class RowMappingTest(unittest.TestCase):
    def test_plain_dictionary_satisfies_runtime_row_protocol(self):
        row: RowMapping = {"id": 7}

        self.assertEqual(7, row["id"])


if __name__ == "__main__":
    unittest.main()
