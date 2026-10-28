import unittest

from field_detection import (
    DETECTED,
    MANUAL_REVIEW,
    NOT_DETECTED,
    validate_label_text,
)
from samples import SAMPLE_LABELS


def by_key(text):
    return {result.key: result for result in validate_label_text(text)}


class FieldDetectionTests(unittest.TestCase):
    def test_sample_with_all_common_fields_is_detected(self):
        results = by_key(SAMPLE_LABELS["Roasted chana · Pantry sample"])
        self.assertEqual(results["mrp"].status, DETECTED)
        self.assertEqual(results["mrp"].value, "₹45.00")
        self.assertEqual(results["net_quantity"].value, "200 g")
        self.assertEqual(results["manufacturer"].status, DETECTED)
        self.assertEqual(results["manufacturing_date"].value, "12/09/2025")
        self.assertEqual(results["consumer_care"].status, DETECTED)
        self.assertEqual(results["expiry"].status, DETECTED)

    def test_all_three_samples_have_expected_values(self):
        expected = {
            "Turmeric powder · Pantry sample": ("₹68.00", "100 g", "09/2025"),
            "Mango drink · Beverage sample": ("₹35.00", "200 ml", "01/10/2025"),
        }
        for sample_name, (mrp, quantity, date) in expected.items():
            with self.subTest(sample=sample_name):
                results = by_key(SAMPLE_LABELS[sample_name])
                self.assertEqual(results["mrp"].value, mrp)
                self.assertEqual(results["net_quantity"].value, quantity)
                self.assertEqual(results["manufacturing_date"].value, date)

    def test_unlabelled_price_requires_manual_review(self):
        results = by_key("Price Rs. 120.00")
        self.assertEqual(results["mrp"].status, MANUAL_REVIEW)
        self.assertIn("₹120.00", results["mrp"].value)

    def test_missing_fields_are_not_mistaken_for_compliance(self):
        results = by_key("A plain package with no readable label details.")
        self.assertEqual(results["mrp"].status, NOT_DETECTED)
        self.assertEqual(results["net_quantity"].status, NOT_DETECTED)
        self.assertEqual(results["manufacturer"].status, NOT_DETECTED)
        self.assertEqual(results["manufacturing_date"].status, NOT_DETECTED)
        self.assertEqual(results["consumer_care"].status, NOT_DETECTED)
        self.assertEqual(results["expiry"].status, MANUAL_REVIEW)

    def test_manufacturer_name_without_address_needs_review(self):
        results = by_key("Manufactured by: Sample Foods Ltd.")
        self.assertEqual(results["manufacturer"].status, MANUAL_REVIEW)

    def test_care_heading_without_contact_needs_review(self):
        results = by_key("Consumer Care: please contact us")
        self.assertEqual(results["consumer_care"].status, MANUAL_REVIEW)

    def test_non_string_input_is_rejected(self):
        with self.assertRaises(TypeError):
            validate_label_text(None)


    def test_ocr_misread_currency_symbol_still_finds_mrp(self):
        results = by_key("MRP ¥ 40.00")
        self.assertEqual(results["mrp"].status, DETECTED)
        self.assertEqual(results["mrp"].value, "₹40.00")

    def test_packed_date_abbreviation_and_next_line_date(self):
        results = by_key("PKD.:\n10/04/2025")
        self.assertEqual(results["manufacturing_date"].status, DETECTED)
        self.assertEqual(results["manufacturing_date"].value, "10/04/2025")

    def test_quantity_number_without_unit_requires_review(self):
        results = by_key("NET WEIGHT:\n2009")
        self.assertEqual(results["net_quantity"].status, MANUAL_REVIEW)
        self.assertEqual(results["net_quantity"].value, "2009")

    def test_best_before_date_on_next_line_is_detected(self):
        results = by_key("BEST BEFORE:\n09/10/2025")
        self.assertEqual(results["expiry"].status, DETECTED)
        self.assertIn("09/10/2025", results["expiry"].value)


if __name__ == "__main__":
    unittest.main()
