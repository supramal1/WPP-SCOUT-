export interface Creative {
  creative_name: string;
  concept: string;
  platform: string;
  objective: string;
  format: string;
  placement: string;
  os_target: string;
  asset_type_canonical: string;
  buying_type: string;
  campaign_normalized: string;
  composite_score: number;
  tier: string;
  action: string;
  spend: number;
  reach: number;
  impressions: number;
  vtr_2s: number;
  completion_rate: number;
  ctr: number;
  engagement_rate: number;
  share_rate: number;
  cpm: number;
  frequency: number;
  cost_per_complete_view: number | null;
  reach_per_pound: number | null;
  completion_vs_expected: number | null;
  scoring_group: string;
  explanation: string;
  low_confidence: boolean;
}

export interface FilterOptions {
  campaigns: string[];
  platforms: string[];
  os: string[];
  placements: string[];
  objectives: string[];
  formats: string[];
  asset_types: string[];
  buying_types: string[];
  concepts: string[];
}

export interface UploadMeta {
  total_rows: number;
  platforms_found: string[];
  brand: string;
}

export interface UploadResponse {
  upload_id: string;
  creatives: Creative[];
  filters: FilterOptions;
  meta: UploadMeta;
}

export interface RescoreResponse {
  creatives: Creative[];
  filters: FilterOptions;
  meta: UploadMeta;
}

export interface ApiError {
  error: string;
  message: string;
}

export type ActiveFilters = Partial<Record<string, string>>;

export type GroupBy = "creative_name" | "concept";

export interface ConceptGroup {
  concept: string;
  composite_score: number;
  tier: string;
  n_variations: number;
  spend: number;
  reach: number;
  impressions: number;
  vtr_2s: number;
  ctr: number;
  engagement_rate: number;
  completion_rate: number;
  cpm: number;
  frequency: number;
  best_variation_score: number;
  worst_variation_score: number;
  creatives: Creative[];
}

export const TIER_COLORS: Record<string, string> = {
  "Top Performer": "#22c55e",
  Strong: "#3b82f6",
  Average: "#a1a1aa",
  "Below Average": "#f97316",
  Poor: "#ef4444",
};

export function getTier(score: number): string {
  if (score >= 85) return "Top Performer";
  if (score >= 70) return "Strong";
  if (score >= 50) return "Average";
  if (score >= 25) return "Below Average";
  return "Poor";
}
