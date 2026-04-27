import asyncio
import json

import pandas as pd

from mcp_server import SESSION_STATE, call_tool, list_tools


def _concept_scored_df():
    return pd.DataFrame(
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


def test_mcp_exposes_concept_level_tools():
    tools = asyncio.run(list_tools())
    names = {tool.name for tool in tools}

    assert "get_top_concepts" in names
    assert "get_bottom_concepts" in names
    assert "get_concept_deep_dive" in names


def test_mcp_concept_deep_dive_returns_rollup_and_placement_level_context():
    session_id = "concept-session"
    scored = _concept_scored_df()
    SESSION_STATE["sessions"][session_id] = {
        "df": scored,
        "df_raw": scored,
        "explained": scored,
    }
    SESSION_STATE["active_session_id"] = session_id

    ranking_response = asyncio.run(
        call_tool("get_top_concepts", {"session_id": session_id, "limit": 1})
    )
    ranking = json.loads(ranking_response[0].text)
    assert ranking["data"][0]["concept"] == "Creator Demo"
    assert ranking["data"][0]["composite_score"] == 60.0

    deep_dive_response = asyncio.run(
        call_tool(
            "get_concept_deep_dive",
            {"session_id": session_id, "concept": "Creator Demo"},
        )
    )
    deep_dive = json.loads(deep_dive_response[0].text)

    assert deep_dive["status"] == "ok"
    assert deep_dive["data"]["rollup"]["concept"] == "Creator Demo"
    assert len(deep_dive["data"]["creative_rows"]) == 2
    assert "concept_level" in deep_dive["data"]["interpretation"]
    assert "placement_level" in deep_dive["data"]["interpretation"]
