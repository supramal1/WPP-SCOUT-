import gzip
import json

from fastapi import APIRouter, HTTPException, Request

from src.data_mapping import create_best_mapping_preview_from_sheets

router = APIRouter()


@router.post("/preview-data-mapping")
async def preview_data_mapping(request: Request):
    """Preview how parsed sheet rows map to WPP Scout's canonical schema."""
    raw = await request.body()

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
        return create_best_mapping_preview_from_sheets(sheets)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "mapping_failed", "message": str(e)},
        )
