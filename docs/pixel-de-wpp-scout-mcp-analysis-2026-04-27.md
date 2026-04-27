# Pixel DE Creative Performance Analysis

Prepared with WPP Scout MCP tools on 2026-04-27.

Source file: `/Users/malik.james-williams/Desktop/(WIP) Pixel DE - Creatives Social Review & Analysis (2).xlsx`

## Executive Summary

The dataset contains 3,204 placement-level rows, rolled up into 529 scored creative rows across Meta and TikTok. Total scored media spend is EUR 5.01m, with Meta carrying most of the scale at EUR 3.97m and TikTok carrying EUR 1.04m.

TikTok is slightly stronger on average score and materially stronger on video attention. TikTok averages a 51.1 creative score and 14.9% VTR, versus Meta at 50.1 and 8.6% VTR. The gap is not huge, but it is directionally consistent: TikTok is better at generating attention, while Meta is carrying the larger media footprint.

Creator-led work is outperforming brand-led work. The MCP dimension analysis shows Creator assets ahead of Brand assets on average score, with stronger VTR and comparable CTR. The strongest scale candidates are mostly creator-style or creator-coded: `uyenninh`, `gesinadem`, `kickiyangz`, `Pigeon Eco`, `irinahp`, `Linda - Camera Coach`, and BLS creator variants.

The biggest optimization opportunity is not finding more winners; it is reducing spend leakage from high-spend, low-score placements. The clearest reallocation candidates are Meta static Feed assets and several high-frequency TikTok TopView/Top Feed placements. The largest immediate review pool includes `Lifestyle Going Out Out`, `Lifestyle On My Way`, `DOOH Product`, `DOOH Product Dark`, `des.qua`, `Studio Schmaus Finding Warmth in Winter`, `Comfort/Fit`, and `Phillip&Fabian`.

Concept-level and placement-level views tell different stories. Some ideas are strong in specific placements but weak as full concepts because spend is diluted into weaker placements. For example, `gesinadem` has the single best TikTok placement-level creative at 87.9, but the concept rolls down to 40.3 when weaker TopView, Top Feed, Reels, Stories, and lower-performing reach rows are included. `X Mas Asset 1` is similar: the Feed placement is excellent at 83.1, while Stories is weak at 46.2.

## How To Read The Scores

WPP Scout scores creatives from 0 to 100 using objective-specific KPIs. For video objectives, the score emphasizes hook/VTR, completion versus expected duration, cost efficiency, and attention proxy inputs. For static assets, the score shifts away from VTR and completion and uses engagement rate, CTR, share rate, and CPM-style efficiency.

Scores are cohort-relative. Paid and Boosting rows are scored separately, and objectives/platforms/formats are scored against their own peer groups. Use the score to rank within comparable buying and objective contexts, then use spend, reach, frequency, and business judgment to decide action.

Placement-level means a specific creative execution in a platform, objective, format, and placement context. Concept-level rolls up the underlying idea across multiple rows, placements, objectives, and sometimes platforms. Placement-level tells us where an idea works. Concept-level tells us whether the overall idea is scalable or being dragged down by weak delivery contexts.

## Data Quality

| Metric | Value |
|---|---:|
| Raw rows analyzed | 3,204 |
| Scored creative rows | 529 |
| Platforms | Meta, TikTok |
| Total scored spend | EUR 5,008,914.99 |
| Low-confidence creative rows | 98 |
| Missing required columns | 0 |
| Mostly zero metric columns | 0 |

There are 98 low-confidence creative rows, mainly where spend or reach is too low for a reliable decision. These should be treated as learning candidates, not final winners or losers. The underlying workbook loaded cleanly with no missing required fields.

## Channel Readout

