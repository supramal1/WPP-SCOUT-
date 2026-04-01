import gzip
import json
from fastapi import APIRouter, Request, HTTPException
from scoring.pipeline import process_upload_json

router = APIRouter()


@router.post("/upload-and-score")
async def upload_and_score(request: Request):
    """Accept pre-parsed sheet data as JSON (optionally gzip-compressed)."""
    raw = await request.body()

    # Decompress if gzipped
    encoding = request.headers.get("content-encoding", "")
    if encoding == "gzip":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail={"error": "bad_encoding", "message": "Invalid gzip data"},
            )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail={"error": "bad_json", "message": "Invalid JSON"},
        )

    sheets = payload.get("sheets")
    if not sheets or not isinstance(sheets, dict):
        raise HTTPException(
            status_code=400,
            detail={"error": "no_sheets", "message": "No sheet data provided"},
        )

    try:
        result = process_upload_json(sheets)
        return result
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_columns",
                "message": f"Required columns missing: {e}",
            },
        )
    except ValueError as e:
        error_msg = str(e)
        if "No matching sheets" in error_msg:
            raise HTTPException(
                status_code=400,
                detail={"error": "no_sheets", "message": error_msg},
            )
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_data", "message": error_msg},
        )
