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
import type { FilterOptions } from "@/lib/types";

interface ComparisonViewProps {
  uploadId: string;
  filters: FilterOptions;
}

const DIMENSION_OPTIONS: { key: string; label: string; optionsKey: keyof FilterOptions }[] = [
  { key: "asset_subtype", label: "Brand / Creator / Partner", optionsKey: "asset_subtypes" },
  { key: "os", label: "OS", optionsKey: "os" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "placement", label: "Placement", optionsKey: "placements" },
  { key: "objective", label: "Objective", optionsKey: "objectives" },
  { key: "buying_type", label: "Buying Type", optionsKey: "buying_types" },
  { key: "concept", label: "Concept", optionsKey: "concepts" },
  { key: "format", label: "Format", optionsKey: "formats" },
];

interface ComparisonRow {
  creative_name: string;
  scores: Record<string, { score: number; tier: string } | null>;
  spread: number | null;
}

export function ComparisonView({ uploadId, filters }: ComparisonViewProps) {
  const [dimension, setDimension] = useState("asset_subtype");
  const [rows, setRows] = useState<ComparisonRow[]>([]);
  const [comparedValues, setComparedValues] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const currentDef = DIMENSION_OPTIONS.find((d) => d.key === dimension)!;
  const options = filters[currentDef.optionsKey] ?? [];

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
    try {
      const results = await Promise.all(
        options.map((val) => rescore(uploadId, { [dimension]: val }))
      );

      // Build a map per value: creative_name -> { score, tier }
      const valueMaps = options.map((val, i) => ({
        val,
        map: new Map(
          results[i].creatives.map((c) => [
            c.creative_name,
            { score: c.composite_score, tier: c.tier },
          ])
        ),
      }));

      // Collect all creative names
      const allNames = new Set<string>();
      for (const { map } of valueMaps) {
        for (const name of map.keys()) allNames.add(name);
      }

      const compared: ComparisonRow[] = Array.from(allNames)
        .map((name) => {
          const scores: Record<string, { score: number; tier: string } | null> = {};
          const validScores: number[] = [];
          for (const { val, map } of valueMaps) {
            const entry = map.get(name) ?? null;
            scores[val] = entry;
            if (entry) validScores.push(entry.score);
          }
          const spread =
            validScores.length >= 2
              ? Math.round((Math.max(...validScores) - Math.min(...validScores)) * 10) / 10
              : null;
          return { creative_name: name, scores, spread };
        })
        .sort((a, b) => Math.abs(b.spread ?? 0) - Math.abs(a.spread ?? 0));

      setComparedValues(options);
      setRows(compared);
    } catch {
      // Error handled silently — user sees empty table
    } finally {
      setIsLoading(false);
    }
  }, [uploadId, dimension, options]);

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Dimension</label>
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

      {rows.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-500">Creative</TableHead>
              {comparedValues.map((val) => (
                <TableHead key={val} className="text-zinc-500">{val}</TableHead>
              ))}
              <TableHead className="text-zinc-500">Spread</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.creative_name} className="border-zinc-800">
                <TableCell className="font-medium">{r.creative_name}</TableCell>
                {comparedValues.map((val) => {
                  const entry = r.scores[val];
                  return (
                    <TableCell key={val}>
                      {entry ? (
                        <TierBadge tier={entry.tier} score={entry.score} />
                      ) : (
                        <span className="text-zinc-600">--</span>
                      )}
                    </TableCell>
                  );
                })}
                <TableCell>
                  {r.spread !== null ? (
                    <span
                      className={`font-mono text-sm ${
                        r.spread > 15 ? "text-amber-400 font-bold" : "text-zinc-400"
                      }`}
                    >
                      {r.spread}
                    </span>
                  ) : (
                    <span className="text-zinc-600">--</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
