import asyncio
import base64
import io
import json
from pathlib import Path

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


def _write_xlsx(path: Path, df: pd.DataFrame) -> None:
    df.to_excel(path, index=False, engine="openpyxl")


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
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


def _standard_sheet_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Creative Name": ["Creative A", "Creative B", "Creative C"],
            "Platform": ["Meta", "Meta", "TikTok"],
            "Objective": ["Awareness", "Awareness", "Video Views"],
            "Format": ["Video", "Video", "Video"],
            "Placement": ["Feed", "Feed", "In Feed"],
            "Campaign": ["Campaign 1", "Campaign 1", "Campaign 2"],
            "Reach": [20000, 25000, 30000],
            "Impressions": [30000, 40000, 70000],
            "Spends": [1000, 1200, 1500],
            "3s VTR": [10.0, 20.0, 5.0],
            "2s VTR": [0.0, 0.0, 25.0],
            "Video Completion": [300, 800, 1200],
            "Total Engagement": [100, 300, 400],
            "Creative Efficiency Index": [44.0, 91.0, 72.0],
            "Concept": ["Concept A", "Concept B", "Concept C"],
        }
    )


def _write_offset_sheet(path: Path, df: pd.DataFrame) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(
            writer,
            sheet_name="Data Analysis (All)",
            startrow=5,
            index=False,
        )


def test_mcp_mapping_preview_and_ingest_with_mapping_id(monkeypatch):
    df = _sample_df()
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
    assert preview["canonical_schema"]["required_fields"] == [
        "creative_name",
        "platform",
        "objective",
        "spend",
        "impressions",
    ]
    assert {
        "source_column",
        "canonical_field",
        "description",
        "confidence",
        "sample_values",
    }.issubset(preview["mapping_diagnostics"][0])

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


def test_mcp_ingest_accepts_server_file_path(tmp_path):
    df = _sample_df()
    file_path = tmp_path / "planner_export.xlsx"
    _write_xlsx(file_path, df)
    SESSION_STATE["explained"] = None

    ingest_response = asyncio.run(
        call_tool(
            "ingest_data",
            {
                "file_path": str(file_path),
                "column_mapping": MAPPING,
            },
        )
    )
    ingest = json.loads(ingest_response[0].text)

    assert ingest["status"] == "ok"
    assert ingest["creatives_analyzed"] == 2


