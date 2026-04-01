import sys
from pathlib import Path

# Add api/ to sys.path so absolute imports (cache, scoring.*, routes.*, models)
# resolve the same way they do on Vercel's @vercel/python runtime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
import openpyxl
import tempfile


@pytest.fixture
def sample_excel_path():
    """Create a minimal Excel file matching the expected Pixel DE format."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for sheet_name, platform, buying_type in [
        ("Data Analysis Paid Meta", "Meta", "Paid"),
        ("Data Analysis Paid TikTok", "TikTok", "Paid"),
    ]:
        ws = wb.create_sheet(sheet_name)
        ws.append(["Report", "", ""])
        ws.append(["Date range", "", ""])
        headers = [
            "Creative Name",
            "Ad name in Platform",
            "Campaign",
            "Platform",
            "Objective",
            "Format",
            "Placement",
            "OS",
            "Targeting Segment",
            "Partner",
            "Concept",
            "Product",
            "Wave",
            "Duration",
            "Impressions",
            "Reach",
            "Frequency",
            "Spends",
            "CPM",
            "Clicks",
            "2s VTR" if platform == "TikTok" else "3s VTR",
            "Video Completion",
            "Shares",
            "Total Engagement",
            "Total Plays",
            "Consolidated_Asset_Key",
        ]
        ws.append(headers)

        rows = [
            [
                f"Creative_A_{platform}",
                f"Ad_A_{platform}_iOS_Feed",
                "Campaign Q2",
                platform,
                "Video Views",
                "Video",
                "Feed",
                "iOS",
                "Broad",
                "BAU",
                "Summer Launch",
                "Pixel 9",
                "Wave 1",
                "15",
                100000,
                50000,
                2.0,
                5000,
                50.0,
                500,
                35.0,
                2000,
                100,
                3000,
                80000,
                f"key_a_{platform.lower()}_ios",
            ],
            [
                f"Creative_A_{platform}",
                f"Ad_A_{platform}_Android_Feed",
                "Campaign Q2",
                platform,
                "Video Views",
                "Video",
                "Feed",
                "Android",
                "Broad",
                "BAU",
                "Summer Launch",
                "Pixel 9",
                "Wave 1",
                "15",
                120000,
                60000,
                2.0,
                6000,
                50.0,
                600,
                32.0,
                1800,
                120,
                3500,
                90000,
                f"key_a_{platform.lower()}_android",
            ],
            [
                f"Creative_B_{platform}",
                f"Ad_B_{platform}_iOS_Stories",
                "Campaign Q2",
                platform,
                "Awareness",
                "Video",
                "Stories",
                "iOS",
                "Interest",
                "Creator",
                "Creator Collab",
                "Pixel 9",
                "Wave 1",
                "30",
                80000,
                40000,
                2.0,
                4000,
                50.0,
                200,
                28.0,
                800,
                50,
                1500,
                60000,
                f"key_b_{platform.lower()}_ios",
            ],
        ]
        for row in rows:
            ws.append(row)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        yield f.name

    Path(f.name).unlink(missing_ok=True)