| Platform | Creative Rows | Spend | Reach | Impressions | Avg Score | Avg VTR | Avg CTR | Low Confidence |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Meta | 436 | EUR 3,965,990 | 331.6m | 701.3m | 50.1 | 8.6% | 0.53% | 96 |
| TikTok | 93 | EUR 1,042,925 | 106.8m | 229.6m | 51.1 | 14.9% | 0.18% | 2 |

Meta is the main scale channel and contains most of the low-confidence rows because it also has the broadest long-tail of smaller placements. TikTok has fewer creative rows, higher average VTR, and fewer low-confidence issues.

## Objective And Format Patterns

| Objective | Creative Rows | Spend | Avg Score | Readout |
|---|---:|---:|---:|---|
| Target Frequency | 8 | EUR 58.8k | 54.4 | Strongest named objective, but low volume. |
| Reach | 51 | EUR 571.0k | 51.3 | Slightly above average, with TikTok Top Feed/Top Feed Takeover showing some promise but TopView needing caution. |
| Engagement | 102 | EUR 800.8k | 51.0 | Creator-led video and Reels can work, but there is high variance. |
| Awareness | 166 | EUR 2.65m | 49.9 | Large spend pool, mixed efficiency. Several high-spend static assets are weak. |
| Traffic | 150 | EUR 291.3k | 49.7 | Many low-confidence rows. Use directional learnings, not hard calls, for the smaller rows. |
| Video Views | 23 | EUR 160.8k | 49.4 | TikTok attention can be high, but frequency and completion quality separate winners from reach-heavy placements. |
| Sales | 24 | EUR 467.3k | 48.3 | Weakest named objective overall. Motion performs better than static for Sales in this data. |

Format by objective is clear enough to act on:

| Objective | Best Format Signal | Avg Score |
|---|---|---:|
| Awareness | Motion | 58.7 |
| Sales | Motion | 64.3 |
| Traffic | Motion | 58.8 |
| Target Frequency | Video | 54.4 |
| Reach | Unknown / Video | 54.4 / 50.7 |
| Engagement | Video, excluding unknown-format noise | 50.7 |

The practical takeaway is to keep motion in the plan where the objective is Awareness, Traffic, or Sales, but avoid assuming all motion is good. Placement still matters.

## Placement Patterns

| Platform | Placement | Spend | Avg Score | Avg VTR | Avg CTR | Readout |
|---|---|---:|---:|---:|---:|---|
| Meta | Feed | EUR 1.82m | 52.7 | 6.7% | 0.42% | Best Meta placement by score. Strong for `X Mas Asset 1`, `uyenninh`, BLS creator variants. |
| Meta | Reels | EUR 783.5k | 50.2 | 17.3% | 0.15% | Good attention, but inconsistent conversion into score. Strong for `Pigeon Eco`, weaker for some high-spend creator lines. |
| Meta | Stories | EUR 1.06m | 46.0 | 4.0% | 0.78% | High CTR but weakest Meta score. Many fatigue or weak completion issues. |
| TikTok | Top Feed Takeover | EUR 64.7k | 54.5 | 19.5% | 0.16% | Small sample, promising. |
| TikTok | Top Feed | EUR 169.5k | 53.8 | 13.3% | 0.15% | Above TikTok average, but still concept-dependent. |
| TikTok | In Feed | EUR 569.1k | 50.9 | 13.3% | 0.09% | Main scalable TikTok placement. Contains the strongest winners. |
| TikTok | TopView | EUR 239.7k | 40.0 | 47.3% | 1.84% | High attention but weak score due fatigue and cost/efficiency context. Needs sharper control. |

TopView is the clearest example of why attention alone is insufficient. It can generate very high VTR and CTR, but the MCP scoring flags frequency and efficiency risk in several rows.

## Top Placement-Level Creatives

### Meta

