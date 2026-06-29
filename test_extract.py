"""
Standalone pricing extraction test — fully dynamic, works with any PDF or Excel.

Run from inside backend_py/:
    python test_extract.py file.pdf file.xlsx   # any combination
    python test_extract.py file.xlsx
    python test_extract.py file.pdf

The LLM figures out the document structure by itself — no hardcoded column names.
Results saved to pricing_result.json

Reads ANTHROPIC_API_KEY (or OPENAI_API_KEY) from backend_py/.env
"""
from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path


# ── File readers ──────────────────────────────────────────────────────────────

def read_pdf(path: str) -> str:
    try:
        import pypdf
        with open(path, "rb") as f:
            content = f.read()
        reader = pypdf.PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        print(f"  PDF  → {len(reader.pages)} page(s), {len(text):,} chars")
        return text
    except Exception as exc:
        print(f"  ERROR reading PDF: {exc}")
        return ""


def read_excel(path: str) -> str:
    try:
        import openpyxl
        with open(path, "rb") as f:
            content = f.read()
        wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
        lines: list[str] = []
        total_rows = 0
        for ws in wb.worksheets:
            lines.append(f"=== Sheet: {ws.title} ===")
            for row in ws.iter_rows(values_only=True):
                row_str = "\t".join("" if v is None else str(v) for v in row)
                if row_str.strip():
                    lines.append(row_str)
                    total_rows += 1
        text = "\n".join(lines)
        print(f"  Excel → {len(wb.worksheets)} sheet(s), {total_rows:,} rows, {len(text):,} chars")
        return text
    except Exception as exc:
        print(f"  ERROR reading Excel: {exc}")
        return ""


