import { TIER_COLORS } from "@/lib/types";

export function TierBadge({ tier, score }: { tier: string; score: number }) {
  const color = TIER_COLORS[tier] || "#9aa0a6";
  return (
    <span
      className="inline-flex items-center gap-1.5 font-mono text-xs font-medium"
      style={{ color }}
    >
      <span
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: color }}
      />
      {score.toFixed(1)}
    </span>
  );
}
