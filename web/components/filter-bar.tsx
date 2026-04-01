"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { FilterOptions, ActiveFilters, GroupBy } from "@/lib/types";

interface FilterBarProps {
  filters: FilterOptions;
  activeFilters: ActiveFilters;
  onFilterChange: (key: string, value: string) => void;
  onRescore: () => void;
  isRescoring: boolean;
  groupBy: GroupBy;
  onGroupByChange: (g: GroupBy) => void;
}

const FILTER_DEFS: { key: string; label: string; optionsKey: keyof FilterOptions }[] = [
  { key: "campaign", label: "Campaign", optionsKey: "campaigns" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "os", label: "OS", optionsKey: "os" },
  { key: "placement", label: "Placement", optionsKey: "placements" },
  { key: "objective", label: "Objective", optionsKey: "objectives" },
  { key: "format", label: "Format", optionsKey: "formats" },
  { key: "asset_type", label: "Asset Type", optionsKey: "asset_types" },
  { key: "buying_type", label: "Buying Type", optionsKey: "buying_types" },
];

export function FilterBar({
  filters,
  activeFilters,
  onFilterChange,
  onRescore,
  isRescoring,
  groupBy,
  onGroupByChange,
}: FilterBarProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3 items-center">
        {FILTER_DEFS.map((def) => (
          <div key={def.key} className="flex flex-col gap-1">
            <label className="text-xs text-zinc-500 uppercase tracking-wider">
              {def.label}
            </label>
            <Select
              value={activeFilters[def.key] || "All"}
              onValueChange={(v) => onFilterChange(def.key, v ?? "All")}
            >
              <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {filters[def.optionsKey].map((opt) => (
                  <SelectItem key={opt} value={opt}>
                    {opt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="sm"
          onClick={onRescore}
          disabled={isRescoring}
          className="border-zinc-600"
        >
          {isRescoring ? (
            <>
              <span className="h-3 w-3 animate-spin rounded-full border border-zinc-400 border-t-transparent mr-2" />
              Re-scoring...
            </>
          ) : (
            "Re-score within filters"
          )}
        </Button>
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-xs text-zinc-500">Group by:</span>
          <Select
            value={groupBy}
            onValueChange={(v) => { if (v) onGroupByChange(v as GroupBy); }}
          >
            <SelectTrigger className="w-[160px] bg-zinc-900 border-zinc-700 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="creative_name">Creative Name</SelectItem>
              <SelectItem value="concept">Concept</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
