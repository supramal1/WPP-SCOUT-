"use client";

import { useState, useCallback } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TierBadge } from "./tier-badge";
import { rescore } from "@/lib/api";
import { aggregateByConcept } from "@/lib/filters";
import type {
  Creative,
  FilterOptions,
  ActiveFilters,
  GroupBy,
  RescoreResponse,
  ConceptGroup,
} from "@/lib/types";

interface ComparisonViewProps {
  uploadId: string;
  filters: FilterOptions;
  activeFilters: ActiveFilters;
  groupBy: GroupBy;
}

const DIMENSION_OPTIONS: { key: string; label: string; optionsKey: keyof FilterOptions }[] = [
  { key: "os", label: "OS", optionsKey: "os" },
  { key: "asset_subtype", label: "Asset Type", optionsKey: "asset_subtypes" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "placement", label: "Placement", optionsKey: "placements" },
  { key: "objective", label: "Objective", optionsKey: "objectives" },
  { key: "buying_type", label: "Buying Type", optionsKey: "buying_types" },
  { key: "format", label: "Format", optionsKey: "formats" },
];

// Metrics shown per dimension value — mirrors the reference spreadsheet columns
const DISPLAY_METRICS: { key: string; label: string; format: (v: number | null) => string }[] = [
  { key: "composite_score", label: "Score", format: (v) => v != null ? v.toFixed(1) : "" },
  { key: "vtr_2s", label: "VTR", format: (v) => v != null ? `${v.toFixed(1)}%` : "" },
  { key: "completion_rate", label: "Completion", format: (v) => v != null ? `${v.toFixed(2)}%` : "" },
  { key: "spend", label: "Spend", format: (v) => v != null ? `€${v.toLocaleString("en", { maximumFractionDigits: 0 })}` : "" },
  { key: "reach", label: "Reach", format: (v) => v != null ? v.toLocaleString("en") : "" },
];

type MetricValues = Record<string, number | null>;

interface ComparisonRow {
  name: string;
  platform: string;
  // dimensionValue -> { metric_key -> number }
  byValue: Record<string, MetricValues>;
}

function extractMetricValues(c: Creative | ConceptGroup): MetricValues {
  return {
    composite_score: c.composite_score,
    vtr_2s: c.vtr_2s,
    completion_rate: c.completion_rate,
    spend: c.spend,
    reach: c.reach,
  };
}

