"""
Extended tests for /api/suppliers/* and /api/bids/* endpoints.

HOW THE TEST SETUP WORKS (from conftest.py):
─────────────────────────────────────────────
- Before each test, a fresh temporary folder is created on disk.
- That folder gets pre-loaded with seed JSON files:
    • suppliers.json  → one supplier: "Test Supplier Inc" (id=SM-001, category=Protein, region=Northeast)
    • bids.json       → one bid:      "Test School District" (id=BID-TEST-001, segment=K-12, status=Active)
    • lineItems.json  → one item:     linked to BID-TEST-001
    • emails, documents, etc. → all empty lists
- The `client` fixture wires FastAPI to read/write ONLY that temp folder —
  so tests never touch the real data files, and each test starts clean.
- No real server needs to be running. pytest handles everything in-memory.

Run all:
    pytest tests/routers/test_suppliers_bids_extended.py -v

Run just supplier tests:
    pytest tests/routers/test_suppliers_bids_extended.py -v -k "supplier"

Run a single test:
    pytest tests/routers/test_suppliers_bids_extended.py::test_create_supplier_duplicate_email_returns_409 -v
"""
from __future__ import annotations

from httpx import AsyncClient


# ══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS — GET /api/suppliers/  (list with optional filters)
#
# The endpoint accepts query params: ?category=  ?segment=  ?region=  ?excludeBounced=
# Each filter narrows the list independently. You can combine them.
# Seed data: one supplier → category=Protein, segment=K-12, region=Northeast, bounce=False
# ══════════════════════════════════════════════════════════════════════════════

async def test_list_suppliers_filter_category_match(client: AsyncClient) -> None:
    # Asking for category=Protein should return our seed supplier (and only Protein ones)
    resp = await client.get("/api/suppliers/?category=Protein")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1                                    # at least the seed supplier
    assert all(s["category"] == "Protein" for s in data)    # no other categories leaked through


async def test_list_suppliers_filter_category_no_match(client: AsyncClient) -> None:
    # A category that doesn't exist in the data → empty list (not 404)
    resp = await client.get("/api/suppliers/?category=NoSuchCategory")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_suppliers_filter_segment(client: AsyncClient) -> None:
    # `segments` is a list field on each supplier — filter checks if K-12 is IN that list
    resp = await client.get("/api/suppliers/?segment=K-12")
    assert resp.status_code == 200
    data = resp.json()
    assert all("K-12" in s.get("segments", []) for s in data)
    assert len(data) >= 1   # seed supplier has segments=["K-12"] so it must appear


async def test_list_suppliers_filter_region(client: AsyncClient) -> None:
    resp = await client.get("/api/suppliers/?region=Northeast")
    assert resp.status_code == 200
    data = resp.json()
    assert all(s["region"] == "Northeast" for s in data)


async def test_list_suppliers_exclude_bounced(client: AsyncClient) -> None:
    # excludeBounced=true hides any supplier where bounce=True.
    # Our seed supplier has bounce=False so it still appears.
    # The important check: no supplier with bounce=True should come through.
    resp = await client.get("/api/suppliers/?excludeBounced=true")
    assert resp.status_code == 200
    assert all(not s.get("bounce", False) for s in resp.json())


async def test_list_suppliers_combined_filters(client: AsyncClient) -> None:
    # Filters stack — both conditions must be true for a supplier to appear
    resp = await client.get("/api/suppliers/?category=Protein&region=Northeast")
    assert resp.status_code == 200
    for s in resp.json():
        assert s["category"] == "Protein"
        assert s["region"] == "Northeast"


# ══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS — GET /api/suppliers/search  (typeahead search)
#
# HOW SEARCH WORKS (routers/suppliers.py line 39):
#   term = q.strip().lower()
#   matches if:
#     • any WORD in the supplier name starts with term   ← word-prefix match
#     • term is anywhere in the contact email            ← substring match
#     • term is anywhere in the category                 ← substring match
#
# KEY GOTCHA: The name check is word-by-word. Searching "Protein Supplier"
# (two words) will never match because no single word equals "protein supplier".
# Always search with a single prefix like "Prot" or "Sup".
#
# Returns at most 10 results.
# Empty query → always returns [].
# ══════════════════════════════════════════════════════════════════════════════

async def test_search_by_category_keyword(client: AsyncClient) -> None:
    # "Protein" is a substring of the category field → seed supplier should match
    resp = await client.get("/api/suppliers/search?q=Protein")
    assert resp.status_code == 200
    assert any(s["category"] == "Protein" for s in resp.json())


