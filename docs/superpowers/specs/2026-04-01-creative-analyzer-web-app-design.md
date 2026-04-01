# Creative Analyzer Web App — Design Spec

> Date: 2026-04-01
> Status: Approved
> Author: Malik Roberts + Claude

---

## Problem

The creative analyzer currently outputs a static Excel workbook. Three limitations have surfaced:

1. **Dimension filters don't change the output.** The Dashboard dropdown offers abstract category names (Asset Type, OS, Placement, Objective) but the ranked table always shows the same scores regardless of selection.
2. **Scores are fixed per asset.** The creative score is computed once across all delivery data. Filtering to "Android only" still shows the score that was calculated including iOS delivery. Users cannot understand how a given asset performs within a specific context.
3. **Creative-name-level scoring causes duplication.** The same concept surfaces multiple times across different placement/format/OS variations, making it harder to identify truly distinct winning ideas.

A spreadsheet cannot solve these problems well. Dynamic recalculation, interactive filtering, and toggleable aggregation levels are fundamentally web app capabilities.

---

## Solution

A web-based creative performance dashboard. Users upload an Excel file, get an interactive scored dashboard with real dimension filters, context-sensitive re-scoring, and concept-level aggregation.

### Architecture

- **Backend:** FastAPI wrapping the existing Python scoring logic (`loader.py`, `scorer.py`, `explainer.py`)
- **Frontend:** Next.js + shadcn/ui, dark theme (zinc palette), single-page app
- **Deployment:** Both services on Vercel (Next.js standard deploy, FastAPI via Fluid Compute Python functions)
- **No persistence:** Upload per session, in-memory cache for raw data (1hr TTL), no database, no auth

### Users

- Internal: EssenceMediacom social/innovation team (2-10 people)
- Client-facing: Used during presentations and screen-shares with brand clients (e.g., Google Pixel)

---

## Data Flow

### Upload & Initial Score

1. User uploads Excel file via drag-and-drop or file picker
2. File sent to `POST /api/upload-and-score`
3. Backend runs `load_data()` -> returns `(df_raw, df_agg)`. `df_raw` at this point already has derived columns computed by `load_data()`: `completion_rate`, `ctr`, `engagement_rate`, canonical metrics (`canonical_hook_rate`, `canonical_hold_rate`, `canonical_completion_rate`), and attention proxy inputs. This is the version that gets cached — not the truly raw DataFrame before derived columns.
4. Backend runs `score_raw_variants(df_raw)` -> scores every individual ad line within its cohort. Note: `score_raw_variants()` recomputes rate metrics from raw counts internally, so percentile ranks are relative to the scoring cohort.
5. Backend runs `assign_action()` on each scored row to add the `action` column (Scale Up, Keep Running, Review, Pause, etc.). This is required because `score_raw_variants()` does not call `assign_action()` — only `score_creatives()` does. The web backend must add this step explicitly after scoring.
6. `df_raw` (post-`load_data()`, pre-scoring, with all derived columns) cached in server memory, keyed by upload ID (TTL 1 hour)
7. Returns full scored dataset as JSON + distinct filter values + metadata

### Client-Side Filtering (instant)

- Filter dropdowns show actual values: Android, iOS, Stories, Feed, Reels, Brand, Creator, etc.
- Selecting a filter subsets the cached scored data in the browser and re-renders the table
- Scores per row don't change — they were scored within their original cohort
- This is the default interaction for all filter changes

### Context-Sensitive Re-Scoring (on demand)

- "Re-score within filters" button in the filter bar
- Sends current filter state to `POST /api/rescore` with the upload ID
- Backend retrieves cached `df_raw`, subsets to matching rows, runs `score_raw_variants()` on the subset
- Scores are now relative to the filtered cohort only (e.g., only Android creatives competing against each other)
- Frontend replaces the scored dataset with the new results

### Concept-Level Aggregation (client-side toggle)

- Toggle switch: "Group by: Creative Name | Concept"
- The `concept` column is already loaded from the Excel data (well-populated, loaded from Excel "Concept" column in `loader.py`). It survives the scoring pipeline — `score_raw_variants()` works on a copy of `df_raw` and `pd.concat` preserves all columns including `concept`.
- When Concept is selected, frontend groups scored rows by `concept` column

