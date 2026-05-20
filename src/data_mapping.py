from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from src.inference import infer_objective_for_dataframe, infer_platform_for_dataframe
from src.xlsx_reader import read_xlsx_sheet_dataframe


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
    "concept": "Creative concept rollup label. If absent, creative_name is used.",
    "product": "Product or product family label.",
    "wave": "Campaign wave or flight label.",
    "performance_score": "Workbook-provided score or performance index to preserve alongside Scout's composite_score.",
    "ad_id": "Stable ad or asset identifier when available, for example OPID or platform asset key.",
    "video_id": "Platform video identifier kept as metadata; not used as the primary creative key unless exact text is available.",
    "campaign_type": "Native platform campaign type or advertising channel type.",
    "campaign_subtype": "Native platform campaign subtype or advertising channel subtype.",
    "bid_strategy_type": "Native platform bid strategy type.",
    "optimization_goal": "Native platform optimization goal or campaign goal.",
    "trueview_views": "Google Ads TrueView view count.",
    "trueview_view_rate": "Google Ads TrueView view rate over view-eligible impressions.",
    "video_quartile_p25_rate": "Video played to 25% rate.",
    "video_quartile_p50_rate": "Video played to 50% rate.",
    "video_quartile_p75_rate": "Video played to 75% rate.",
    "video_quartile_p100_rate": "Video played to 100% rate.",
}

REQUIRED_FIELDS = ["creative_name", "platform", "objective", "spend", "impressions"]
OUTCOME_FIELDS = ["reach", "clicks", "vtr_2s", "video_views_100", "engagements", "shares"]
METADATA_FIELDS = {
    "ad_id",
    "ad_name_raw",
    "video_id",
    "campaign_type",
    "campaign_subtype",
    "bid_strategy_type",
    "optimization_goal",
    "format_raw",
    "placement_raw",
    "campaign_raw",
    "buying_type",
    "asset_type_raw",
    "os_target",
    "audience_segment",
    "concept",
    "product",
    "wave",
}
SKIP_SHEET_TERMS = ("methodology", "summary", "looker", "rankings")

FIELD_ALIASES = {
    "creative_name": ["creative", "creative concept", "ad name", "asset name"],
    "platform": ["platform", "publisher", "channel"],
    "objective": ["objective", "campaign objective", "buying objective"],
    "spend": ["spend", "spends", "cost", "amount spent", "media spend"],
    "impressions": ["impressions", "imps", "impr."],
    "reach": ["reach", "unique reach", "people reached"],
    "frequency": ["frequency", "freq"],
    "cpm": ["cpm", "cost per mille"],
    "clicks": ["clicks", "link clicks", "outbound clicks"],
    "vtr_2s": ["views", "video views", "2s views", "3s views", "hook rate"],
    "video_views_100": ["completed views", "complete views", "100% views", "video completions"],
    "shares": ["shares"],
    "engagements": ["engagements", "interactions", "total engagement"],
    "duration_s": ["duration", "video duration", "length"],
    "format_raw": ["format", "asset format", "format type"],
    "placement_raw": ["placement", "where it ran"],
    "campaign_raw": ["campaign", "campaign name"],
    "ad_name_raw": ["raw ad name", "ad variant", "variant"],
    "buying_type": ["buying type", "buying method", "paid or boosting"],
    "asset_type_raw": ["asset type", "creator type", "partner"],
    "os_target": ["os", "operating system", "device os"],
    "audience_segment": ["audience", "targeting", "segment"],
    "concept": ["concept", "creative territory", "idea"],
    "product": ["product", "product family"],
    "wave": ["wave", "flight", "phase"],
    "performance_score": [
        "score",
        "performance score",
        "performance index",
        "creative efficiency index",
        "efficiency index",
    ],
    "ad_id": ["ad id", "asset id", "opid", "consolidated asset key"],
    "video_id": ["video id", "youtube video id", "yt video id"],
    "campaign_type": ["campaign type", "advertising channel type"],
    "campaign_subtype": ["campaign subtype", "advertising channel subtype"],
    "bid_strategy_type": ["bid strategy type", "bidding strategy type"],
    "optimization_goal": ["optimization goal", "campaign goal", "goal type"],
    "trueview_views": ["trueview views", "true view views"],
    "trueview_view_rate": ["trueview view rate", "true view view rate"],
    "video_quartile_p25_rate": ["video played to 25%", "25% video played", "video quartile 25%"],
    "video_quartile_p50_rate": ["video played to 50%", "50% video played", "video quartile 50%"],
    "video_quartile_p75_rate": ["video played to 75%", "75% video played", "video quartile 75%"],
    "video_quartile_p100_rate": ["video played to 100%", "100% video played", "video quartile 100%"],
}


