# Creative Performance Analyzer - Context Dump

> Generated: 2026-03-19
> Purpose: Full technical breakdown for handoff to another chat session

---

## Project Overview

**What it is:** An automated Python tool that scores and ranks social media creatives based on performance metrics, built for Google Pixel campaign data (TikTok + Meta).

**Who it's for:** EssenceMediacom social team - automates the manual creative evaluation process.

**Key Output:** A formatted Excel report with:
- Ranked creatives by score (0-100)
- Plain-English explanations of why each creative ranked where it did
- Per-platform breakdowns (TikTok, Meta)
- Split analysis (iOS vs Android, audience segments, asset types)
- Looker Studio export

---

## Architecture

```
creative-analyzer/
├── main.py              # Entry point, CLI args, orchestration
├── requirements.txt     # pandas, openpyxl, xlsxwriter
├── README.md
├── .env.example
├── venv/                # Python 3.13 venv
└── src/
    ├── __init__.py
    ├── loader.py        # Data ingestion, Excel parsing, aggregation
    ├── scorer.py        # Scoring logic, objective-metric mapping
    ├── explainer.py     # Plain-English explanation generation
    └── reporter.py      # Excel output, Looker export, console reports
```

---

## Data Flow

```
Excel Input (platform + Wooshi sheets)
    ↓
loader.py → Parse, clean, aggregate creatives
    ↓
scorer.py → Score 0-100 based on objective-aligned metrics
    ↓
explainer.py → Generate "why it ranked here" text
    ↓
reporter.py → Export formatted Excel + Looker CSV
```

---

## Input Format (Excel)

The tool expects a multi-sheet Excel file with:

### Platform Data Sheets
- **TikTok** sheet or similar
- **Meta** sheet or similar
- Columns expected:
  - `ad_name` or `Ad name` - raw ad identifier
  - `spend` / `Amount spent` - media spend
  - `reach` - unique users reached
  - `impressions` - total impressions
  - `clicks` - click count
  - `video_views_100` - 100% video views
  - `video_views_2s` / `video_views_3s` - hook metric
  - `video_p25_watched` / `video_p50_watched` / `video_p75_watched` - quartile views
  - `frequency` - impressions/reach
  - `objective` / `Objective` - campaign objective
  - `buying_type` - Paid vs Boosting (inferred if not present)
  - Duration columns for completion rate adjustment

### Wooshi Brand Measurement Sheet
- `creative_name` - matching identifier
- `brand_score` - brand recall score
- `core_message_score` - message delivery score

---

## Scoring Methodology

### Objective → Metric Mapping

```python
OBJECTIVE_METRICS = {
    'Video Views': {
        'primary': ['vtr_2s'],                              # Hook metric
        'secondary': ['completion_vs_expected', 'ctr', 'share_rate'],
        'efficiency': 'cost_per_complete_view',
    },
    'Brand Awareness': {
        'primary': ['reach_per_pound'],
        'secondary': ['vtr_2s', 'completion_vs_expected'],
        'efficiency': 'cpm',
    },
    'Engagement': {
        'primary': ['engagement_rate'],
        'secondary': ['share_rate', 'ctr', 'completion_vs_expected'],
        'efficiency': 'cpm',
    },
    'Traffic': {
        'primary': ['ctr'],
        'secondary': ['engagement_rate', 'completion_vs_expected'],
        'efficiency': 'cpm',
    },
    'Conversions': {
        'primary': ['ctr'],
        'secondary': ['completion_vs_expected', 'engagement_rate'],
        'efficiency': 'cpm',
    },
}
```

### Scoring Weights

| Component | Weight | Description |
|-----------|--------|-------------|
| Primary metric | 50% | Objective-aligned KPI (VTR, completion rate, CTR, etc.) |
| Secondary metrics | 25% | Supporting KPIs (shares, engagement, etc.) |
| Cost efficiency | 15% | Cost per outcome vs group average |
| Brand measurement | 10% | Wooshi brand + core message scores |

### Additional Factors

- **Spend normalization:** Creatives under €500 spend flagged as "low confidence"
- **Frequency penalty:** Frequency > 2x reduces score (audience fatigue)
- **Duration-adjusted completion:** Normalizes completion rate by video length
  - <15s: ~3.5% expected
  - 15-30s: ~2.4% expected
  - 30-60s: ~0.9% expected
  - 60s+: ~0.5% expected

### Score Interpretation

| Score | Tier | Action |
|-------|------|--------|
| 85-100 | Top Performer | Scale spend, use as template |
| 70-84 | Strong | Keep running, consider budget increase |
| 50-69 | Average | Review for optimization |
| 25-49 | Below Average | Consider pausing |
| 0-24 | Poor | Pause and replace |

---

## Key Functions by Module

### loader.py

