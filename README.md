# WPP SCOUT

```text
                  .-=================================================-.
              .--'                                                   '--.
 __        ______  ____    ____   ____ ___  _   _ _____                 |
 \ \      / /  _ \|  _ \  / ___| / ___/ _ \| | | |_   _|                |
  \ \ /\ / /| |_) | |_) | \___ \| |  | | | | | | | | |                  |
   \ V  V / |  __/|  __/   ___) | |__| |_| | |_| | | |                  |
    \_/\_/  |_|   |_|     |____/ \____\___/ \___/  |_|                  |
              '--.                                                   .--'
                  '-====[ campaign signal intelligence over MCP ]====-'

        raw exports >>> map >>> QA >>> score >>> explain >>> recommend
                  placement truth + concept rollups + action plans
```

WPP Scout is an MCP-first backend for analyzing paid social creative performance. It ingests Meta and TikTok campaign exports, maps them into a canonical schema, scores creatives against objective-specific KPIs, and exposes the analysis through MCP tools for an agent to query.

The intended user experience is: a non-technical user asks a chat agent a campaign-performance question, and the agent calls WPP Scout MCP tools to ingest data, inspect quality, rank creatives, compare concepts, explain performance, and recommend action.

There is no bundled web frontend in this repo. The optional FastAPI app remains as a local/API harness for health checks, browser-upload style JSON payloads, mapping preview, and scoring routes.

## Current Status

- Product name: `WPP Scout`
- MCP server name: `wpp-scout`
- Primary runtime: `mcp_server.py`
- Optional API runtime: `api/main.py`
- Supported source formats: Pixel DE-style Excel workbooks, generic CSV, generic Excel exports
- AI mapping layer: Gemini via Vertex AI using Google Application Default Credentials, with a heuristic fallback
- Planned hosting: GCP/Cloud Run, not required for local development

## Repository Layout

| Path | Purpose |
|---|---|
| `mcp_server.py` | MCP server, tool registry, session state, SSE transport. |
| `main.py` | CLI workflow for local Excel report generation. |
| `src/loader.py` | Standard workbook loading, mapped data loading, normalization, aggregation. |
| `src/data_mapping.py` | Mapping preview workflow and canonical schema definitions. |
| `src/llm_mapper.py` | Gemini/Vertex column-mapping layer with heuristic fallback. |
| `src/scorer.py` | Objective-specific scoring algorithm, confidence, fatigue, tiers, actions. |
| `src/explainer.py` | Plain-English creative explanations and dimension trend summaries. |
| `src/insights.py` | Data-quality, concept, fatigue, budget, comparison, and action-plan helpers. |
| `src/reporter.py` | Optional CLI Excel/Looker-style exports. |
| `api/` | Optional FastAPI app and API route wrappers. |
| `tests/`, `api/tests/` | Unit and integration tests. |
| `test_mcp_flow.py` | Deterministic local MCP smoke test using an in-memory CSV. |
| `docs/` | Analysis outputs and project documentation. |

Useful docs:

| Doc | Purpose |
|---|---|
| `docs/wpp-scout-algorithm-onepager.html` | Executive visual one-pager explaining the scoring approach and hidden analytical complexity. |
| `docs/pixel-de-wpp-scout-mcp-analysis-2026-04-27.md` | Client-ready analysis generated from MCP outputs against the provided Pixel DE workbook. |

## Requirements

- Python 3.11+ recommended.
- Google Cloud ADC is only required for AI-assisted mapping. Standard Pixel workbooks and explicit mappings work without it.
- Root runtime dependencies are in `requirements.txt`.
- Optional FastAPI dependencies are in `api/requirements.txt`.

## Installation

Create a virtual environment and install the root dependencies:

```bash
cd /Users/malik.james-williams/Desktop/CreativeAnalyser
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

If you also need the optional FastAPI harness:

```bash
python3 -m pip install -r api/requirements.txt
```

For AI mapping via Gemini on Vertex AI, set the Google project and make sure ADC is available:

```bash
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
gcloud auth application-default login
```

On Cloud Run, ADC should come from the service account. The service account will need permission to call Vertex AI Gemini models.

## Quick Smoke Test

Run the local MCP smoke test:

```bash
python3 test_mcp_flow.py
```

Expected shape:

```text
MCP smoke passed: 2 creatives, 0 priority action(s)
```

Run the full test suite:

```bash
python3 -m pytest api/tests tests -q
```

Optional syntax/import check:

```bash
python3 -m compileall api src mcp_server.py main.py test_mcp_flow.py -q
```

## Running The MCP Server Locally

Start the MCP server:

```bash
PORT=8765 python3 mcp_server.py
```

Local SSE endpoints:

| Endpoint | Purpose |
|---|---|
| `http://localhost:8765/sse` | MCP SSE connection endpoint. |
| `http://localhost:8765/messages` | MCP message POST endpoint used by the SSE transport. |

The MCP server stores analyzed data in process memory. `ingest_data` always returns a `session_id`; pass it into later tools. If a query omits `session_id`, Scout can still use the active session, but the response includes a warning and session summary. Strict agents should pass `require_session_id: true`.

## MCP Data Ingest Workflow

Remote agents should treat upload as the default path. If the user provides a file from their laptop or chat attachment, read the bytes and send them to Scout with chunked upload. `file_path` is only for files that already exist on the Scout server filesystem; a client-local path such as `/Users/.../Downloads/file.xlsx` will not be readable by the remote Cloud Run service.

For small files, `preview_data_mapping` and `ingest_data` still accept:

```json
{
  "file_data_base64": "<base64 CSV/XLS/XLSX>",
  "file_name": "campaign_export.xlsx"
}
```

For normal campaign workbooks, prefer chunked upload so the agent does not have to pass one large base64 argument:

1. Optionally call `recommend_upload_plan` with `file_name` and `size_bytes` for chunk guidance.
2. Call `create_file_upload_session` with `file_name`, `expected_size_bytes`, and `expected_chunks`.
3. Base64-encode the file and send it in smaller chunks with `append_file_upload_chunk` using `chunk_data_base64` (the older `data_base64` alias is also accepted).
4. Call `get_file_upload_status` if a chunk upload needs debugging or retry confirmation.
5. Call `finalize_file_upload`.
6. Pass the returned `upload_id` or `file_handle` to `preview_data_mapping`.
7. If needed, include `sheet_name` and `header_row`; `header_row` is 1-based, so Excel row 6 is `header_row: 6`.
8. Review `mapping_diagnostics`, `field_coverage`, `missing_required_fields`, `sample_normalized_rows`, `canonical_mapped_fields`, and `preserved_metadata_fields`.
9. Pass the same `upload_id` plus `mapping_id` to `ingest_data`.

Chunks may be slices of one full-file base64 string or independently base64-encoded byte chunks. Independently encoded chunks with padding are decoded chunk-by-chunk before Scout concatenates bytes, so non-final padding does not break finalization. A practical default for remote agents is 64-128 KB of raw bytes per chunk, with retry checks through `get_file_upload_status`.

Chunk retries are idempotent when `chunk_index` is supplied. Repeating the same index with identical data is accepted as a no-op; repeating it with different data returns a conflict.

Minimal chunked upload payloads:

```json
{ "file_name": "campaign_export.xlsx", "total_size": 7823412 }
```

```json
{ "upload_id": "<upload_id>", "chunk_index": 0, "chunk_data_base64": "<base64 chunk>" }
```

```json
{ "upload_id": "<upload_id>", "sheet_name": "Data Analysis (All)", "header_row": 6 }
```

Local or self-hosted agents can also pass a server-accessible `file_path`, `file://` handle, or `upload:<upload_id>` handle to `preview_data_mapping` and `ingest_data`. Remote WPP Open agents should use chunked upload unless the host provides a server-side file handle.

Useful MCP tools:

