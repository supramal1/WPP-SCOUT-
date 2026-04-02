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

const METRICS: {
  key: string;
  label: string;
  format: (v: number) => string;
}[] = [
  { key: "composite_score", label: "Score", format: (v) => v.toFixed(1) },
  {
    key: "vtr_2s",
    label: "VTR",
    format: (v) => `${v.toFixed(1)}%`,
  },
  {
    key: "completion_rate",
    label: "Comp%",
    format: (v) => `${v.toFixed(1)}%`,
  },
  {
    key: "spend",
    label: "Spend",
    format: (v) =>
      `\u00A3${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
  },
  {
    key: "reach",
    label: "Reach",
    format: (v) =>
      v.toLocaleString(undefined, { maximumFractionDigits: 0 }),
  },
];

export function ComparisonTable({ creatives, groupBy = "creative_name" }: ComparisonTableProps) {
  const [dimIndex, setDimIndex] = useState(0);
  const dim = DIMENSION_OPTIONS[dimIndex];

  const dimValues = useMemo(() => {
    return [
      ...new Set(creatives.map((c) => String(c[dim.field]))),
    ]
      .filter(Boolean)
      .sort();
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
          const totalSpend = items.reduce((s, c) => s + c.spend, 0);
          const totalImpressions = items.reduce(
            (s, c) => s + c.impressions,
            0
          );

          const weightedScore =
            totalSpend > 0
              ? items.reduce(
                  (s, c) => s + c.composite_score * c.spend,
                  0
                ) / totalSpend
              : items.length > 0
                ? items.reduce(
                    (s, c) => s + c.composite_score,
                    0
                  ) / items.length
                : 0;

          const weightedVtr =
            totalImpressions > 0
              ? items.reduce(
                  (s, c) => s + c.vtr_2s * c.impressions,
                  0
                ) / totalImpressions
              : 0;

          const weightedCompletion =
            totalImpressions > 0
              ? items.reduce(
                  (s, c) => s + c.completion_rate * c.impressions,
                  0
                ) / totalImpressions
              : 0;

          cells[dv] = {
            composite_score: Math.round(weightedScore * 10) / 10,
            vtr_2s: Math.round(weightedVtr * 10) / 10,
            completion_rate:
              Math.round(weightedCompletion * 10) / 10,
            spend: totalSpend,
            reach: items.reduce((s, c) => s + c.reach, 0),
          };
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
  }, [creatives, dim.field, dimValues]);

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
                    colSpan={METRICS.length}
                    className="text-center px-2 py-2 text-[#202124] font-medium border-l border-[#e8eaed]"
                  >
                    {dv}
                  </th>
                ))}
              </tr>
              <tr className="bg-[#f8f9fa] border-t border-[#e8eaed]">
                <th className="sticky left-0 bg-[#f8f9fa] z-10" />
                {dimValues.flatMap((dv) =>
                  METRICS.map((m, mi) => (
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
                    METRICS.map((m, mi) => {
                      const val = row.cells[dv]?.[m.key] ?? 0;
                      const isEmpty =
                        !row.cells[dv] ||
                        (row.cells[dv].spend === 0 &&
                          row.cells[dv].composite_score === 0);
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
        {dim.label.toLowerCase()} values &middot; {METRICS.length} metrics
        each
      </p>
    </div>
  );
}
