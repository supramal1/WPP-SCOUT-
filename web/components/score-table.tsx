"use client";

import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TierBadge } from "./tier-badge";
import type { Creative } from "@/lib/types";

interface ScoreTableProps {
  creatives: Creative[];
  isLoading?: boolean;
}

type SortKey = "composite_score" | "spend" | "vtr_2s" | "ctr" | "engagement_rate" | "completion_rate" | "cpm";

export function ScoreTable({ creatives, isLoading }: ScoreTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortAsc, setSortAsc] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const sorted = [...creatives].sort((a, b) => {
    const av = a[sortKey] ?? 0;
    const bv = b[sortKey] ?? 0;
    return sortAsc ? av - bv : bv - av;
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortAsc ? " \u2191" : " \u2193") : "";

  return (
    <div className={`relative ${isLoading ? "opacity-50" : ""}`}>
      <Table>
        <TableHeader>
          <TableRow className="border-zinc-800 hover:bg-transparent">
            <TableHead className="text-zinc-500 w-12">#</TableHead>
            <TableHead className="text-zinc-500">Creative</TableHead>
            <TableHead className="text-zinc-500 cursor-pointer" onClick={() => handleSort("composite_score")}>
              Score{sortIcon("composite_score")}
            </TableHead>
            <TableHead className="text-zinc-500">Platform</TableHead>
            <TableHead className="text-zinc-500">Objective</TableHead>
            <TableHead className="text-zinc-500">Format</TableHead>
            <TableHead className="text-zinc-500 cursor-pointer font-mono" onClick={() => handleSort("vtr_2s")}>
              VTR{sortIcon("vtr_2s")}
            </TableHead>
            <TableHead className="text-zinc-500 cursor-pointer font-mono" onClick={() => handleSort("completion_rate")}>
              Comp%{sortIcon("completion_rate")}
            </TableHead>
            <TableHead className="text-zinc-500 cursor-pointer font-mono" onClick={() => handleSort("ctr")}>
              CTR{sortIcon("ctr")}
            </TableHead>
            <TableHead className="text-zinc-500 cursor-pointer font-mono" onClick={() => handleSort("spend")}>
              Spend{sortIcon("spend")}
            </TableHead>
            <TableHead className="text-zinc-500">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((c, i) => (
            <React.Fragment key={`${c.creative_name}-${c.os_target}-${c.placement}-${i}`}>
              <TableRow
                className="border-zinc-800 cursor-pointer hover:bg-zinc-900/50"
                onClick={() =>
                  setExpandedRow(
                    expandedRow === `${i}` ? null : `${i}`
                  )
                }
              >
                <TableCell className="font-mono text-zinc-500">{i + 1}</TableCell>
                <TableCell className="max-w-[280px] truncate font-medium">
                  {c.creative_name}
                </TableCell>
                <TableCell>
                  <TierBadge tier={c.tier} score={c.composite_score} />
                </TableCell>
                <TableCell className="text-sm text-zinc-400">{c.platform}</TableCell>
                <TableCell className="text-sm text-zinc-400">{c.objective}</TableCell>
                <TableCell className="text-sm text-zinc-400">{c.format}</TableCell>
                <TableCell className="font-mono text-sm">{c.vtr_2s?.toFixed(1)}%</TableCell>
                <TableCell className="font-mono text-sm">{c.completion_rate?.toFixed(1)}%</TableCell>
                <TableCell className="font-mono text-sm">{c.ctr?.toFixed(3)}%</TableCell>
                <TableCell className="font-mono text-sm">
                  {"\u00A3"}{c.spend?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </TableCell>
                <TableCell>
                  <span className={`text-xs px-2 py-1 rounded ${
                    c.action === "Scale Up" ? "bg-green-900/40 text-green-400" :
                    c.action === "Keep Running" ? "bg-blue-900/40 text-blue-400" :
                    c.action === "Pause" ? "bg-red-900/40 text-red-400" :
                    "bg-zinc-800 text-zinc-400"
                  }`}>
                    {c.action}
                  </span>
                </TableCell>
              </TableRow>
              {expandedRow === `${i}` && (
                <TableRow className="border-zinc-800/50 bg-zinc-900/30">
                  <TableCell colSpan={11} className="py-4 px-6">
                    <div className="space-y-1">
                      <p>{c.explanation}</p>
                      <p className="text-xs text-zinc-600 font-mono">
                        OS: {c.os_target} | Asset: {c.asset_type_canonical} | Group: {c.scoring_group}
                        {c.low_confidence && " | LOW CONFIDENCE"}
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
