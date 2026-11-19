# Unit Test Documentation — V3
## File: `tests/routers/test_bids_v3.py`

---

## What's New in V3 vs V2

| Feature | V2 (29 tests) | V3 (47 tests) |
|---|---|---|
| `GET /{bid_id}/files` | ❌ | ✅ New |
| `PATCH /{bid_id}/line-items/{id}` | ❌ | ✅ New |
| `GET /{bid_id}/emails/by-supplier` | ❌ | ✅ New |
| Combined segment + status filter | ❌ | ✅ New |
| Create with ALL optional fields | ❌ | ✅ New |
| Status workflow (Active→Solicitation→Awarded) | ❌ | ✅ New |
| Multiple bids listed together | ❌ | ✅ New |
| Patch multiple fields at once | ❌ | ✅ New |
| All cascade delete counts verified | ❌ | ✅ New |
| GET bid returns all expected fields | ❌ | ✅ New |
| Coverage | 30% | 34% |

---

## Where Data Comes From

Every test starts with a clean environment. Three sources populate it:

### 1. `conftest.py` — Automatic seed data (loaded before every test)

| File | Content |
|---|---|
| `bids.json` | `BID-TEST-001` — customer: *Test School District*, segment: K-12, status: Active, items: 0 |
| `lineItems.json` | `LI-BID-TEST-001-001` — bidId: BID-TEST-001, bidItem: "0001", qty: 100, category: Protein |
| `suppliers.json` | `SM-001` — *Test Supplier Inc*, category: Protein |
| `emailThreads.json` | Empty `[]` |
| `documents.json` | Empty `[]` |

### 2. Test request body — Values the test explicitly sends

```python
resp = await client.post("/api/bids/", json={
    "id": "BID-FULL-001",        ← test chose this
    "customer": "Full Fields School",
    "compliance": ["USDA"],
})
```

### 3. Server defaults — Fields filled automatically when omitted

| Field | Default |
|---|---|
| `status` | `"Active"` |
| `items` | `0` |
| `notes` | `""` |
| `uploadedFiles` | `[]` |
| `suppliersContacted` | `0` |
| `responsesReceived` | `0` |
| `solicitedSuppliers` | `[]` |

---

## How to Run

```bash
# Navigate to backend folder first
cd backend_py

# All 47 tests
.\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v3.py -v

# With coverage report
.\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v3.py -v --cov=routers.bids --cov-report=term-missing

# Stop on first failure
.\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v3.py -v -x

# One specific test
.\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v3.py::test_status_workflow_progression -v
```

---

## Section 1 — List Bids (`GET /api/bids/`)

**Filters:** `?segment=` and `?status=` can be combined.

| # | Test Name | What it checks |
|---|---|---|
| 1 | `test_list_bids_returns_seed` | No filter → BID-TEST-001 appears |
| 2 | `test_list_bids_filter_segment_match` | `?segment=K-12` → only K-12 bids |
| 3 | `test_list_bids_filter_segment_no_match` | Unknown segment → `[]` |
| 4 | `test_list_bids_filter_status_match` | `?status=Active` → only Active bids |
| 5 | `test_list_bids_filter_status_no_match` | `?status=Awarded` → `[]` (none in seed) |
| 6 | `test_list_bids_combined_segment_and_status` | Both filters together — Healthcare bid must NOT appear in K-12+Active results |
| 7 | `test_list_multiple_bids` | Creates 2 extra bids — all 3 must appear in the list |

**Key for test 6:**
```
Seed:  BID-TEST-001  segment=K-12      status=Active  ← appears
New:   BID-HEALTH-001  segment=Healthcare  status=Active  ← filtered out
Filter: ?segment=K-12&status=Active
```

---

## Section 2 — Get Single Bid (`GET /api/bids/{bid_id}`)

| # | Test Name | What it checks |
|---|---|---|
| 8 | `test_get_bid_found` | BID-TEST-001 returns 200 + correct customer name |
| 9 | `test_get_bid_not_found` | Fake id returns 404 |
| 10 | `test_get_bid_returns_all_expected_fields` | Response contains all fields the frontend needs: `id`, `customer`, `segment`, `status`, `items`, `suppliersContacted`, `responsesReceived`, `compliance`, `uploadedFiles` |

---