**Aggregation formula (mirrors `aggregate_creatives()` logic):**
- `score`: spend-weighted average — `sum(score * spend) / sum(spend)` across all rows in the concept
- `spend`, `reach`, `impressions`, `clicks`, `shares`, `engagements`: summed
- `vtr_2s`: impression-weighted average — `sum(vtr_2s * impressions) / sum(impressions)` (matches existing aggregation in `loader.py`)
- `ctr`, `engagement_rate`, `completion_rate`: recomputed from summed numerators — e.g., `ctr = (sum(clicks) / sum(impressions)) * 100`
- `cpm`: recomputed — `(sum(spend) / sum(impressions)) * 1000`
- `frequency`: recomputed — `sum(impressions) / sum(reach)`
- `tier`: derived from the aggregated weighted score using standard tier boundaries
- `n_variations`: count of rows in the group
- `best_variation_score`, `worst_variation_score`: max/min of `composite_score` within group

Expandable rows reveal individual creatives within the concept.

---

## API Design

### `POST /api/upload-and-score`

**Request:** Multipart file upload (Excel)

**Response:**
```json
{
  "upload_id": "abc123",
  "creatives": [
    {
      "creative_name": "Pixel_Summer_15s_iOS_Feed",
      "concept": "Pixel Summer",
      "platform": "Meta",
      "objective": "Awareness",
      "format": "Video",
      "placement": "Feed",
      "os_target": "iOS",
      "asset_type_canonical": "Brand",
      "buying_type": "Paid",
      "campaign_normalized": "Pixel UK Q2",
      "composite_score": 78.3,
      "tier": "Strong",
      "action": "Scale Up",
      "spend": 12500,
      "reach": 450000,
      "impressions": 890000,
      "vtr_2s": 34.2,
      "completion_rate": 2.1,
      "ctr": 0.45,
      "engagement_rate": 0.12,
      "share_rate": 0.03,
      "cpm": 14.04,
      "frequency": 1.98,
      "cost_per_complete_view": 0.18,
      "reach_per_pound": 36.0,
      "completion_vs_expected": 1.4,
      "scoring_group": "Awareness | Meta | Paid",
      "explanation": "Strong performer (score: 78.3/100)...",
      "low_confidence": false
    }
  ],
  "filters": {
    "campaigns": ["Pixel UK Q2", "Pixel DE Q2"],
    "platforms": ["TikTok", "Meta"],
    "os": ["iOS", "Android", "All"],
    "placements": ["Feed", "Stories", "Reels", "In Feed"],
    "objectives": ["Awareness", "Video Views", "Engagement"],
    "formats": ["Video", "Static", "Motion"],
    "asset_types": ["Brand", "Creator"],
    "buying_types": ["Paid", "Boosting"],
    "concepts": ["Pixel Summer", "Pixel Fall", "Creator Collab"]
  },
  "meta": {
    "total_rows": 1234,
    "platforms_found": ["TikTok", "Meta"],
    "brand": "Google Pixel"
  }
}
```

### `POST /api/rescore`

**Request:**
```json
{
  "upload_id": "abc123",
  "filters": {
    "os": "Android",
    "platform": "Meta"
  }
}
```

**Response:** Same `creatives` shape as upload response, with recalculated scores relative to the filtered subset.

**Error cases:**
- Upload ID not found in cache (instance recycled or routed to different instance): `404 { "error": "upload_expired", "message": "Session expired. Please re-upload your file." }`
- Note: Vercel may route concurrent requests to different function instances. The in-memory cache is per-instance, so a rescore request may hit a different instance than the upload. This is the same user-facing symptom as instance recycling — handled identically with the re-upload prompt.

### `POST /api/upload-and-score` — Error Responses

- Invalid file type (not .xlsx/.xls): `400 { "error": "invalid_file", "message": "Please upload an Excel file (.xlsx)" }`
- No matching sheets found: `400 { "error": "no_sheets", "message": "No matching data sheets found. Expected sheets: Data Analysis Paid Meta, Data Analysis Paid TikTok, etc." }`
- Missing required columns: `400 { "error": "missing_columns", "message": "Required columns missing: [list]" }`
- Empty data after parsing: `400 { "error": "empty_data", "message": "No valid creative data found in the uploaded file." }`

