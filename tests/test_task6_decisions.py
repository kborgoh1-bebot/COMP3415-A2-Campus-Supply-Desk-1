"""Tests for changes made while evaluating AI recommendations (Task 6)."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService
from supplydesk.storage import JsonStore


class InMemoryStore:
    """Test double with the same load()/save() interface as JsonStore."""

    def __init__(self, state):
        self.state = copy.deepcopy(state)
        self.saves = 0

    def load(self):
        return copy.deepcopy(self.state)

    def save(self, state):
        self.state = copy.deepcopy(state)
        self.saves += 1


def fresh_state():
    return JsonStore(Path(tempfile.mkdtemp()) / "missing.json").load()


class InjectedStoreTests(unittest.TestCase):
    def test_service_runs_without_any_file(self):
        store = InMemoryStore(fresh_state())
        service = OrderService(store=store)
        order = service.place_order("regular", [{"product_id": "mug", "quantity": 2}])
        self.assertEqual(order["order_id"], "ORD-0001")
        self.assertEqual(store.saves, 1)
        self.assertEqual(service.cancel_order("ORD-0001")["status"], "cancelled")

    def test_quote_never_saves(self):
        store = InMemoryStore(fresh_state())
        OrderService(store=store).quote("student", [{"product_id": "hoodie", "quantity": 2}], "express")
        self.assertEqual(store.saves, 0)

    def test_default_constructor_still_uses_json_file(self):
        path = Path(tempfile.mkdtemp()) / "state.json"
        OrderService(path).place_order("regular", [{"product_id": "mug", "quantity": 1}])
        self.assertTrue(path.exists())


class DamagedSaveFileTests(unittest.TestCase):
    def test_cancel_with_missing_product_raises_and_saves_nothing(self):
        path = Path(tempfile.mkdtemp()) / "state.json"
        service = OrderService(path)
        service.place_order("regular", [{"product_id": "notebook", "quantity": 1},
                                        {"product_id": "mug", "quantity": 2}])
        state = json.loads(path.read_text())
        state["catalog"] = [p for p in state["catalog"] if p["product_id"] != "mug"]
        path.write_text(json.dumps(state))
        before = path.read_text()
        with self.assertRaises(ValueError):
            service.cancel_order("ORD-0001")
        self.assertEqual(path.read_text(), before)  # notebook not restored either


if __name__ == "__main__":
    unittest.main()
