import pandas as pd
import numpy as np


# =============================================================================
# SCORING CONFIGURATION
# =============================================================================

# Scoring weights (when attention proxy is available)
WEIGHTS_FULL = {
    "primary": 0.50,
    "secondary": 0.25,
    "efficiency": 0.15,
    "attention_proxy": 0.10,
}

# Scoring weights (when attention proxy is NOT available - renormalized)
WEIGHTS_RENORMALIZED = {
    "primary": 0.556,  # 50/90
    "secondary": 0.278,  # 25/90
    "efficiency": 0.167,  # 15/90
    "attention_proxy": 0.0,
}

# =============================================================================
# OBJECTIVE METRICS MAPPING
# =============================================================================

OBJECTIVE_METRICS = {
    "Video Views": {
        "primary": ["vtr_2s"],
        "secondary": ["completion_vs_expected", "ctr", "share_rate"],
        "efficiency": "cost_per_complete_view",
        "efficiency_lower_is_better": True,
    },
    "Awareness": {
        "primary": ["vtr_2s"],
        "secondary": ["completion_vs_expected", "reach_per_pound"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Reach": {
        "primary": ["reach_per_pound"],
        "secondary": ["vtr_2s", "frequency"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Engagement": {
        "primary": ["engagement_rate"],
        "secondary": ["share_rate", "ctr", "completion_vs_expected"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Traffic": {
        "primary": ["ctr"],
        "secondary": ["engagement_rate", "completion_vs_expected"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Sales": {
        "primary": ["ctr"],
        "secondary": ["completion_vs_expected", "engagement_rate"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Target Frequency": {
        "primary": ["completion_vs_expected"],
        "secondary": ["vtr_2s", "engagement_rate"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
}

# Default for unrecognized objectives
DEFAULT_METRICS = {
    "primary": ["vtr_2s"],
    "secondary": ["completion_vs_expected", "ctr", "share_rate"],
    "efficiency": "cpm",
    "efficiency_lower_is_better": True,
}

# =============================================================================
# STATIC ASSET METRICS — VTR/completion are irrelevant for statics
# =============================================================================

STATIC_OBJECTIVE_METRICS = {
    "Video Views": {
        "primary": ["engagement_rate", "ctr"],
        "secondary": ["share_rate"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Awareness": {
        "primary": ["engagement_rate"],
        "secondary": ["ctr", "reach_per_pound"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Reach": {
        "primary": ["reach_per_pound"],
        "secondary": ["engagement_rate", "ctr"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Engagement": {
        "primary": ["engagement_rate"],
        "secondary": ["share_rate", "ctr"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Traffic": {
        "primary": ["ctr"],
        "secondary": ["engagement_rate", "share_rate"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Sales": {
        "primary": ["ctr"],
        "secondary": ["engagement_rate", "share_rate"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
    "Target Frequency": {
        "primary": ["engagement_rate"],
        "secondary": ["ctr", "share_rate"],
        "efficiency": "cpm",
        "efficiency_lower_is_better": True,
    },
}

STATIC_DEFAULT_METRICS = {
    "primary": ["engagement_rate", "ctr"],
    "secondary": ["share_rate"],
    "efficiency": "cpm",
    "efficiency_lower_is_better": True,
}


def is_static_format(format_val) -> bool:
    """Check if a format is a static (non-video) asset."""
    if not isinstance(format_val, str):
        return False
    return format_val.strip().lower() in ("static", "image", "carousel", "static image")


def get_metrics_config(objective: str, format_canonical: str) -> dict:
    """Return the correct metrics config based on objective and format.

    Static assets use ER/CTR instead of VTR/completion.
    """
    if is_static_format(format_canonical):
        return STATIC_OBJECTIVE_METRICS.get(objective, STATIC_DEFAULT_METRICS)
    return OBJECTIVE_METRICS.get(objective, DEFAULT_METRICS)


# =============================================================================
# SCORING FUNCTIONS
# =============================================================================


def frequency_penalty(freq: float) -> float:
    """Penalize creatives with high frequency (audience fatigue).

    No penalty up to frequency 2. Each point above 2 reduces score by ~15%.
    """
    if pd.isna(freq):
        return 1.0
    excess = max(0, freq - 2.0)
    return 1.0 / (1.0 + excess * 0.15)


def percentile_rank(series: pd.Series) -> pd.Series:
    """Compute percentile rank (0-100) for a series, handling NaN."""
    return series.rank(pct=True, na_option="bottom") * 100


def percentile_rank_inverted(series: pd.Series) -> pd.Series:
    """For metrics where lower is better (e.g., cost per view)."""
    return (1 - series.rank(pct=True, na_option="top")) * 100


def compute_attention_proxy_score(df: pd.DataFrame) -> pd.DataFrame:
    """Compute attention proxy score from available native metrics.

    Uses canonical attention metrics when available:
    - canonical_hook_rate (3s VTR for Meta, 2s VTR for TikTok)
    - canonical_hold_rate (50% VTR / 3s VTR for Meta, 25% VTR / 2s VTR for TikTok)
    - canonical_completion_rate

    Returns score (0-100) and whether inputs were available.
    If no attention inputs are available, returns NaN (not neutral 50).
    """
    df = df.copy()

    attention_metrics = []
    for col in [
        "canonical_hook_rate",
        "canonical_hold_rate",
        "canonical_completion_rate",
    ]:
        if col in df.columns and df[col].notna().any():
            attention_metrics.append(df[col])

    if attention_metrics:
        # Average percentile rank across available attention metrics
        combined = pd.concat(attention_metrics, axis=1)
        df["attention_proxy_score"] = combined.mean(axis=1).apply(
            lambda x: percentile_rank(pd.Series([x]))[0] if pd.notna(x) else 50.0
        )
        # For groups with multiple rows, use proper percentile ranking
        df["attention_proxy_score"] = 50.0  # Will be overwritten in score_group
        df["attention_inputs_available"] = True
    else:
        df["attention_proxy_score"] = float("nan")
        df["attention_inputs_available"] = False

    return df


def score_group(
    group: pd.DataFrame, metrics_config: dict, weights: dict
) -> pd.DataFrame:
    """Score a group of creatives that share the same objective+platform+buying_type.

    IMPORTANT: Paid and Boosting are scored in entirely separate cohorts.
    Do NOT compare scores across buying_type directly.
    """
    df = group.copy()

    if len(df) < 2:
        df["primary_kpi_score"] = 50.0
        df["secondary_kpi_score"] = 50.0
        df["cost_efficiency_score"] = 50.0
        df["attention_proxy_score"] = 50.0
        df["attention_inputs_available"] = False
        df["score_renormalized"] = True
        df["attention_proxy_weight"] = 0.0
        df["applied_weight_total"] = 0.9
        df["composite_score"] = 50.0
        df["rank_in_group"] = 1
        df["group_size"] = len(df)
        return df

    # Primary metric score (average percentile across primary metrics)
    primary_scores = []
    for metric in metrics_config["primary"]:
        if metric in df.columns and df[metric].notna().any():
            primary_scores.append(percentile_rank(df[metric]))
    if primary_scores:
        df["primary_kpi_score"] = pd.concat(primary_scores, axis=1).mean(axis=1)
    else:
        df["primary_kpi_score"] = 50.0

    # Secondary metric score
    secondary_scores = []
    for metric in metrics_config["secondary"]:
        if metric in df.columns and df[metric].notna().any():
            secondary_scores.append(percentile_rank(df[metric]))
    if secondary_scores:
        df["secondary_kpi_score"] = pd.concat(secondary_scores, axis=1).mean(axis=1)
    else:
        df["secondary_kpi_score"] = 50.0

    # Efficiency score
    eff_metric = metrics_config["efficiency"]
    if eff_metric in df.columns and df[eff_metric].notna().any():
        if metrics_config["efficiency_lower_is_better"]:
            df["cost_efficiency_score"] = percentile_rank_inverted(df[eff_metric])
        else:
            df["cost_efficiency_score"] = percentile_rank(df[eff_metric])
    else:
        df["cost_efficiency_score"] = 50.0

    # Attention Proxy Score (replaces Wooshii)
    # Use pre-computed attention metrics if available
    attention_metrics = []
    for col in [
        "canonical_hook_rate",
        "canonical_hold_rate",
        "canonical_completion_rate",
    ]:
        if col in df.columns and df[col].notna().any():
            attention_metrics.append(percentile_rank(df[col]))

    if attention_metrics:
        df["attention_proxy_score"] = pd.concat(attention_metrics, axis=1).mean(axis=1)
        df["attention_inputs_available"] = True
        df["score_renormalized"] = False
        df["attention_proxy_weight"] = weights["attention_proxy"]
        df["applied_weight_total"] = 1.0
    else:
        # No attention inputs available - renormalize
        df["attention_proxy_score"] = float("nan")
        df["attention_inputs_available"] = False
        df["score_renormalized"] = True
        df["attention_proxy_weight"] = 0.0
        df["applied_weight_total"] = 0.9

    # Compute composite score with appropriate weights
    if df["score_renormalized"].iloc[0]:
        # Use renormalized weights (no attention proxy)
        df["composite_raw"] = (
            df["primary_kpi_score"]
            * weights.get("primary_renormalized", WEIGHTS_RENORMALIZED["primary"])
            + df["secondary_kpi_score"]
            * weights.get("secondary_renormalized", WEIGHTS_RENORMALIZED["secondary"])
            + df["cost_efficiency_score"]
            * weights.get("efficiency_renormalized", WEIGHTS_RENORMALIZED["efficiency"])
        )
    else:
        # Use full weights (attention proxy included)
        df["composite_raw"] = (
            df["primary_kpi_score"] * weights["primary"]
            + df["secondary_kpi_score"] * weights["secondary"]
            + df["cost_efficiency_score"] * weights["efficiency"]
            + df["attention_proxy_score"] * weights["attention_proxy"]
        )

    # Apply frequency penalty
    df["freq_penalty"] = df["frequency"].apply(frequency_penalty)
    df["composite_score"] = df["composite_raw"] * df["freq_penalty"]

    # Apply audience consistency adjustment
    # Creatives that perform consistently across audiences keep their score.
    # Inconsistent creatives are moderated toward the group average.
    # This prevents a creative that got lucky with one audience from ranking #1.
    if "audience_consistency" in df.columns:
        group_avg = df["composite_score"].mean()
        df["composite_score"] = df["composite_score"] * df[
            "audience_consistency"
        ] + group_avg * (1 - df["audience_consistency"])

    # Cap low-confidence creatives
    df.loc[df["low_confidence"], "composite_score"] = df.loc[
        df["low_confidence"], "composite_score"
    ].clip(upper=80)

    # Rank within group
    df["rank_in_group"] = (
        df["composite_score"].rank(ascending=False, method="min").astype(int)
    )
    df["group_size"] = len(df)

    return df


def _expected_completion_rate(duration: float) -> float:
    """Expected 100% completion rate for a given video duration (empirical baseline)."""
    if pd.isna(duration) or duration <= 0:
        return 1.0
    elif duration <= 15:
        return 3.5
    elif duration <= 30:
        return 2.4
    elif duration <= 60:
        return 0.9
    return 0.5


def score_raw_variants(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Score individual ad-line variants preserving OS/audience split dimensions.

    Applies the same objective-aligned scoring as score_creatives but at the raw
    ad-line level so iOS vs Android, different audience segments, and Brand vs Creator
    creatives can be compared directly within each group.

    Paid and Boosting variants are kept in separate scoring cohorts so they are
    only ranked against peers with the same buying type.

    IMPORTANT: Scores are NOT comparable across buying_type cohorts.

    Audience consistency is not applicable here (it's a cross-variant metric)
    so variants are scored purely on their own performance metrics.
    """
    df = df_raw.copy()

    # Derived rate metrics (mirror what load_data computes on the aggregated df)
    imp = df["impressions"].replace(0, float("nan"))
    df["ctr"] = (df["clicks"] / imp) * 100
    df["engagement_rate"] = (df["engagements"] / imp) * 100
    df["share_rate"] = (df["shares"] / imp) * 100
    df["cost_per_complete_view"] = df["spend"] / df["video_views_100"].replace(
        0, float("nan")
    )
    df["reach_per_pound"] = df["reach"] / df["spend"].replace(0, float("nan"))
    df["cpm"] = (df["spend"] / imp) * 1000
    # frequency may already be in df_raw from source data, but recompute to be safe
    df["frequency"] = df["impressions"] / df["reach"].replace(0, float("nan"))

    # Duration-adjusted completion (inline to avoid circular import with loader)
    df["expected_completion"] = df["duration_s"].apply(_expected_completion_rate)
    df["completion_vs_expected"] = df["completion_rate"] / df[
        "expected_completion"
    ].replace(0, float("nan"))

    # Audience consistency doesn't apply at variant level — neutral score
    df["audience_consistency"] = 1.0
    df["low_confidence"] = (df["spend"] < 500) | (df["reach"] < 10000)

    # Ensure buying_type exists (default to 'Paid' for backwards compatibility)
    if "buying_type" not in df.columns:
        df["buying_type"] = "Paid"

    # Ensure format_canonical exists for format-aware scoring
    if "format_canonical" not in df.columns:
        df["format_canonical"] = df.get("format", pd.Series("Unknown", index=df.index))

    scored_groups = []
    for (objective, platform, buying_type, fmt), group in df.groupby(
        ["objective", "platform", "buying_type", "format_canonical"]
    ):
        metrics_config = get_metrics_config(objective, fmt)
        scored = score_group(group.copy(), metrics_config, WEIGHTS_FULL)
        fmt_label = f" [{fmt}]" if is_static_format(fmt) else ""
        scored["scoring_group"] = f"{objective} | {platform} | {buying_type}{fmt_label}"
        scored_groups.append(scored)

    if not scored_groups:
        return df

    result = pd.concat(scored_groups, ignore_index=True)
    result["composite_score"] = result["composite_score"].round(1)
    result["tier"] = pd.cut(
        result["composite_score"],
        bins=[0, 25, 50, 70, 85, 100],
        labels=["Poor", "Below Average", "Average", "Strong", "Top Performer"],
        include_lowest=True,
    )

    sort_cols = [
        c
        for c in ["creative_name", "platform", "os_target", "audience_segment"]
        if c in result.columns
    ]
    return result.sort_values(sort_cols)


def assign_action(row: pd.Series) -> str:
    """Translate score + frequency + confidence into a plain-English recommended action."""
    score = row.get("composite_score", 0) or 0
    freq = row.get("frequency", 0) or 0
    low_conf = bool(row.get("low_confidence", False))
    spend = row.get("spend", 0) or 0

    if score >= 70:
        if low_conf:
            return "Keep Running — Low Data"
        if freq > 3.5:
            return "Keep Running — Refresh Creative"
        return "Scale Up"
    if score >= 50:
        if low_conf:
            return "Monitor — Low Data"
        if freq > 3.5:
            return "Optimise — Frequency Too High"
        return "Keep running"
    if score >= 25:
        if freq > 3.5:
            return "Consider Pausing — Fatigued"
        if spend > 5000:
            return "Consider Pausing — Budget Wasted"
        return "Review"
    # score < 25
    if spend > 2000:
        return "Pause — Wasting Budget"
    return "Pause"


def score_creatives(df: pd.DataFrame) -> pd.DataFrame:
    """Score all creatives, grouped by objective + platform + buying_type.

    IMPORTANT: Paid and Boosting are scored in entirely separate cohorts.
    Do NOT compare scores across buying_type directly.

    A Boosting creative is always ranked against other Boosting creatives;
    a Paid creative against other Paid creatives. The scoring method and
    weights are identical — only the peer group changes.
    """
    # Ensure buying_type exists (default to 'Paid' for backwards compatibility)
    if "buying_type" not in df.columns:
        df = df.copy()
        df["buying_type"] = "Paid"

    # Ensure format_canonical exists for format-aware scoring
    if "format_canonical" not in df.columns:
        df = df.copy()
        df["format_canonical"] = df.get("format", pd.Series("Unknown", index=df.index))

    scored_groups = []

    for (objective, platform, buying_type, fmt), group in df.groupby(
        ["objective", "platform", "buying_type", "format_canonical"]
    ):
        metrics_config = get_metrics_config(objective, fmt)
        scored = score_group(group, metrics_config, WEIGHTS_FULL)
        fmt_label = f" [{fmt}]" if is_static_format(fmt) else ""
        scored["scoring_group"] = f"{objective} | {platform} | {buying_type}{fmt_label}"
        scored_groups.append(scored)

    result = pd.concat(scored_groups, ignore_index=True)
    result["composite_score"] = result["composite_score"].clip(upper=100).round(1)

    # Assign performance tier
    result["tier"] = pd.cut(
        result["composite_score"],
        bins=[0, 25, 50, 70, 85, 100],
        labels=["Poor", "Below Average", "Average", "Strong", "Top Performer"],
        include_lowest=True,
    )

    # Recommended action per creative
    result["action"] = result.apply(assign_action, axis=1)

    # Format-specific flags
    result["format_flag"] = ""
    stories_mask = result["format"].str.contains("Stories", case=False, na=False)
    high_completion_stories = stories_mask & (result["completion_rate"] > 5)
    result.loc[high_completion_stories, "format_flag"] = "Exceptional for Stories"

    return result.sort_values("composite_score", ascending=False)
