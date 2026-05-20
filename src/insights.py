from typing import Any

import pandas as pd

from src.scorer import DEFAULT_RANK_METRIC, METHODOLOGY_VERSION


def _safe_val(value: Any):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def _creative_record(row: pd.Series) -> dict:
    fields = [
        "creative_name",
        "concept",
        "platform",
        "objective",
        "format_canonical",
        "placement",
        "placement_canonical",
        "composite_score",
        "combined_scout_score",
        "creative_quality_score",
        "media_efficiency_overlay_score",
        "methodology_version",
        "source_grain",
        "directional_only",
        "score_caveats",
        "scoring_group",
        "group_size",
        "rank_in_group",
        "youtube_measurement_family",
        "tier",
        "action",
        "spend",
        "reach",
        "impressions",
        "frequency",
        "low_confidence",
        "explanation",
    ]
    return {field: _safe_val(row.get(field)) for field in fields if field in row}


def _tier_for_score(score: float) -> str:
    if score >= 85:
        return "Top Performer"
    if score >= 70:
        return "Strong"
    if score >= 50:
        return "Average"
    if score >= 25:
        return "Below Average"
    return "Poor"


def _weighted_average(group: pd.DataFrame, value_col: str, weight_col: str) -> float:
    values = pd.to_numeric(group[value_col], errors="coerce").fillna(0)
    weights = pd.to_numeric(group[weight_col], errors="coerce").fillna(0)
    if weights.sum() > 0:
        return float((values * weights).sum() / weights.sum())
    if len(values):
        return float(values.mean())
    return 0.0


def _concept_series(scored: pd.DataFrame) -> pd.Series:
    if "concept" in scored.columns:
        concept = scored["concept"].fillna("").astype(str).str.strip()
        return concept.where(concept != "", scored["creative_name"].astype(str))
    return scored["creative_name"].astype(str)


def _concept_rows(scored: pd.DataFrame, include_low_confidence: bool) -> pd.DataFrame:
    rows = scored.copy()
    rows["_concept_rollup_key"] = _concept_series(rows)
    if not include_low_confidence and "low_confidence" in rows.columns:
        rows = rows[~rows["low_confidence"].fillna(False).astype(bool)]
    return rows


def _concept_record(concept: str, group: pd.DataFrame, top_variation_limit: int = 3) -> dict:
    spend = float(pd.to_numeric(group["spend"], errors="coerce").fillna(0).sum())
    impressions = float(pd.to_numeric(group["impressions"], errors="coerce").fillna(0).sum())
    reach = float(pd.to_numeric(group["reach"], errors="coerce").fillna(0).sum())
    score = round(_weighted_average(group, "composite_score", "spend"), 1)

    def weighted_metric(column: str) -> float:
        if column not in group.columns:
            return 0.0
        return round(_weighted_average(group, column, "impressions"), 4)

    top_variations = group.sort_values("composite_score", ascending=False).head(top_variation_limit)
    low_confidence_count = (
        int(group["low_confidence"].fillna(False).astype(bool).sum())
        if "low_confidence" in group.columns
        else 0
    )
    actions = (
        sorted(group["action"].dropna().astype(str).unique().tolist())
        if "action" in group.columns
        else []
    )

    return {
        "concept": _safe_val(concept),
        "composite_score": score,
        "tier": _tier_for_score(score),
        "n_creative_rows": int(len(group)),
        "n_unique_creatives": int(group["creative_name"].dropna().nunique())
        if "creative_name" in group.columns
        else int(len(group)),
        "platforms": sorted(group["platform"].dropna().astype(str).unique().tolist())
        if "platform" in group.columns
        else [],
        "objectives": sorted(group["objective"].dropna().astype(str).unique().tolist())
        if "objective" in group.columns
        else [],
        "formats": sorted(group["format_canonical"].dropna().astype(str).unique().tolist())
        if "format_canonical" in group.columns
        else [],
        "actions": actions,
        "spend": round(spend, 2),
        "reach": round(reach, 2),
        "impressions": round(impressions, 2),
        "frequency": round(impressions / reach, 4) if reach else 0.0,
        "vtr_2s": weighted_metric("vtr_2s"),
        "completion_rate": weighted_metric("completion_rate"),
        "ctr": weighted_metric("ctr"),
        "engagement_rate": weighted_metric("engagement_rate"),
        "best_variation_score": _safe_val(group["composite_score"].max()),
        "worst_variation_score": _safe_val(group["composite_score"].min()),
        "low_confidence_rows": low_confidence_count,
        "top_variations": [
            _creative_record(row) for _, row in top_variations.iterrows()
        ],
    }


