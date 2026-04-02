"use client";

import type { Creative } from "@/lib/types";
import { TIER_COLORS, getTier } from "@/lib/types";

interface TopBottomCreativesProps {
  creatives: Creative[];
  count?: number;
}

const COLUMNS: { key: keyof Creative; label: string }[] = [
  { key: "composite_score", label: "Score" },
  { key: "vtr_2s", label: "VTR" },
  { key: "completion_rate", label: "Comp%" },
  { key: "ctr", label: "CTR" },
  { key: "spend", label: "Spend" },
  { key: "reach", label: "Reach" },
];

function fmt(key: string, v: number | null | undefined): string {
  if (v == null) return "\u2014";
  if (key === "spend")
    return `\u00A3${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (key === "reach" || key === "impressions")
    return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (key === "ctr") return `${v.toFixed(3)}%`;
  if (key === "composite_score") return v.toFixed(1);
  return `${v.toFixed(1)}%`;
}

function CreativeTable({
  creatives,
  label,
  variant,
}: {
  creatives: Creative[];
  label: string;
  variant: "top" | "bottom";
}) {
  return (
    <div className="rounded-lg border border-[#dadce0] bg-white overflow-hidden">
      <div
        className={`px-4 py-2.5 border-b border-[#e8eaed] flex items-center justify-between ${
          variant === "top" ? "bg-[#e6f4ea]/50" : "bg-[#fce8e6]/50"
        }`}
      >
        <h4 className="text-sm font-medium text-[#202124]">{label}</h4>
        <span className="text-[11px] text-[#5f6368] font-mono">
          {creatives.length} creatives
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-[#f8f9fa]">
              <th className="text-left px-3 py-2 text-[#5f6368] font-medium w-8">
                #
              </th>
              <th className="text-left px-3 py-2 text-[#5f6368] font-medium">
                Creative
              </th>
              <th className="text-left px-3 py-2 text-[#5f6368] font-medium">
                Platform
              </th>
              {COLUMNS.map((col) => (
                <th
                  key={col.key}
                  className="text-right px-3 py-2 text-[#5f6368] font-medium"
                >
                  {col.label}
                </th>
              ))}
              <th className="text-left px-3 py-2 text-[#5f6368] font-medium">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {creatives.map((c, i) => {
              const tier = getTier(c.composite_score);
              return (
                <tr
                  key={`${c.creative_name}-${c.platform}-${i}`}
                  className="border-t border-[#f1f3f4] hover:bg-[#f8f9fa] transition-colors"
                >
                  <td className="px-3 py-2 font-mono text-[#80868b]">
                    {i + 1}
                  </td>
                  <td className="px-3 py-2 font-medium text-[#202124] max-w-[220px] truncate">
                    {c.creative_name}
                  </td>
                  <td className="px-3 py-2 text-[#5f6368]">{c.platform}</td>
                  {COLUMNS.map((col) => (
                    <td
                      key={col.key}
                      className="text-right px-3 py-2 font-mono text-[#202124]"
                    >
                      {col.key === "composite_score" ? (
                        <span
                          className="font-medium"
                          style={{ color: TIER_COLORS[tier] }}
                        >
                          {fmt(col.key, c[col.key] as number)}
                        </span>
                      ) : (
                        fmt(col.key, c[col.key] as number)
                      )}
                    </td>
                  ))}
                  <td className="px-3 py-2">
                    <span
                      className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                        c.action === "Scale Up"
                          ? "bg-[#ceead6] text-[#137333]"
                          : c.action === "Keep Running"
                            ? "bg-[#d2e3fc] text-[#1967d2]"
                            : c.action === "Pause"
                              ? "bg-[#fce8e6] text-[#c5221f]"
                              : "bg-[#f1f3f4] text-[#5f6368]"
                      }`}
                    >
                      {c.action}
                    </span>
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

export function TopBottomCreatives({
  creatives,
  count = 10,
}: TopBottomCreativesProps) {
  if (creatives.length === 0) return null;

  const sorted = [...creatives].sort(
    (a, b) => b.composite_score - a.composite_score
  );
  const top = sorted.slice(0, count);
  const bottom = sorted.length > count
    ? sorted.slice(-count).sort((a, b) => a.composite_score - b.composite_score)
    : [];

  return (
    <div className="space-y-4">
      <CreativeTable
        creatives={top}
        label={`Top ${top.length} Creatives`}
        variant="top"
      />
      {bottom.length > 0 && (
        <CreativeTable
          creatives={bottom}
          label={`Bottom ${bottom.length} Creatives`}
          variant="bottom"
        />
      )}
    </div>
  );
}
