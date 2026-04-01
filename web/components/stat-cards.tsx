import { Card, CardContent } from "@/components/ui/card";
import type { Creative } from "@/lib/types";

interface StatCardsProps {
  creatives: Creative[];
  totalCount: number;
}

export function StatCards({ creatives, totalCount }: StatCardsProps) {
  const filteredCount = creatives.length;
  const avgScore =
    filteredCount > 0
      ? creatives.reduce((s, c) => s + c.composite_score, 0) / filteredCount
      : 0;
  const topPerformers = creatives.filter((c) => c.tier === "Top Performer").length;

  const stats = [
    { label: "Total Creatives", value: totalCount, mono: true },
    { label: "Filtered", value: filteredCount, mono: true },
    { label: "Avg Score", value: avgScore.toFixed(1), mono: true },
    { label: "Top Performers", value: topPerformers, mono: true },
  ];

  return (
    <div className="grid grid-cols-4 gap-4">
      {stats.map((s) => (
        <Card key={s.label} className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500">{s.label}</p>
            <p className={`text-2xl font-bold ${s.mono ? "font-mono" : ""}`}>
              {s.value}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
