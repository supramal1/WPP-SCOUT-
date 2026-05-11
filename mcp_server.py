import base64
import contextlib
import os
import tempfile
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any

import uvicorn
import pandas as pd
from starlette.applications import Starlette
from starlette.routing import Route
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool

from src.loader import load_data
from src.scorer import score_creatives, score_raw_variants, OBJECTIVE_METRICS
from src.explainer import generate_explanations, generate_dimension_insights
from src.data_mapping import create_best_mapping_preview, get_canonical_schema
from src.insights import (
    compare_creatives,
    find_actionable_insights,
    get_budget_reallocation_recommendations,
    get_concept_deep_dive,
    get_concept_rankings,
    get_data_quality_report,
    get_fatigue_risks,
    get_low_confidence_creatives,
    get_score_breakdown,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Session State ---
# In a production environment, this might be a Redis cache or file-based storage.
# For this implementation, we use a global dictionary.
SESSION_STATE: Dict[str, Any] = {
    "df": None,           # Aggregated creative data
    "df_raw": None,       # Raw variant data
    "explained": None,    # Dataframe with explanations
    "mapping_previews": {},  # mapping_id -> preview payload
    "uploads": {},        # upload_id -> chunked upload metadata
    "sessions": {},       # session_id -> analyzed dataframes
    "active_session_id": None,
}

ALLOWED_FILE_SUFFIXES = {".csv", ".xls", ".xlsx"}

# Create the MCP server
app = Server("wpp-scout")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ingest_data",
            description="UPLOAD WORKFLOW STEP 5 OF 5: analyze a finalized upload_id. Default remote path is create_file_upload_session -> append_file_upload_chunk -> finalize_file_upload -> preview_data_mapping -> ingest_data. file_path is server-local only; client-local files must be uploaded.",
            inputSchema={
                "type": "object",
                "properties": {
                    "upload_id": {"type": "string", "description": "Preferred remote input. Returned by create_file_upload_session/finalize_file_upload."},
                    "file_data_base64": {"type": "string", "description": "Small-file fallback only. Base64 encoded Excel or CSV file."},
                    "file_name": {"type": "string", "description": "e.g., 'data.xlsx'. Required only when file_data_base64 is used."},
                    "file_path": {"type": "string", "description": "Server-local path only. Do not send a client-local desktop/download path to remote Scout; upload the bytes instead."},
                    "file_handle": {"type": "string", "description": "Alias for upload_id, upload:<id>, file:// path, or server-local path."},
                    "sheet_name": {"type": "string", "description": "Optional Excel sheet to parse, e.g. 'Data Analysis (All)'."},
                    "header_row": {"type": "integer", "description": "Optional 1-based Excel header row, e.g. 6 for row 6."},
                    "min_spend": {"type": "number", "default": 500},
                    "min_reach": {"type": "number", "default": 10000},
                    "mapping_id": {"type": "string", "description": "Mapping preview ID returned by preview_data_mapping."},
                    "column_mapping": {
                        "type": "object",
                        "description": "Explicit mapping from source column names to WPP Scout canonical fields.",
                        "additionalProperties": {"type": "string"}
                    }
                }
            }
        ),
        Tool(
            name="preview_data_mapping",
            description="UPLOAD WORKFLOW STEP 4 OF 5: preview mapping diagnostics for a finalized upload_id before ingest_data. Supports sheet_name and 1-based header_row. file_path is server-local only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "upload_id": {"type": "string", "description": "Preferred remote input from finalize_file_upload."},
                    "file_data_base64": {"type": "string", "description": "Small-file fallback only. Base64 encoded Excel or CSV file."},
                    "file_name": {"type": "string", "description": "e.g., 'planner_export.xlsx'. Required only when file_data_base64 is used."},
                    "file_path": {"type": "string", "description": "Server-local path only. Client-local files must be uploaded."},
                    "file_handle": {"type": "string", "description": "Alias for upload_id, upload:<id>, file:// path, or server-local path."},
                    "sheet_name": {"type": "string", "description": "Optional Excel sheet to parse, e.g. 'Data Analysis (All)'."},
                    "header_row": {"type": "integer", "description": "Optional 1-based Excel header row, e.g. 6 for row 6."},
                }
            }
        ),
        Tool(
            name="create_file_upload_session",
            description="UPLOAD WORKFLOW STEP 1 OF 5: start remote upload for CSV/XLS/XLSX. Then call append_file_upload_chunk, finalize_file_upload, preview_data_mapping, ingest_data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "description": "Original file name, e.g. campaign.xlsx."},
                    "mime_type": {"type": "string", "description": "Optional source MIME type for diagnostics."},
                    "total_size": {"type": "integer", "description": "Optional expected decoded file size; alias of expected_size_bytes."},
                    "expected_size_bytes": {"type": "integer", "description": "Optional expected decoded file size."},
                    "expected_chunks": {"type": "integer", "description": "Optional expected chunk count."},
                },
                "required": ["file_name"],
            },
        ),
        Tool(
            name="append_file_upload_chunk",
            description="UPLOAD WORKFLOW STEP 2 OF 5: append one base64 chunk to an upload session. Then call finalize_file_upload, preview_data_mapping, ingest_data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "upload_id": {"type": "string"},
                    "chunk_data_base64": {"type": "string", "description": "Canonical base64 chunk field."},
                    "data_base64": {"type": "string", "description": "Backward-compatible alias for chunk_data_base64."},
                    "chunk_index": {"type": "integer", "description": "Optional zero-based chunk index for diagnostics."},
                },
                "required": ["upload_id"],
            },
        ),
        Tool(
            name="finalize_file_upload",
            description="UPLOAD WORKFLOW STEP 3 OF 5: decode and finalize chunks. Then call preview_data_mapping with upload_id, then ingest_data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "upload_id": {"type": "string"},
                },
                "required": ["upload_id"],
            },
        ),
        Tool(
            name="get_canonical_schema",
            description="Returns WPP Scout's canonical campaign schema, required fields, outcome fields, custom performance_score field, common aliases, and upload-first workflow guidance.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="analyze_creatives",
            description="Alias for ingest_data (legacy support).",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_data_base64": {"type": "string"},
                    "file_name": {"type": "string"},
                    "file_path": {"type": "string"},
                    "file_handle": {"type": "string"},
                    "upload_id": {"type": "string"},
                    "sheet_name": {"type": "string"},
                    "header_row": {"type": "integer"},
                }
            }
        ),
        Tool(
            name="rank_creatives",
            description="Post-ingest analysis query. Rank creatives or grouped cohorts by any numeric metric such as composite_score, spend, reach, vtr_2s, engagement_rate, ctr, or workbook-provided performance_score.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "metric": {"type": "string", "default": "composite_score"},
                    "group_by": {"type": "string", "description": "Optional grouping field, e.g. creative_name, concept, platform, objective, format_canonical, placement_canonical, asset_type_canonical, os_target."},
                    "top_n": {"type": "integer", "default": 10},
                    "bottom_n": {"type": "integer", "default": 10},
                    "min_spend": {"type": "number", "default": 0},
                    "platform": {"type": "string"},
                    "objective": {"type": "string"},
                    "include_low_confidence": {"type": "boolean", "default": True},
                },
            },
        ),
        Tool(
            name="get_top_performers",
            description="Returns the top N high-performing creatives.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                    "platform": {"type": "string", "enum": ["Meta", "TikTok", "All"], "default": "All"},
                    "objective": {"type": "string", "description": "Filter by objective (e.g., Awareness, Traffic)"}
                }
            }
        ),
        Tool(
            name="get_bottom_performers",
            description="Returns underperforming creatives that may need pausing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                    "platform": {"type": "string", "enum": ["Meta", "TikTok", "All"], "default": "All"}
                }
            }
        ),
        Tool(
            name="get_top_concepts",
            description="Returns top creative concepts, rolling up duplicate creative/placement rows into concept-level performance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                    "platform": {"type": "string", "enum": ["Meta", "TikTok", "All"], "default": "All"},
                    "objective": {"type": "string", "description": "Optional objective filter."},
                    "include_low_confidence": {"type": "boolean", "default": False}
                }
            }
        ),
        Tool(
            name="get_bottom_concepts",
            description="Returns weakest creative concepts, rolling up duplicate creative/placement rows into concept-level performance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                    "platform": {"type": "string", "enum": ["Meta", "TikTok", "All"], "default": "All"},
                    "objective": {"type": "string", "description": "Optional objective filter."},
                    "include_low_confidence": {"type": "boolean", "default": False}
                }
            }
        ),
        Tool(
            name="get_concept_deep_dive",
            description="Explains one creative concept at both concept level and placement/row level, so agents can separate idea performance from placement execution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "concept": {"type": "string", "description": "Exact or partial concept name."},
                    "include_low_confidence": {"type": "boolean", "default": True}
                },
                "required": ["concept"]
            }
        ),
        Tool(
            name="get_creative_deep_dive",
            description="Provides a detailed analysis of a specific creative by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "creative_name": {"type": "string", "description": "The exact or partial name of the creative."}
                },
                "required": ["creative_name"]
            }
        ),
        Tool(
            name="summarize_campaign_trends",
            description="Returns high-level wins and dimensional learnings (e.g., Creator vs Brand performance).",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_action_plan",
            description="Returns a prioritized list of ads to Scale Up or Pause.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="explain_scoring_methodology",
            description="Explains how creatives are scored for a specific campaign objective.",
            inputSchema={
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "e.g., Awareness, Video Views, Traffic"}
                },
                "required": ["objective"]
            }
        ),
        Tool(
            name="compare_dimensions",
            description="Compares performance across cohorts like OS, Asset Type, or Platform.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dimension": {"type": "string", "enum": ["os_target", "asset_type_canonical", "platform", "format_canonical"]}
                },
                "required": ["dimension"]
            }
        ),
        Tool(
            name="get_objective_format_matrix",
            description="Shows which creative formats perform best for each campaign objective.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="search_by_objective",
            description="Ranks creatives specifically for a chosen business goal.",
            inputSchema={
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "e.g., Traffic, Sales, Awareness"}
                },
                "required": ["objective"]
            }
        ),
        Tool(
            name="get_data_quality_report",
            description="Returns data quality counts, warnings, and validation context for the analyzed campaign data.",
            inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}}}
        ),
        Tool(
            name="get_score_breakdown",
            description="Returns score components and recommendation context for a creative.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "creative_name": {"type": "string"}
                },
                "required": ["creative_name"]
            }
        ),
        Tool(
            name="get_low_confidence_creatives",
            description="Returns creatives that need more spend or reach before conclusions are reliable.",
            inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}, "limit": {"type": "integer", "default": 20}}}
        ),
        Tool(
            name="get_fatigue_risks",
            description="Returns creatives with high frequency that may need refreshing or pausing.",
            inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}, "limit": {"type": "integer", "default": 10}}}
        ),
        Tool(
            name="compare_creatives",
            description="Compares named creatives and identifies the strongest option by composite score.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "creative_names": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["creative_names"]
            }
        ),
        Tool(
            name="get_budget_reallocation_recommendations",
            description="Returns structured candidates to scale up and candidates to review or pause.",
            inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}, "limit": {"type": "integer", "default": 5}}}
        ),
        Tool(
            name="find_actionable_insights",
            description="Returns prioritized campaign actions across scale, pause, fatigue, low-confidence, and data-quality signals.",
            inputSchema={"type": "object", "properties": {"session_id": {"type": "string"}}}
        )
    ]

