import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np
import re
import warnings

from src.inference import infer_objective_for_dataframe, infer_platform_for_dataframe
from src.xlsx_reader import read_xlsx_sheet_dataframe

logger = logging.getLogger(__name__)


def _metadata_column_name(source_column: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z]+", "_", str(source_column).strip().lower()).strip("_")
    return f"metadata_{slug or 'column'}"


def _has_header_signal(columns) -> bool:
    labels = {str(col).strip().lower().replace("\n", " ") for col in columns}
    return bool(
        labels
        & {
            "creative name",
            "ad name",
            "ad name in platform",
            "platform",
            "objective",
            "spends",
            "spend",
            "impressions",
        }
    )


# =============================================================================
# FORMAT MAPPINGS — Creative asset type, separate from placement
# =============================================================================

FORMAT_MAPPINGS = {
    "Video": [
        "video",
        "video 15s",
        "video 30s",
        "video 60s",
        "video 6s",
        'video 15"',
        'video 30"',
        "video 15sec",
        "video 30sec",
        "video 60sec",
        "video ad",
        "vv",
        "video view",
    ],
    "Motion": [
        "motion",
        "motion graphic",
        "animated",
        "gif",
        "cinemagraph",
        "loop",
        "animated image",
        "motion graphic",
        "animated gif",
    ],
    "Static": [
        "static",
        "static image",
        "image",
        "still",
        "photo",
        "static image",
        "single image",
        "static ad",
        "still image",
        "carousel",
        "static carousel",
        "image carousel",
    ],
}

# Platform-specific placement canonicalization
META_PLACEMENT_MAPPINGS = {
    "Feed": [
        "feed",
        "facebook feed",
        "instagram feed",
        "fb feed",
        "ig feed",
        "meta feed",
    ],
    "Reels": ["reels", "instagram reels", "fb reels", "meta reels", "reels placement"],
    "Stories": [
        "stories",
        "instagram stories",
        "fb stories",
        "meta stories",
        "facebook stories",
    ],
    "Carousel": ["carousel", "carousel placement", "carousel ad"],
    "Explore": ["explore", "instagram explore", "explore placement"],
    "Search": ["search", "search results", "facebook search"],
}

TIKTOK_PLACEMENT_MAPPINGS = {
    "In Feed": [
        "in feed",
        "in-feed",
        "for you feed",
        "fyp",
        "for you page",
        "tiktok feed",
    ],
    "Top Feed": ["top feed", "top of feed", "topfeed"],
    "Top Feed Takeover": [
        "top feed takeover",
        "top feed take over",
        "topfeed takeover",
        "tft",
        "brand takeover",
        "takeover",
    ],
    "TopView": ["topview", "top view", "top-view"],
    "Spark Ads": ["spark ads", "spark", "creator ads", "spark ad"],
    "Hashtag Challenge": [
        "hashtag challenge",
        "challenge",
        "branded hashtag",
        "hashtag",
    ],
}

# Asset type subtype mapping
ASSET_SUBTYPE_MAPPINGS = {
    "BAU": ["bau", "", "n/a", "na", "none", "brand bau", "standard"],
    "Partner": ["partner", "hybrid", "co-branded", "co brand", "co-brand"],
    "Influencer": ["influencer", "creator", "talent", "influencer content"],
    "UGC": ["ugc", "user generated", "user-generated", "user content"],
}

# Objective mapping — remove Reach from Awareness, keep as separate
OBJECTIVE_MAPPINGS = {
    "Awareness": [
        "brand awareness",
        "awareness",
        "brand",
        "aware",
        "brand awareness",
        "video awareness",
        "ad recall",
        "brand recall",
    ],
    "Engagement": [
        "engagement",
        "interaction",
        "video engagement",
        "post engagement",
        "interactions",
        "engagements",
    ],
    "Sales": [
        "conversion",
        "conversions",
        "purchase",
        "lead",
        "sales",
        "catalogue sales",
        "catalog sales",
        "leads",
        "purchases",
        "app installs",
    ],
    "Traffic": [
        "traffic",
        "click",
        "landing page",
        "link click",
        "clicks",
        "link clicks",
        "traffic objective",
    ],
    "Reach": [
        "reach",
        "unique reach",
        "brand reach",
        "reach objective",
        "max reach",
    ],
    "Target Frequency": [
        "frequency",
        "target frequency",
        "frequency capping",
        "freq capping",
        "frequency control",
        "frequency objective",
    ],
    "Video Views": [
        "video view",
        "focused view",
        "thruplay",
        "video views",
        "vv",
        "video views objective",
        "video view objective",
        "views",
    ],
}


def _pick_col(df: pd.DataFrame, candidates: list[str], default=0):
    """Return the first column from candidates that exists in df, else a Series filled with default."""
    for col in candidates:
        if col in df.columns:
            return df[col]
    # Always return a Series so callers can use .astype() etc.
    return pd.Series(default, index=df.index)


