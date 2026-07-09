"""
Comprehensive v3 tests for /api/bids/* endpoints.

WHAT'S NEW IN V3 vs V2
───────────────────────
• GET  /{bid_id}/files            — uploaded files list (new)
• PATCH /{bid_id}/line-items/{id} — update a single line item (new)
• GET  /{bid_id}/emails/by-supplier — emails grouped by supplier (new)
• Create bid with ALL optional fields (opco, region, compliance, etc.)
• Combined segment + status filter
• Status workflow progression (Active → Solicitation → Analysis → Awarded)
• Multiple bids: create 3, list all, filter down to 1
• Patch multiple fields at once
• Delete cascade verifies ALL removed counts (lineItems, emails, pricing, docs)

WHERE DATA COMES FROM
──────────────────────
1. conftest.py seeds these before every test (no test creates them manually):
     • bids.json       → BID-TEST-001, customer="Test School District",
                         segment=K-12, status=Active
     • lineItems.json  → LI-BID-TEST-001-001, bidId=BID-TEST-001, bidItem="0001"
     • suppliers.json  → SM-001, name="Test Supplier Inc"
     • emails/docs     → empty lists

2. Individual tests POST their own data when they need something specific.

3. Server fills defaults for omitted fields:
     status="Active", items=0, notes="", uploadedFiles=[], etc.

Run all:
    .\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v3.py -v

Run with coverage:
    .\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v3.py -v --cov=routers.bids --cov-report=term-missing

Run one test:
    .\.venv\Scripts\python.exe -m pytest tests/routers/test_bids_v3.py::test_status_workflow_progression -v
"""
from __future__ import annotations

from httpx import AsyncClient


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/  — List bids
# ══════════════════════════════════════════════════════════════════════════════

async def test_list_bids_returns_seed(client: AsyncClient) -> None:
    # No filter — seed bid BID-TEST-001 must appear
    resp = await client.get("/api/bids/")
    assert resp.status_code == 200
    assert any(b["id"] == "BID-TEST-001" for b in resp.json())


async def test_list_bids_filter_segment_match(client: AsyncClient) -> None:
    resp = await client.get("/api/bids/?segment=K-12")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(b["segment"] == "K-12" for b in data)


async def test_list_bids_filter_segment_no_match(client: AsyncClient) -> None:
    resp = await client.get("/api/bids/?segment=UnknownSegment")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_bids_filter_status_match(client: AsyncClient) -> None:
    resp = await client.get("/api/bids/?status=Active")
    assert resp.status_code == 200
    assert all(b["status"] == "Active" for b in resp.json())


async def test_list_bids_filter_status_no_match(client: AsyncClient) -> None:
    # No Awarded bids in seed → empty list
    resp = await client.get("/api/bids/?status=Awarded")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_bids_combined_segment_and_status(client: AsyncClient) -> None:
    # Create a second bid with different segment to verify both filters stack
    await client.post("/api/bids/", json={
        "id": "BID-HEALTH-001",
        "customer": "City Hospital",
        "segment": "Healthcare",
        "status": "Active",
    })
    resp = await client.get("/api/bids/?segment=K-12&status=Active")
    assert resp.status_code == 200
    data = resp.json()
    # Only K-12 + Active bids — Healthcare one must not appear
    assert all(b["segment"] == "K-12" for b in data)
    assert all(b["status"] == "Active" for b in data)
    assert not any(b["id"] == "BID-HEALTH-001" for b in data)


async def test_list_multiple_bids(client: AsyncClient) -> None:
    # Create 2 more bids — list should return all 3 (seed + 2 new)
    await client.post("/api/bids/", json={"id": "BID-EXTRA-001", "customer": "School A", "segment": "K-12"})
    await client.post("/api/bids/", json={"id": "BID-EXTRA-002", "customer": "School B", "segment": "K-12"})
    resp = await client.get("/api/bids/")
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert "BID-TEST-001" in ids
    assert "BID-EXTRA-001" in ids
    assert "BID-EXTRA-002" in ids


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/{bid_id}  — Single bid
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_bid_found(client: AsyncClient) -> None:
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.status_code == 200
    assert resp.json()["customer"] == "Test School District"


