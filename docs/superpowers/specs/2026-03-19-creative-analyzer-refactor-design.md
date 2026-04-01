# Creative Performance Analyzer — Refactor Design Spec

> **Generated:** 2026-03-19
> **Status:** Draft for PM Review
> **Scope:** Dashboard refactor, scoring changes, Wooshii removal, native attention proxy

---

## Executive Summary

This refactor transforms the Creative Performance Analyzer workbook from a static report into an interactive dashboard tool. Key changes:

1. **Remove Wooshii** — Replace with a "Native Attention Proxy" built from platform metrics
2. **Add canonical metric layer** — Normalize Meta and TikTok metrics for safe cross-platform comparison
3. **Build interactive dashboard** — Front sheet with filters for Campaign/Platform/Format, dimension controls, and dynamic tables
4. **Improve data robustness** — Better standardization of campaign names, platforms, formats, placements, OS, objectives, and asset types
5. **Transparent scoring** — Explicit component model with renormalization when inputs are missing

---

## 1. Scoring Changes

### 1.1 Remove Wooshii Component

**Current state:**
- 10% of score weight allocated to brand measurement (Wooshii brand_score, core_message_score)
- When Wooshii data is absent, defaults to neutral 50 points

**New state:**
- Remove all Wooshii references from scoring logic
- Remove Wooshii columns from output column lists
- Remove Wooshii explanations from explainer.py
- Rename any "Brand Measurement" labels to avoid confusion

### 1.2 Native Attention Proxy (Replaces Wooshii)

**Purpose:** Use available native platform metrics as a proxy for attention/engagement quality.

**Meta attention inputs:**
- 3s VTR (hook rate proxy)
- 50% VTR (hold rate proxy)
- Completion rate
- Hook rate (if available in data)
- Hold rate (if available in data)

**TikTok attention inputs:**
- 2s VTR (hook rate proxy)
- 25% VTR (hold rate proxy)
- Completion rate
- Hook rate (if available in data)
- Hold rate (if available in data)

**Attention Proxy Score Calculation:**
```python
def compute_attention_proxy_score(row) -> tuple[float, bool]:
    """
    Returns (score, was_renormalized).

    If all attention inputs are available:
      - Average percentile rank across available metrics
      - Weight: 10% of final score

    If some inputs missing:
      - Use available metrics only
      - Renormalize the score components so missing attention doesn't penalize

    If no attention inputs available:
      - Return neutral 50, flag for renormalization
    """
```

**Renormalization Logic:**
When attention proxy cannot be computed (no inputs available), redistribute the 10% weight proportionally:
- Primary: 50% → 55.6% (50/90)
- Secondary: 25% → 27.8% (25/90)
- Cost Efficiency: 15% → 16.7% (15/90)

**Output:**
- New column: `attention_proxy_score` (0-100)
- New column: `attention_inputs_available` (bool)
- New column: `score_renormalized` (bool)

### 1.3 Updated Weight Distribution

| Component | Weight (Full) | Weight (Renormalized) |
|-----------|---------------|----------------------|
| Primary KPI | 50% | 55.6% |
| Secondary KPIs | 25% | 27.8% |
| Cost Efficiency | 15% | 16.7% |
| Native Attention Proxy | 10% | 0% (n/a) |

### 1.4 Explicit Score Component Model

Each row will have these component columns:

```
primary_kpi_score          # 0-100, percentile within objective+platform+buying_type
secondary_kpi_score        # 0-100, average of secondary metrics
cost_efficiency_score      # 0-100, cost per outcome vs peers
attention_proxy_score      # 0-100, native attention metrics (or 50 neutral)
attention_proxy_weight     # 0.10 or 0.0 if renormalized
applied_weight_total       # 1.0 (full) or 0.9 (renormalized)
final_creative_score       # 0-100, weighted composite
```

---

## 2. Canonical Metric Layer

### 2.1 Purpose

Platform metrics are not directly comparable:
- TikTok reports 2s VTR; Meta reports 3s VTR
- Hook rate and hold rate definitions differ
- Completion rate baselines vary by platform

The canonical layer normalizes these into comparable metrics while preserving raw platform values.

### 2.2 Canonical Metric Definitions