| Rank | Creative | Score | Spend | Action | Why It Wins |
|---:|---|---:|---:|---|---|
| 1 | P10 Phase 4 2025-Google Pixel-uyenninh-Stories-23" | 83.8 | EUR 15,941 | Scale Up | Strong traffic row, 15.0% 3s VTR, 5.38% completion, 3.02% engagement, moderate frequency. |
| 2 | P10 Phase 4 2025-Google Pixel-uyenninh-Feed-23" | 83.1 | EUR 1,514 | Scale Up | Strong awareness row, 13.4% 3s VTR, high attention proxy, low frequency. |
| 3 | P10 Phase 4 2025-Google Pixel-X Mas Asset 1-Feed-motion | 83.1 | EUR 40,239 | Scale Up | Best scaled Meta winner, strong attention proxy, 12.2% 3s VTR, efficient complete views. |
| 4 | Euro Phase 3 2025-Google Pixel-Pigeon Eco-Reels-15" | 82.5 | EUR 5,364 | Scale Up | 24.6% 3s VTR, good completion, low frequency, broad variant base. |
| 5 | Euro Phase 3 2025-Google Pixel-Wave 1 BLS Gemini Ice Breaker-Feed-15-30" | 81.8 | EUR 2,388 | Scale Up | Strong awareness feed performer, low frequency, good enough attention to scale as a template. |

Meta's best rows are disproportionately Feed and creator-coded video, with one high-scale brand/motion exception in `X Mas Asset 1`.

### TikTok

| Rank | Creative | Score | Spend | Action | Why It Wins |
|---:|---|---:|---:|---|---|
| 1 | P10 Phase 4 2025-Google Pixel-gesinadem-In Feed-28" | 87.9 | EUR 3,240 | Scale Up | Highest placement score in the dataset, strong attention proxy and efficient reach. |
| 2 | P10 Phase 4 2025-Google Pixel-Tease Change Your Phone-In Feed-15" | 81.6 | EUR 7,421 | Scale Up | Strong Target Frequency row, 17.8% VTR, efficient complete views, low frequency. |
| 3 | P10 Phase 4 2025-Google Pixel-Deep Thoughts Blazer-In Feed-6" | 80.0 | EUR 7,336 | Scale Up | Short-form brand asset with strong completion economics. |
| 4 | P10 Phase 4 2025-Google Pixel-Gia BTS 1-In Feed-15" | 78.1 | EUR 13,674 | Scale Up | Creator-led, 23.0% VTR, strong paid scale signal. |
| 5 | P10 Phase 4 2025-Google Pixel-kickiyangz-In Feed-18" | 77.0 | EUR 9,113 | Scale Up | Best TikTok concept-level winner, solid attention and low frequency. |

TikTok's clearest scalable placement is In Feed. The best TikTok winners are not necessarily the highest-spend placements; they are the rows where attention, frequency, and cost efficiency align.

## Concept-Level Winners

### Strongest Concepts Overall

| Concept | Score | Spend | Rows | Platforms | Readout |
|---|---:|---:|---:|---|---|
| Google Pixel Liga / Pixel Cam Teaser | 81.6 | EUR 960 | 1 | Meta | Strong but low-scale. Validate before making it a major scale pillar. |
| Sabrina - Pixel Residency | 80.3 | EUR 2,976 | 1 | Meta | Strong creator engagement signal in Reels. |
| Rausgegangen - Tiktok Video Post | 74.3 | EUR 1,000 | 1 | TikTok | Strong engagement signal, but currently low-scale. |
| Gia Coppola Feedpost 1 - Reels | 74.0 | EUR 894 | 1 | Meta | Strong reach row, low-scale. |
| Linda - Camera Coach | 73.6 | EUR 3,980 | 2 | Meta, TikTok | Strong cross-platform concept, good candidate for expansion. |
| X Mas Asset 1 | 72.3 | EUR 60,816 | 3 | Meta | Strong enough to scale, but placement management is critical. |

Some top concepts are high-scoring but low-spend. They are good creative learning candidates, not necessarily immediate high-budget reallocations. `X Mas Asset 1`, `uyenninh`, and `Tease Change Your Phone` are more useful for budget planning because they have meaningful spend behind them.

