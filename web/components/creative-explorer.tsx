"use client";

import React, { useState, useMemo } from "react";
import type { Creative, GroupBy } from "@/lib/types";
import { TIER_COLORS, getTier } from "@/lib/types";

interface CreativeExplorerProps {
  creatives: Creative[];
  dimension: string;
  groupBy?: GroupBy;
}

/** Aggregate creatives by concept, returning synthetic Creative objects with weighted metrics. */
function collapseByConceptLocal(items: Creative[]): Creative[] {
  const map = new Map<string, Creative[]>();
  for (const c of items) {
    const key = c.concept || c.creative_name;
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(c);
  }

  return Array.from(map.entries()).map(([concept, cs]) => {
    const totalSpend = cs.reduce((s, c) => s + c.spend, 0);
    const totalImpressions = cs.reduce((s, c) => s + c.impressions, 0);
    const totalReach = cs.reduce((s, c) => s + c.reach, 0);
    const totalClicks = cs.reduce((s, c) => s + (c.ctr * c.impressions) / 100, 0);
    const totalEngagements = cs.reduce((s, c) => s + (c.engagement_rate * c.impressions) / 100, 0);
    const totalCompletions = cs.reduce((s, c) => s + (c.completion_rate * c.impressions) / 100, 0);

    const weightedScore =
      totalSpend > 0
        ? cs.reduce((s, c) => s + c.composite_score * c.spend, 0) / totalSpend
        : cs.reduce((s, c) => s + c.composite_score, 0) / cs.length;
    const weightedVtr =
      totalImpressions > 0
        ? cs.reduce((s, c) => s + c.vtr_2s * c.impressions, 0) / totalImpressions
        : 0;

    return {
      ...cs[0],
      creative_name: concept,
      concept,
      platform: `${cs.length} variation${cs.length === 1 ? "" : "s"}`,
      composite_score: Math.round(weightedScore * 10) / 10,
      tier: getTier(weightedScore),
      spend: totalSpend,
      reach: totalReach,
      impressions: totalImpressions,
      vtr_2s: Math.round(weightedVtr * 10) / 10,
      ctr: totalImpressions > 0 ? Math.round((totalClicks / totalImpressions) * 100 * 1000) / 1000 : 0,
      engagement_rate: totalImpressions > 0 ? Math.round((totalEngagements / totalImpressions) * 100 * 1000) / 1000 : 0,
      completion_rate: totalImpressions > 0 ? Math.round((totalCompletions / totalImpressions) * 100 * 100) / 100 : 0,
      cpm: totalImpressions > 0 ? Math.round((totalSpend / totalImpressions) * 1000 * 100) / 100 : 0,
      frequency: totalReach > 0 ? Math.round((totalImpressions / totalReach) * 100) / 100 : 0,
    } as Creative;
  });
}

const RANGE_OPTIONS = [10, 20, 50, 100] as const;

const KPI_OPTIONS: { key: string; label: string }[] = [
  { key: "composite_score", label: "Score" },
  { key: "vtr_2s", label: "VTR" },
  { key: "completion_rate", label: "Comp%" },
  { key: "ctr", label: "CTR" },
  { key: "spend", label: "Spend" },
  { key: "reach", label: "Reach" },
  { key: "impressions", label: "Impr." },
  { key: "engagement_rate", label: "Eng%" },
  { key: "cpm", label: "CPM" },
];

const DIMENSION_FIELD: Record<string, keyof Creative> = {
  "Asset Type": "asset_type_subtype",
  OS: "os_target",
  Placement: "placement",
  Objective: "objective",
  "Buying Type": "buying_type",
  Format: "format",
};

