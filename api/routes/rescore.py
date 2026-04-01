from fastapi import APIRouter, HTTPException
from models import RescoreRequest
from scoring.pipeline import process_rescore

router = APIRouter()


@router.post("/rescore")
async def rescore(request: RescoreRequest):
    result = process_rescore(request.upload_id, request.filters)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "upload_expired",
                "message": "Session expired. Please re-upload your file.",
            },
        )
    return result
