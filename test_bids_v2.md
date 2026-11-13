# Unit Test Documentation — V2
## File: `tests/routers/test_bids_v2.py`

---

## Overview

This is the **v2 comprehensive test file** for the Bids API. It combines everything from the original `test_bids.py` (11 tests) with the additional bid tests from `test_suppliers_bids_extended.py` into one complete file.

| | test_bids.py | test_bids_v2.py |
|---|---|---|
| Total tests | 11 | 29 |
| List filters | ❌ | ✅ |
| GET single bid | ✅ | ✅ |
| Create (explicit id) | ✅ | ✅ |
| Create (auto id) | ❌ | ✅ |
| Create (with line items) | ❌ | ✅ |
| Patch status | ✅ | ✅ |
| Patch notes | ❌ | ✅ |
| Patch compliance | ❌ | ✅ |
| Patch id immutable | ❌ | ✅ |
| Patch persists | ❌ | ✅ |
| Delete (full shape check) | ✅ | ✅ |
| Delete (cascade count) | ❌ | ✅ |
| Delete (removed from list) | ❌ | ✅ |
| Delete (404 on missing) | ❌ | ✅ |
| Line items (seed bid) | ✅ | ✅ |
| Line items (unknown bid) | ❌ | ✅ |
| Emails sub-resource | ✅ | ✅ |
| Portal templates ordering | ✅ | ✅ |
| Health check | ✅ | ✅ |

---

## How the Test Setup Works

Before every test, `conftest.py` automatically:

1. Creates a fresh isolated temp folder
2. Seeds it with starter JSON files:

| File | Seed Content |
|---|---|
| `bids.json` | One bid — *Test School District* (id: BID-TEST-001, segment: K-12, status: Active) |
| `lineItems.json` | One line item — linked to BID-TEST-001, bidItem: "0001" |
| `emailThreads.json` | Empty list |
| `documents.json` | Empty list |

3. Points FastAPI at that temp folder — no real data files are touched
4. Deletes the folder after the test finishes

---

## How to Run

```bash
# All 29 tests
.\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v2.py -v

# With coverage report
.\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v2.py -v --cov=routers.bids --cov-report=term-missing

# Stop on first failure
.\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v2.py -v -x

# Single test
.\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v2.py::test_create_bid_with_line_items_updates_item_count -v
```

---

## Section 1 — List Bids (`GET /api/bids/`)

Returns all bids. Optional filters: `?segment=` and `?status=`.

### Tests

| # | Test Name | What it checks |
|---|---|---|
| 1 | `test_list_bids_returns_seed` | Response is a list and contains BID-TEST-001 |
| 2 | `test_list_bids_filter_segment` | `?segment=K-12` returns only K-12 bids |
| 3 | `test_list_bids_filter_segment_no_match` | Unknown segment returns `[]` not 404 |
| 4 | `test_list_bids_filter_status` | `?status=Active` returns only Active bids |
| 5 | `test_list_bids_filter_status_no_match` | `?status=Awarded` returns `[]` (no awarded bids in seed) |

---

## Section 2 — Get Single Bid (`GET /api/bids/{bid_id}`)

Returns one specific bid. Returns 404 if not found.

### Tests

| # | Test Name | What it checks |
|---|---|---|
| 6 | `test_get_bid_found` | BID-TEST-001 returns 200 and correct customer name |
| 7 | `test_get_bid_not_found` | A fake bid id returns 404 |

---

## Section 3 — Portal Templates (`GET /api/bids/portal-templates`)

Returns pre-built RFP templates. This test guards against a **route ordering bug** — if `/portal-templates` is declared after `/{bid_id}` in the router file, FastAPI would try to find a bid with id `"portal-templates"` and return 404.

### Test

| # | Test Name | What it checks |
|---|---|---|
| 8 | `test_portal_templates_not_mistaken_for_bid_id` | Returns 200 + a list (not treated as a bid id) |

---

## Section 4 — Create Bid (`POST /api/bids/`)

Creates a new bid. Key behaviours:
- Explicit `id` in body → used as-is
- No `id` in body → server auto-generates one
- No `status` → defaults to `"Active"`
- `lineItems` array in body → saved separately, `bid.items` count updated