```python
def load_data(filepath: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (raw_df, aggregated_df)"""

def aggregate_creatives(df: pd.DataFrame) -> pd.DataFrame:
    """Groups by creative_name + platform + objective + buying_type
    - Sums: spend, reach, impressions, clicks, video views
    - Impression-weighted average: VTR
    - Takes first: format, asset_type, currency"""

def compute_duration_adjusted_completion(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizes completion rate by video duration"""

def compute_audience_consistency(df_raw, df_agg) -> pd.DataFrame:
    """Scores consistency across audiences/campaigns"""
```

### scorer.py

```python
def score_creatives(df: pd.DataFrame) -> pd.DataFrame:
    """Main scoring function - adds composite_score column
    Scores are relative within objective + platform + buying_type cohort"""

def score_raw_variants(df: pd.DataFrame) -> pd.DataFrame:
    """Scores individual ad lines (not aggregated) for split analysis"""

def assign_action(score: float, low_confidence: bool) -> str:
    """Maps score to action: Scale Up, Optimise, Review, Consider Pausing, Pause"""
```

### explainer.py

```python
def explain_creative(row: pd.Series) -> str:
    """Generates plain-English explanation of why a creative ranked where it did
    Includes: score assessment, strength highlights, weakness flags, recommendation"""

def generate_explanations(df: pd.DataFrame) -> pd.DataFrame:
    """Adds 'explanation' column to scored DataFrame"""
```

### reporter.py

```python
def print_console_report(df: pd.DataFrame, brand: str) -> None:
    """Prints summary to terminal"""

def export_excel(df, output_path, df_raw, brand) -> None:
    """Exports formatted Excel with multiple sheets"""

def export_looker_csv(df_raw: pd.DataFrame, output_path: str) -> None:
    """Exports flat XLSX for Looker Studio connection"""
```

---

## Output Excel Structure

| Sheet | Purpose |
|-------|---------|
| **Summary** | Dashboard with top performers, stats, methodology |
| **TikTok Rankings** | All TikTok creatives ranked by score |
| **Meta Rankings** | All Meta creatives ranked by score |
| **Splits Analysis** | Raw ad lines with all split dimensions filterable |
| **OS Comparison** | iOS vs Android performance side-by-side |
| **Cross-Platform** | Creatives running on both TikTok + Meta |
| **Asset Types** | Performance by asset type (Static, Video, Carousel) |
| **Obj × Format Matrix** | Score averages by objective + format combination |
| **Looker Export** | Flat table for Google Sheets → Looker Studio |
| **Methodology** | Scoring weights and tier definitions |

---

## CLI Usage

```bash
# Basic usage
python main.py "path/to/campaign_data.xlsx"

# With options
python main.py "campaign_data.xlsx" \
  -o "output_report.xlsx" \
  --min-spend 1000 \
  --min-reach 50000 \
  --looker-csv "looker_export.xlsx" \
  --brand "Google Pixel"
```

### CLI Arguments

| Arg | Default | Description |
|-----|---------|-------------|
| `input_file` | required | Path to Excel input |
| `-o, --output` | `creative_analysis_output.xlsx` | Output path |
| `--min-spend` | 500 | Low confidence threshold (€) |
| `--min-reach` | 10000 | Low confidence threshold |
| `--looker-csv` | None | Export Looker-ready XLSX |
| `--brand` | "" | Brand name for report headers |

---

## Dependencies

```
pandas>=2.2.0
openpyxl>=3.1.0
xlsxwriter>=3.1.0
```

---

## Key Technical Details

### Platform Normalization
- Detects "TikTok" or "Meta" from sheet names
- Normalizes column names to snake_case

### VTR Handling
- TikTok: 2-second VTR
- Meta: 3-second VTR
- Scored separately per platform, not directly comparable

### Buying Type
- Paid vs Boosting scored in separate cohorts
- Never compare Paid score to Boosting score directly

### Cross-Platform Detection
- Same `creative_name` appearing on both platforms
- Flagged in output for comparison

---

## Common Gotchas

1. **Column name variations:** Loader handles multiple naming conventions (`spend` vs `Amount spent`), but new formats may need updates
2. **Missing Wooshi data:** Tool handles absence gracefully, scores without brand measurement component
3. **Duration extraction:** Parsed from `ad_name_raw` using regex - may fail on non-standard naming
4. **OS/segment detection:** Based on keywords in ad name - relies on naming conventions

---

## Current State

- Working prototype, last modified Mar 16-18, 2026
- Built for Google Pixel UK/DE campaigns
- Handles TikTok + Meta data
- Generates full Excel reports with split analysis
- Looker Studio export available

---

## Files for Reference

- `main.py` - Entry point (100 lines)
- `src/loader.py` - Data parsing (~400 lines)
- `src/scorer.py` - Scoring logic (~200 lines)
- `src/explainer.py` - Explanations (~100 lines)
- `src/reporter.py` - Output generation (~800 lines)