def get_canonical_schema() -> dict:
    """Return the documented target schema that mapping tools can use."""
    fields = {}
    for field, description in TARGET_FIELDS.items():
        fields[field] = {
            "description": description,
            "required": field in REQUIRED_FIELDS,
            "outcome_metric": field in OUTCOME_FIELDS,
            "aliases": FIELD_ALIASES.get(field, []),
        }
    return {
        "fields": fields,
        "required_fields": REQUIRED_FIELDS,
        "outcome_fields": OUTCOME_FIELDS,
        "minimum_viable_mapping": REQUIRED_FIELDS,
        "notes": [
            "Remote MCP agents should upload files by default: recommend_upload_plan, create_file_upload_session, append_file_upload_chunk, get_file_upload_status, finalize_file_upload, preview_data_mapping, ingest_data.",
            "file_path is only for files already available on the Scout server. Client-local desktop/download paths must be uploaded.",
            "For large uploads, prefer independently base64-encoded 64-128 KB raw byte chunks with chunk_index for idempotent retries.",
            "Excel parsing can auto-detect headers across the first 10 XML rows and does not rely on workbook dimension metadata.",
            "Use preview_data_mapping before ingesting non-standard exports.",
            "vtr_2s is the early attention field for 2-second views, 3-second views, or hook rate.",
            "video_views_100 is the completed-view count used for completion-rate metrics.",
            "performance_score preserves a workbook-provided score such as Creative Efficiency Index; Scout's own score remains composite_score.",
        ],
    }


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


def infer_alias_mapping(df: pd.DataFrame) -> dict[str, str]:
    """Map obvious canonical/alias columns without using the LLM."""
    alias_to_field = {}
    for field, aliases in FIELD_ALIASES.items():
        keys = [field, field.replace("_", " "), *aliases]
        for key in keys:
            alias_to_field[_normalise_label(key)] = field

    mapping = {}
    seen_targets = set()
    for column in df.columns:
        target = alias_to_field.get(_normalise_label(column))
        if target and target not in seen_targets:
            mapping[column] = target
            seen_targets.add(target)
    return mapping


def merge_mapping_candidates(alias_mapping: dict[str, str], provider_mapping: dict[str, str]) -> dict[str, str]:
    """Merge deterministic aliases with provider mappings without losing required fields."""
    merged = dict(alias_mapping)
    for source, provider_target in provider_mapping.items():
        alias_target = merged.get(source)
        if alias_target is None:
            if provider_target not in merged.values():
                merged[source] = provider_target
            continue
        if provider_target in REQUIRED_FIELDS and alias_target not in REQUIRED_FIELDS:
            merged[source] = provider_target
    return merged


def _normalise_label(value) -> str:
    return " ".join(str(value or "").strip().replace("\n", " ").replace("_", " ").lower().split())


def _column_series(df: pd.DataFrame, source: str) -> pd.Series:
    selected = df.loc[:, source]
    if isinstance(selected, pd.DataFrame):
        for _, series in selected.items():
            if not series.dropna().empty:
                return series
        return selected.iloc[:, 0]
    return selected


def _sample_normalized_rows(df: pd.DataFrame, valid_mapping: dict[str, str]) -> list[dict]:
    sample_data = {}
    for target in TARGET_FIELDS:
        source = next(
            (source for source, mapped_target in valid_mapping.items() if mapped_target == target),
            None,
        )
        if source is None and target in df.columns:
            source = target
        if source is not None:
            sample_data[target] = _column_series(df, source)
    if not sample_data:
        return []
    return pd.DataFrame(sample_data).head(5).to_dict(orient="records")


