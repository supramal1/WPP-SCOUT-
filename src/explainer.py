import pandas as pd


def explain_creative(row: pd.Series) -> str:
    """Generate a plain-English explanation of why a creative performed well or poorly.

    Incorporates attention proxy scoring and renormalization logic.
    """
    parts = []
    score = row["composite_score"]

    # Opening assessment
    if score >= 70:
        parts.append(f"Strong performer (score: {score}/100).")
    elif score >= 50:
        parts.append(f"Average performer (score: {score}/100).")
    else:
        parts.append(f"Underperformer (score: {score}/100).")

    # Aggregation context
    n_variants = row.get("n_variants", 1)
    if n_variants > 1:
        parts.append(f"Based on {int(n_variants)} ad variants combined.")

    # Detect static format
    fmt = str(row.get("format_canonical", row.get("format", ""))).strip().lower()
    is_static = fmt in ("static", "image", "carousel", "static image")

    if is_static:
        # Static assets: lead with ER and CTR (VTR/completion are N/A)
        parts.append(
            "Static asset — scored on Engagement Rate and CTR (VTR not applicable)."
        )
        er = row.get("engagement_rate", 0)
        if er and er > 0 and not pd.isna(er):
            parts.append(f"Engagement rate: {er:.3f}%.")
        ctr = row.get("ctr", 0)
        if ctr and ctr > 0 and not pd.isna(ctr):
            parts.append(f"CTR: {ctr:.3f}%.")
    else:
        # Video/Motion: existing VTR + completion logic
        if row.get("vtr_2s", 0) > 0:
            vtr_label = "3s VTR" if row.get("platform") == "Meta" else "2s VTR"
            parts.append(f"{vtr_label}: {row['vtr_2s']:.1f}%.")

        # Duration-adjusted completion
        cve = row.get("completion_vs_expected", 0)
        duration = row.get("duration_s", 0)
        if cve and not pd.isna(cve) and cve > 0 and row.get("completion_rate", 0) > 0:
            if cve >= 2.0:
                parts.append(
                    f"Completion rate {row['completion_rate']:.2f}% - {cve:.1f}x better than expected for a {int(duration)}s video."
                )
            elif cve >= 1.2:
                parts.append(
                    f"Completion rate {row['completion_rate']:.2f}% - above average for a {int(duration)}s video."
                )
            elif cve < 0.5:
                parts.append(
                    f"Completion rate {row['completion_rate']:.2f}% - below average for a {int(duration)}s video."
                )
            else:
                parts.append(
                    f"Completion rate: {row['completion_rate']:.2f}% ({int(duration)}s video)."
                )

        if row.get("engagement_rate", 0) > 0 and row["platform"] == "Meta":
            parts.append(f"Engagement rate: {row['engagement_rate']:.3f}%.")

    # Spend context
    spend = row.get("spend", 0)
    if row.get("low_confidence", False):
        parts.append(
            f"Low confidence: only €{spend:,.0f} spend / {row['reach']:,.0f} reach - insufficient for reliable conclusions."
        )
    else:
        parts.append(f"€{spend:,.0f} total spend ({row['reach']:,.0f} reach).")

    # Frequency insight
    freq = row.get("frequency", 0)
    if not pd.isna(freq):
        if freq > 4:
            penalty_pct = (1 - row.get("freq_penalty", 1)) * 100
            parts.append(
                f"High frequency ({freq:.1f}x) - audience fatigue likely. Score reduced by {penalty_pct:.0f}%."
            )
        elif freq > 3:
            parts.append(
                f"Moderate frequency ({freq:.1f}x) - approaching fatigue territory."
            )
        elif freq < 1.5 and freq > 0:
            parts.append(f"Low frequency ({freq:.1f}x) - audience is fresh.")

    # Audience consistency
    consistency = row.get("audience_consistency", 1.0)
    n_campaigns = row.get("n_campaigns", 1)
    if not pd.isna(consistency) and n_campaigns > 1:
        if consistency >= 0.95:
            parts.append(
                f"Performed consistently across {int(n_campaigns)} campaigns - results are reliable."
            )
        elif consistency < 0.7:
            parts.append(
                f"Performance varied significantly across {int(n_campaigns)} campaigns - results may be audience-dependent rather than creative quality."
            )

    # Cost efficiency (skip CPCV for statics — not meaningful)
    if not is_static:
        cpcv = row.get("cost_per_complete_view", 0)
        if cpcv and cpcv > 0 and not pd.isna(cpcv):
            parts.append(f"Cost per complete view: €{cpcv:.2f}.")

    # Attention Proxy (replaces Wooshii explanation)
    attention_available = row.get("attention_inputs_available", False)
    attention_score = row.get("attention_proxy_score")

    if attention_available and not pd.isna(attention_score):
        parts.append(
            f"Native attention proxy score: {attention_score:.1f}/100 (based on hook rate, hold rate, and completion patterns)."
        )
    elif row.get("score_renormalized", False):
        parts.append(
            "Score renormalized across remaining components (no attention proxy inputs available for this cohort)."
        )

    # Asset type context (Brand vs Creator)
    asset_type = row.get("asset_type_canonical", row.get("asset_type", ""))
    if asset_type and asset_type in ("Brand", "Creator"):
        parts.append(f"Asset type: {asset_type}.")

    # OS context (if split data available)
    os_target = row.get("os_target", "")
    if os_target and os_target not in ("", "All", "nan"):
        parts.append(f"Target OS: {os_target}.")

    # Format flag
    if row.get("format_flag"):
        parts.append(
            f"Note: {row['format_flag']} - unusually high engagement for this placement type."
        )

    # Recommendation
    if score >= 70:
        parts.append(
            "Recommendation: Scale spend or use as a template for future creative."
        )
    elif score < 40 and not row.get("low_confidence", False):
        parts.append(
            "Recommendation: Consider pausing and replacing with higher-performing variants."
        )
    elif row.get("low_confidence", False) and score > 50:
        parts.append("Recommendation: Shows promise but needs more spend to validate.")

    return " ".join(parts)


