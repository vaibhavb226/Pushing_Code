"""
POST /api/parse-rfp         — Upload PDF + Excel, call BEX AI, return parsed bid + line items
POST /api/parse-rfp/create  — Save parsed data to JSON files, return created bid
"""
from __future__ import annotations

import io
import json
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import aiofiles
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Form, UploadFile
from fastapi.responses import JSONResponse

from config import get_settings
from dependencies import UPLOADS_DIR, get_bids_repo, get_line_items_repo, get_llm_service
from repositories.bids_repo import BidsRepository
from repositories.line_items_repo import LineItemsRepository
from routers.prompts import BEX_SYSTEM_PROMPT
from services.llm.json_parser import extract_json
from services.llm.provider import LLMService

log = structlog.get_logger()
router = APIRouter(tags=["rfp-parser"])


# ── Shared helper — also used by bids.py ────────────────────────────────────

def build_line_item(li: dict[str, Any], bid_id: str, idx: int) -> dict[str, Any]:
    """
    Construct a lineItems.json record from a parsed AI line item.
    Mirrors buildLineItem() in backend/routes/rfpParser.js exactly.
    """
    return {
        "id": f"LI-{bid_id}-{idx + 1:03d}",
        "bidId": bid_id,
        "bidItem": str(li.get("line_number") or (idx + 1)).zfill(4),
        "mpcCode": li.get("mpc_code") or li.get("mfg_code") or "",
        "brand": li.get("brand") or "",
        "description": li.get("description") or "",
        "pack": li.get("pack") or "",
        "size": li.get("size") or "",
        "unit": li.get("uom") or "",
        "category": li.get("category") or "",
        "qty": int(float(li.get("volume") or li.get("est_qty") or 0)),
        "storage": li.get("storage") or "",
        "cw": "N",
        "stkType": "A",
        "buyAmerican": bool(li.get("buy_american")),
        "childNutrition": bool(li.get("child_nutrition")),
        "pfsRequired": bool(li.get("pfs_required")),
        "exactSpec": bool(li.get("exact_spec")),
        "rfpPopulated": True,
        "_source": "pdf",
        "trueVendor": None,
        "suppliedPrice": None,
        "allw": None,
        "dl": None,
        "priceCase": None,
        "devType": None,
        "openReview": False,
        "status": "No Response",
        "confidence": None,
        "supplierPricing": [],
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("", response_model=dict[str, Any])
async def parse_rfp(
    pdf: UploadFile | None = None,
    excel: UploadFile | None = None,
    demo: bool = Form(False),
    llm: LLMService = Depends(get_llm_service),
    line_items_repo: LineItemsRepository = Depends(get_line_items_repo),
) -> dict[str, Any]:
    if demo:
        return await _demo_response(line_items_repo)

    pdf_text = ""
    excel_text = ""
    data_row_count = 0

    if pdf:
        pdf_bytes = await pdf.read()
        pdf_text = _extract_pdf_text(pdf_bytes)

    if excel:
        excel_bytes = await excel.read()
        excel_text, data_row_count = _extract_excel_text(excel_bytes)

    if not pdf_text and not excel_text:
        return await _demo_response(line_items_repo)

    # Build user prompt
    user_prompt = ""
    if pdf_text:
        user_prompt += (
            "PDF CONTENT (use for bid metadata ONLY — extract customer_name, bid_id, "
            "segment, opco, region, due dates, compliance requirements from here):\n"
            f"{pdf_text[:40000]}\n\n"
        )
    if excel_text:
        user_prompt += (
            f"EXCEL ITEM LIST (extract ALL individual line items from here):\n"
            f"{excel_text[:50000]}\n\n"
            f"CRITICAL: The Excel has {data_row_count} data rows. "
            f"Your line_items array MUST contain exactly {data_row_count} separate objects "
            "— one per row. Do NOT group rows by category."
        )

    # Fail fast with a clear message when the API key is not configured,
    # rather than silently returning demo data.
    settings = get_settings()
    provider = settings.llm_provider.lower()
    missing_key = (
        (provider == "anthropic" and not settings.anthropic_api_key.get_secret_value())
        or (provider == "openai" and not settings.openai_api_key.get_secret_value())
        or (provider == "vertexai" and not settings.gcp_project)
    )
    if missing_key:
        key_var = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "vertexai": "GCP_PROJECT",
        }.get(provider, "API key")
        return JSONResponse(
            status_code=503,
            content={
                "error": f"AI provider '{provider}' is not configured",
                "hint": f"Add {key_var} to backend_py/.env and restart the server",
            },
        )

    try:
        result = await llm.chat(system=BEX_SYSTEM_PROMPT, user=user_prompt, max_tokens=8000)
        parsed = extract_json(result.content)
    except Exception as exc:
        log.error("rfp_parser.ai_failed", error=str(exc))
        return await _demo_response(line_items_repo)

    # Save temp files for /create endpoint fallback
    temp_pdf_path = ""
    temp_excel_path = ""
    if pdf:
        pdf_bytes_saved = await pdf.seek(0) or b""  # already consumed
        temp_pdf_path = ""  # reset — already read above; caller can re-upload
    if excel:
        temp_excel_path = ""

    line_items_raw: list[dict[str, Any]] = parsed.get("line_items", [])
    log.info(
        "rfp_parser.done",
        customer=parsed.get("metadata", {}).get("customer_name"),
        items=len(line_items_raw),
    )
    return {
        "metadata": parsed.get("metadata", {}),
        "line_items": line_items_raw,
        "supplier_targeting": parsed.get("supplier_targeting", {}),
        "parsing_warnings": parsed.get("parsing_warnings", []),
    }