def create_mapping_preview(
    df: pd.DataFrame,
    sheet_name: str,
    mapping: dict[str, str],
    preserve_columns: list[str] | None = None,
) -> dict:
    """Build an auditable preview for a proposed source-column mapping."""
    valid_mapping = {
        source: target
        for source, target in mapping.items()
        if source in df.columns and target in TARGET_FIELDS
    }
    mapped_targets = set(valid_mapping.values())
    for source in df.columns:
        if source in TARGET_FIELDS and source not in valid_mapping and source not in mapped_targets:
            valid_mapping[source] = source
            mapped_targets.add(source)

    mapped_targets = set(valid_mapping.values())
    preserve_columns = preserve_columns or []
    preserved_custom_columns = [
        source for source in preserve_columns if source in df.columns and source not in valid_mapping
    ]

    sample_rows = _sample_normalized_rows(df, valid_mapping)

    warnings = []
    derived_fields = {}
    platform_inferred = None
    objective_inferred = None
    if "platform" not in mapped_targets:
        platform_inferred = infer_platform_for_dataframe(df)
        if platform_inferred.value != "Unknown":
            mapped_targets.add("platform")
            derived_fields["platform"] = platform_inferred.to_preview_dict()
    if "objective" not in mapped_targets:
        objective_inferred = infer_objective_for_dataframe(df)
        if objective_inferred.value != "Unknown":
            mapped_targets.add("objective")
            derived_fields["objective"] = objective_inferred.to_preview_dict()

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

    video_id_source = next(
        (source for source, target in valid_mapping.items() if target == "video_id"),
        None,
    )
    if video_id_source is not None:
        video_id_values = _column_series(df, video_id_source).dropna().astype(str)
        if video_id_values.str.contains(r"^\s*\d+(?:\.\d+)?e\+\d+\s*$", case=False, regex=True).any():
            warnings.append(
                "Video ID appears in scientific notation; use creative_name/ad_id as the stable key unless exact text IDs are supplied."
            )

    confidence_by_field = {}
    for source, target in valid_mapping.items():
        confidence_by_field[target] = max(
            confidence_by_field.get(target, 0.0),
            _confidence_for_mapping(source, target),
        )

    mapping_diagnostics = []
    for source, target in valid_mapping.items():
        source_series = _column_series(df, source)
        sample_values = [
            value
            for value in source_series.dropna().head(3).astype(str).tolist()
            if value and value.lower() != "nan"
        ]
        mapping_diagnostics.append(
            {
                "source_column": source,
                "canonical_field": target,
                "description": TARGET_FIELDS[target],
                "confidence": confidence_by_field.get(target, 0.0),
                "sample_values": sample_values,
            }
        )

    field_coverage = {
        "mapped_field_count": len(mapped_targets),
        "required_mapped": sorted(
            field for field in REQUIRED_FIELDS if field in mapped_targets
        ),
        "required_missing": missing_required,
        "outcome_fields_mapped": sorted(
            field for field in OUTCOME_FIELDS if field in mapped_targets
        ),
    }
    canonical_mapped_fields = sorted(mapped_targets - METADATA_FIELDS)
    preserved_metadata_fields = sorted(mapped_targets & METADATA_FIELDS)

    return {
        "sheet_name": sheet_name,
        "row_count": int(len(df)),
        "source_columns": list(df.columns),
        "proposed_mapping": valid_mapping,
        "mapping_diagnostics": mapping_diagnostics,
        "confidence_by_field": confidence_by_field,
        "field_coverage": field_coverage,
        "canonical_mapped_fields": canonical_mapped_fields,
        "preserved_metadata_fields": preserved_metadata_fields,
        "preserved_custom_columns": preserved_custom_columns,
        "derived_fields": derived_fields,
        "missing_required_fields": missing_required,
        "ambiguous_targets": ambiguous_targets,
        "ignored_columns": [
            col
            for col in df.columns
            if col not in valid_mapping and col not in preserved_custom_columns
        ],
        "sample_normalized_rows": sample_rows,
        "canonical_schema": get_canonical_schema(),
        "warnings": warnings,
        "ready_to_ingest": not missing_required and not ambiguous_targets,
    }


