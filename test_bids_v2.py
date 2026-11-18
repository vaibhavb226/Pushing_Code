"""
Comprehensive v2 tests for /api/bids/* endpoints.

Combines everything from test_bids.py + the bids section of test_suppliers_bids_extended.py
into one complete file covering all routes and edge cases.

Run all:
    .\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v2.py -v

Run with coverage:
    .\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v2.py -v --cov=routers.bids --cov-report=term-missing

Run a single test:
    .\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v2.py::test_create_bid_with_line_items_updates_item_count -v
"""
from __future__ import annotations

from httpx import AsyncClient


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/  — List all bids
#
# No filters → returns every bid in the system.
# With filters → ?segment=  ?status=  narrows the results.
# Seed: one bid → id=BID-TEST-001, segment=K-12, status=Active
# ══════════════════════════════════════════════════════════════════════════════

async def test_list_bids_returns_seed(client: AsyncClient) -> None:
    # Basic list with no filters — seed bid must be present
    resp = await client.get("/api/bids/")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(b["id"] == "BID-TEST-001" for b in data)


async def test_list_bids_filter_segment(client: AsyncClient) -> None:
    # Only bids matching that segment should come through
    resp = await client.get("/api/bids/?segment=K-12")
    assert resp.status_code == 200
    data = resp.json()
    assert all(b["segment"] == "K-12" for b in data)
    assert len(data) >= 1


async def test_list_bids_filter_segment_no_match(client: AsyncClient) -> None:
    # A segment with no bids → empty list, not 404
    resp = await client.get("/api/bids/?segment=NoSuchSegment")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_bids_filter_status(client: AsyncClient) -> None:
    # Only bids with that status should come through
    resp = await client.get("/api/bids/?status=Active")
    assert resp.status_code == 200
    data = resp.json()
    assert all(b["status"] == "Active" for b in data)


async def test_list_bids_filter_status_no_match(client: AsyncClient) -> None:
    # No bid in seed data has status=Awarded → empty list
    resp = await client.get("/api/bids/?status=Awarded")
    assert resp.status_code == 200
    assert resp.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/{bid_id}  — Fetch a single bid
#
# Returns the full bid object on success.
# Returns 404 if the id does not exist.
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_bid_found(client: AsyncClient) -> None:
    # Seed bid must be fetchable by id and return correct customer name
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.status_code == 200
    assert resp.json()["customer"] == "Test School District"


async def test_get_bid_not_found(client: AsyncClient) -> None:
    # A made-up id must return 404, not a 500 or empty object
    resp = await client.get("/api/bids/BID-DOES-NOT-EXIST")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/portal-templates  — Route ordering safety check
#
# IMPORTANT: This route must be declared BEFORE /{bid_id} in the router file.
# If the order is reversed, FastAPI treats "portal-templates" as a bid_id
# and returns 404 instead of the templates list.
# ══════════════════════════════════════════════════════════════════════════════

