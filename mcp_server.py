import base64
import contextlib
import hashlib
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
from src.scorer import (
    DEFAULT_RANK_METRIC,
    METHODOLOGY_VERSION,
    OBJECTIVE_METRICS,
    score_creatives,
    score_raw_variants,
)
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
            description="UPLOAD WORKFLOW STEP 5 OF 5: analyze a finalized upload_id and return session_id. Default remote path is recommend_upload_plan -> create_file_upload_session -> append_file_upload_chunk -> get_file_upload_status -> finalize_file_upload -> preview_data_mapping -> ingest_data. file_path is server-local only; client-local files must be uploaded.",
            inputSchema={
                "type": "object",
                "properties": {
                    "upload_id": {"type": "string", "description": "Preferred remote input. Returned by create_file_upload_session/finalize_file_upload."},
                    "file_data_base64": {"type": "string", "description": "Small-file fallback only. Base64 encoded Excel or CSV file."},
                    "file_name": {"type": "string", "description": "e.g., 'data.xlsx'. Required only when file_data_base64 is used."},
                    "file_path": {"type": "string", "description": "Advanced/server-local only. Do not send a client-local desktop/download path to remote Scout; upload the bytes instead."},
                    "file_handle": {"type": "string", "description": "Alias for upload_id, upload:<id>, file:// path, or server-local path."},
                    "sheet_name": {"type": "string", "description": "Optional Excel sheet to parse, e.g. 'Data Analysis (All)'."},
                    "header_row": {"type": "integer", "description": "Optional 1-based Excel header row, e.g. 6 for row 6."},
                    "min_spend": {"type": "number", "default": 500},
                    "min_reach": {"type": "number", "default": 10000},
                    "mapping_id": {"type": "string", "description": "Mapping preview ID returned by preview_data_mapping."},
                    "preserve_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional source columns to retain as metadata_<slug> fields for filtering/grouping when they are outside the canonical schema.",
                    },
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
            description="UPLOAD WORKFLOW STEP 4 OF 5: preview mapping diagnostics for a finalized upload_id before ingest_data. Supports sheet_name, 1-based header_row, and automatic header detection. file_path is server-local only.",
            inputSchema={
                "type": "object",
                "properties": {
                    "upload_id": {"type": "string", "description": "Preferred remote input from finalize_file_upload."},
                    "file_data_base64": {"type": "string", "description": "Small-file fallback only. Base64 encoded Excel or CSV file."},
                    "file_name": {"type": "string", "description": "e.g., 'planner_export.xlsx'. Required only when file_data_base64 is used."},
                    "file_path": {"type": "string", "description": "Advanced/server-local only. Client-local files must be uploaded."},
                    "file_handle": {"type": "string", "description": "Alias for upload_id, upload:<id>, file:// path, or server-local path."},
                    "sheet_name": {"type": "string", "description": "Optional Excel sheet to parse, e.g. 'Data Analysis (All)'."},
                    "header_row": {"type": "integer", "description": "Optional 1-based Excel header row, e.g. 6 for row 6."},
                    "preserve_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional source columns to retain as metadata rather than report as ignored.",
                    },
                }
            }
        ),
        Tool(
            name="create_file_upload_session",
            description="UPLOAD WORKFLOW STEP 1 OF 5: start remote upload for CSV/XLS/XLSX. Use recommend_upload_plan first for large files; then append chunks, check status, finalize, preview, and ingest.",
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
            name="recommend_upload_plan",
            description="Return upload-first guidance for remote agents, including recommended chunk size/count and the canonical chunked-upload workflow.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string"},
                    "size_bytes": {"type": "integer"},
                    "max_raw_chunk_bytes": {"type": "integer", "description": "Optional override; defaults to 98304 bytes."},
                },
            },
        ),
        Tool(
            name="append_file_upload_chunk",
            description="UPLOAD WORKFLOW STEP 2 OF 5: append one base64 chunk. Prefer 64-128 KB raw byte chunks encoded independently. chunk_index retries are idempotent: identical repeats no-op, different repeats conflict.",
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
            name="get_file_upload_status",
            description="Debug a remote upload session. Returns chunk counts/indexes, received chars/decoded bytes, expected size/chunks, storage mode, readiness, and finalization status.",
            inputSchema={
                "type": "object",
                "properties": {"upload_id": {"type": "string"}},
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
                    "preserve_columns": {"type": "array", "items": {"type": "string"}},
                }
            }
        ),
        Tool(
            name="rank_creatives",
            description="Post-ingest analysis query. Defaults to creative_quality_score, the headline creative diagnostic metric. Use combined_scout_score/composite_score for the blended creative + media-efficiency view, or pass any numeric metric such as spend, reach, vtr_2s, engagement_rate, ctr, or workbook-provided performance_score. Pass session_id; omitting it uses active session with a warning unless require_session_id=true.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "metric": {"type": "string", "default": DEFAULT_RANK_METRIC},
                    "group_by": {"type": "string", "description": "Optional grouping field, e.g. creative_name, concept, platform, objective, format_canonical, placement_canonical, asset_type_canonical, os_target."},
                    "top_n": {"type": "integer", "default": 10},
                    "bottom_n": {"type": "integer", "default": 10},
                    "min_spend": {"type": "number", "default": 0},
                    "platform": {"type": "string"},
                    "objective": {"type": "string"},
                    "include_low_confidence": {"type": "boolean", "default": True},
                    "require_session_id": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="describe_session",
            description="Summarize an analyzed session: row counts, available metrics/grouping fields, platform/objective distributions, mapping context, and warnings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "require_session_id": {"type": "boolean", "default": False},
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
    session, _, _ = _resolve_session_context(arguments)
    return session


def _resolve_session_context(arguments: dict) -> tuple[dict | None, str | None, bool]:
    session_id = arguments.get("session_id") or SESSION_STATE.get("active_session_id")
    requested_session_id = arguments.get("session_id")
    if requested_session_id:
        return SESSION_STATE["sessions"].get(requested_session_id), requested_session_id, False
    active_session_id = SESSION_STATE.get("active_session_id")
    if active_session_id:
        return SESSION_STATE["sessions"].get(active_session_id), active_session_id, True
    if SESSION_STATE["explained"] is not None:
        return {
            "df": SESSION_STATE["df"],
            "df_raw": SESSION_STATE["df_raw"],
            "explained": SESSION_STATE["explained"],
            "metadata": {},
        }, None, True
    return None, None, False


def _session_summary_payload(session: dict, session_id: str | None, used_active: bool) -> dict:
    explained = session["explained"]
    return {
        "session_id": session_id,
        "used_active_session": used_active,
        "row_counts": {
            "scored_creatives": int(len(explained)),
            "raw_rows": int(len(session.get("df_raw", []))),
        },
        "source": session.get("metadata", {}).get("source", {}),
    }


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


def _unique_columns(columns: list[str]) -> list[str]:
    seen = set()
    unique = []
    for col in columns:
        if col not in seen:
            unique.append(col)
            seen.add(col)
    return unique


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
                f"This is a client-local path or unavailable server path: {file_path}. "
                "file_path is server-local only. Use create_file_upload_session + append_file_upload_chunk chunks for remote MCP."
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


def _source_metadata(arguments: dict, resolved_path: Path) -> dict:
    upload_id = arguments.get("upload_id")
    file_handle = arguments.get("file_handle")
    if file_handle and not upload_id:
        upload_id, _ = _resolve_file_handle(file_handle)
    upload = SESSION_STATE.setdefault("uploads", {}).get(upload_id) if upload_id else None
    return {
        "file_name": upload.get("file_name") if upload else resolved_path.name,
        "upload_id": upload_id,
        "file_handle": f"upload:{upload_id}" if upload_id else file_handle,
        "file_path_mode": "upload" if upload_id else ("server-local" if arguments.get("file_path") else "inline-base64"),
        "sheet_name": arguments.get("sheet_name"),
        "header_row": arguments.get("header_row"),
    }


async def handle_create_file_upload_session(arguments: dict) -> list[TextContent]:
    try:
        file_name = _safe_file_name(arguments.get("file_name", "upload.xlsx"))
    except ValueError as e:
        return _json_response({"status": "error", "message": str(e)})

    upload_id = str(uuid.uuid4())
    upload_dir = _upload_root() / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    base64_path = upload_dir / f"{file_name}.b64"
    part_path = upload_dir / f"{file_name}.part"
    final_path = upload_dir / file_name
    base64_path.write_text("")
    part_path.write_bytes(b"")
    SESSION_STATE.setdefault("uploads", {})[upload_id] = {
        "status": "created",
        "file_name": file_name,
        "mime_type": arguments.get("mime_type"),
        "base64_path": str(base64_path),
        "part_path": str(part_path),
        "file_path": str(final_path),
        "chunk_count": 0,
        "received_base64_chars": 0,
        "received_bytes": 0,
        "chunk_storage_mode": "decoded_chunks",
        "chunks_by_index": {},
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


def handle_recommend_upload_plan(arguments: dict) -> list[TextContent]:
    file_name = arguments.get("file_name") or "upload.xlsx"
    size_bytes = int(arguments.get("size_bytes") or 0)
    raw_chunk_bytes = int(arguments.get("max_raw_chunk_bytes") or 96 * 1024)
    raw_chunk_bytes = max(64 * 1024, min(raw_chunk_bytes, 128 * 1024))
    estimated_chunks = (size_bytes + raw_chunk_bytes - 1) // raw_chunk_bytes if size_bytes else None
    estimated_base64_chars_per_chunk = ((raw_chunk_bytes + 2) // 3) * 4
    return _json_response(
        {
            "status": "ok",
            "file_name": file_name,
            "size_bytes": size_bytes or None,
            "recommended_raw_chunk_bytes": raw_chunk_bytes,
            "estimated_base64_chars_per_chunk": estimated_base64_chars_per_chunk,
            "estimated_chunks": estimated_chunks,
            "workflow": [
                "create_file_upload_session(file_name, expected_size_bytes, expected_chunks)",
                "append_file_upload_chunk(upload_id, chunk_index, chunk_data_base64) for each chunk",
                "get_file_upload_status(upload_id) to verify received chunks/bytes or retry safely",
                "finalize_file_upload(upload_id)",
                "preview_data_mapping(upload_id, sheet_name/header_row as needed)",
                "ingest_data(upload_id, mapping_id as needed)",
            ],
            "notes": [
                "Prefer independently base64-encoded raw byte chunks of 64-128 KB.",
                "Repeated chunk_index with identical data is accepted as a no-op; different data returns a conflict.",
                "file_path is server-local only. Client-local files must use upload.",
            ],
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

    chunk = chunk.strip()
    chunk_index = arguments.get("chunk_index")
    chunk_hash = hashlib.sha256(chunk.encode("ascii")).hexdigest()
    if chunk_index is not None:
        chunk_key = str(chunk_index)
        existing = upload.setdefault("chunks_by_index", {}).get(chunk_key)
        if existing:
            if existing["sha256"] == chunk_hash:
                return _json_response(
                    {
                        "status": "ok",
                        "upload_id": upload_id,
                        "duplicate": True,
                        "chunk_index": chunk_index,
                        "chunk_count": upload["chunk_count"],
                        "received_base64_chars": upload["received_base64_chars"],
                        "received_bytes": upload.get("received_bytes"),
                        "message": "Chunk already received with identical data; no-op.",
                    }
                )
            return _json_response(
                {
                    "status": "error",
                    "upload_id": upload_id,
                    "chunk_index": chunk_index,
                    "message": "Chunk index conflict: this chunk_index was already received with different data.",
                }
            )

    with open(upload["base64_path"], "a", encoding="ascii") as handle:
        handle.write(chunk)
    try:
        chunk_bytes = base64.b64decode(chunk, validate=True)
        if upload.get("chunk_storage_mode") != "base64_stream":
            with open(upload["part_path"], "ab") as handle:
                handle.write(chunk_bytes)
            upload["received_bytes"] = int(upload.get("received_bytes", 0)) + len(chunk_bytes)
    except Exception:
        upload["chunk_storage_mode"] = "base64_stream"

    upload["status"] = "uploading"
    upload["chunk_count"] += 1
    upload["received_base64_chars"] += len(chunk)
    upload["last_chunk_index"] = chunk_index
    if chunk_index is not None:
        upload.setdefault("chunks_by_index", {})[str(chunk_index)] = {
            "sha256": chunk_hash,
            "base64_chars": len(chunk),
        }
    return _json_response(
        {
            "status": "ok",
            "upload_id": upload_id,
            "chunk_count": upload["chunk_count"],
            "received_base64_chars": upload["received_base64_chars"],
            "received_bytes": upload.get("received_bytes"),
        }
    )


def _upload_status_payload(upload_id: str, upload: dict) -> dict:
    expected_size = upload.get("expected_size_bytes")
    expected_chunks = upload.get("expected_chunks")
    received_bytes = upload.get("received_bytes")
    ready_by_chunks = expected_chunks is None or int(expected_chunks) == int(upload.get("chunk_count", 0))
    ready_by_size = (
        expected_size is None
        or upload.get("chunk_storage_mode") == "base64_stream"
        or received_bytes is None
        or int(expected_size) == int(received_bytes or 0)
    )
    return {
        "status": upload.get("status"),
        "upload_id": upload_id,
        "file_name": upload.get("file_name"),
        "mime_type": upload.get("mime_type"),
        "chunk_count": int(upload.get("chunk_count", 0)),
        "received_base64_chars": int(upload.get("received_base64_chars", 0)),
        "received_bytes": received_bytes,
        "expected_size_bytes": expected_size,
        "expected_chunks": expected_chunks,
        "last_chunk_index": upload.get("last_chunk_index"),
        "received_chunk_indexes": sorted(
            int(index) if str(index).isdigit() else index
            for index in upload.get("chunks_by_index", {})
        ),
        "chunk_storage_mode": upload.get("chunk_storage_mode"),
        "ready_to_finalize": upload.get("status") in {"uploading", "created"} and ready_by_chunks and ready_by_size,
        "finalized": upload.get("status") == "finalized",
        "error": upload.get("error"),
    }


async def handle_get_file_upload_status(arguments: dict) -> list[TextContent]:
    upload_id = arguments.get("upload_id")
    upload = SESSION_STATE.setdefault("uploads", {}).get(upload_id)
    if upload is None:
        return _json_response({"status": "error", "message": f"Unknown upload_id: {upload_id}"})
    return _json_response(_upload_status_payload(upload_id, upload))


async def handle_finalize_file_upload(arguments: dict) -> list[TextContent]:
    upload_id = arguments.get("upload_id")
    upload = SESSION_STATE.setdefault("uploads", {}).get(upload_id)
    if upload is None:
        return _json_response({"status": "error", "message": f"Unknown upload_id: {upload_id}"})

    try:
        part_path = Path(upload.get("part_path", ""))
        if upload.get("chunk_storage_mode") == "decoded_chunks" and part_path.exists():
            file_bytes = part_path.read_bytes()
        else:
            encoded = Path(upload["base64_path"]).read_text(encoding="ascii")
            file_bytes = base64.b64decode(encoded, validate=True)
        expected_size = upload.get("expected_size_bytes")
        if expected_size is not None and int(expected_size) != len(file_bytes):
            raise ValueError(
                f"Decoded upload size {len(file_bytes)} did not match expected_size_bytes {expected_size}."
            )
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
        if not arguments.get("preserve_columns"):
            arguments = {
                **arguments,
                "preserve_columns": preview.get("preserved_custom_columns", []),
            }

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            tmp_path = _resolve_input_file(arguments, tmpdir)
            source = _source_metadata(arguments, tmp_path)
            df_raw, df = load_data(
                str(tmp_path),
                column_mapping=column_mapping,
                sheet_name=arguments.get("sheet_name"),
                header_row=arguments.get("header_row"),
                preserve_columns=arguments.get("preserve_columns"),
            )
            reach_available = df["reach"] > 0
            df["low_confidence"] = (df["spend"] < float(min_spend)) | (
                reach_available & (df["reach"] < float(min_reach))
            )
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
                "metadata": {
                    "mapping_id": mapping_id,
                    "source": source,
                    "sheet_name": arguments.get("sheet_name"),
                    "header_row": arguments.get("header_row"),
                    "preserve_columns": arguments.get("preserve_columns") or [],
                    "preserved_metadata_fields": [
                        col for col in df.columns if col.startswith("metadata_")
                    ],
                    "mapped_fields": column_mapping or {},
                },
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
                preserve_columns=arguments.get("preserve_columns"),
            )
            mapping_id = str(uuid.uuid4())
            preview = {**preview, "mapping_id": mapping_id}
            SESSION_STATE["mapping_previews"][mapping_id] = preview
            return _json_response(preview)
        except Exception as e:
            logger.error(f"Mapping preview failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Mapping preview failed: {str(e)}")]


def handle_rank_creatives(
    arguments: dict,
    explained: pd.DataFrame,
    session_context: dict | None = None,
) -> list[TextContent]:
    metric = arguments.get("metric") or DEFAULT_RANK_METRIC
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
        group_aggs = {
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
        if metric not in group_aggs:
            group_aggs[metric] = (metric, "mean")
        grouped = (
            ranked.groupby(group_by, dropna=False)
            .agg(**group_aggs)
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
            "creative_quality_score",
            "media_efficiency_overlay_score",
            "combined_scout_score",
            "scoring_group",
            "group_size",
            "rank_in_group",
            "youtube_measurement_family",
            "methodology_version",
            "source_grain",
            "directional_only",
            "score_caveats",
            metric,
        ]
        if group_by and group_by in ranked.columns:
            keep_cols.append(group_by)
        ranked_output = ranked[
            _unique_columns([col for col in keep_cols if col in ranked.columns])
        ]

    top = ranked_output.sort_values(metric, ascending=False).head(top_n)
    bottom = ranked_output.sort_values(metric, ascending=True).head(bottom_n)

    warnings = []
    if session_context and session_context.get("used_active_session"):
        warnings.append(
            "session_id was omitted; Scout used the active session. Pass session_id or require_session_id=true for strict agents."
        )

    return _json_response(
        {
            "status": "ok",
            "metric": metric,
            "default_metric": DEFAULT_RANK_METRIC,
            "methodology_version": METHODOLOGY_VERSION,
            "group_by": group_by,
            "session": session_context,
            "warnings": warnings,
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


def handle_describe_session(session: dict) -> list[TextContent]:
    explained = session["explained"]
    df_raw = session["df_raw"]
    metadata = session.get("metadata", {})

    numeric_metrics = sorted(
        col for col in explained.columns if pd.api.types.is_numeric_dtype(explained[col])
    )
    group_fields = sorted(
        col
        for col in explained.columns
        if not pd.api.types.is_numeric_dtype(explained[col])
        or col in {"concept", "platform", "objective_normalized", "format_canonical", "placement_canonical", "asset_type_canonical", "os_target", "rows_rolled_up"}
        or col.startswith("metadata_")
    )

    warnings = []
    low_confidence_count = int(explained.get("low_confidence", pd.Series(dtype=bool)).sum())
    if low_confidence_count:
        warnings.append(f"{low_confidence_count} low-confidence creative(s) need more data.")
    if "group_size" in explained.columns:
        group_size = pd.to_numeric(explained["group_size"], errors="coerce").fillna(0)
        small_cohort_count = int(((group_size > 0) & (group_size < 8)).sum())
        if small_cohort_count:
            warnings.append(
                f"{small_cohort_count} creative(s) are in small scoring cohorts; rankings are directional only."
            )

    return _json_response(
        {
            "status": "ok",
            "methodology_version": METHODOLOGY_VERSION,
            "default_rank_metric": DEFAULT_RANK_METRIC,
            "score_contract": {
                "headline_metric": DEFAULT_RANK_METRIC,
                "combined_metric": "combined_scout_score",
                "legacy_combined_metric": "composite_score",
                "media_efficiency_metric": "media_efficiency_overlay_score",
                "row_metadata": [
                    "methodology_version",
                    "source_grain",
                    "directional_only",
                    "score_caveats",
                    "scoring_group",
                    "group_size",
                    "rank_in_group",
                ],
            },
            "row_counts": {
                "raw_rows": int(len(df_raw)),
                "scored_creatives": int(len(explained)),
            },
            "available_numeric_metrics": numeric_metrics,
            "available_group_by_fields": group_fields,
            "platform_distribution": {
                str(key): int(value)
                for key, value in explained["platform"].value_counts(dropna=False).to_dict().items()
            }
            if "platform" in explained.columns
            else {},
            "objective_distribution": {
                str(key): int(value)
                for key, value in explained["objective_normalized"].value_counts(dropna=False).to_dict().items()
            }
            if "objective_normalized" in explained.columns
            else {},
            "source": metadata.get("source", {}),
            "mapping": metadata,
            "preserved_metadata_fields": metadata.get("preserved_metadata_fields", []),
            "warnings": warnings,
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
    if name == "recommend_upload_plan":
        return handle_recommend_upload_plan(arguments)
    if name == "append_file_upload_chunk":
        return await handle_append_file_upload_chunk(arguments)
    if name == "finalize_file_upload":
        return await handle_finalize_file_upload(arguments)
    if name == "get_file_upload_status":
        return await handle_get_file_upload_status(arguments)
    if name == "get_canonical_schema":
        return _json_response(get_canonical_schema())

    if arguments.get("require_session_id") and not arguments.get("session_id"):
        return _json_response(
            {
                "status": "error",
                "message": "session_id is required when require_session_id=true.",
            }
        )

    # Check if data exists for query tools
    session, resolved_session_id, used_active_session = _resolve_session_context(arguments)
    if session is None:
        return [TextContent(type="text", text="No data has been analyzed yet. Please use the 'ingest_data' tool first.")]
    session_context = _session_summary_payload(
        session,
        resolved_session_id,
        used_active_session,
    )

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
            return handle_rank_creatives(arguments, explained, session_context)

        elif name == "describe_session":
            return handle_describe_session(session)

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
            match = explained[
                explained["creative_name"].str.contains(
                    c_name, case=False, na=False, regex=False
                )
            ]
            
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
