"""Temporary diagnostic endpoint to verify JSON upload data integrity."""

import gzip
import json
from fastapi import APIRouter, Request, HTTPException

router = APIRouter()


@router.post("/diagnostics/upload-check")
async def upload_check(request: Request):
    """Accepts the same gzipped JSON as /upload-and-score but returns a data audit."""
    raw = await request.body()

    encoding = request.headers.get("content-encoding", "")
    if encoding == "gzip":
        raw = gzip.decompress(raw)

    payload = json.loads(raw)
    sheets = payload.get("sheets", {})

    report = {
        "sheets_received": list(sheets.keys()),
        "sheet_details": {},
    }

    for name, rows in sheets.items():
        if not rows:
            report["sheet_details"][name] = {"row_count": 0}
            continue

        # Find header row (row index 2 in the Pixel DE format)
        header_row_idx = None
        for i, row in enumerate(rows[:5]):
            str_vals = [str(v).strip() if v is not None else "" for v in row]
            if "Creative Name" in str_vals:
                header_row_idx = i
                break

        if header_row_idx is None:
            report["sheet_details"][name] = {
                "row_count": len(rows),
                "error": "No header row with 'Creative Name' found in first 5 rows",
                "first_rows": rows[:3],
            }
            continue

        headers = [
            str(c).strip() if c is not None else "" for c in rows[header_row_idx]
        ]
        data_rows = rows[header_row_idx + 1 :]

        # Check row widths
        row_lengths = [len(r) for r in data_rows if r]
        non_empty_rows = [
            r
            for r in data_rows
            if r and any(v is not None and str(v).strip() != "" for v in r)
        ]

        # Check for expected columns
        expected_cols = [
            "Creative Name",
            "Ad name in Platform",
            "Campaign",
            "Platform",
            "Objective",
            "Format",
            "Placement",
            "OS",
            "Targeting Segment",
            "Partner",
            "Concept",
            "Product",
            "Wave",
            "Duration",
            "Impressions",
            "Reach",
            "Frequency",
            "Spends",
            "CPM",
            "Clicks",
            "Video Completion",
            "Shares",
            "Total Engagement",
            "Total Plays",
            "Consolidated_Asset_Key",
        ]
        # Also check for VTR variants
        vtr_cols = ["2s VTR", "3s VTR", "Hook Rate"]

        present = [c for c in expected_cols if c in headers]
        missing = [c for c in expected_cols if c not in headers]
        vtr_present = [c for c in vtr_cols if c in headers]

        # Sample a data row to check types
        sample_row = {}
        if non_empty_rows:
            r = non_empty_rows[0]
            for j, h in enumerate(headers):
                if j < len(r) and h:
                    val = r[j]
                    sample_row[h] = {
                        "value": str(val)[:50] if val is not None else None,
                        "type": type(val).__name__,
                    }

        report["sheet_details"][name] = {
            "total_rows": len(rows),
            "header_row_index": header_row_idx,
            "header_count": len(headers),
            "headers": headers,
            "data_row_count": len(data_rows),
            "non_empty_data_rows": len(non_empty_rows),
            "row_length_range": [min(row_lengths), max(row_lengths)]
            if row_lengths
            else [],
            "expected_cols_present": present,
            "expected_cols_missing": missing,
            "vtr_cols_present": vtr_present,
            "sample_first_data_row": sample_row,
        }

    return report