export function ComparisonView({ uploadId, filters, activeFilters, groupBy }: ComparisonViewProps) {
  const [dimension, setDimension] = useState("os");
  const [rows, setRows] = useState<ComparisonRow[]>([]);
  const [dimValues, setDimValues] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentDef = DIMENSION_OPTIONS.find((d) => d.key === dimension)!;
  const options = filters[currentDef.optionsKey] ?? [];

  const baseFilters = Object.fromEntries(
    Object.entries(activeFilters).filter(([k, v]) => k !== dimension && v && v !== "All")
  );

  const handleDimensionChange = useCallback((v: string | null) => {
    if (v) {
      setDimension(v);
      setRows([]);
      setDimValues([]);
    }
  }, []);

  const handleCompare = useCallback(async () => {
    if (options.length < 2) return;
    setIsLoading(true);
    setError(null);
    try {
      const results: RescoreResponse[] = [];
      for (const val of options) {
        results.push(await rescore(uploadId, { ...baseFilters, [dimension]: val }));
      }

      // Build a map per dimension value: name -> metrics
      const valueMaps = options.map((val, i) => {
        if (groupBy === "concept") {
          const concepts = aggregateByConcept(results[i].creatives);
          return {
            val,
            map: new Map(concepts.map((g) => [g.concept, { metrics: extractMetricValues(g), platform: "" }])),
          };
        }
        return {
          val,
          map: new Map(
            results[i].creatives.map((c) => [c.creative_name, { metrics: extractMetricValues(c), platform: c.platform }])
          ),
        };
      });

      // Collect all creative names
      const allNames = new Set<string>();
      for (const { map } of valueMaps) {
        for (const name of map.keys()) allNames.add(name);
      }

      // Build rows
      const compared: ComparisonRow[] = Array.from(allNames)
        .map((name) => {
          const byValue: Record<string, MetricValues> = {};
          let platform = "";
          for (const { val, map } of valueMaps) {
            const entry = map.get(name);
            byValue[val] = entry?.metrics ?? { composite_score: null, vtr_2s: null, completion_rate: null, spend: null, reach: null };
            if (entry?.platform) platform = entry.platform;
          }
          return { name, platform, byValue };
        })
        .sort((a, b) => {
          // Sort by best score across any dimension value
          const bestA = Math.max(...options.map((v) => a.byValue[v]?.composite_score ?? 0));
          const bestB = Math.max(...options.map((v) => b.byValue[v]?.composite_score ?? 0));
          return bestB - bestA;
        });

      setDimValues(options);
      setRows(compared);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Comparison failed. Try re-uploading your data.");
    } finally {
      setIsLoading(false);
    }
  }, [uploadId, dimension, options, groupBy, baseFilters]);

  const activeGlobalFilters = Object.entries(activeFilters)
    .filter(([k, v]) => v && v !== "All" && k !== dimension)
    .map(([k, v]) => `${k}=${v}`);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Compare by</label>
          <Select value={dimension} onValueChange={handleDimensionChange}>
            <SelectTrigger className="w-[200px] bg-zinc-900 border-zinc-700">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DIMENSION_OPTIONS.map((d) => (
                <SelectItem key={d.key} value={d.key}>{d.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Values</label>
          <span className="text-sm text-zinc-400 px-2 py-1.5">
            {options.length > 0 ? options.join(" vs ") : "No values"}
          </span>
        </div>
        <Button
          onClick={handleCompare}
          disabled={options.length < 2 || isLoading}
          className="bg-zinc-800 hover:bg-zinc-700"
        >
          {isLoading ? "Comparing..." : "Compare"}
        </Button>
      </div>

      {activeGlobalFilters.length > 0 && (
        <div className="text-xs text-zinc-500">
          Active filters: {activeGlobalFilters.join(", ")}
        </div>
      )}

      {error && (
        <div className="rounded-md bg-red-950/50 border border-red-900 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-zinc-800 hover:bg-transparent">
                <TableHead className="text-zinc-500 sticky left-0 bg-zinc-950 z-10">
                  {groupBy === "concept" ? "Concept" : "Creative"}
                </TableHead>
                {groupBy !== "concept" && (
                  <TableHead className="text-zinc-500">Platform</TableHead>
                )}
                {dimValues.map((val) =>
                  DISPLAY_METRICS.map((m) => (
                    <TableHead key={`${val}-${m.key}`} className="text-zinc-500 text-right min-w-[90px]">
                      <div className="text-[10px] text-zinc-600">{m.label}</div>
                      <div>{val}</div>
                    </TableHead>
                  ))
                )}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.name} className="border-zinc-800">
                  <TableCell className="font-medium sticky left-0 bg-zinc-950 z-10 max-w-[280px] truncate">
                    {r.name}
                  </TableCell>
                  {groupBy !== "concept" && (
                    <TableCell className="text-zinc-400 text-sm">{r.platform}</TableCell>
                  )}
                  {dimValues.map((val) =>
                    DISPLAY_METRICS.map((m) => {
                      const v = r.byValue[val]?.[m.key] ?? null;
                      if (m.key === "composite_score" && v != null) {
                        // Determine tier from score
                        const tier = v >= 75 ? "Top Performer" : v >= 60 ? "Strong" : v >= 45 ? "Average" : "Below Average";
                        return (
                          <TableCell key={`${r.name}-${val}-${m.key}`} className="text-right">
                            <TierBadge tier={tier} score={v} />
                          </TableCell>
                        );
                      }
                      return (
                        <TableCell key={`${r.name}-${val}-${m.key}`} className="text-right">
                          <span className={`font-mono text-sm ${v != null ? "text-zinc-300" : "text-zinc-700"}`}>
                            {m.format(v)}
                          </span>
                        </TableCell>
                      );
                    })
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