### Filter Key to DataFrame Column Mapping

API filter keys map to DataFrame columns as follows:

| Filter Key (API) | DataFrame Column | Notes |
|---|---|---|
| `campaign` | `campaign_normalized` | Normalized campaign name |
| `platform` | `platform` | TikTok, Meta |
| `os` | `os_target` | iOS, Android, All |
| `placement` | `placement` | Feed, Stories, Reels, In Feed, etc. |
| `objective` | `objective` | Awareness, Video Views, Engagement, etc. |
| `format` | `format_canonical` | Video, Static, Motion (same as `format` in response) |
| `asset_type` | `asset_type_canonical` | Brand, Creator |
| `buying_type` | `buying_type` | Paid, Boosting |
| `concept` | `concept` | Concept grouping from Excel |

---

## Frontend Views

### Action View (default, landing page after upload)

- **Upload zone** at the top: drag-and-drop or file picker, disappears after upload
- **Filter bar:** Campaign, Platform, OS, Placement, Objective, Format, Asset Type, Buying Type — all dropdowns populated from API `filters` response, showing actual values not category names
- **"Re-score within filters" button** in the filter bar
- **Summary stat cards:** Total creatives, filtered count, average score, top tier count
- **Ranked table:** Rank, Creative Name, Score (with tier colour), Platform, Objective, Format, KPI columns (VTR, Completion Rate, CTR), Spend, Action recommendation
- Tier colour coding: Top Performer (green), Strong (blue), Average (neutral), Below Average (orange), Poor (red)
- Sortable columns, row click to expand explanation

### Concept View (toggle)

- Toggle switch in filter bar: "Group by: Creative Name | Concept"
- Table shows: Concept name, weighted score, tier, number of variations, total spend, best/worst variation score
- Expandable rows reveal individual creatives within the concept
- Same filter bar applies

### Comparison View (tab)

- Select a dimension to split by (e.g., OS, Platform, Asset Type)
- Side-by-side table: same creatives, scores in each context
- Highlights significant score divergence (>15 points difference)
- Useful for answering "does this creative work better on Android or iOS?"

**How it works (API):** The Comparison View uses the existing `/api/rescore` endpoint, called multiple times in parallel. For example, comparing Android vs iOS:
1. Frontend calls `POST /api/rescore` with `{ "filters": { "os": "Android" } }`
2. Frontend calls `POST /api/rescore` with `{ "filters": { "os": "iOS" } }` (in parallel)
3. Both responses return scored creatives relative to their respective cohorts
4. Frontend joins results by `creative_name` and renders side-by-side with score delta

No dedicated comparison API endpoint is needed — the frontend orchestrates parallel rescore calls and merges the results client-side.

### Layout

Single-page app. No routing. Upload -> dashboard appears. Three view modes accessible via tabs or toggle. All state in browser memory after upload.

---

## Project Structure

```
creative-analyzer/
├── api/                          # FastAPI backend
│   ├── main.py                   # FastAPI app, CORS, lifespan
│   ├── routes/
│   │   ├── upload.py             # POST /api/upload-and-score
│   │   └── rescore.py            # POST /api/rescore
│   ├── scoring/
│   │   ├── loader.py             # Adapted from src/loader.py
│   │   ├── scorer.py             # Adapted from src/scorer.py
│   │   └── explainer.py          # Adapted from src/explainer.py
│   ├── models.py                 # Pydantic request/response schemas
│   ├── cache.py                  # In-memory upload cache (TTL 1hr)
│   └── requirements.txt          # fastapi, uvicorn, pandas, openpyxl
│
├── web/                          # Next.js frontend
│   ├── app/
│   │   ├── layout.tsx            # Root layout, Geist font, dark theme
│   │   └── page.tsx              # Single-page dashboard
│   ├── components/
│   │   ├── upload-zone.tsx       # Drag-and-drop file upload
│   │   ├── filter-bar.tsx        # Dimension dropdowns + rescore button
│   │   ├── score-table.tsx       # Ranked creative table (Action view)
│   │   ├── concept-view.tsx      # Concept-level grouped table
│   │   ├── comparison-view.tsx   # Side-by-side dimension comparison
│   │   ├── tier-badge.tsx        # Colour-coded tier indicator
│   │   └── stat-cards.tsx        # Summary stat cards
│   ├── lib/
│   │   ├── api.ts                # Fetch helpers for upload/rescore endpoints
│   │   ├── filters.ts            # Client-side filter/aggregate logic
│   │   └── types.ts              # TypeScript types matching API response
│   ├── package.json
│   └── next.config.ts
│
├── src/                          # Original CLI tool (preserved, untouched)
│   ├── loader.py
│   ├── scorer.py
│   ├── explainer.py
│   └── reporter.py
├── main.py                       # Original CLI entry point (preserved)
├── requirements.txt              # Original CLI deps (preserved)
└── docs/
```

