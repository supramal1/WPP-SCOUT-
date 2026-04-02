"use client";

import React, { useState, useMemo } from "react";
import type { Creative, GroupBy } from "@/lib/types";
import { OverviewDashboard } from "./overview-dashboard";
import { CreativeExplorer } from "./creative-explorer";
import { ComparisonTable } from "./comparison-table";

interface CampaignTabsProps {
  creatives: Creative[];
  allCreatives: Creative[];
  groupBy: GroupBy;
  isLoading?: boolean;
}

const SUB_TABS = [
  "Overview",
  "Compare",
  "Asset Type",
  "OS",
  "Placement",
  "Objective",
] as const;
type SubTab = (typeof SUB_TABS)[number];

function deriveTabs(creatives: Creative[]): string[] {
  const combos = new Set<string>();
  for (const c of creatives) {
    const label = [c.campaign_normalized, c.platform, c.format]
      .filter(Boolean)
      .join(" \u00D7 ");
    if (label) combos.add(label);
  }
  return Array.from(combos).sort();
}

function filterByTab(creatives: Creative[], tab: string): Creative[] {
  if (tab === "All") return creatives;
  return creatives.filter((c) => {
    const label = [c.campaign_normalized, c.platform, c.format]
      .filter(Boolean)
      .join(" \u00D7 ");
    return label === tab;
  });
}

export function CampaignTabs({
  creatives,
  allCreatives,
  groupBy,
  isLoading,
}: CampaignTabsProps) {
  const [activeTab, setActiveTab] = useState("All");
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("Overview");

  // Derive tabs from ALL creatives so they don't disappear on filter
  const tabs = useMemo(() => deriveTabs(allCreatives), [allCreatives]);

  // Content uses filtered creatives, further filtered by active tab
  const tabCreatives = useMemo(
    () => filterByTab(creatives, activeTab),
    [creatives, activeTab]
  );

  return (
    <div
      className={`space-y-4 ${isLoading ? "opacity-50 pointer-events-none" : ""}`}
    >
      {/* Campaign tabs */}
      <div className="overflow-x-auto -mx-1 pb-1">
        <div className="flex items-center gap-1.5 px-1 min-w-max">
          <button
            onClick={() => {
              setActiveTab("All");
              setActiveSubTab("Overview");
            }}
            className={`px-3.5 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
              activeTab === "All"
                ? "bg-[#1a73e8] text-white shadow-sm"
                : "bg-[#f1f3f4] text-[#5f6368] hover:bg-[#e8eaed]"
            }`}
          >
            All Campaigns
          </button>
          {tabs.map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab);
                setActiveSubTab("Overview");
              }}
              className={`px-3.5 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                activeTab === tab
                  ? "bg-[#1a73e8] text-white shadow-sm"
                  : "bg-[#f1f3f4] text-[#5f6368] hover:bg-[#e8eaed]"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Sub-tabs */}
      <div className="border-b border-[#dadce0]">
        <div className="flex items-center">
          {SUB_TABS.map((st) => (
            <button
              key={st}
              onClick={() => setActiveSubTab(st)}
              className={`px-4 py-2.5 text-xs font-medium transition-colors relative ${
                activeSubTab === st
                  ? "text-[#1a73e8]"
                  : "text-[#5f6368] hover:text-[#202124]"
              }`}
            >
              {st}
              {activeSubTab === st && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#1a73e8] rounded-full" />
              )}
            </button>
          ))}
          <div className="ml-auto text-[11px] text-[#5f6368] font-mono pr-2">
            {tabCreatives.length} creatives
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="min-h-[200px]">
        {activeSubTab === "Overview" ? (
          <OverviewDashboard
            creatives={tabCreatives}
            groupBy={groupBy}
          />
        ) : activeSubTab === "Compare" ? (
          <ComparisonTable creatives={tabCreatives} />
        ) : (
          <CreativeExplorer
            creatives={tabCreatives}
            dimension={activeSubTab}
          />
        )}
      </div>
    </div>
  );
}