| Canonical Field | Meta Source | TikTok Source | Notes |
|-----------------|-------------|---------------|-------|
| `canonical_hook_rate` | 3s VTR / Impressions | 2s VTR / Impressions | Early attention |
| `canonical_hold_rate` | 50% VTR / 3s VTR | 25% VTR / 2s VTR | Mid-roll retention |
| `canonical_completion_rate` | video_views_100 / Impressions | video_views_100 / Impressions | Full watch |
| `canonical_engagement_rate` | engagements / Impressions | engagements / Impressions | Direct engagement |
| `canonical_ctr` | clicks / Impressions | clicks / Impressions | Click behavior |
| `canonical_cost_efficiency` | CPM or CPC | CPM or CPC | Cost efficiency |
| `canonical_primary_kpi_value` | Objective-dependent | Objective-dependent | Primary metric value |
| `canonical_secondary_kpi_values` | Objective-dependent | Objective-dependent | Secondary metric values |
| `attention_proxy_score` | Composite of above | Composite of above | Attention quality |

### 2.3 Implementation Location

Add to `src/loader.py`:

```python
def compute_canonical_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add canonical metric columns to dataframe.
    Platform-specific logic applied row-by-row based on 'platform' column.
    Preserves raw platform metrics in original columns.
    """
```

---

## 3. Objective Mapping Refinement

### 3.1 Current Objectives

- Video Views
- Brand Awareness
- Engagement
- Traffic
- Conversions

### 3.2 New/Refined Objectives

| Objective | Primary KPI | Secondary KPIs | Efficiency Metric |
|-----------|-------------|----------------|-------------------|
| **Awareness** | 3s VTR / early view quality | Reach efficiency, hook rate | CPM |
| **Engagement** | Engagement rate | Share rate, comments, saves | CPE (cost per engagement) |
| **Sales** | CPC / cost efficiency | CTR, conversion proxy | CPA (if available) or CPC |
| **Traffic** | CTR | Engagement rate, bounce proxy | CPC |
| **Reach** | Reach per € / reach efficiency | Frequency control, VTR | CPM |
| **Target Frequency** | Hold rate / attention retention | Completion rate, frequency | CPF (cost per frequency) |
| **Video Views** | Completion rate | VTR, share rate | CPCV (cost per completed view) |

### 3.3 Objective Normalization (loader.py)

Improve `normalize_objective()` to handle more variations:

```python
OBJECTIVE_MAPPINGS = {
    'awareness': ['brand awareness', 'awareness', 'reach', 'brand', 'aware'],
    'engagement': ['engagement', 'interaction', 'video engagement', 'post engagement'],
    'sales': ['conversion', 'conversions', 'purchase', 'lead', 'sales', 'catalogue sales'],
    'traffic': ['traffic', 'click', 'landing page', 'link click', 'clicks'],
    'reach': ['reach', 'unique reach', 'brand reach'],
    'target_frequency': ['frequency', 'target frequency', 'frequency capping'],
    'video_views': ['video view', 'focused view', 'thruplay', 'video views', 'vv'],
}
```

---

## 4. Data Standardization (loader.py)

### 4.1 Field Standardization Functions

```python
# Campaign names
def normalize_campaign_name(val) -> str:
    """
    - Strip whitespace
    - Remove "COPY" suffixes
    - Standardize "DE" / "UK" / "US" market codes
    - Remove duplicate spaces
    """

# Platform values
def normalize_platform(val) -> str:
    """
    Already exists, but add more variations:
    - FB, IG, FB/IG, FACEBOOK, INSTAGRAM, META → 'Meta'
    - TIKTOK, TT, TIK TOK → 'TikTok'
    """

# Format values
def normalize_format(val) -> str:
    """
    Standardize to: Video, Motion, Static, Carousel, Stories, Reels, In-Feed
    Handle variations like:
    - "Video 15s", "Video 30s" → "Video"
    - "Static Image", "Image" → "Static"
    - "In-Feed", "Feed" → "In-Feed"
    """

# Placement values
def normalize_placement(val) -> str:
    """
    Standardize placement names within platforms.
    Meta: Feed, Stories, Reels, Explore, Search
    TikTok: In-Feed, TopView, Spark Ads, Hashtag Challenge
    """

# Asset Type values
def normalize_asset_type(val) -> str:
    """
    Standardize to: Brand, Creator, Partner, BAU
    Handle: "BAU", "Brand", "N/A", "None" → "Brand"
            "Creator", "Influencer", "UGC" → "Creator"
            "Partner", "Hybrid", "Co-branded" → "Partner"
    """

# OS values
def normalize_os(val) -> str:
    """
    Standardize to: iOS, Android, All
    Handle: "iPhone", "iPad" → "iOS"
            "Android", "android" → "Android"
            "", "All", "Both" → "All"
    """

# Objective values (see section 3.3)
def normalize_objective(val) -> str:
    """Map platform objectives to canonical categories."""
```

