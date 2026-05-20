import pandas as pd

from src.data_mapping import create_best_mapping_preview
from src.scorer import DEFAULT_RANK_METRIC, METHODOLOGY_VERSION, score_creatives


def _base_target_frequency_rows() -> list[dict]:
    return [
        {
            "creative_name": "Completion Led",
            "platform": "YouTube",
            "objective": "Target Frequency",
            "buying_type": "Paid",
            "format": "Video",
            "format_canonical": "Video",
            "youtube_measurement_family": "trueview_eligible",
            "spend": 1000,
            "reach": 0,
            "impressions": 10000,
            "frequency": 0,
            "low_confidence": False,
            "completion_vs_expected": 100,
            "vtr_2s": 10,
            "engagement_rate": 1,
            "cpm": 4,
            "canonical_hook_rate": 10,
            "canonical_hold_rate": 10,
            "canonical_completion_rate": 100,
            "audience_consistency": 1,
            "completion_rate": 80,
        },
        {
            "creative_name": "Retention Led",
            "platform": "YouTube",
            "objective": "Target Frequency",
            "buying_type": "Paid",
            "format": "Video",
            "format_canonical": "Video",
            "youtube_measurement_family": "trueview_eligible",
            "spend": 1000,
            "reach": 0,
            "impressions": 10000,
            "frequency": 0,
            "low_confidence": False,
            "completion_vs_expected": 1,
            "vtr_2s": 90,
            "engagement_rate": 5,
            "cpm": 6,
            "canonical_hook_rate": 90,
            "canonical_hold_rate": 90,
            "canonical_completion_rate": 1,
            "audience_consistency": 1,
            "completion_rate": 30,
        },
    ]


def test_target_frequency_attention_proxy_does_not_reuse_completion_primary_metric():
    scored = score_creatives(pd.DataFrame(_base_target_frequency_rows()))

    completion_led = scored.set_index("creative_name").loc["Completion Led"]
    retention_led = scored.set_index("creative_name").loc["Retention Led"]

    assert "canonical_completion_rate" not in completion_led["attention_proxy_metrics_used"]
    assert completion_led["attention_proxy_metrics_used"] == "canonical_hook_rate, canonical_hold_rate"
    assert retention_led["attention_proxy_score"] > completion_led["attention_proxy_score"]


def test_frequency_penalty_only_applies_when_reach_and_frequency_are_valid():
    rows = _base_target_frequency_rows()
    rows[0]["creative_name"] = "High Frequency Without Reach"
    rows[0]["frequency"] = 5
    rows[0]["reach"] = 0
    rows[1]["creative_name"] = "High Frequency With Reach"
    rows[1]["frequency"] = 5
    rows[1]["reach"] = 10000

    scored = score_creatives(pd.DataFrame(rows)).set_index("creative_name")

    assert scored.loc["High Frequency Without Reach", "freq_penalty"] == 1.0
    assert bool(scored.loc["High Frequency Without Reach", "frequency_penalty_applied"]) is False
    assert round(scored.loc["High Frequency With Reach", "freq_penalty"], 3) == 0.69
    assert bool(scored.loc["High Frequency With Reach", "frequency_penalty_applied"]) is True


def test_score_outputs_separate_creative_quality_from_media_efficiency_overlay():
    scored = score_creatives(pd.DataFrame(_base_target_frequency_rows()))

    assert "creative_quality_score" in scored.columns
    assert "media_efficiency_overlay_score" in scored.columns
    assert "combined_scout_score" in scored.columns
    assert scored["combined_scout_score"].equals(scored["composite_score"])
    assert not scored["creative_quality_score"].equals(scored["media_efficiency_overlay_score"])
    assert DEFAULT_RANK_METRIC == "creative_quality_score"


def test_score_outputs_methodology_metadata_and_row_level_caveats():
    scored = score_creatives(pd.DataFrame(_base_target_frequency_rows()))

    assert set(scored["methodology_version"]) == {METHODOLOGY_VERSION}
    assert set(scored["source_grain"]) == {"creative"}
    assert scored["directional_only"].tolist() == [True, True]
    assert scored["score_caveats"].str.contains("Small scoring cohort").all()
    assert scored["score_caveats"].str.contains("frequency penalty not applied").all()


def test_derived_platform_and_objective_use_evidence_strength_not_statistical_confidence(tmp_path):
    csv_path = tmp_path / "youtube_mid_funnel.csv"
    pd.DataFrame(
        {
            "Campaign": ["1713870 | Pixel | GB | YT TF | GAds_Arm 1"],
            "Ad name": ["(OPID-1)_Pixel_YouTube_20s_Generic_Imp"],
            "Cost": ["800"],
            "Impr.": ["8,189"],
        }
    ).to_csv(csv_path, index=False)

    preview = create_best_mapping_preview(str(csv_path))

    assert preview["derived_fields"]["platform"]["evidence_strength"] == "strong"
    assert preview["derived_fields"]["objective"]["evidence_strength"] == "strong"
    assert "confidence" not in preview["derived_fields"]["platform"]
    assert "confidence" not in preview["derived_fields"]["objective"]
