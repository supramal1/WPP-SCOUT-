import json
import logging
from typing import Dict
import pandas as pd
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Define the target schema fields we want the LLM to map to.
TARGET_FIELDS = {
    "ad_name_raw": "The raw name of the ad variant.",
    "creative_name": "The overarching creative concept name.",
    "platform": "The platform the ad ran on (e.g., Meta, TikTok).",
    "format_raw": "The ad format (e.g., Video, Static, Motion).",
    "placement_raw": "Where the ad appeared (e.g., In-Feed, Stories).",
    "campaign_raw": "The campaign name.",
    "objective": "The campaign objective (e.g., Awareness, Video Views, Conversions).",
    "buying_type": "The buying type: typically 'Paid' or 'Boosting'.",
    "reach": "Unique users reached (numeric).",
    "impressions": "Total ad impressions (numeric).",
    "frequency": "Average frequency of exposure.",
    "spend": "Total amount spent / cost (numeric).",
    "cpm": "Cost per 1000 impressions (numeric).",
    "clicks": "Total clicks (numeric).",
    "vtr_2s": "Hook rate or 2-second/3-second video plays (numeric).",
    "video_views_100": "100% video completions (numeric).",
    "shares": "Total shares (numeric).",
    "engagements": "Total engagements/interactions (numeric).",
    "duration_s": "Duration of the video asset in seconds.",
    "asset_type_raw": "Granular asset type (e.g., BAU, Creator, Partner).",
    "os_target": "Operating system targeted (e.g., iOS, Android, All).",
    "audience_segment": "Audience or targeting segment.",
    "performance_score": "Workbook-provided score or performance index to preserve alongside Scout's composite_score.",
}

# Provide few-shot examples of common column renames
FEW_SHOT_EXAMPLES = """
Example 1:
Input columns: ["Campaign Name", "Ad Set Name", "Ad Name", "Cost", "Imps", "Unique Reach", "Link Clicks", "3s video views", "Video completes", "Platform", "Objective"]
Mapping: {
    "Campaign Name": "campaign_raw",
    "Ad Name": "ad_name_raw",
    "Cost": "spend",
    "Imps": "impressions",
    "Unique Reach": "reach",
    "Link Clicks": "clicks",
    "3s video views": "vtr_2s",
    "Video completes": "video_views_100",
    "Platform": "platform",
    "Objective": "objective"
}

Example 2:
Input columns: ["Creative ID", "Creative Name", "Network", "Spend (€)", "Impressions", "Clicks", "Cost per Mille", "Total Engagements", "Shares", "2-second video plays", "100% video plays"]
Mapping: {
    "Creative Name": "creative_name",
    "Network": "platform",
    "Spend (€)": "spend",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Cost per Mille": "cpm",
    "Total Engagements": "engagements",
    "Shares": "shares",
    "2-second video plays": "vtr_2s",
    "100% video plays": "video_views_100"
}
"""

class ColumnMapping(BaseModel):
    mapping: dict[str, str] = Field(
        description="A dictionary mapping the original column names to the target schema names. Use null or omit if there is no clear mapping."
    )

def generate_column_mapping(df: pd.DataFrame, target_fields: Dict[str, str] = TARGET_FIELDS) -> Dict[str, str]:
    """Use Vertex AI (Gemini) to generate a column mapping for an unstructured DataFrame."""
    
    # We just need the first few rows to give the model context about the data types
    sample_df = df.head(5)
    
    columns_list = list(df.columns)
    data_sample = sample_df.to_dict(orient="records")
    
    prompt = f"""
    You are an expert data engineer analyzing social media campaign performance data.
    Your task is to map the unstructured input column names to a standard, canonical schema.
    
    TARGET SCHEMA (Keys you must map to):
    {json.dumps(target_fields, indent=2)}
    
    FEW-SHOT EXAMPLES:
    {FEW_SHOT_EXAMPLES}
    
    INPUT DATA TO MAP:
    Original Columns: {json.dumps(columns_list)}
    Data Sample (first 5 rows): {json.dumps(data_sample, default=str)}
    
    Instructions:
    Return ONLY a valid JSON object mapping the original column names to the target schema keys.
    If a column does not logically map to any target schema key, do not include it in the mapping.
    Do not hallucinate keys that are not in the TARGET SCHEMA.
    """
    
    try:
        # Uses Application Default Credentials (ADC) in GCP for Vertex AI
        client = genai.Client(vertexai=True)
        
        logger.info(f"Requesting LLM mapping for columns: {columns_list}")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0
            ),
        )
        
        result = response.text
        if not result:
            raise ValueError("Gemini returned an empty mapping response")

        mapping = json.loads(result)
            
        # Filter out invalid target keys and ensure uniqueness
        valid_mapping = {}
        seen_targets = set()
        for k, v in mapping.items():
            if v in target_fields.keys() and v not in seen_targets:
                valid_mapping[k] = v
                seen_targets.add(v)
                
        logger.info(f"LLM produced mapping: {valid_mapping}")
        return valid_mapping
        
    except Exception as e:
        logger.error(f"Failed to generate LLM mapping: {e}. Falling back to heuristic mapping.")
        
        # Simple heuristic fallback
        heuristic_mapping = {}
        target_keys = list(target_fields.keys())
        seen_targets = set()
        
        # Common patterns for mapping
        patterns = {
            "spend": ["spend", "spent", "cost", "amount", "budget"],
            "impressions": ["impression", "impressions", "imps", "served", "shown"],
            "reach": ["reach", "unique"],
            "clicks": ["click"],
            "video_views_100": ["complete", "completion", "100%", "finish"],
            "vtr_2s": ["2s", "3s", "hook", "video play", "video plays", "views"],
            "creative_name": ["creative", "concept", "ad name"],
            "platform": ["platform", "network", "where"],
            "objective": ["objective", "goal"],
            "buying_type": ["buying", "method", "type"],
            "format_raw": ["format"],
            "os_target": ["os", "operating"],
            "cpm": ["cpm"],
            "engagements": ["engagement", "interaction"],
            "shares": ["share"],
            "performance_score": ["score", "performance index", "efficiency index"],
        }
        
        for col in columns_list:
            col_lower = col.lower()
            for target_key, keywords in patterns.items():
                if target_key not in seen_targets and any(kw in col_lower for kw in keywords):
                    heuristic_mapping[col] = target_key
                    seen_targets.add(target_key)
                    break
        
        logger.info(f"Heuristic produced mapping: {heuristic_mapping}")
        return heuristic_mapping

def apply_llm_mapping(df: pd.DataFrame) -> pd.DataFrame:
    """Detect columns, get mapping from LLM, and rename them to the canonical schema."""
    mapping = generate_column_mapping(df)
    if mapping:
        df_mapped = df.rename(columns=mapping)
        return df_mapped
    return df
