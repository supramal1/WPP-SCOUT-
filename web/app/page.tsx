"use client";

import { useState, useCallback } from "react";
import { UploadZone } from "@/components/upload-zone";
import { FilterBar } from "@/components/filter-bar";
import { ScoreTable } from "@/components/score-table";
import { StatCards } from "@/components/stat-cards";
import { uploadAndScore, rescore } from "@/lib/api";
import { applyFilters, aggregateByConcept } from "@/lib/filters";
import { ConceptView } from "@/components/concept-view";
import type {
  Creative,
  FilterOptions,
  UploadMeta,
  ActiveFilters,
  GroupBy,
} from "@/lib/types";

export default function Dashboard() {
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [allCreatives, setAllCreatives] = useState<Creative[]>([]);
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [meta, setMeta] = useState<UploadMeta | null>(null);
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({});
  const [groupBy, setGroupBy] = useState<GroupBy>("creative_name");
  const [isUploading, setIsUploading] = useState(false);
  const [isRescoring, setIsRescoring] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleUpload = useCallback(async (file: File) => {
    setIsUploading(true);
    setLoadingMessage("Uploading and scoring...");
    setError(null);
    try {
      const result = await uploadAndScore(file);
      setUploadId(result.upload_id);
      setAllCreatives(result.creatives);
      setFilters(result.filters);
      setMeta(result.meta);
      setActiveFilters({});
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

  const displayedCreatives = filters
    ? applyFilters(allCreatives, activeFilters)
    : allCreatives;

  const hasData = allCreatives.length > 0 && filters && meta;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <div className="max-w-[1400px] mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Creative Performance Analyzer
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Upload campaign data to score and rank creatives dynamically
          </p>
        </div>

        {!hasData && (
          <UploadZone
            onUpload={handleUpload}
            isLoading={isUploading}
            loadingMessage={loadingMessage}
          />
        )}

        {error && (
          <div className="rounded-md bg-red-950/50 border border-red-900 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {hasData && (
          <>
            <StatCards creatives={displayedCreatives} totalCount={meta.total_rows} />

            <FilterBar
              filters={filters}
              activeFilters={activeFilters}
              onFilterChange={handleFilterChange}
              onRescore={handleRescore}
              isRescoring={isRescoring}
              groupBy={groupBy}
              onGroupByChange={setGroupBy}
            />

            {groupBy === "creative_name" ? (
              <ScoreTable creatives={displayedCreatives} isLoading={isRescoring} />
            ) : (
              <ConceptView
                concepts={aggregateByConcept(displayedCreatives)}
                isLoading={isRescoring}
              />
            )}
          </>
        )}
      </div>
    </main>
  );
}
