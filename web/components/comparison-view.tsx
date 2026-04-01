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
  { key: "asset_subtype", label: "Brand / Creator / Partner", optionsKey: "asset_subtypes" },
  { key: "os", label: "OS", optionsKey: "os" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "placement", label: "Placement", optionsKey: "placements" },
  { key: "objective", label: "Objective", optionsKey: "objectives" },
  { key: "buying_type", label: "Buying Type", optionsKey: "buying_types" },
  { key: "format", label: "Format", optionsKey: "formats" },
];

const METRICS: { key: string; label: string; format: (v: number | null) => string }[] = [
  { key: "composite_score", label: "Score", format: (v) => v != null ? v.toFixed(1) : "--" },
  { key: "vtr_2s", label: "VTR", format: (v) => v != null ? `${v.toFixed(1)}%` : "--" },
  { key: "ctr", label: "CTR", format: (v) => v != null ? `${v.toFixed(2)}%` : "--" },
  { key: "engagement_rate", label: "Eng. Rate", format: (v) => v != null ? `${v.toFixed(2)}%` : "--" },
  { key: "completion_rate", label: "Completion", format: (v) => v != null ? `${v.toFixed(2)}%` : "--" },
  { key: "cpm", label: "CPM", format: (v) => v != null ? `€${v.toFixed(2)}` : "--" },
  { key: "spend", label: "Spend", format: (v) => v != null ? `€${v.toLocaleString("en", { maximumFractionDigits: 0 })}` : "--" },
  { key: "impressions", label: "Impressions", format: (v) => v != null ? v.toLocaleString("en") : "--" },
  { key: "reach", label: "Reach", format: (v) => v != null ? v.toLocaleString("en") : "--" },
  { key: "frequency", label: "Frequency", format: (v) => v != null ? v.toFixed(1) : "--" },
];

interface CreativeMetrics {
  composite_score: number;
  tier: string;
  vtr_2s: number;
  ctr: number;
  engagement_rate: number;
  completion_rate: number;
  cpm: number;
  spend: number;
  impressions: number;
  reach: number;
  frequency: number;
}

interface ComparisonRow {
  name: string;
  metrics: Record<string, CreativeMetrics | null>;
}

function extractMetrics(c: Creative | ConceptGroup): CreativeMetrics {
  return {
    composite_score: c.composite_score,
    tier: c.tier,
    vtr_2s: c.vtr_2s,
    ctr: c.ctr,
    engagement_rate: c.engagement_rate,
    completion_rate: c.completion_rate,
    cpm: c.cpm,
    spend: c.spend,
    impressions: c.impressions,
    reach: c.reach,
    frequency: c.frequency,
  };
}

function metricCellClass(
  metricKey: string,
  value: number | null,
  allValues: (number | null)[]
): string {
  if (value == null) return "text-zinc-600";
  const valid = allValues.filter((v): v is number => v != null);
  if (valid.length < 2) return "text-zinc-300";
  const lowerIsBetter = metricKey === "cpm";
  const best = lowerIsBetter ? Math.min(...valid) : Math.max(...valid);
  if (value === best) return "text-emerald-400 font-semibold";
  return "text-zinc-300";
}

function average(values: (number | null)[]): number {
  const valid = values.filter((v): v is number => v != null);
  return valid.length > 0 ? valid.reduce((a, b) => a + b, 0) / valid.length : 0;
}

