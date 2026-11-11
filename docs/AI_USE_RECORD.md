# AI-Use Record (Task 6)

Tool: Claude (Anthropic), claude.ai. Used only after Checkpoint A was submitted.
Full conversation: <PASTE CLAUDE SHARE LINK HERE>

## What AI was used for
- Implementation assistance for the three Task 4 refactorings and the defect-fix commit.
- Drafting additional tests (pricing tests, CR-01 tests) and a golden-output CLI check.
- Implementing CR-01 and suggesting tests for it.
- Reviewing the design choices listed below.

## Recommendations evaluated (detail in the report, Section 6)
| # | Recommendation | Decision | Evidence | Commit |
| --- | --- | --- | --- | --- |
| 1 | Extract shared pricing into a pure module-level `price_request(catalog, ...)` | ACCEPT | 864-request differential test; `tests/test_pricing.py` runs with no file I/O | Refactor: remove duplicated validation/pricing |
| 2 | Leave `OrderService.__init__` unchanged (no store injection) | MODIFY | Added optional `store=None`; existing callers unchanged; `InjectedStoreTests` | Task 6: optional store injection |
| 3 | Keep silent skip of unknown products in `_adjust_stock()` | REJECT | Damaged-save experiment: cancel reported success, stock lost; `DamagedSaveFileTests` | Task 6: error instead of silent skip |

## How AI output was verified
Every change was checked by running the full unit suite against the recorded baseline and
by diffing `evidence/golden.sh` output before and after. Suspected-defect tests kept their
expected values throughout.

## Additional AI assistance
- Drafting the CR-01 Part A prediction, recorded and committed before any CR-01 code or tests were written.
