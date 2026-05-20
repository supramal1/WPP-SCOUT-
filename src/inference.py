from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DerivedField:
    value: str
    source: str
    evidence_strength: str
    evidence: str
    confidence: float

    def to_preview_dict(self) -> dict[str, str]:
        return {
            "value": self.value,
            "source": self.source,
            "evidence_strength": self.evidence_strength,
            "evidence": self.evidence,
        }


def _normalise_label(value) -> str:
    return " ".join(str(value or "").strip().replace("\n", " ").lower().split())


def _first_existing(df: pd.DataFrame, labels: list[str]) -> pd.Series:
    lookup = {_normalise_label(column): column for column in df.columns}
    for label in labels:
        column = lookup.get(_normalise_label(label))
        if column is not None:
            return df[column].astype(str)
    return pd.Series("", index=df.index)


def _combined_text(df: pd.DataFrame, labels: list[str]) -> pd.Series:
    parts = [_first_existing(df, [label]) for label in labels]
    if not parts:
        return pd.Series("", index=df.index)
    combined = parts[0].fillna("").astype(str)
    for series in parts[1:]:
        combined = combined.str.cat(series.fillna("").astype(str), sep=" ")
    return combined.str.lower()


def _has_column(df: pd.DataFrame, labels: list[str]) -> bool:
    existing = {_normalise_label(column) for column in df.columns}
    return any(_normalise_label(label) in existing for label in labels)


def infer_platform_for_dataframe(df: pd.DataFrame) -> DerivedField:
    text = _combined_text(
        df,
        [
            "platform",
            "Campaign type",
            "Campaign subtype",
            "Advertising channel type",
            "Advertising channel subtype",
            "Site (CM360)",
            "Campaign",
            "campaign_raw",
            "Ad name",
            "ad_name_raw",
            "creative_name",
        ],
    )
    joined = " ".join(text.dropna().head(25).tolist())

    if re.search(r"\b(youtube|you\s*tube|yt|trueview)\b", joined):
        return DerivedField("YouTube", "derived", "strong", "YouTube/YT/TrueView evidence in report fields", 0.9)
    if re.search(r"\b(meta|facebook|instagram|fb|ig)\b", joined):
        return DerivedField("Meta", "derived", "strong", "Meta/Facebook/Instagram evidence in report fields", 0.85)
    if re.search(r"\b(tiktok|tik tok)\b", joined):
        return DerivedField("TikTok", "derived", "strong", "TikTok evidence in report fields", 0.85)
    return DerivedField("Unknown", "missing", "none", "No platform evidence found", 0.0)


def infer_objective_for_dataframe(df: pd.DataFrame) -> DerivedField:
    text = _combined_text(
        df,
        [
            "objective",
            "Campaign goal",
            "Goal type",
            "Optimization goal",
            "Bid strategy type",
            "Campaign type",
            "Campaign subtype",
            "Advertising channel subtype",
            "Campaign",
            "campaign_raw",
            "Ad name",
            "ad_name_raw",
            "creative_name",
        ],
    )
    joined = " ".join(text.dropna().head(25).tolist())

    if re.search(r"\b(tf|target frequency|video_reach_target_frequency)\b", joined):
        return DerivedField("Target Frequency", "derived", "strong", "Target-frequency evidence in campaign taxonomy", 0.9)
    if re.search(r"\b(video_action|action|conversions?|lead|sales)\b", joined):
        return DerivedField("Traffic", "derived", "moderate", "Action/conversion evidence in native campaign fields", 0.75)
    if re.search(r"\b(non[-_ ]?skippable|reach|awareness)\b", joined):
        return DerivedField("Reach", "derived", "moderate", "Reach/non-skippable evidence in native campaign fields", 0.75)
    if re.search(r"\b(video views?|trueview|consideration|mid funnel|views)\b", joined) or _has_column(
        df, ["TrueView views", "TrueView view rate"]
    ):
        return DerivedField("Video Views", "derived", "moderate", "Video-view evidence in native campaign fields", 0.7)
    return DerivedField("Unknown", "missing", "none", "No objective evidence found", 0.0)