def read_csv(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        print(f"  CSV  → {len(lines):,} rows, {len(text):,} chars")
        return text
    except Exception as exc:
        print(f"  ERROR reading CSV: {exc}")
        return ""


# ── Dynamic system prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an intelligent document analysis and pricing extraction assistant.

You will receive one or more documents (PDF, Excel, CSV). Your job is to:

STEP 1 — UNDERSTAND THE DOCUMENT
  Examine the document carefully. Figure out on your own:
  - What type of document is this? (order guide, quote sheet, bid response,
    RFP, price list, USDA schedule, invoice, catalog, etc.)
  - What columns or fields exist?
  - Which columns contain product identifiers, descriptions, and prices?
  - Are there multiple price types (e.g. sell price, net price, fee, allowance,
    USDA value, delivered price, FOB price, list price)?

STEP 2 — EXTRACT EVERY ITEM
  For every product / line item found in the document extract:
  - description    : the product name / description (REQUIRED — never skip)
  - productCode    : any product identifier found (SUPC, item code, part number,
                     end product code, SKU, MPC, bid item number, etc.) — null if none
  - category       : product category or type if present — null if none
  - pricing        : a JSON object containing ALL price-related values found for
                     this item. Use clear descriptive keys based on the actual
                     column header found in the document. Examples:
                       "sellPricePerCase", "feePerCase", "netPrice", "deliveredPrice",
                       "usdaValuePerCase", "allowance", "listPrice", "unitPrice", etc.
                     Include every numeric price column — do not drop any.
  - specs          : a JSON object for non-price fields that are useful context
                     (weight, pack size, servings, unit of measure, storage temp,
                     catch weight flag, compliance flags, guarantee date, etc.)
                     Leave as empty object {} if nothing relevant.

RULES
  - Extract ONLY data explicitly present in the document. Never fabricate values.
  - Include ALL items — do not skip rows or truncate the list.
  - If two documents are provided, link items that appear in both (same product)
    by merging their data into one item entry.
  - Use the exact column header text as the key name inside "pricing" and "specs"
    (converted to camelCase). This makes the output self-documenting.
  - Return ONLY valid JSON. No markdown. No explanation. Start with { end with }.

Return exactly this structure:
{
  "documentSummary": "one sentence describing what document(s) were provided",
  "items": [
    {
      "description": "string",
      "productCode": "string or null",
      "category": "string or null",
      "pricing": {
        "keyNameMatchingColumnHeader": 0.00
      },
      "specs": {
        "keyNameMatchingColumnHeader": "value"
      }
    }
  ],
  "totalItems": 0
}"""


# ── User prompt builder ───────────────────────────────────────────────────────

def build_user_prompt(files: list[tuple[str, str]]) -> str:
    """
    files = list of (label, text) e.g. [("PDF", "..."), ("Excel", "...")]
    Labels are generic — LLM figures out the content type itself.
    """
    sections: list[str] = []
    for label, text in files:
        sections.append(
            f"=== DOCUMENT ({label}) ===\n{text}"
        )
    return "\n\n".join(sections)


# ── Pretty printer ────────────────────────────────────────────────────────────

def print_results(items: list[dict], summary: str) -> None:
    print(f"\n{'=' * 80}")
    print(f"  {summary}")
    print(f"  {len(items)} item(s) extracted")
    print(f"{'=' * 80}\n")

    if not items:
        print("  No items found.")
        return

    # Discover all pricing keys across all items for table header
    all_price_keys: list[str] = []
    for item in items:
        for k in item.get("pricing", {}).keys():
            if k not in all_price_keys:
                all_price_keys.append(k)

    # Build column widths
    desc_w  = 42
    code_w  = 10
    cat_w   = 14
    price_w = 11

    header = (
        f"{'#':>3}  {'Description':<{desc_w}}  {'Code':<{code_w}}  {'Category':<{cat_w}}"
        + "".join(f"  {k[:price_w-2]:>{price_w}}" for k in all_price_keys)
    )
    print(header)
    print("-" * len(header))

    for i, item in enumerate(items, 1):
        desc  = str(item.get("description") or "")[:desc_w - 1]
        code  = str(item.get("productCode") or "")[:code_w - 1]
        cat   = str(item.get("category") or "")[:cat_w - 1]
        pricing = item.get("pricing", {})

        price_cols = ""
        for k in all_price_keys:
            val = pricing.get(k)
            if isinstance(val, (int, float)):
                cell = f"${val:.2f}"
            elif val is not None:
                cell = str(val)[:price_w - 1]
            else:
                cell = "n/a"
            price_cols += f"  {cell:>{price_w}}"

        print(f"{i:>3}.  {desc:<{desc_w}}  {code:<{code_w}}  {cat:<{cat_w}}{price_cols}")

    # Show specs of first item as a sample
    if items and items[0].get("specs"):
        print(f"\nSample specs (item 1): {json.dumps(items[0]['specs'])}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    # ── Read all provided files ───────────────────────────────────────────────
    file_contents: list[tuple[str, str]] = []   # (label, text)

    for arg in args:
        p = Path(arg)
        if not p.exists():
            print(f"ERROR: file not found — {arg}")
            sys.exit(1)

        ext = p.suffix.lower()
        print(f"\nReading: {arg}")

        if ext == ".pdf":
            text = read_pdf(arg)
            label = "PDF"
        elif ext in (".xlsx", ".xls"):
            text = read_excel(arg)
            label = "Excel"
        elif ext == ".csv":
            text = read_csv(arg)
            label = "CSV"
        else:
            print(f"  Skipped — unrecognised type ({ext})")
            continue

        if text:
            file_contents.append((label, text))

    if not file_contents:
        print("\nERROR: no text could be extracted from the provided file(s).")
        sys.exit(1)

    # ── Build prompt ──────────────────────────────────────────────────────────
    user_prompt = build_user_prompt(file_contents)
    mode = " + ".join(label for label, _ in file_contents)
    print(f"\nMode         : {mode}")
    print(f"Prompt size  : {len(user_prompt):,} chars")

    # ── Load LLM ──────────────────────────────────────────────────────────────
    print("\nLoading LLM from .env ...")
    try:
        from config import get_settings
        from services.llm.factory import build_llm_service
        from services.llm.json_parser import extract_json
    except ImportError:
        print(
            "\nERROR: Cannot import backend modules.\n"
            "Run this script from inside backend_py/:\n\n"
            "    cd backend_py\n"
            "    python test_extract.py pdf_try.pdf excel_try.xlsx\n"
        )
        sys.exit(1)

    settings = get_settings()
    llm = build_llm_service(settings)
    print(f"Provider     : {settings.llm_provider.upper()}")

    # ── Call LLM ──────────────────────────────────────────────────────────────
    # 8192 tokens — the Excel has 205 rows, needs room for full output
    print("\nCalling LLM (max_tokens=8192) …")
    try:
        response = await llm.chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=8192,
            temperature=0.0,
        )
    except Exception as exc:
        print(f"\nERROR: LLM call failed — {exc}")
        sys.exit(1)

    print("\n--- Raw LLM response (first 600 chars) ---")
    print(response.content[:600])
    if len(response.content) > 600:
        print(f"  … ({len(response.content):,} chars total)")
    print("---")

    # ── Parse ─────────────────────────────────────────────────────────────────
    try:
        parsed = extract_json(response.content)
    except ValueError as exc:
        print(f"\nERROR: Could not parse LLM response as JSON.\n{exc}")
        sys.exit(1)

    items: list[dict] = parsed.get("items", []) if isinstance(parsed, dict) else []
    summary: str = parsed.get("documentSummary", mode) if isinstance(parsed, dict) else mode

    # ── Print table ───────────────────────────────────────────────────────────
    print_results(items, summary)

    # ── Save JSON ─────────────────────────────────────────────────────────────
    out_path = Path("pricing_result.json")
    out_path.write_text(
        json.dumps(
            {"documentSummary": summary, "itemCount": len(items), "items": items},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nFull JSON saved to: {out_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