export function ComparisonView({ uploadId, filters, activeFilters, groupBy }: ComparisonViewProps) {
  const [dimension, setDimension] = useState("asset_subtype");
  const [rows, setRows] = useState<ComparisonRow[]>([]);
  const [comparedValues, setComparedValues] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedMetric, setSelectedMetric] = useState("composite_score");

  const currentDef = DIMENSION_OPTIONS.find((d) => d.key === dimension)!;
  const options = filters[currentDef.optionsKey] ?? [];

  // Don't include the pivot dimension in global filters (would conflict)
  const baseFilters = Object.fromEntries(
    Object.entries(activeFilters).filter(([k, v]) => k !== dimension && v && v !== "All")
  );

  const handleDimensionChange = useCallback((v: string | null) => {
    if (v) {
      setDimension(v);
      setRows([]);
      setComparedValues([]);
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

      const valueMaps = options.map((val, i) => {
        if (groupBy === "concept") {
          const concepts = aggregateByConcept(results[i].creatives);
          return {
            val,
            map: new Map(concepts.map((g) => [g.concept, extractMetrics(g)])),
          };
        }
        return {
          val,
          map: new Map(
            results[i].creatives.map((c) => [c.creative_name, extractMetrics(c)])
          ),
        };
      });

      const allNames = new Set<string>();
      for (const { map } of valueMaps) {
        for (const name of map.keys()) allNames.add(name);
      }

      const compared: ComparisonRow[] = Array.from(allNames)
        .map((name) => {
          const metrics: Record<string, CreativeMetrics | null> = {};
          for (const { val, map } of valueMaps) {
            metrics[val] = map.get(name) ?? null;
          }
          return { name, metrics };
        })
        .sort((a, b) => {
          const avgA = average(Object.values(a.metrics).map((m) => m?.composite_score ?? null));
          const avgB = average(Object.values(b.metrics).map((m) => m?.composite_score ?? null));
          return avgB - avgA;
        });

      setComparedValues(options);
      setRows(compared);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Comparison failed. Try re-uploading your data.");
    } finally {
      setIsLoading(false);
    }
  }, [uploadId, dimension, options, groupBy, baseFilters]);

  const currentMetricDef = METRICS.find((m) => m.key === selectedMetric)!;
  const activeGlobalFilters = Object.entries(activeFilters)
    .filter(([k, v]) => v && v !== "All" && k !== dimension)
    .map(([k, v]) => `${k}=${v}`);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Pivot by</label>
          <Select value={dimension} onValueChange={handleDimensionChange}>
            <SelectTrigger className="w-[220px] bg-zinc-900 border-zinc-700">
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
          <label className="text-xs text-zinc-500 uppercase">Metric</label>
          <Select value={selectedMetric} onValueChange={(v) => v && setSelectedMetric(v)}>
            <SelectTrigger className="w-[160px] bg-zinc-900 border-zinc-700">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {METRICS.map((m) => (
                <SelectItem key={m.key} value={m.key}>{m.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Comparing</label>
          <span className="text-sm text-zinc-400 px-2 py-1.5">
            {options.length > 0 ? `${options.length} values` : "No values"}
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
                {comparedValues.map((val) => (
                  <TableHead key={val} className="text-zinc-500 text-center min-w-[120px]">
                    <div>{val}</div>
                    <div className="text-[10px] text-zinc-600 font-normal">{currentMetricDef.label}</div>
                  </TableHead>
                ))}
                <TableHead className="text-zinc-500 text-center min-w-[80px]">Spread</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => {
                const values = comparedValues.map(
                  (val) => (r.metrics[val]?.[selectedMetric as keyof CreativeMetrics] as number) ?? null
                );
                const valid = values.filter((v): v is number => v != null);
                const spread =
                  valid.length >= 2
                    ? Math.round((Math.max(...valid) - Math.min(...valid)) * 100) / 100
                    : null;

                return (
                  <TableRow key={r.name} className="border-zinc-800">
                    <TableCell className="font-medium sticky left-0 bg-zinc-950 z-10 max-w-[250px] truncate">
                      {selectedMetric === "composite_score" && r.metrics[comparedValues[0]] ? (
                        <div className="flex items-center gap-2">
                          <TierBadge
                            tier={r.metrics[comparedValues[0]]!.tier}
                            score={r.metrics[comparedValues[0]]!.composite_score}
                          />
                          <span className="truncate">{r.name}</span>
                        </div>
                      ) : (
                        r.name
                      )}
                    </TableCell>
                    {comparedValues.map((val, i) => {
                      const m = r.metrics[val];
                      const v = values[i];
                      return (
                        <TableCell key={val} className="text-center">
                          {selectedMetric === "composite_score" && m ? (
                            <TierBadge tier={m.tier} score={m.composite_score} />
                          ) : (
                            <span
                              className={`font-mono text-sm ${metricCellClass(selectedMetric, v, values)}`}
                            >
                              {currentMetricDef.format(v)}
                            </span>
                          )}
                        </TableCell>
                      );
                    })}
                    <TableCell className="text-center">
                      {spread !== null ? (
                        <span
                          className={`font-mono text-sm ${
                            selectedMetric === "composite_score" && spread > 15
                              ? "text-amber-400 font-bold"
                              : "text-zinc-400"
                          }`}
                        >
                          {selectedMetric === "composite_score"
                            ? spread.toFixed(1)
                            : currentMetricDef.format(spread)}
                        </span>
                      ) : (
                        <span className="text-zinc-600">--</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
