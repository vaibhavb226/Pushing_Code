# Unit Test Documentation
## File: `tests/routers/test_suppliers_bids_extended.py`

---

## Overview

This file contains **31 unit tests** covering the Suppliers and Bids API endpoints of the Sysco RFP AIQ backend. The tests are written using **pytest** and **httpx** (an async HTTP client), and they run entirely in memory — no live server or real database is needed.

---

## How the Test Setup Works

Before every single test runs, the framework automatically:

1. **Creates a fresh temporary folder** on disk (a new one for each test, so tests never affect each other).
2. **Seeds it with starter JSON files** containing one sample supplier and one sample bid:

| File | Seed Content |
|---|---|
| `suppliers.json` | One supplier — *Test Supplier Inc* (id: SM-001, category: Protein, region: Northeast) |
| `bids.json` | One bid — *Test School District* (id: BID-TEST-001, segment: K-12, status: Active) |
| `lineItems.json` | One line item — linked to BID-TEST-001 |
| `emailThreads.json` | Empty list |
| `documents.json` | Empty list |

3. **Points FastAPI at that folder** — all reads and writes during the test go to the temp folder, never touching real data files.
4. **Tears it all down** after the test finishes — the folder is deleted automatically.

This setup is defined in `tests/conftest.py` and is shared across all test files.

---

## How to Run the Tests

```bash
# Navigate into the backend folder first
cd backend_py

# Run all 31 tests with verbose output
pytest tests/routers/test_suppliers_bids_extended.py -v

# Run only supplier tests
pytest tests/routers/test_suppliers_bids_extended.py -v -k "supplier"

# Run only bid tests
pytest tests/routers/test_suppliers_bids_extended.py -v -k "bid"

# Run a single specific test
pytest tests/routers/test_suppliers_bids_extended.py::test_create_supplier_duplicate_email_returns_409 -v

# Run with short error output on failure
pytest tests/routers/test_suppliers_bids_extended.py -v --tb=short
```

---

## Section 1 — Suppliers: List with Filters

**Endpoint:** `GET /api/suppliers/`

**What it does:** Returns all suppliers. You can narrow the results using query parameters.

| Query Parameter | What it filters |
|---|---|
| `?category=Protein` | Only suppliers in that category |
| `?segment=K-12` | Only suppliers who serve that segment |
| `?region=Northeast` | Only suppliers in that region |
| `?excludeBounced=true` | Hides suppliers whose emails have bounced |

You can combine multiple filters in one request.

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_list_suppliers_filter_category_match` | Filtering by `category=Protein` returns only Protein suppliers |
| `test_list_suppliers_filter_category_no_match` | A category that doesn't exist returns an empty list (not an error) |
| `test_list_suppliers_filter_segment` | Filtering by `segment=K-12` returns only suppliers who have K-12 in their segments list |
| `test_list_suppliers_filter_region` | Filtering by `region=Northeast` returns only Northeast suppliers |
| `test_list_suppliers_exclude_bounced` | With `excludeBounced=true`, no supplier with `bounce=True` appears |
| `test_list_suppliers_combined_filters` | Sending both `category=Protein` and `region=Northeast` together filters on both at once |

---

## Section 2 — Suppliers: Search (Typeahead)

**Endpoint:** `GET /api/suppliers/search?q=<term>`

**What it does:** A quick-search used for autocomplete dropdowns. Returns at most 10 results.

### How the matching works (important)

The search checks three fields:

- **Name** — splits the supplier name into individual words, then checks if any word *starts with* your query. Example: `q=Pro` matches "**Pro**tein Supplier" because the word "Protein" starts with "Pro".
- **Contact email** — checks if your query appears *anywhere* in the email address.
- **Category** — checks if your query appears *anywhere* in the category name.

> **Gotcha:** The name check is word-by-word. If you search `q=Protein Supplier` (two words), no single word in the name equals "protein supplier", so it won't match. Always use a **single word prefix** like `q=Prot` or `q=Sup`.

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_search_by_category_keyword` | Searching `q=Protein` matches suppliers whose category is Protein |
| `test_search_by_contact_email` | Searching `q=supplier@test` matches by email substring |
| `test_search_empty_query_returns_empty` | An empty `q=` immediately returns `[]` without searching |
| `test_search_capped_at_ten_results` | Even if 12 suppliers match, only 10 are returned |

---

## Section 3 — Suppliers: Auto-Populate

**Endpoint:** `POST /api/suppliers/auto-populate`

**What it does:** Used when setting up a bid. You send a list of item categories (e.g. `["Protein", "Dairy"]`) and it returns all suppliers who cover those categories, plus a count of how many have bounced emails.

**Request body example:**
```json
{
  "itemCategories": ["Protein"],
  "excludeBounced": false
}
```