### Key Decisions

- `api/scoring/` copies and adapts from `src/` rather than importing — keeps CLI and web versions independent
- `web/` is a standalone Next.js app with its own `package.json`
- Dark theme default (shadcn/ui zinc palette) — professional for client presentations
- Geist Sans for interface text, Geist Mono for scores/metrics

---

## Deployment

- **Frontend:** `web/` deployed as standard Next.js on Vercel
- **Backend:** `api/` deployed as Vercel Python function via Fluid Compute
- **Routing:** `next.config.ts` rewrites `/api/*` to the Python backend URL — same domain, no CORS
- **Environment:** `NEXT_PUBLIC_API_URL` (or just `/api` via rewrites). No API keys, no database, no secrets.

### In-Memory Cache on Vercel

- Fluid Compute reuses function instances across requests — in-memory cache works for most sessions
- If instance recycles between upload and rescore, user gets "please re-upload" message
- Acceptable for v1 given upload-per-session model
- Upgrade path: swap to Upstash Redis if this becomes a pain point

### Limits

- Vercel Python functions: 300s timeout (plenty for scoring thousands of rows)
- File upload: 4.5MB on Hobby, 50MB on Pro (Excel files well within this)

---

## Deferred (v2+)

- Authentication / login
- Persistent reports (save and share via URL)
- Multi-brand loader configs (flexible Excel format mapping)
- Export/download (PDF, CSV)
- Historical comparison (this month vs last month)

---

## Scoring Logic Reference

The web app reuses the existing scoring methodology unchanged:

| Component | Weight | Description |
|-----------|--------|-------------|
| Primary metric | 50% | Objective-aligned KPI (VTR, completion rate, CTR, etc.) |
| Secondary metrics | 25% | Supporting KPIs (shares, engagement, etc.) |
| Cost efficiency | 15% | Cost per outcome vs group average |
| Attention proxy | 10% | Hook rate, hold rate, completion patterns (renormalized to 90% if unavailable) |

Additional factors: frequency penalty (>2x), audience consistency adjustment, low-confidence cap (spend <500 or reach <10k), format-aware scoring (static assets use ER/CTR instead of VTR/completion).

Scoring cohorts: objective x platform x buying_type x format_canonical. Paid and Boosting are never compared directly.

### Tier Score Boundaries

| Score Range | Tier | Colour (frontend) |
|---|---|---|
| 85-100 | Top Performer | Green (`#22c55e`) |
| 70-84 | Strong | Blue (`#3b82f6`) |
| 50-69 | Average | Neutral/grey (`#a1a1aa`) |
| 25-49 | Below Average | Orange (`#f97316`) |
| 0-24 | Poor | Red (`#ef4444`) |

These match `scorer.py` lines 423-428 (`pd.cut` bins: `[0, 25, 50, 70, 85, 100]`).

### UX for Loading States

- **Upload + initial score:** Full-page loading state with progress text ("Uploading...", "Scoring creatives...", "Building dashboard...")
- **Re-score within filters:** Inline loading spinner on the "Re-score" button + table skeleton/overlay. Filter bar remains interactive. Previous data stays visible but dimmed until new scores arrive.
- **Comparison View:** Both columns show skeleton loaders until their respective rescore calls complete. They can resolve independently.
