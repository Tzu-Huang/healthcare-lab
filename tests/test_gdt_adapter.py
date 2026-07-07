import unittest

from backend.gdt_adapter import (
    GdtValidationError,
    build_gdt_6302_request,
    parse_gdt_6310_result,
    parse_gdt_message,
    render_gdt_message,
)


class GdtAdapterTests(unittest.TestCase):
    def test_6302_generation_validates_record_lengths_and_8100(self):
        result = build_gdt_6302_request(
            {
                "gdtPatientNumber": "GDT-PAT-000001",
                "lastName": "Morgan",
                "firstName": "Avery",
                "birthDate": "12041985",
                "localGdtOrderNumber": "GDT-ORD-000001",
                "sex": "2",
                "requestedAt": "20260706110000",
                "orderingProvider": "1001^WANG^AMY",
                "clinicalIndication": "Resting ECG baseline",
                "patient": {"mrn": "MRN-GDT-001"},
                "order": {"localGdtOrderNumber": "GDT-ORD-000001"},
            }
        )

        fields = parse_gdt_message(result.raw_gdt_text)

        self.assertEqual(fields["8000"], ["6302"])
        self.assertEqual(fields["8100"], [f"{len(result.raw_gdt_text.encode('cp1252')):05d}"])
        self.assertEqual(fields["8402"], ["EKG01"])
        self.assertEqual(result.validation, {"errors": [], "warnings": []})

    def test_6310_result_measurements_status_and_text_are_canonicalized(self):
        payload = render_gdt_message(
            [
                ("3000", "GDT-PAT-000001"),
                ("8402", "EKG01"),
                ("6200", "GDT-ORD-000001"),
                ("8418", "B"),
                ("8410", "HR"),
                ("8420", "75"),
                ("8421", "/min"),
                ("8410", "PR"),
                ("8420", "160"),
                ("8421", "ms"),
                ("8410", "QRS"),
                ("8420", "95"),
                ("8421", "ms"),
                ("8410", "QT"),
                ("8420", "400"),
                ("8421", "ms"),
                ("8410", "QTC"),
                ("8420", "420"),
                ("8421", "ms"),
                ("6227", "Reviewed by device"),
                ("6228", "Normal sinus rhythm"),
            ],
            set_type="6310",
        )

        result = parse_gdt_6310_result(payload)
        measurements = result.canonical["result"]["measurements"]

        self.assertEqual(result.canonical["result"]["status"], "B")
        self.assertEqual(measurements["HR"], {"value": 75, "unit": "/min", "sourceTestId": "HR"})
        self.assertEqual(measurements["PR"]["value"], 160)
        self.assertEqual(measurements["QRS"]["unit"], "ms")
        self.assertEqual(measurements["QT"]["value"], 400)
        self.assertEqual(measurements["QTC"]["value"], 420)
        self.assertEqual(result.canonical["result"]["comments"], ["Reviewed by device"])
        self.assertEqual(result.canonical["result"]["formattedText"], ["Normal sinus rhythm"])

    def test_6310_result_allows_optional_name_fields(self):
        payload = render_gdt_message(
            [
                ("3000", "GDT-PAT-000001"),
                ("8402", "EKG01"),
                ("6200", "GDT-ORD-000001"),
                ("8410", "HR"),
                ("8420", "75"),
                ("8421", "/min"),
            ],
            set_type="6310",
        )

        result = parse_gdt_6310_result(payload)

        self.assertEqual(result.canonical["patient"]["gdtPatientNumber"], "GDT-PAT-000001")
        self.assertEqual(result.canonical["patient"]["lastName"], "")
        self.assertEqual(result.canonical["patient"]["firstName"], "")

    def test_bad_record_length_is_rejected(self):
        payload = render_gdt_message([("3000", "GDT-PAT-000001")], set_type="6310")

        with self.assertRaisesRegex(GdtValidationError, "byte length"):
            parse_gdt_message("999" + payload[3:])

    def test_missing_or_mismatched_8100_is_rejected(self):
        payload = render_gdt_message([("3000", "GDT-PAT-000001")], set_type="6310")
        marker = payload.find("8100")
        mismatched = payload[: marker + 4] + "99999" + payload[marker + 9 :]
        missing = payload.replace("8100", "8101", 1)

        with self.assertRaisesRegex(GdtValidationError, "8100 total length"):
            parse_gdt_message(mismatched)

        with self.assertRaisesRegex(GdtValidationError, "8100"):
            parse_gdt_message(missing)

    def test_unknown_measurement_id_is_preserved_as_warning(self):
        payload = render_gdt_message(
            [
                ("3000", "GDT-PAT-000001"),
                ("8402", "EKG01"),
                ("8410", "VENDORX"),
                ("8420", "12"),
                ("8421", "ms"),
            ],
            set_type="6310",
        )

        result = parse_gdt_6310_result(payload)

        self.assertEqual(result.parsed_fields["8410"], ["VENDORX"])
        self.assertEqual(result.validation["warnings"][0]["code"], "301")
        self.assertEqual(result.validation["warnings"][0]["field"], "8410")


if __name__ == "__main__":
    unittest.main()
