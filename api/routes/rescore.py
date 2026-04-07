import gzip
import json
import traceback
from fastapi import APIRouter, Request, HTTPException
from scoring.pipeline import process_rescore

router = APIRouter()


@router.post("/rescore")
async def rescore(request: Request):
    raw = await request.body()
    print(
        f"[rescore] received {len(raw)} bytes, content-encoding={request.headers.get('content-encoding', 'none')}"
    )

    encoding = request.headers.get("content-encoding", "")
    if encoding == "gzip":
        try:
            raw = gzip.decompress(raw)
            print(f"[rescore] decompressed to {len(raw)} bytes")
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

    upload_id = payload.get("upload_id")
    filters = payload.get("filters", {})
    sheets = payload.get("sheets")

    if not upload_id:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_field", "message": "upload_id is required"},
        )

    has_sheets = sheets is not None
    print(
        f"[rescore] upload_id={upload_id}, filters={filters}, has_sheets={has_sheets}"
    )

    try:
        result = process_rescore(upload_id, filters, sheets)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": "scoring_error",
                "message": f"Scoring failed: {type(e).__name__}: {e}",
            },
        )

    if result is None:
        print(f"[rescore] cache miss for upload_id={upload_id}, no sheets provided")
        raise HTTPException(
            status_code=404,
            detail={
                "error": "upload_expired",
                "message": "Session expired. Please re-upload your file.",
            },
        )

    print(f"[rescore] success: {len(result.get('creatives', []))} creatives")
    return result
