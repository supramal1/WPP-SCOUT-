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
      // Don't overwrite filters — keep original dropdown options from upload
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

  const displayCount = useMemo(() => {
    if (groupBy === "concept") {
      return aggregateByConcept(filteredCreatives).length;
    }
    return filteredCreatives.length;
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
                {meta.brand} &middot; {displayCount}{" "}
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
        {!hasData && (
          <UploadZone
            onUpload={handleUpload}
            isLoading={isUploading}
            loadingMessage={loadingMessage}
          />
        )}

        {error && (
          <div className="rounded-lg bg-[#fce8e6] border border-[#f28b82] p-3 text-sm text-[#c5221f]">
            {error}
          </div>
        )}

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
              creatives={filteredCreatives}
              allCreatives={allCreatives}
              groupBy={groupBy}
              isLoading={isRescoring}
            />
          </>
        )}
      </div>
    </main>
  );
}
