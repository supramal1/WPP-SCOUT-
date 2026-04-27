import pandas as pd

from src.data_mapping import create_mapping_preview
from src.loader import load_data


def test_create_mapping_preview_reports_validation_and_sample_rows():
    df = pd.DataFrame(
        {
            "Creative Concept": ["Pixel Pro Video"],
            "Where it ran": ["TikTok"],
            "The Objective": ["Video Views"],
            "Total Spent": [1500],
            "Impressions Total": [100000],
            "People Reached": [80000],
            "Link Clicks": [500],
            "3s Video Plays": [20000],
            "100% Video Completions": [1000],
            "Buying Method": ["Paid"],
            "Format Type": ["Video"],
            "Planner Notes": ["keep this out"],
        }
    )

    preview = create_mapping_preview(
        df,
        sheet_name="Planner Export",
        mapping={
            "Creative Concept": "creative_name",
            "Where it ran": "platform",
            "The Objective": "objective",
            "Total Spent": "spend",
            "Impressions Total": "impressions",
            "People Reached": "reach",
            "Link Clicks": "clicks",
            "3s Video Plays": "vtr_2s",
            "100% Video Completions": "video_views_100",
            "Buying Method": "buying_type",
            "Format Type": "format_raw",
        },
    )

    assert preview["sheet_name"] == "Planner Export"
    assert preview["proposed_mapping"]["Creative Concept"] == "creative_name"
    assert preview["missing_required_fields"] == []
    assert preview["ignored_columns"] == ["Planner Notes"]
    assert preview["sample_normalized_rows"][0]["creative_name"] == "Pixel Pro Video"
    assert preview["sample_normalized_rows"][0]["platform"] == "TikTok"
    assert preview["confidence_by_field"]["creative_name"] >= 0.8


def test_load_data_uses_explicit_mapping_for_unstructured_csv(tmp_path):
    csv_path = tmp_path / "planner_export.csv"
    pd.DataFrame(
        {
            "Creative Concept": ["Pixel Pro Video", "Pixel Static"],
            "Where it ran": ["TikTok", "Meta"],
            "The Objective": ["Video Views", "Awareness"],
            "Total Spent": [1500, 900],
            "Impressions Total": [100000, 50000],
            "People Reached": [80000, 45000],
            "Link Clicks": [500, 100],
            "3s Video Plays": [20000, 0],
            "100% Video Completions": [1000, 0],
            "Buying Method": ["Paid", "Paid"],
            "Format Type": ["Video", "Static"],
            "Campaign Concept": ["Creator Demo", "Brand Still"],
        }
    ).to_csv(csv_path, index=False)

    mapping = {
        "Creative Concept": "creative_name",
        "Where it ran": "platform",
        "The Objective": "objective",
        "Total Spent": "spend",
        "Impressions Total": "impressions",
        "People Reached": "reach",
        "Link Clicks": "clicks",
        "3s Video Plays": "vtr_2s",
        "100% Video Completions": "video_views_100",
        "Buying Method": "buying_type",
        "Format Type": "format_raw",
        "Campaign Concept": "concept",
    }

    df_raw, df = load_data(str(csv_path), column_mapping=mapping)

    assert len(df_raw) == 2
    assert set(df_raw["platform"]) == {"Meta", "TikTok"}
    assert set(df["creative_name"]) == {"Pixel Pro Video", "Pixel Static"}
    assert set(df["concept"]) == {"Creator Demo", "Brand Still"}
    assert df["spend"].sum() == 2400
