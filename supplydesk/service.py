"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore

CUSTOMER_TYPES = ("regular", "student")
FULFILLMENT_OPTIONS = ("pickup", "delivery")
MIN_QUANTITY = 1
MAX_QUANTITY = 99
# Spec: students get 10% off when the subtotal is at least $50.00.
# NOTE: the comparison below still uses ">" (see defect D1); refactoring keeps it unchanged.
STUDENT_DISCOUNT_THRESHOLD_CENTS = 5000
STUDENT_DISCOUNT_PERCENT = 10
DELIVERY_FEE_CENTS = 600
FREE_DELIVERY_THRESHOLD_CENTS = 10000
ORDER_ID_PREFIX = "ORD-"
ORDER_NUMBER_WIDTH = 4
STATUS_PLACED = "placed"
STATUS_CANCELLED = "cancelled"


def percent_rounded_half_up(amount_cents, percent):
    """Integer percentage of a cent amount, rounding half a cent upward."""
    return (amount_cents * percent + 50) // 100


class OrderService:
    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        if customer_type not in CUSTOMER_TYPES:
            raise ValueError("Customer type must be regular or student.")
        if fulfillment not in FULFILLMENT_OPTIONS:
            raise ValueError("Fulfillment must be pickup or delivery.")
        if not isinstance(items, list) or not items:
            raise ValueError("An order must contain at least one item.")
        lines = []
        subtotal = 0
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item must contain a product_id and quantity.")
            product = None
            for candidate in state["catalog"]:
                if candidate["product_id"] == item.get("product_id"):
                    product = candidate
                    break
            if product is None:
                raise ValueError("Unknown product.")
            quantity = item.get("quantity")
            if type(quantity) is not int or quantity < MIN_QUANTITY or quantity > MAX_QUANTITY:
                raise ValueError(f"Quantity must be an integer from {MIN_QUANTITY} to {MAX_QUANTITY}.")
            if quantity > product["stock"]:
                raise ValueError("Not enough stock for " + product["product_id"] + ".")
            line_total = product["unit_price_cents"] * quantity
            subtotal += line_total
            lines.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "unit_price_cents": product["unit_price_cents"],
                "quantity": quantity,
                "line_total_cents": line_total,
            })
        discount = 0
        if customer_type == "student" and subtotal > STUDENT_DISCOUNT_THRESHOLD_CENTS:
            discount = percent_rounded_half_up(subtotal, STUDENT_DISCOUNT_PERCENT)
        delivery = 0
        if fulfillment == "delivery" and subtotal - discount < FREE_DELIVERY_THRESHOLD_CENTS:
            delivery = DELIVERY_FEE_CENTS
        return {
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        if customer_type not in CUSTOMER_TYPES:
            raise ValueError("Customer type must be regular or student.")
        if fulfillment not in FULFILLMENT_OPTIONS:
            raise ValueError("Fulfillment must be pickup or delivery.")
        if not isinstance(items, list) or not items:
            raise ValueError("An order must contain at least one item.")
        lines = []
        subtotal = 0
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item must contain a product_id and quantity.")
            product = None
            for candidate in state["catalog"]:
                if candidate["product_id"] == item.get("product_id"):
                    product = candidate
                    break
            if product is None:
                raise ValueError("Unknown product.")
            quantity = item.get("quantity")
            if type(quantity) is not int or quantity < MIN_QUANTITY or quantity > MAX_QUANTITY:
                raise ValueError(f"Quantity must be an integer from {MIN_QUANTITY} to {MAX_QUANTITY}.")
            if quantity > product["stock"]:
                raise ValueError("Not enough stock for " + product["product_id"] + ".")
            line_total = product["unit_price_cents"] * quantity
            subtotal += line_total
            lines.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "unit_price_cents": product["unit_price_cents"],
                "quantity": quantity,
                "line_total_cents": line_total,
            })
        discount = 0
        if customer_type == "student" and subtotal > STUDENT_DISCOUNT_THRESHOLD_CENTS:
            discount = percent_rounded_half_up(subtotal, STUDENT_DISCOUNT_PERCENT)
        delivery = 0
        if fulfillment == "delivery" and subtotal - discount < FREE_DELIVERY_THRESHOLD_CENTS:
            delivery = DELIVERY_FEE_CENTS
        order = {
            "order_id": ORDER_ID_PREFIX + str(state["next_order_number"]).zfill(ORDER_NUMBER_WIDTH),
            "status": STATUS_PLACED,
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }
        for line in lines:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] -= line["quantity"]
        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        state = self.store.load()
        for order in state["orders"]:
            if order["order_id"] == order_id:
                return order
        raise ValueError("Unknown order: " + order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = None
        for candidate in state["orders"]:
            if candidate["order_id"] == order_id:
                order = candidate
                break
        if order is None:
            raise ValueError("Unknown order: " + order_id)
        for line in order["items"]:
            for product in state["catalog"]:
                if product["product_id"] == line["product_id"]:
                    product["stock"] += line["quantity"]
        order["status"] = STATUS_CANCELLED
        self.store.save(state)
        return order