def iter_candidate_dataframes(filepath: str) -> list[tuple[str, pd.DataFrame]]:
    """Read plausible data-bearing sheets or CSV dataframes from an upload."""
    path = Path(filepath)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return [(path.stem, pd.read_csv(path, dtype=str, keep_default_na=False))]

    xl = pd.ExcelFile(filepath)
    frames = []
    for sheet_name in xl.sheet_names:
        if any(skip in sheet_name.lower() for skip in SKIP_SHEET_TERMS):
            continue
        df, _ = read_xlsx_sheet_dataframe(filepath, sheet_name)
        if df.empty:
            df = pd.read_excel(xl, sheet_name=sheet_name)
        if not df.empty and len(df.columns) >= 3:
            frames.append((sheet_name, df))
    return frames


def read_selected_dataframe(
    filepath: str, sheet_name: str | None = None, header_row: int | None = None
) -> tuple[str, pd.DataFrame]:
    path = Path(filepath)
    if path.suffix.lower() == ".csv":
        return path.stem, pd.read_csv(
            path,
            header=(header_row - 1) if header_row else 0,
            dtype=str,
            keep_default_na=False,
        )

    xl = pd.ExcelFile(filepath)
    selected_sheet = sheet_name or xl.sheet_names[0]
    if selected_sheet not in xl.sheet_names:
        raise ValueError(
            f"Sheet '{selected_sheet}' not found. Available sheets: {', '.join(xl.sheet_names)}"
        )
    if header_row is None:
        try:
            df, detected_header_row = read_xlsx_sheet_dataframe(filepath, selected_sheet)
            if not df.empty and len(df.columns) >= 3:
                df.attrs["detected_header_row"] = detected_header_row
                return selected_sheet, df
        except Exception:
            pass

    header = (int(header_row) - 1) if header_row is not None else 0
    df = pd.read_excel(xl, sheet_name=selected_sheet, header=header)
    detected_header_row = header_row
    if df.empty or len(df.columns) < 3 or (
        header_row is None and not _has_header_signal(df.columns)
    ):
        df, detected_header_row = read_xlsx_sheet_dataframe(
            filepath,
            selected_sheet,
            header_row=header_row,
        )
    df.attrs["detected_header_row"] = detected_header_row
    return selected_sheet, df


def _has_header_signal(columns) -> bool:
    labels = {str(col).strip().lower().replace("\n", " ") for col in columns}
    return bool(
        labels
        & {
            "creative name",
            "ad name",
            "ad name in platform",
            "platform",
            "objective",
            "spends",
            "spend",
            "impressions",
        }
    )


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
        mapping = infer_alias_mapping(df)
        if not all(field in mapping.values() for field in REQUIRED_FIELDS):
            mapping = merge_mapping_candidates(mapping, mapping_provider(df))
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
    sheet_name: str | None = None,
    header_row: int | None = None,
    preserve_columns: list[str] | None = None,
) -> dict:
    """Create the highest-coverage mapping preview for an uploaded file."""
    if mapping_provider is None:
        from src.llm_mapper import generate_column_mapping

        mapping_provider = generate_column_mapping

    previews = []
    candidates = (
        [read_selected_dataframe(filepath, sheet_name, header_row)]
        if sheet_name or header_row
        else iter_candidate_dataframes(filepath)
    )
    for sheet_name, df in candidates:
        mapping = infer_alias_mapping(df)
        if not all(field in mapping.values() for field in REQUIRED_FIELDS):
            mapping = merge_mapping_candidates(mapping, mapping_provider(df))
        preview = create_mapping_preview(
            df,
            sheet_name,
            mapping,
            preserve_columns=preserve_columns,
        )
        if df.attrs.get("detected_header_row"):
            preview["detected_header_row"] = df.attrs["detected_header_row"]
        previews.append(
            preview
        )

    if not previews:
        raise ValueError("No data-bearing sheets or CSV rows found to map.")

    def preview_score(preview: dict) -> tuple[int, int, int]:
        mapped_count = len(preview["proposed_mapping"])
        missing_count = len(preview["missing_required_fields"])
        warning_count = len(preview["warnings"])
        return (mapped_count, -missing_count, -warning_count)

    return max(previews, key=preview_score)
