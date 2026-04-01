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
import type { ConceptGroup } from "@/lib/types";

interface ConceptViewProps {
  concepts: ConceptGroup[];
  isLoading?: boolean;
}

export function ConceptView({ concepts, isLoading }: ConceptViewProps) {
  const [expandedConcept, setExpandedConcept] = useState<string | null>(null);

  return (
    <div className={`relative ${isLoading ? "opacity-50" : ""}`}>
      <Table>
        <TableHeader>
          <TableRow className="border-zinc-800 hover:bg-transparent">
            <TableHead className="text-zinc-500 w-12">#</TableHead>
            <TableHead className="text-zinc-500">Concept</TableHead>
            <TableHead className="text-zinc-500">Score</TableHead>
            <TableHead className="text-zinc-500 font-mono">Variations</TableHead>
            <TableHead className="text-zinc-500 font-mono">Best</TableHead>
            <TableHead className="text-zinc-500 font-mono">Worst</TableHead>
            <TableHead className="text-zinc-500 font-mono">VTR</TableHead>
            <TableHead className="text-zinc-500 font-mono">CTR</TableHead>
            <TableHead className="text-zinc-500 font-mono">Spend</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {concepts.map((g, i) => (
            <React.Fragment key={g.concept}>
              <TableRow
                className="border-zinc-800 cursor-pointer hover:bg-zinc-900/50"
                onClick={() =>
                  setExpandedConcept(expandedConcept === g.concept ? null : g.concept)
                }
              >
                <TableCell className="font-mono text-zinc-500">{i + 1}</TableCell>
                <TableCell className="font-medium">{g.concept}</TableCell>
                <TableCell>
                  <TierBadge tier={g.tier} score={g.composite_score} />
                </TableCell>
                <TableCell className="font-mono text-sm">{g.n_variations}</TableCell>
                <TableCell className="font-mono text-sm text-green-400">
                  {g.best_variation_score.toFixed(1)}
                </TableCell>
                <TableCell className="font-mono text-sm text-red-400">
                  {g.worst_variation_score.toFixed(1)}
                </TableCell>
                <TableCell className="font-mono text-sm">{g.vtr_2s.toFixed(1)}%</TableCell>
                <TableCell className="font-mono text-sm">{g.ctr.toFixed(3)}%</TableCell>
                <TableCell className="font-mono text-sm">
                  {"\u00A3"}{g.spend.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </TableCell>
              </TableRow>
              {expandedConcept === g.concept &&
                g.creatives.map((c, j) => (
                  <TableRow
                    key={`${g.concept}-${j}`}
                    className="border-zinc-800/50 bg-zinc-900/20"
                  >
                    <TableCell />
                    <TableCell className="text-sm text-zinc-400 pl-8">
                      {c.creative_name}
                    </TableCell>
                    <TableCell>
                      <TierBadge tier={c.tier} score={c.composite_score} />
                    </TableCell>
                    <TableCell className="text-sm text-zinc-500">{c.platform}</TableCell>
                    <TableCell className="text-sm text-zinc-500">{c.os_target}</TableCell>
                    <TableCell className="text-sm text-zinc-500">{c.placement}</TableCell>
                    <TableCell className="font-mono text-sm text-zinc-400">
                      {c.vtr_2s?.toFixed(1)}%
                    </TableCell>
                    <TableCell className="font-mono text-sm text-zinc-400">
                      {c.ctr?.toFixed(3)}%
                    </TableCell>
                    <TableCell className="font-mono text-sm text-zinc-400">
                      {"\u00A3"}{c.spend?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </TableCell>
                  </TableRow>
                ))}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
