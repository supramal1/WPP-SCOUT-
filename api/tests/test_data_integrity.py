"""Verify JSON upload path produces identical results to file-based path."""

import pytest
import pandas as pd
from scoring.loader import load_data, load_data_from_sheets
from scoring.pipeline import _score_and_enrich


def test_json_path_matches_file_path(sample_excel_path, sample_sheets_json):
    """The JSON pipeline should produce the same df_raw and df as the file pipeline."""
    df_raw_file, df_file = load_data(sample_excel_path)
    df_raw_json, df_json = load_data_from_sheets(sample_sheets_json)

    # Same number of raw rows
    assert len(df_raw_file) == len(df_raw_json), (
        f"Raw row count mismatch: file={len(df_raw_file)}, json={len(df_raw_json)}"
    )

    # Same number of aggregated rows
    assert len(df_file) == len(df_json), (
        f"Aggregated row count mismatch: file={len(df_file)}, json={len(df_json)}"
    )

    # Same columns in df_raw
    file_cols = set(df_raw_file.columns)
    json_cols = set(df_raw_json.columns)
    missing_in_json = file_cols - json_cols
    extra_in_json = json_cols - file_cols
    assert not missing_in_json, f"Columns in file but not JSON: {missing_in_json}"
    assert not extra_in_json, f"Columns in JSON but not file: {extra_in_json}"

    # Same columns in aggregated df
    file_agg_cols = set(df_file.columns)
    json_agg_cols = set(df_json.columns)
    missing_agg = file_agg_cols - json_agg_cols
    extra_agg = json_agg_cols - file_agg_cols
    assert not missing_agg, f"Agg columns in file but not JSON: {missing_agg}"
    assert not extra_agg, f"Agg columns in JSON but not file: {extra_agg}"

    # Same creative names
    file_names = sorted(df_raw_file["creative_name"].unique())
    json_names = sorted(df_raw_json["creative_name"].unique())
    assert file_names == json_names, (
        f"Creative names differ:\n  file: {file_names}\n  json: {json_names}"
    )

    # Same platforms
    file_platforms = sorted(df_raw_file["platform"].unique())
    json_platforms = sorted(df_raw_json["platform"].unique())
    assert file_platforms == json_platforms

    # Key numeric columns should match closely
    for col in [
        "spend",
        "impressions",
        "reach",
        "clicks",
        "vtr_2s",
        "video_views_100",
        "shares",
        "engagements",
        "total_plays",
    ]:
        if col in df_raw_file.columns:
            file_sum = df_raw_file[col].sum()
            json_sum = df_raw_json[col].sum()
            assert abs(file_sum - json_sum) < 0.01, (
                f"Column '{col}' sum mismatch: file={file_sum}, json={json_sum}"
            )


def test_scored_output_matches(sample_excel_path, sample_sheets_json):
    """After scoring, both paths should produce matching composite scores."""
    _, df_file = load_data(sample_excel_path)
    _, df_json = load_data_from_sheets(sample_sheets_json)

    scored_file = _score_and_enrich(df_file)
    scored_json = _score_and_enrich(df_json)

    assert len(scored_file) == len(scored_json)

    # Both should now have scoring columns
    for col in ["composite_score", "tier", "action", "scoring_group", "explanation"]:
        assert col in scored_file.columns, f"File scored missing '{col}'"
        assert col in scored_json.columns, f"JSON scored missing '{col}'"

    # Scores should be identical
    file_scores = scored_file.set_index("creative_name")["composite_score"].to_dict()
    json_scores = scored_json.set_index("creative_name")["composite_score"].to_dict()
    for name in file_scores:
        assert name in json_scores, f"Creative '{name}' missing from JSON path"
        diff = abs(file_scores[name] - json_scores[name])
        assert diff < 0.1, (
            f"Score mismatch for '{name}': file={file_scores[name]:.2f}, "
            f"json={json_scores[name]:.2f}"
        )


def test_json_path_column_inventory(sample_sheets_json):
    """Check that all expected columns exist after JSON loading."""
    df_raw, df = load_data_from_sheets(sample_sheets_json)

    # Critical raw columns
    expected_raw = [
        "creative_name",
        "platform",
        "buying_type",
        "format_canonical",
        "placement",
        "placement_canonical",
        "objective",
        "objective_normalized",
        "os_target",
        "asset_type_canonical",
        "campaign_normalized",
        "spend",
        "reach",
        "impressions",
        "clicks",
        "frequency",
        "vtr_2s",
        "video_views_100",
        "shares",
        "engagements",
        "duration_s",
        "concept",
        "product",
        "wave",
        "audience_segment",
        "device_type",
    ]
    raw_missing = [c for c in expected_raw if c not in df_raw.columns]
    assert not raw_missing, f"Missing raw columns: {raw_missing}"

    # Aggregated columns (before scoring — loader output)
    expected_agg = [
        "creative_name",
        "platform",
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
        "low_confidence",
        "completion_vs_expected",
    ]
    agg_missing = [c for c in expected_agg if c not in df.columns]
    assert not agg_missing, f"Missing aggregated columns: {agg_missing}"

    # After scoring should add these
    scored = _score_and_enrich(df)
    score_cols = ["composite_score", "tier", "action", "scoring_group", "explanation"]
    score_missing = [c for c in score_cols if c not in scored.columns]
    assert not score_missing, f"Missing scored columns: {score_missing}"