### Top Meta Concepts

| Concept | Score | Spend | Rows | Best/Worst Row | Recommendation |
|---|---:|---:|---:|---:|---|
| Google Pixel Liga / Pixel Cam Teaser | 81.6 | EUR 960 | 1 | 81.6 / 81.6 | Validate with more spend. |
| Sabrina - Pixel Residency | 80.3 | EUR 2,976 | 1 | 80.3 / 80.3 | Scale carefully in similar Reels contexts. |
| uyenninh | 77.8 | EUR 87,199 | 4 | 83.8 / 76.2 | Strong Meta concept. Scale Feed, Stories Traffic, and Reels. |
| Gia Coppola Feedpost 1 - Reels | 74.0 | EUR 894 | 1 | 74.0 / 74.0 | Validate further. |
| Linda - Camera Coach | 73.2 | EUR 2,981 | 1 | 73.2 / 73.2 | Good creator learning; extend variants. |
| X Mas Asset 1 | 72.3 | EUR 60,816 | 3 | 83.1 / 46.2 | Scale Feed, reduce Stories. |

### Top TikTok Concepts

| Concept | Score | Spend | Rows | Best/Worst Row | Recommendation |
|---|---:|---:|---:|---:|---|
| kickiyangz | 77.0 | EUR 9,113 | 1 | 77.0 / 77.0 | Scale In Feed. |
| Linda - Camera Coach | 74.9 | EUR 999 | 1 | 74.9 / 74.9 | Validate with more spend. |
| Rausgegangen - Tiktok Video Post | 74.3 | EUR 1,000 | 1 | 74.3 / 74.3 | Validate and extend. |
| Nowness TikTok Video Post Masterclass Stini | 71.1 | EUR 1,000 | 1 | 71.1 / 71.1 | Keep as learning candidate. |
| Unboxing P10 | 71.0 | EUR 1,000 | 1 | 71.0 / 71.0 | Keep as learning candidate. |
| Tease Change Your Phone | 70.2 | EUR 126,281 | 4 | 81.6 / 65.5 | Scale In Feed, watch TopView frequency. |

## Concept Versus Placement Examples

### uyenninh

`uyenninh` is one of the strongest Meta concepts but more mixed when all platforms and placements are included.

At Meta-only concept level it scores 77.8 across four rows, with all rows marked Scale Up. At full cross-platform concept level it scores 62.6 across nine rows because TikTok In Feed, Top Feed Takeover, and Reach rows are weaker.

The right action is not "scale everything." Scale Meta Stories Traffic, Meta Feed Awareness, Meta Feed Traffic, and Meta Reels Engagement. Keep or optimize TikTok In Feed, but reduce or review TikTok Top Feed Takeover and TikTok Reach rows where scores fall into the low 40s.

### gesinadem

`gesinadem` has the highest individual placement-level result: TikTok In Feed Awareness at 87.9. However, the full concept rolls down to 40.3 across 10 rows because TopView, Top Feed, Reels, Stories, and several Reach rows are much weaker.

This is a textbook case for placement-level decisioning. Do not kill the idea. Isolate the winning TikTok In Feed and Meta Feed/Stories executions, while cutting back the weak TopView and Reels placements.

### X Mas Asset 1

`X Mas Asset 1` is a strong concept overall at 72.3, but the placement split matters:

| Placement | Score | Spend | Readout |
|---|---:|---:|---|
| Feed | 83.1 | EUR 40,250 | Clear scale area. |
| Collection / Unknown | 54.8 | EUR 12,244 | Keep running, but not a scale priority. |
| Stories | 46.2 | EUR 8,367 | Review or reduce. |

The concept is good. The Stories placement is the drag.

### Tease Change Your Phone

`Tease Change Your Phone` is strong in TikTok In Feed and weaker elsewhere.

