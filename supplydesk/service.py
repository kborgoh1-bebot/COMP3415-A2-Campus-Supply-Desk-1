"""Business rules for the order desk: validation, pricing, stock and order history."""

from supplydesk.storage import JsonStore

CUSTOMER_TYPES = ("regular", "student")
FULFILLMENT_OPTIONS = ("pickup", "delivery", "express")
MIN_QUANTITY = 1
MAX_QUANTITY = 99
# Students get 10% off when the subtotal is at least $50.00.
STUDENT_DISCOUNT_THRESHOLD_CENTS = 5000
STUDENT_DISCOUNT_PERCENT = 10
DELIVERY_FEE_CENTS = 600
FREE_DELIVERY_THRESHOLD_CENTS = 10000
# CR-01: express is a flat fee that is never waived.
EXPRESS_FEE_CENTS = 1200
ORDER_ID_PREFIX = "ORD-"
ORDER_NUMBER_WIDTH = 4
STATUS_PLACED = "placed"
STATUS_CANCELLED = "cancelled"


def percent_rounded_half_up(amount_cents, percent):
    """Integer percentage of a cent amount, rounding half a cent upward."""
    return (amount_cents * percent + 50) // 100


def _validate_options(customer_type, fulfillment, items):
    """Check the request-level fields before any item is examined."""
    if customer_type not in CUSTOMER_TYPES:
        raise ValueError("Customer type must be regular or student.")
    if fulfillment not in FULFILLMENT_OPTIONS:
        raise ValueError("Fulfillment must be one of: " + ", ".join(FULFILLMENT_OPTIONS) + ".")
    if not isinstance(items, list) or not items:
        raise ValueError("An order must contain at least one item.")


def _find_product(catalog, product_id):
    """Return the catalog entry with this ID, or None."""
    for product in catalog:
        if product["product_id"] == product_id:
            return product
    return None


def _price_line(catalog, item, already_requested=0):
    """Validate one requested item and return its priced line.

    already_requested is the quantity of the same product on earlier lines,
    so stock is checked against the combined request.
    """
    if not isinstance(item, dict):
        raise ValueError("Each item must contain a product_id and quantity.")
    product = _find_product(catalog, item.get("product_id"))
    if product is None:
        raise ValueError("Unknown product.")
    quantity = item.get("quantity")
    if type(quantity) is not int or quantity < MIN_QUANTITY or quantity > MAX_QUANTITY:
        raise ValueError(f"Quantity must be an integer from {MIN_QUANTITY} to {MAX_QUANTITY}.")
    if already_requested + quantity > product["stock"]:
        raise ValueError("Not enough stock for " + product["product_id"] + ".")
    return {
        "product_id": product["product_id"],
        "name": product["name"],
        "unit_price_cents": product["unit_price_cents"],
        "quantity": quantity,
        "line_total_cents": product["unit_price_cents"] * quantity,
    }


def _student_discount(customer_type, subtotal):
    """Discount in cents for this customer type and subtotal."""
    if customer_type == "student" and subtotal >= STUDENT_DISCOUNT_THRESHOLD_CENTS:
        return percent_rounded_half_up(subtotal, STUDENT_DISCOUNT_PERCENT)
    return 0


def _delivery_charge(fulfillment, discounted_subtotal):
    """Delivery charge in cents.

    Pickup is free. Standard delivery is free at or above the threshold.
    Express always costs the flat express fee.
    """
    if fulfillment == "express":
        return EXPRESS_FEE_CENTS
    if fulfillment == "delivery" and discounted_subtotal < FREE_DELIVERY_THRESHOLD_CENTS:
        return DELIVERY_FEE_CENTS
    return 0


def price_request(catalog, customer_type, items, fulfillment="pickup"):
    """Validate a request against the catalog and price it.

    Pure function: reads the catalog but never changes it. Shared by quote()
    and place_order() so both always apply identical rules.
    Raises ValueError for an invalid request.
    """
    _validate_options(customer_type, fulfillment, items)
    lines = []
    requested = {}
    for item in items:
        product_id = item.get("product_id") if isinstance(item, dict) else None
        line = _price_line(catalog, item, requested.get(product_id, 0))
        requested[line["product_id"]] = requested.get(line["product_id"], 0) + line["quantity"]
        lines.append(line)
    subtotal = sum(line["line_total_cents"] for line in lines)
    discount = _student_discount(customer_type, subtotal)
    delivery = _delivery_charge(fulfillment, subtotal - discount)
    return {
        "customer_type": customer_type,
        "fulfillment": fulfillment,
        "items": lines,
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "delivery_cents": delivery,
        "total_cents": subtotal - discount + delivery,
    }


def _adjust_stock(catalog, lines, direction):
    """Add (direction=+1) or remove (direction=-1) each line's units from stock."""
    products = [_find_product(catalog, line["product_id"]) for line in lines]
    for line, product in zip(lines, products):
        if product is None:  # damaged save file: fail before changing anything
            raise ValueError("Saved order references unknown product: " + line["product_id"])
    for line, product in zip(lines, products):
        product["stock"] += direction * line["quantity"]


def _format_order_id(number):
    return ORDER_ID_PREFIX + str(number).zfill(ORDER_NUMBER_WIDTH)

class OrderService:
    def __init__(self, state_path=".supplydesk/state.json", store=None):
        """Use the JSON save file at state_path, or an injected store with load()/save()."""
        self.store = store if store is not None else JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        return price_request(state["catalog"], customer_type, items, fulfillment)

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        priced = price_request(state["catalog"], customer_type, items, fulfillment)
        order = {
            "order_id": _format_order_id(state["next_order_number"]),
            "status": STATUS_PLACED,
            **priced,
        }
        _adjust_stock(state["catalog"], order["items"], -1)
        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        return self._find_order(self.store.load(), order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = self._find_order(state, order_id)
        if order["status"] == STATUS_CANCELLED:
            return order  # already cancelled: no second stock restore
        _adjust_stock(state["catalog"], order["items"], +1)
        order["status"] = STATUS_CANCELLED
        self.store.save(state)
        return order

    @staticmethod
    def _find_order(state, order_id):
        """Return the order with this ID from loaded state, or raise ValueError."""
        for order in state["orders"]:
            if order["order_id"] == order_id:
                return order
        raise ValueError("Unknown order: " + order_id)
