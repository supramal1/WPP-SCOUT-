"use client";

import type { Creative } from "@/lib/types";

interface PanelHeatmapProps {
  creatives: Creative[];
}

function getHeatColor(score: number): string {
  if (score >= 85) return "#ceead6";
  if (score >= 70) return "#d2e3fc";
  if (score >= 50) return "#e8eaed";
  if (score >= 25) return "#fef7e0";
  return "#fce8e6";
}

function getHeatTextColor(score: number): string {
  if (score >= 85) return "#137333";
  if (score >= 70) return "#1967d2";
  if (score >= 50) return "#5f6368";
  if (score >= 25) return "#ea8600";
  return "#c5221f";
}

export function PanelHeatmap({ creatives }: PanelHeatmapProps) {
  const objectives = [...new Set(creatives.map((c) => c.objective))].sort();
  const placements = [...new Set(creatives.map((c) => c.placement))].sort();

  if (objectives.length === 0 || placements.length === 0) return null;

  const matrix = new Map<
    string,
    Map<string, { total: number; weight: number }>
  >();
  for (const c of creatives) {
    if (!matrix.has(c.objective)) matrix.set(c.objective, new Map());
    const row = matrix.get(c.objective)!;
    if (!row.has(c.placement))
      row.set(c.placement, { total: 0, weight: 0 });
    const cell = row.get(c.placement)!;
    cell.total += c.composite_score * c.spend;
    cell.weight += c.spend;
  }

  return (
    <div className="rounded-lg border border-[#dadce0] bg-white">
      <div className="px-4 py-3 border-b border-[#e8eaed]">
        <h3 className="text-sm font-medium text-[#202124]">
          Objective &times; Placement Heatmap
        </h3>
        <p className="text-[11px] text-[#5f6368] mt-0.5">
          Spend-weighted average score
        </p>
      </div>
      <div className="p-4 overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr>
              <th className="text-left px-3 py-2 text-[#5f6368] font-medium bg-[#f8f9fa] rounded-tl-md" />
              {placements.map((p) => (
                <th
                  key={p}
                  className="text-center px-3 py-2 text-[#5f6368] font-medium bg-[#f8f9fa] text-[10px] uppercase tracking-wide"
                >
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {objectives.map((obj) => (
              <tr key={obj}>
                <td className="px-3 py-2.5 font-medium text-[#202124] bg-[#f8f9fa] whitespace-nowrap text-[11px]">
                  {obj}
                </td>
                {placements.map((pl) => {
                  const cell = matrix.get(obj)?.get(pl);
                  if (!cell || cell.weight === 0) {
                    return (
                      <td
                        key={pl}
                        className="text-center px-3 py-2.5 text-[#80868b]"
                      >
                        &mdash;
                      </td>
                    );
                  }
                  const score =
                    Math.round((cell.total / cell.weight) * 10) / 10;
                  return (
                    <td
                      key={pl}
                      className="text-center px-3 py-2.5 font-mono font-medium"
                      style={{
                        backgroundColor: getHeatColor(score),
                        color: getHeatTextColor(score),
                      }}
                    >
                      {score.toFixed(1)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-4 pb-3 flex items-center gap-3 text-[10px] text-[#5f6368]">
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: "#ceead6" }}
          />
          85+
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: "#d2e3fc" }}
          />
          70+
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: "#e8eaed" }}
          />
          50+
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: "#fef7e0" }}
          />
          25+
        </span>
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-3 w-3 rounded-sm"
            style={{ backgroundColor: "#fce8e6" }}
          />
          &lt;25
        </span>
      </div>
    </div>
  );
}
