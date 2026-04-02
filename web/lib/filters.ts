import type { Creative, ActiveFilters, ConceptGroup } from "./types";
import { getTier } from "./types";

const FILTER_TO_FIELD: Record<string, keyof Creative> = {
  campaign: "campaign_normalized",
  platform: "platform",
  os: "os_target",
  placement: "placement",
  objective: "objective",
  format: "format",
  asset_type: "asset_type_canonical",
  asset_subtype: "asset_type_subtype",
  buying_type: "buying_type",
  concept: "concept",
};

export function applyFilters(
  creatives: Creative[],
  filters: ActiveFilters
): Creative[] {
  return creatives.filter((c) =>
    Object.entries(filters).every(([key, value]) => {
      if (!value || value === "All") return true;
      const field = FILTER_TO_FIELD[key];
      if (!field) return true;
      return String(c[field]) === value;
    })
  );
}

export function aggregateByConcept(creatives: Creative[]): ConceptGroup[] {
  const groups = new Map<string, Creative[]>();

  for (const c of creatives) {
    const key = c.concept || c.creative_name;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(c);
  }

  return Array.from(groups.entries())
    .map(([concept, items]) => {
      const totalSpend = items.reduce((s, c) => s + c.spend, 0);
      const totalImpressions = items.reduce((s, c) => s + c.impressions, 0);
      const totalReach = items.reduce((s, c) => s + c.reach, 0);
      const totalClicks = items.reduce((s, c) => s + c.ctr * c.impressions / 100, 0);
      const totalEngagements = items.reduce((s, c) => s + c.engagement_rate * c.impressions / 100, 0);
      const totalCompletions = items.reduce((s, c) => s + c.completion_rate * c.impressions / 100, 0);

      const weightedScore =
        totalSpend > 0
          ? items.reduce((s, c) => s + c.composite_score * c.spend, 0) / totalSpend
          : items.reduce((s, c) => s + c.composite_score, 0) / items.length;

      const weightedVtr =
        totalImpressions > 0
          ? items.reduce((s, c) => s + c.vtr_2s * c.impressions, 0) / totalImpressions
          : 0;

      return {
        concept,
        composite_score: Math.round(weightedScore * 10) / 10,
        tier: getTier(weightedScore),
        n_variations: items.length,
        spend: totalSpend,
        reach: totalReach,
        impressions: totalImpressions,
        vtr_2s: Math.round(weightedVtr * 10) / 10,
        ctr: totalImpressions > 0 ? Math.round((totalClicks / totalImpressions) * 100 * 1000) / 1000 : 0,
        engagement_rate: totalImpressions > 0 ? Math.round((totalEngagements / totalImpressions) * 100 * 1000) / 1000 : 0,
        completion_rate: totalImpressions > 0 ? Math.round((totalCompletions / totalImpressions) * 100 * 100) / 100 : 0,
        cpm: totalImpressions > 0 ? Math.round((totalSpend / totalImpressions) * 1000 * 100) / 100 : 0,
        frequency: totalReach > 0 ? Math.round((totalImpressions / totalReach) * 100) / 100 : 0,
        best_variation_score: Math.max(...items.map((c) => c.composite_score)),
        worst_variation_score: Math.min(...items.map((c) => c.composite_score)),
        creatives: items.sort((a, b) => b.composite_score - a.composite_score),
      };
    })
    .sort((a, b) => b.composite_score - a.composite_score);
}