function formatValue(key: string, value: number | null | undefined): string {
  if (value == null) return "\u2014";
  if (key === "spend")
    return `\u00A3${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (key === "reach" || key === "impressions")
    return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (key === "ctr") return `${value.toFixed(3)}%`;
  if (key === "composite_score") return value.toFixed(1);
  if (key === "cpm") return `\u00A3${value.toFixed(2)}`;
  return `${value.toFixed(1)}%`;
}

export function CreativeExplorer({
  creatives,
  dimension,
  groupBy = "creative_name",
}: CreativeExplorerProps) {
  const isConcept = groupBy === "concept";
  const [showTop, setShowTop] = useState(true);
  const [range, setRange] = useState<number>(50);
  const [selectedKPIs, setSelectedKPIs] = useState<string[]>([
    "composite_score",
    "vtr_2s",
    "completion_rate",
    "ctr",
    "spend",
    "reach",
  ]);

  const field = DIMENSION_FIELD[dimension];

  const groups = useMemo(() => {
    if (!field) return [];
    const map = new Map<string, Creative[]>();
    for (const c of creatives) {
      const key = String(c[field]) || "Unknown";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(c);
    }
    return Array.from(map.entries())
      .map(([name, items]) => {
        const displayItems = isConcept ? collapseByConceptLocal(items) : items;
        return {
          name,
          items: displayItems
            .sort((a, b) =>
              showTop
                ? b.composite_score - a.composite_score
                : a.composite_score - b.composite_score
            )
            .slice(0, range),
          total: displayItems.length,
        };
      })
      .sort((a, b) => b.total - a.total);
  }, [creatives, field, showTop, range, isConcept]);

  const toggleKPI = (key: string) => {
    setSelectedKPIs((prev) =>
      prev.includes(key)
        ? prev.filter((k) => k !== key)
        : [...prev, key]
    );
  };

  if (groups.length === 0) {
    return (
      <div className="rounded-lg border border-[#dadce0] bg-white p-8 text-center">
        <p className="text-sm text-[#5f6368]">
          No data available for this dimension.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Top / Bottom toggle */}
        <div className="flex items-center rounded-full bg-[#f1f3f4] p-0.5">
          <button
            onClick={() => setShowTop(true)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              showTop
                ? "bg-white text-[#202124] shadow-sm"
                : "text-[#5f6368]"
            }`}
          >
            Top
          </button>
          <button
            onClick={() => setShowTop(false)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              !showTop
                ? "bg-white text-[#202124] shadow-sm"
                : "text-[#5f6368]"
            }`}
          >
            Bottom
          </button>
        </div>

        {/* Range */}
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-[#5f6368]">Show</span>
          {RANGE_OPTIONS.map((n) => (
            <button
              key={n}
              onClick={() => setRange(n)}
              className={`h-7 min-w-[28px] px-1.5 rounded-full text-xs font-medium transition-colors ${
                range === n
                  ? "bg-[#1a73e8] text-white"
                  : "bg-[#f1f3f4] text-[#5f6368] hover:bg-[#e8eaed]"
              }`}
            >
              {n}
            </button>
          ))}
        </div>

        {/* Divider */}
        <div className="h-5 w-px bg-[#dadce0]" />

        {/* KPI pills */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {KPI_OPTIONS.map((kpi) => (
            <button
              key={kpi.key}
              onClick={() => toggleKPI(kpi.key)}
              className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors ${
                selectedKPIs.includes(kpi.key)
                  ? "bg-[#e8f0fe] text-[#1a73e8]"
                  : "bg-[#f1f3f4] text-[#80868b] hover:bg-[#e8eaed]"
              }`}
            >
              {kpi.label}
            </button>
          ))}
        </div>
      </div>

      {/* One table per dimension value */}
      {groups.map((group) => (
        <div
          key={group.name}
          className="rounded-lg border border-[#dadce0] bg-white overflow-hidden"
        >
          <div className="px-4 py-2.5 bg-[#f8f9fa] border-b border-[#e8eaed] flex items-center justify-between">
            <h4 className="text-sm font-medium text-[#202124]">
              {group.name}
            </h4>
            <span className="text-[11px] text-[#5f6368] font-mono">
              {showTop ? "Top" : "Bottom"} {group.items.length} of{" "}
              {group.total}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[#e8eaed]">
                  <th className="text-left px-3 py-2 text-[#5f6368] font-medium">
                    {dimension}
                  </th>
                  <th className="text-left px-3 py-2 text-[#5f6368] font-medium">
                    Campaign
                  </th>
                  <th className="text-left px-3 py-2 text-[#5f6368] font-medium">
                    {isConcept ? "Concept" : "Creative"}
                  </th>
                  <th className="text-left px-3 py-2 text-[#5f6368] font-medium">
                    Platform
                  </th>
                  {selectedKPIs.map((k) => (
                    <th
                      key={k}
                      className="text-right px-3 py-2 text-[#5f6368] font-medium"
                    >
                      {KPI_OPTIONS.find((o) => o.key === k)?.label || k}
                    </th>
                  ))}
                  <th className="text-left px-3 py-2 text-[#5f6368] font-medium">
                    Tier
                  </th>
                </tr>
              </thead>
              <tbody>
                {group.items.map((c, i) => {
                  const tier = getTier(c.composite_score);
                  const isGood = c.composite_score >= 70;
                  const isBad = c.composite_score < 25;
                  return (
                    <tr
                      key={`${c.creative_name}-${c.platform}-${i}`}
                      className={`border-t border-[#f1f3f4] transition-colors ${
                        isGood
                          ? "bg-[#e6f4ea]/50"
                          : isBad
                            ? "bg-[#fce8e6]/50"
                            : "hover:bg-[#f8f9fa]"
                      }`}
                    >
                      <td className="px-3 py-2 text-[#5f6368]">
                        {String(c[field!]) || "Unknown"}
                      </td>
                      <td className="px-3 py-2 text-[#5f6368] max-w-[180px] truncate">
                        {c.campaign_normalized}
                      </td>
                      <td className="px-3 py-2 font-medium text-[#202124] max-w-[280px] truncate">
                        {c.creative_name}
                      </td>
                      <td className="px-3 py-2 text-[#5f6368]">
                        {c.platform}
                      </td>
                      {selectedKPIs.map((k) => (
                        <td
                          key={k}
                          className="text-right px-3 py-2 font-mono text-[#202124]"
                        >
                          {k === "composite_score" ? (
                            <span
                              className="font-medium"
                              style={{
                                color: TIER_COLORS[tier] || "#9aa0a6",
                              }}
                            >
                              {formatValue(k, c[k as keyof Creative] as number)}
                            </span>
                          ) : (
                            formatValue(k, c[k as keyof Creative] as number)
                          )}
                        </td>
                      ))}
                      <td className="px-3 py-2">
                        <span
                          className="text-[11px] font-medium"
                          style={{ color: TIER_COLORS[tier] || "#9aa0a6" }}
                        >
                          {tier}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
