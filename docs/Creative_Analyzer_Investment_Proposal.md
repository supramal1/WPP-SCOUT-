# Creative Analyzer: From POC to Platform

**One-liner:** Turn a proven creative scoring prototype into an always-on creative intelligence platform that eliminates manual reporting, surfaces actionable insights in real time, and scales across campaigns, markets, and platforms.

---

## What We Have Today

A working Python CLI tool built for the Google Pixel DE campaign. It ingests Excel exports from Meta and TikTok, scores every creative 0-100 using an objective-aligned methodology, and outputs a formatted Excel workbook with rankings, explanations, and a filterable dashboard.

### Current Capabilities

| Capability | Detail |
|-----------|--------|
| **Scoring engine** | Weighted composite score (Primary KPI 50%, Secondary KPIs 25%, Cost Efficiency 15%, Attention Proxy 10%) with objective-aware metric selection |
| **Objective-aligned evaluation** | 7 objective types (Awareness, Reach, Video Views, Engagement, Traffic, Sales, Target Frequency) each scored against the KPI that matters for how the ad was bought |
| **Format-aware scoring** | Separate scoring paths for Video/Motion vs Static assets — static creatives are never penalised for missing VTR |
| **Cohort separation** | Paid vs Boosting scored independently — never compared across buying types |
| **Cross-platform analysis** | Meta + TikTok with canonical metric normalisation (3s VTR vs 2s VTR, platform-specific placements) |
| **Attention proxy** | Native platform metrics (hook rate, hold rate, completion) replace third-party brand measurement |
| **Duration-adjusted completion** | 15s video at 3% completion is benchmarked differently to 90s video at 0.5% |
| **Audience consistency** | Flags creatives that only perform well with one targeting group vs genuine all-round performers |
| **Frequency fatigue** | Automatic penalty for over-exposed creatives (frequency > 2x) |
| **Plain-English explanations** | Every creative gets a written explanation of why it scored the way it did |
| **Split analysis** | OS, device, audience segment, placement breakdowns preserved at ad-line level |
| **Output** | Interactive Excel dashboard with filters + Looker Studio export + Google Sheets compatibility |

### Current Limitations

| Limitation | Impact |
|-----------|--------|
| **Manual Excel ingestion** | Someone has to export data from platform UIs and run the script |
| **Single-campaign scope** | One run = one campaign. No historical trending, no cross-campaign comparison |
| **Excel-based dashboard** | Filters are pre-rendered, not truly interactive. No real-time updates |
| **No creative asset analysis** | Scores are based on performance data only — the tool never sees the actual ad |
| **CLI-only** | Requires Python environment. Not accessible to planners, strategists, or clients |
| **Two platforms** | Meta and TikTok only. No YouTube, Snapchat, Pinterest, DV360 |
| **No persistence** | No database. Every run starts from scratch. No benchmark library |

---

## What 200-300k Unlocks

Three tiers of investment, each building on the last. The recommendation is **Tier 2** as the sweet spot for impact vs risk.

---

### Tier 1: Production Platform (est. ~100-120k)

*Turn the POC into a self-service tool the whole team can use, every day, without touching a terminal.*

| Component | What It Does |
|-----------|-------------|
| **Web application** | Next.js dashboard replacing the Excel output. Real-time filtering, interactive charts, shareable URLs. Dark-mode analytics UI. |
| **Automated data ingestion** | Direct API connections to Meta Marketing API and TikTok Ads API. Scheduled daily pulls — no more manual exports. |
| **Database backend** | PostgreSQL for historical storage. Every scoring run is persisted. Trend lines over time. Campaign-over-campaign comparison. |
| **Multi-campaign support** | Run scoring across all active campaigns simultaneously. Cross-campaign creative leaderboard. |
| **Team access** | Role-based login. Planners see dashboards. Strategists see insights. Leads see everything. |
| **Automated reporting** | Scheduled PDF/email reports. Weekly creative performance digests sent to stakeholders. |

**Timeline:** 10-12 weeks | **Team:** 1 senior full-stack engineer, 1 designer (part-time), PM oversight

---

### Tier 2: Creative Intelligence Layer (est. ~180-220k)