| Placement | Score | Spend | Readout |
|---|---:|---:|---|
| TikTok In Feed | 78.4 | EUR 30,014 | Scale. |
| Meta Feed | 75.4 | EUR 3,435 | Strong but smaller. |
| TikTok TopView | 68.7 | EUR 64,258 | Attention is high, but frequency is 3.9x. Optimize rather than blindly scale. |
| Meta Reels | 44.6 | EUR 24,298 | Reduce or refresh. |
| Meta Stories | 34.5 | EUR 2,965 | Review or stop. |

This concept should remain in plan, but budget should favor In Feed and Feed rather than TopView, Reels, or Stories.

## Underperforming Concepts To Review

| Concept | Score | Spend | Why It Matters |
|---|---:|---:|---|
| Phillip&Fabian | 32.8 | EUR 123,422 | Large spend, weak average, poor Stories performance. |
| Comfort/Fit | 27.9 | EUR 90,262 | High frequency, weak Stories and static performance. |
| Comfort/Fit02 | 30.4 | EUR 66,511 | Static Feed and Collection drag the concept. |
| Studio Schmaus Finding Warmth in Winter | 24.6 | EUR 59,322 | High spend, poor score, pause recommendation. |
| Winter Table | 33.9 | EUR 55,300 | Below average despite meaningful spend. |
| Suitecase | 27.5 | EUR 38,448 | Mixed rows, with Feed static/Sales dragging down the concept. |

These are the strongest candidates for budget review because they combine low scores with meaningful spend. The recommendation is to pause, refresh, or sharply reduce rather than keep optimizing around the same executions.

## Budget Reallocation

### Scale Toward

| Creative / Concept | Platform | Placement | Score | Spend | Action |
|---|---|---|---:|---:|---|
| gesinadem | TikTok | In Feed | 87.9 | EUR 3,240 | Scale Up |
| uyenninh | Meta | Stories | 83.8 | EUR 15,941 | Scale Up |
| X Mas Asset 1 | Meta | Feed | 83.1 | EUR 40,239 | Scale Up |
| uyenninh | Meta | Feed | 83.1 | EUR 1,514 | Scale Up |
| Pigeon Eco | Meta | Reels | 82.5 | EUR 5,364 | Scale Up |
| Tease Change Your Phone | TikTok | In Feed | 81.6 | EUR 7,421 | Scale Up |
| irinahp | Meta | Feed | 81.4 | EUR 3,288 | Scale Up |
| Wave 2 BLS Kick It | Meta | Feed | 80.9 | EUR 9,170 | Scale Up |

### Scale Away From

| Creative / Concept | Platform | Placement | Score | Spend | Action |
|---|---|---|---:|---:|---|
| Lifestyle Going Out Out | Meta | Feed static | 37.3 | EUR 113,449 | Consider pausing |
| Lifestyle On My Way | Meta | Feed static | 43.9 | EUR 112,139 | Consider pausing |
| DOOH Product | Meta | Feed static | 25.8 | EUR 80,779 | Consider pausing |
| des.qua | Meta | Reels | 49.4 | EUR 72,024 | Consider pausing |
| DOOH Product Dark | Meta | Collection static | 47.5 | EUR 71,613 | Consider pausing |
| des.qua | TikTok | TopView | 30.1 | EUR 61,598 | Fatigue risk |
| UK Video | Meta | Reels | 31.3 | EUR 59,617 | Fatigue risk |
| Studio Schmaus Finding Warmth in Winter | Meta | Reels | 24.6 | EUR 59,322 | Pause |
| Veo 3 Dog | TikTok | TopView | 33.1 | EUR 57,082 | Consider pausing |
| gesinadem | TikTok | TopView | 28.3 | EUR 56,761 | Fatigue risk |

Practical action: move the first tranche of flexible budget out of high-spend, low-score rows into proven Feed/In Feed/Reels winners. Do this in controlled increments rather than a single hard shift, because some current winners are lower-spend and need validation at scale.

