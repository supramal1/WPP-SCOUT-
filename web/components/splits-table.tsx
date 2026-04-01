"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SplitRow } from "@/lib/types";

interface SplitsTableProps {
  splits: SplitRow[];
}

const COLUMNS: { key: keyof SplitRow; label: string; mono?: boolean }[] = [
  { key: "creative_name", label: "Creative" },
  { key: "platform", label: "Platform" },
  { key: "buying_type", label: "Type" },
  { key: "format_canonical", label: "Format" },
  { key: "placement_canonical", label: "Placement" },
  { key: "objective_normalized", label: "Objective" },
  { key: "os_target", label: "OS" },
  { key: "asset_type_canonical", label: "Asset" },
  { key: "campaign_normalized", label: "Campaign" },
  { key: "audience_segment", label: "Audience" },
  { key: "concept", label: "Concept" },
  { key: "spend", label: "Spend", mono: true },
  { key: "reach", label: "Reach", mono: true },
  { key: "impressions", label: "Impr.", mono: true },
  { key: "frequency", label: "Freq", mono: true },
  { key: "vtr_2s", label: "VTR", mono: true },
  { key: "completion_rate", label: "Comp%", mono: true },
  { key: "ctr", label: "CTR", mono: true },
  { key: "engagement_rate", label: "Eng%", mono: true },
  { key: "cpm", label: "CPM", mono: true },
  { key: "duration_s", label: "Dur(s)", mono: true },
];

function formatCell(key: keyof SplitRow, val: SplitRow[keyof SplitRow]): string {
  if (val === null || val === undefined || val === "") return "--";
  if (typeof val === "boolean") return val ? "Yes" : "No";
  if (key === "spend") return `\u00A3${(val as number).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (key === "reach" || key === "impressions") return (val as number).toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (key === "vtr_2s" || key === "completion_rate" || key === "ctr" || key === "engagement_rate") return `${(val as number).toFixed(2)}%`;
  if (key === "cpm") return `\u00A3${(val as number).toFixed(2)}`;
  if (key === "frequency") return (val as number).toFixed(2);
  if (key === "duration_s") return `${val}s`;
  return String(val);
}

export function SplitsTable({ splits }: SplitsTableProps) {
  if (splits.length === 0) {
    return (
      <div className="rounded-md bg-zinc-900 border border-zinc-800 p-8 text-center text-zinc-500 text-sm">
        Loading splits data...
      </div>
    );
  }

  return (
    <div className="relative overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow className="border-zinc-800 hover:bg-transparent">
            {COLUMNS.map((col) => (
              <TableHead
                key={col.key}
                className={`text-zinc-500 text-xs whitespace-nowrap ${col.mono ? "font-mono" : ""}`}
              >
                {col.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {splits.map((row, i) => (
            <TableRow key={i} className="border-zinc-800 hover:bg-zinc-900/50">
              {COLUMNS.map((col) => (
                <TableCell
                  key={col.key}
                  className={`text-xs whitespace-nowrap ${col.mono ? "font-mono text-zinc-400" : "text-zinc-300"}`}
                >
                  {formatCell(col.key, row[col.key])}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