## Section 3 — Portal Templates (`GET /api/bids/portal-templates`)

Route ordering guard — must be declared before `/{bid_id}` in the router file.

| # | Test Name | What it checks |
|---|---|---|
| 11 | `test_portal_templates_not_mistaken_for_bid_id` | Returns 200 + list, not treated as a bid id |

---

## Section 4 — Create Bid (`POST /api/bids/`)

| # | Test Name | What it checks |
|---|---|---|
| 12 | `test_create_bid_minimal_body` | Only id/customer/segment sent → all server defaults applied correctly |
| 13 | `test_create_bid_with_all_optional_fields` | Every optional field sent → all are honoured in the response |
| 14 | `test_create_bid_auto_generates_id` | No id in body → server assigns a non-empty id |
| 15 | `test_create_bid_defaults_status_to_active` | No status in body → defaults to "Active" |
| 16 | `test_create_bid_with_line_items_updates_count` | 1 line item in body → `bid.items = 1` |
| 17 | `test_create_bid_persists` | After POST, GET returns the same bid |
| 18 | `test_create_bid_appears_in_list` | After POST, bid appears in `GET /api/bids/` |

**All optional fields tested in test 13:**
```json
{
  "opco": "016",
  "opcoName": "Sysco Boston",
  "region": "Northeast",
  "customerDue": "2026-09-01",
  "internalDue": "2026-08-25",
  "bidRelease": "2026-08-01",
  "notes": "High priority bid",
  "compliance": ["Child Nutrition", "USDA"],
  "itemCategories": ["Protein", "Dairy"]
}
```

---

## Section 5 — Update Bid (`PATCH /api/bids/{bid_id}`)

| # | Test Name | What it checks |
|---|---|---|
| 19 | `test_patch_bid_updates_status` | Patching status to "Solicitation" works |
| 20 | `test_patch_bid_updates_notes` | Patching notes works |
| 21 | `test_patch_bid_updates_compliance` | Patching compliance (list) works |
| 22 | `test_patch_bid_updates_multiple_fields_at_once` | Patching status + notes + internalDue together — all update |
| 23 | `test_patch_bid_id_immutable` | Sending new id in body → id stays unchanged |
| 24 | `test_patch_bid_other_fields_unchanged` | Patching notes only → customer and segment stay the same |
| 25 | `test_patch_bid_change_persists` | Patch then re-fetch → change was written to disk |
| 26 | `test_patch_bid_not_found` | Fake id → 404 |
| 27 | `test_status_workflow_progression` | Full lifecycle: Active → Solicitation → Analysis → Awarded, each step verified |

**Status workflow (test 27):**
```
Active → Solicitation → Analysis → Awarded
  ↑ seed      ↑ step 1       ↑ step 2     ↑ step 3
```

---

## Section 6 — Delete Bid (`DELETE /api/bids/{bid_id}`)

Cascade delete — removes the bid and all related records.

**Full response shape:**
```json
{
  "success": true,
  "deleted": "BID-TEST-001",
  "removed": {
    "lineItems": 1,
    "emails": 0,
    "pricing": 0,
    "documents": 0,
    "submissions": 0,
    "files": 0
  }
}
```

| # | Test Name | What it checks |
|---|---|---|
| 28 | `test_delete_bid_response_shape` | All 6 keys present in `removed` (lineItems, emails, pricing, documents, submissions, files) |
| 29 | `test_delete_bid_cascade_line_items_count` | `removed.lineItems = 1` (seed has 1 line item) |
| 30 | `test_delete_bid_cascade_zero_emails` | `removed.emails = 0` (no emails in seed) |
| 31 | `test_delete_bid_removed_from_list` | Bid gone from `GET /api/bids/` |
| 32 | `test_delete_bid_then_get_returns_404` | Direct GET on deleted id returns 404 |
| 33 | `test_delete_bid_not_found_returns_404` | Deleting non-existent id returns 404 |
| 34 | `test_delete_cleans_line_items` | After delete, line-items endpoint returns `[]` for that bid |

---

## Section 7 — Uploaded Files (`GET /api/bids/{bid_id}/files`) ← New in V3

Returns the `uploadedFiles` array from the bid object. Unlike `/line-items`, this returns **404** for a non-existent bid (not an empty list) because it has to load the bid first.

