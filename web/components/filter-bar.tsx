"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { FilterOptions, ActiveFilters } from "@/lib/types";

interface FilterBarProps {
  filters: FilterOptions;
  activeFilters: ActiveFilters;
  onFilterChange: (key: string, value: string) => void;
  onRescore: () => void;
  isRescoring: boolean;
}

const FILTER_DEFS: { key: string; label: string; optionsKey: keyof FilterOptions }[] = [
  { key: "campaign", label: "Campaign", optionsKey: "campaigns" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "os", label: "OS", optionsKey: "os" },
  { key: "placement", label: "Placement", optionsKey: "placements" },
  { key: "objective", label: "Objective", optionsKey: "objectives" },
  { key: "format", label: "Format", optionsKey: "formats" },
  { key: "asset_type", label: "Asset Type", optionsKey: "asset_types" },
  { key: "asset_subtype", label: "Brand / Creator / Partner", optionsKey: "asset_subtypes" },
  { key: "buying_type", label: "Buying Type", optionsKey: "buying_types" },
  { key: "concept", label: "Concept", optionsKey: "concepts" },
];

export function FilterBar({
  filters,
  activeFilters,
  onFilterChange,
  onRescore,
  isRescoring,
}: FilterBarProps) {
  const activeCount = Object.values(activeFilters).filter((v) => v && v !== "All").length;

  return (
    <div className="rounded-lg bg-[oklch(0.2_0.005_265)] border border-[oklch(1_0_0/8%)] p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium text-[#9aa0a6] uppercase tracking-wide">Filters</h3>
        {activeCount > 0 && (
          <span className="text-[11px] text-[#8ab4f8] font-medium">{activeCount} active</span>
        )}
      </div>
      <div className="flex flex-wrap gap-2.5">
        {FILTER_DEFS.map((def) => (
          <div key={def.key} className="flex flex-col gap-1">
            <label className="text-[10px] text-[#9aa0a6] font-medium uppercase tracking-wider">
              {def.label}
            </label>
            <Select
              value={activeFilters[def.key] || "All"}
              onValueChange={(v) => onFilterChange(def.key, v ?? "All")}
            >
              <SelectTrigger className="w-[130px] h-8 bg-[oklch(0.16_0.005_265)] border-[oklch(1_0_0/10%)] text-xs">
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
      <Button
        size="sm"
        onClick={onRescore}
        disabled={isRescoring || activeCount === 0}
        className="bg-[#1a73e8] hover:bg-[#1967d2] text-white text-xs font-medium h-8 px-4"
      >
        {isRescoring ? (
          <>
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white mr-2" />
            Re-scoring...
          </>
        ) : (
          "Re-score"
        )}
      </Button>
    </div>
  );
}
