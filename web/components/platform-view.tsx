"use client";

import { ScoreTable } from "./score-table";
import { ConceptView } from "./concept-view";
import { aggregateByConcept } from "@/lib/filters";
import type { Creative, GroupBy } from "@/lib/types";

interface PlatformViewProps {
  creatives: Creative[];
  isLoading?: boolean;
  groupBy: GroupBy;
}

const PLATFORM_SECTIONS: { label: string; platform: string; buying_type: string }[] = [
  { label: "TikTok Paid", platform: "TikTok", buying_type: "Paid" },
  { label: "Meta Paid", platform: "Meta", buying_type: "Paid" },
  { label: "TikTok Boosting", platform: "TikTok", buying_type: "Boosting" },
  { label: "Meta Boosting", platform: "Meta", buying_type: "Boosting" },
];

export function PlatformView({ creatives, isLoading, groupBy }: PlatformViewProps) {
  const sections = PLATFORM_SECTIONS.map((s) => ({
    ...s,
    data: creatives.filter(
      (c) =>
        c.platform.toLowerCase() === s.platform.toLowerCase() &&
        c.buying_type.toLowerCase() === s.buying_type.toLowerCase()
    ),
  })).filter((s) => s.data.length > 0);

  if (sections.length === 0) {
    return (
      <div className="text-zinc-500 text-sm py-8 text-center">
        No platform data available for the current filters.
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {sections.map((s) => (
        <div key={s.label}>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400 mb-3 border-b border-zinc-800 pb-2">
            {s.label}
            <span className="ml-2 font-mono font-normal text-zinc-600">
              ({groupBy === "concept"
                ? `${aggregateByConcept(s.data).length} concepts`
                : `${s.data.length} creatives`})
            </span>
          </h2>
          {groupBy === "concept" ? (
            <ConceptView concepts={aggregateByConcept(s.data)} isLoading={isLoading} />
          ) : (
            <ScoreTable creatives={s.data} isLoading={isLoading} />
          )}
        </div>
      ))}
    </div>
  );
}