def _placement_summary(group: pd.DataFrame) -> list[dict]:
    placement_col = next(
        (
            col
            for col in ["placement_canonical", "placement", "placement_raw"]
            if col in group.columns
        ),
        None,
    )
    if placement_col is None:
        return []

    rows = []
    for placement, placement_group in group.groupby(placement_col, dropna=False):
        record = _concept_record(str(placement), placement_group, top_variation_limit=2)
        rows.append(
            {
                "placement": _safe_val(placement),
                "composite_score": record["composite_score"],
                "tier": record["tier"],
                "n_creative_rows": record["n_creative_rows"],
                "spend": record["spend"],
                "reach": record["reach"],
                "impressions": record["impressions"],
                "frequency": record["frequency"],
                "vtr_2s": record["vtr_2s"],
                "completion_rate": record["completion_rate"],
                "ctr": record["ctr"],
                "engagement_rate": record["engagement_rate"],
                "best_variation_score": record["best_variation_score"],
                "worst_variation_score": record["worst_variation_score"],
                "top_variations": record["top_variations"],
            }
        )
    return sorted(rows, key=lambda row: row["spend"], reverse=True)


def _ok(data, warnings=None, next_actions=None) -> dict:
    return {
        "status": "ok",
        "data": data,
        "warnings": warnings or [],
        "next_actions": next_actions or [],
    }


def get_data_quality_report(df_raw: pd.DataFrame, scored: pd.DataFrame) -> dict:
    warnings = []
    required = ["creative_name", "platform", "objective", "spend", "impressions"]
    missing_columns = [col for col in required if col not in df_raw.columns]
    if missing_columns:
        warnings.append("Missing required columns: " + ", ".join(missing_columns))

    low_confidence_count = (
        int(scored["low_confidence"].sum()) if "low_confidence" in scored.columns else 0
    )
    if low_confidence_count:
        warnings.append(f"{low_confidence_count} low-confidence creative(s) need more data.")

    zero_heavy_columns = []
    for col in ["spend", "reach", "impressions", "clicks"]:
        if col in df_raw.columns:
            values = pd.to_numeric(df_raw[col], errors="coerce").fillna(0)
            if len(values) and (values == 0).mean() >= 0.8:
                zero_heavy_columns.append(col)
    if zero_heavy_columns:
        warnings.append("Mostly zero columns: " + ", ".join(zero_heavy_columns))

    small_cohort_count = 0
    if "group_size" in scored.columns:
        group_size = pd.to_numeric(scored["group_size"], errors="coerce").fillna(0)
        small_cohort_count = int(((group_size > 0) & (group_size < 8)).sum())
        if small_cohort_count:
            warnings.append(
                f"{small_cohort_count} creative(s) are in small scoring cohorts; rankings are directional only."
            )

    data = {
        "raw_rows": int(len(df_raw)),
        "scored_creatives": int(len(scored)),
        "platforms": sorted(df_raw["platform"].dropna().astype(str).unique().tolist())
        if "platform" in df_raw.columns
        else [],
        "objectives": sorted(df_raw["objective"].dropna().astype(str).unique().tolist())
        if "objective" in df_raw.columns
        else [],
        "low_confidence_creatives": low_confidence_count,
        "zero_heavy_columns": zero_heavy_columns,
        "missing_columns": missing_columns,
        "small_scoring_cohort_creatives": small_cohort_count,
        "methodology_version": METHODOLOGY_VERSION,
        "default_rank_metric": DEFAULT_RANK_METRIC,
    }
    return _ok(data, warnings=warnings)


def get_score_breakdown(scored: pd.DataFrame, creative_name: str) -> dict:
    match = scored[
        scored["creative_name"]
        .astype(str)
        .str.contains(creative_name, case=False, na=False, regex=False)
    ]
    if match.empty:
        return {"status": "not_found", "data": None, "warnings": [f"No creative found matching {creative_name!r}"], "next_actions": []}

    row = match.sort_values("composite_score", ascending=False).iloc[0]
    data = _creative_record(row)
    data["score_components"] = {
        "primary_kpi_score": _safe_val(row.get("primary_kpi_score")),
        "secondary_kpi_score": _safe_val(row.get("secondary_kpi_score")),
        "cost_efficiency_score": _safe_val(row.get("cost_efficiency_score")),
        "attention_proxy_score": _safe_val(row.get("attention_proxy_score")),
        "creative_quality_score": _safe_val(row.get("creative_quality_score")),
        "media_efficiency_overlay_score": _safe_val(
            row.get("media_efficiency_overlay_score")
        ),
        "combined_scout_score": _safe_val(row.get("combined_scout_score")),
    }
    return _ok(data)


def get_fatigue_risks(scored: pd.DataFrame, limit: int = 10) -> dict:
    if "frequency" not in scored.columns:
        return _ok([], warnings=["No frequency column available."])
    risks = scored[pd.to_numeric(scored["frequency"], errors="coerce").fillna(0) >= 3.5]
    risks = risks.sort_values(["frequency", "spend"], ascending=False).head(limit)
    return _ok([_creative_record(row) for _, row in risks.iterrows()])


def get_low_confidence_creatives(scored: pd.DataFrame, limit: int = 20) -> dict:
    if "low_confidence" not in scored.columns:
        return _ok([], warnings=["No low_confidence column available."])
    low_data = scored[scored["low_confidence"]].sort_values("spend", ascending=False)
    return _ok([_creative_record(row) for _, row in low_data.head(limit).iterrows()])