def _format_creative_list(df: pd.DataFrame) -> list:
    """Helper to format a dataframe of creatives into a clean list for the LLM."""
    items = []
    for _, row in df.iterrows():
        items.append({
            "name": row.get("creative_name"),
            "score": round(row.get("composite_score", 0), 1),
            "tier": row.get("tier"),
            "action": row.get("action"),
            "spend": f"€{row.get('spend', 0):,.2f}",
            "explanation": row.get("explanation")
        })
    return items


def _json_response(payload: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, default=str))]


def _get_session(arguments: dict) -> dict | None:
    session_id = arguments.get("session_id") or SESSION_STATE.get("active_session_id")
    if session_id:
        return SESSION_STATE["sessions"].get(session_id)
    if SESSION_STATE["explained"] is not None:
        return {
            "df": SESSION_STATE["df"],
            "df_raw": SESSION_STATE["df_raw"],
            "explained": SESSION_STATE["explained"],
        }
    return None


def _safe_number(value):
    if isinstance(value, dict):
        return {key: _safe_number(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_number(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def _upload_root() -> Path:
    root = Path(os.environ.get("WPP_SCOUT_UPLOAD_DIR", "/tmp/wpp-scout-uploads"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_file_name(file_name: str) -> str:
    name = Path(file_name or "upload.xlsx").name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_FILE_SUFFIXES:
        raise ValueError(
            "Unsupported file type. Use a .csv, .xls, or .xlsx campaign export."
        )
    return name


def _resolve_upload_path(upload_id: str) -> Path:
    upload = SESSION_STATE.setdefault("uploads", {}).get(upload_id)
    if upload is None:
        raise ValueError(f"Unknown upload_id: {upload_id}")
    if upload.get("status") != "finalized":
        raise ValueError(f"Upload {upload_id} has not been finalized yet.")
    path = Path(upload["file_path"])
    if not path.exists():
        raise ValueError(f"Upload {upload_id} file is no longer available.")
    return path


def _resolve_file_handle(file_handle: str) -> tuple[str | None, str | None]:
    if file_handle.startswith("upload:"):
        return file_handle.split(":", 1)[1], None
    if file_handle in SESSION_STATE.setdefault("uploads", {}):
        return file_handle, None
    if file_handle.startswith("file://"):
        return None, file_handle[7:]
    return None, file_handle


def _resolve_input_file(arguments: dict, tmpdir: str) -> Path:
    upload_id = arguments.get("upload_id")
    file_path = arguments.get("file_path")
    file_handle = arguments.get("file_handle")

    if file_handle and not upload_id and not file_path:
        upload_id, file_path = _resolve_file_handle(file_handle)

    if upload_id:
        return _resolve_upload_path(upload_id)

    if file_path:
        path = Path(file_path).expanduser()
        if path.suffix.lower() not in ALLOWED_FILE_SUFFIXES:
            raise ValueError(
                "Unsupported file type. Use a .csv, .xls, or .xlsx campaign export."
            )
        if not path.exists() or not path.is_file():
            raise ValueError(
                f"This path is local to the client or unavailable to the remote Scout server: {file_path}. "
                "Use file upload/base64/chunked upload for remote MCP."
            )
        return path

    file_data_base64 = arguments.get("file_data_base64")
    if not file_data_base64:
        raise ValueError(
            "Provide one of file_data_base64, upload_id, file_path, or file_handle."
        )

    file_name = _safe_file_name(arguments.get("file_name", "upload.xlsx"))
    try:
        file_bytes = base64.b64decode(file_data_base64, validate=True)
    except Exception as e:
        raise ValueError(f"Error decoding base64: {e}") from e

    tmp_path = Path(tmpdir) / file_name
    tmp_path.write_bytes(file_bytes)
    return tmp_path


async def handle_create_file_upload_session(arguments: dict) -> list[TextContent]:
    try:
        file_name = _safe_file_name(arguments.get("file_name", "upload.xlsx"))
    except ValueError as e:
        return _json_response({"status": "error", "message": str(e)})

    upload_id = str(uuid.uuid4())
    upload_dir = _upload_root() / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    base64_path = upload_dir / f"{file_name}.b64"
    final_path = upload_dir / file_name
    base64_path.write_text("")
    SESSION_STATE.setdefault("uploads", {})[upload_id] = {
        "status": "created",
        "file_name": file_name,
        "mime_type": arguments.get("mime_type"),
        "base64_path": str(base64_path),
        "file_path": str(final_path),
        "chunk_count": 0,
        "received_base64_chars": 0,
        "expected_size_bytes": arguments.get("expected_size_bytes") or arguments.get("total_size"),
        "expected_chunks": arguments.get("expected_chunks"),
    }
    return _json_response(
        {
            "status": "ok",
            "upload_id": upload_id,
            "file_name": file_name,
            "accepted_file_types": sorted(ALLOWED_FILE_SUFFIXES),
            "next_step": "Call append_file_upload_chunk for each base64 chunk, then finalize_file_upload.",
        }
    )


async def handle_append_file_upload_chunk(arguments: dict) -> list[TextContent]:
    upload_id = arguments.get("upload_id")
    chunk = arguments.get("chunk_data_base64") or arguments.get("data_base64") or ""
    upload = SESSION_STATE.setdefault("uploads", {}).get(upload_id)
    if upload is None:
        return _json_response({"status": "error", "message": f"Unknown upload_id: {upload_id}"})
    if upload.get("status") == "finalized":
        return _json_response({"status": "error", "message": f"Upload {upload_id} is already finalized."})
    if not isinstance(chunk, str) or not chunk:
        return _json_response({"status": "error", "message": "chunk_data_base64 is required."})

    with open(upload["base64_path"], "a", encoding="ascii") as handle:
        handle.write(chunk.strip())

    upload["status"] = "uploading"
    upload["chunk_count"] += 1
    upload["received_base64_chars"] += len(chunk.strip())
    upload["last_chunk_index"] = arguments.get("chunk_index")
    return _json_response(
        {
            "status": "ok",
            "upload_id": upload_id,
            "chunk_count": upload["chunk_count"],
            "received_base64_chars": upload["received_base64_chars"],
        }
    )


async def handle_finalize_file_upload(arguments: dict) -> list[TextContent]:
    upload_id = arguments.get("upload_id")
    upload = SESSION_STATE.setdefault("uploads", {}).get(upload_id)
    if upload is None:
        return _json_response({"status": "error", "message": f"Unknown upload_id: {upload_id}"})

    try:
        encoded = Path(upload["base64_path"]).read_text(encoding="ascii")
        file_bytes = base64.b64decode(encoded, validate=True)
        final_path = Path(upload["file_path"])
        final_path.write_bytes(file_bytes)
    except Exception as e:
        upload["status"] = "error"
        upload["error"] = str(e)
        return _json_response({"status": "error", "upload_id": upload_id, "message": f"Error decoding upload: {e}"})

    upload["status"] = "finalized"
    upload["received_bytes"] = len(file_bytes)
    return _json_response(
        {
            "status": "ok",
            "upload_id": upload_id,
            "file_name": upload["file_name"],
            "received_bytes": len(file_bytes),
            "file_handle": f"upload:{upload_id}",
            "next_step": "Pass upload_id to preview_data_mapping or ingest_data.",
        }
    )


async def handle_ingest(arguments: dict) -> list[TextContent]:
    min_spend = arguments.get("min_spend", 500)
    min_reach = arguments.get("min_reach", 10000)
    mapping_id = arguments.get("mapping_id")
    column_mapping = arguments.get("column_mapping")

    if mapping_id:
        preview = SESSION_STATE["mapping_previews"].get(mapping_id)
        if preview is None:
            return [TextContent(type="text", text=f"Unknown mapping_id: {mapping_id}")]
        column_mapping = preview.get("proposed_mapping")

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            tmp_path = _resolve_input_file(arguments, tmpdir)
            df_raw, df = load_data(
                str(tmp_path),
                column_mapping=column_mapping,
                sheet_name=arguments.get("sheet_name"),
                header_row=arguments.get("header_row"),
            )
            df['low_confidence'] = (df['spend'] < float(min_spend)) | (df['reach'] < float(min_reach))
            scored = score_creatives(df)
            explained = generate_explanations(scored)
            df_raw_scored = score_raw_variants(df_raw)
            session_id = arguments.get("session_id") or str(uuid.uuid4())
            
            # Update Session State
            SESSION_STATE["df"] = df
            SESSION_STATE["df_raw"] = df_raw_scored
            SESSION_STATE["explained"] = explained
            SESSION_STATE["active_session_id"] = session_id
            SESSION_STATE["sessions"][session_id] = {
                "df": df,
                "df_raw": df_raw_scored,
                "explained": explained,
            }
            
            return _json_response({
                "status": "ok",
                "message": f"Successfully analyzed {len(df)} creatives. You can now ask specific questions about the performance.",
                "session_id": session_id,
                "creatives_analyzed": int(len(df)),
            })
        except Exception as e:
            logger.error(f"Ingest failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Analysis failed: {str(e)}")]

async def handle_mapping_preview(arguments: dict) -> list[TextContent]:
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            tmp_path = _resolve_input_file(arguments, tmpdir)
            preview = create_best_mapping_preview(
                str(tmp_path),
                sheet_name=arguments.get("sheet_name"),
                header_row=arguments.get("header_row"),
            )
            mapping_id = str(uuid.uuid4())
            preview = {**preview, "mapping_id": mapping_id}
            SESSION_STATE["mapping_previews"][mapping_id] = preview
            return _json_response(preview)
        except Exception as e:
            logger.error(f"Mapping preview failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Mapping preview failed: {str(e)}")]


def handle_rank_creatives(arguments: dict, explained: pd.DataFrame) -> list[TextContent]:
    metric = arguments.get("metric") or "composite_score"
    group_by = arguments.get("group_by")
    top_n = int(arguments.get("top_n", 10))
    bottom_n = int(arguments.get("bottom_n", 10))
    min_spend = float(arguments.get("min_spend", 0))

    if metric not in explained.columns:
        return _json_response(
            {
                "status": "error",
                "message": f"Metric '{metric}' not found.",
                "available_numeric_metrics": sorted(
                    col
                    for col in explained.columns
                    if pd.api.types.is_numeric_dtype(explained[col])
                ),
            }
        )
    if not pd.api.types.is_numeric_dtype(explained[metric]):
        return _json_response(
            {"status": "error", "message": f"Metric '{metric}' is not numeric."}
        )

    ranked = explained.copy()
    if min_spend:
        ranked = ranked[ranked["spend"] >= min_spend]
    if not arguments.get("include_low_confidence", True):
        ranked = ranked[~ranked["low_confidence"]]
    platform = arguments.get("platform")
    if platform and platform != "All":
        ranked = ranked[ranked["platform"] == platform]
    objective = arguments.get("objective")
    if objective:
        ranked = ranked[
            ranked["objective_normalized"].str.contains(objective, case=False, na=False)
        ]

    if group_by:
        if group_by not in ranked.columns:
            return _json_response(
                {"status": "error", "message": f"group_by '{group_by}' not found."}
            )
        grouped = (
            ranked.groupby(group_by, dropna=False)
            .agg(
                **{
                    metric: (metric, "mean"),
                    "spend": ("spend", "sum"),
                    "reach": ("reach", "sum"),
                    "impressions": ("impressions", "sum"),
                    "creative_rows": ("creative_name", "count"),
                    "platforms": ("platform", lambda x: sorted(set(x.dropna()))),
                    "objectives": (
                        "objective_normalized",
                        lambda x: sorted(set(x.dropna())),
                    ),
                }
            )
            .reset_index()
        )
        ranked_output = grouped
    else:
        keep_cols = [
            "creative_name",
            "concept",
            "platform",
            "objective_normalized",
            "format_canonical",
            "placement_canonical",
            "tier",
            "action",
            "spend",
            "reach",
            "impressions",
            "low_confidence",
            metric,
        ]
        ranked_output = ranked[[col for col in keep_cols if col in ranked.columns]]

    top = ranked_output.sort_values(metric, ascending=False).head(top_n)
    bottom = ranked_output.sort_values(metric, ascending=True).head(bottom_n)

    return _json_response(
        {
            "status": "ok",
            "metric": metric,
            "group_by": group_by,
            "filters": {
                "min_spend": min_spend,
                "platform": platform,
                "objective": objective,
                "include_low_confidence": arguments.get(
                    "include_low_confidence", True
                ),
            },
            "row_count": int(len(ranked_output)),
            "top": [
                {key: _safe_number(value) for key, value in row.items()}
                for row in top.to_dict(orient="records")
            ],
            "bottom": [
                {key: _safe_number(value) for key, value in row.items()}
                for row in bottom.to_dict(orient="records")
            ],
        }
    )

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Ingest tools don't need existing data
    if name in ["ingest_data", "analyze_creatives"]:
        return await handle_ingest(arguments)
    if name == "preview_data_mapping":
        return await handle_mapping_preview(arguments)
    if name == "create_file_upload_session":
        return await handle_create_file_upload_session(arguments)
    if name == "append_file_upload_chunk":
        return await handle_append_file_upload_chunk(arguments)
    if name == "finalize_file_upload":
        return await handle_finalize_file_upload(arguments)
    if name == "get_canonical_schema":
        return _json_response(get_canonical_schema())

    # Check if data exists for query tools
    session = _get_session(arguments)
    if session is None:
        return [TextContent(type="text", text="No data has been analyzed yet. Please use the 'ingest_data' tool first.")]

    explained = session["explained"]
    df_raw = session["df_raw"]

    try:
        if name == "get_top_performers":
            limit = arguments.get("limit", 10)
            platform = arguments.get("platform", "All")
            obj = arguments.get("objective")
            
            filtered = explained[~explained["low_confidence"]]
            if platform != "All":
                filtered = filtered[filtered["platform"] == platform]
            if obj:
                filtered = filtered[filtered["objective_normalized"].str.contains(obj, case=False, na=False)]
            
            top = filtered.sort_values("composite_score", ascending=False).head(limit)
            return [TextContent(type="text", text=json.dumps(_format_creative_list(top), indent=2))]

        elif name == "rank_creatives":
            return handle_rank_creatives(arguments, explained)

        elif name == "get_bottom_performers":
            limit = arguments.get("limit", 10)
            platform = arguments.get("platform", "All")
            
            filtered = explained[~explained["low_confidence"]]
            if platform != "All":
                filtered = filtered[filtered["platform"] == platform]
            
            bottom = filtered.sort_values("composite_score", ascending=True).head(limit)
            return [TextContent(type="text", text=json.dumps(_format_creative_list(bottom), indent=2))]

        elif name == "get_top_concepts":
            return _json_response(
                get_concept_rankings(
                    explained,
                    limit=arguments.get("limit", 10),
                    platform=arguments.get("platform", "All"),
                    objective=arguments.get("objective"),
                    sort="top",
                    include_low_confidence=arguments.get("include_low_confidence", False),
                )
            )

        elif name == "get_bottom_concepts":
            return _json_response(
                get_concept_rankings(
                    explained,
                    limit=arguments.get("limit", 10),
                    platform=arguments.get("platform", "All"),
                    objective=arguments.get("objective"),
                    sort="bottom",
                    include_low_confidence=arguments.get("include_low_confidence", False),
                )
            )

        elif name == "get_concept_deep_dive":
            return _json_response(
                get_concept_deep_dive(
                    explained,
                    arguments.get("concept", ""),
                    include_low_confidence=arguments.get("include_low_confidence", True),
                )
            )

        elif name == "get_creative_deep_dive":
            c_name = arguments.get("creative_name", "")
            match = explained[explained["creative_name"].str.contains(c_name, case=False, na=False)]
            
            if match.empty:
                return [TextContent(type="text", text=f"No creative found matching '{c_name}'")]
            
            creative_data = match.iloc[0]
            # Find raw variants to show splits
            variants = df_raw[df_raw["creative_name"] == creative_data["creative_name"]]
            
            splits = []
            for _, v in variants.iterrows():
                splits.append({
                    "platform": v.get("platform"),
                    "os": v.get("os_target"),
                    "placement": v.get("placement_raw"),
                    "spend": f"€{v.get('spend', 0):,.2f}",
                    "vtr": f"{v.get('vtr_2s', 0):.1f}%",
                    "score": v.get("composite_score")
                })

            result = {
                "overview": _format_creative_list(match)[0],
                "detailed_splits": splits
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "summarize_campaign_trends":
            insights = generate_dimension_insights(explained)
            return [TextContent(type="text", text="\n".join([f"• {i}" for i in insights]))]

        elif name == "get_action_plan":
            critical_scale = explained[explained["action"] == "Scale Up"].head(5)
            critical_pause = explained[explained["action"].str.contains("Pause", na=False)].head(5)
            
            result = {
                "top_scaling_opportunities": _format_creative_list(critical_scale),
                "top_pausing_recommendations": _format_creative_list(critical_pause)
            }
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "explain_scoring_methodology":
            obj = arguments.get("objective", "Awareness")
            metrics = OBJECTIVE_METRICS.get(obj, OBJECTIVE_METRICS.get("Awareness"))
            
            explanation = f"For {obj} campaigns, we score creatives based on:\n"
            explanation += f"1. Primary Metric (50%): {', '.join(metrics['primary'])}\n"
            explanation += f"2. Secondary Metrics (25%): {', '.join(metrics['secondary'])}\n"
            explanation += f"3. Cost Efficiency (15%): Based on {metrics['efficiency']}\n"
            explanation += "4. Attention Quality (10%): Based on platform-native hook/hold rates."
            
            return [TextContent(type="text", text=explanation)]

        elif name == "compare_dimensions":
            dim = arguments.get("dimension", "platform")
            if dim not in df_raw.columns:
                return [TextContent(type="text", text=f"Dimension '{dim}' not found in data.")]
            
            comparison = df_raw.groupby(dim).agg({
                "composite_score": "mean",
                "spend": "sum",
                "vtr_2s": "mean",
                "ctr": "mean"
            }).sort_values("composite_score", ascending=False).reset_index()
            
            result = []
            for _, row in comparison.iterrows():
                result.append({
                    dim: row[dim],
                    "avg_score": round(row["composite_score"], 1),
                    "total_spend": f"€{row['spend']:,.2f}",
                    "avg_vtr": f"{row['vtr_2s']:.1f}%",
                    "avg_ctr": f"{row['ctr']:.2f}%"
                })
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "get_objective_format_matrix":
            matrix = explained.groupby(["objective_normalized", "format_canonical"])["composite_score"].mean().unstack().fillna(0)
            # Format matrix for readability
            matrix_dict = matrix.round(1).to_dict(orient="index")
            return [TextContent(type="text", text=json.dumps(matrix_dict, indent=2))]

        elif name == "search_by_objective":
            obj = arguments.get("objective", "")
            filtered = explained[explained["objective_normalized"].str.contains(obj, case=False, na=False)]
            top = filtered.sort_values("composite_score", ascending=False).head(15)
            return [TextContent(type="text", text=json.dumps(_format_creative_list(top), indent=2))]

        elif name == "get_data_quality_report":
            return _json_response(get_data_quality_report(df_raw, explained))

        elif name == "get_score_breakdown":
            return _json_response(get_score_breakdown(explained, arguments.get("creative_name", "")))

        elif name == "get_low_confidence_creatives":
            return _json_response(get_low_confidence_creatives(explained, arguments.get("limit", 20)))

        elif name == "get_fatigue_risks":
            return _json_response(get_fatigue_risks(explained, arguments.get("limit", 10)))

        elif name == "compare_creatives":
            return _json_response(compare_creatives(explained, arguments.get("creative_names", [])))

        elif name == "get_budget_reallocation_recommendations":
            return _json_response(get_budget_reallocation_recommendations(explained, arguments.get("limit", 5)))

        elif name == "find_actionable_insights":
            return _json_response(find_actionable_insights(df_raw, explained))

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

# Standard MCP SSE Transport
sse = SseServerTransport("/messages")
streamable_http = StreamableHTTPSessionManager(app=app)

class SseEndpoint:
    async def __call__(self, scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())


class MessageEndpoint:
    async def __call__(self, scope, receive, send):
        await sse.handle_post_message(scope, receive, send)


class MergedMcpEndpoint:
    def __init__(self, classic_sse_handler, streamable_http_handler):
        self.classic_sse_handler = classic_sse_handler
        self.streamable_http_handler = streamable_http_handler

    @staticmethod
    def _scope_with_mcp_accept(scope, accept_value: bytes):
        headers = list(scope.get("headers") or [])
        normalized_headers = [
            (name, value) for name, value in headers if name.lower() != b"accept"
        ]
        normalized_headers.append((b"accept", accept_value))
        return {**scope, "headers": normalized_headers}

    @staticmethod
    def _has_explicit_accept(scope, required_types: tuple[bytes, ...]) -> bool:
        headers = dict(scope.get("headers") or [])
        accept = headers.get(b"accept", b"").lower()
        return all(required_type in accept for required_type in required_types)

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers") or [])
        is_streamable_session_get = b"mcp-session-id" in headers
        if scope.get("method") == "GET" and not is_streamable_session_get:
            await self.classic_sse_handler(scope, receive, send)
            return

        if scope.get("method") == "POST" and not self._has_explicit_accept(
            scope, (b"application/json", b"text/event-stream")
        ):
            scope = self._scope_with_mcp_accept(
                scope, b"application/json, text/event-stream"
            )
        elif scope.get("method") == "GET" and is_streamable_session_get and not self._has_explicit_accept(
            scope, (b"text/event-stream",)
        ):
            scope = self._scope_with_mcp_accept(scope, b"text/event-stream")

        await self.streamable_http_handler(scope, receive, send)


class StreamableHttpEndpoint:
    async def __call__(self, scope, receive, send):
        await streamable_http.handle_request(scope, receive, send)


@contextlib.asynccontextmanager
async def lifespan(starlette_app):
    async with streamable_http.run():
        yield


classic_sse_endpoint = SseEndpoint()
streamable_http_endpoint = StreamableHttpEndpoint()

starlette_app = Starlette(
    routes=[
        Route(
            "/sse",
            endpoint=MergedMcpEndpoint(
                classic_sse_handler=classic_sse_endpoint,
                streamable_http_handler=streamable_http_endpoint,
            ),
            methods=["GET", "POST", "DELETE"],
        ),
        Route("/mcp", endpoint=streamable_http_endpoint, methods=["GET", "POST", "DELETE"]),
        Route("/messages", endpoint=MessageEndpoint(), methods=["POST"]),
    ],
    lifespan=lifespan,
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting WPP Scout MCP server on port {port}")
    uvicorn.run("mcp_server:starlette_app", host="0.0.0.0", port=port)
