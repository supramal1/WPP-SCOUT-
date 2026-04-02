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
    { label: "Total Creatives", value: totalCount.toLocaleString() },
    { label: "Filtered", value: filteredCount.toLocaleString() },
    { label: "Avg Score", value: avgScore.toFixed(1), accent: true },
    { label: "Top Performers", value: topPerformers.toLocaleString(), accent: true },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {stats.map((s) => (
        <div
          key={s.label}
          className="rounded-lg bg-[oklch(0.2_0.005_265)] border border-[oklch(1_0_0/8%)] px-4 py-3"
        >
          <p className="text-[11px] font-medium text-[#9aa0a6] uppercase tracking-wide">{s.label}</p>
          <p className={`text-2xl font-semibold font-mono mt-0.5 ${s.accent ? "text-[#8ab4f8]" : "text-[#e8eaed]"}`}>
            {s.value}
          </p>
        </div>
      ))}
    </div>
  );
}