| Tool | Purpose |
|---|---|
| `get_canonical_schema` | Returns target fields, required fields, outcome fields, and common aliases. |
| `recommend_upload_plan` | Returns recommended chunk size/count and canonical remote-upload steps. |
| `create_file_upload_session` | Starts a chunked upload for `.csv`, `.xls`, or `.xlsx`. |
| `append_file_upload_chunk` | Appends one base64 chunk. Supports full-string slices, independently encoded chunks, and idempotent `chunk_index` retries. |
| `get_file_upload_status` | Returns chunk count, received indexes, received chars/bytes, expected size/chunks, storage mode, readiness, and finalization status. |
| `finalize_file_upload` | Decodes the uploaded chunks and returns a reusable `upload_id` / `file_handle`. |
| `preview_data_mapping` | Returns proposed column mapping, diagnostics, schema, and sample normalized rows before scoring. |
| `ingest_data` | Scores the finalized upload or file once the mapping has been confirmed. |
| `rank_creatives` | Post-ingest ranking by any numeric metric, including Scout `composite_score` or workbook `performance_score`. |
| `describe_session` | Summarizes an ingested session, including row counts, available metrics/group-by fields, distributions, mapping context, and warnings. |

Workbook parsing options accepted by `preview_data_mapping` and `ingest_data`:

| Option | Purpose |
|---|---|
| `sheet_name` | Parse one named sheet, for example `Data Analysis (All)`. |
| `header_row` | 1-based Excel header row, for example `6` for row 6. |
| `preserve_columns` | Keep extra source columns as `metadata_<slug>` fields for later filtering or `rank_creatives(group_by=...)`. |

For `.xlsx` files, Scout reads actual worksheet XML when normal pandas/openpyxl loading returns empty or weak columns. It does not rely on workbook dimension metadata such as `<dimension ref>`, `max_row`, or `max_column`. When `header_row` is omitted, Scout scores the first 10 worksheet rows for headers using aliases such as `Creative Name`, `Spends`, `Impressions`, `Platform`, and `Objective`.

Workbook-provided scoring:

Map columns such as `Creative Efficiency Index`, `Performance Score`, or `Performance Index` to `performance_score`. Scout preserves this alongside its own `composite_score`, and `rank_creatives` can rank by either metric.

## Optional FastAPI Harness

Run the API harness:

```bash
uvicorn api.main:app --reload --port 8000 --app-dir api
```

Useful routes:

| Route | Method | Purpose |
|---|---|---|
| `/api/health` | `GET` | Health check. |
| `/api/preview-data-mapping` | `POST` | Preview canonical mapping for parsed browser sheet rows. |
| `/api/upload-and-score` | `POST` | Score parsed browser sheet rows. Accepts optional `column_mapping`. |
| `/api/rescore` | `POST` | Rescore existing payloads. |
| `/api/diagnostics` | varies | Local diagnostic helpers. |
| `/api/splits` | varies | Split analysis helpers. |

The API accepts JSON shaped like:

```json
{
  "sheets": {
    "Data Analysis Paid Meta": [
      ["row 1"],
      ["row 2"],
      ["header", "row", "values"],
      ["data", "row", "values"]
    ]
  },
  "column_mapping": {
    "Spend (EUR)": "spend",
    "Impressions": "impressions"
  }
}
```

Payloads may be gzip-compressed with `Content-Encoding: gzip`.

## CLI Usage

The CLI is useful for local analyst workflows and Excel output. It is not the primary agent path.

```bash
python3 main.py "/path/to/campaign_export.xlsx"
```

Options:

```bash
python3 main.py "/path/to/campaign_export.xlsx" \
  --min-spend 500 \
  --min-reach 10000 \
  --brand "Google Pixel" \
  --output "/path/to/creative_analysis_output.xlsx" \
  --looker-csv "/path/to/looker_export.xlsx"
```

| Option | Default | Purpose |
|---|---:|---|
| `--min-spend` | `500` | Marks creative rows below this spend as low confidence. |
| `--min-reach` | `10000` | Marks creative rows below this reach as low confidence. |
| `--brand` | empty | Display label for report headers. |
| `--output` | next to input file | Excel output path. |
| `--looker-csv` | unset | Also export a flat Looker-friendly file. |
| `--google-sheets` | false | Export a Google Sheets-friendly workbook variant. |

## Supported Data Inputs

### Native Pixel Workbook

