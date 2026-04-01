import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from scoring.pipeline import process_upload, process_upload_json

router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


class SheetsUpload(BaseModel):
    sheets: dict[str, list[list]]


@router.post("/upload-and-score")
async def upload_and_score(payload: SheetsUpload):
    """Accept pre-parsed sheet data as JSON (parsed client-side with SheetJS)."""
    if not payload.sheets:
        raise HTTPException(
            status_code=400,
            detail={"error": "no_sheets", "message": "No sheet data provided"},
        )

    try:
        result = process_upload_json(payload.sheets)
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
