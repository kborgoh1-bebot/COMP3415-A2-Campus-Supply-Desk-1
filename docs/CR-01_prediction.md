# CR-01 Part A – Prediction (written before implementation)

## 1. Behaviour / requirements expected to change
- The set of valid fulfillment values grows from {pickup, delivery} to {pickup, delivery, express}.
- The delivery-charge rule gains a branch: express = 1,200 cents always, never waived.
- Discount, rounding, standard-delivery threshold, validation, stock, numbering and
  cancellation rules should NOT change.
- User-facing text: menu prompt, CLI choices/help, the invalid-fulfillment error message, docs.

## 2. Files / methods expected to change
- service.py: FULFILLMENT_OPTIONS, new EXPRESS_FEE_CENTS constant, _delivery_charge().
  Also _validate_options(): its message "Fulfillment must be pickup or delivery." is a
  hard-coded string and will become wrong.
- cli.py: build_parser() hard-codes choices=("pickup", "delivery"), duplicating the service
  list; needs express and help text.
- menu.py: read_request() prompt "[pickup/delivery]".
- FUNCTIONAL_SPEC.md / README: document express.
- Expected NOT to change: storage.py (fulfillment is already stored as a plain string,
  schema version stays 1), place_order(), cancel_order(), get_order(), list_orders().

## 3. Tests needed
- New: the three CR-01 examples (2200, 8400, 12000 vs 13200); express fee charged even at
  or above the 10,000-cent threshold; discount computed on merchandise only.
- New: express order placed, reopened, retrieved and cancelled keeps fulfillment, items,
  fee, discount and total; stock restored.
- New: quote == placed order for express.
- New: invalid values ("Express", "overnight", "") still raise ValueError.
- New: CLI `quote --fulfillment express` returns total_cents 8400; CLI rejects bad values
  with nonzero exit; menu accepts "express" and still defaults to pickup.
- Existing tests: all should pass unchanged (regression check).