**Response example:**
```json
{
  "suppliers": [ ... ],
  "bouncedCount": 2
}
```

> Note: The "Broker" supplier category is always included in the results, regardless of what `itemCategories` you send.

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_auto_populate_returns_suppliers_and_bounced_count` | Response always contains both `suppliers` list and `bouncedCount` number |
| `test_auto_populate_exclude_bounced_flag` | When `excludeBounced=true`, no supplier with `bounce=True` appears in the returned list |
| `test_auto_populate_unknown_category` | Sending an unknown category doesn't crash the server — returns a valid (possibly empty) response |

---

## Section 4 — Suppliers: Create

**Endpoint:** `POST /api/suppliers/`

**What it does:** Creates a new supplier. The server auto-generates an `SM-NNN` ID by finding the highest existing number and adding 1.

**Request body example:**
```json
{
  "name": "New Vendor Co",
  "category": "Dairy",
  "contact": "vendor@example.com",
  "region": "Northeast",
  "segments": ["K-12"]
}
```

**Rules enforced by the server:**
- Email must be unique — sending the same contact email twice returns **409 Conflict**
- `bounce` is always set to `false` on creation (you can't create a pre-bounced supplier)

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_create_supplier_id_auto_increments` | Creating two suppliers assigns consecutive IDs (e.g. SM-002, SM-003) |
| `test_create_supplier_duplicate_email_returns_409` | Using an email that already exists returns 409 with an "already exists" message |
| `test_create_supplier_defaults_bounce_to_false` | Newly created supplier always has `bounce = false` |
| `test_create_supplier_persists_in_list` | After creating, the supplier appears when you list all suppliers |
| `test_create_supplier_appears_in_search` | After creating, the supplier can be found via the search endpoint |

---

## Section 5 — Bids: List with Filters

**Endpoint:** `GET /api/bids/`

**What it does:** Returns all bids. Supports two filters:

| Query Parameter | What it filters |
|---|---|
| `?segment=K-12` | Only bids for that customer segment |
| `?status=Active` | Only bids in that status |

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_list_bids_filter_segment` | Filtering by `segment=K-12` returns only K-12 bids |
| `test_list_bids_filter_segment_no_match` | A segment with no matching bids returns `[]` |
| `test_list_bids_filter_status` | Filtering by `status=Active` returns only Active bids |
| `test_list_bids_filter_status_no_match` | A status with no matching bids (e.g. Awarded) returns `[]` |

---

## Section 6 — Bids: Create

**Endpoint:** `POST /api/bids/`

**What it does:** Creates a new bid.

**Key behaviours:**
- If you don't send an `id`, the server generates one automatically
- `status` defaults to `"Active"` if not provided
- If you include a `lineItems` array in the request, they are saved separately and `bid.items` is updated to reflect the count

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_create_bid_auto_generates_id` | Omitting `id` in the request still produces a bid with a non-empty id |
| `test_create_bid_defaults_status_to_active` | A new bid without a `status` field gets `status = "Active"` |
| `test_create_bid_with_line_items_updates_item_count` | Sending one line item in the body sets `bid.items = 1` |
| `test_create_bid_persists` | After creating, a GET on the same bid id returns the correct data |

---

## Section 7 — Bids: Update (Partial)

**Endpoint:** `PATCH /api/bids/{bid_id}`

**What it does:** Updates specific fields on a bid without touching the others. You only send the fields you want to change.

**Rules:**
- The `id` field cannot be changed — if you send a new id in the body, it is silently ignored
- Returns the full updated bid on success
- Returns **404** if the bid doesn't exist

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_patch_bid_updates_notes` | Patching `notes` updates only that field |
| `test_patch_bid_updates_compliance` | Patching `compliance` replaces the compliance list |
| `test_patch_bid_id_immutable` | Sending a different `id` in the body does not change the bid's id |
| `test_patch_bid_change_persists` | A patched value is still there when you fetch the bid again (confirms it was saved) |
| `test_patch_bid_not_found_returns_404` | Patching a non-existent bid id returns 404 |

---

## Section 8 — Bids: Delete (Cascade)

**Endpoint:** `DELETE /api/bids/{bid_id}`

**What it does:** Deletes the bid and all related data in one operation:
- Line items linked to this bid
- Email threads
- Pricing data
- Documents
- Supplier submissions
- Uploaded files on disk

**Response example:**
```json
{
  "success": true,
  "deleted": "BID-TEST-001",
  "removed": {
    "lineItems": 1,
    "emails": 0,
    "documents": 0
  }
}
```

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_delete_bid_cascades_line_items_count` | Deleting the seed bid reports `removed.lineItems = 1` (the one seed line item was deleted) |
| `test_delete_bid_removed_from_list` | After delete, the bid no longer appears in `GET /api/bids/` |
| `test_delete_bid_then_get_returns_404` | After delete, fetching the same bid id directly returns 404 |
| `test_delete_bid_not_found_returns_404` | Deleting a bid id that doesn't exist returns 404 |