def get_concept_rankings(
    scored: pd.DataFrame,
    limit: int = 10,
    platform: str | None = None,
    objective: str | None = None,
    sort: str = "top",
    include_low_confidence: bool = False,
) -> dict:
    rows = _concept_rows(scored, include_low_confidence=include_low_confidence)
    if platform and platform != "All" and "platform" in rows.columns:
        rows = rows[rows["platform"].astype(str) == platform]
    if objective and "objective" in rows.columns:
        rows = rows[rows["objective"].astype(str).str.contains(objective, case=False, na=False)]

    if rows.empty:
        return _ok([], warnings=["No concept rows matched the requested filters."])

    records = [
        _concept_record(concept, group)
        for concept, group in rows.groupby("_concept_rollup_key", dropna=False)
    ]
    reverse = sort != "bottom"
    records = sorted(records, key=lambda item: item["composite_score"], reverse=reverse)
    return _ok(records[:limit])


def get_concept_deep_dive(
    scored: pd.DataFrame,
    concept: str,
    include_low_confidence: bool = True,
) -> dict:
    rows = _concept_rows(scored, include_low_confidence=include_low_confidence)
    match = rows[
        rows["_concept_rollup_key"].astype(str).str.contains(concept, case=False, na=False)
    ]
    if match.empty:
        return {
            "status": "not_found",
            "data": None,
            "warnings": [f"No concept found matching {concept!r}"],
            "next_actions": [],
        }

    best_key = (
        match.groupby("_concept_rollup_key")["spend"]
        .sum()
        .sort_values(ascending=False)
        .index[0]
    )
    group = rows[rows["_concept_rollup_key"] == best_key]
    rollup = _concept_record(str(best_key), group, top_variation_limit=5)
    placement_summary = _placement_summary(group)

    data = {
        "rollup": rollup,
        "creative_rows": [
            _creative_record(row)
            for _, row in group.sort_values("composite_score", ascending=False).iterrows()
        ],
        "placement_summary": placement_summary,
        "interpretation": {
            "concept_level": (
                "Use the concept-level rollup to judge the underlying creative idea across "
                "all matching platform, objective, format, and placement rows."
            ),
            "placement_level": (
                "Use the placement-level rows to see where that concept is driving or losing "
                "performance. Placement scores can differ because each row is scored within its "
                "own platform/objective/format cohort."
            ),
        },
    }
    return _ok(data)


def compare_creatives(scored: pd.DataFrame, creative_names: list[str]) -> dict:
    rows = []
    for name in creative_names:
        match = scored[
            scored["creative_name"]
            .astype(str)
            .str.contains(name, case=False, na=False, regex=False)
        ]
        if not match.empty:
            rows.append(match.sort_values("composite_score", ascending=False).iloc[0])

    if not rows:
        return {"status": "not_found", "data": {"creatives": [], "winner": None}, "warnings": ["No requested creatives found."], "next_actions": []}

    records = [_creative_record(row) for row in rows]
    winner = max(records, key=lambda item: item.get("composite_score") or 0)
    return _ok({"creatives": records, "winner": winner["creative_name"]})


def get_budget_reallocation_recommendations(scored: pd.DataFrame, limit: int = 5) -> dict:
    action_text = scored["action"].fillna("").astype(str) if "action" in scored.columns else ""
    score = pd.to_numeric(scored["composite_score"], errors="coerce").fillna(0)
    low_confidence = (
        scored["low_confidence"].fillna(False).astype(bool)
        if "low_confidence" in scored.columns
        else pd.Series(False, index=scored.index)
    )
    scale_to = scored[(score >= 70) & ~low_confidence]
    scale_from = scored[
        action_text.str.contains("Pause|Fatigued|Budget Wasted", case=False, na=False)
        | (score < 40)
    ]

    scale_to = scale_to.sort_values("composite_score", ascending=False).head(limit)
    scale_from = scale_from.sort_values(["spend", "frequency"], ascending=False).head(limit)

    data = {
        "scale_to": [_creative_record(row) for _, row in scale_to.iterrows()],
        "scale_from": [_creative_record(row) for _, row in scale_from.iterrows()],
    }
    next_actions = []
    if data["scale_to"] and data["scale_from"]:
        next_actions.append("Move budget from scale_from creatives into scale_to creatives after channel-owner review.")
    return _ok(data, next_actions=next_actions)


def find_actionable_insights(df_raw: pd.DataFrame, scored: pd.DataFrame) -> dict:
    quality = get_data_quality_report(df_raw, scored)
    budget = get_budget_reallocation_recommendations(scored)
    fatigue = get_fatigue_risks(scored)
    low_confidence = get_low_confidence_creatives(scored)

    priority_actions = []
    if budget["data"]["scale_to"]:
        priority_actions.append("Scale the strongest high-confidence creative(s).")
    if budget["data"]["scale_from"]:
        priority_actions.append("Review or pause inefficient/fatigued creative(s).")
    if low_confidence["data"]:
        priority_actions.append("Collect more spend/reach before judging low-confidence creative(s).")

    return _ok(
        {
            "priority_actions": priority_actions,
            "budget_reallocation": budget["data"],
            "fatigue_risks": fatigue["data"],
            "low_confidence": low_confidence["data"],
            "data_quality": quality["data"],
        },
        warnings=quality["warnings"],
    )