*Everything in Tier 1 plus AI-powered analysis of the creative assets themselves — not just their performance numbers.*

| Component | What It Does |
|-----------|-------------|
| **Computer vision analysis** | Analyse actual ad images and video thumbnails: text overlay density, colour composition, face presence, brand logo placement, visual complexity score |
| **LLM-generated insights** | Replace template explanations with contextual, nuanced analysis. "This creator-led TikTok outperformed because the hook is a direct-to-camera question — a pattern that consistently drives 2s VTR on this platform." |
| **Creative pattern detection** | Identify which visual/structural patterns correlate with high scores across the portfolio. Surface "winning formulas" automatically. |
| **Fatigue prediction** | Model frequency decay curves per creative to predict when performance will drop — before it happens. |
| **A/B test recommendations** | Based on dimensional analysis (OS, placement, format, audience), automatically suggest which variables to test next. |
| **Benchmark library** | Persistent library of scored creatives across campaigns. "This creative scores in the 85th percentile vs all Pixel awareness creatives in the last 6 months." |
| **Extended platforms** | Add YouTube and Snapchat. Architecture designed for plug-in platform adapters. |

**Timeline:** 16-20 weeks (including Tier 1) | **Team:** 1 senior full-stack engineer, 1 ML/AI engineer (part-time), 1 designer (part-time), PM oversight

---

### Tier 3: Client-Facing Product (est. ~280-300k)

*Everything in Tiers 1 & 2 plus a white-labelled client portal and multi-client architecture.*

| Component | What It Does |
|-----------|-------------|
| **Client portal** | White-labelled, brand-customised dashboards accessible to client marketing teams directly. No more waiting for agency reports. |
| **Multi-client architecture** | Single platform serving multiple brands with data isolation. Reusable across the EssenceMediacom portfolio. |
| **Pre-flight scoring** | Upload a creative concept before launch and get a predicted performance score based on pattern matching against the benchmark library. |
| **Competitive creative signals** | Where available (Meta Ad Library, TikTok Creative Center), pull competitor creative data for contextual benchmarking. |
| **Exportable insights** | One-click generation of client-ready creative performance decks (Google Slides format). |
| **API for downstream tools** | REST API so creative scores can feed into bidding tools, media plans, or other agency systems. |

**Timeline:** 24-28 weeks (including Tiers 1 & 2) | **Team:** 2 engineers, 1 ML/AI engineer (part-time), 1 designer, PM oversight

---

## Current State vs Funded: Side by Side

| Dimension | Today (POC) | Tier 1 (Platform) | Tier 2 (Intelligence) | Tier 3 (Product) |
|-----------|------------|-------------------|----------------------|------------------|
| **Data input** | Manual Excel export | Automated API ingestion | Automated + asset analysis | Automated + competitive signals |
| **Scoring** | Performance metrics only | Same + historical benchmarks | + Visual/structural analysis | + Pre-flight prediction |
| **Insights** | Template explanations | Same + trending | LLM-generated, pattern-based | + Competitive context |
| **Platforms** | Meta, TikTok | Meta, TikTok | + YouTube, Snapchat | + Plug-in architecture for any platform |
| **Interface** | CLI + Excel | Web dashboard | Web dashboard + AI insights panel | + Client portal |
| **Users** | 1-2 analysts | Whole team (10-15) | Team + strategists (20-30) | + Client stakeholders (50+) |
| **Campaigns** | One at a time | All active campaigns | + Historical benchmarking | + Cross-client patterns |
| **Reporting** | Manual | Automated weekly | Automated + ad-hoc AI briefings | + Client-ready decks |
| **Time to insight** | Hours (export + run + review) | **Minutes** (open dashboard) | **Seconds** (proactive alerts) | **Zero** (always-on, client-accessible) |
| **Marginal cost per campaign** | ~2-3 hours analyst time | ~0 (automated) | ~0 (automated) | ~0 (automated) |

---

## The Opportunity

**What problem this solves:** Creative performance analysis is currently manual, retrospective, and siloed by campaign. The team exports data, runs a script, reviews an Excel file, then translates findings into recommendations. This cycle takes hours per campaign and the insights arrive too late to act on.