| # | Test Name | What it checks |
|---|---|---|
| 35 | `test_get_bid_files_empty_for_seed` | Seed bid has no files → `[]` |
| 36 | `test_get_bid_files_not_found_returns_404` | Non-existent bid → 404 |

---

## Section 8 — Line Items (`GET /api/bids/{bid_id}/line-items`)

| # | Test Name | What it checks |
|---|---|---|
| 37 | `test_get_line_items_for_seed_bid` | BID-TEST-001 has 1 item, `bidItem="0001"`, `bidId` correct |
| 38 | `test_get_line_items_unknown_bid_returns_empty` | Unknown bid → `[]` (not 404) |

---

## Section 9 — Update Line Item (`PATCH /api/bids/{bid_id}/line-items/{line_id}`) ← New in V3

Updates a specific line item. The `id` and `bidId` fields are immutable.

**Seed line item:** `LI-BID-TEST-001-001` — qty: 100, status: "No Response"

| # | Test Name | What it checks |
|---|---|---|
| 39 | `test_patch_line_item_updates_qty` | Patching qty to 200 works |
| 40 | `test_patch_line_item_updates_status` | Patching status to "Awarded" works |
| 41 | `test_patch_line_item_id_immutable` | Sending new id in body → id stays unchanged |
| 42 | `test_patch_line_item_not_found_returns_404` | Fake line item id → 404 |
| 43 | `test_patch_line_item_change_persists` | Patch qty → re-fetch list → updated value is there |

---

## Section 10 — Emails (`GET /api/bids/{bid_id}/emails`)

| # | Test Name | What it checks |
|---|---|---|
| 44 | `test_get_bid_emails_empty` | Seed has no emails → `[]` |

---

## Section 11 — Emails by Supplier (`GET /api/bids/{bid_id}/emails/by-supplier`) ← New in V3

Returns supplier names with their matching email threads grouped together. Requires the bid to exist — returns 404 otherwise.

| # | Test Name | What it checks |
|---|---|---|
| 45 | `test_get_emails_by_supplier_empty` | Seed has no solicited suppliers → empty list |
| 46 | `test_get_emails_by_supplier_not_found_returns_404` | Non-existent bid → 404 |

---

## Section 12 — Health Check (`GET /api/health`)

| # | Test Name | What it checks |
|---|---|---|
| 47 | `test_health_endpoint` | Returns 200, `status="ok"`, includes `llmProvider` and `dbBackend` |

---

## Full Summary Table

