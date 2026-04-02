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
    <div className={`relative rounded-lg border border-[oklch(1_0_0/8%)] overflow-hidden ${isLoading ? "opacity-50" : ""}`}>
      <Table>
        <TableHeader>
          <TableRow className="border-[oklch(1_0_0/6%)] bg-[oklch(0.18_0.005_265)] hover:bg-[oklch(0.18_0.005_265)]">
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium w-12">#</TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium">Creative</TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium cursor-pointer select-none" onClick={() => handleSort("composite_score")}>
              Score{sortIcon("composite_score")}
            </TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium">Platform</TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium">Objective</TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium">Format</TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium cursor-pointer select-none font-mono" onClick={() => handleSort("vtr_2s")}>
              VTR{sortIcon("vtr_2s")}
            </TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium cursor-pointer select-none font-mono" onClick={() => handleSort("completion_rate")}>
              Comp%{sortIcon("completion_rate")}
            </TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium cursor-pointer select-none font-mono" onClick={() => handleSort("ctr")}>
              CTR{sortIcon("ctr")}
            </TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium cursor-pointer select-none font-mono" onClick={() => handleSort("spend")}>
              Spend{sortIcon("spend")}
            </TableHead>
            <TableHead className="text-[#9aa0a6] text-[11px] font-medium">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((c, i) => (
            <React.Fragment key={`${c.creative_name}-${c.os_target}-${c.placement}-${i}`}>
              <TableRow
                className="border-[oklch(1_0_0/5%)] cursor-pointer hover:bg-[oklch(0.22_0.005_265)] transition-colors"
                onClick={() =>
                  setExpandedRow(
                    expandedRow === `${i}` ? null : `${i}`
                  )
                }
              >
                <TableCell className="font-mono text-[#9aa0a6] text-xs">{i + 1}</TableCell>
                <TableCell className="max-w-[280px] truncate text-sm font-medium text-[#e8eaed]">
                  {c.creative_name}
                </TableCell>
                <TableCell>
                  <TierBadge tier={c.tier} score={c.composite_score} />
                </TableCell>
                <TableCell className="text-xs text-[#bdc1c6]">{c.platform}</TableCell>
                <TableCell className="text-xs text-[#bdc1c6]">{c.objective}</TableCell>
                <TableCell className="text-xs text-[#bdc1c6]">{c.format}</TableCell>
                <TableCell className="font-mono text-xs text-[#e8eaed]">{c.vtr_2s?.toFixed(1)}%</TableCell>
                <TableCell className="font-mono text-xs text-[#e8eaed]">{c.completion_rate?.toFixed(1)}%</TableCell>
                <TableCell className="font-mono text-xs text-[#e8eaed]">{c.ctr?.toFixed(3)}%</TableCell>
                <TableCell className="font-mono text-xs text-[#e8eaed]">
                  {"\u00A3"}{c.spend?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </TableCell>
                <TableCell>
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                    c.action === "Scale Up" ? "bg-[#34a853]/15 text-[#81c995]" :
                    c.action === "Keep Running" ? "bg-[#1a73e8]/15 text-[#8ab4f8]" :
                    c.action === "Pause" ? "bg-[#ea4335]/15 text-[#f28b82]" :
                    "bg-[oklch(0.26_0.005_265)] text-[#9aa0a6]"
                  }`}>
                    {c.action}
                  </span>
                </TableCell>
              </TableRow>
              {expandedRow === `${i}` && (
                <TableRow className="border-[oklch(1_0_0/4%)] bg-[oklch(0.18_0.005_265)]">
                  <TableCell colSpan={11} className="py-3 px-6">
                    <div className="space-y-1.5">
                      <p className="text-sm text-[#bdc1c6]">{c.explanation}</p>
                      <p className="text-[11px] text-[#9aa0a6] font-mono">
                        OS: {c.os_target} | Asset: {c.asset_type_canonical} | Group: {c.scoring_group}
                        {c.low_confidence && (
                          <span className="text-[#f9ab00] ml-2">LOW CONFIDENCE</span>
                        )}
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
