"use client";

import { useState, useCallback } from "react";
import { UploadZone } from "@/components/upload-zone";
import { FilterBar } from "@/components/filter-bar";
import { ScoreTable } from "@/components/score-table";
import { StatCards } from "@/components/stat-cards";
import { uploadAndScore, rescore, fetchSplits } from "@/lib/api";
import { applyFilters, aggregateByConcept } from "@/lib/filters";
import { ConceptView } from "@/components/concept-view";
import { PlatformView } from "@/components/platform-view";
import { DimensionView } from "@/components/dimension-view";
import { SplitsTable } from "@/components/splits-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ComparisonView } from "@/components/comparison-view";
import type {
  Creative,
  FilterOptions,
  UploadMeta,
  ActiveFilters,
  SplitRow,
  GroupBy,
} from "@/lib/types";

const BUYING_TYPE_FILTERS = ["All", "Paid", "Boosting"] as const;
type BuyingTypeFilter = (typeof BUYING_TYPE_FILTERS)[number];

export default function Dashboard() {
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [allCreatives, setAllCreatives] = useState<Creative[]>([]);
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [meta, setMeta] = useState<UploadMeta | null>(null);
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({});
  const [rankingsBuyingType, setRankingsBuyingType] = useState<BuyingTypeFilter>("All");
  const [groupBy, setGroupBy] = useState<GroupBy>("creative_name");
  const [isUploading, setIsUploading] = useState(false);
  const [isRescoring, setIsRescoring] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [splits, setSplits] = useState<SplitRow[]>([]);

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

  const displayedCreatives = filters
    ? applyFilters(allCreatives, activeFilters)
    : allCreatives;

  const rankingsCreatives =
    rankingsBuyingType === "All"
      ? displayedCreatives
      : displayedCreatives.filter(
          (c) => c.buying_type.toLowerCase() === rankingsBuyingType.toLowerCase()
        );

  const hasData = allCreatives.length > 0 && filters && meta;

  return (
    <main className="min-h-screen bg-[oklch(0.14_0.005_265)] text-[#e8eaed]">
      <header className="border-b border-[oklch(1_0_0/8%)] bg-[oklch(0.16_0.005_265)]">
        <div className="max-w-[1440px] mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-[#e8eaed] tracking-tight">
              Creative Performance Analyzer
            </h1>
            <p className="text-xs text-[#9aa0a6] mt-0.5">
              Upload campaign data to score and rank creatives
            </p>
          </div>
          {hasData && (
            <div className="flex items-center gap-1.5 bg-[oklch(0.2_0.005_265)] rounded-full p-0.5">
              {(["creative_name", "concept"] as const).map((g) => (
                <button
                  key={g}
                  onClick={() => setGroupBy(g)}
                  className={`px-3.5 py-1 rounded-full text-xs font-medium transition-colors ${
                    groupBy === g
                      ? "bg-[#1a73e8] text-white"
                      : "text-[#9aa0a6] hover:text-[#e8eaed]"
                  }`}
                >
                  {g === "creative_name" ? "Creative" : "Concept"}
                </button>
              ))}
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
          <div className="rounded-lg bg-[#ea4335]/10 border border-[#ea4335]/30 p-3 text-sm text-[#f28b82]">
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
            />

            <Tabs defaultValue="rankings" className="space-y-4">
              <TabsList className="w-full bg-[oklch(0.2_0.005_265)] border border-[oklch(1_0_0/8%)] h-10">
                <TabsTrigger value="rankings">Rankings</TabsTrigger>
                <TabsTrigger value="platform">Platform</TabsTrigger>
                <TabsTrigger value="by-dimension">By Dimension</TabsTrigger>
                <TabsTrigger value="splits">Splits</TabsTrigger>
                <TabsTrigger value="compare">Compare</TabsTrigger>
              </TabsList>

              <TabsContent value="rankings">
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 bg-[oklch(0.2_0.005_265)] rounded-lg p-0.5 border border-[oklch(1_0_0/8%)]">
                      {BUYING_TYPE_FILTERS.map((bt) => (
                        <button
                          key={bt}
                          onClick={() => setRankingsBuyingType(bt)}
                          className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                            rankingsBuyingType === bt
                              ? "bg-[oklch(0.3_0.01_265)] text-[#e8eaed]"
                              : "text-[#9aa0a6] hover:text-[#e8eaed]"
                          }`}
                        >
                          {bt}
                        </button>
                      ))}
                    </div>
                    <span className="text-xs text-[#9aa0a6] font-mono ml-1">
                      {rankingsCreatives.length} creatives
                      {groupBy === "concept" && ` / ${aggregateByConcept(rankingsCreatives).length} concepts`}
                    </span>
                  </div>
                  {groupBy === "concept" ? (
                    <ConceptView
                      concepts={aggregateByConcept(rankingsCreatives)}
                      isLoading={isRescoring}
                    />
                  ) : (
                    <ScoreTable creatives={rankingsCreatives} isLoading={isRescoring} />
                  )}
                </div>
              </TabsContent>

              <TabsContent value="platform">
                <PlatformView creatives={displayedCreatives} isLoading={isRescoring} groupBy={groupBy} />
              </TabsContent>

              <TabsContent value="by-dimension">
                <DimensionView creatives={displayedCreatives} isLoading={isRescoring} groupBy={groupBy} />
              </TabsContent>

              <TabsContent value="splits">
                <SplitsTable splits={splits} />
              </TabsContent>

              <TabsContent value="compare">
                <ComparisonView uploadId={uploadId!} filters={filters} activeFilters={activeFilters} groupBy={groupBy} />
              </TabsContent>
            </Tabs>
          </>
        )}
      </div>
    </main>
  );
}