def _to_numeric(series: pd.Series, default=0) -> pd.Series:
    """Parse platform-export numeric strings with commas, currency, and percent signs."""
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("£", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("%", "", regex=False)
        .replace({"": default, "nan": default, "None": default, "---": default, "-": default})
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(default)


def _extract_opid(series: pd.Series) -> pd.Series:
    return series.astype(str).str.extract(r"\b(OPID-\d+)\b", expand=False).fillna("")


def _extract_duration_from_text(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.extract(r"(?:^|_|\b)(\d{1,3})s(?:_|$|\b)", expand=False)
        .astype(float)
        .fillna(0.0)
    )


def _normalize_pct(series: pd.Series) -> pd.Series:
    """Ensure a rate metric is in 0-100 range (percentage, not decimal).

    Some platform exports use decimals (0.38), others use percentages (38.0).
    If the median non-zero value is <= 1 we treat it as a decimal and scale up.
    """
    non_zero = series[series > 0]
    if non_zero.empty:
        return series
    if non_zero.median() <= 1.0:
        return series * 100
    return series


def parse_duration(val) -> float:
    """Convert duration string like '15"' or '0:15' to seconds (float)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    s = str(val).strip().replace('"', "").replace("'", "").replace("\u201d", "")
    if not s or s.lower() in ("nan", "na", "n/a", ""):
        return 0.0
    # Handle M:SS format
    if ":" in s:
        parts = s.split(":")
        try:
            return float(parts[0]) * 60 + float(parts[1])
        except (ValueError, IndexError):
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def normalize_platform(val) -> str:
    """Normalise platform labels to canonical platform names."""
    if not isinstance(val, str):
        return "Unknown"
    v = val.strip().upper()
    if v in ("FB", "IG", "FB/IG", "FACEBOOK", "INSTAGRAM", "META"):
        return "Meta"
    if v in ("TIKTOK", "TT"):
        return "TikTok"
    if v in ("YOUTUBE", "YT", "GOOGLE - YOUTUBE", "GOOGLE ADS - YOUTUBE"):
        return "YouTube"
    return val.strip()


def normalize_format(val) -> str:
    """Normalise format to canonical values: Video, Motion, Static."""
    if not isinstance(val, str) or not val.strip():
        return "Unknown"
    v = val.strip().lower()

    for canonical, variations in FORMAT_MAPPINGS.items():
        if v in variations:
            return canonical
    if "video" in v or "trueview" in v or "in-stream" in v or "instream" in v:
        return "Video"
    return "Unknown"


def normalize_placement(val: str, platform: str) -> str:
    """Normalise placement names within platforms.

    Format and Placement are kept separate:
    - Format = creative asset type (Video/Motion/Static)
    - Placement = where the ad ran on platform

    Enhanced mapping to reduce Unknown values using partial matching.
    """
    if not isinstance(val, str) or not val.strip():
        return "Unknown"
    v = val.strip().lower()

    # Platform-specific mapping (exact match)
    if platform == "Meta":
        for canonical, variations in META_PLACEMENT_MAPPINGS.items():
            if v in variations:
                return canonical
    elif platform == "TikTok":
        for canonical, variations in TIKTOK_PLACEMENT_MAPPINGS.items():
            if v in variations:
                return canonical

    # Partial matching for common patterns.
    # TikTok top-of-app placements are checked before the generic "feed"
    # branch so "top feed takeover" / "top view" don't collapse into In Feed.
    if "takeover" in v or "take over" in v:
        return "Top Feed Takeover"
    if "topview" in v or "top view" in v:
        return "TopView"
    if platform == "TikTok" and "top" in v and "feed" in v:
        return "Top Feed"
    if "reel" in v:
        return "Reels"
    if "story" in v or "storie" in v:
        return "Stories"
    if "feed" in v or "in feed" in v or "in-feed" in v:
        return "Feed" if platform == "Meta" else "In Feed"
    if "explore" in v:
        return "Explore"
    if "search" in v:
        return "Search"
    if "carousel" in v:
        return "Carousel"
    if "spark" in v:
        return "Spark Ads"
    if "hashtag" in v or "challenge" in v:
        return "Hashtag Challenge"

    return "Unknown"


# OS canonical mapping
OS_MAPPINGS = {
    "iOS": [
        "ios",
        "iphone",
        "apple",
        "ipad",
        "i-os",
        "io.s",
        "ipod",
        "ipados",
        "ipadOs",
        "macos",
        "mac os",
    ],
    "Android": [
        "android",
        "google",
        "samsung",
        "pixel",
        "droid",
        "andr oid",
        "huawei",
        "xiaomi",
        "oppo",
        "vivo",
        "oneplus",
        "realme",
        "motorola",
        "lg",
        "sony",
        "nokia",
        "honor",
        "zte",
        "redmi",
        "poco",
        "nothing",
        "google pixel",
        "samsung galaxy",
        "galaxy",
    ],
    "Desktop": [
        "desktop",
        "pc",
        "mac",
        "windows",
        "computer",
        "laptop",
        "web",
        "browser",
        "chromebook",
        "linux",
        "ubuntu",
        "chrome os",
        "chromeos",
        "win",
        "win10",
        "win11",
        "macos",
        "osx",
        "os x",
    ],
    "Other": ["other", "unknown", "na", "n/a", "none", ""],
}


def normalize_os(val) -> str:
    """Normalize OS values to canonical: iOS, Android, Desktop, Other, All.

    Handles case variations and common misspellings.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "All"
    v = str(val).strip().lower()

    if not v or v in ("all", "nan", "none", "n/a", "na", ""):
        return "All"

    for canonical, variations in OS_MAPPINGS.items():
        if v in variations:
            return canonical
        # Partial match for compound values
        for var in variations:
            if var and var in v:
                return canonical

    logger.warning("Unrecognized OS value falling through to 'All': %r", val)
    return "All"


def normalize_asset_type_canonical(val) -> str:
    """Map to canonical: Brand or Creator."""
    v = str(val).strip().upper() if isinstance(val, str) and val else ""
    if v in (
        "BAU",
        "BRAND",
        "N/A",
        "NA",
        "NONE",
        "",
        "STANDARD",
        "BRANDED",
        "BRAND CONTENT",
        "BRAND ASSET",
        "BRAND VIDEO",
        "BRAND CREATIVE",
        "ORIGINAL",
        "IN-HOUSE",
        "INHOUSE",
        "IN HOUSE",
        "OWNED",
        "DIRECT",
        "INTERNAL",
        "STUDIO",
        "AGENCY",
        "STATIC",
        "VIDEO",
        "MOTION",
        "ANIMATION",
        "PRODUCT",
        "HERO",
        "MASTER",
        "NAN",
        "PARTNER",
        "HYBRID",
        "CO-BRANDED",
        "CO BRAND",
        "CO-BRAND",
        "COBRAND",
        "COBRANDED",
        "COLLAB",
        "COLLABORATION",
        "PARTNERSHIP",
        "AFFILIATE",
        "SPONSORED",
        "SPONSOR",
    ):
        return "Brand"
    # Creator-like values
    v_lower = v.lower()
    if any(kw in v_lower for kw in ("creator", "influencer", "ugc", "talent", "kol")):
        return "Creator"
    return "Brand"


def extract_asset_subtype(val) -> str:
    """Extract granular subtype for filtering.

    Returns: Brand, Creator, Partner, or Other
    """
    v = str(val).strip().upper() if isinstance(val, str) and val else ""

    if v in (
        "BAU",
        "",
        "N/A",
        "NA",
        "NONE",
        "STANDARD",
        "BRAND",
        "BRANDED",
        "BRAND CONTENT",
        "BRAND ASSET",
        "BRAND VIDEO",
        "BRAND CREATIVE",
        "ORIGINAL",
        "IN-HOUSE",
        "INHOUSE",
        "IN HOUSE",
        "OWNED",
        "DIRECT",
        "INTERNAL",
        "STUDIO",
        "AGENCY",
        "STATIC",
        "VIDEO",
        "MOTION",
        "ANIMATION",
        "PRODUCT",
        "HERO",
        "MASTER",
        "NAN",
    ):
        return "Brand"
    elif v in (
        "PARTNER",
        "HYBRID",
        "CO-BRANDED",
        "CO BRAND",
        "CO-BRAND",
        "COBRAND",
        "COBRANDED",
        "COLLAB",
        "COLLABORATION",
        "PARTNERSHIP",
        "AFFILIATE",
        "SPONSORED",
        "SPONSOR",
        "JOINT",
        "JOINT VENTURE",
        "LICENSED",
        "LICENSE",
        "SYNDICATED",
        "SYNDICATION",
        "WHITE LABEL",
        "WHITELABEL",
        "WHITE-LABEL",
    ):
        return "Partner"
    elif v in (
        "INFLUENCER",
        "CREATOR",
        "TALENT",
        "UGC",
        "USER GENERATED",
        "USER-GENERATED",
        "USER_GENERATED",
        "USERGENERATED",
        "KOL",
        "KEY OPINION LEADER",
        "AMBASSADOR",
        "BRAND AMBASSADOR",
        "ADVOCATE",
        "TESTIMONIAL",
        "REVIEW",
        "ENDORSEMENT",
        "CREATOR CONTENT",
        "CREATOR ASSET",
        "INFLUENCER CONTENT",
        "TALENT CONTENT",
        "COMMUNITY",
        "FAN",
        "FAN CONTENT",
        "EARNED",
        "ORGANIC CREATOR",
    ):
        return "Creator"

    # Partial matching for compound values
    v_lower = v.lower()
    if any(kw in v_lower for kw in ("creator", "influencer", "ugc", "talent", "kol")):
        return "Creator"
    if any(kw in v_lower for kw in ("partner", "collab", "co-brand", "hybrid")):
        return "Partner"
    if any(kw in v_lower for kw in ("brand", "bau", "standard", "in-house", "studio")):
        return "Brand"

    logger.warning("Unrecognized asset subtype falling through to 'Brand': %r", val)
    return "Brand"


def normalize_objective(obj) -> str:
    """Map platform-specific objective names to canonical categories.

    IMPORTANT: Reach is now a separate objective from Awareness.
    """
    if not isinstance(obj, str):
        return "Unknown"
    obj_lower = obj.lower().replace("_", " ")

    for canonical, variations in OBJECTIVE_MAPPINGS.items():
        if any(variant in obj_lower for variant in variations):
            return canonical

    return obj.strip()


def compute_canonical_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Add canonical metric columns to dataframe.

    Platform-specific logic applied row-by-row based on 'platform' column.
    Preserves raw platform metrics in original columns.

    Canonical metrics:
    - canonical_hook_rate: Normalized early attention metric
    - canonical_hold_rate: Normalized mid-roll retention
    - canonical_completion_rate: Full watch rate
    - canonical_engagement_rate: Direct engagement
    - canonical_ctr: Click behavior
    - canonical_cost_efficiency: Cost efficiency metric
    """
    df = df.copy()

    # Hook rate: Meta uses 3s VTR, TikTok uses 2s VTR
    # Already normalised to 0-100 range in _normalize_pct
    df["canonical_hook_rate"] = df["vtr_2s"]

    # Hold rate: Meta has 50% VTR, TikTok has 25% VTR
    # Calculate as ratio of mid-view to early-view
    if "hold_rate" in df.columns:
        df["canonical_hold_rate"] = df["hold_rate"]
    elif "video_quartile_p50_rate" in df.columns and df["video_quartile_p50_rate"].notna().any():
        df["canonical_hold_rate"] = df["video_quartile_p50_rate"]
    elif "video_quartile_p25_rate" in df.columns and df["video_quartile_p25_rate"].notna().any():
        df["canonical_hold_rate"] = df["video_quartile_p25_rate"]
    else:
        # Derive from available quartile data if explicit hold_rate not present
        df["canonical_hold_rate"] = pd.Series(float("nan"), index=df.index)

    # Completion rate is platform-agnostic. Prefer native quartile rate when present.
    if "video_quartile_p100_rate" in df.columns and df["video_quartile_p100_rate"].notna().any():
        df["canonical_completion_rate"] = df["video_quartile_p100_rate"].where(
            df["video_quartile_p100_rate"] > 0,
            df["completion_rate"],
        )
    else:
        df["canonical_completion_rate"] = df["completion_rate"]

    # Engagement rate is platform-agnostic
    df["canonical_engagement_rate"] = df["engagement_rate"]

    # CTR is platform-agnostic
    df["canonical_ctr"] = df["ctr"]

    # Cost efficiency: Use CPM as the standard efficiency metric
    df["canonical_cost_efficiency"] = df["cpm"]

    return df


def compute_attention_proxy_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Identify which attention proxy inputs are available.

    Returns columns:
    - attention_hook_available: bool
    - attention_hold_available: bool
    - attention_completion_available: bool
    - attention_inputs_count: int
    """
    df = df.copy()

    df["attention_hook_available"] = df["canonical_hook_rate"].notna() & (
        df["canonical_hook_rate"] > 0
    )

    df["attention_hold_available"] = df["canonical_hold_rate"].notna() & (
        df["canonical_hold_rate"] > 0
    )

    df["attention_completion_available"] = df["canonical_completion_rate"].notna() & (
        df["canonical_completion_rate"] > 0
    )

    df["attention_inputs_count"] = (
        df["attention_hook_available"].astype(int)
        + df["attention_hold_available"].astype(int)
        + df["attention_completion_available"].astype(int)
    )

    return df


def _load_sheet(
    xl: pd.ExcelFile,
    sheet_name: str,
    platform_default: str,
    buying_type: str,
    header: int = 2,
    df_override: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Load one 'Data Analysis' sheet and normalise to internal schema.

    The Pixel DE spreadsheet format has:
    - Headers on row 3 (header=2 in pandas, zero-indexed)
    - Pre-cleaned 'Creative Name' column (no regex extraction needed)
    - Explicit 'OS' and 'Targeting Segment' columns
    - 'Spends' for spend (not 'Cost' or 'Amount spent')
    - 'Video Completion' for 100% view count
    - '2s VTR' (TikTok) or '3s VTR' (Meta) — both mapped to vtr_2s internally
    - No Wooshi brand measurement columns
    """
    df = df_override if df_override is not None else pd.read_excel(xl, sheet_name=sheet_name, header=header)
    if df.empty or "Creative Name" not in df.columns or "Impressions" not in df.columns:
        try:
            df, _ = read_xlsx_sheet_dataframe(
                str(xl.io),
                sheet_name,
                header_row=None,
            )
        except Exception:
            pass

    # Normalise column names: strip whitespace and collapse embedded newlines
    df.columns = [
        str(c).strip().replace("\n", " ") if c is not None else "" for c in df.columns
    ]

    # Drop completely empty rows
    df = df.dropna(subset=["Creative Name", "Impressions", "Spends"], how="all")
    df = df[
        df["Creative Name"].notna()
        & (df["Creative Name"].astype(str).str.strip() != "")
    ]

    # Platform: use column value and normalise, fall back to sheet-level default
    platform_col = _pick_col(df, ["Platform"], platform_default)
    platform_series = platform_col.apply(
        lambda x: (
            normalize_platform(str(x))
            if pd.notna(x) and str(x).strip()
            else platform_default
        )
    )

    # Extract format and placement from relevant columns
    format_raw = (
        _pick_col(df, ["Format", "Placement"], "Unknown").astype(str).str.strip()
    )
    placement_raw = _pick_col(df, ["Placement"], "Unknown").astype(str).str.strip()

    # Normalize format and placement separately
    format_normalized = format_raw.apply(
        lambda x: (
            normalize_format(str(x)) if pd.notna(x) and str(x).strip() else "Unknown"
        )
    )
    placement_normalized = placement_raw.apply(
        lambda x: (
            normalize_placement(str(x), platform_default)
            if pd.notna(x) and str(x).strip()
            else "Unknown"
        )
    )

    # VTR: TikTok uses 2s VTR; Meta uses 3s VTR — both become vtr_2s internally
    vtr_raw = _normalize_pct(
        pd.to_numeric(
            _pick_col(df, ["2s VTR", "3s VTR", "Hook Rate"], 0), errors="coerce"
        ).fillna(0)
    )

    # Asset type processing - three-tier system
    asset_type_raw = (
        _pick_col(df, ["Partner", "Asset Type", "Partner Type"], "BAU")
        .astype(str)
        .str.strip()
    )
    asset_type_canonical = asset_type_raw.apply(normalize_asset_type_canonical)
    asset_type_subtype = asset_type_raw.apply(extract_asset_subtype)

    # Normalize campaign name for consistent grouping
    campaign_raw_series = _pick_col(df, ["Campaign"], "").astype(str)
    campaign_normalized_series = campaign_raw_series.apply(
        lambda x: str(x).strip() if pd.notna(x) and str(x).strip() else "Unknown"
    )

    normalized = pd.DataFrame(
        {
            "ad_name_raw": _pick_col(df, ["Ad name in Platform", "Ad name"], "").astype(
                str
            ),
            "ad_id": _pick_col(df, ["Consolidated_Asset_Key"], "").astype(str),
            "creative_name": _pick_col(df, ["Creative Name", "Ad name in Platform"], "")
            .astype(str)
            .str.strip(),
            "platform": platform_series,
            "currency": "EUR",
            "format_raw": format_raw,
            "format": format_normalized,
            "format_canonical": format_normalized,  # Alias for consistency
            "placement_raw": placement_raw,
            "placement": placement_normalized,
            "placement_canonical": placement_normalized,  # Canonical alias
            "campaign_name": _pick_col(df, ["Campaign"], "").astype(str),
            "campaign_raw": _pick_col(df, ["Campaign"], "").astype(
                str
            ),  # Preserve original
            "campaign_normalized": campaign_normalized_series,  # Normalized for grouping
            "objective": _pick_col(df, ["Objective"], "Unknown").apply(
                lambda x: normalize_objective(str(x)) if pd.notna(x) else "Unknown"
            ),
            "objective_normalized": _pick_col(df, ["Objective"], "Unknown").apply(
                lambda x: normalize_objective(str(x)) if pd.notna(x) else "Unknown"
            ),
            "buying_type": buying_type,
            "reach": pd.to_numeric(_pick_col(df, ["Reach"], 0), errors="coerce").fillna(
                0
            ),
            "impressions": pd.to_numeric(
                _pick_col(df, ["Impressions"], 0), errors="coerce"
            ).fillna(0),
            "frequency": pd.to_numeric(
                _pick_col(df, ["Frequency"], 0), errors="coerce"
            ).fillna(0),
            "spend": pd.to_numeric(
                _pick_col(df, ["Spends", "Spend", "Cost"], 0), errors="coerce"
            ).fillna(0),
            "cpm": pd.to_numeric(_pick_col(df, ["CPM"], 0), errors="coerce").fillna(0),
            "clicks": pd.to_numeric(
                _pick_col(df, ["Clicks"], 0), errors="coerce"
            ).fillna(0),
            "vtr_2s": vtr_raw,
            "video_views_100": pd.to_numeric(
                _pick_col(df, ["Video Completion"], 0), errors="coerce"
            ).fillna(0),
            "shares": pd.to_numeric(
                _pick_col(df, ["Shares"], 0), errors="coerce"
            ).fillna(0),
            "engagements": pd.to_numeric(
                _pick_col(df, ["Total Engagement", "Engagements"], 0), errors="coerce"
            ).fillna(0),
            "duration_s": _pick_col(df, ["Duration"], "").apply(parse_duration),
            "ad_status": "Active",
            "total_plays": pd.to_numeric(
                _pick_col(df, ["Total Plays"], 0), errors="coerce"
            ).fillna(0),
            # Split dimensions — explicitly provided in new format
            "asset_type_raw": asset_type_raw,
            "asset_type_canonical": asset_type_canonical,
            "asset_type_subtype": asset_type_subtype,
            "os_target": _pick_col(df, ["OS"], "All").apply(normalize_os),
            "os_canonical": _pick_col(df, ["OS"], "All").apply(
                normalize_os
            ),  # Canonical alias
            "device_type": _pick_col(df, ["OS"], "All")
            .apply(normalize_os)
            .map(
                {
                    "iOS": "Mobile",
                    "Android": "Mobile",
                    "Desktop": "Desktop",
                    "All": "All",
                }
            )
            .fillna("All"),
            "audience_segment": _pick_col(df, ["Targeting Segment"], "All")
            .astype(str)
            .str.strip()
            .replace({"": "All", "nan": "All", "None": "All"}),
            # Enrichment fields (new in DE format)
            "concept": _pick_col(df, ["Concept"], "").astype(str),
            "product": _pick_col(df, ["Product"], "").astype(str),
            "wave": _pick_col(df, ["Wave"], "").astype(str),
            "performance_score": pd.to_numeric(
                _pick_col(
                    df,
                    [
                        "Performance Score",
                        "Performance Index",
                        "Creative Efficiency Index",
                    ],
                    float("nan"),
                ),
                errors="coerce",
            ),
        }
    )

    return normalized


def aggregate_creatives(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate ad-line variants into one row per creative concept.

    Groups by creative name + platform + objective + buying_type + format_canonical
    so that Paid/Boosting and Video/Static creatives are kept in separate cohorts.

    IMPORTANT: Scores are NOT comparable across buying_type cohorts.
    Paid and Boosting are scored in entirely separate cohorts.
    Static and Video assets are scored with different primary KPIs.
    """
    group_cols = [
        "creative_name",
        "platform",
        "objective",
        "buying_type",
        "format_canonical",
    ]

    first_cols = {
        "ad_id": "first",
        "ad_name_raw": "first",
        "video_id": "first",
        "format_raw": "first",
        "format": "first",
        "placement_raw": "first",
        "placement": "first",
        "placement_canonical": "first",
        "ad_status": "first",
        "asset_type_raw": "first",
        "asset_type_canonical": "first",
        "asset_type_subtype": "first",
        "currency": "first",
        "campaign_raw": "first",
        "campaign_type": "first",
        "campaign_subtype": "first",
        "bid_strategy_type": "first",
        "optimization_goal": "first",
        "campaign_normalized": "first",
        "objective_normalized": "first",
        "platform_source": "first",
        "platform_confidence": "mean",
        "platform_evidence_strength": "first",
        "platform_evidence": "first",
        "objective_source": "first",
        "objective_confidence": "mean",
        "objective_evidence_strength": "first",
        "objective_evidence": "first",
        "concept": "first",
        "product": "first",
        "wave": "first",
    }
    for col in df.columns:
        if col.startswith("metadata_") and col not in group_cols:
            first_cols[col] = "first"

    sum_cols = {
        "spend": "sum",
        "reach": "sum",
        "impressions": "sum",
        "clicks": "sum",
        "video_views_100": "sum",
        "trueview_views": "sum",
        "shares": "sum",
        "engagements": "sum",
        "total_plays": "sum",
    }

    mean_cols = {
        "duration_s": "first",
        "performance_score": "mean",
    }

    campaign_col = {"campaign_name": "nunique"}

    split_cols = {
        "os_target": lambda x: ", ".join(sorted(set(x.dropna()))),
        "device_type": lambda x: ", ".join(sorted(set(x.dropna()))),
        "audience_segment": lambda x: ", ".join(sorted(set(x.dropna()))),
    }
    bool_cols = {
        "trueview_eligible": "max",
    }
    family_col = {
        "youtube_measurement_family": lambda x: (
            "mixed" if len(set(x.dropna())) > 1 else next(iter(set(x.dropna())), "standard")
        )
    }

    # Vectorised impression-weighted VTR
    df_vtr = df.copy()
    df_vtr["vtr_imp"] = df_vtr["vtr_2s"] * df_vtr["impressions"]
    vtr_agg = (
        df_vtr.groupby(group_cols)[["vtr_imp", "impressions"]]
        .sum()
        .assign(
            vtr_2s=lambda x: x["vtr_imp"] / x["impressions"].replace(0, float("nan"))
        )[["vtr_2s"]]
        .reset_index()
    )

    weighted_rate_cols = [
        "trueview_view_rate",
        "video_quartile_p25_rate",
        "video_quartile_p50_rate",
        "video_quartile_p75_rate",
        "video_quartile_p100_rate",
    ]
    rate_aggs = []
    for col in weighted_rate_cols:
        if col not in df.columns:
            continue
        temp = df[group_cols + [col, "impressions"]].copy()
        temp[f"{col}_weighted"] = temp[col] * temp["impressions"]
        rate_aggs.append(
            temp.groupby(group_cols)[[f"{col}_weighted", "impressions"]]
            .sum()
            .assign(**{col: lambda x, c=col: x[f"{c}_weighted"] / x["impressions"].replace(0, float("nan"))})[
                [col]
            ]
            .reset_index()
        )

    agg_dict = {
        **first_cols,
        **sum_cols,
        **mean_cols,
        **campaign_col,
        **split_cols,
        **bool_cols,
        **family_col,
    }
    agg_dict = {col: fn for col, fn in agg_dict.items() if col in df.columns}
    agg = df.groupby(group_cols, as_index=False).agg(agg_dict)
    variant_counts = (
        df.groupby(group_cols, as_index=False)
        .size()
        .rename(columns={"size": "n_variants"})
    )
    agg = agg.rename(columns={"campaign_name": "n_campaigns"})
    agg = agg.merge(variant_counts, on=group_cols, how="left")
    agg["rows_rolled_up"] = agg["n_variants"]
    agg = agg.merge(vtr_agg, on=group_cols, how="left")
    for rate_agg in rate_aggs:
        agg = agg.merge(rate_agg, on=group_cols, how="left", suffixes=("", "_weighted"))
        for col in weighted_rate_cols:
            weighted_col = f"{col}_weighted"
            if weighted_col in agg.columns:
                agg[col] = agg[weighted_col].combine_first(agg.get(col))
                agg = agg.drop(columns=[weighted_col])

    agg["frequency"] = agg["impressions"] / agg["reach"].replace(0, float("nan"))

    return agg


def compute_duration_adjusted_completion(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise completion rate for video duration.

    A 15s video with 3% completion is not more engaging than a 90s video
    with 0.5% completion - the short video is just easier to finish.

    Expected completion rate model (empirical):
      <15s: ~3.5%, 15-30s: ~2.4%, 30-60s: ~0.9%, 60s+: ~0.5%
    """
    df = df.copy()

    def expected_completion(duration):
        if duration <= 0:
            return 1.0
        elif duration <= 15:
            return 3.5
        elif duration <= 30:
            return 2.4
        elif duration <= 60:
            return 0.9
        else:
            return 0.5

    df["expected_completion"] = df["duration_s"].apply(expected_completion)
    df["completion_vs_expected"] = df["completion_rate"] / df[
        "expected_completion"
    ].replace(0, float("nan"))

    return df


def compute_audience_consistency(
    df_raw: pd.DataFrame, df_agg: pd.DataFrame
) -> pd.DataFrame:
    """Score how consistently a creative performs across different audiences/campaigns.

    A creative that performs well across multiple targeting groups is genuinely
    strong. One that varies wildly might be audience-dependent rather than
    creative-dependent.
    """
    df_agg = df_agg.copy()

    consistency_scores = []
    for _, row in df_agg.iterrows():
        mask = (
            (df_raw["creative_name"] == row["creative_name"])
            & (df_raw["platform"] == row["platform"])
            & (df_raw["objective"] == row["objective"])
            & (df_raw["buying_type"] == row["buying_type"])
            & (df_raw["format_canonical"] == row["format_canonical"])
        )
        variants = df_raw[mask]

        if len(variants) <= 1 or row["n_campaigns"] <= 1:
            consistency_scores.append(1.0)
            continue

        # Use ER for static assets, VTR for video/motion
        is_static = row.get("format_canonical", "").strip().lower() in (
            "static",
            "image",
            "carousel",
            "static image",
        )
        metric_col = "engagement_rate" if is_static else "vtr_2s"
        metric_values = (
            variants[metric_col]
            if metric_col in variants.columns
            else variants["vtr_2s"]
        )
        metric_values = metric_values[metric_values > 0]

        if len(metric_values) <= 1:
            consistency_scores.append(1.0)
            continue

        mean_val = metric_values.mean()
        if mean_val == 0:
            consistency_scores.append(1.0)
            continue

        cv = metric_values.std() / mean_val
        consistency = 1.0 / (1.0 + cv)
        consistency_scores.append(consistency)

    df_agg["audience_consistency"] = consistency_scores
    return df_agg


def normalize_unstructured_dataframe(
    df_sheet: pd.DataFrame,
    column_mapping: dict[str, str],
    preserve_columns: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Normalize a mapped non-standard export into WPP Scout's internal schema."""
    mapped_df = df_sheet.rename(columns=column_mapping)

    def get_col(candidates, default):
        return _pick_col(mapped_df, candidates, default)

    derived_platform = infer_platform_for_dataframe(mapped_df)
    derived_objective = infer_objective_for_dataframe(mapped_df)

    platform_input = get_col(["platform"], "")
    platform_series = platform_input.apply(lambda x: normalize_platform(str(x)))
    missing_platform = platform_series.astype(str).str.strip().isin(["", "Unknown", "nan", "None"])
    if derived_platform.value != "Unknown":
        platform_series.loc[missing_platform] = derived_platform.value
    platform_source = pd.Series("explicit", index=mapped_df.index)
    platform_source.loc[missing_platform & (derived_platform.value != "Unknown")] = "derived"
    platform_confidence = pd.Series(1.0, index=mapped_df.index)
    platform_confidence.loc[platform_source == "derived"] = derived_platform.confidence
    platform_confidence.loc[platform_series == "Unknown"] = 0.0
    platform_evidence_strength = pd.Series("explicit", index=mapped_df.index)
    platform_evidence_strength.loc[platform_source == "derived"] = (
        derived_platform.evidence_strength
    )
    platform_evidence_strength.loc[platform_series == "Unknown"] = "none"

    objective_input = get_col(["objective"], "")
    objective_series = objective_input.apply(lambda x: normalize_objective(str(x)))
    missing_objective = objective_series.astype(str).str.strip().isin(["", "Unknown", "nan", "None"])
    if derived_objective.value != "Unknown":
        objective_series.loc[missing_objective] = derived_objective.value
    objective_source = pd.Series("explicit", index=mapped_df.index)
    objective_source.loc[missing_objective & (derived_objective.value != "Unknown")] = "derived"
    objective_confidence = pd.Series(1.0, index=mapped_df.index)
    objective_confidence.loc[objective_source == "derived"] = derived_objective.confidence
    objective_confidence.loc[objective_series == "Unknown"] = 0.0
    objective_evidence_strength = pd.Series("explicit", index=mapped_df.index)
    objective_evidence_strength.loc[objective_source == "derived"] = (
        derived_objective.evidence_strength
    )
    objective_evidence_strength.loc[objective_series == "Unknown"] = "none"

    format_raw = get_col(["format_raw"], "Unknown").astype(str)
    format_normalized = format_raw.apply(normalize_format)
    placement_raw = get_col(["placement_raw"], "Unknown").astype(str)
    placement_normalized = pd.Series(
        [
            normalize_placement(placement, platform)
            for placement, platform in zip(placement_raw, platform_series)
        ],
        index=mapped_df.index,
    )

    vtr_raw = _normalize_pct(
        _to_numeric(get_col(["vtr_2s"], 0), default=0)
    )
    trueview_view_rate = _normalize_pct(
        _to_numeric(get_col(["trueview_view_rate"], 0), default=0)
    )
    vtr_raw = vtr_raw.where(vtr_raw > 0, trueview_view_rate)
    asset_type_raw = get_col(["asset_type_raw"], "BAU").astype(str)

    normalized = pd.DataFrame(
        {
            "ad_name_raw": get_col(["ad_name_raw"], "").astype(str),
            "ad_id": get_col(["ad_id"], "").astype(str),
            "video_id": get_col(["video_id"], "").astype(str),
            "creative_name": get_col(["creative_name"], "")
            .astype(str)
            .replace("", "Unknown Creative")
            .replace("nan", "Unknown Creative"),
            "platform": platform_series,
            "currency": "EUR",
            "format_raw": format_raw,
            "format": format_normalized,
            "format_canonical": format_normalized,
            "placement_raw": placement_raw,
            "placement": placement_normalized,
            "placement_canonical": placement_normalized,
            "campaign_name": get_col(["campaign_raw"], "").astype(str),
            "campaign_raw": get_col(["campaign_raw"], "").astype(str),
            "campaign_type": get_col(["campaign_type"], "").astype(str),
            "campaign_subtype": get_col(["campaign_subtype"], "").astype(str),
            "bid_strategy_type": get_col(["bid_strategy_type"], "").astype(str),
            "optimization_goal": get_col(["optimization_goal"], "").astype(str),
            "campaign_normalized": get_col(["campaign_raw"], "")
            .astype(str)
            .apply(
                lambda x: str(x).strip()
                if pd.notna(x) and str(x).strip()
                else "Unknown"
            ),
            "platform_source": platform_source,
            "platform_confidence": platform_confidence,
            "platform_evidence_strength": platform_evidence_strength,
            "platform_evidence": derived_platform.evidence,
            "objective": objective_series,
            "objective_normalized": objective_series,
            "objective_source": objective_source,
            "objective_confidence": objective_confidence,
            "objective_evidence_strength": objective_evidence_strength,
            "objective_evidence": derived_objective.evidence,
            "buying_type": get_col(["buying_type"], "Paid")
            .astype(str)
            .replace("nan", "Paid")
            .replace("", "Paid"),
            "reach": _to_numeric(get_col(["reach"], 0), default=0),
            "impressions": _to_numeric(get_col(["impressions"], 0), default=0),
            "frequency": _to_numeric(get_col(["frequency"], 0), default=0),
            "spend": _to_numeric(get_col(["spend"], 0), default=0),
            "cpm": _to_numeric(get_col(["cpm"], 0), default=0),
            "clicks": _to_numeric(get_col(["clicks"], 0), default=0),
            "vtr_2s": vtr_raw,
            "video_views_100": _to_numeric(get_col(["video_views_100"], 0), default=0),
            "trueview_views": _to_numeric(get_col(["trueview_views"], 0), default=0),
            "trueview_view_rate": trueview_view_rate,
            "video_quartile_p25_rate": _normalize_pct(
                _to_numeric(get_col(["video_quartile_p25_rate"], 0), default=0)
            ),
            "video_quartile_p50_rate": _normalize_pct(
                _to_numeric(get_col(["video_quartile_p50_rate"], 0), default=0)
            ),
            "video_quartile_p75_rate": _normalize_pct(
                _to_numeric(get_col(["video_quartile_p75_rate"], 0), default=0)
            ),
            "video_quartile_p100_rate": _normalize_pct(
                _to_numeric(get_col(["video_quartile_p100_rate"], 0), default=0)
            ),
            "shares": _to_numeric(get_col(["shares"], 0), default=0),
            "engagements": _to_numeric(get_col(["engagements"], 0), default=0),
            "duration_s": get_col(["duration_s"], "").apply(parse_duration),
            "ad_status": "Active",
            "total_plays": _to_numeric(get_col(["total_plays"], 0), default=0),
            "asset_type_raw": asset_type_raw,
            "asset_type_canonical": asset_type_raw.apply(normalize_asset_type_canonical),
            "asset_type_subtype": asset_type_raw.apply(extract_asset_subtype),
            "os_target": get_col(["os_target"], "All").apply(normalize_os),
            "os_canonical": get_col(["os_target"], "All").apply(normalize_os),
            "device_type": get_col(["os_target"], "All")
            .apply(normalize_os)
            .map(
                {
                    "iOS": "Mobile",
                    "Android": "Mobile",
                    "Desktop": "Desktop",
                    "All": "All",
                }
            )
            .fillna("All"),
            "audience_segment": get_col(["audience_segment"], "All")
            .astype(str)
            .str.strip()
            .replace({"": "All", "nan": "All", "None": "All"}),
            "concept": get_col(["concept"], "").astype(str),
            "product": get_col(["product"], "").astype(str),
            "wave": get_col(["wave"], "").astype(str),
            "performance_score": pd.to_numeric(
                get_col(["performance_score"], float("nan")), errors="coerce"
            ),
        }
    )

    missing_ad_name = normalized["ad_name_raw"].str.strip().isin(["", "nan", "None"])
    normalized.loc[missing_ad_name, "ad_name_raw"] = normalized.loc[
        missing_ad_name, "creative_name"
    ]
    extracted_opid = _extract_opid(
        normalized["ad_name_raw"].where(
            normalized["ad_name_raw"].str.strip() != "",
            normalized["creative_name"],
        )
    )
    missing_ad_id = normalized["ad_id"].str.strip().isin(["", "nan", "None"])
    normalized.loc[missing_ad_id, "ad_id"] = extracted_opid[missing_ad_id]

    missing_duration = normalized["duration_s"] <= 0
    normalized.loc[missing_duration, "duration_s"] = _extract_duration_from_text(
        normalized.loc[missing_duration, "ad_name_raw"].where(
            normalized.loc[missing_duration, "ad_name_raw"].str.strip() != "",
            normalized.loc[missing_duration, "creative_name"],
        )
    )

    normalized["trueview_eligible"] = (
        (normalized["trueview_views"] > 0) | (normalized["trueview_view_rate"] > 0)
    )
    has_completion_signal = normalized["video_quartile_p100_rate"] > 0
    normalized["youtube_measurement_family"] = "standard"
    normalized.loc[
        normalized["platform"].eq("YouTube") & normalized["trueview_eligible"],
        "youtube_measurement_family",
    ] = "trueview_eligible"
    normalized.loc[
        normalized["platform"].eq("YouTube")
        & ~normalized["trueview_eligible"]
        & has_completion_signal,
        "youtube_measurement_family",
    ] = "completion_only"

    normalized = normalized[normalized["creative_name"] != "Unknown Creative"]
    normalized = normalized[(normalized["spend"] > 0) | (normalized["impressions"] > 0)]
    for source_column in preserve_columns or []:
        if source_column not in df_sheet.columns or source_column in column_mapping:
            continue
        metadata_column = _metadata_column_name(source_column)
        normalized[metadata_column] = df_sheet.loc[normalized.index, source_column].astype(str)
    return normalized


def _load_unstructured_frames(
    candidates: list[tuple[str, pd.DataFrame]],
    column_mapping: Optional[dict[str, str]] = None,
    preserve_columns: Optional[list[str]] = None,
) -> list[pd.DataFrame]:
    frames = []
    if column_mapping is None:
        try:
            from src.llm_mapper import generate_column_mapping
            from src.data_mapping import (
                infer_alias_mapping,
                merge_mapping_candidates,
                REQUIRED_FIELDS,
            )
        except ImportError:
            raise ValueError(
                "llm_mapper module not found. Cannot process unstructured data."
            )

    for _, df_sheet in candidates:
        if df_sheet.empty or len(df_sheet.columns) < 3:
            continue
        if column_mapping is not None:
            mapping = column_mapping
        else:
            mapping = infer_alias_mapping(df_sheet)
            if not all(field in mapping.values() for field in REQUIRED_FIELDS):
                mapping = merge_mapping_candidates(
                    mapping, generate_column_mapping(df_sheet)
                )
        normalized = normalize_unstructured_dataframe(
            df_sheet,
            mapping,
            preserve_columns=preserve_columns,
        )
        if not normalized.empty:
            frames.append(normalized)
    return frames


def _load_selected_excel_sheet(
    filepath: str,
    sheet_name: str,
    header_row: Optional[int] = None,
    column_mapping: Optional[dict[str, str]] = None,
    preserve_columns: Optional[list[str]] = None,
) -> list[pd.DataFrame]:
    xl = pd.ExcelFile(filepath)
    if sheet_name not in xl.sheet_names:
        raise ValueError(
            f"Sheet '{sheet_name}' not found. Available sheets: {', '.join(xl.sheet_names)}"
        )

    detected_header_row = header_row
    if header_row is None:
        try:
            df_sheet, detected_header_row = read_xlsx_sheet_dataframe(filepath, sheet_name)
        except Exception:
            df_sheet = pd.read_excel(xl, sheet_name=sheet_name, header=0)
    else:
        header = int(header_row) - 1
        df_sheet = pd.read_excel(xl, sheet_name=sheet_name, header=header)
        if df_sheet.empty or len(df_sheet.columns) < 3:
            df_sheet, detected_header_row = read_xlsx_sheet_dataframe(
                filepath,
                sheet_name,
                header_row=header_row,
            )
    df_sheet.columns = [
        str(c).strip().replace("\n", " ") if c is not None else ""
        for c in df_sheet.columns
    ]
    standard_cols = {"Creative Name", "Impressions", "Spends"}
    if standard_cols.issubset(set(df_sheet.columns)):
        return [
            _load_sheet(
                xl,
                sheet_name,
                "Unknown",
                "Paid",
                header=(int(detected_header_row) - 1) if detected_header_row else 0,
                df_override=df_sheet,
            )
        ]
    return _load_unstructured_frames(
        [(sheet_name, df_sheet)],
        column_mapping=column_mapping,
        preserve_columns=preserve_columns,
    )


def load_data(
    filepath: str,
    column_mapping: Optional[dict[str, str]] = None,
    sheet_name: Optional[str] = None,
    header_row: Optional[int] = None,
    preserve_columns: Optional[list[str]] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load Excel file and return (df_raw, df_agg).

    Reads four 'Data Analysis' sheets from the Pixel DE format:
      - Data Analysis Paid Meta     → buying_type = 'Paid'
      - Data Analysis Paid TikTok   → buying_type = 'Paid'
      - Data Analysis Boosting Meta → buying_type = 'Boosting'
      - Data Analysis Boosting TikTok → buying_type = 'Boosting'

    Paid and Boosting creatives are kept in separate cohorts throughout
    so they are only ranked against peers with the same buying type.

    IMPORTANT: Scores are NOT comparable across buying_type cohorts.
    A Boosting creative is always ranked against other Boosting creatives;
    a Paid creative against other Paid creatives.

    df_raw — one row per ad line, split dimensions intact.
    df_agg — one row per creative concept (name + platform + objective + buying_type + format).
    """
    frames = []
    path = Path(filepath)
    sheet_configs = [
        ("Data Analysis Paid Meta", "Meta", "Paid"),
        ("Data Analysis Paid TikTok", "TikTok", "Paid"),
        ("Data Analysis Boosting Meta", "Meta", "Boosting"),
        ("Data Analysis Boosting TikTok", "TikTok", "Boosting"),
    ]

    if path.suffix.lower() == ".csv":
        frames.extend(
            _load_unstructured_frames(
                [
                    (
                        path.stem,
                        pd.read_csv(
                            filepath,
                            header=(int(header_row) - 1) if header_row else 0,
                            dtype=str,
                            keep_default_na=False,
                        ),
                    )
                ],
                column_mapping=column_mapping,
                preserve_columns=preserve_columns,
            )
        )
    elif sheet_name:
        frames.extend(
            _load_selected_excel_sheet(
                filepath,
                sheet_name=sheet_name,
                header_row=header_row,
                column_mapping=column_mapping,
                preserve_columns=preserve_columns,
            )
        )
    else:
        xl = pd.ExcelFile(filepath)

        for sheet_name, platform_default, buying_type in sheet_configs:
            if sheet_name in xl.sheet_names:
                frames.append(_load_sheet(xl, sheet_name, platform_default, buying_type))

        if not frames:
            logger.info(
                "No standard sheets found in %s. Attempting mapping workflow...",
                filepath,
            )
            from src.data_mapping import iter_candidate_dataframes

            frames.extend(
                _load_unstructured_frames(
                    iter_candidate_dataframes(filepath),
                    column_mapping=column_mapping,
                    preserve_columns=preserve_columns,
                )
            )

    if not frames:
        raise ValueError(
            f"No matching sheets found in {filepath} and LLM mapping failed to extract valid data. "
            f"Expected standard sheets or mappable columns."
        )

    df_raw = pd.concat(frames, ignore_index=True)

    # Per-ad-line derived metrics (needed before aggregation)
    imp_raw = df_raw["impressions"].replace(0, float("nan"))
    completion_from_counts = (df_raw["video_views_100"] / imp_raw) * 100
    if "video_quartile_p100_rate" in df_raw.columns:
        df_raw["completion_rate"] = df_raw["video_quartile_p100_rate"].where(
            df_raw["video_quartile_p100_rate"] > 0,
            completion_from_counts,
        )
    else:
        df_raw["completion_rate"] = completion_from_counts
    df_raw["ctr"] = (df_raw["clicks"] / imp_raw) * 100
    df_raw["engagement_rate"] = (df_raw["engagements"] / imp_raw) * 100

    # Add canonical metrics to raw data
    df_raw = compute_canonical_metrics(df_raw)

    # Identify attention proxy input availability
    df_raw = compute_attention_proxy_inputs(df_raw)

    # Aggregate to one row per creative concept
    df = aggregate_creatives(df_raw)

    # Recompute derived metrics on aggregated data
    imp = df["impressions"].replace(0, float("nan"))
    completion_from_counts = (df["video_views_100"] / imp) * 100
    if "video_quartile_p100_rate" in df.columns:
        df["completion_rate"] = df["video_quartile_p100_rate"].where(
            df["video_quartile_p100_rate"] > 0,
            completion_from_counts,
        )
    else:
        df["completion_rate"] = completion_from_counts
    df["ctr"] = (df["clicks"] / imp) * 100
    df["engagement_rate"] = (df["engagements"] / imp) * 100
    df["share_rate"] = (df["shares"] / imp) * 100
    df["cost_per_complete_view"] = df["spend"] / df["video_views_100"].replace(
        0, float("nan")
    )
    df["reach_per_pound"] = df["reach"] / df["spend"].replace(0, float("nan"))
    # CPM recomputed from aggregated spend + impressions (spend-weighted average)
    df["cpm"] = (df["spend"] / imp) * 1000

    # Compute canonical metrics on aggregated data
    df = compute_canonical_metrics(df)

    df = compute_duration_adjusted_completion(df)
    df = compute_audience_consistency(df_raw, df)

    reach_available = df["reach"] > 0
    df["low_confidence"] = (df["spend"] < 500) | (
        reach_available & (df["reach"] < 10000)
    )

    name_to_platforms = (
        df_raw.groupby("creative_name")["platform"]
        .apply(lambda x: ", ".join(sorted(x.unique())))
        .to_dict()
    )
    df["platforms_active"] = df["creative_name"].map(name_to_platforms)
    df["cross_platform"] = df["platforms_active"].str.contains(",", na=False)

    return df_raw, df


def _load_sheet_from_rows(
    rows: list[list], sheet_name: str, platform_default: str, buying_type: str
) -> pd.DataFrame:
    """Load a standard Pixel sheet from parsed JSON rows."""
    if len(rows) < 4:
        return pd.DataFrame()

    import io

    headers = [
        str(c).strip().replace("\n", " ") if c is not None else "" for c in rows[2]
    ]
    data_rows = rows[3:]
    n_cols = len(headers)
    padded = [(list(row) + [None] * (n_cols - len(row)))[:n_cols] for row in data_rows]

    df = pd.DataFrame(padded, columns=headers)
    buf = io.BytesIO()
    df.to_excel(buf, sheet_name=sheet_name, index=False, engine="openpyxl")
    buf.seek(0)
    xl = pd.ExcelFile(buf, engine="openpyxl")
    return _load_sheet(xl, sheet_name, platform_default, buying_type, header=0)


def _finish_loaded_frames(frames: list[pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run common post-processing after standard or mapped frames are loaded."""
    if not frames:
        raise ValueError("No matching sheets found and mapping failed to extract valid data.")

    df_raw = pd.concat(frames, ignore_index=True)

    imp_raw = df_raw["impressions"].replace(0, float("nan"))
    df_raw["completion_rate"] = (df_raw["video_views_100"] / imp_raw) * 100
    df_raw["ctr"] = (df_raw["clicks"] / imp_raw) * 100
    df_raw["engagement_rate"] = (df_raw["engagements"] / imp_raw) * 100

    df_raw = compute_canonical_metrics(df_raw)
    df_raw = compute_attention_proxy_inputs(df_raw)

    df = aggregate_creatives(df_raw)

    imp = df["impressions"].replace(0, float("nan"))
    df["completion_rate"] = (df["video_views_100"] / imp) * 100
    df["ctr"] = (df["clicks"] / imp) * 100
    df["engagement_rate"] = (df["engagements"] / imp) * 100
    df["share_rate"] = (df["shares"] / imp) * 100
    df["cost_per_complete_view"] = df["spend"] / df["video_views_100"].replace(
        0, float("nan")
    )
    df["reach_per_pound"] = df["reach"] / df["spend"].replace(0, float("nan"))
    df["cpm"] = (df["spend"] / imp) * 1000

    df = compute_canonical_metrics(df)
    df = compute_duration_adjusted_completion(df)
    df = compute_audience_consistency(df_raw, df)

    reach_available = df["reach"] > 0
    df["low_confidence"] = (df["spend"] < 500) | (
        reach_available & (df["reach"] < 10000)
    )

    name_to_platforms = (
        df_raw.groupby("creative_name")["platform"]
        .apply(lambda x: ", ".join(sorted(x.unique())))
        .to_dict()
    )
    df["platforms_active"] = df["creative_name"].map(name_to_platforms)
    df["cross_platform"] = df["platforms_active"].str.contains(",", na=False)

    return df_raw, df


def load_data_from_sheets(
    sheets: dict[str, list[list]], column_mapping: Optional[dict[str, str]] = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load parsed browser sheet rows and return (df_raw, df_agg)."""
    sheet_configs = [
        ("Data Analysis Paid Meta", "Meta", "Paid"),
        ("Data Analysis Paid TikTok", "TikTok", "Paid"),
        ("Data Analysis Boosting Meta", "Meta", "Boosting"),
        ("Data Analysis Boosting TikTok", "TikTok", "Boosting"),
    ]

    frames = []
    for sheet_name, platform_default, buying_type in sheet_configs:
        if sheet_name in sheets:
            result = _load_sheet_from_rows(
                sheets[sheet_name], sheet_name, platform_default, buying_type
            )
            if not result.empty:
                frames.append(result)

    if not frames:
        from src.data_mapping import iter_candidate_dataframes_from_sheets

        frames.extend(
            _load_unstructured_frames(
                iter_candidate_dataframes_from_sheets(sheets),
                column_mapping=column_mapping,
            )
        )

    return _finish_loaded_frames(frames)
