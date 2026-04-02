"use client";

import { useMemo } from "react";
import type { Creative, GroupBy } from "@/lib/types";
import { getTier } from "@/lib/types";
import { aggregateByConcept } from "@/lib/filters";
import { TopBottomCreatives } from "./top-bottom-creatives";
import { PanelComparison } from "./panel-comparison";
import { PanelHeatmap } from "./panel-heatmap";

interface OverviewDashboardProps {
  creatives: Creative[];
  groupBy: GroupBy;
}

export function OverviewDashboard({ creatives, groupBy }: OverviewDashboardProps) {
  if (creatives.length === 0) {
    return (
      <div className="rounded-lg border border-[#dadce0] bg-white p-8 text-center">
        <p className="text-sm text-[#5f6368]">No creatives match the current filters.</p>
      </div>
    );
  }

  // For Top/Bottom: use concept aggregation when in concept mode
  const rankingCreatives = useMemo(() => {
    if (groupBy === "concept") {
      const concepts = aggregateByConcept(creatives);
      return concepts.map((g): Creative => ({
        creative_name: g.concept,
        concept: g.concept,
        platform: `${g.n_variations} variations`,
        objective: "",
        format: "",
        placement: "",
        os_target: "",
        asset_type_canonical: "",
        asset_type_subtype: "",
        buying_type: "",
        campaign_normalized: "",
        composite_score: g.composite_score,
        tier: getTier(g.composite_score),
        action: g.composite_score >= 70 ? "Scale Up" : g.composite_score >= 50 ? "Keep Running" : "Pause",
        spend: g.spend,
        reach: g.reach,
        impressions: g.impressions,
        vtr_2s: g.vtr_2s,
        completion_rate: g.completion_rate,
        ctr: g.ctr,
        engagement_rate: g.engagement_rate,
        share_rate: 0,
        cpm: g.cpm,
        frequency: g.frequency,
        cost_per_complete_view: null,
        reach_per_pound: null,
        completion_vs_expected: null,
        scoring_group: "",
        explanation: `${g.n_variations} variations`,
        low_confidence: false,
      }));
    }
    return creatives;
  }, [creatives, groupBy]);

  return (
    <div className="space-y-4">
      {/* Top & Bottom — uses concept aggregation in concept mode */}
      <TopBottomCreatives creatives={rankingCreatives} count={10} />

      {/* Dimension summaries — always use raw creatives */}
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