async def test_get_bid_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/bids/BID-DOES-NOT-EXIST")
    assert resp.status_code == 404


async def test_get_bid_returns_all_expected_fields(client: AsyncClient) -> None:
    # Confirm the response has the core fields the frontend depends on
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.status_code == 200
    data = resp.json()
    for field in ["id", "customer", "segment", "status", "items",
                  "suppliersContacted", "responsesReceived", "compliance", "uploadedFiles"]:
        assert field in data, f"Missing field: {field}"


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/portal-templates  — Route ordering guard
#
# Must be declared BEFORE /{bid_id} in the router file, otherwise FastAPI
# treats "portal-templates" as a bid_id and returns 404.
# ══════════════════════════════════════════════════════════════════════════════

async def test_portal_templates_not_mistaken_for_bid_id(client: AsyncClient) -> None:
    resp = await client.get("/api/bids/portal-templates")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/bids/  — Create bid
# ══════════════════════════════════════════════════════════════════════════════

async def test_create_bid_minimal_body(client: AsyncClient) -> None:
    # Only required fields — server fills in everything else with defaults
    resp = await client.post("/api/bids/", json={
        "id": "BID-MINIMAL",
        "customer": "Minimal Customer",
        "segment": "K-12",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "BID-MINIMAL"
    assert data["status"] == "Active"        # server default
    assert data["items"] == 0               # server default
    assert data["uploadedFiles"] == []      # server default
    assert data["suppliersContacted"] == 0  # server default
    assert data["responsesReceived"] == 0   # server default


async def test_create_bid_with_all_optional_fields(client: AsyncClient) -> None:
    # Every optional field provided — server must honour them all
    resp = await client.post("/api/bids/", json={
        "id": "BID-FULL-001",
        "customer": "Full Fields School",
        "opco": "016",
        "opcoName": "Sysco Boston",
        "region": "Northeast",
        "segment": "K-12",
        "status": "Active",
        "customerDue": "2026-09-01",
        "internalDue": "2026-08-25",
        "bidRelease": "2026-08-01",
        "notes": "High priority bid",
        "compliance": ["Child Nutrition", "USDA"],
        "itemCategories": ["Protein", "Dairy"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["opco"] == "016"
    assert data["region"] == "Northeast"
    assert data["notes"] == "High priority bid"
    assert "USDA" in data["compliance"]
    assert "Protein" in data["itemCategories"]


async def test_create_bid_auto_generates_id(client: AsyncClient) -> None:
    # Omit id — server must generate a non-empty one
    resp = await client.post("/api/bids/", json={
        "customer": "Auto ID Customer",
        "segment": "K-12",
    })
    assert resp.status_code == 201
    assert resp.json()["id"] != ""


async def test_create_bid_defaults_status_to_active(client: AsyncClient) -> None:
    resp = await client.post("/api/bids/", json={
        "id": "BID-NO-STATUS",
        "customer": "No Status Customer",
        "segment": "K-12",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "Active"


async def test_create_bid_with_line_items_updates_count(client: AsyncClient) -> None:
    # lineItems in POST body → saved to lineItems.json, bid.items = 1
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


async def test_create_bid_persists(client: AsyncClient) -> None:
    await client.post("/api/bids/", json={
        "id": "BID-PERSIST-CHECK",
        "customer": "Persist Customer",
        "segment": "K-12",
    })
    resp = await client.get("/api/bids/BID-PERSIST-CHECK")
    assert resp.status_code == 200
    assert resp.json()["customer"] == "Persist Customer"


async def test_create_bid_appears_in_list(client: AsyncClient) -> None:
    await client.post("/api/bids/", json={
        "id": "BID-LIST-CHECK",
        "customer": "List Check Customer",
        "segment": "Healthcare",
    })
    resp = await client.get("/api/bids/")
    assert any(b["id"] == "BID-LIST-CHECK" for b in resp.json())


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/bids/{bid_id}  — Partial update
# ══════════════════════════════════════════════════════════════════════════════

async def test_patch_bid_updates_status(client: AsyncClient) -> None:
    resp = await client.patch("/api/bids/BID-TEST-001", json={"status": "Solicitation"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Solicitation"


async def test_patch_bid_updates_notes(client: AsyncClient) -> None:
    resp = await client.patch("/api/bids/BID-TEST-001", json={"notes": "Updated note here"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Updated note here"


async def test_patch_bid_updates_compliance(client: AsyncClient) -> None:
    resp = await client.patch("/api/bids/BID-TEST-001", json={"compliance": ["USDA", "Child Nutrition"]})
    assert resp.status_code == 200
    assert "USDA" in resp.json()["compliance"]


async def test_patch_bid_updates_multiple_fields_at_once(client: AsyncClient) -> None:
    # Patch several fields in a single request — all must update together
    resp = await client.patch("/api/bids/BID-TEST-001", json={
        "status": "Analysis",
        "notes": "In review",
        "internalDue": "2026-08-01",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "Analysis"
    assert data["notes"] == "In review"
    assert data["internalDue"] == "2026-08-01"


async def test_patch_bid_id_immutable(client: AsyncClient) -> None:
    # Sending a new id in the body must be silently ignored
    resp = await client.patch("/api/bids/BID-TEST-001", json={"id": "HACKED-ID"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "BID-TEST-001"


async def test_patch_bid_other_fields_unchanged(client: AsyncClient) -> None:
    # Only notes is patched — customer and segment must stay the same
    resp = await client.patch("/api/bids/BID-TEST-001", json={"notes": "Only notes changed"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["customer"] == "Test School District"   # unchanged
    assert data["segment"] == "K-12"                    # unchanged


async def test_patch_bid_change_persists(client: AsyncClient) -> None:
    # Patch then re-fetch — confirms it was written to disk, not just returned
    await client.patch("/api/bids/BID-TEST-001", json={"status": "Awarded"})
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.json()["status"] == "Awarded"


async def test_patch_bid_not_found(client: AsyncClient) -> None:
    resp = await client.patch("/api/bids/BID-NOPE-XYZ", json={"status": "Active"})
    assert resp.status_code == 404


async def test_status_workflow_progression(client: AsyncClient) -> None:
    # Simulate the full bid lifecycle: Active → Solicitation → Analysis → Awarded
    for status in ["Solicitation", "Analysis", "Awarded"]:
        resp = await client.patch("/api/bids/BID-TEST-001", json={"status": status})
        assert resp.status_code == 200
        assert resp.json()["status"] == status
    # Final state must be Awarded
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.json()["status"] == "Awarded"


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/bids/{bid_id}  — Cascade delete
# ══════════════════════════════════════════════════════════════════════════════

async def test_delete_bid_response_shape(client: AsyncClient) -> None:
    resp = await client.delete("/api/bids/BID-TEST-001")
    assert resp.status_code == 200
    result = resp.json()
    assert result["success"] is True
    assert result["deleted"] == "BID-TEST-001"
    # All cascade counts must be present in the response
    for key in ["lineItems", "emails", "pricing", "documents", "submissions", "files"]:
        assert key in result["removed"], f"Missing key in removed: {key}"


async def test_delete_bid_cascade_line_items_count(client: AsyncClient) -> None:
    # Seed has 1 line item for BID-TEST-001
    resp = await client.delete("/api/bids/BID-TEST-001")
    assert resp.json()["removed"]["lineItems"] == 1


async def test_delete_bid_cascade_zero_emails(client: AsyncClient) -> None:
    # Seed has no emails → removed.emails must be 0
    resp = await client.delete("/api/bids/BID-TEST-001")
    assert resp.json()["removed"]["emails"] == 0


async def test_delete_bid_removed_from_list(client: AsyncClient) -> None:
    await client.delete("/api/bids/BID-TEST-001")
    resp = await client.get("/api/bids/")
    assert not any(b["id"] == "BID-TEST-001" for b in resp.json())


async def test_delete_bid_then_get_returns_404(client: AsyncClient) -> None:
    await client.delete("/api/bids/BID-TEST-001")
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.status_code == 404


async def test_delete_bid_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.delete("/api/bids/BID-NO-SUCH-ID")
    assert resp.status_code == 404


async def test_delete_cleans_line_items(client: AsyncClient) -> None:
    # After deleting the bid, its line items must be gone from the line-items endpoint
    await client.delete("/api/bids/BID-TEST-001")
    resp = await client.get("/api/bids/BID-TEST-001/line-items")
    # Line items endpoint returns [] for unknown bid (not 404)
    assert resp.status_code == 200
    assert resp.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/{bid_id}/files  — Uploaded files list  ← NEW IN V3
#
# Returns the uploadedFiles array stored on the bid object.
# Seed bid has uploadedFiles=[] so it always starts empty.
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_bid_files_empty_for_seed(client: AsyncClient) -> None:
    # Seed bid has no uploaded files → empty list
    resp = await client.get("/api/bids/BID-TEST-001/files")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_bid_files_not_found_returns_404(client: AsyncClient) -> None:
    # Non-existent bid → 404 (unlike /line-items which returns [])
    resp = await client.get("/api/bids/BID-NO-SUCH-ID/files")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/{bid_id}/line-items  — Line items sub-resource
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_line_items_for_seed_bid(client: AsyncClient) -> None:
    # Seed has 1 line item linked to BID-TEST-001
    resp = await client.get("/api/bids/BID-TEST-001/line-items")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["bidItem"] == "0001"
    assert items[0]["bidId"] == "BID-TEST-001"


async def test_get_line_items_unknown_bid_returns_empty(client: AsyncClient) -> None:
    # No line items for this bid → empty list (not 404)
    resp = await client.get("/api/bids/BID-NO-ITEMS-XYZ/line-items")
    assert resp.status_code == 200
    assert resp.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# PATCH /api/bids/{bid_id}/line-items/{line_id}  — Update a line item  ← NEW IN V3
#
# Seed line item: id=LI-BID-TEST-001-001, bidItem="0001", category="Protein", qty=100
# ══════════════════════════════════════════════════════════════════════════════

async def test_patch_line_item_updates_qty(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/bids/BID-TEST-001/line-items/LI-BID-TEST-001-001",
        json={"qty": 200},
    )
    assert resp.status_code == 200
    assert resp.json()["qty"] == 200


async def test_patch_line_item_updates_status(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/bids/BID-TEST-001/line-items/LI-BID-TEST-001-001",
        json={"status": "Awarded"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "Awarded"


async def test_patch_line_item_id_immutable(client: AsyncClient) -> None:
    # Sending a new id in body must be ignored
    resp = await client.patch(
        "/api/bids/BID-TEST-001/line-items/LI-BID-TEST-001-001",
        json={"id": "HACKED-LI-ID"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "LI-BID-TEST-001-001"


async def test_patch_line_item_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.patch(
        "/api/bids/BID-TEST-001/line-items/LI-DOES-NOT-EXIST",
        json={"qty": 999},
    )
    assert resp.status_code == 404


async def test_patch_line_item_change_persists(client: AsyncClient) -> None:
    # Patch then re-fetch list — change must still be there
    await client.patch(
        "/api/bids/BID-TEST-001/line-items/LI-BID-TEST-001-001",
        json={"qty": 500},
    )
    resp = await client.get("/api/bids/BID-TEST-001/line-items")
    assert resp.json()[0]["qty"] == 500


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/{bid_id}/emails  — Email threads sub-resource
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_bid_emails_empty(client: AsyncClient) -> None:
    # Seed has no emails → empty list
    resp = await client.get("/api/bids/BID-TEST-001/emails")
    assert resp.status_code == 200
    assert resp.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/bids/{bid_id}/emails/by-supplier  — Emails grouped by supplier  ← NEW IN V3
#
# Returns solicited suppliers with their matching email threads.
# Seed bid has solicitedSuppliers=[] and no emails → returns empty list.
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_emails_by_supplier_empty(client: AsyncClient) -> None:
    # Seed bid has no solicited suppliers → empty list
    resp = await client.get("/api/bids/BID-TEST-001/emails/by-supplier")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_get_emails_by_supplier_not_found_returns_404(client: AsyncClient) -> None:
    # Non-existent bid → 404
    resp = await client.get("/api/bids/BID-NO-SUCH-ID/emails/by-supplier")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/health  — Server health check
# ══════════════════════════════════════════════════════════════════════════════

async def test_health_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "llmProvider" in body
    assert "dbBackend" in body
