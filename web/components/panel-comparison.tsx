"use client";

import type { Creative } from "@/lib/types";
import { TIER_COLORS, getTier } from "@/lib/types";

interface PanelComparisonProps {
  title: string;
  creatives: Creative[];
  dimensionField: keyof Creative;
  metrics?: string[];
}

const DEFAULT_METRICS = [
  "composite_score",
  "vtr_2s",
  "completion_rate",
  "ctr",
  "spend",
  "reach",
];

const METRIC_LABELS: Record<string, string> = {
  composite_score: "Score",
  vtr_2s: "VTR",
  completion_rate: "Comp%",
  ctr: "CTR",
  spend: "Spend",
  reach: "Reach",
  impressions: "Impr.",
  engagement_rate: "Eng%",
  cpm: "CPM",
};

function formatMetric(key: string, value: number): string {
  if (key === "spend")
    return `\u00A3${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (key === "reach" || key === "impressions")
    return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (key === "ctr") return `${value.toFixed(3)}%`;
  if (key === "composite_score") return value.toFixed(1);
  if (key === "cpm") return `\u00A3${value.toFixed(2)}`;
  return `${value.toFixed(1)}%`;
}

interface AggRow {
  dimension: string;
  n: number;
  [key: string]: string | number;
}

function aggregateByDimension(
  creatives: Creative[],
  field: keyof Creative
): AggRow[] {
  const groups = new Map<string, Creative[]>();
  for (const c of creatives) {
    const key = String(c[field]) || "Unknown";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(c);
  }

  return Array.from(groups.entries())
    .map(([dimValue, items]) => {
      const totalSpend = items.reduce((s, c) => s + c.spend, 0);
      const totalImpressions = items.reduce((s, c) => s + c.impressions, 0);
      const totalReach = items.reduce((s, c) => s + c.reach, 0);

      const weightedScore =
        totalSpend > 0
          ? items.reduce((s, c) => s + c.composite_score * c.spend, 0) /
            totalSpend
          : items.reduce((s, c) => s + c.composite_score, 0) / items.length;

      const weightedVtr =
        totalImpressions > 0
          ? items.reduce((s, c) => s + c.vtr_2s * c.impressions, 0) /
            totalImpressions
          : 0;

      const weightedCompletion =
        totalImpressions > 0
          ? items.reduce(
              (s, c) => s + c.completion_rate * c.impressions,
              0
            ) / totalImpressions
          : 0;

      const totalClicks = items.reduce(
        (s, c) => s + (c.ctr * c.impressions) / 100,
        0
      );
      const totalEngagements = items.reduce(
        (s, c) => s + (c.engagement_rate * c.impressions) / 100,
        0
      );

      return {
        dimension: dimValue,
        n: items.length,
        composite_score: Math.round(weightedScore * 10) / 10,
        vtr_2s: Math.round(weightedVtr * 10) / 10,
        completion_rate: Math.round(weightedCompletion * 10) / 10,
        ctr:
          totalImpressions > 0
            ? Math.round(
                (totalClicks / totalImpressions) * 100 * 1000
              ) / 1000
            : 0,
        engagement_rate:
          totalImpressions > 0
            ? Math.round(
                (totalEngagements / totalImpressions) * 100 * 1000
              ) / 1000
            : 0,
        spend: totalSpend,
        reach: totalReach,
        impressions: totalImpressions,
        cpm:
          totalImpressions > 0
            ? Math.round(
                (totalSpend / totalImpressions) * 1000 * 100
              ) / 100
            : 0,
      };
    })
    .sort((a, b) => (b.composite_score as number) - (a.composite_score as number));
}

export function PanelComparison({
  title,
  creatives,
  dimensionField,
  metrics = DEFAULT_METRICS,
}: PanelComparisonProps) {
  const rows = aggregateByDimension(creatives, dimensionField);
  if (rows.length === 0) return null;

  const maxScore = Math.max(
    ...rows.map((r) => r.composite_score as number),
    1
  );

  return (
    <div className="rounded-lg border border-[#dadce0] bg-white">
      <div className="px-4 py-3 border-b border-[#e8eaed]">
        <h3 className="text-sm font-medium text-[#202124]">{title}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f8f9fa]">
              <th className="text-left px-4 py-2.5 text-[#5f6368] font-medium">
                {title.split(" vs ")[0]?.split(" ")[0] || title}
              </th>
              <th className="text-right px-3 py-2.5 text-[#5f6368] font-medium">
                n
              </th>
              {metrics.map((m) => (
                <th
                  key={m}
                  className="text-right px-3 py-2.5 text-[#5f6368] font-medium"
                >
                  {METRIC_LABELS[m] || m}
                </th>
              ))}
              <th className="px-4 py-2.5 text-[#5f6368] font-medium w-36">
                Score
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const score = row.composite_score as number;
              const tier = getTier(score);
              const barWidth = (score / maxScore) * 100;
              return (
                <tr
                  key={row.dimension}
                  className="border-t border-[#f1f3f4] hover:bg-[#f8f9fa] transition-colors"
                >
                  <td className="px-4 py-2.5 font-medium text-[#202124]">
                    {row.dimension}
                  </td>
                  <td className="text-right px-3 py-2.5 text-[#5f6368] font-mono">
                    {row.n}
                  </td>
                  {metrics.map((m) => (
                    <td
                      key={m}
                      className="text-right px-3 py-2.5 font-mono text-[#202124]"
                    >
                      {formatMetric(m, (row[m] as number) ?? 0)}
                    </td>
                  ))}
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-4 bg-[#f1f3f4] rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${barWidth}%`,
                            backgroundColor:
                              TIER_COLORS[tier] || "#9aa0a6",
                          }}
                        />
                      </div>
                      <span
                        className="text-xs font-mono font-medium w-8 text-right"
                        style={{
                          color: TIER_COLORS[tier] || "#9aa0a6",
                        }}
                      >
                        {score.toFixed(1)}
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