### 4.2 Null/Missing Handling

- Replace empty strings with `None` or appropriate default
- Log warnings for unexpected column states
- Preserve raw values in `_raw` suffixed columns for debugging
- Never force zero for missing rate metrics — use NaN and handle downstream

---

## 5. Dashboard Requirements (Front Sheet)

### 5.1 Top Filter Bar

**Position:** Rows 1-4 of Dashboard sheet

**Controls:**

| Filter | Options | Implementation |
|--------|---------|----------------|
| **Campaign** | Dropdown list of unique campaigns + "All" | Data validation dropdown |
| **Platform** | All, Meta, TikTok | Data validation dropdown |
| **Format** | All, Video, Motion, Static | Data validation dropdown |

**Behavior:**
- Filters apply to all dashboard content below
- Summary stats update based on filtered data
- Tables re-render based on selected dimension

### 5.2 Secondary Configuration Controls

**Position:** Rows 5-8 of Dashboard sheet

| Control | Options | Implementation |
|---------|---------|----------------|
| **Top Range** | Top 5, Top 10, Top 50 | Data validation dropdown |
| **Dimension** | Asset Type, Placement, OS, Objective | Data validation dropdown |
| **KPI Columns** | Multi-select (checkbox-style simulation) | Data validation or explicit column visibility |

**Default KPI Columns:**
- Creative (always visible)
- Score (always visible)
- VTR
- Hook Rate
- Hold Rate
- Completion Rate
- ER (Engagement Rate)
- CTR
- CPC
- Reach
- Frequency
- Spend
- Impressions

### 5.3 Main Comparison Tables

**Position:** Rows 10+ of Dashboard sheet

**Dynamic rendering based on Dimension selection:**

**When Dimension = OS:**
```
┌─────────────────────────────────────────────┐
│ iOS — Top 5 Performers                      │
├─────┬────────────────────┬───────┬─────┬───┤
│ Rank│ Creative           │ Score │ VTR │...│
├─────┼────────────────────┼───────┼─────┼───┤
│  1  │ [Creative Name]    │  85.2 │12.5%│...│
│  2  │ [Creative Name]    │  82.1 │11.8%│...│
│ ... │ ...                │   ... │ ... │...│
└─────┴────────────────────┴───────┴─────┴───┘

┌─────────────────────────────────────────────┐
│ iOS — Bottom 5 Performers                   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Android — Top 5 Performers                  │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Android — Bottom 5 Performers               │
└─────────────────────────────────────────────┘
```

**When Dimension = Asset Type:**
```
┌─────────────────────────────────────────────┐
│ Brand — Top 5 Performers                    │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Creator — Top 5 Performers                  │
└─────────────────────────────────────────────┘
```

**When Dimension = Placement:**
- One table per placement value in filtered set
- Each table shows top/bottom performers for that placement

**When Dimension = Objective:**
- One table per objective value in filtered set
- Each table shows top/bottom performers for that objective

### 5.4 Lower Overview Section

**Position:** Below main tables, always visible

**Sections (filtered by top-level Campaign/Platform/Format):**

1. **iOS vs Android Performance Summary**
   - Avg Score, Avg VTR, Avg Completion, Total Spend per OS
   - VTR winner highlighted

2. **Brand vs Creator Performance Summary**
   - Avg Score, Avg VTR, Avg Completion, Total Spend per Asset Type
   - Per-platform breakdown if both platforms selected

3. **Audience Segment Performance** (if segment data exists)
   - Top-performing segment
   - Segment score distribution

