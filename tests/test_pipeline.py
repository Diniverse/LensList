from __future__ import annotations

import unittest
from datetime import date

from scripts.core import classify_fee, deduplicate, is_expired, parse_deadline
from scripts.healthcheck import validate_active


class PipelineTests(unittest.TestCase):
    def test_expired_opportunity_is_rejected_from_active_feed(self):
        item = self.valid_item(deadline="2020-01-01")
        self.assertTrue(is_expired(item["deadline"], today=date(2026, 10, 28)))
        self.assertTrue(any("expired" in error for error in validate_active([item])))

    def test_duplicate_urls_are_removed(self):
        first = self.valid_item(source_url="https://example.org/call?utm_source=test")
        second = self.valid_item(id="two", title="Different title", source_url="https://example.org/call")
        self.assertEqual(len(deduplicate([first, second])), 1)

    def test_unverified_fee_is_not_confirmed_free(self):
        status, _evidence = classify_fee("Applications are open. Review all terms before applying.")
        self.assertEqual(status, "unverified")

    def test_mandatory_paid_fee_overrides_free_language(self):
        text = "The webinar is free. The mandatory application fee is $25."
        status, _evidence = classify_fee(text)
        self.assertEqual(status, "fee-detected")

    def test_explicit_no_fee_is_confirmed(self):
        status, evidence = classify_fee("There is no application fee. Applications close soon.")
        self.assertEqual(status, "confirmed-free")
        self.assertIn("no application fee", evidence.lower())

    def test_deadline_parser_uses_deadline_context(self):
        self.assertEqual(parse_deadline("Applications close on November 30, 2026."), "2026-11-30")

    @staticmethod
    def valid_item(**overrides):
        item = {
            "id": "one",
            "title": "Free call",
            "organization": "Example",
            "category": "Open call",
            "location": "International",
            "geography": "International",
            "eligibility": "Adults",
            "compensation": "Grant",
            "copyright_terms": "Artist retains copyright",
            "publication_costs": "None stated",
            "source_url": "https://example.org/call",
            "deadline": "2099-01-01",
            "fee_status": "confirmed-free",
            "last_verified": "2026-10-28T00:00:00Z",
        }
        item.update(overrides)
        return item


if __name__ == "__main__":
    unittest.main()
