from pathlib import Path
from typing import Callable, Optional

import pandas as pd


TARGET_FIELDS = {
    "ad_name_raw": "The raw name of the ad variant.",
    "creative_name": "The overarching creative concept name.",
    "platform": "The platform the ad ran on, for example Meta or TikTok.",
    "format_raw": "The ad format, for example Video, Static, or Motion.",
    "placement_raw": "Where the ad appeared, for example In-Feed or Stories.",
    "campaign_raw": "The campaign name.",
    "objective": "The campaign objective, for example Awareness or Video Views.",
    "buying_type": "The buying type, usually Paid or Boosting.",
    "reach": "Unique users reached.",
    "impressions": "Total ad impressions.",
    "frequency": "Average exposure frequency.",
    "spend": "Total amount spent.",
    "cpm": "Cost per 1000 impressions.",
    "clicks": "Total clicks.",
    "vtr_2s": "Hook rate or 2-second/3-second video plays.",
    "video_views_100": "100% video completions.",
    "shares": "Total shares.",
    "engagements": "Total engagements or interactions.",
    "duration_s": "Video asset duration in seconds.",
    "asset_type_raw": "Granular asset type, for example BAU, Creator, or Partner.",
    "os_target": "Operating system targeted, for example iOS, Android, or All.",
    "audience_segment": "Audience or targeting segment.",
}

REQUIRED_FIELDS = ["creative_name", "platform", "objective", "spend", "impressions"]
OUTCOME_FIELDS = ["reach", "clicks", "vtr_2s", "video_views_100", "engagements", "shares"]
SKIP_SHEET_TERMS = ("methodology", "summary", "looker", "rankings")


def _confidence_for_mapping(source: str, target: str) -> float:
    source_words = source.lower().replace("_", " ").replace("-", " ")
    target_words = target.lower().replace("_", " ")
    if source_words == target_words:
        return 0.98
    if target_words in source_words:
        return 0.92
    if any(part and part in source_words for part in target_words.split()):
        return 0.85
    return 0.8


def create_mapping_preview(
    df: pd.DataFrame, sheet_name: str, mapping: dict[str, str]
) -> dict:
    """Build an auditable preview for a proposed source-column mapping."""
    valid_mapping = {
        source: target
        for source, target in mapping.items()
        if source in df.columns and target in TARGET_FIELDS
    }
    mapped_targets = set(valid_mapping.values())

    mapped_df = df.rename(columns=valid_mapping)
    sample_cols = [field for field in TARGET_FIELDS if field in mapped_df.columns]
    sample_rows = mapped_df[sample_cols].head(5).to_dict(orient="records")

    warnings = []
    missing_required = [
        field for field in REQUIRED_FIELDS if field not in mapped_targets
    ]
    if missing_required:
        warnings.append(
            "Missing required fields: " + ", ".join(sorted(missing_required))
        )

    if not any(field in mapped_targets for field in OUTCOME_FIELDS):
        warnings.append(
            "No outcome metric mapped; scores may be weak or impossible to compare."
        )

    target_counts = {}
    for target in valid_mapping.values():
        target_counts[target] = target_counts.get(target, 0) + 1
    ambiguous_targets = sorted(
        target for target, count in target_counts.items() if count > 1
    )
    if ambiguous_targets:
        warnings.append(
            "Multiple source columns map to: " + ", ".join(ambiguous_targets)
        )

    confidence_by_field = {}
    for source, target in valid_mapping.items():
        confidence_by_field[target] = max(
            confidence_by_field.get(target, 0.0),
            _confidence_for_mapping(source, target),
        )

    return {
        "sheet_name": sheet_name,
        "row_count": int(len(df)),
        "source_columns": list(df.columns),
        "proposed_mapping": valid_mapping,
        "confidence_by_field": confidence_by_field,
        "missing_required_fields": missing_required,
        "ambiguous_targets": ambiguous_targets,
        "ignored_columns": [col for col in df.columns if col not in valid_mapping],
        "sample_normalized_rows": sample_rows,
        "warnings": warnings,
        "ready_to_ingest": not missing_required and not ambiguous_targets,
    }