4. **Objective × Format Matrix / Heatmap**
   - Grid showing avg score for each Objective × Format combination
   - Conditional formatting: green (70+), yellow (50-70), red (<50)

---

## 6. Workbook Tab Structure

### 6.1 New Tab Structure

| Tab | Purpose | Status |
|-----|---------|--------|
| **Dashboard** | Interactive front sheet with filters | Major refactor |
| **How Scoring Works** | Methodology explanation | Update for attention proxy |
| **Summary - Top Performers** | Overall top performers (filtered view) | Minor update |
| **Top by Asset Type** | Top performers per asset type | New |
| **Top by OS** | Top performers per OS | New |
| **Top by Placement** | Top performers per placement | New |
| **TikTok Paid Rankings** | Full TikTok Paid rankings | Existing |
| **Meta Paid Rankings** | Full Meta Paid rankings | Existing |
| **TikTok Boosting Rankings** | Full TikTok Boosting rankings | Existing |
| **Meta Boosting Rankings** | Full Meta Boosting rankings | Existing |
| **Splits Analysis** | Raw ad-line data with all dimensions | Existing |
| **OS Comparison** | iOS vs Android side-by-side | Existing |
| **Cross-Platform** | Creatives on both platforms | Existing |
| **Asset Types** | Brand vs Creator analysis | Existing |
| **Obj × Format Matrix** | Objective × Format heatmap | Existing |
| **Looker Export** | Flat data for Looker Studio | Update columns |
| **Raw Data** | All raw platform data | New (for debugging) |

### 6.2 Tab Design Principles

- **No per-campaign tabs** — Prevents workbook explosion
- **Reusable summary tabs** — One tab per breakdown dimension
- **Dashboard as entry point** — Most users should only need Dashboard
- **Detail tabs for power users** — Full data available when needed

---

## 7. Implementation Plan

### Phase 1: Scoring & Data Layer (Estimated: ~40% of effort)

**Files to modify:**
- `src/loader.py` — Add canonical metrics, improve standardization
- `src/scorer.py` — Remove Wooshii, add attention proxy, explicit components

**Tasks:**
1. Add `compute_canonical_metrics()` to loader.py
2. Add normalization functions for campaign, format, placement, OS, objective
3. Remove Wooshii from scorer.py scoring weights
4. Add `compute_attention_proxy_score()` function
5. Add renormalization logic when attention inputs missing
6. Add explicit component score columns
7. Update `OBJECTIVE_METRICS` mapping for new objectives

### Phase 2: Explainer Updates (Estimated: ~10% of effort)

**Files to modify:**
- `src/explainer.py`

**Tasks:**
1. Remove Wooshii references from explanations
2. Add attention proxy explanation when used
3. Add renormalization notice when applied
4. Add dimension-level pattern insights (e.g., "Creator wins on TikTok In-Feed for Android")

### Phase 3: Dashboard & Reporter (Estimated: ~40% of effort)

**Files to modify:**
- `src/reporter.py` — Major refactor

**Tasks:**
1. Create Dashboard sheet with filter controls
2. Implement data validation dropdowns
3. Build dynamic table rendering based on dimension
4. Create summary tabs (Top by Asset Type, Top by OS, Top by Placement)
5. Add Raw Data tab
6. Update column lists to remove Wooshii, add attention proxy columns
7. Update "How Scoring Works" methodology text
8. Add conditional formatting for score columns
9. Set Dashboard as first active sheet

### Phase 4: Testing & Polish (Estimated: ~10% of effort)

**Tasks:**
1. Test with sample data to verify scoring changes
2. Verify filters work correctly
3. Check all tabs render without errors
4. Validate attention proxy calculation
5. Confirm renormalization triggers correctly

---

## 8. Files Changed Summary

| File | Changes |
|------|---------|
| `src/loader.py` | Add canonical metrics, improve standardization functions |
| `src/scorer.py` | Remove Wooshii, add attention proxy, explicit component model |
| `src/explainer.py` | Update explanations for new scoring logic |
| `src/reporter.py` | Major refactor — new Dashboard, summary tabs, updated columns |
| `main.py` | No changes (CLI unchanged) |

---

## 9. Schema Changes

