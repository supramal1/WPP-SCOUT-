import base64
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
from mcp.types import TextContent, Tool

from src.loader import load_data
from src.scorer import score_creatives, score_raw_variants, OBJECTIVE_METRICS
from src.explainer import generate_explanations, generate_dimension_insights
from src.data_mapping import create_best_mapping_preview
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
    "sessions": {},       # session_id -> analyzed dataframes
    "active_session_id": None,
}

# Create the MCP server
app = Server("wpp-scout")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ingest_data",
            description="Uploads and analyzes campaign data. Use preview_data_mapping first for non-standard exports, then pass mapping_id or column_mapping.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_data_base64": {"type": "string", "description": "Base64 encoded Excel or CSV file."},
                    "file_name": {"type": "string", "description": "e.g., 'data.xlsx'"},
                    "min_spend": {"type": "number", "default": 500},
                    "min_reach": {"type": "number", "default": 10000},
                    "mapping_id": {"type": "string", "description": "Mapping preview ID returned by preview_data_mapping."},
                    "column_mapping": {
                        "type": "object",
                        "description": "Explicit mapping from source column names to WPP Scout canonical fields.",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["file_data_base64", "file_name"]
            }
        ),
        Tool(
            name="preview_data_mapping",
            description="Preview how an uploaded non-standard Excel/CSV export maps to WPP Scout's canonical campaign schema before ingesting.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_data_base64": {"type": "string", "description": "Base64 encoded Excel or CSV file."},
                    "file_name": {"type": "string", "description": "e.g., 'planner_export.xlsx'"},
                },
                "required": ["file_data_base64", "file_name"]
            }
        ),
        Tool(
            name="analyze_creatives",
            description="Alias for ingest_data (legacy support).",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_data_base64": {"type": "string"},
                    "file_name": {"type": "string"}
                },
                "required": ["file_data_base64", "file_name"]
            }
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

async def handle_ingest(arguments: dict) -> list[TextContent]:
    file_data_base64 = arguments.get("file_data_base64")
    file_name = arguments.get("file_name", "upload.xlsx")
    min_spend = arguments.get("min_spend", 500)
    min_reach = arguments.get("min_reach", 10000)
    mapping_id = arguments.get("mapping_id")
    column_mapping = arguments.get("column_mapping")

    if mapping_id:
        preview = SESSION_STATE["mapping_previews"].get(mapping_id)
        if preview is None:
            return [TextContent(type="text", text=f"Unknown mapping_id: {mapping_id}")]
        column_mapping = preview.get("proposed_mapping")

    try:
        file_bytes = base64.b64decode(file_data_base64)
    except Exception as e:
        return [TextContent(type="text", text=f"Error decoding base64: {e}")]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / file_name
        tmp_path.write_bytes(file_bytes)
        try:
            df_raw, df = load_data(str(tmp_path), column_mapping=column_mapping)
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
    file_data_base64 = arguments.get("file_data_base64")
    file_name = arguments.get("file_name", "upload.xlsx")

    try:
        file_bytes = base64.b64decode(file_data_base64)
    except Exception as e:
        return [TextContent(type="text", text=f"Error decoding base64: {e}")]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / file_name
        tmp_path.write_bytes(file_bytes)
        try:
            preview = create_best_mapping_preview(str(tmp_path))
            mapping_id = str(uuid.uuid4())
            preview = {**preview, "mapping_id": mapping_id}
            SESSION_STATE["mapping_previews"][mapping_id] = preview
            return _json_response(preview)
        except Exception as e:
            logger.error(f"Mapping preview failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Mapping preview failed: {str(e)}")]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Ingest tools don't need existing data
    if name in ["ingest_data", "analyze_creatives"]:
        return await handle_ingest(arguments)
    if name == "preview_data_mapping":
        return await handle_mapping_preview(arguments)

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

class SseEndpoint:
    async def __call__(self, scope, receive, send):
        async with sse.connect_sse(scope, receive, send) as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())


class MessageEndpoint:
    async def __call__(self, scope, receive, send):
        await sse.handle_post_message(scope, receive, send)

starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=SseEndpoint()),
        Route("/messages", endpoint=MessageEndpoint(), methods=["POST"]),
    ]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting WPP Scout MCP server on port {port}")
    uvicorn.run("mcp_server:starlette_app", host="0.0.0.0", port=port)