def test_mcp_chunked_upload_can_preview_and_ingest(monkeypatch, tmp_path):
    df = _sample_df()
    file_path = tmp_path / "planner_export.xlsx"
    _write_xlsx(file_path, df)
    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    midpoint = len(encoded) // 2
    monkeypatch.setattr("src.llm_mapper.generate_column_mapping", lambda _: MAPPING)
    SESSION_STATE["uploads"] = {}
    SESSION_STATE["mapping_previews"] = {}

    create_response = asyncio.run(
        call_tool(
            "create_file_upload_session",
            {
                "file_name": "planner_export.xlsx",
                "total_size": file_path.stat().st_size,
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        )
    )
    upload = json.loads(create_response[0].text)
    upload_id = upload["upload_id"]

    for index, chunk in enumerate((encoded[:midpoint], encoded[midpoint:])):
        chunk_field = "chunk_data_base64" if index == 0 else "data_base64"
        append_response = asyncio.run(
            call_tool(
                "append_file_upload_chunk",
                {
                    "upload_id": upload_id,
                    chunk_field: chunk,
                    "chunk_index": index,
                },
            )
        )
        assert json.loads(append_response[0].text)["status"] == "ok"

    finalize_response = asyncio.run(
        call_tool("finalize_file_upload", {"upload_id": upload_id})
    )
    finalized = json.loads(finalize_response[0].text)
    assert finalized["status"] == "ok"
    assert finalized["received_bytes"] == file_path.stat().st_size

    preview_response = asyncio.run(
        call_tool("preview_data_mapping", {"upload_id": upload_id})
    )
    preview = json.loads(preview_response[0].text)
    assert preview["ready_to_ingest"] is True
    assert preview["mapping_diagnostics"]

    ingest_response = asyncio.run(
        call_tool(
            "ingest_data",
            {"upload_id": upload_id, "mapping_id": preview["mapping_id"]},
        )
    )
    ingest = json.loads(ingest_response[0].text)
    assert ingest["status"] == "ok"
    assert ingest["creatives_analyzed"] == 2


def test_mcp_preview_upload_without_args_handles_duplicate_headers(tmp_path):
    df = pd.DataFrame(
        [
            ["Creative A", "Meta", "Awareness", 1000, 999, 30000, 20000],
            ["Creative B", "TikTok", "Video Views", 1200, 888, 40000, 25000],
        ],
        columns=[
            "Creative Name",
            "Platform",
            "Objective",
            "Spends",
            "Spends",
            "Impressions",
            "Reach",
        ],
    )
    file_path = tmp_path / "duplicate_headers.xlsx"
    _write_xlsx(file_path, df)
    encoded = base64.b64encode(file_path.read_bytes()).decode("utf-8")
    SESSION_STATE["uploads"] = {}
    SESSION_STATE["mapping_previews"] = {}

    create_response = asyncio.run(
        call_tool(
            "create_file_upload_session",
            {
                "file_name": "duplicate_headers.xlsx",
                "expected_size_bytes": file_path.stat().st_size,
                "expected_chunks": 1,
            },
        )
    )
    upload_id = json.loads(create_response[0].text)["upload_id"]

    append_response = asyncio.run(
        call_tool(
            "append_file_upload_chunk",
            {
                "upload_id": upload_id,
                "chunk_index": 0,
                "chunk_data_base64": encoded,
            },
        )
    )
    assert json.loads(append_response[0].text)["status"] == "ok"
    finalize_response = asyncio.run(call_tool("finalize_file_upload", {"upload_id": upload_id}))
    assert json.loads(finalize_response[0].text)["status"] == "ok"

    preview_response = asyncio.run(call_tool("preview_data_mapping", {"upload_id": upload_id}))
    preview = json.loads(preview_response[0].text)

    assert preview.get("status") != "error"
    assert preview["ready_to_ingest"] is True
    assert preview["sample_normalized_rows"][0]["spend"] == 1000
    spend_diagnostic = next(
        item for item in preview["mapping_diagnostics"] if item["canonical_field"] == "spend"
    )
    assert spend_diagnostic["sample_values"] == ["1000", "1200"]


def test_mcp_chunked_upload_accepts_independently_encoded_padded_chunks(tmp_path):
    file_bytes = b"abcde"
    SESSION_STATE["uploads"] = {}

    create_response = asyncio.run(
        call_tool(
            "create_file_upload_session",
            {
                "file_name": "planner_export.xlsx",
                "expected_size_bytes": len(file_bytes),
                "expected_chunks": 2,
            },
        )
    )
    upload = json.loads(create_response[0].text)
    upload_id = upload["upload_id"]

    chunks = [
        base64.b64encode(file_bytes[:2]).decode("ascii"),
        base64.b64encode(file_bytes[2:]).decode("ascii"),
    ]
    for index, chunk in enumerate(chunks):
        append_response = asyncio.run(
            call_tool(
                "append_file_upload_chunk",
                {
                    "upload_id": upload_id,
                    "chunk_data_base64": chunk,
                    "chunk_index": index,
                },
            )
        )
        assert json.loads(append_response[0].text)["status"] == "ok"

    status_response = asyncio.run(call_tool("get_file_upload_status", {"upload_id": upload_id}))
    status = json.loads(status_response[0].text)
    assert status["status"] == "uploading"
    assert status["chunk_count"] == 2
    assert status["received_bytes"] == len(file_bytes)
    assert status["ready_to_finalize"] is True

    finalize_response = asyncio.run(call_tool("finalize_file_upload", {"upload_id": upload_id}))
    finalized = json.loads(finalize_response[0].text)
    assert finalized["status"] == "ok"
    assert finalized["received_bytes"] == len(file_bytes)


def test_mcp_chunked_upload_is_idempotent_by_chunk_index(tmp_path):
    file_bytes = b"abcdef"
    first_chunk = base64.b64encode(file_bytes[:3]).decode("ascii")
    conflicting_chunk = base64.b64encode(b"xyz").decode("ascii")
    SESSION_STATE["uploads"] = {}

    create_response = asyncio.run(
        call_tool(
            "create_file_upload_session",
            {"file_name": "planner_export.xlsx", "expected_size_bytes": len(file_bytes)},
        )
    )
    upload_id = json.loads(create_response[0].text)["upload_id"]

    first_response = asyncio.run(
        call_tool(
            "append_file_upload_chunk",
            {"upload_id": upload_id, "chunk_index": 0, "chunk_data_base64": first_chunk},
        )
    )
    repeat_response = asyncio.run(
        call_tool(
            "append_file_upload_chunk",
            {"upload_id": upload_id, "chunk_index": 0, "chunk_data_base64": first_chunk},
        )
    )
    conflict_response = asyncio.run(
        call_tool(
            "append_file_upload_chunk",
            {"upload_id": upload_id, "chunk_index": 0, "chunk_data_base64": conflicting_chunk},
        )
    )

    assert json.loads(first_response[0].text)["status"] == "ok"
    repeat = json.loads(repeat_response[0].text)
    conflict = json.loads(conflict_response[0].text)
    assert repeat["status"] == "ok"
    assert repeat["duplicate"] is True
    assert repeat["chunk_count"] == 1
    assert conflict["status"] == "error"
    assert "conflict" in conflict["message"].lower()


def test_mcp_recommends_upload_plan_for_large_files():
    response = asyncio.run(
        call_tool(
            "recommend_upload_plan",
            {"file_name": "campaign.xlsx", "size_bytes": 8_225_731},
        )
    )
    plan = json.loads(response[0].text)

    assert plan["status"] == "ok"
    assert 64 * 1024 <= plan["recommended_raw_chunk_bytes"] <= 128 * 1024
    assert plan["estimated_chunks"] > 1
    assert "create_file_upload_session" in plan["workflow"][0]


def test_mcp_exposes_canonical_schema_tool():
    tools = asyncio.run(list_tools())
    tool_names = {tool.name for tool in tools}
    assert "get_canonical_schema" in tool_names
    assert "get_file_upload_status" in tool_names
    assert "describe_session" in tool_names
    assert "recommend_upload_plan" in tool_names

    schema_response = asyncio.run(call_tool("get_canonical_schema", {}))
    schema = json.loads(schema_response[0].text)

    assert schema["required_fields"] == [
        "creative_name",
        "platform",
        "objective",
        "spend",
        "impressions",
    ]
    assert schema["fields"]["spend"]["required"] is True
    assert schema["fields"]["video_views_100"]["aliases"]
    assert schema["fields"]["performance_score"]["aliases"]


def test_mcp_ingest_accepts_sheet_name_header_row_and_rank_query(tmp_path):
    workbook_path = tmp_path / "offset_workbook.xlsx"
    _write_offset_sheet(workbook_path, _standard_sheet_df())

    ingest_response = asyncio.run(
        call_tool(
            "ingest_data",
            {
                "file_path": str(workbook_path),
                "sheet_name": "Data Analysis (All)",
                "header_row": 6,
            },
        )
    )
    ingest = json.loads(ingest_response[0].text)
    assert ingest["status"] == "ok"
    session_id = ingest["session_id"]

    ranking_response = asyncio.run(
        call_tool(
            "rank_creatives",
            {
                "session_id": session_id,
                "metric": "performance_score",
                "group_by": "concept",
                "top_n": 2,
                "bottom_n": 1,
                "min_spend": 0,
            },
        )
    )
    ranking = json.loads(ranking_response[0].text)

    assert ranking["status"] == "ok"
    assert ranking["metric"] == "performance_score"
    assert ranking["top"][0]["concept"] == "Concept B"
    assert ranking["top"][0]["performance_score"] == 91.0
    assert ranking["bottom"][0]["concept"] == "Concept A"


def test_mcp_rank_creatives_handles_grouped_list_values(tmp_path):
    workbook_path = tmp_path / "multi_platform_group.xlsx"
    df = _standard_sheet_df()
    df.loc[0, "Concept"] = "Shared Concept"
    df.loc[1, "Concept"] = "Shared Concept"
    df.loc[1, "Platform"] = "TikTok"
    _write_offset_sheet(workbook_path, df)

    ingest_response = asyncio.run(
        call_tool(
            "ingest_data",
            {
                "file_path": str(workbook_path),
                "sheet_name": "Data Analysis (All)",
                "header_row": 6,
            },
        )
    )
    ingest = json.loads(ingest_response[0].text)

    ranking_response = asyncio.run(
        call_tool(
            "rank_creatives",
            {
                "session_id": ingest["session_id"],
                "metric": "performance_score",
                "group_by": "concept",
                "top_n": 2,
                "bottom_n": 0,
                "min_spend": 0,
            },
        )
    )
    ranking = json.loads(ranking_response[0].text)

    assert ranking["status"] == "ok"
    shared = next(row for row in ranking["top"] if row["concept"] == "Shared Concept")
    assert shared["platforms"] == ["Meta", "TikTok"]
    assert shared["performance_score"] == 67.5


def test_mcp_rank_creatives_by_spend_without_duplicate_columns(tmp_path):
    workbook_path = tmp_path / "offset_workbook.xlsx"
    _write_offset_sheet(workbook_path, _standard_sheet_df())

    ingest_response = asyncio.run(
        call_tool(
            "ingest_data",
            {
                "file_path": str(workbook_path),
                "sheet_name": "Data Analysis (All)",
                "header_row": 6,
            },
        )
    )
    ingest = json.loads(ingest_response[0].text)

    ranking_response = asyncio.run(
        call_tool(
            "rank_creatives",
            {
                "session_id": ingest["session_id"],
                "metric": "spend",
                "top_n": 3,
                "bottom_n": 1,
                "min_spend": 0,
            },
        )
    )
    ranking = json.loads(ranking_response[0].text)

    assert ranking["status"] == "ok"
    assert ranking["metric"] == "spend"
    assert ranking["top"][0]["creative_name"] == "Creative C"
    assert ranking["top"][0]["spend"] == 1500


def test_mcp_describe_session_reports_metrics_and_distributions(tmp_path):
    workbook_path = tmp_path / "offset_workbook.xlsx"
    _write_offset_sheet(workbook_path, _standard_sheet_df())

    ingest_response = asyncio.run(
        call_tool(
            "ingest_data",
            {
                "file_path": str(workbook_path),
                "sheet_name": "Data Analysis (All)",
                "header_row": 6,
            },
        )
    )
    ingest = json.loads(ingest_response[0].text)

    summary_response = asyncio.run(
        call_tool("describe_session", {"session_id": ingest["session_id"]})
    )
    summary = json.loads(summary_response[0].text)

    assert summary["status"] == "ok"
    assert summary["row_counts"]["scored_creatives"] == 3
    assert "spend" in summary["available_numeric_metrics"]
    assert "performance_score" in summary["available_numeric_metrics"]
    assert summary["platform_distribution"]["Meta"] == 2
    assert summary["objective_distribution"]["Awareness"] == 2
    assert "concept" in summary["available_group_by_fields"]
    assert summary["source"]["file_name"] == "offset_workbook.xlsx"
    assert summary["source"]["sheet_name"] == "Data Analysis (All)"
    assert summary["source"]["header_row"] == 6


def test_mcp_query_tools_warn_or_require_explicit_session(tmp_path):
    workbook_path = tmp_path / "offset_workbook.xlsx"
    _write_offset_sheet(workbook_path, _standard_sheet_df())

    ingest_response = asyncio.run(
        call_tool(
            "ingest_data",
            {
                "file_path": str(workbook_path),
                "sheet_name": "Data Analysis (All)",
                "header_row": 6,
            },
        )
    )
    ingest = json.loads(ingest_response[0].text)

    active_response = asyncio.run(
        call_tool("rank_creatives", {"metric": "spend", "top_n": 1, "bottom_n": 0})
    )
    strict_response = asyncio.run(
        call_tool(
            "rank_creatives",
            {"metric": "spend", "require_session_id": True},
        )
    )
    active = json.loads(active_response[0].text)
    strict = json.loads(strict_response[0].text)

    assert ingest["session_id"]
    assert active["status"] == "ok"
    assert active["session"]["used_active_session"] is True
    assert active["warnings"]
    assert strict["status"] == "error"
    assert "session_id" in strict["message"]


def test_mcp_file_path_error_explains_remote_upload_default():
    response = asyncio.run(
        call_tool(
            "preview_data_mapping",
            {"file_path": "/Users/someone/Desktop/local-only.xlsx"},
        )
    )

    assert "client-local path" in response[0].text
    assert "file_path is server-local only" in response[0].text
    assert "create_file_upload_session" in response[0].text
