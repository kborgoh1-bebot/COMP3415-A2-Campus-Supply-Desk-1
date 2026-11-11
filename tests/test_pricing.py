"""Pricing tests that need no save file, made possible by price_request()."""

import copy
import unittest

from supplydesk.service import (
    DELIVERY_FEE_CENTS,
    percent_rounded_half_up,
    price_request,
)

CATALOG = [
    {"product_id": "notebook", "name": "Notebook", "unit_price_cents": 500, "stock": 20},
    {"product_id": "hoodie", "name": "Campus hoodie", "unit_price_cents": 4000, "stock": 5},
    {"product_id": "bag", "name": "Canvas bag", "unit_price_cents": 2500, "stock": 4},
]


class RoundingTests(unittest.TestCase):
    def test_half_cent_rounds_up(self):
        self.assertEqual(percent_rounded_half_up(5005, 10), 501)  # 500.5 -> 501

    def test_below_half_cent_rounds_down(self):
        self.assertEqual(percent_rounded_half_up(5004, 10), 500)  # 500.4 -> 500

    def test_result_is_integer(self):
        self.assertIsInstance(percent_rounded_half_up(8000, 10), int)


class PriceRequestTests(unittest.TestCase):
    def test_spec_example_regular_delivery_three_hoodies(self):
        result = price_request(CATALOG, "regular", [{"product_id": "hoodie", "quantity": 3}], "delivery")
        self.assertEqual((result["subtotal_cents"], result["discount_cents"],
                          result["delivery_cents"], result["total_cents"]), (12000, 0, 0, 12000))

    def test_delivery_fee_uses_discounted_subtotal(self):
        # 11 notebooks: 5500 - 550 = 4950, under the free-delivery threshold.
        result = price_request(CATALOG, "student", [{"product_id": "notebook", "quantity": 11}], "delivery")
        self.assertEqual(result["delivery_cents"], DELIVERY_FEE_CENTS)

    def test_line_snapshot_fields(self):
        line = price_request(CATALOG, "regular", [{"product_id": "bag", "quantity": 2}])["items"][0]
        self.assertEqual(line, {"product_id": "bag", "name": "Canvas bag",
                                "unit_price_cents": 2500, "quantity": 2, "line_total_cents": 5000})

    def test_does_not_mutate_catalog(self):
        catalog = copy.deepcopy(CATALOG)
        price_request(catalog, "regular", [{"product_id": "bag", "quantity": 4}])
        self.assertEqual(catalog, CATALOG)

    def test_non_dict_item_rejected(self):
        with self.assertRaises(ValueError):
            price_request(CATALOG, "regular", ["notebook"])


if __name__ == "__main__":
    unittest.main()
