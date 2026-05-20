import pandas as pd

from src.insights import (
    compare_creatives,
    find_actionable_insights,
    get_concept_deep_dive,
    get_concept_rankings,
    get_budget_reallocation_recommendations,
    get_data_quality_report,
    get_fatigue_risks,
    get_low_confidence_creatives,
    get_score_breakdown,
)


def _scored_df():
    return pd.DataFrame(
        [
            {
                "creative_name": "Winner",
                "platform": "TikTok",
                "objective": "Video Views",
                "format_canonical": "Video",
                "composite_score": 82.4,
                "primary_kpi_score": 90,
                "secondary_kpi_score": 75,
                "cost_efficiency_score": 70,
                "attention_proxy_score": 80,
                "frequency": 1.6,
                "spend": 5000,
                "reach": 100000,
                "impressions": 160000,
                "action": "Scale Up",
                "tier": "Strong",
                "low_confidence": False,
                "explanation": "Strong performer.",
            },
            {
                "creative_name": "Fatigued",
                "platform": "Meta",
                "objective": "Awareness",
                "format_canonical": "Static",
                "composite_score": 32.0,
                "primary_kpi_score": 25,
                "secondary_kpi_score": 35,
                "cost_efficiency_score": 30,
                "attention_proxy_score": 0,
                "frequency": 4.2,
                "spend": 7000,
                "reach": 20000,
                "impressions": 84000,
                "action": "Consider Pausing - Fatigued",
                "tier": "Below Average",
                "low_confidence": False,
                "explanation": "High frequency.",
            },
            {
                "creative_name": "Low Data",
                "platform": "Meta",
                "objective": "Traffic",
                "format_canonical": "Static",
                "composite_score": 64.0,
                "primary_kpi_score": 60,
                "secondary_kpi_score": 65,
                "cost_efficiency_score": 55,
                "attention_proxy_score": 0,
                "frequency": 1.1,
                "spend": 120,
                "reach": 900,
                "impressions": 1000,
                "action": "Monitor - Low Data",
                "tier": "Average",
                "low_confidence": True,
                "explanation": "Needs more data.",
            },
        ]
    )


def _raw_df():
    return pd.DataFrame(
        [
            {
                "creative_name": "Winner",
                "platform": "TikTok",
                "objective": "Video Views",
                "spend": 5000,
                "reach": 100000,
                "impressions": 160000,
                "clicks": 500,
            },
            {
                "creative_name": "Fatigued",
                "platform": "Meta",
                "objective": "Awareness",
                "spend": 7000,
                "reach": 20000,
                "impressions": 84000,
                "clicks": 0,
            },
        ]
    )


def test_data_quality_report_has_status_counts_and_warnings():
    report = get_data_quality_report(_raw_df(), _scored_df())

    assert report["status"] == "ok"
    assert report["data"]["raw_rows"] == 2
    assert report["data"]["scored_creatives"] == 3
    assert report["data"]["low_confidence_creatives"] == 1
    assert any("low-confidence" in warning for warning in report["warnings"])


def test_data_quality_report_warns_for_small_scoring_cohorts():
    scored = _scored_df()
    scored["group_size"] = [2, 2, 9]

    report = get_data_quality_report(_raw_df(), scored)

    assert any("directional only" in warning for warning in report["warnings"])


def test_richer_insight_helpers_return_structured_outputs():
    scored = _scored_df()

    assert get_score_breakdown(scored, "Winner")["data"]["creative_name"] == "Winner"
    assert get_fatigue_risks(scored)["data"][0]["creative_name"] == "Fatigued"
    assert get_low_confidence_creatives(scored)["data"][0]["creative_name"] == "Low Data"
    assert compare_creatives(scored, ["Winner", "Fatigued"])["data"]["winner"] == "Winner"
    assert get_budget_reallocation_recommendations(scored)["data"]["scale_from"][0]["creative_name"] == "Fatigued"
    assert find_actionable_insights(_raw_df(), scored)["data"]["priority_actions"]