`load_data()` looks for these standard sheets:

| Sheet | Platform | Buying Type |
|---|---|---|
| `Data Analysis Paid Meta` | Meta | Paid |
| `Data Analysis Paid TikTok` | TikTok | Paid |
| `Data Analysis Boosting Meta` | Meta | Boosting |
| `Data Analysis Boosting TikTok` | TikTok | Boosting |

The native workbook loader expects headers on row 3 and normalizes columns such as `Creative Name`, `Platform`, `Format`, `Placement`, `Campaign`, `Objective`, `Reach`, `Impressions`, `Frequency`, `Spends`, `CPM`, `Clicks`, `2s VTR`, `3s VTR`, `Video Completion`, `Shares`, `Total Engagement`, `Duration`, `Partner`, `OS`, `Targeting Segment`, `Concept`, `Product`, and `Wave`.

### Non-Standard CSV Or Excel

For non-standard exports, use the mapping workflow:

1. Call `get_canonical_schema` if the agent needs the target fields.
2. Upload the file with chunked upload for larger workbooks, or pass a small `file_data_base64` payload.
3. Call `preview_data_mapping`.
4. Review `proposed_mapping`, `mapping_diagnostics`, `field_coverage`, `missing_required_fields`, `ignored_columns`, `canonical_mapped_fields`, `preserved_metadata_fields`, and `sample_normalized_rows`.
5. If acceptable, call `ingest_data` with `mapping_id`.
6. If the user corrects the mapping, call `ingest_data` with explicit `column_mapping`.
7. Use `preserve_columns` for useful fields outside Scout's scoring model. For example, `["Review Owner"]` becomes `metadata_review_owner`.

The mapping provider first tries Gemini on Vertex AI. If credentials are unavailable or the model call fails, it falls back to heuristic column matching. The heuristic is useful for simple exports but should not be treated as authoritative for client-critical uploads.

## Canonical Data Schema

These are the fields that the mapping layer can target.

| Field | Required | Description |
|---|---|---|
| `creative_name` | yes | Overarching creative/concept row name used for scoring and rollups. |
| `platform` | yes | Platform, normally `Meta` or `TikTok`. |
| `objective` | yes | Campaign objective, normalized to values such as `Awareness`, `Reach`, `Traffic`, `Engagement`, `Sales`, `Target Frequency`, or `Video Views`. |
| `spend` | yes | Total spend. |
| `impressions` | yes | Total ad impressions. |
| `ad_name_raw` | no | Raw ad variant name. |
| `format_raw` | no | Raw asset format. |
| `placement_raw` | no | Raw placement. |
| `campaign_raw` | no | Raw campaign name. |
| `buying_type` | no | `Paid` or `Boosting`; defaults to `Paid` for mapped exports. |
| `reach` | no | Unique reach. |
| `frequency` | no | Average frequency. If missing, the pipeline recomputes from impressions/reach where possible. |
| `cpm` | no | Cost per 1,000 impressions. Recomputed after aggregation. |
| `clicks` | no | Total clicks. |
| `vtr_2s` | no | Early attention rate. Meta 3s VTR and TikTok 2s VTR both map here. |
| `video_views_100` | no | 100% video completions. |
| `shares` | no | Total shares. |
| `engagements` | no | Total engagements/interactions. |
| `duration_s` | no | Video duration in seconds. |
| `asset_type_raw` | no | Raw asset type, used to derive Brand vs Creator. |
| `os_target` | no | OS split, such as `iOS`, `Android`, `Desktop`, or `All`. |
| `audience_segment` | no | Audience or targeting segment. |
| `concept` | no | Creative concept rollup label. If missing, concept tools fall back to `creative_name`. |
| `product` | no | Product label for enrichment/filtering. |
| `wave` | no | Campaign wave label for enrichment/filtering. |
| `performance_score` | no | Workbook-provided score or performance index, such as `Creative Efficiency Index`; preserved separately from Scout `composite_score`. |

Required fields are minimal so WPP Scout can ingest a wide range of exports. Better optional metric coverage produces better scoring and explanations.

## MCP Tool Catalog

