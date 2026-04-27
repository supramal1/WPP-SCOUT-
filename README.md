# WPP SCOUT

Automated tool for scoring and ranking social media creatives based on the evaluation methodology used by the social team at EssenceMediacom. Built for Google Pixel campaign data across TikTok and Meta.

## What it does

1. Reads campaign performance data from an Excel export (platform data + Wooshi brand measurement)
2. Scores each creative 0-100 based on:
   - **Objective alignment** - evaluates against the metric that matters for how the ad was bought (VTR for Video Views, reach efficiency for Brand Awareness, etc.)
   - **Spend normalisation** - flags low-spend creatives as "low confidence" so they don't falsely rank high
   - **Frequency penalty** - reduces scores for over-exposed creatives (frequency > 2x)
   - **Cost efficiency** - rewards creatives that deliver outcomes cheaper
   - **Brand measurement** - incorporates Wooshi brand/core message scores where available
3. Generates plain-English explanations of why each creative ranked where it did
4. Exports a formatted Excel report with Summary, per-platform rankings, and methodology documentation

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python main.py "path/to/Pixel Data chat - pixel UK and DE_Automation.xlsx"
```

### Options

- `-o OUTPUT` - Custom output file path (default: `creative_analysis_output.xlsx` in same directory as input)
- `--min-spend 500` - Minimum spend threshold for statistical significance (default: £500)
- `--min-reach 10000` - Minimum reach threshold (default: 10,000)

## Output

- **Console** - Top 10 and bottom 5 creatives per platform with key metrics
- **Excel** - Full workbook with:
  - `Summary - Top Performers` - Top 30 high-confidence creatives with explanations
  - `TikTok Rankings` - All TikTok creatives scored and ranked
  - `Meta Rankings` - All Meta creatives scored and ranked
  - `Methodology` - Documents the scoring approach

## Scoring Weights

| Component | Weight | Description |
|-----------|--------|-------------|
| Primary metric | 50% | Objective-aligned KPI (VTR, completion rate, CTR, etc.) |
| Secondary metrics | 25% | Supporting KPIs (shares, engagement, etc.) |
| Cost efficiency | 15% | Cost per outcome vs group average |
| Brand measurement | 10% | Wooshi brand + core message scores |