def test_creative_lookup_treats_names_as_literal_text():
    creative_name = "(OPID-4624156)_Deep-Thoughts_20s_Generic_Horizontal_Currys_Imp"
    scored = pd.DataFrame(
        [
            {
                "creative_name": creative_name,
                "platform": "YouTube",
                "objective": "Target Frequency",
                "format_canonical": "Video",
                "composite_score": 83.2,
                "primary_kpi_score": 90,
                "secondary_kpi_score": 75,
                "cost_efficiency_score": 70,
                "attention_proxy_score": 80,
                "frequency": 1.6,
                "spend": 5000,
                "reach": 0,
                "impressions": 160000,
                "action": "Scale Up",
                "tier": "Strong",
                "low_confidence": False,
                "explanation": "Strong performer.",
            }
        ]
    )

    assert get_score_breakdown(scored, creative_name)["status"] == "ok"
    assert compare_creatives(scored, [creative_name])["data"]["winner"] == creative_name


def test_concept_rankings_roll_up_multiple_creative_rows():
    scored = pd.DataFrame(
        [
            {
                "concept": "Creator Demo",
                "creative_name": "Creator Demo - Feed",
                "platform": "Meta",
                "objective": "Awareness",
                "format_canonical": "Video",
                "composite_score": 90.0,
                "spend": 1000,
                "reach": 10000,
                "impressions": 20000,
                "vtr_2s": 20.0,
                "completion_rate": 4.0,
                "ctr": 1.0,
                "engagement_rate": 2.0,
                "frequency": 2.0,
                "low_confidence": False,
                "action": "Scale Up",
            },
            {
                "concept": "Creator Demo",
                "creative_name": "Creator Demo - Stories",
                "platform": "Meta",
                "objective": "Awareness",
                "format_canonical": "Video",
                "composite_score": 50.0,
                "spend": 3000,
                "reach": 20000,
                "impressions": 60000,
                "vtr_2s": 10.0,
                "completion_rate": 1.0,
                "ctr": 0.5,
                "engagement_rate": 1.0,
                "frequency": 3.0,
                "low_confidence": False,
                "action": "Review",
            },
        ]
    )

    rankings = get_concept_rankings(scored)

    assert rankings["status"] == "ok"
    concept = rankings["data"][0]
    assert concept["concept"] == "Creator Demo"
    assert concept["n_creative_rows"] == 2
    assert concept["n_unique_creatives"] == 2
    assert concept["spend"] == 4000
    assert concept["composite_score"] == 60.0
    assert concept["best_variation_score"] == 90.0
    assert concept["worst_variation_score"] == 50.0
    assert concept["top_variations"][0]["creative_name"] == "Creator Demo - Feed"


def test_concept_deep_dive_matches_concept_and_returns_variants():
    scored = pd.DataFrame(
        [
            {
                "concept": "Creator Demo",
                "creative_name": "Creator Demo - Feed",
                "platform": "Meta",
                "objective": "Awareness",
                "format_canonical": "Video",
                "placement": "Feed",
                "composite_score": 90.0,
                "spend": 1000,
                "reach": 10000,
                "impressions": 20000,
                "vtr_2s": 20.0,
                "completion_rate": 4.0,
                "ctr": 1.0,
                "engagement_rate": 2.0,
                "frequency": 2.0,
                "low_confidence": False,
                "action": "Scale Up",
            },
            {
                "concept": "Creator Demo",
                "creative_name": "Creator Demo - Stories",
                "platform": "Meta",
                "objective": "Awareness",
                "format_canonical": "Video",
                "placement": "Stories",
                "composite_score": 50.0,
                "spend": 3000,
                "reach": 20000,
                "impressions": 60000,
                "vtr_2s": 10.0,
                "completion_rate": 1.0,
                "ctr": 0.5,
                "engagement_rate": 1.0,
                "frequency": 3.0,
                "low_confidence": False,
                "action": "Review",
            },
        ]
    )

    result = get_concept_deep_dive(scored, "Creator")

    assert result["status"] == "ok"
    assert result["data"]["rollup"]["concept"] == "Creator Demo"
    assert len(result["data"]["creative_rows"]) == 2
    assert result["data"]["placement_summary"][0]["placement"] == "Stories"