async def test_search_by_contact_email(client: AsyncClient) -> None:
    # "supplier@test" is a substring of "supplier@test-demo.test" → matches
    resp = await client.get("/api/suppliers/search?q=supplier@test")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_search_empty_query_returns_empty(client: AsyncClient) -> None:
    # Router short-circuits immediately if q is blank — returns [] without DB hit
    resp = await client.get("/api/suppliers/search?q=")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_search_capped_at_ten_results(client: AsyncClient) -> None:
    # Create 12 suppliers whose names all start with "Omega"
    # The router does results[:10], so we should never get back more than 10
    for i in range(12):
        await client.post("/api/suppliers/", json={
            "name": f"Omega Supplier {i}",
            "category": "Dairy",
            "contact": f"omega{i}@cap-test.test",
            "region": "Northeast",
            "segments": ["K-12"],
        })
    resp = await client.get("/api/suppliers/search?q=Omega")
    assert resp.status_code == 200
    assert len(resp.json()) <= 10   # hard cap enforced by the router


# ══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS — POST /api/suppliers/auto-populate
#
# Used when creating a bid: given a list of item categories (e.g. ["Protein"]),
# the router maps them via CATEGORY_MAP → supplier categories, then returns
# all matching suppliers plus a count of how many have bounce=True.
# "Broker" category is always included regardless of what itemCategories says.
# ══════════════════════════════════════════════════════════════════════════════

async def test_auto_populate_returns_suppliers_and_bounced_count(client: AsyncClient) -> None:
    # Response must always have both keys, even if the lists are empty
    resp = await client.post("/api/suppliers/auto-populate", json={
        "itemCategories": ["Protein"],
        "excludeBounced": False,        # include bounced ones in the list
    })
    assert resp.status_code == 200
    body = resp.json()
    assert "suppliers" in body
    assert "bouncedCount" in body
    assert isinstance(body["bouncedCount"], int)


async def test_auto_populate_exclude_bounced_flag(client: AsyncClient) -> None:
    # When excludeBounced=True, the returned suppliers list must contain no bounced entries
    # (bouncedCount is still reported so the UI can show "X hidden due to bounce")
    resp = await client.post("/api/suppliers/auto-populate", json={
        "itemCategories": ["Protein"],
        "excludeBounced": True,
    })
    assert resp.status_code == 200
    for s in resp.json()["suppliers"]:
        assert not s.get("bounce", False)


async def test_auto_populate_unknown_category(client: AsyncClient) -> None:
    # CATEGORY_MAP won't have an entry for a made-up category.
    # The router falls back to using the raw category name → likely 0 matches,
    # but the response shape must still be valid (not a 500 or 422).
    resp = await client.post("/api/suppliers/auto-populate", json={
        "itemCategories": ["XYZ_Unknown_Category_9999"],
        "excludeBounced": False,
    })
    assert resp.status_code == 200
    assert "suppliers" in resp.json()


# ══════════════════════════════════════════════════════════════════════════════
# SUPPLIERS — POST /api/suppliers/  (create)
#
# Auto-generates an SM-NNN id by finding the highest existing number and adding 1.
# Duplicate email (case-insensitive) → 409 Conflict.
# bounce always defaults to False on creation.
# ══════════════════════════════════════════════════════════════════════════════

async def test_create_supplier_id_auto_increments(client: AsyncClient) -> None:
    # Seed has SM-001. First new one should be SM-002, second SM-003.
    r1 = await client.post("/api/suppliers/", json={
        "name": "First Co",
        "category": "Dairy",
        "contact": "first-co@inc-test.test",
        "region": "Northeast",
        "segments": [],
    })
    r2 = await client.post("/api/suppliers/", json={
        "name": "Second Co",
        "category": "Dairy",
        "contact": "second-co@inc-test.test",
        "region": "Northeast",
        "segments": [],
    })
    # Extract the numeric part of "SM-002" → 2, "SM-003" → 3
    num1 = int(r1.json()["id"].split("-")[1])
    num2 = int(r2.json()["id"].split("-")[1])
    assert num2 == num1 + 1   # each creation bumps the counter by 1


async def test_create_supplier_duplicate_email_returns_409(client: AsyncClient) -> None:
    # conftest.py seeds supplier@test-demo.test (SM-001).
    # Trying to create another supplier with the same email must fail.
    resp = await client.post("/api/suppliers/", json={
        "name": "Dup Supplier",
        "category": "Dairy",
        "contact": "supplier@test-demo.test",   # ← same as seed
        "region": "Northeast",
        "segments": [],
    })
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"].lower()


