import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from scoring.pipeline import process_upload

router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


@router.post("/upload-and-score")
async def upload_and_score(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_file",
                "message": "Please upload an Excel file (.xlsx)",
            },
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = process_upload(tmp_path)
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
    finally:
        Path(tmp_path).unlink(missing_ok=True)