@router.post("/create", response_model=dict[str, Any], status_code=201)
async def create_bid_from_parse(
    body: dict[str, Any],
    bids_repo: BidsRepository = Depends(get_bids_repo),
    line_items_repo: LineItemsRepository = Depends(get_line_items_repo),
) -> dict[str, Any]:
    """
    Save the parsed bid + line items returned from /parse-rfp.
    Body: { metadata, line_items, ... } + step-2 form fields.
    """
    meta = body.get("metadata", {})
    raw_items: list[dict[str, Any]] = body.get("line_items", [])

    # Generate bid ID if not provided
    bid_id: str = (
        body.get("bid_id")
        or meta.get("bid_id")
        or f"BID-{int(time.time() * 1000) % 100000}"
    )

    today = date.today().isoformat()
    new_bid: dict[str, Any] = {
        "id": bid_id,
        "customer": body.get("customer_name") or meta.get("customer_name") or "Unknown Customer",
        "opco": body.get("opco_code") or meta.get("opco_code") or "",
        "opcoName": body.get("opco_name") or meta.get("opco_name") or "",
        "region": body.get("region") or meta.get("region") or "",
        "segment": body.get("segment") or meta.get("segment") or "",
        "status": "Active",
        "intakeDate": today,
        "customerDue": body.get("customer_due") or meta.get("customer_due_date") or "",
        "internalDue": body.get("internal_due") or "",
        "bidRelease": body.get("bid_release") or "",
        "items": len(raw_items),
        "suppliersContacted": 0,
        "responsesReceived": 0,
        "notes": body.get("notes") or "",
        "compliance": body.get("compliance_flags") or meta.get("compliance_flags") or [],
        "itemCategories": list({li.get("category", "") for li in raw_items if li.get("category")}),
        "solicitedSuppliers": [],
        "uploadedFiles": [],
        "_lineItemSource": "pdf",
    }

    await bids_repo.append(new_bid)

    # Save line items
    built_items = [build_line_item(li, bid_id, i) for i, li in enumerate(raw_items)]
    if built_items:
        all_items = await line_items_repo.load()
        # Remove any existing items for this bid first
        all_items = [it for it in all_items if it.get("bidId") != bid_id]
        all_items.extend(built_items)
        await line_items_repo.save(all_items)

        # Update bid item count
        await bids_repo.update_one(
            lambda b: b.get("id") == bid_id,
            lambda b: {**b, "items": len(built_items)},
        )

    log.info("rfp_parser.bid_created", bid_id=bid_id, items=len(built_items))
    return {**new_bid, "lineItems": built_items}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_pdf_text(content: bytes) -> str:
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""


def _extract_excel_text(content: bytes) -> tuple[str, int]:
    """Return (TSV-style text, data row count)."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return "", 0
        # First non-empty row treated as header
        header_idx = next((i for i, r in enumerate(rows) if any(c is not None for c in r)), 0)
        data_rows = rows[header_idx + 1:]
        non_empty_data = [r for r in data_rows if any(c is not None for c in r)]

        lines: list[str] = []
        header = "\t".join("" if v is None else str(v) for v in rows[header_idx])
        lines.append(header)
        for row in non_empty_data:
            lines.append("\t".join("" if v is None else str(v) for v in row))

        return "\n".join(lines), len(non_empty_data)
    except Exception:
        return "", 0


async def _demo_response(line_items_repo: LineItemsRepository) -> dict[str, Any]:
    """Return demo data when no file is uploaded or AI is unavailable."""
    all_items = await line_items_repo.load()
    demo_items = [it for it in all_items if it.get("bidId") == "B2600042"][:5]
    return {
        "metadata": {
            "bid_id": "DEMO-001",
            "customer_name": "Demo School District",
            "segment": "K-12",
            "opco_code": "016",
            "opco_name": "Sysco Boston",
            "region": "Northeast",
            "customer_due_date": None,
            "compliance_flags": ["Child Nutrition", "Buy American"],
            "total_items": len(demo_items),
            "parsing_confidence": 85,
        },
        "line_items": demo_items,
        "supplier_targeting": {},
        "parsing_warnings": ["Demo mode — upload a real RFP to parse"],
    }