**Why this matters commercially:**
- **Creative is the #1 lever in social advertising.** Platform algorithms optimise delivery, but the creative determines whether people watch, engage, and convert. A **10% improvement in creative hit rate** across the Pixel portfolio could translate to **hundreds of thousands in media efficiency gains** — budget that performs harder without spending more.
- **Speed to insight = speed to optimisation.** A creative that's underperforming burns budget every hour it runs undetected. Automated daily scoring catches underperformers on day 1, not week 3.
- **Scalability beyond Pixel.** The methodology is brand-agnostic. Every social campaign at EssenceMediacom could benefit from the same scoring framework. The investment in one client creates a **reusable capability** across the portfolio.

**Why now:**
- The POC is **proven and in production** — the client already loves it and is offering budget
- AI capabilities (vision models, LLMs) have reached the quality/cost threshold where creative asset analysis is practical at scale
- Platform APIs are mature enough for reliable automated ingestion
- Competitor agencies are investing in similar capabilities — this is a **window to lead, not follow**

---

## Expected Outcomes

| Phase | Success Criteria | Measurable Target |
|-------|-----------------|-------------------|
| **Tier 1 (Month 3)** | Self-service dashboard live, daily automated scoring | **0 manual hours** per campaign cycle. Team adoption >80% |
| **Tier 2 (Month 5)** | AI insights generating actionable creative recommendations | **>70% of AI-generated recommendations** rated useful by planners. Creative hit rate improvement measurable vs control |
| **Tier 3 (Month 7)** | Client portal live, first external users onboarded | Client NPS improvement. **Reduction in reporting turnaround** from days to real-time |

---

## Investment Breakdown

| Item | Tier 1 | Tier 2 | Tier 3 |
|------|--------|--------|--------|
| Engineering (build) | 70-80k | 120-140k | 180-200k |
| Design (UI/UX) | 10-15k | 15-20k | 25-30k |
| Infrastructure (hosting, APIs, AI) | 5-10k/yr | 15-25k/yr | 25-35k/yr |
| PM / oversight | 10-15k | 15-20k | 20-25k |
| **Total (build)** | **~100-120k** | **~180-220k** | **~280-300k** |
| **Ongoing annual** | **~10-15k** | **~20-30k** | **~30-40k** |

Infrastructure costs include: cloud hosting, database, API usage (Meta/TikTok rate limits are free), AI model inference (vision + LLM), and monitoring.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Platform API rate limits or policy changes | Medium | High | Build with abstraction layer. Cache aggressively. Maintain Excel fallback. |
| AI insight quality insufficient for client-facing use | Medium | Medium | Human-in-the-loop review for Tier 3. Tier 2 is internal-only. Iterate on prompts with real data. |
| Scope creep across tiers | High | Medium | Hard phase gates. Tier 1 must be live before Tier 2 starts. Each tier delivers standalone value. |
| Team capacity / competing priorities | Medium | High | Dedicated engineer, not fractional across projects. Clear sprint commitments. |
| Client expectations outpace delivery | Low | High | Tier 1 is a visible, tangible upgrade. Ship early, iterate. Manage expectations with phased roadmap. |
| Data quality issues from platform APIs | Medium | Medium | Validation layer that flags anomalies. Reconcile API data against platform UI exports during Tier 1. |

---

## Recommendation

**Invest in Tier 2 (~200k).** It delivers the highest-impact capabilities — automated ingestion, web dashboard, AND AI-powered creative intelligence — while staying within the client's stated budget range. Tier 1 alone is a productivity tool; Tier 2 is a genuine competitive advantage.

### Immediate Next Steps

1. **Confirm scope and budget** with the client (this document as the basis)
2. **Lock engineering resource** — 1 senior full-stack + 1 ML/AI engineer (part-time)
3. **Kick off Tier 1 sprint** — target dashboard MVP in 6 weeks, full Tier 1 in 10-12 weeks
4. **Begin Tier 2 in parallel from week 8** — AI model prototyping while Tier 1 stabilises

---

*Built on a proven POC. Backed by a client ready to fund. Designed to scale beyond one brand.*
