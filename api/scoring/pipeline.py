import pandas as pd
import numpy as np
from cache import UploadCache
from scoring.loader import load_data, load_data_from_sheets
from scoring.scorer import score_raw_variants, assign_action
from scoring.explainer import generate_explanations

# Global cache instance
upload_cache = UploadCache(ttl_seconds=3600)

# Filter key -> DataFrame column mapping (from spec)
FILTER_COLUMN_MAP = {
    "campaign": "campaign_normalized",
    "platform": "platform",
    "os": "os_target",
    "placement": "placement",
    "objective": "objective",
    "format": "format_canonical",
    "asset_type": "asset_type_canonical",
    "buying_type": "buying_type",
    "concept": "concept",
}


def _safe_val(val):
    """Convert pandas/numpy values to JSON-safe Python types."""
    if val is None or (isinstance(val, float) and (pd.isna(val) or np.isinf(val))):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val


def _df_to_creatives(df: pd.DataFrame) -> list[dict]:
    """Convert scored DataFrame to list of creative dicts for API response."""
    fields = [
        "creative_name",
        "concept",
        "platform",
        "objective",
        "format_canonical",
        "placement",
        "os_target",
        "asset_type_canonical",
        "buying_type",
        "campaign_normalized",
        "composite_score",
        "tier",
        "action",
        "spend",
        "reach",
        "impressions",
        "vtr_2s",
        "completion_rate",
        "ctr",
        "engagement_rate",
        "share_rate",
        "cpm",
        "frequency",
        "cost_per_complete_view",
        "reach_per_pound",
        "completion_vs_expected",
        "scoring_group",
        "explanation",
        "low_confidence",
    ]
    records = []
    for _, row in df.iterrows():
        record = {}
        for f in fields:
            val = row.get(f)
            key = "format" if f == "format_canonical" else f
            record[key] = _safe_val(val)
        records.append(record)
    return records


def _extract_filters(df: pd.DataFrame) -> dict:
    """Extract distinct filter values from DataFrame."""

    def _unique_sorted(col: str) -> list[str]:
        if col not in df.columns:
            return []
        vals = df[col].dropna().astype(str).unique()
        return sorted([v for v in vals if v.strip() and v != "nan"])

    return {
        "campaigns": _unique_sorted("campaign_normalized"),
        "platforms": _unique_sorted("platform"),
        "os": _unique_sorted("os_target"),
        "placements": _unique_sorted("placement"),
        "objectives": _unique_sorted("objective"),
        "formats": _unique_sorted("format_canonical"),
        "asset_types": _unique_sorted("asset_type_canonical"),
        "buying_types": _unique_sorted("buying_type"),
        "concepts": _unique_sorted("concept"),
    }


def _score_and_enrich(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Run scoring pipeline: score_raw_variants -> assign_action -> generate_explanations."""
    scored = score_raw_variants(df_raw)
    scored["action"] = scored.apply(assign_action, axis=1)
    scored = generate_explanations(scored)
    return scored


def _apply_filters(df: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    """Subset DataFrame by filter dict using the column mapping."""
    result = df.copy()
    for filter_key, filter_value in filters.items():
        col = FILTER_COLUMN_MAP.get(filter_key)
        if col and col in result.columns:
            result = result[result[col].astype(str) == str(filter_value)]
    return result


def process_upload(filepath: str) -> dict:
    """Full upload pipeline: load -> score -> cache -> serialize."""
    df_raw, _ = load_data(filepath)
    upload_id = upload_cache.store(df_raw)
    scored = _score_and_enrich(df_raw)
    creatives = _df_to_creatives(scored)
    filters = _extract_filters(df_raw)
    platforms_found = sorted(df_raw["platform"].dropna().unique().tolist())

    return {
        "upload_id": upload_id,
        "creatives": creatives,
        "filters": filters,
        "meta": {
            "total_rows": len(scored),
            "platforms_found": platforms_found,
            "brand": "",
        },
    }


def process_upload_json(sheets: dict[str, list[list]]) -> dict:
    """Upload pipeline from pre-parsed JSON sheet data (no file needed)."""
    df_raw, _ = load_data_from_sheets(sheets)
    upload_id = upload_cache.store(df_raw)
    scored = _score_and_enrich(df_raw)
    creatives = _df_to_creatives(scored)
    filters = _extract_filters(df_raw)
    platforms_found = sorted(df_raw["platform"].dropna().unique().tolist())

    return {
        "upload_id": upload_id,
        "creatives": creatives,
        "filters": filters,
        "meta": {
            "total_rows": len(scored),
            "platforms_found": platforms_found,
            "brand": "",
        },
    }


def process_rescore(upload_id: str, filters: dict[str, str]) -> dict | None:
    """Rescore with filters: retrieve cached df_raw -> filter -> score -> serialize."""
    df_raw = upload_cache.get(upload_id)
    if df_raw is None:
        return None

    filtered = _apply_filters(df_raw, filters)
    if filtered.empty:
        return {
            "creatives": [],
            "filters": _extract_filters(filtered),
            "meta": {"total_rows": 0, "platforms_found": [], "brand": ""},
        }

    scored = _score_and_enrich(filtered)
    creatives = _df_to_creatives(scored)
    filter_options = _extract_filters(filtered)
    platforms_found = sorted(filtered["platform"].dropna().unique().tolist())

    return {
        "creatives": creatives,
        "filters": filter_options,
        "meta": {
            "total_rows": len(scored),
            "platforms_found": platforms_found,
            "brand": "",
        },
    }
