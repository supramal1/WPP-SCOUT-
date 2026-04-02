"use client";

import type { Creative } from "@/lib/types";
import { TopBottomCreatives } from "./top-bottom-creatives";
import { PanelComparison } from "./panel-comparison";
import { PanelHeatmap } from "./panel-heatmap";

interface OverviewDashboardProps {
  creatives: Creative[];
}

export function OverviewDashboard({ creatives }: OverviewDashboardProps) {
  if (creatives.length === 0) {
    return (
      <div className="rounded-lg border border-[#dadce0] bg-white p-8 text-center">
        <p className="text-sm text-[#5f6368]">No creatives match the current filters.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top & Bottom Creatives */}
      <TopBottomCreatives creatives={creatives} count={10} />

      {/* Dimension summaries */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PanelComparison
          title="OS Comparison"
          creatives={creatives}
          dimensionField="os_target"
        />
        <PanelComparison
          title="Asset Type"
          creatives={creatives}
          dimensionField="asset_type_subtype"
        />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PanelComparison
          title="Placement Summary"
          creatives={creatives}
          dimensionField="placement"
        />
        <PanelComparison
          title="Objective Summary"
          creatives={creatives}
          dimensionField="objective"
        />
      </div>
      <PanelHeatmap creatives={creatives} />
    </div>
  );
}