---

## Section 9 — Bids: Sub-Resources

**Endpoint:** `GET /api/bids/{bid_id}/line-items`

**What it does:** Returns all line items belonging to a specific bid.

### Tests in this section

| Test Name | What it checks |
|---|---|
| `test_get_line_items_unknown_bid_returns_empty` | A bid id with no line items returns `[]` (not 404), because line items are stored separately and filtered by bid id |

---

## Summary Table

| # | Test Name | Endpoint | Expected Status |
|---|---|---|---|
| 1 | test_list_suppliers_filter_category_match | GET /api/suppliers/?category=Protein | 200 |
| 2 | test_list_suppliers_filter_category_no_match | GET /api/suppliers/?category=NoSuchCategory | 200 (empty) |
| 3 | test_list_suppliers_filter_segment | GET /api/suppliers/?segment=K-12 | 200 |
| 4 | test_list_suppliers_filter_region | GET /api/suppliers/?region=Northeast | 200 |
| 5 | test_list_suppliers_exclude_bounced | GET /api/suppliers/?excludeBounced=true | 200 |
| 6 | test_list_suppliers_combined_filters | GET /api/suppliers/?category=Protein&region=Northeast | 200 |
| 7 | test_search_by_category_keyword | GET /api/suppliers/search?q=Protein | 200 |
| 8 | test_search_by_contact_email | GET /api/suppliers/search?q=supplier@test | 200 |
| 9 | test_search_empty_query_returns_empty | GET /api/suppliers/search?q= | 200 (empty) |
| 10 | test_search_capped_at_ten_results | GET /api/suppliers/search?q=Omega | 200 (max 10) |
| 11 | test_auto_populate_returns_suppliers_and_bounced_count | POST /api/suppliers/auto-populate | 200 |
| 12 | test_auto_populate_exclude_bounced_flag | POST /api/suppliers/auto-populate | 200 |
| 13 | test_auto_populate_unknown_category | POST /api/suppliers/auto-populate | 200 |
| 14 | test_create_supplier_id_auto_increments | POST /api/suppliers/ | 201 |
| 15 | test_create_supplier_duplicate_email_returns_409 | POST /api/suppliers/ | 409 |
| 16 | test_create_supplier_defaults_bounce_to_false | POST /api/suppliers/ | 201 |
| 17 | test_create_supplier_persists_in_list | POST → GET /api/suppliers/ | 201 → 200 |
| 18 | test_create_supplier_appears_in_search | POST → GET /api/suppliers/search | 201 → 200 |
| 19 | test_list_bids_filter_segment | GET /api/bids/?segment=K-12 | 200 |
| 20 | test_list_bids_filter_segment_no_match | GET /api/bids/?segment=NoSuchSegment | 200 (empty) |
| 21 | test_list_bids_filter_status | GET /api/bids/?status=Active | 200 |
| 22 | test_list_bids_filter_status_no_match | GET /api/bids/?status=Awarded | 200 (empty) |
| 23 | test_create_bid_auto_generates_id | POST /api/bids/ | 201 |
| 24 | test_create_bid_defaults_status_to_active | POST /api/bids/ | 201 |
| 25 | test_create_bid_with_line_items_updates_item_count | POST /api/bids/ | 201 |
| 26 | test_create_bid_persists | POST → GET /api/bids/ | 201 → 200 |
| 27 | test_patch_bid_updates_notes | PATCH /api/bids/BID-TEST-001 | 200 |
| 28 | test_patch_bid_updates_compliance | PATCH /api/bids/BID-TEST-001 | 200 |
| 29 | test_patch_bid_id_immutable | PATCH /api/bids/BID-TEST-001 | 200 |
| 30 | test_patch_bid_change_persists | PATCH → GET /api/bids/BID-TEST-001 | 200 → 200 |
| 31 | test_patch_bid_not_found_returns_404 | PATCH /api/bids/BID-NOPE-XYZ | 404 |
| 32 | test_delete_bid_cascades_line_items_count | DELETE /api/bids/BID-TEST-001 | 200 |
| 33 | test_delete_bid_removed_from_list | DELETE → GET /api/bids/ | 200 |
| 34 | test_delete_bid_then_get_returns_404 | DELETE → GET /api/bids/BID-TEST-001 | 404 |
| 35 | test_delete_bid_not_found_returns_404 | DELETE /api/bids/BID-DOES-NOT-EXIST-XYZ | 404 |
| 36 | test_get_line_items_unknown_bid_returns_empty | GET /api/bids/BID-NO-ITEMS-XYZ/line-items | 200 (empty) |