### Tests

| # | Test Name | What it checks |
|---|---|---|
| 9 | `test_create_bid_with_explicit_id` | Sending an explicit id returns 201 with that id and correct customer |
| 10 | `test_create_bid_persists_after_explicit_id` | After creating, GET on the same id returns the bid |
| 11 | `test_create_bid_auto_generates_id` | Omitting id still produces a non-empty id in the response |
| 12 | `test_create_bid_defaults_status_to_active` | No status in body → response has `status = "Active"` |
| 13 | `test_create_bid_with_line_items_updates_item_count` | 1 line item in body → `bid.items = 1` in response |

**Request body used in test 13:**
```json
{
  "id": "BID-WITH-LI",
  "customer": "Line Item Customer",
  "segment": "K-12",
  "lineItems": [
    {
      "id": "LI-BID-WITH-LI-001",
      "bidId": "BID-WITH-LI",
      "bidItem": "0001",
      "description": "Test Product",
      "category": "Protein",
      "qty": 50,
      "unit": "CS"
    }
  ]
}
```

---

## Section 5 — Update Bid (`PATCH /api/bids/{bid_id}`)

Partial update — only the fields you send are changed. The `id` field cannot be changed. Returns 404 if bid doesn't exist.

### Tests

| # | Test Name | What it checks |
|---|---|---|
| 14 | `test_patch_bid_updates_status` | Patching `status` to "Solicitation" returns the updated value |
| 15 | `test_patch_bid_updates_notes` | Patching `notes` returns the updated value |
| 16 | `test_patch_bid_updates_compliance` | Patching `compliance` replaces the list |
| 17 | `test_patch_bid_id_immutable` | Sending a new `id` in body does NOT change the bid's id |
| 18 | `test_patch_bid_change_persists` | Patched value is still there on a follow-up GET (confirms it was saved) |
| 19 | `test_patch_bid_not_found` | Patching `NOPE` (fake id) returns 404 |
| 20 | `test_patch_bid_not_found_explicit` | Patching `BID-NOPE-XYZ` (another fake id) returns 404 |

---

## Section 6 — Delete Bid (`DELETE /api/bids/{bid_id}`)

Cascade delete — removes the bid and all related records.

**What gets deleted:**

| Data | File |
|---|---|
| The bid itself | `bids.json` |
| Line items for this bid | `lineItems.json` |
| Email threads for this bid | `emailThreads.json` |
| Pricing data for this bid | `pricingData.json` |
| Documents for this bid | `documents.json` |
| Submissions for this bid | `submissions.json` |
| Uploaded files on disk | `uploads/<bid_id>/` |

**Response shape:**
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

### Tests

| # | Test Name | What it checks |
|---|---|---|
| 21 | `test_delete_bid_returns_success_shape` | Response has `success=True`, `deleted` id, and `lineItems` key in `removed` |
| 22 | `test_delete_bid_cascades_line_items_count` | `removed.lineItems = 1` (the seed line item was deleted) |
| 23 | `test_delete_bid_removed_from_list` | Bid no longer appears in `GET /api/bids/` |
| 24 | `test_delete_bid_then_get_returns_404` | Fetching the deleted bid directly returns 404 |
| 25 | `test_delete_bid_not_found_returns_404` | Deleting a non-existent bid returns 404 |

---

## Section 7 — Line Items Sub-Resource (`GET /api/bids/{bid_id}/line-items`)

Returns all line items linked to a bid. Stored in a separate file (`lineItems.json`) and filtered by `bidId`.

### Tests

| # | Test Name | What it checks |
|---|---|---|
| 26 | `test_get_line_items_for_seed_bid` | BID-TEST-001 has exactly 1 line item with `bidItem = "0001"` |
| 27 | `test_get_line_items_unknown_bid_returns_empty` | Unknown bid id returns `[]` not 404 |

---

## Section 8 — Emails Sub-Resource (`GET /api/bids/{bid_id}/emails`)

Returns all email threads for a bid.

### Test

