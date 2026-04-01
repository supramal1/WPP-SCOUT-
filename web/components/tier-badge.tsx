import { Badge } from "@/components/ui/badge";
import { TIER_COLORS } from "@/lib/types";

export function TierBadge({ tier, score }: { tier: string; score: number }) {
  const color = TIER_COLORS[tier] || "#a1a1aa";
  return (
    <Badge
      variant="outline"
      className="font-mono text-xs"
      style={{ borderColor: color, color }}
    >
      {score.toFixed(1)}
    </Badge>
  );
}