All tools return text content. Most structured tools return JSON as the text body.

| Tool | Main Inputs | Purpose |
|---|---|---|
| `recommend_upload_plan` | `file_name`, `size_bytes` | Recommends chunk size/count and upload workflow for remote agents. |
| `create_file_upload_session` | `file_name`, optional `expected_size_bytes`, `expected_chunks`, `mime_type` | Starts a remote upload session. |
| `append_file_upload_chunk` | `upload_id`, `chunk_data_base64`, optional `chunk_index` | Appends a padding-safe base64 chunk with idempotent retry semantics. |
| `get_file_upload_status` | `upload_id` | Reports upload progress and readiness. |
| `finalize_file_upload` | `upload_id` | Finalizes upload and returns an `upload_id` / `file_handle` for ingest. |
| `preview_data_mapping` | `upload_id` or small-file `file_data_base64`, optional `sheet_name`, `header_row`, `preserve_columns` | Preview how a CSV/Excel upload maps to the canonical schema. Returns `mapping_id`, `proposed_mapping`, diagnostics, missing fields, ignored columns, preserved metadata, warnings, and sample normalized rows. |
| `ingest_data` | `upload_id` or small-file `file_data_base64`, optional `min_spend`, `min_reach`, `mapping_id`, `column_mapping`, `session_id`, `preserve_columns` | Load, normalize, aggregate, score, explain, and store an analysis session. Returns `session_id` and analyzed creative count. |
| `analyze_creatives` | same file inputs as `ingest_data` | Legacy alias for `ingest_data`. |
| `describe_session` | optional `session_id` | Session row counts, available metrics/groupings, distributions, mapping context, and warnings. |
| `rank_creatives` | optional `session_id`, `metric`, `group_by`, `top_n`, `bottom_n`, `min_spend` | Rank creatives or grouped cohorts by any numeric metric, including `spend`. |
| `get_top_performers` | optional `session_id`, `limit`, `platform`, `objective` | Top high-confidence creative rows by composite score. |
| `get_bottom_performers` | optional `session_id`, `limit`, `platform` | Lowest high-confidence creative rows by composite score. |
| `get_top_concepts` | optional `session_id`, `limit`, `platform`, `objective`, `include_low_confidence` | Top concept-level rollups across creative/placement rows. |
| `get_bottom_concepts` | optional `session_id`, `limit`, `platform`, `objective`, `include_low_confidence` | Weakest concept-level rollups. |
| `get_concept_deep_dive` | `concept`, optional `session_id`, `include_low_confidence` | Explains a concept at rollup, creative-row, and placement levels. Use this to separate idea performance from placement execution. |
| `get_creative_deep_dive` | `creative_name` | Detailed view of one creative row plus raw split rows. |
| `summarize_campaign_trends` | optional `session_id` | Plain-English dimension trends, such as OS/platform and Creator/Brand patterns. |
| `get_action_plan` | optional `session_id` | Top scale-up and pause candidates. |
| `explain_scoring_methodology` | `objective` | Objective-specific scoring method explanation. |
| `compare_dimensions` | `dimension` | Compares `os_target`, `asset_type_canonical`, `platform`, or `format_canonical`. |
| `get_objective_format_matrix` | optional `session_id` | Average score matrix by objective and format. |
| `search_by_objective` | `objective` | Ranks creatives for a chosen business objective. |
| `get_data_quality_report` | optional `session_id` | Counts rows, platforms, objectives, missing columns, low-confidence creatives, and zero-heavy columns. |
| `get_score_breakdown` | `creative_name`, optional `session_id` | Score components and recommendation context for one creative. |
| `get_low_confidence_creatives` | optional `session_id`, `limit` | Rows below spend/reach confidence thresholds. |
| `get_fatigue_risks` | optional `session_id`, `limit` | Rows with high frequency, sorted by frequency and spend. |
| `compare_creatives` | `creative_names`, optional `session_id` | Compares named creatives and identifies the strongest score. |
| `get_budget_reallocation_recommendations` | optional `session_id`, `limit` | Structured `scale_to` and `scale_from` candidates. |
| `find_actionable_insights` | optional `session_id` | Priority actions combining budget, fatigue, low-confidence, and data-quality signals. |

