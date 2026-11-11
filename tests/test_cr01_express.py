"""CR-01: express delivery."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from supplydesk import cli
from supplydesk.service import OrderService


def stock_of(service, product_id):
    return next(p["stock"] for p in service.catalog() if p["product_id"] == product_id)


class ExpressBase(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.path = Path(d.name) / "state.json"
        self.service = OrderService(self.path)


class ExpressPricingTests(ExpressBase):
    def totals(self, customer, items, fulfillment):
        q = self.service.quote(customer, items, fulfillment)
        return q["subtotal_cents"], q["discount_cents"], q["delivery_cents"], q["total_cents"]

    def test_example_regular_two_notebooks(self):
        self.assertEqual(self.totals("regular", [{"product_id": "notebook", "quantity": 2}], "express"),
                         (1000, 0, 1200, 2200))

    def test_example_student_two_hoodies(self):
        self.assertEqual(self.totals("student", [{"product_id": "hoodie", "quantity": 2}], "express"),
                         (8000, 800, 1200, 8400))

    def test_example_three_hoodies_standard_vs_express(self):
        items = [{"product_id": "hoodie", "quantity": 3}]
        self.assertEqual(self.totals("regular", items, "delivery")[3], 12000)
        self.assertEqual(self.totals("regular", items, "express")[3], 13200)

    def test_express_fee_not_waived_at_free_delivery_threshold(self):
        # 4 bags = exactly 10,000: standard is free, express is not.
        items = [{"product_id": "bag", "quantity": 4}]
        self.assertEqual(self.totals("regular", items, "delivery")[2], 0)
        self.assertEqual(self.totals("regular", items, "express")[2], 1200)

    def test_discount_is_on_merchandise_only(self):
        # Discount is 10% of 8,000, not of 8,000 + 1,200.
        self.assertEqual(self.totals("student", [{"product_id": "hoodie", "quantity": 2}], "express")[1],
                         800)

    def test_pickup_and_standard_unchanged(self):
        items = [{"product_id": "notebook", "quantity": 2}]
        self.assertEqual(self.totals("regular", items, "pickup"), (1000, 0, 0, 1000))
        self.assertEqual(self.totals("regular", items, "delivery"), (1000, 0, 600, 1600))

    def test_other_fulfillment_values_still_invalid(self):
        for bad in ("Express", "EXPRESS", "overnight", "", None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.service.quote("regular", [{"product_id": "mug", "quantity": 1}], bad)


class ExpressOrderLifecycleTests(ExpressBase):
    REQUEST = ("student", [{"product_id": "hoodie", "quantity": 2}], "express")

    def test_quote_matches_placed_order(self):
        q = self.service.quote(*self.REQUEST)
        o = self.service.place_order(*self.REQUEST)
        self.assertEqual({k: o[k] for k in q}, q)

    def test_reopen_get_and_cancel_keep_express_details(self):
        placed = self.service.place_order(*self.REQUEST)
        self.assertEqual(stock_of(self.service, "hoodie"), 3)
        reopened = OrderService(self.path)
        self.assertEqual(reopened.get_order(placed["order_id"]), placed)
        cancelled = reopened.cancel_order(placed["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")
        for key in ("fulfillment", "items", "delivery_cents", "discount_cents", "total_cents"):
            self.assertEqual(cancelled[key], placed[key], key)
        self.assertEqual(stock_of(OrderService(self.path), "hoodie"), 5)

    def test_numbering_continues_across_fulfillment_types(self):
        ids = [self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}], f)["order_id"]
               for f in ("pickup", "express", "delivery")]
        self.assertEqual(ids, ["ORD-0001", "ORD-0002", "ORD-0003"])

    def test_invalid_express_request_changes_nothing(self):
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [{"product_id": "bag", "quantity": 5}], "express")
        self.assertFalse(self.path.exists())


class ExpressInterfaceTests(ExpressBase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = cli.main(["--data", str(self.path), *args])
            except SystemExit as exit_:
                code = exit_.code
        return code, out.getvalue(), err.getvalue()

    def test_cli_example_from_cr01(self):
        code, out, _ = self.run_cli("quote", "--customer", "student", "--fulfillment", "express",
                                    "--item", "hoodie:2")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["total_cents"], 8400)

    def test_cli_rejects_unknown_fulfillment(self):
        code, _, _ = self.run_cli("quote", "--fulfillment", "overnight", "--item", "mug:1")
        self.assertNotEqual(code, 0)

    def test_cli_help_mentions_express(self):
        code, out, _ = self.run_cli("quote", "--help")
        self.assertEqual(code, 0)
        self.assertIn("express", out)

    def test_cli_default_is_still_pickup(self):
        _, out, _ = self.run_cli("quote", "--item", "mug:1")
        self.assertEqual(json.loads(out)["fulfillment"], "pickup")

    def run_menu(self, answers):
        from supplydesk.menu import run_menu
        out = io.StringIO()
        with mock.patch("builtins.input", side_effect=answers), contextlib.redirect_stdout(out):
            run_menu(self.service)
        return out.getvalue()

    def test_menu_places_express_order(self):
        out = self.run_menu(["3", "student", "hoodie", "2", "", "express", "y", "0"])
        self.assertIn("Fulfillment: express", out)
        self.assertIn("Delivery: $12.00", out)
        self.assertEqual(self.service.list_orders()[0]["total_cents"], 8400)

    def test_menu_prompt_offers_express_and_keeps_pickup_default(self):
        prompts = []

        def fake_input(prompt=""):
            prompts.append(prompt)
            return ["2", "", "mug", "1", "", "", "0"][len(prompts) - 1]

        from supplydesk.menu import run_menu
        out = io.StringIO()
        with mock.patch("builtins.input", side_effect=fake_input), contextlib.redirect_stdout(out):
            run_menu(self.service)
        self.assertTrue(any("express" in p for p in prompts if p.startswith("Fulfillment")))
        self.assertIn("Fulfillment: pickup", out.getvalue())


if __name__ == "__main__":
    unittest.main()