async def test_create_supplier_defaults_bounce_to_false(client: AsyncClient) -> None:
    # The create endpoint always sets bounce=False regardless of what the body sends
    resp = await client.post("/api/suppliers/", json={
        "name": "Bounce Default Test",
        "category": "Produce",
        "contact": "bounce-def@test.test",
        "region": "Northeast",
        "segments": [],
    })
    assert resp.status_code == 201
    assert resp.json()["bounce"] is False


async def test_create_supplier_persists_in_list(client: AsyncClient) -> None:
    # After a successful POST, a GET /api/suppliers/ must include the new supplier.
    # This confirms the repository actually wrote to the JSON file.
    await client.post("/api/suppliers/", json={
        "name": "Persist Check Supplier",
        "category": "Produce",
        "contact": "persist-check@test.test",
        "region": "Southeast",
        "segments": ["Healthcare"],
    })
    resp = await client.get("/api/suppliers/")
    assert any(s["name"] == "Persist Check Supplier" for s in resp.json())


async def test_create_supplier_appears_in_search(client: AsyncClient) -> None:
    # After creating, the supplier must be findable via the search endpoint.
    # IMPORTANT: search does word-prefix matching on the name, so we search
    # with "Uniquely" (single word) — NOT "Uniquely Named Vendor" (multi-word phrase
    # would fail because no single token equals the whole phrase).
    await client.post("/api/suppliers/", json={
        "name": "Uniquely Named Vendor ABC",
        "category": "Dairy",
        "contact": "unique-vendor@test.test",
        "region": "Northeast",
        "segments": [],
    })
    resp = await client.get("/api/suppliers/search?q=Uniquely")   # single-word prefix
    assert resp.status_code == 200
    assert any(s["name"] == "Uniquely Named Vendor ABC" for s in resp.json())


# ══════════════════════════════════════════════════════════════════════════════
# BIDS — GET /api/bids/  (list with optional filters)
#
# Filters: ?segment=  ?status=
# Seed data: one bid → segment=K-12, status=Active
# ══════════════════════════════════════════════════════════════════════════════

async def test_list_bids_filter_segment(client: AsyncClient) -> None:
    resp = await client.get("/api/bids/?segment=K-12")
    assert resp.status_code == 200
    data = resp.json()
    assert all(b["segment"] == "K-12" for b in data)
    assert len(data) >= 1   # seed bid must appear


async def test_list_bids_filter_segment_no_match(client: AsyncClient) -> None:
    # A segment that doesn't exist → empty list, not 404
    resp = await client.get("/api/bids/?segment=NoSuchSegment")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_bids_filter_status(client: AsyncClient) -> None:
    resp = await client.get("/api/bids/?status=Active")
    assert resp.status_code == 200
    data = resp.json()
    assert all(b["status"] == "Active" for b in data)


async def test_list_bids_filter_status_no_match(client: AsyncClient) -> None:
    # No bid in the seed data has status=Awarded, so this must be an empty list
    resp = await client.get("/api/bids/?status=Awarded")
    assert resp.status_code == 200
    assert resp.json() == []


# ══════════════════════════════════════════════════════════════════════════════
# BIDS — POST /api/bids/  (create)
#
# If no `id` is given, the router auto-generates one.
# If `lineItems` array is included, they are saved and `items` count is updated.
# `status` defaults to "Active" if not provided.
# ══════════════════════════════════════════════════════════════════════════════

async def test_create_bid_auto_generates_id(client: AsyncClient) -> None:
    # Omit the `id` field — the router must fill it in
    resp = await client.post("/api/bids/", json={
        "customer": "Auto ID Customer",
        "segment": "K-12",
        "customerDue": "2026-09-01",
    })
    assert resp.status_code == 201
    assert resp.json()["id"] != ""   # some non-empty id was assigned


