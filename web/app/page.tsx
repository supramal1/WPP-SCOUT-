"use client";

import { useState, useCallback, useMemo } from "react";
import { UploadZone } from "@/components/upload-zone";
import { GlobalFilterBar } from "@/components/global-filter-bar";
import { CampaignTabs } from "@/components/campaign-tabs";
import { uploadAndScore, rescore, fetchSplits } from "@/lib/api";
import { applyFilters, aggregateByConcept } from "@/lib/filters";
import type {
  Creative,
  FilterOptions,
  UploadMeta,
  ActiveFilters,
  SplitRow,
  GroupBy,
} from "@/lib/types";

export default function Dashboard() {
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [allCreatives, setAllCreatives] = useState<Creative[]>([]);
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [meta, setMeta] = useState<UploadMeta | null>(null);
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({});
  const [isUploading, setIsUploading] = useState(false);
  const [isRescoring, setIsRescoring] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [, setSplits] = useState<SplitRow[]>([]);
  const [groupBy, setGroupBy] = useState<GroupBy>("creative_name");

  const handleUpload = useCallback(async (file: File) => {
    setIsUploading(true);
    setLoadingMessage("Reading file...");
    setError(null);
    try {
      const result = await uploadAndScore(file, setLoadingMessage);
      setUploadId(result.upload_id);
      setAllCreatives(result.creatives);
      setFilters(result.filters);
      setMeta(result.meta);
      setActiveFilters({});
      fetchSplits(result.upload_id)
        .then(setSplits)
        .catch(() => setSplits([]));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleRescore = useCallback(async () => {
    if (!uploadId) return;
    const cleanFilters = Object.fromEntries(
      Object.entries(activeFilters).filter(([, v]) => v && v !== "All")
    );
    if (Object.keys(cleanFilters).length === 0) return;

    setIsRescoring(true);
    try {
      const result = await rescore(uploadId, cleanFilters);
      setAllCreatives(result.creatives);
      setFilters(result.filters);
      setMeta(result.meta);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rescore failed");
    } finally {
      setIsRescoring(false);
    }
  }, [uploadId, activeFilters]);

  const handleFilterChange = useCallback((key: string, value: string) => {
    setActiveFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleReset = useCallback(() => {
    setUploadId(null);
    setAllCreatives([]);
    setFilters(null);
    setMeta(null);
    setActiveFilters({});
    setSplits([]);
    setError(null);
    setGroupBy("creative_name");
  }, []);

  const filteredCreatives = filters
    ? applyFilters(allCreatives, activeFilters)
    : allCreatives;

  const displayedCreatives = useMemo(() => {
    if (groupBy === "concept") {
      const concepts = aggregateByConcept(filteredCreatives);
      return concepts.map((g): Creative => ({
        creative_name: g.concept,
        concept: g.concept,
        platform: "",
        objective: "",
        format: "",
        placement: "",
        os_target: "",
        asset_type_canonical: "",
        asset_type_subtype: "",
        buying_type: "",
        campaign_normalized: "",
        composite_score: g.composite_score,
        tier: g.tier,
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
    return filteredCreatives;
  }, [filteredCreatives, groupBy]);

  const hasData = allCreatives.length > 0 && filters && meta;

  return (
    <main className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-[#dadce0] bg-white sticky top-0 z-10">
        <div className="max-w-[1440px] mx-auto px-6 py-3 flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold text-[#202124] tracking-tight">
              Creative Performance Analyzer
            </h1>
            {meta && (
              <p className="text-[11px] text-[#5f6368] mt-0.5">
                {meta.brand} &middot; {displayedCreatives.length}{" "}
                {groupBy === "concept" ? "concepts" : "creatives"}
                &middot; {meta.total_rows} rows
              </p>
            )}
          </div>
          {hasData && (
            <div className="flex items-center gap-3">
              <div className="flex items-center rounded-full bg-[#f1f3f4] p-0.5">
                <button
                  onClick={() => setGroupBy("creative_name")}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    groupBy === "creative_name"
                      ? "bg-white text-[#202124] shadow-sm"
                      : "text-[#5f6368]"
                  }`}
                >
                  Creative
                </button>
                <button
                  onClick={() => setGroupBy("concept")}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                    groupBy === "concept"
                      ? "bg-white text-[#202124] shadow-sm"
                      : "text-[#5f6368]"
                  }`}
                >
                  Concept
                </button>
              </div>
              <button
                onClick={handleReset}
                className="text-xs text-[#5f6368] hover:text-[#202124] px-3 py-1.5 rounded-md hover:bg-[#f1f3f4] transition-colors"
              >
                New upload
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="max-w-[1440px] mx-auto px-6 py-5 space-y-5">
        {/* Upload zone */}
        {!hasData && (
          <UploadZone
            onUpload={handleUpload}
            isLoading={isUploading}
            loadingMessage={loadingMessage}
          />
        )}

        {/* Error */}
        {error && (
          <div className="rounded-lg bg-[#fce8e6] border border-[#f28b82] p-3 text-sm text-[#c5221f]">
            {error}
          </div>
        )}

        {/* Dashboard */}
        {hasData && (
          <>
            <GlobalFilterBar
              filters={filters}
              activeFilters={activeFilters}
              onFilterChange={handleFilterChange}
              onRescore={handleRescore}
              isRescoring={isRescoring}
            />

            <CampaignTabs
              creatives={displayedCreatives}
              isLoading={isRescoring}
            />
          </>
        )}
      </div>
    </main>
  );
}
