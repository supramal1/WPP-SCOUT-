import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def unstructured_sheets_json():
    return {
        "Planner Export": [
            [
                "Creative Concept",
                "Where it ran",
                "The Objective",
                "Total Spent",
                "Impressions Total",
                "People Reached",
                "Link Clicks",
                "3s Video Plays",
                "100% Video Completions",
                "Buying Method",
                "Format Type",
            ],
            [
                "Pixel Pro Video",
                "TikTok",
                "Video Views",
                1500,
                100000,
                80000,
                500,
                20000,
                1000,
                "Paid",
                "Video",
            ],
            [
                "Pixel Static",
                "Meta",
                "Awareness",
                900,
                50000,
                45000,
                100,
                0,
                0,
                "Paid",
                "Static",
            ],
        ]
    }


@pytest.fixture
def planner_mapping():
    return {
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
    }


def test_preview_data_mapping_for_json_sheet_rows(
    client, monkeypatch, unstructured_sheets_json, planner_mapping
):
    monkeypatch.setattr("src.llm_mapper.generate_column_mapping", lambda _: planner_mapping)

    response = client.post(
        "/api/preview-data-mapping",
        json={"sheets": unstructured_sheets_json},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sheet_name"] == "Planner Export"
    assert data["ready_to_ingest"] is True
    assert data["proposed_mapping"]["Creative Concept"] == "creative_name"
    assert data["sample_normalized_rows"][0]["creative_name"] == "Pixel Pro Video"


def test_upload_and_score_accepts_column_mapping_for_unstructured_rows(
    client, unstructured_sheets_json, planner_mapping
):
    response = client.post(
        "/api/upload-and-score",
        json={"sheets": unstructured_sheets_json, "column_mapping": planner_mapping},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["creatives"]) == 2
    assert {creative["creative_name"] for creative in data["creatives"]} == {
        "Pixel Pro Video",
        "Pixel Static",
    }