### New Columns Added

| Column | Type | Description |
|--------|------|-------------|
| `canonical_hook_rate` | float | Normalized hook rate |
| `canonical_hold_rate` | float | Normalized hold rate |
| `canonical_completion_rate` | float | Normalized completion rate |
| `canonical_engagement_rate` | float | Normalized engagement rate |
| `canonical_ctr` | float | Normalized CTR |
| `canonical_cost_efficiency` | float | Normalized cost efficiency |
| `attention_proxy_score` | float | 0-100 attention proxy score |
| `attention_inputs_available` | bool | Whether attention inputs existed |
| `score_renormalized` | bool | Whether score was renormalized |
| `primary_kpi_score` | float | Explicit primary component |
| `secondary_kpi_score` | float | Explicit secondary component |
| `cost_efficiency_score` | float | Explicit efficiency component |
| `attention_proxy_weight` | float | Actual weight used (0.0-0.1) |
| `applied_weight_total` | float | Sum of weights (0.9 or 1.0) |
| `campaign_normalized` | str | Standardized campaign name |
| `format_normalized` | str | Standardized format |
| `placement_normalized` | str | Standardized placement |
| `objective_normalized` | str | Standardized objective |

### Columns Removed

| Column | Reason |
|--------|--------|
| `brand_score` | Wooshii removed |
| `core_message_score` | Wooshii removed |
| `association_score` | Wooshii removed |
| `brand_score_pct` | Wooshii component removed |

---

## 10. Assumptions & Limitations

### Assumptions

1. **Input data structure** — Same Excel format with "Data Analysis Paid Meta", "Data Analysis Paid TikTok", etc. sheets
2. **Platform metrics available** — 2s/3s VTR, completion rate, and basic engagement metrics are present
3. **Hook/Hold rate** — May not be available in all exports; attention proxy handles missing gracefully
4. **Single workbook output** — One Excel file per run, no multi-file aggregation

### Limitations

1. **Excel filter limitations** — Data validation dropdowns are static; won't auto-update if data changes after open
2. **No true interactivity** — Dashboard is pre-rendered; users can't change filters and see results update in real-time
3. **No per-campaign tabs** — By design, to prevent workbook bloat
4. **Looker export** — Requires manual upload to Google Sheets before connecting to Looker Studio

### Out of Scope

1. Real-time data refresh
2. API-based data ingestion
3. Database storage
4. Web-based dashboard (future consideration)
5. Automated Looker Studio connection

---

## 11. Success Criteria

The refactor is complete when:

- [ ] Wooshii references removed from all code and output
- [ ] Native attention proxy calculates correctly
- [ ] Score renormalization works when attention inputs missing
- [ ] Dashboard front sheet has Campaign/Platform/Format filters
- [ ] Dashboard has Top Range / Dimension / KPI selection controls
- [ ] Main comparison tables render correctly for each dimension
- [ ] Lower overview sections (iOS vs Android, Brand vs Creator, etc.) update with filters
- [ ] Summary tabs exist for Overall, Asset Type, OS, Placement
- [ ] All column lists updated (Wooshii removed, attention proxy added)
- [ ] "How Scoring Works" tab reflects new methodology
- [ ] CLI behavior unchanged (same arguments, same exit codes)

---

## 12. Questions for PM Review

1. **Attention Proxy Inputs** — Are hook rate and hold rate metrics available in the current data exports? If not, should we rely solely on VTR + completion rate?

2. **Objective Mapping** — Should we add "Sales" as a distinct objective, or map conversions/purchases to the existing "Conversions" objective?

3. **Dashboard Interactivity** — Given Excel's limitations, is a pre-rendered dashboard acceptable, or should we consider a web-based dashboard (Streamlit/Gradio) for true interactivity?

4. **Asset Type Labels** — The requirement mentions "Brand vs Creator" — should we also support "Partner" as a third category, or collapse all non-Brand into "Creator"?

5. **Format Categories** — You mentioned Video/Motion/Static — should we also track Carousel, Reels, Stories as separate formats, or group them differently?

6. **Top Range Options** — Is "Top 5 / Top 10 / Top 50" sufficient, or should we add more options (Top 20, Top 100)?

---

*End of Design Spec*