def iter_candidate_dataframes(filepath: str) -> list[tuple[str, pd.DataFrame]]:
    """Read plausible data-bearing sheets or CSV dataframes from an upload."""
    path = Path(filepath)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return [(path.stem, pd.read_csv(path))]

    xl = pd.ExcelFile(filepath)
    frames = []
    for sheet_name in xl.sheet_names:
        if any(skip in sheet_name.lower() for skip in SKIP_SHEET_TERMS):
            continue
        df = pd.read_excel(xl, sheet_name=sheet_name)
        if not df.empty and len(df.columns) >= 3:
            frames.append((sheet_name, df))
    return frames


def rows_to_dataframe(rows: list[list]) -> pd.DataFrame:
    """Convert SheetJS-style array rows to a dataframe using the most likely header row."""
    if not rows:
        return pd.DataFrame()

    best_index = 0
    best_score = -1
    for index, row in enumerate(rows[:5]):
        values = [str(value).strip() for value in row if value is not None]
        score = sum(1 for value in values if value)
        if score > best_score:
            best_index = index
            best_score = score

    headers = [
        str(value).strip().replace("\n", " ") if value is not None else ""
        for value in rows[best_index]
    ]
    data_rows = rows[best_index + 1 :]
    if not headers or not data_rows:
        return pd.DataFrame()

    width = len(headers)
    padded_rows = [
        (list(row) + [None] * (width - len(row)))[:width] for row in data_rows
    ]
    df = pd.DataFrame(padded_rows, columns=headers)
    return df.dropna(how="all")


def iter_candidate_dataframes_from_sheets(
    sheets: dict[str, list[list]],
) -> list[tuple[str, pd.DataFrame]]:
    """Read plausible data-bearing dataframes from parsed browser sheet rows."""
    frames = []
    for sheet_name, rows in sheets.items():
        if any(skip in sheet_name.lower() for skip in SKIP_SHEET_TERMS):
            continue
        df = rows_to_dataframe(rows)
        if not df.empty and len(df.columns) >= 3:
            frames.append((sheet_name, df))
    return frames


def create_best_mapping_preview_from_sheets(
    sheets: dict[str, list[list]],
    mapping_provider: Optional[Callable[[pd.DataFrame], dict[str, str]]] = None,
) -> dict:
    """Create the highest-coverage mapping preview for parsed browser sheet rows."""
    if mapping_provider is None:
        from src.llm_mapper import generate_column_mapping

        mapping_provider = generate_column_mapping

    previews = []
    for sheet_name, df in iter_candidate_dataframes_from_sheets(sheets):
        mapping = mapping_provider(df)
        previews.append(create_mapping_preview(df, sheet_name, mapping))

    if not previews:
        raise ValueError("No data-bearing sheet rows found to map.")

    def preview_score(preview: dict) -> tuple[int, int, int]:
        mapped_count = len(preview["proposed_mapping"])
        missing_count = len(preview["missing_required_fields"])
        warning_count = len(preview["warnings"])
        return (mapped_count, -missing_count, -warning_count)

    return max(previews, key=preview_score)


def create_best_mapping_preview(
    filepath: str,
    mapping_provider: Optional[Callable[[pd.DataFrame], dict[str, str]]] = None,
) -> dict:
    """Create the highest-coverage mapping preview for an uploaded file."""
    if mapping_provider is None:
        from src.llm_mapper import generate_column_mapping

        mapping_provider = generate_column_mapping

    previews = []
    for sheet_name, df in iter_candidate_dataframes(filepath):
        mapping = mapping_provider(df)
        previews.append(create_mapping_preview(df, sheet_name, mapping))

    if not previews:
        raise ValueError("No data-bearing sheets or CSV rows found to map.")

    def preview_score(preview: dict) -> tuple[int, int, int]:
        mapped_count = len(preview["proposed_mapping"])
        missing_count = len(preview["missing_required_fields"])
        warning_count = len(preview["warnings"])
        return (mapped_count, -missing_count, -warning_count)

    return max(previews, key=preview_score)