| # | Test Name | What it checks |
|---|---|---|
| 28 | `test_get_bid_emails_empty` | BID-TEST-001 has no emails in seed data → returns `[]` |

---

## Section 9 — Health Check (`GET /api/health`)

### Test

| # | Test Name | What it checks |
|---|---|---|
| 29 | `test_health_endpoint` | Returns 200 and `status = "ok"` |

---

## Full Summary Table

| # | Test Name | Endpoint | Method | Expected |
|---|---|---|---|---|
| 1 | test_list_bids_returns_seed | /api/bids/ | GET | 200 + seed bid in list |
| 2 | test_list_bids_filter_segment | /api/bids/?segment=K-12 | GET | 200 + only K-12 bids |
| 3 | test_list_bids_filter_segment_no_match | /api/bids/?segment=NoSuchSegment | GET | 200 + `[]` |
| 4 | test_list_bids_filter_status | /api/bids/?status=Active | GET | 200 + only Active bids |
| 5 | test_list_bids_filter_status_no_match | /api/bids/?status=Awarded | GET | 200 + `[]` |
| 6 | test_get_bid_found | /api/bids/BID-TEST-001 | GET | 200 + correct customer |
| 7 | test_get_bid_not_found | /api/bids/BID-DOES-NOT-EXIST | GET | 404 |
| 8 | test_portal_templates_not_mistaken_for_bid_id | /api/bids/portal-templates | GET | 200 + list |
| 9 | test_create_bid_with_explicit_id | /api/bids/ | POST | 201 + correct id & customer |
| 10 | test_create_bid_persists_after_explicit_id | /api/bids/ → /api/bids/BID-PERSIST-001 | POST → GET | 201 → 200 |
| 11 | test_create_bid_auto_generates_id | /api/bids/ | POST | 201 + non-empty id |
| 12 | test_create_bid_defaults_status_to_active | /api/bids/ | POST | 201 + status=Active |
| 13 | test_create_bid_with_line_items_updates_item_count | /api/bids/ | POST | 201 + items=1 |
| 14 | test_patch_bid_updates_status | /api/bids/BID-TEST-001 | PATCH | 200 + status=Solicitation |
| 15 | test_patch_bid_updates_notes | /api/bids/BID-TEST-001 | PATCH | 200 + updated notes |
| 16 | test_patch_bid_updates_compliance | /api/bids/BID-TEST-001 | PATCH | 200 + updated compliance |
| 17 | test_patch_bid_id_immutable | /api/bids/BID-TEST-001 | PATCH | 200 + id unchanged |
| 18 | test_patch_bid_change_persists | /api/bids/BID-TEST-001 → GET | PATCH → GET | 200 → value saved |
| 19 | test_patch_bid_not_found | /api/bids/NOPE | PATCH | 404 |
| 20 | test_patch_bid_not_found_explicit | /api/bids/BID-NOPE-XYZ | PATCH | 404 |
| 21 | test_delete_bid_returns_success_shape | /api/bids/BID-TEST-001 | DELETE | 200 + correct shape |
| 22 | test_delete_bid_cascades_line_items_count | /api/bids/BID-TEST-001 | DELETE | 200 + removed.lineItems=1 |
| 23 | test_delete_bid_removed_from_list | /api/bids/BID-TEST-001 → GET /api/bids/ | DELETE → GET | bid gone from list |
| 24 | test_delete_bid_then_get_returns_404 | /api/bids/BID-TEST-001 → GET | DELETE → GET | 404 |
| 25 | test_delete_bid_not_found_returns_404 | /api/bids/BID-DOES-NOT-EXIST-XYZ | DELETE | 404 |
| 26 | test_get_line_items_for_seed_bid | /api/bids/BID-TEST-001/line-items | GET | 200 + 1 item, bidItem=0001 |
| 27 | test_get_line_items_unknown_bid_returns_empty | /api/bids/BID-NO-ITEMS-XYZ/line-items | GET | 200 + `[]` |
| 28 | test_get_bid_emails_empty | /api/bids/BID-TEST-001/emails | GET | 200 + `[]` |
| 29 | test_health_endpoint | /api/health | GET | 200 + status=ok |
