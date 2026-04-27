import asyncio
import base64
import io
import json

import pandas as pd

from mcp_server import SESSION_STATE, call_tool, list_tools


MAPPING = {
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


def _xlsx_base64(df: pd.DataFrame) -> str:
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def test_mcp_mapping_preview_and_ingest_with_mapping_id(monkeypatch):
    df = pd.DataFrame(
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
        }
    )
    file_data_base64 = _xlsx_base64(df)
    monkeypatch.setattr("src.llm_mapper.generate_column_mapping", lambda _: MAPPING)
    SESSION_STATE["mapping_previews"] = {}
    SESSION_STATE["explained"] = None

    tools = asyncio.run(list_tools())
    assert "preview_data_mapping" in {tool.name for tool in tools}

    preview_response = asyncio.run(
        call_tool(
            "preview_data_mapping",
            {
                "file_data_base64": file_data_base64,
                "file_name": "planner_export.xlsx",
            },
        )
    )
    preview = json.loads(preview_response[0].text)

    assert preview["mapping_id"]
    assert preview["ready_to_ingest"] is True
    assert preview["proposed_mapping"]["Creative Concept"] == "creative_name"

    ingest_response = asyncio.run(
        call_tool(
            "ingest_data",
            {
                "file_data_base64": file_data_base64,
                "file_name": "planner_export.xlsx",
                "mapping_id": preview["mapping_id"],
            },
        )
    )

    assert "Successfully analyzed 2 creatives" in ingest_response[0].text
    ingest_payload = json.loads(ingest_response[0].text)
    session_id = ingest_payload["session_id"]
    assert SESSION_STATE["explained"] is not None

    quality_response = asyncio.run(
        call_tool("get_data_quality_report", {"session_id": session_id})
    )
    quality = json.loads(quality_response[0].text)
    assert quality["status"] == "ok"
    assert quality["data"]["scored_creatives"] == 2

    breakdown_response = asyncio.run(
        call_tool(
            "get_score_breakdown",
            {"session_id": session_id, "creative_name": "Pixel Pro Video"},
        )
    )
    breakdown = json.loads(breakdown_response[0].text)
    assert breakdown["data"]["creative_name"] == "Pixel Pro Video"
