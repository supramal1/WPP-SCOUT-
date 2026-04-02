"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { FilterOptions, ActiveFilters } from "@/lib/types";

interface GlobalFilterBarProps {
  filters: FilterOptions;
  activeFilters: ActiveFilters;
  onFilterChange: (key: string, value: string) => void;
  onRescore: () => void;
  isRescoring: boolean;
}

const GLOBAL_FILTERS: { key: string; label: string; optionsKey: keyof FilterOptions }[] = [
  { key: "campaign", label: "Campaign", optionsKey: "campaigns" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "format", label: "Format", optionsKey: "formats" },
  { key: "concept", label: "Concept", optionsKey: "concepts" },
];

export function GlobalFilterBar({
  filters,
  activeFilters,
  onFilterChange,
  onRescore,
  isRescoring,
}: GlobalFilterBarProps) {
  const activeCount = Object.values(activeFilters).filter(
    (v) => v && v !== "All"
  ).length;

  return (
    <div className="flex items-center gap-2.5 flex-wrap">
      {GLOBAL_FILTERS.map((def) => (
        <Select
          key={def.key}
          value={activeFilters[def.key] || "All"}
          onValueChange={(v) => onFilterChange(def.key, v ?? "All")}
        >
          <SelectTrigger className="h-8 w-[150px] rounded-full bg-[#f3e8fd] border-0 text-xs font-medium text-[#5f6368] hover:bg-[#e8d5f5] focus:ring-1 focus:ring-[#1a73e8]">
            <span className="truncate">
              {activeFilters[def.key] && activeFilters[def.key] !== "All"
                ? activeFilters[def.key]
                : `All ${def.label}s`}
            </span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="All">All {def.label}s</SelectItem>
            {filters[def.optionsKey].map((opt) => (
              <SelectItem key={opt} value={opt}>
                {opt}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ))}

      <button
        onClick={onRescore}
        disabled={isRescoring || activeCount === 0}
        className="h-8 px-4 rounded-full bg-[#1a73e8] text-white text-xs font-medium hover:bg-[#1967d2] disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
      >
        {isRescoring && (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
        )}
        {isRescoring ? "Re-scoring..." : "Re-score"}
      </button>

      {activeCount > 0 && (
        <span className="text-xs text-[#1a73e8] font-medium">
          {activeCount} filter{activeCount > 1 ? "s" : ""} active
        </span>
      )}
    </div>
  );
}
