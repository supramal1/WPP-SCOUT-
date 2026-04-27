import base64
import os
import tempfile
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import uvicorn
import pandas as pd
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool

from src.loader import load_data
from src.scorer import score_creatives, score_raw_variants, OBJECTIVE_METRICS
from src.explainer import generate_explanations, generate_dimension_insights

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Session State ---
# In a production environment, this might be a Redis cache or file-based storage.
# For this implementation, we use a global dictionary.
SESSION_STATE: Dict[str, Any] = {
    "df": None,           # Aggregated creative data
    "df_raw": None,       # Raw variant data
    "explained": None,    # Dataframe with explanations
}

# Create the MCP server
app = Server("creative-analyser")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="ingest_data",
            description="Uploads and analyzes campaign data. Must be called before other query tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_data_base64": {"type": "string", "description": "Base64 encoded Excel/CSV file."},
                    "file_name": {"type": "string", "description": "e.g., 'data.xlsx'"},
                    "min_spend": {"type": "number", "default": 500},
                    "min_reach": {"type": "number", "default": 10000}
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

async def handle_ingest(arguments: dict) -> list[TextContent]:
    file_data_base64 = arguments.get("file_data_base64")
    file_name = arguments.get("file_name", "upload.xlsx")
    min_spend = arguments.get("min_spend", 500)
    min_reach = arguments.get("min_reach", 10000)

    try:
        file_bytes = base64.b64decode(file_data_base64)
    except Exception as e:
        return [TextContent(type="text", text=f"Error decoding base64: {e}")]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / file_name
        tmp_path.write_bytes(file_bytes)
        try:
            df_raw, df = load_data(str(tmp_path))
            df['low_confidence'] = (df['spend'] < float(min_spend)) | (df['reach'] < float(min_reach))
            scored = score_creatives(df)
            explained = generate_explanations(scored)
            
            # Update Session State
            SESSION_STATE["df"] = df
            SESSION_STATE["df_raw"] = score_raw_variants(df_raw)
            SESSION_STATE["explained"] = explained
            
            return [TextContent(type="text", text=f"Successfully analyzed {len(df)} creatives. You can now ask specific questions about the performance.")]
        except Exception as e:
            logger.error(f"Ingest failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Analysis failed: {str(e)}")]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Ingest tools don't need existing data
    if name in ["ingest_data", "analyze_creatives"]:
        return await handle_ingest(arguments)

    # Check if data exists for query tools
    if SESSION_STATE["explained"] is None:
        return [TextContent(type="text", text="No data has been analyzed yet. Please use the 'ingest_data' tool first.")]

    explained = SESSION_STATE["explained"]
    df_raw = SESSION_STATE["df_raw"]

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

        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]

# Standard MCP SSE Transport
sse = SseServerTransport("/messages")

async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await app.run(streams[0], streams[1], app.create_initialization_options())

async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

starlette_app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Expanded MCP server on port {port}")
    uvicorn.run("mcp_server:starlette_app", host="0.0.0.0", port=port)