async def test_portal_templates_not_mistaken_for_bid_id(client: AsyncClient) -> None:
    # Must return 200 + a list — confirms route ordering is correct
    resp = await client.get("/api/bids/portal-templates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/bids/  — Create a bid
#
# - Explicit id → uses it as-is
# - No id → server auto-generates one
# - No status → defaults to "Active"
# - lineItems in body → saved separately, bid.items count updated
# - After creation, GET must return the same bid (confirms persistence)
# ══════════════════════════════════════════════════════════════════════════════

async def test_create_bid_with_explicit_id(client: AsyncClient) -> None:
    # Sending an explicit id → must be used as-is, customer name returned correctly
    resp = await client.post("/api/bids/", json={
        "id": "BID-NEW-001",
        "customer": "New Customer",
        "segment": "Healthcare",
        "customerDue": "2026-08-01",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "BID-NEW-001"
    assert data["customer"] == "New Customer"


async def test_create_bid_persists_after_explicit_id(client: AsyncClient) -> None:
    # After creating, a GET on the same id must succeed
    await client.post("/api/bids/", json={
        "id": "BID-PERSIST-001",
        "customer": "Persist Customer",
        "segment": "K-12",
    })
    resp = await client.get("/api/bids/BID-PERSIST-001")
    assert resp.status_code == 200
    assert resp.json()["customer"] == "Persist Customer"


async def test_create_bid_auto_generates_id(client: AsyncClient) -> None:
    # Omit id → server must assign a non-empty one
    resp = await client.post("/api/bids/", json={
        "customer": "Auto ID Customer",
        "segment": "K-12",
        "customerDue": "2026-09-01",
    })
    assert resp.status_code == 201
    assert resp.json()["id"] != ""


async def test_create_bid_defaults_status_to_active(client: AsyncClient) -> None:
    # No status in body → must default to "Active"
    resp = await client.post("/api/bids/", json={
        "id": "BID-STATUS-DEFAULT",
        "customer": "Status Test",
        "segment": "K-12",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "Active"


async def test_create_bid_with_line_items_updates_item_count(client: AsyncClient) -> None:
    # lineItems in the POST body → saved to lineItems.json, bid.items set to count
    resp = await client.post("/api/bids/", json={
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
                "unit": "CS",
            }
        ],
    })
    assert resp.status_code == 201
    assert resp.json()["items"] == 1


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/bids/{bid_id}  — Partial update
#
# Only the fields you send are changed — everything else stays the same.
# The `id` field is immutable — sending a new id in the body is silently ignored.
# Returns the full updated bid on success, 404 if bid_id doesn't exist.
# ══════════════════════════════════════════════════════════════════════════════

async def test_patch_bid_updates_status(client: AsyncClient) -> None:
    # Most common patch — changing the bid status through its workflow
    resp = await client.patch("/api/bids/BID-TEST-001", json={"status": "Solicitation"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Solicitation"


async def test_patch_bid_updates_notes(client: AsyncClient) -> None:
    resp = await client.patch("/api/bids/BID-TEST-001", json={"notes": "Important note"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Important note"


async def test_patch_bid_updates_compliance(client: AsyncClient) -> None:
    # Compliance is a list — patching it replaces the entire list
    resp = await client.patch("/api/bids/BID-TEST-001", json={"compliance": ["USDA", "Child Nutrition"]})
    assert resp.status_code == 200
    assert "USDA" in resp.json()["compliance"]


async def test_patch_bid_id_immutable(client: AsyncClient) -> None:
    # Sending a different id in the body must NOT change the bid's id
    resp = await client.patch("/api/bids/BID-TEST-001", json={"id": "HACKED-ID"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "BID-TEST-001"


async def test_patch_bid_change_persists(client: AsyncClient) -> None:
    # Patch then re-fetch — confirms the value was actually written to disk
    await client.patch("/api/bids/BID-TEST-001", json={"status": "Awarded"})
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.json()["status"] == "Awarded"


async def test_patch_bid_not_found(client: AsyncClient) -> None:
    resp = await client.patch("/api/bids/NOPE", json={"status": "Active"})
    assert resp.status_code == 404


async def test_patch_bid_not_found_explicit(client: AsyncClient) -> None:
    resp = await client.patch("/api/bids/BID-NOPE-XYZ", json={"status": "Active"})
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/bids/{bid_id}  — Cascade delete
#
# Removes the bid AND all related records:
#   lineItems, emailThreads, pricingData, documents, submissions, uploaded files
#
# Response: { "success": True, "deleted": "<id>", "removed": { "lineItems": N, ... } }
# Returns 404 if the bid doesn't exist.
# ══════════════════════════════════════════════════════════════════════════════

async def test_delete_bid_returns_success_shape(client: AsyncClient) -> None:
    # Response must have success=True, the deleted id, and a removed counts object
    resp = await client.delete("/api/bids/BID-TEST-001")
    assert resp.status_code == 200
    result = resp.json()
    assert result["success"] is True
    assert result["deleted"] == "BID-TEST-001"
    assert "lineItems" in result["removed"]


async def test_delete_bid_cascades_line_items_count(client: AsyncClient) -> None:
    # Seed has 1 line item for BID-TEST-001 → removed.lineItems must be 1
    resp = await client.delete("/api/bids/BID-TEST-001")
    assert resp.status_code == 200
    assert resp.json()["removed"]["lineItems"] == 1


async def test_delete_bid_removed_from_list(client: AsyncClient) -> None:
    # After delete, bid must not appear in GET /api/bids/
    await client.delete("/api/bids/BID-TEST-001")
    resp = await client.get("/api/bids/")
    assert not any(b["id"] == "BID-TEST-001" for b in resp.json())


async def test_delete_bid_then_get_returns_404(client: AsyncClient) -> None:
    # After delete, fetching the same id directly must return 404
    await client.delete("/api/bids/BID-TEST-001")
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.status_code == 404


async def test_delete_bid_not_found_returns_404(client: AsyncClient) -> None:
    # Deleting a non-existent bid must return 404, not 200 or 500
    resp = await client.delete("/api/bids/BID-DOES-NOT-EXIST-XYZ")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/{bid_id}/line-items  — Sub-resource: line items
#
# Returns all line items linked to the given bid.
# Seed data has 1 line item for BID-TEST-001 with bidItem="0001".
# An unknown bid id returns an empty list (not 404) — items are stored
# separately and filtered by bidId, so no match = empty result.
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_line_items_for_seed_bid(client: AsyncClient) -> None:
    # Seed bid has exactly 1 line item
    resp = await client.get("/api/bids/BID-TEST-001/line-items")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["bidItem"] == "0001"


async def test_get_line_items_unknown_bid_returns_empty(client: AsyncClient) -> None:
    # Unknown bid id → empty list, not 404
    resp = await client.get("/api/bids/BID-NO-ITEMS-XYZ/line-items")
    assert resp.status_code == 200
    assert resp.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/{bid_id}/emails  — Sub-resource: email threads
#
# Returns all email threads for the given bid.
# Seed data has no emails → always returns empty list.
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_bid_emails_empty(client: AsyncClient) -> None:
    # No emails seeded → must return empty list
    resp = await client.get("/api/bids/BID-TEST-001/emails")
    assert resp.status_code == 200
    assert resp.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/health  — Server health check
# ══════════════════════════════════════════════════════════════════════════════

async def test_health_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