## Fatigue And Refresh Risks

The clearest fatigue risks are high-frequency rows with weak or weakening scores:

| Creative / Concept | Platform | Placement | Score | Spend | Frequency | Recommendation |
|---|---|---|---:|---:|---:|---|
| Winter Picnic V2 | Meta | Stories | 39.6 | EUR 33,843 | 5.8x | Pause or replace. |
| Comfort/Fit | Meta | Stories static | 19.2 | EUR 55,319 | 5.1x | Pause. |
| Helpfulness | Meta | Stories | 10.1 | EUR 32,846 | 4.9x | Pause. |
| Fitness/Health | Meta | Feed | 31.2 | EUR 54,343 | 4.8x | Refresh or reduce. |
| Gia Cut Down 2 | TikTok | In Feed | 48.8 | EUR 16,551 | 4.2x | Refresh. |
| Tease Change Your Phone | TikTok | TopView | 68.7 | EUR 64,258 | 3.9x | Keep concept, optimize placement. |
| uyenninh | TikTok | In Feed | 52.3 | EUR 24,500 | 4.0x | Keep concept, rotate variants. |

Fatigue is concentrated in Meta Stories/static and TikTok high-reach placements. Refreshing the same concepts in better placements is preferable to retiring every concept outright.

## Client Recommendations

1. Rebalance spend from weak static Meta Feed rows into proven video/motion Feed and TikTok In Feed rows.

2. Treat TikTok TopView as a reach tool, not a default scale tool. It can deliver attention, but this dataset shows frequent score drag from frequency and efficiency.

3. Scale `uyenninh` on Meta but manage it by placement. The Meta Feed, Stories Traffic, and Reels rows are strong; the full cross-platform concept is diluted by weaker TikTok reach placements.

4. Scale `gesinadem` only where it works. TikTok In Feed Awareness is the best row in the dataset, but TopView and some Meta/TikTok reach placements drag the concept down.

5. Keep `X Mas Asset 1` in plan, but redirect emphasis to Feed. Stories should be reduced or rebuilt.

6. Refresh or reduce `Comfort/Fit`, `Phillip&Fabian`, `Studio Schmaus Finding Warmth in Winter`, and static `Lifestyle`/`DOOH Product` assets. These are the biggest spend leakage areas.

7. Use Creator-led patterns as the next creative brief input. Creator work wins on average and appears repeatedly in the best rows across Meta and TikTok.

8. Split future reporting into concept and placement views. The client should see both: concept-level for creative idea health and placement-level for activation decisions.

## Next Test Plan

Build the next round around three buckets:

| Bucket | What To Do | Examples |
|---|---|---|
| Scale | Increase controlled spend into proven placements. | `uyenninh` Meta Feed/Stories/Reels, `X Mas Asset 1` Meta Feed, `gesinadem` TikTok In Feed, `Tease Change Your Phone` TikTok In Feed. |
| Refresh | Keep concept but change execution or placement. | `Tease Change Your Phone` TopView, `uyenninh` TikTok In Feed, high-frequency Stories variants. |
| Cut / Replace | Pause or materially reduce low-score high-spend rows. | `Lifestyle Going Out Out`, `Lifestyle On My Way`, `DOOH Product`, `Comfort/Fit`, `Phillip&Fabian`, `Studio Schmaus`. |

## MCP Tools Used

This analysis was generated from the WPP Scout MCP tool outputs, including `ingest_data`, `get_data_quality_report`, `get_top_performers`, `get_bottom_performers`, `get_top_concepts`, `get_bottom_concepts`, `get_concept_deep_dive`, `get_score_breakdown`, `summarize_campaign_trends`, `get_action_plan`, `compare_dimensions`, `get_objective_format_matrix`, `search_by_objective`, `get_fatigue_risks`, `get_low_confidence_creatives`, `get_budget_reallocation_recommendations`, and `find_actionable_insights`.