async def test_create_bid_defaults_status_to_active(client: AsyncClient) -> None:
    # No status field in the request → router should default it to "Active"
    resp = await client.post("/api/bids/", json={
        "id": "BID-STATUS-DEFAULT",
        "customer": "Status Test",
        "segment": "K-12",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "Active"


async def test_create_bid_with_line_items_updates_item_count(client: AsyncClient) -> None:
    # When lineItems is included in the POST body, the router saves them
    # to lineItems.json and sets bid.items = len(lineItems)
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
    assert resp.json()["items"] == 1   # bid.items was updated to match the line item count


async def test_create_bid_persists(client: AsyncClient) -> None:
    # After POST, a GET on the same id must return the bid (confirms it was written to disk)
    await client.post("/api/bids/", json={
        "id": "BID-PERSIST-CHECK",
        "customer": "Persist Customer",
        "segment": "K-12",
    })
    resp = await client.get("/api/bids/BID-PERSIST-CHECK")
    assert resp.status_code == 200
    assert resp.json()["customer"] == "Persist Customer"


# ══════════════════════════════════════════════════════════════════════════════
# BIDS — PATCH /api/bids/{bid_id}  (partial update)
#
# Only the fields you send are changed — other fields stay the same.
# The `id` field is immutable — even if you send a new id in the body, it's ignored.
# Returns the full updated bid on success, 404 if the bid_id doesn't exist.
# ══════════════════════════════════════════════════════════════════════════════

async def test_patch_bid_updates_notes(client: AsyncClient) -> None:
    # Seed bid has notes="" — patch it and verify the returned object reflects the change
    resp = await client.patch("/api/bids/BID-TEST-001", json={"notes": "Important note"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Important note"


async def test_patch_bid_updates_compliance(client: AsyncClient) -> None:
    # compliance is a list field — patching it replaces the whole list
    resp = await client.patch("/api/bids/BID-TEST-001", json={"compliance": ["USDA", "Child Nutrition"]})
    assert resp.status_code == 200
    assert "USDA" in resp.json()["compliance"]


async def test_patch_bid_id_immutable(client: AsyncClient) -> None:
    # Sending a different `id` in the body must NOT change the bid's id.
    # The router strips or ignores id changes to prevent accidental corruption.
    resp = await client.patch("/api/bids/BID-TEST-001", json={"id": "HACKED-ID"})
    assert resp.status_code == 200
    assert resp.json()["id"] == "BID-TEST-001"   # original id unchanged


async def test_patch_bid_change_persists(client: AsyncClient) -> None:
    # Patch then re-fetch — confirms the change was written to the JSON file,
    # not just returned in the response without being saved
    await client.patch("/api/bids/BID-TEST-001", json={"status": "Awarded"})
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.json()["status"] == "Awarded"


async def test_patch_bid_not_found_returns_404(client: AsyncClient) -> None:
    resp = await client.patch("/api/bids/BID-NOPE-XYZ", json={"status": "Active"})
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# BIDS — DELETE /api/bids/{bid_id}  (cascade delete)
#
# Deletes the bid AND all related records from:
#   lineItems.json, emailThreads.json, pricingData.json,
#   documents.json, submissions.json, and the uploaded files on disk.
# Response: { "success": True, "deleted": "<id>", "removed": { "lineItems": N, ... } }
# ══════════════════════════════════════════════════════════════════════════════

async def test_delete_bid_cascades_line_items_count(client: AsyncClient) -> None:
    # Seed data has 1 line item for BID-TEST-001 → removed.lineItems must be 1
    resp = await client.delete("/api/bids/BID-TEST-001")
    assert resp.status_code == 200
    assert resp.json()["removed"]["lineItems"] == 1


async def test_delete_bid_removed_from_list(client: AsyncClient) -> None:
    # After delete, the bid must not appear in GET /api/bids/
    await client.delete("/api/bids/BID-TEST-001")
    resp = await client.get("/api/bids/")
    assert not any(b["id"] == "BID-TEST-001" for b in resp.json())


async def test_delete_bid_then_get_returns_404(client: AsyncClient) -> None:
    # After delete, fetching the same id directly must return 404
    await client.delete("/api/bids/BID-TEST-001")
    resp = await client.get("/api/bids/BID-TEST-001")
    assert resp.status_code == 404


async def test_delete_bid_not_found_returns_404(client: AsyncClient) -> None:
    # Deleting a non-existent bid must return 404 (not 200 or 500)
    resp = await client.delete("/api/bids/BID-DOES-NOT-EXIST-XYZ")
    assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# BIDS — GET /api/bids/{bid_id}/line-items  (sub-resource)
# ══════════════════════════════════════════════════════════════════════════════

async def test_get_line_items_unknown_bid_returns_empty(client: AsyncClient) -> None:
    # A bid id that exists nowhere → empty list (not 404), because line items
    # are stored separately and we're just filtering by bidId
    resp = await client.get("/api/bids/BID-NO-ITEMS-XYZ/line-items")
    assert resp.status_code == 200
    assert resp.json() == []