### Example MCP Flow

For a native Pixel workbook:

```json
{
  "tool": "ingest_data",
  "arguments": {
    "file_data_base64": "<base64 workbook>",
    "file_name": "pixel_de.xlsx",
    "min_spend": 500,
    "min_reach": 10000
  }
}
```

Then:

```json
{
  "tool": "get_top_concepts",
  "arguments": {
    "session_id": "<session_id from ingest_data>",
    "platform": "All",
    "limit": 10
  }
}
```

For a non-standard export:

```json
{
  "tool": "preview_data_mapping",
  "arguments": {
    "file_data_base64": "<base64 csv or workbook>",
    "file_name": "platform_export.csv"
  }
}
```

If the preview is acceptable:

```json
{
  "tool": "ingest_data",
  "arguments": {
    "file_data_base64": "<same base64 data>",
    "file_name": "platform_export.csv",
    "mapping_id": "<mapping_id from preview_data_mapping>"
  }
}
```

If the user corrects columns:

```json
{
  "tool": "ingest_data",
  "arguments": {
    "file_data_base64": "<same base64 data>",
    "file_name": "platform_export.csv",
    "column_mapping": {
      "Creative Concept": "creative_name",
      "Network": "platform",
      "Campaign Objective": "objective",
      "Cost": "spend",
      "Imps": "impressions",
      "Unique Reach": "reach",
      "Clicks": "clicks",
      "3s Video Views": "vtr_2s",
      "100% Video Views": "video_views_100"
    }
  }
}
```

## Scoring Algorithm

### Processing Pipeline

1. Load standard Pixel sheets or mapped CSV/Excel data.
2. Normalize platform, objective, format, placement, OS, asset type, and campaign labels.
3. Compute raw row metrics: completion rate, CTR, engagement rate, canonical attention inputs.
4. Aggregate raw ad lines to creative rows by `creative_name + platform + objective + buying_type + format_canonical`.
5. Recompute aggregate metrics: CTR, engagement rate, share rate, completion rate, cost per complete view, reach per spend, and CPM.
6. Add duration-adjusted completion and audience-consistency adjustment.
7. Mark low-confidence rows using spend/reach thresholds.
8. Score within cohort using objective-specific metrics.
9. Apply frequency penalty, audience-consistency adjustment, and low-confidence cap.
10. Assign tier, action, explanation, and expose insights through MCP tools.

### Scoring Cohorts

Scores are percentile-based within cohorts. A cohort is defined by:

```text
objective + platform + buying_type + format_canonical
```

This means:

- Paid and Boosting are scored separately.
- Static and video/motion formats are scored separately when relevant.
- A Meta Awareness static row should not be directly compared to a TikTok Video Views row as if the score means the same absolute thing.
- Use scores for ranking within the right context, then use spend, reach, frequency, and business judgment for final action.

### Weights

When attention proxy inputs are available:

| Component | Weight | Description |
|---|---:|---|
| Primary KPI | 50% | Objective-aligned main metric. |
| Secondary KPIs | 25% | Supporting quality/response metrics. |
| Cost efficiency | 15% | Lower-cost delivery of the objective. |
| Attention proxy | 10% | Native hook, hold, and completion signals where available. |

When no attention proxy inputs are available, the 10% attention component is removed and the other weights are renormalized:

| Component | Renormalized Weight |
|---|---:|
| Primary KPI | 55.6% |
| Secondary KPIs | 27.8% |
| Cost efficiency | 16.7% |
| Attention proxy | 0% |

### Objective Metrics

