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
  { key: "os", label: "OS", optionsKey: "os" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "asset_type", label: "Asset Type", optionsKey: "asset_types" },
  { key: "placement", label: "Placement", optionsKey: "placements" },
  { key: "buying_type", label: "Buying Type", optionsKey: "buying_types" },
];

interface ComparisonRow {
  creative_name: string;
  left_score: number | null;
  right_score: number | null;
  left_tier: string;
  right_tier: string;
  delta: number | null;
}

export function ComparisonView({ uploadId, filters }: ComparisonViewProps) {
  const [dimension, setDimension] = useState("os");
  const [leftValue, setLeftValue] = useState("");
  const [rightValue, setRightValue] = useState("");
  const [rows, setRows] = useState<ComparisonRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const currentDef = DIMENSION_OPTIONS.find((d) => d.key === dimension)!;
  const options = filters[currentDef.optionsKey];

  const handleCompare = useCallback(async () => {
    if (!leftValue || !rightValue) return;
    setIsLoading(true);
    try {
      const [leftRes, rightRes] = await Promise.all([
        rescore(uploadId, { [dimension]: leftValue }),
        rescore(uploadId, { [dimension]: rightValue }),
      ]);

      const leftMap = new Map(
        leftRes.creatives.map((c) => [c.creative_name, c])
      );
      const rightMap = new Map(
        rightRes.creatives.map((c) => [c.creative_name, c])
      );

      const allNames = new Set([...leftMap.keys(), ...rightMap.keys()]);
      const compared: ComparisonRow[] = Array.from(allNames)
        .map((name) => {
          const l = leftMap.get(name);
          const r = rightMap.get(name);
          return {
            creative_name: name,
            left_score: l?.composite_score ?? null,
            right_score: r?.composite_score ?? null,
            left_tier: l?.tier ?? "",
            right_tier: r?.tier ?? "",
            delta:
              l && r ? Math.round((l.composite_score - r.composite_score) * 10) / 10 : null,
          };
        })
        .sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0));

      setRows(compared);
    } catch {
      // Error handled silently — user sees empty table
    } finally {
      setIsLoading(false);
    }
  }, [uploadId, dimension, leftValue, rightValue]);

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Dimension</label>
          <Select value={dimension} onValueChange={(v) => { if (v) setDimension(v); }}>
            <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700">
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
          <label className="text-xs text-zinc-500 uppercase">Left</label>
          <Select value={leftValue} onValueChange={(v) => setLeftValue(v ?? "")}>
            <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {options.map((o) => (
                <SelectItem key={o} value={o}>{o}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Right</label>
          <Select value={rightValue} onValueChange={(v) => setRightValue(v ?? "")}>
            <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {options.map((o) => (
                <SelectItem key={o} value={o}>{o}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          onClick={handleCompare}
          disabled={!leftValue || !rightValue || isLoading}
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
              <TableHead className="text-zinc-500">{leftValue} Score</TableHead>
              <TableHead className="text-zinc-500">{rightValue} Score</TableHead>
              <TableHead className="text-zinc-500">Score Difference</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.creative_name} className="border-zinc-800">
                <TableCell className="font-medium">{r.creative_name}</TableCell>
                <TableCell>
                  {r.left_score !== null ? (
                    <TierBadge tier={r.left_tier} score={r.left_score} />
                  ) : (
                    <span className="text-zinc-600">--</span>
                  )}
                </TableCell>
                <TableCell>
                  {r.right_score !== null ? (
                    <TierBadge tier={r.right_tier} score={r.right_score} />
                  ) : (
                    <span className="text-zinc-600">--</span>
                  )}
                </TableCell>
                <TableCell>
                  {r.delta !== null ? (
                    <span
                      className={`font-mono text-sm ${
                        Math.abs(r.delta) > 15
                          ? r.delta > 0
                            ? "text-green-400 font-bold"
                            : "text-red-400 font-bold"
                          : "text-zinc-400"
                      }`}
                    >
                      {r.delta > 0 ? "+" : ""}
                      {r.delta}
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