def explain_dimensional_patterns(df: pd.DataFrame) -> dict:
    """Analyze performance patterns across dimensions.

    Returns insights about which combinations of dimensions perform well or poorly.
    Used for generating dashboard-level insights like "Creator wins on TikTok In-Feed for Android".
    """
    insights = {}

    # OS × Platform patterns
    if "os_target" in df.columns and df["os_target"].notna().any():
        os_platform = (
            df.groupby(["os_target", "platform"])
            .agg(
                {"composite_score": "mean", "vtr_2s": "mean", "creative_name": "count"}
            )
            .reset_index()
        )
        os_platform = os_platform[os_platform["os_target"].isin(["iOS", "Android"])]
        if not os_platform.empty:
            best_idx = os_platform["composite_score"].idxmax()
            row = os_platform.loc[best_idx]
            insights["os_platform_winner"] = {
                "os": row["os_target"],
                "platform": row["platform"],
                "avg_score": round(row["composite_score"], 1),
                "avg_vtr": round(row["vtr_2s"], 1),
                "n_creatives": int(row["creative_name"]),
            }

    # Asset Type × Platform patterns
    if (
        "asset_type_canonical" in df.columns
        and df["asset_type_canonical"].notna().any()
    ):
        asset_platform = (
            df.groupby(["asset_type_canonical", "platform"])
            .agg(
                {"composite_score": "mean", "vtr_2s": "mean", "creative_name": "count"}
            )
            .reset_index()
        )
        if not asset_platform.empty:
            best_idx = asset_platform["composite_score"].idxmax()
            row = asset_platform.loc[best_idx]
            insights["asset_platform_winner"] = {
                "asset_type": row["asset_type_canonical"],
                "platform": row["platform"],
                "avg_score": round(row["composite_score"], 1),
                "avg_vtr": round(row["vtr_2s"], 1),
                "n_creatives": int(row["creative_name"]),
            }

    # Objective × Format patterns
    if "objective" in df.columns and "format" in df.columns:
        obj_format = (
            df.groupby(["objective", "format"])
            .agg({"composite_score": "mean", "creative_name": "count"})
            .reset_index()
        )
        if not obj_format.empty:
            best_idx = obj_format["composite_score"].idxmax()
            row = obj_format.loc[best_idx]
            insights["objective_format_winner"] = {
                "objective": row["objective"],
                "format": row["format"],
                "avg_score": round(row["composite_score"], 1),
                "n_creatives": int(row["creative_name"]),
            }

    return insights


def generate_dimension_insights(df: pd.DataFrame) -> list[str]:
    """Generate human-readable insights about dimensional patterns."""
    patterns = explain_dimensional_patterns(df)
    insights = []

    if "os_platform_winner" in patterns:
        p = patterns["os_platform_winner"]
        insights.append(
            f"{p['os']} outperforms on {p['platform']} "
            f"(avg score {p['avg_score']}, VTR {p['avg_vtr']}%) across {p['n_creatives']} creatives."
        )

    if "asset_platform_winner" in patterns:
        p = patterns["asset_platform_winner"]
        insights.append(
            f"{p['asset_type']} creatives win on {p['platform']} "
            f"(avg score {p['avg_score']}, VTR {p['avg_vtr']}%) across {p['n_creatives']} assets."
        )

    if "objective_format_winner" in patterns:
        p = patterns["objective_format_winner"]
        insights.append(
            f"{p['format']} is the best format for {p['objective']} objective "
            f"(avg score {p['avg_score']}) across {p['n_creatives']} creatives."
        )

    return insights


def generate_explanations(df: pd.DataFrame) -> pd.DataFrame:
    """Add explanation column to scored DataFrame."""
    df = df.copy()
    df["explanation"] = df.apply(explain_creative, axis=1)
    return df
