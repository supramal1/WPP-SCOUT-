"use client";

import React, { useState, useMemo } from "react";
import type { Creative, GroupBy } from "@/lib/types";
import { TIER_COLORS, getTier } from "@/lib/types";

interface ComparisonTableProps {
  creatives: Creative[];
  groupBy?: GroupBy;
}

const DIMENSION_OPTIONS: { label: string; field: keyof Creative }[] = [
  { label: "OS", field: "os_target" },
  { label: "Asset Type", field: "asset_type_subtype" },
  { label: "Platform", field: "platform" },
  { label: "Placement", field: "placement" },
  { label: "Objective", field: "objective" },
  { label: "Buying Type", field: "buying_type" },
  { label: "Format", field: "format" },
];

const ALL_METRICS: {
  key: string;
  label: string;
  format: (v: number) => string;
  aggregate: "spend-weighted" | "impression-weighted" | "sum" | "derived";
}[] = [
  { key: "composite_score", label: "Score", format: (v) => v.toFixed(1), aggregate: "spend-weighted" },
  { key: "vtr_2s", label: "VTR", format: (v) => `${v.toFixed(1)}%`, aggregate: "impression-weighted" },
  { key: "completion_rate", label: "Comp%", format: (v) => `${v.toFixed(1)}%`, aggregate: "impression-weighted" },
  { key: "ctr", label: "CTR", format: (v) => `${v.toFixed(3)}%`, aggregate: "impression-weighted" },
  { key: "engagement_rate", label: "Eng%", format: (v) => `${v.toFixed(2)}%`, aggregate: "impression-weighted" },
  { key: "share_rate", label: "Share%", format: (v) => `${v.toFixed(2)}%`, aggregate: "impression-weighted" },
  { key: "spend", label: "Spend", format: (v) => `\u00A3${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, aggregate: "sum" },
  { key: "reach", label: "Reach", format: (v) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }), aggregate: "sum" },
  { key: "impressions", label: "Impr.", format: (v) => v.toLocaleString(undefined, { maximumFractionDigits: 0 }), aggregate: "sum" },
  { key: "cpm", label: "CPM", format: (v) => `\u00A3${v.toFixed(2)}`, aggregate: "derived" },
  { key: "frequency", label: "Freq", format: (v) => v.toFixed(2), aggregate: "derived" },
  { key: "cost_per_complete_view", label: "CPCV", format: (v) => `\u00A3${v.toFixed(3)}`, aggregate: "spend-weighted" },
  { key: "reach_per_pound", label: "Reach/\u00A3", format: (v) => v.toFixed(1), aggregate: "derived" },
  { key: "completion_vs_expected", label: "Comp vs Exp", format: (v) => `${v > 0 ? "+" : ""}${v.toFixed(1)}%`, aggregate: "impression-weighted" },
];

const DEFAULT_SELECTED = ["composite_score", "vtr_2s", "completion_rate", "spend", "reach"];

function aggregateCell(items: Creative[]): Record<string, number> {
  if (items.length === 0) return {};

  const totalSpend = items.reduce((s, c) => s + c.spend, 0);
  const totalImpressions = items.reduce((s, c) => s + c.impressions, 0);
  const totalReach = items.reduce((s, c) => s + c.reach, 0);

  const spendWeighted = (field: keyof Creative) =>
    totalSpend > 0
      ? items.reduce((s, c) => s + (c[field] as number ?? 0) * c.spend, 0) / totalSpend
      : items.reduce((s, c) => s + (c[field] as number ?? 0), 0) / items.length;

  const impressionWeighted = (field: keyof Creative) =>
    totalImpressions > 0
      ? items.reduce((s, c) => s + (c[field] as number ?? 0) * c.impressions, 0) / totalImpressions
      : 0;

  const totalCompletions = items.reduce(
    (s, c) => s + (c.completion_rate * c.impressions) / 100,
    0
  );

  return {
    composite_score: Math.round(spendWeighted("composite_score") * 10) / 10,
    vtr_2s: Math.round(impressionWeighted("vtr_2s") * 10) / 10,
    completion_rate: Math.round(impressionWeighted("completion_rate") * 10) / 10,
    ctr: totalImpressions > 0
      ? Math.round(items.reduce((s, c) => s + (c.ctr * c.impressions) / 100, 0) / totalImpressions * 100 * 1000) / 1000
      : 0,
    engagement_rate: totalImpressions > 0
      ? Math.round(items.reduce((s, c) => s + (c.engagement_rate * c.impressions) / 100, 0) / totalImpressions * 100 * 1000) / 1000
      : 0,
    share_rate: totalImpressions > 0
      ? Math.round(items.reduce((s, c) => s + (c.share_rate * c.impressions) / 100, 0) / totalImpressions * 100 * 1000) / 1000
      : 0,
    spend: totalSpend,
    reach: totalReach,
    impressions: totalImpressions,
    cpm: totalImpressions > 0 ? Math.round((totalSpend / totalImpressions) * 1000 * 100) / 100 : 0,
    frequency: totalReach > 0 ? Math.round((totalImpressions / totalReach) * 100) / 100 : 0,
    cost_per_complete_view: totalCompletions > 0 ? Math.round((totalSpend / totalCompletions) * 1000) / 1000 : 0,
    reach_per_pound: totalSpend > 0 ? Math.round((totalReach / totalSpend) * 10) / 10 : 0,
    completion_vs_expected: Math.round(impressionWeighted("completion_vs_expected") * 10) / 10,
  };
}

export function ComparisonTable({ creatives, groupBy = "creative_name" }: ComparisonTableProps) {
  const [dimIndex, setDimIndex] = useState(0);
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>(DEFAULT_SELECTED);
  const dim = DIMENSION_OPTIONS[dimIndex];
  const activeMetrics = ALL_METRICS.filter((m) => selectedMetrics.includes(m.key));

  const toggleMetric = (key: string) => {
    setSelectedMetrics((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const dimValues = useMemo(() => {
    const vals = new Set(creatives.map((c) => String(c[dim.field])));
    // Ensure Asset Type always shows Brand, Creator, Partner
    if (dim.field === "asset_type_subtype") {
      vals.add("Brand");
      vals.add("Creator");
      vals.add("Partner");
    }
    return [...vals].filter(Boolean).sort();
  }, [creatives, dim.field]);

  const rows = useMemo(() => {
    const byName = new Map<string, Map<string, Creative[]>>();
    const nameKey = groupBy === "concept" ? "concept" : "creative_name";
    for (const c of creatives) {
      const dv = String(c[dim.field]);
      const rowKey = c[nameKey] || c.creative_name;
      if (!byName.has(rowKey))
        byName.set(rowKey, new Map());
      const inner = byName.get(rowKey)!;
      if (!inner.has(dv)) inner.set(dv, []);
      inner.get(dv)!.push(c);
    }

    return Array.from(byName.entries())
      .map(([name, dimMap]) => {
        const cells: Record<string, Record<string, number>> = {};
        for (const dv of dimValues) {
          const items = dimMap.get(dv) || [];
          cells[dv] = aggregateCell(items);
        }

        const scores = dimValues
          .map((dv) => cells[dv]?.composite_score || 0)
          .filter((s) => s > 0);
        const avgScore =
          scores.length > 0
            ? scores.reduce((a, b) => a + b, 0) / scores.length
            : 0;

        return { name, cells, avgScore };
      })
      .sort((a, b) => b.avgScore - a.avgScore);
  }, [creatives, dim.field, dimValues, groupBy]);

  if (dimValues.length === 0) {
    return (
      <div className="rounded-lg border border-[#dadce0] bg-white p-8 text-center">
        <p className="text-sm text-[#5f6368]">
          No comparison data available.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Dimension picker */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs text-[#5f6368] mr-1">Compare by</span>
        {DIMENSION_OPTIONS.map((d, i) => (
          <button
            key={d.label}
            onClick={() => setDimIndex(i)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              dimIndex === i
                ? "bg-[#1a73e8] text-white"
                : "bg-[#f1f3f4] text-[#5f6368] hover:bg-[#e8eaed]"
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      {/* Metric toggle pills */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs text-[#5f6368] mr-1">Metrics</span>
        {ALL_METRICS.map((m) => (
          <button
            key={m.key}
            onClick={() => toggleMetric(m.key)}
            className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors ${
              selectedMetrics.includes(m.key)
                ? "bg-[#e8f0fe] text-[#1a73e8]"
                : "bg-[#f1f3f4] text-[#80868b] hover:bg-[#e8eaed]"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="rounded-lg border border-[#dadce0] bg-white overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-[#f8f9fa]">
                <th className="text-left px-3 py-2 text-[#5f6368] font-medium sticky left-0 bg-[#f8f9fa] z-10 min-w-[200px]">
                  {groupBy === "concept" ? "Concept" : "Creative"}
                </th>
                {dimValues.map((dv) => (
                  <th
                    key={dv}
                    colSpan={activeMetrics.length}
                    className="text-center px-2 py-2 text-[#202124] font-medium border-l border-[#e8eaed]"
                  >
                    {dv}
                  </th>
                ))}
              </tr>
              <tr className="bg-[#f8f9fa] border-t border-[#e8eaed]">
                <th className="sticky left-0 bg-[#f8f9fa] z-10" />
                {dimValues.flatMap((dv) =>
                  activeMetrics.map((m, mi) => (
                    <th
                      key={`${dv}-${m.key}`}
                      className={`text-right px-2 py-1.5 text-[10px] text-[#80868b] font-medium ${
                        mi === 0
                          ? "border-l border-[#e8eaed]"
                          : "border-l border-[#f1f3f4]"
                      }`}
                    >
                      {m.label}
                    </th>
                  ))
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr
                  key={`${row.name}-${ri}`}
                  className="border-t border-[#f1f3f4] hover:bg-[#f8f9fa] transition-colors"
                >
                  <td className="px-3 py-2 font-medium text-[#202124] max-w-[250px] truncate sticky left-0 bg-white z-10">
                    {row.name}
                  </td>
                  {dimValues.flatMap((dv) =>
                    activeMetrics.map((m, mi) => {
                      const val = row.cells[dv]?.[m.key] ?? 0;
                      const isEmpty =
                        !row.cells[dv] ||
                        Object.keys(row.cells[dv]).length === 0;
                      if (isEmpty) {
                        return (
                          <td
                            key={`${dv}-${m.key}`}
                            className={`text-right px-2 py-2 text-[#80868b] ${
                              mi === 0
                                ? "border-l border-[#e8eaed]"
                                : "border-l border-[#f1f3f4]"
                            }`}
                          >
                            &mdash;
                          </td>
                        );
                      }
                      const isScore = m.key === "composite_score";
                      const tier = isScore ? getTier(val) : "";
                      return (
                        <td
                          key={`${dv}-${m.key}`}
                          className={`text-right px-2 py-2 font-mono ${
                            mi === 0
                              ? "border-l border-[#e8eaed]"
                              : "border-l border-[#f1f3f4]"
                          }`}
                          style={
                            isScore
                              ? { color: TIER_COLORS[tier] }
                              : { color: "#202124" }
                          }
                        >
                          {m.format(val)}
                        </td>
                      );
                    })
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <p className="text-[11px] text-[#5f6368]">
        {rows.length} {groupBy === "concept" ? "concepts" : "creatives"} &middot; {dimValues.length}{" "}
        {dim.label.toLowerCase()} values &middot; {activeMetrics.length} metrics
        selected
      </p>
    </div>
  );
}
