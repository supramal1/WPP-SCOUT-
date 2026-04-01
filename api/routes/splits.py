from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from scoring.pipeline import upload_cache, _safe_val

router = APIRouter()

SPLITS_FIELDS = [
    "creative_name",
    "platform",
    "buying_type",
    "format_canonical",
    "placement_canonical",
    "placement",
    "objective_normalized",
    "objective",
    "asset_type_canonical",
    "os_target",
    "audience_segment",
    "campaign_normalized",
    "concept",
    "spend",
    "reach",
    "impressions",
    "frequency",
    "vtr_2s",
    "completion_rate",
    "ctr",
    "engagement_rate",
    "cpm",
    "duration_s",
]


class SplitsRequest(BaseModel):
    upload_id: str


def _df_to_splits(df) -> list[dict]:
    records = []
    for _, row in df.iterrows():
        record = {}

        record["creative_name"] = _safe_val(row.get("creative_name"))
        record["platform"] = _safe_val(row.get("platform"))
        record["buying_type"] = _safe_val(row.get("buying_type"))
        record["format_canonical"] = _safe_val(row.get("format_canonical"))

        # placement: prefer placement_canonical, fall back to placement
        record["placement_canonical"] = _safe_val(
            row.get("placement_canonical") or row.get("placement")
        )

        # objective: prefer objective_normalized, fall back to objective
        record["objective_normalized"] = _safe_val(
            row.get("objective_normalized") or row.get("objective")
        )

        record["asset_type_canonical"] = _safe_val(row.get("asset_type_canonical"))
        record["os_target"] = _safe_val(row.get("os_target"))
        record["audience_segment"] = _safe_val(row.get("audience_segment"))
        record["campaign_normalized"] = _safe_val(row.get("campaign_normalized"))
        record["concept"] = _safe_val(row.get("concept"))
        record["spend"] = _safe_val(row.get("spend"))
        record["reach"] = _safe_val(row.get("reach"))
        record["impressions"] = _safe_val(row.get("impressions"))
        record["frequency"] = _safe_val(row.get("frequency"))
        record["vtr_2s"] = _safe_val(row.get("vtr_2s"))
        record["completion_rate"] = _safe_val(row.get("completion_rate"))
        record["ctr"] = _safe_val(row.get("ctr"))
        record["engagement_rate"] = _safe_val(row.get("engagement_rate"))
        record["cpm"] = _safe_val(row.get("cpm"))
        record["duration_s"] = _safe_val(row.get("duration_s"))

        # low_confidence: use existing column if present, otherwise compute inline
        if "low_confidence" in df.columns:
            record["low_confidence"] = _safe_val(row.get("low_confidence"))
        else:
            spend = row.get("spend")
            reach = row.get("reach")
            try:
                spend_val = float(spend) if spend is not None else 0.0
                reach_val = float(reach) if reach is not None else 0.0
                record["low_confidence"] = spend_val < 500 or reach_val < 10000
            except (TypeError, ValueError):
                record["low_confidence"] = True

        records.append(record)
    return records


@router.post("/splits")
async def get_splits(request: SplitsRequest):
    df_raw = upload_cache.get(request.upload_id)
    if df_raw is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "upload_expired"},
        )

    splits = _df_to_splits(df_raw)
    return {
        "splits": splits,
        "meta": {"total_rows": len(splits)},
    }