| Objective | Primary | Secondary | Efficiency |
|---|---|---|---|
| `Video Views` | `vtr_2s` | `completion_vs_expected`, `ctr`, `share_rate` | `cost_per_complete_view` lower is better |
| `Awareness` | `vtr_2s` | `completion_vs_expected`, `reach_per_pound` | `cpm` lower is better |
| `Reach` | `reach_per_pound` | `vtr_2s`, `frequency` | `cpm` lower is better |
| `Engagement` | `engagement_rate` | `share_rate`, `ctr`, `completion_vs_expected` | `cpm` lower is better |
| `Traffic` | `ctr` | `engagement_rate`, `completion_vs_expected` | `cpm` lower is better |
| `Sales` | `ctr` | `completion_vs_expected`, `engagement_rate` | `cpm` lower is better |
| `Target Frequency` | `completion_vs_expected` | `vtr_2s`, `engagement_rate` | `cpm` lower is better |

Static assets use static-specific metrics because VTR and completion are not meaningful:

| Static Objective | Primary | Secondary | Efficiency |
|---|---|---|---|
| `Awareness` | `engagement_rate` | `ctr`, `reach_per_pound` | `cpm` lower is better |
| `Reach` | `reach_per_pound` | `engagement_rate`, `ctr` | `cpm` lower is better |
| `Engagement` | `engagement_rate` | `share_rate`, `ctr` | `cpm` lower is better |
| `Traffic` | `ctr` | `engagement_rate`, `share_rate` | `cpm` lower is better |
| `Sales` | `ctr` | `engagement_rate`, `share_rate` | `cpm` lower is better |
| `Video Views` | `engagement_rate`, `ctr` | `share_rate` | `cpm` lower is better |
| `Target Frequency` | `engagement_rate` | `ctr`, `share_rate` | `cpm` lower is better |

### Derived Metrics

| Metric | Formula |
|---|---|
| `completion_rate` | `video_views_100 / impressions * 100` |
| `ctr` | `clicks / impressions * 100` |
| `engagement_rate` | `engagements / impressions * 100` |
| `share_rate` | `shares / impressions * 100` |
| `cost_per_complete_view` | `spend / video_views_100` |
| `reach_per_pound` | `reach / spend` |
| `cpm` | `spend / impressions * 1000` |
| `frequency` | `impressions / reach` where available/recomputed |

`completion_vs_expected` adjusts completion rate by video duration. Expected completion baselines:

| Duration | Expected Completion Rate |
|---|---:|
| `<= 15s` | 3.5% |
| `16-30s` | 2.4% |
| `31-60s` | 0.9% |
| `> 60s` | 0.5% |
| missing/zero duration | 1.0% |

### Frequency Penalty

Frequency is penalized after the weighted score is calculated:

```text
if frequency <= 2.0:
  penalty = 1.0
else:
  penalty = 1 / (1 + (frequency - 2.0) * 0.15)

composite_score = composite_raw * penalty
```

This is intentionally gradual. It does not automatically kill high-frequency creatives, but it reduces scores where overexposure is likely.

### Audience Consistency

If a creative has multiple campaigns/audience splits, WPP Scout estimates consistency using the coefficient of variation across the relevant metric:

- Static assets use engagement rate.
- Video/motion assets use VTR.

More consistent creatives keep more of their score. Volatile creatives are moderated toward their cohort average.

### Low Confidence

A creative row is low confidence if:

```text
spend < min_spend OR reach < min_reach
```

Defaults:

```text
min_spend = 500
min_reach = 10000
```

Low-confidence rows are capped at a score of 80 and are excluded from top/bottom performer lists unless a concept tool is explicitly asked to include them.

### Tiers

| Score | Tier |
|---:|---|
| `85-100` | Top Performer |
| `70-84.9` | Strong |
| `50-69.9` | Average |
| `25-49.9` | Below Average |
| `<25` | Poor |

### Action Labels

Actions are derived from score, frequency, low-confidence state, and spend:

| Condition | Action |
|---|---|
| Score `>= 70`, high confidence, frequency `<= 3.5` | `Scale Up` |
| Score `>= 70`, low confidence | `Keep Running - Low Data` |
| Score `>= 70`, frequency `> 3.5` | `Keep Running - Refresh Creative` |
| Score `50-69.9`, high confidence, frequency `<= 3.5` | `Keep running` |
| Score `50-69.9`, low confidence | `Monitor - Low Data` |
| Score `50-69.9`, frequency `> 3.5` | `Optimise - Frequency Too High` |
| Score `25-49.9`, frequency `> 3.5` | `Consider Pausing - Fatigued` |
| Score `25-49.9`, spend `> 5000` | `Consider Pausing - Budget Wasted` |
| Score `25-49.9`, otherwise | `Review` |
| Score `< 25`, spend `> 2000` | `Pause - Wasting Budget` |
| Score `< 25`, otherwise | `Pause` |