| # | Test Name | Endpoint | Method | Expected |
|---|---|---|---|---|
| 1 | test_list_bids_returns_seed | /api/bids/ | GET | 200 |
| 2 | test_list_bids_filter_segment_match | /api/bids/?segment=K-12 | GET | 200 |
| 3 | test_list_bids_filter_segment_no_match | /api/bids/?segment=Unknown | GET | 200 `[]` |
| 4 | test_list_bids_filter_status_match | /api/bids/?status=Active | GET | 200 |
| 5 | test_list_bids_filter_status_no_match | /api/bids/?status=Awarded | GET | 200 `[]` |
| 6 | test_list_bids_combined_segment_and_status | /api/bids/?segment=K-12&status=Active | GET | 200 |
| 7 | test_list_multiple_bids | /api/bids/ | GET | 200, 3 bids |
| 8 | test_get_bid_found | /api/bids/BID-TEST-001 | GET | 200 |
| 9 | test_get_bid_not_found | /api/bids/BID-DOES-NOT-EXIST | GET | 404 |
| 10 | test_get_bid_returns_all_expected_fields | /api/bids/BID-TEST-001 | GET | 200, all fields present |
| 11 | test_portal_templates_not_mistaken_for_bid_id | /api/bids/portal-templates | GET | 200, list |
| 12 | test_create_bid_minimal_body | /api/bids/ | POST | 201, defaults applied |
| 13 | test_create_bid_with_all_optional_fields | /api/bids/ | POST | 201, all fields saved |
| 14 | test_create_bid_auto_generates_id | /api/bids/ | POST | 201, id non-empty |
| 15 | test_create_bid_defaults_status_to_active | /api/bids/ | POST | 201, status=Active |
| 16 | test_create_bid_with_line_items_updates_count | /api/bids/ | POST | 201, items=1 |
| 17 | test_create_bid_persists | /api/bids/ → GET | POST → GET | 201 → 200 |
| 18 | test_create_bid_appears_in_list | /api/bids/ → GET /api/bids/ | POST → GET | 201 → in list |
| 19 | test_patch_bid_updates_status | /api/bids/BID-TEST-001 | PATCH | 200 |
| 20 | test_patch_bid_updates_notes | /api/bids/BID-TEST-001 | PATCH | 200 |
| 21 | test_patch_bid_updates_compliance | /api/bids/BID-TEST-001 | PATCH | 200 |
| 22 | test_patch_bid_updates_multiple_fields_at_once | /api/bids/BID-TEST-001 | PATCH | 200, all 3 fields updated |
| 23 | test_patch_bid_id_immutable | /api/bids/BID-TEST-001 | PATCH | 200, id unchanged |
| 24 | test_patch_bid_other_fields_unchanged | /api/bids/BID-TEST-001 | PATCH | 200, customer/segment intact |
| 25 | test_patch_bid_change_persists | /api/bids/BID-TEST-001 → GET | PATCH → GET | saved to disk |
| 26 | test_patch_bid_not_found | /api/bids/BID-NOPE-XYZ | PATCH | 404 |
| 27 | test_status_workflow_progression | /api/bids/BID-TEST-001 | PATCH x3 | Active→Solicitation→Analysis→Awarded |
| 28 | test_delete_bid_response_shape | /api/bids/BID-TEST-001 | DELETE | 200, all 6 keys in removed |
| 29 | test_delete_bid_cascade_line_items_count | /api/bids/BID-TEST-001 | DELETE | removed.lineItems=1 |
| 30 | test_delete_bid_cascade_zero_emails | /api/bids/BID-TEST-001 | DELETE | removed.emails=0 |
| 31 | test_delete_bid_removed_from_list | /api/bids/BID-TEST-001 → GET /api/bids/ | DELETE → GET | bid gone |
| 32 | test_delete_bid_then_get_returns_404 | /api/bids/BID-TEST-001 → GET | DELETE → GET | 404 |
| 33 | test_delete_bid_not_found_returns_404 | /api/bids/BID-NO-SUCH-ID | DELETE | 404 |
| 34 | test_delete_cleans_line_items | /api/bids/BID-TEST-001 → GET line-items | DELETE → GET | `[]` |
| 35 | test_get_bid_files_empty_for_seed | /api/bids/BID-TEST-001/files | GET | 200 `[]` |
| 36 | test_get_bid_files_not_found_returns_404 | /api/bids/BID-NO-SUCH-ID/files | GET | 404 |
| 37 | test_get_line_items_for_seed_bid | /api/bids/BID-TEST-001/line-items | GET | 200, 1 item |
| 38 | test_get_line_items_unknown_bid_returns_empty | /api/bids/BID-NO-ITEMS-XYZ/line-items | GET | 200 `[]` |
| 39 | test_patch_line_item_updates_qty | /api/bids/BID-TEST-001/line-items/LI-BID-TEST-001-001 | PATCH | 200, qty=200 |
| 40 | test_patch_line_item_updates_status | /api/bids/BID-TEST-001/line-items/LI-BID-TEST-001-001 | PATCH | 200, status=Awarded |
| 41 | test_patch_line_item_id_immutable | /api/bids/BID-TEST-001/line-items/LI-BID-TEST-001-001 | PATCH | 200, id unchanged |
| 42 | test_patch_line_item_not_found_returns_404 | /api/bids/BID-TEST-001/line-items/LI-DOES-NOT-EXIST | PATCH | 404 |
| 43 | test_patch_line_item_change_persists | /api/bids/BID-TEST-001/line-items/LI-BID-TEST-001-001 → GET | PATCH → GET | saved |
| 44 | test_get_bid_emails_empty | /api/bids/BID-TEST-001/emails | GET | 200 `[]` |
| 45 | test_get_emails_by_supplier_empty | /api/bids/BID-TEST-001/emails/by-supplier | GET | 200, list |
| 46 | test_get_emails_by_supplier_not_found_returns_404 | /api/bids/BID-NO-SUCH-ID/emails/by-supplier | GET | 404 |
| 47 | test_health_endpoint | /api/health | GET | 200, status=ok |
