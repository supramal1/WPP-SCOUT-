"use client";

import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ScoreTable } from "./score-table";
import { ConceptView } from "./concept-view";
import { aggregateByConcept } from "@/lib/filters";
import type { Creative, GroupBy } from "@/lib/types";

interface DimensionViewProps {
  creatives: Creative[];
  isLoading?: boolean;
  groupBy: GroupBy;
}

type DimensionKey = "os_target" | "placement" | "objective" | "asset_type_canonical";

const DIMENSION_TABS: { value: DimensionKey; label: string }[] = [
  { value: "os_target", label: "OS" },
  { value: "placement", label: "Placement" },
  { value: "objective", label: "Objective" },
  { value: "asset_type_canonical", label: "Asset Type" },
];

function DimensionTab({
  creatives,
  dimensionKey,
  isLoading,
  groupBy,
}: {
  creatives: Creative[];
  dimensionKey: DimensionKey;
  isLoading?: boolean;
  groupBy: GroupBy;
}) {
  const groups = new Map<string, Creative[]>();
  for (const c of creatives) {
    const val = String(c[dimensionKey] || "Unknown");
    if (!groups.has(val)) groups.set(val, []);
    groups.get(val)!.push(c);
  }

  const sorted = Array.from(groups.entries()).sort((a, b) => {
    const aAvg = a[1].reduce((s, c) => s + c.composite_score, 0) / a[1].length;
    const bAvg = b[1].reduce((s, c) => s + c.composite_score, 0) / b[1].length;
    return bAvg - aAvg;
  });

  if (sorted.length === 0) {
    return (
      <div className="text-zinc-500 text-sm py-8 text-center">
        No data available for the current filters.
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {sorted.map(([groupName, groupCreatives]) => (
        <div key={groupName}>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-400 mb-3 border-b border-zinc-800 pb-2">
            {groupName}
            <span className="ml-2 font-mono font-normal text-zinc-600">
              ({groupBy === "concept"
                ? `${aggregateByConcept(groupCreatives).length} concepts`
                : `${groupCreatives.length} creatives`})
            </span>
          </h2>
          {groupBy === "concept" ? (
            <ConceptView concepts={aggregateByConcept(groupCreatives)} isLoading={isLoading} />
          ) : (
            <ScoreTable creatives={groupCreatives} isLoading={isLoading} />
          )}
        </div>
      ))}
    </div>
  );
}

export function DimensionView({ creatives, isLoading, groupBy }: DimensionViewProps) {
  const [activeDim, setActiveDim] = useState<DimensionKey>("os_target");

  return (
    <Tabs
      value={activeDim}
      onValueChange={(v) => setActiveDim(v as DimensionKey)}
      className="space-y-4"
    >
      <TabsList className="bg-zinc-900 border border-zinc-800">
        {DIMENSION_TABS.map((t) => (
          <TabsTrigger key={t.value} value={t.value}>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>
      {DIMENSION_TABS.map((t) => (
        <TabsContent key={t.value} value={t.value}>
          <DimensionTab
            creatives={creatives}
            dimensionKey={t.value}
            isLoading={isLoading}
            groupBy={groupBy}
          />
        </TabsContent>
      ))}
    </Tabs>
  );
}
