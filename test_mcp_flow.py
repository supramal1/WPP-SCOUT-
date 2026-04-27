import asyncio
import base64
import json
import tempfile
from pathlib import Path

import pandas as pd

from mcp_server import call_tool


SMOKE_MAPPING = {
    "Creative Concept": "creative_name",
    "Where it ran": "platform",
    "The Objective": "objective",
    "Total Spent": "spend",
    "Impressions Total": "impressions",
    "People Reached": "reach",
    "Link Clicks": "clicks",
    "Hook Rate": "vtr_2s",
    "100% Video Completions": "video_views_100",
    "Buying Method": "buying_type",
    "Format Type": "format_raw",
    "Placement": "placement_raw",
    "Total Engagements": "engagements",
    "Shares": "shares",
}


def _content_json(response):
    return json.loads(response[0].text)


async def smoke_mcp_flow():
    df = pd.DataFrame(
        {
            "Creative Concept": ["Pixel Pro Video", "Pixel Standard Static"],
            "Where it ran": ["TikTok", "Meta"],
            "The Objective": ["Video Views", "Awareness"],
            "Total Spent": [1500, 800],
            "Impressions Total": [100000, 50000],
            "People Reached": [80000, 45000],
            "Link Clicks": [500, 100],
            "Hook Rate": [24.5, 0],
            "100% Video Completions": [1800, 0],
            "Buying Method": ["Paid", "Paid"],
            "Format Type": ["Video", "Static"],
            "Placement": ["In Feed", "Feed"],
            "Total Engagements": [3200, 450],
            "Shares": [120, 12],
        }
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "smoke_campaign.csv"
        df.to_csv(csv_path, index=False)
        b64_data = base64.b64encode(csv_path.read_bytes()).decode("utf-8")

    ingest = _content_json(
        await call_tool(
            "ingest_data",
            {
                "file_data_base64": b64_data,
                "file_name": "smoke_campaign.csv",
                "column_mapping": SMOKE_MAPPING,
            },
        )
    )
    assert ingest["status"] == "ok", ingest
    session_id = ingest["session_id"]

    quality = _content_json(
        await call_tool("get_data_quality_report", {"session_id": session_id})
    )
    assert quality["status"] == "ok", quality
    assert quality["data"]["raw_rows"] == 2, quality

    insights = _content_json(
        await call_tool("find_actionable_insights", {"session_id": session_id})
    )
    assert insights["status"] == "ok", insights

    print(
        "MCP smoke passed:",
        f"{ingest['creatives_analyzed']} creatives,",
        f"{len(insights['data']['priority_actions'])} priority action(s)",
    )


if __name__ == "__main__":
    asyncio.run(smoke_mcp_flow())
