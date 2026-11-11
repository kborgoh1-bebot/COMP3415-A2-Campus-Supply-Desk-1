"""Stand-in for the user's safety net: same behaviours as described in Task 2."""

from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService


def stock_of(service, product_id):
    return next(p["stock"] for p in service.catalog() if p["product_id"] == product_id)


class Base(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.path = Path(d.name) / "state.json"
        self.service = OrderService(self.path)


class Normal(Base):
    def test_place_three_notebooks(self):
        order = self.service.place_order("regular", [{"product_id": "notebook", "quantity": 3}])
        self.assertEqual((order["order_id"], order["status"], order["total_cents"]),
                         ("ORD-0001", "placed", 1500))
        self.assertEqual(stock_of(self.service, "notebook"), 17)

    def test_student_delivery_two_hoodies(self):
        q = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], "delivery")
        self.assertEqual((q["subtotal_cents"], q["discount_cents"], q["delivery_cents"],
                          q["total_cents"]), (8000, 800, 600, 7800))


class Boundary(Base):
    def test_discount_just_above_threshold(self):
        q = self.service.quote("student", [{"product_id": "notebook", "quantity": 11}])
        self.assertEqual(q["discount_cents"], 550)

    def test_delivery_threshold(self):
        at = self.service.quote("regular", [{"product_id": "bag", "quantity": 4}], "delivery")
        below = self.service.quote("regular", [{"product_id": "notebook", "quantity": 19}], "delivery")
        self.assertEqual((at["delivery_cents"], below["delivery_cents"]), (0, 600))

    def test_quantity_limits(self):
        svc = self.service
        for bad in (0, 100):
            with self.assertRaises(ValueError):
                svc.quote("regular", [{"product_id": "notebook", "quantity": bad}])
        svc.store.save({**svc.store.load(), "catalog": [
            {"product_id": "notebook", "name": "Notebook", "unit_price_cents": 500, "stock": 200}]})
        self.assertEqual(svc.quote("regular", [{"product_id": "notebook", "quantity": 99}])
                         ["subtotal_cents"], 49500)

    def test_exact_stock_vs_one_more(self):
        self.service.quote("regular", [{"product_id": "bag", "quantity": 4}])
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "bag", "quantity": 5}])


class Invalid(Base):
    def test_invalid_requests_raise(self):
        bad = [("regular", [{"product_id": "nope", "quantity": 1}], "pickup"),
               ("vip", [{"product_id": "mug", "quantity": 1}], "pickup"),
               ("regular", [], "pickup"),
               ("regular", [{"product_id": "mug", "quantity": 1}], "drone"),
               ("regular", [{"product_id": "mug", "quantity": "2"}], "pickup"),
               ("regular", [{"product_id": "mug", "quantity": True}], "pickup"),
               ("regular", [{"product_id": "mug", "quantity": 1.5}], "pickup")]
        for args in bad:
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.service.quote(*args)

    def test_unknown_order_id(self):
        with self.assertRaises(ValueError):
            self.service.get_order("ORD-9999")
        with self.assertRaises(ValueError):
            self.service.cancel_order("ORD-9999")

    def test_rejected_order_changes_nothing(self):
        self.service.place_order("regular", [{"product_id": "mug", "quantity": 1}])
        before = (self.service.catalog(), self.service.list_orders())
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [{"product_id": "mug", "quantity": 1},
                                                 {"product_id": "nope", "quantity": 1}])
        self.assertEqual((self.service.catalog(), self.service.list_orders()), before)


class Preserve(Base):
    def test_quote_changes_nothing_and_creates_no_file(self):
        self.service.quote("regular", [{"product_id": "mug", "quantity": 2}])
        self.assertFalse(self.path.exists())

    def test_quote_matches_placed_order(self):
        req = ("student", [{"product_id": "hoodie", "quantity": 1},
                           {"product_id": "mug", "quantity": 2}], "delivery")
        q = self.service.quote(*req)
        o = self.service.place_order(*req)
        self.assertEqual({k: o[k] for k in q}, q)

    def test_order_ids_increase(self):
        ids = [self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 1}])
               ["order_id"] for _ in range(3)]
        self.assertEqual(ids, ["ORD-0001", "ORD-0002", "ORD-0003"])

    def test_cancel_restores_stock_and_keeps_history(self):
        o = self.service.place_order("regular", [{"product_id": "bag", "quantity": 2}])
        self.service.cancel_order(o["order_id"])
        self.assertEqual(stock_of(self.service, "bag"), 4)
        h = self.service.list_orders()
        self.assertEqual((len(h), h[0]["status"], h[0]["total_cents"]), (1, "cancelled", 5000))

    def test_reopen_preserves_state(self):
        o = self.service.place_order("regular", [{"product_id": "mug", "quantity": 3}])
        reopened = OrderService(self.path)
        self.assertEqual(reopened.list_orders(), [o])
        self.assertEqual(stock_of(reopened, "mug"), 5)


class SuspectedDefects(Base):
    def test_discount_at_exactly_5000(self):
        q = self.service.quote("student", [{"product_id": "notebook", "quantity": 10}])
        self.assertEqual(q["discount_cents"], 500)

    def test_double_cancel_restores_once(self):
        before = self.service.catalog()
        o = self.service.place_order("regular", [{"product_id": "pen-pack", "quantity": 2}])
        self.service.cancel_order(o["order_id"])
        self.service.cancel_order(o["order_id"])
        self.assertEqual(self.service.catalog(), before)

    def test_duplicate_lines_combined_stock(self):
        self.service.store.save({**self.service.store.load(), "catalog": [
            {"product_id": "notebook", "name": "Notebook", "unit_price_cents": 500, "stock": 4}]})
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [{"product_id": "notebook", "quantity": 3},
                                                 {"product_id": "notebook", "quantity": 3}])


if __name__ == "__main__":
    unittest.main()