## Concept-Level Versus Placement-Level Analysis

WPP Scout intentionally supports both levels because they answer different questions.

| Level | What It Answers | Relevant Tools |
|---|---|---|
| Placement-level creative row | Where did this specific execution work or fail? | `get_top_performers`, `get_bottom_performers`, `get_creative_deep_dive`, `get_score_breakdown` |
| Concept-level rollup | Is the underlying idea strong across placements/platforms/objectives? | `get_top_concepts`, `get_bottom_concepts`, `get_concept_deep_dive` |

The same concept can have a strong placement and a weak overall rollup. For example, a TikTok In Feed row can score very highly while the same concept performs poorly in TopView or Stories. Agents should avoid saying "the creative works" or "the creative fails" without specifying the level.

Recommended agent language:

```text
At placement level, this execution is strong in TikTok In Feed. At concept level, performance is mixed because TopView and Stories rows dilute the rollup. The recommendation is to scale the winning placement, not the entire concept indiscriminately.
```

## AI Mapping Layer

The mapping layer exists so agents can ingest unfamiliar platform exports without hand-building a parser for every source.

Flow:

1. Candidate sheets are selected from the uploaded workbook or CSV.
2. The first five rows and source column names are sent to `generate_column_mapping()`.
3. Gemini returns a JSON mapping from source columns to canonical fields.
4. The mapping is filtered to valid target fields and unique targets.
5. `create_mapping_preview()` returns an auditable preview.
6. `ingest_data()` normalizes the mapped data and scores it.

Important behavior:

- Gemini is called with `temperature=0.0` and `response_mime_type="application/json"`.
- If Gemini or ADC fails, WPP Scout falls back to heuristic matching.
- The preview may return `ready_to_ingest=false` if required fields are missing or ambiguous.
- Explicit `column_mapping` always overrides AI/heuristic mapping and is preferred when a user corrects the mapping.

Known local caveat:

```text
If Google ADC is not configured locally, preview_data_mapping still runs but uses heuristic fallback. This is enough for simple smoke tests, but it does not fully validate the AI mapping path.
```

## Data Quality And Operational Caveats

- Scores are cohort-relative, not absolute truth.
- Paid and Boosting scores should not be compared directly.
- Static and video scores use different metric sets.
- Low-confidence rows can be promising but should not drive large budget moves until validated.
- `Unknown` format or placement values should be monitored; too many unknowns usually means the source mapping needs improvement.
- The MCP in-memory session state is fine for local/dev use. For production Cloud Run, use an external store if sessions need to survive restarts or scale across instances.
- The current service does not perform media/asset visual analysis. It only analyzes structured performance metrics and mapped metadata.
- The current service does not authenticate MCP requests. Add auth before exposing publicly.

## Handover Checklist

Before handing WPP Scout to another engineer or deploying it:

1. Run `python3 -m pytest api/tests tests -q`.
2. Run `python3 test_mcp_flow.py`.
3. Confirm `README.md` matches the current MCP tool list.
4. Configure `GOOGLE_CLOUD_PROJECT` and ADC/service-account access if AI mapping is required.
5. Decide whether production sessions need Redis, Cloud Storage, Firestore, or another shared session store.
6. Add auth at the MCP/API boundary before public exposure.
7. Smoke test a native Pixel workbook and a non-standard mapped CSV.

## Recent Verification

On 2026-04-27, all 22 MCP tools were smoke-tested against the provided Pixel DE workbook:

- 22/22 tools listed and called.
- 0 missing tools.
- 0 failed tools.
- `ingest_data` and `analyze_creatives` each scored 529 creatives.
- Native workbook ingest succeeded.
- Local AI mapping could not be fully validated because Google ADC was unavailable; mapping preview fell back to heuristics.
