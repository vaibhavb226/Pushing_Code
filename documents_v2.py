"""
GET   /api/documents         — list with filters
GET   /api/documents/:id     — single document
POST  /api/documents/upload  — upload file + add metadata (stores fileHash for duplicate detection)
PATCH /api/documents/:id/vault — toggle Filed ↔ Extracted
"""
from __future__ import annotations

import hashlib
import time
import uuid
from pathlib import Path
from typing import Any

import aiofiles
import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile

from dependencies import UPLOADS_DIR, get_documents_repo
from repositories.documents_repo import DocumentsRepository
from utils.file_utils import format_file_size, safe_filename

log = structlog.get_logger()
router = APIRouter(tags=["documents"])


@router.get("/", response_model=list[dict[str, Any]])
async def list_documents(
    bid_id: str | None = Query(None, alias="bidId"),
    supplier: str | None = None,
    category: str | None = None,
    doc_type: str | None = Query(None, alias="type"),
    tag: str | None = None,
    search: str | None = None,
    repo: DocumentsRepository = Depends(get_documents_repo),
) -> list[dict[str, Any]]:
    docs = await repo.load()

    if bid_id:
        docs = [d for d in docs if d.get("bidId") in (bid_id, "ALL")]
    if supplier:
        docs = [d for d in docs if supplier.lower() in d.get("supplier", "").lower()]
    if category:
        docs = [d for d in docs if d.get("supplierCategory") == category]
    if doc_type:
        docs = [d for d in docs if d.get("documentType") == doc_type]
    if tag:
        docs = [d for d in docs if tag in d.get("tags", [])]
    if search:
        term = search.lower()
        docs = [
            d for d in docs
            if term in d.get("fileName", "").lower()
            or term in d.get("supplier", "").lower()
            or term in d.get("description", "").lower()
        ]
    return docs


@router.get("/{doc_id}", response_model=dict[str, Any])
async def get_document(
    doc_id: str,
    repo: DocumentsRepository = Depends(get_documents_repo),
) -> dict[str, Any]:
    doc = await repo.find_one(lambda d: d.get("id") == doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    return doc


@router.post("/upload", response_model=dict[str, Any], status_code=201)
async def upload_document(
    file: UploadFile,
    bid_id: str | None = Form(None, alias="bidId"),
    supplier: str | None = Form(None),
    document_type: str = Form("Other", alias="documentType"),
    notes: str = Form(""),
    repo: DocumentsRepository = Depends(get_documents_repo),
) -> dict[str, Any]:
    content = await file.read()

    # Compute SHA-256 fingerprint of the file bytes.
    # This is stored on every record so the frontend can detect duplicates
    # before uploading by comparing against existing records.
    file_hash = hashlib.sha256(content).hexdigest()

    timestamp = int(time.time() * 1000)
    fname = safe_filename(file.filename or "upload")
    saved_name = f"{timestamp}_{fname}"
    dest = UPLOADS_DIR / saved_name

    async with aiofiles.open(dest, "wb") as f:
        await f.write(content)

    from datetime import date
    doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    ext = Path(fname).suffix.lstrip(".")
    doc_record: dict[str, Any] = {
        "id": doc_id,
        "fileName": fname,
        "fileType": ext,
        "fileHash": file_hash,
        "sizeKb": len(content) // 1024,
        "supplier": supplier or "",
        "supplierId": None,
        "bidId": bid_id or "ALL",
        "documentType": document_type,
        "tags": [],
        "uploadDate": date.today().isoformat(),
        "uploadedBy": "System",
        "status": "Filed",
        "filePath": f"uploads/{saved_name}",
        "description": notes,
    }
    await repo.append(doc_record)
    log.info("document.uploaded", id=doc_id, file=fname, hash=file_hash[:8])
    return doc_record


@router.patch("/{doc_id}/vault", response_model=dict[str, Any])
async def toggle_vault(
    doc_id: str,
    repo: DocumentsRepository = Depends(get_documents_repo),
) -> dict[str, Any]:
    def toggle(doc: dict[str, Any]) -> dict[str, Any]:
        doc["status"] = "Filed" if doc.get("status") == "Extracted" else "Extracted"
        return doc

    updated = await repo.update_one(lambda d: d.get("id") == doc_id, toggle)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Document {doc_id!r} not found")
    return updated
