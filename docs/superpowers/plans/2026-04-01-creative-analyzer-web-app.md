# Creative Analyzer Web App — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the creative analyzer from a Python CLI + Excel output to an interactive web dashboard with dynamic filtering, context-sensitive re-scoring, and concept-level aggregation.

**Architecture:** FastAPI backend (adapts existing Python scoring logic) + Next.js frontend (shadcn/ui, dark theme). Both deployed to Vercel. No auth, no database, upload-per-session with in-memory cache.

**Tech Stack:** Python 3.13, FastAPI, pandas, openpyxl, Pydantic | Next.js 16, TypeScript, shadcn/ui, Tailwind CSS, Geist fonts

**Spec:** `docs/superpowers/specs/2026-04-01-creative-analyzer-web-app-design.md`

---

## File Map

### Backend (`api/`)

| File | Responsibility |
|---|---|
| `api/main.py` | FastAPI app, CORS config, lifespan |
| `api/cache.py` | In-memory upload cache with TTL (1hr) |
| `api/models.py` | Pydantic request/response schemas |
| `api/routes/__init__.py` | Route registration |
| `api/routes/upload.py` | `POST /api/upload-and-score` endpoint |
| `api/routes/rescore.py` | `POST /api/rescore` endpoint |
| `api/scoring/__init__.py` | Package init |
| `api/scoring/loader.py` | Adapted from `src/loader.py` (unchanged logic) |
| `api/scoring/scorer.py` | Adapted from `src/scorer.py` (unchanged logic) |
| `api/scoring/explainer.py` | Adapted from `src/explainer.py` (unchanged logic) |
| `api/scoring/pipeline.py` | Orchestrates load -> score -> action -> serialize |
| `api/requirements.txt` | Backend dependencies |
| `api/tests/test_cache.py` | Cache unit tests |
| `api/tests/test_pipeline.py` | Pipeline integration tests |
| `api/tests/test_upload.py` | Upload endpoint tests |
| `api/tests/test_rescore.py` | Rescore endpoint tests |
| `api/tests/conftest.py` | Shared fixtures (test Excel file, FastAPI test client) |

### Frontend (`web/`)

| File | Responsibility |
|---|---|
| `web/app/layout.tsx` | Root layout, Geist fonts, dark theme |
| `web/app/page.tsx` | Single-page dashboard orchestrator |
| `web/components/upload-zone.tsx` | Drag-and-drop file upload |
| `web/components/filter-bar.tsx` | Dimension dropdowns + rescore button |
| `web/components/score-table.tsx` | Ranked creative table (Action view) |
| `web/components/concept-view.tsx` | Concept-level grouped table |
| `web/components/comparison-view.tsx` | Side-by-side dimension comparison |
| `web/components/tier-badge.tsx` | Colour-coded tier indicator |
| `web/components/stat-cards.tsx` | Summary stat cards |
| `web/lib/api.ts` | Fetch helpers for upload/rescore endpoints |
| `web/lib/filters.ts` | Client-side filter + concept aggregation logic |
| `web/lib/types.ts` | TypeScript types matching API response |
| `web/next.config.ts` | API rewrite rules |
| `web/package.json` | Frontend dependencies |

---

## Chunk 1: Backend Foundation

### Task 1: Scaffold API project and install dependencies

**Files:**
- Create: `api/requirements.txt`
- Create: `api/__init__.py`
- Create: `api/tests/__init__.py`

- [ ] **Step 1: Create api directory structure**

```bash
cd ~/Projects/creative-analyzer
mkdir -p api/routes api/scoring api/tests
touch api/__init__.py api/routes/__init__.py api/scoring/__init__.py api/tests/__init__.py
```

- [ ] **Step 2: Write requirements.txt**

Create `api/requirements.txt`:
```
fastapi>=0.115.0
uvicorn>=0.32.0
pandas>=2.2.0
openpyxl>=3.1.0
python-multipart>=0.0.18
pydantic>=2.10.0
pytest>=8.0.0
httpx>=0.28.0
```

- [ ] **Step 3: Create venv and install**

```bash
cd ~/Projects/creative-analyzer
python3 -m venv api/venv
source api/venv/bin/activate
pip install -r api/requirements.txt
```

- [ ] **Step 4: Verify imports work**

```bash
source api/venv/bin/activate
python -c "import fastapi, pandas, openpyxl, pydantic; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add api/requirements.txt api/__init__.py api/routes/__init__.py api/scoring/__init__.py api/tests/__init__.py
git commit -m "chore: scaffold API project structure and dependencies"
```

---

### Task 2: In-memory upload cache

**Files:**
- Create: `api/cache.py`
- Create: `api/tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_cache.py`:
```python
import time
import pandas as pd
from api.cache import UploadCache


def test_store_and_retrieve():
    cache = UploadCache(ttl_seconds=3600)
    df = pd.DataFrame({"a": [1, 2, 3]})
    uid = cache.store(df)
    assert uid is not None
    retrieved = cache.get(uid)
    assert retrieved is not None
    pd.testing.assert_frame_equal(retrieved, df)


def test_get_missing_returns_none():
    cache = UploadCache(ttl_seconds=3600)
    assert cache.get("nonexistent") is None


def test_expired_entry_returns_none():
    cache = UploadCache(ttl_seconds=0)  # instant expiry
    df = pd.DataFrame({"a": [1]})
    uid = cache.store(df)
    time.sleep(0.01)
    assert cache.get(uid) is None


def test_cleanup_removes_expired():
    cache = UploadCache(ttl_seconds=0)
    df = pd.DataFrame({"a": [1]})
    cache.store(df)
    cache.store(df)
    time.sleep(0.01)
    removed = cache.cleanup()
    assert removed >= 2
    assert len(cache._entries) == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/Projects/creative-analyzer
source api/venv/bin/activate
python -m pytest api/tests/test_cache.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'api.cache'`

- [ ] **Step 3: Write implementation**

Create `api/cache.py`:
```python
import time
import uuid
import threading
import pandas as pd


class UploadCache:
    """In-memory cache for uploaded DataFrames, keyed by upload ID with TTL."""

    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[float, pd.DataFrame]] = {}
        self._lock = threading.Lock()

    def store(self, df: pd.DataFrame) -> str:
        uid = uuid.uuid4().hex[:12]
        with self._lock:
            self._entries[uid] = (time.time(), df)
        return uid

    def get(self, upload_id: str) -> pd.DataFrame | None:
        with self._lock:
            entry = self._entries.get(upload_id)
            if entry is None:
                return None
            timestamp, df = entry
            if time.time() - timestamp > self.ttl_seconds:
                del self._entries[upload_id]
                return None
            return df

    def cleanup(self) -> int:
        now = time.time()
        removed = 0
        with self._lock:
            expired = [
                uid
                for uid, (ts, _) in self._entries.items()
                if now - ts > self.ttl_seconds
            ]
            for uid in expired:
                del self._entries[uid]
                removed += 1
        return removed
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/Projects/creative-analyzer
source api/venv/bin/activate
python -m pytest api/tests/test_cache.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add api/cache.py api/tests/test_cache.py
git commit -m "feat(api): add in-memory upload cache with TTL"
```

---

### Task 3: Pydantic models

**Files:**
- Create: `api/models.py`

- [ ] **Step 1: Write models**

Create `api/models.py`:
```python
from pydantic import BaseModel


class Creative(BaseModel):
    creative_name: str
    concept: str
    platform: str
    objective: str
    format: str
    placement: str
    os_target: str
    asset_type_canonical: str
    buying_type: str
    campaign_normalized: str
    composite_score: float
    tier: str
    action: str
    spend: float
    reach: float
    impressions: float
    vtr_2s: float
    completion_rate: float
    ctr: float
    engagement_rate: float
    share_rate: float
    cpm: float
    frequency: float
    cost_per_complete_view: float | None = None
    reach_per_pound: float | None = None
    completion_vs_expected: float | None = None
    scoring_group: str
    explanation: str
    low_confidence: bool


class FilterOptions(BaseModel):
    campaigns: list[str]
    platforms: list[str]
    os: list[str]
    placements: list[str]
    objectives: list[str]
    formats: list[str]
    asset_types: list[str]
    buying_types: list[str]
    concepts: list[str]


class UploadMeta(BaseModel):
    total_rows: int
    platforms_found: list[str]
    brand: str


class UploadResponse(BaseModel):
    upload_id: str
    creatives: list[Creative]
    filters: FilterOptions
    meta: UploadMeta


class RescoreRequest(BaseModel):
    upload_id: str
    filters: dict[str, str]


class RescoreResponse(BaseModel):
    creatives: list[Creative]
    filters: FilterOptions
    meta: UploadMeta


class ErrorResponse(BaseModel):
    error: str
    message: str
```

- [ ] **Step 2: Verify models parse correctly**

```bash
source api/venv/bin/activate
python -c "
from api.models import Creative, UploadResponse, RescoreRequest
c = Creative(creative_name='test', concept='test', platform='Meta', objective='Awareness',
    format='Video', placement='Feed', os_target='iOS', asset_type_canonical='Brand',
    buying_type='Paid', campaign_normalized='Test', composite_score=78.3, tier='Strong',
    action='Scale Up', spend=12500, reach=450000, impressions=890000, vtr_2s=34.2,
    completion_rate=2.1, ctr=0.45, engagement_rate=0.12, share_rate=0.03, cpm=14.04,
    frequency=1.98, scoring_group='Awareness | Meta | Paid', explanation='Good', low_confidence=False)
print('Creative OK')
r = RescoreRequest(upload_id='abc123', filters={'os': 'Android'})
print('RescoreRequest OK')
"
```
Expected: `Creative OK`, `RescoreRequest OK`

- [ ] **Step 3: Commit**

```bash
git add api/models.py
git commit -m "feat(api): add Pydantic request/response models"
```

---

### Task 4: Copy and adapt scoring modules

**Files:**
- Create: `api/scoring/loader.py` (copy from `src/loader.py`)
- Create: `api/scoring/scorer.py` (copy from `src/scorer.py`)
- Create: `api/scoring/explainer.py` (copy from `src/explainer.py`)

- [ ] **Step 1: Copy scoring modules**

```bash
cd ~/Projects/creative-analyzer
cp src/loader.py api/scoring/loader.py
cp src/scorer.py api/scoring/scorer.py
cp src/explainer.py api/scoring/explainer.py
```

- [ ] **Step 2: Verify imports work from api package**

```bash
source api/venv/bin/activate
python -c "
from api.scoring.loader import load_data
from api.scoring.scorer import score_raw_variants, assign_action
from api.scoring.explainer import generate_explanations
print('All imports OK')
"
```
Expected: `All imports OK`

- [ ] **Step 3: Commit**

```bash
git add api/scoring/loader.py api/scoring/scorer.py api/scoring/explainer.py
git commit -m "feat(api): copy scoring modules from src/ for web backend"
```

---

### Task 5: Scoring pipeline orchestrator

**Files:**
- Create: `api/scoring/pipeline.py`
- Create: `api/tests/test_pipeline.py`
- Create: `api/tests/conftest.py`

The pipeline orchestrates: load -> score -> assign_action -> extract filters -> serialize.

- [ ] **Step 1: Create test fixtures**

Create `api/tests/conftest.py`:
```python
import pytest
import pandas as pd
import openpyxl
from pathlib import Path
import tempfile


@pytest.fixture
def sample_excel_path():
    """Create a minimal Excel file matching the expected Pixel DE format."""
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    for sheet_name, platform, buying_type in [
        ("Data Analysis Paid Meta", "Meta", "Paid"),
        ("Data Analysis Paid TikTok", "TikTok", "Paid"),
    ]:
        ws = wb.create_sheet(sheet_name)
        # Header rows (rows 1-2 are metadata, row 3 is headers — header=2 in pandas)
        ws.append(["Report", "", ""])  # row 1
        ws.append(["Date range", "", ""])  # row 2
        headers = [
            "Creative Name", "Ad name in Platform", "Campaign", "Platform",
            "Objective", "Format", "Placement", "OS", "Targeting Segment",
            "Partner", "Concept", "Product", "Wave", "Duration",
            "Impressions", "Reach", "Frequency", "Spends", "CPM",
            "Clicks", "2s VTR" if platform == "TikTok" else "3s VTR",
            "Video Completion", "Shares", "Total Engagement", "Total Plays",
            "Consolidated_Asset_Key",
        ]
        ws.append(headers)  # row 3

        # Data rows
        rows = [
            [
                f"Creative_A_{platform}", f"Ad_A_{platform}_iOS_Feed", "Campaign Q2",
                platform, "Video Views", "Video", "Feed", "iOS", "Broad",
                "BAU", "Summer Launch", "Pixel 9", "Wave 1", "15",
                100000, 50000, 2.0, 5000, 50.0,
                500, 35.0, 2000, 100, 3000, 80000, f"key_a_{platform.lower()}_ios",
            ],
            [
                f"Creative_A_{platform}", f"Ad_A_{platform}_Android_Feed", "Campaign Q2",
                platform, "Video Views", "Video", "Feed", "Android", "Broad",
                "BAU", "Summer Launch", "Pixel 9", "Wave 1", "15",
                120000, 60000, 2.0, 6000, 50.0,
                600, 32.0, 1800, 120, 3500, 90000, f"key_a_{platform.lower()}_android",
            ],
            [
                f"Creative_B_{platform}", f"Ad_B_{platform}_iOS_Stories", "Campaign Q2",
                platform, "Awareness", "Video", "Stories", "iOS", "Interest",
                "Creator", "Creator Collab", "Pixel 9", "Wave 1", "30",
                80000, 40000, 2.0, 4000, 50.0,
                200, 28.0, 800, 50, 1500, 60000, f"key_b_{platform.lower()}_ios",
            ],
        ]
        for row in rows:
            ws.append(row)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        yield f.name

    Path(f.name).unlink(missing_ok=True)
```

- [ ] **Step 2: Write the failing test**

Create `api/tests/test_pipeline.py`:
```python
import pandas as pd
from api.scoring.pipeline import process_upload, process_rescore


def test_process_upload_returns_expected_shape(sample_excel_path):
    result = process_upload(sample_excel_path)
    assert "upload_id" in result
    assert "creatives" in result
    assert "filters" in result
    assert "meta" in result
    assert len(result["creatives"]) > 0
    # Check a creative has expected keys
    c = result["creatives"][0]
    assert "creative_name" in c
    assert "composite_score" in c
    assert "tier" in c
    assert "action" in c
    assert "concept" in c
    assert "scoring_group" in c


def test_process_upload_filters_populated(sample_excel_path):
    result = process_upload(sample_excel_path)
    f = result["filters"]
    assert "TikTok" in f["platforms"] or "Meta" in f["platforms"]
    assert len(f["os"]) > 0
    assert len(f["concepts"]) > 0


def test_process_upload_meta(sample_excel_path):
    result = process_upload(sample_excel_path)
    assert result["meta"]["total_rows"] > 0
    assert len(result["meta"]["platforms_found"]) > 0


def test_process_rescore_with_filter(sample_excel_path):
    upload_result = process_upload(sample_excel_path)
    upload_id = upload_result["upload_id"]
    # Rescore filtering to Meta only
    rescore_result = process_rescore(upload_id, {"platform": "Meta"})
    assert rescore_result is not None
    assert len(rescore_result["creatives"]) > 0
    # All results should be Meta
    for c in rescore_result["creatives"]:
        assert c["platform"] == "Meta"


def test_process_rescore_missing_upload_returns_none():
    result = process_rescore("nonexistent", {})
    assert result is None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
source api/venv/bin/activate
python -m pytest api/tests/test_pipeline.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'api.scoring.pipeline'`

- [ ] **Step 4: Write the pipeline**

Create `api/scoring/pipeline.py`:
```python
import pandas as pd
import numpy as np
from ..cache import UploadCache
from .loader import load_data
from .scorer import score_raw_variants, assign_action
from .explainer import generate_explanations

# Global cache instance
upload_cache = UploadCache(ttl_seconds=3600)

# Filter key -> DataFrame column mapping (from spec)
FILTER_COLUMN_MAP = {
    "campaign": "campaign_normalized",
    "platform": "platform",
    "os": "os_target",
    "placement": "placement",
    "objective": "objective",
    "format": "format_canonical",
    "asset_type": "asset_type_canonical",
    "buying_type": "buying_type",
    "concept": "concept",
}


def _safe_val(val):
    """Convert pandas/numpy values to JSON-safe Python types."""
    if val is None or (isinstance(val, float) and (pd.isna(val) or np.isinf(val))):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return round(float(val), 4)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val


def _df_to_creatives(df: pd.DataFrame) -> list[dict]:
    """Convert scored DataFrame to list of creative dicts for API response."""
    fields = [
        "creative_name", "concept", "platform", "objective", "format_canonical",
        "placement", "os_target", "asset_type_canonical", "buying_type",
        "campaign_normalized", "composite_score", "tier", "action",
        "spend", "reach", "impressions", "vtr_2s", "completion_rate",
        "ctr", "engagement_rate", "share_rate", "cpm", "frequency",
        "cost_per_complete_view", "reach_per_pound", "completion_vs_expected",
        "scoring_group", "explanation", "low_confidence",
    ]
    records = []
    for _, row in df.iterrows():
        record = {}
        for f in fields:
            val = row.get(f)
            # Rename format_canonical -> format in response
            key = "format" if f == "format_canonical" else f
            record[key] = _safe_val(val)
        records.append(record)
    return records


def _extract_filters(df: pd.DataFrame) -> dict:
    """Extract distinct filter values from DataFrame."""
    def _unique_sorted(col: str) -> list[str]:
        if col not in df.columns:
            return []
        vals = df[col].dropna().astype(str).unique()
        return sorted([v for v in vals if v.strip() and v != "nan"])

    return {
        "campaigns": _unique_sorted("campaign_normalized"),
        "platforms": _unique_sorted("platform"),
        "os": _unique_sorted("os_target"),
        "placements": _unique_sorted("placement"),
        "objectives": _unique_sorted("objective"),
        "formats": _unique_sorted("format_canonical"),
        "asset_types": _unique_sorted("asset_type_canonical"),
        "buying_types": _unique_sorted("buying_type"),
        "concepts": _unique_sorted("concept"),
    }


def _score_and_enrich(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Run scoring pipeline: score_raw_variants -> assign_action -> generate_explanations."""
    scored = score_raw_variants(df_raw)
    scored["action"] = scored.apply(assign_action, axis=1)
    scored = generate_explanations(scored)
    return scored


def _apply_filters(df: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    """Subset DataFrame by filter dict using the column mapping."""
    result = df.copy()
    for filter_key, filter_value in filters.items():
        col = FILTER_COLUMN_MAP.get(filter_key)
        if col and col in result.columns:
            result = result[result[col].astype(str) == str(filter_value)]
    return result


def process_upload(filepath: str) -> dict:
    """Full upload pipeline: load -> score -> cache -> serialize."""
    df_raw, _ = load_data(filepath)
    upload_id = upload_cache.store(df_raw)
    scored = _score_and_enrich(df_raw)
    creatives = _df_to_creatives(scored)
    filters = _extract_filters(df_raw)
    platforms_found = sorted(df_raw["platform"].dropna().unique().tolist())

    return {
        "upload_id": upload_id,
        "creatives": creatives,
        "filters": filters,
        "meta": {
            "total_rows": len(scored),
            "platforms_found": platforms_found,
            "brand": "",
        },
    }


def process_rescore(upload_id: str, filters: dict[str, str]) -> dict | None:
    """Rescore with filters: retrieve cached df_raw -> filter -> score -> serialize."""
    df_raw = upload_cache.get(upload_id)
    if df_raw is None:
        return None

    filtered = _apply_filters(df_raw, filters)
    if filtered.empty:
        return {
            "creatives": [],
            "filters": _extract_filters(filtered),
            "meta": {"total_rows": 0, "platforms_found": [], "brand": ""},
        }

    scored = _score_and_enrich(filtered)
    creatives = _df_to_creatives(scored)
    filter_options = _extract_filters(filtered)
    platforms_found = sorted(filtered["platform"].dropna().unique().tolist())

    return {
        "creatives": creatives,
        "filters": filter_options,
        "meta": {
            "total_rows": len(scored),
            "platforms_found": platforms_found,
            "brand": "",
        },
    }
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
source api/venv/bin/activate
python -m pytest api/tests/test_pipeline.py -v
```
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add api/scoring/pipeline.py api/tests/test_pipeline.py api/tests/conftest.py
git commit -m "feat(api): add scoring pipeline orchestrator with tests"
```

---

## Chunk 2: Backend API Routes

### Task 6: FastAPI app and upload endpoint

**Files:**
- Create: `api/main.py`
- Create: `api/routes/upload.py`
- Create: `api/tests/test_upload.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_upload.py`:
```python
import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_upload_valid_excel(client, sample_excel_path):
    with open(sample_excel_path, "rb") as f:
        response = client.post(
            "/api/upload-and-score",
            files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "upload_id" in data
    assert len(data["creatives"]) > 0
    assert "filters" in data
    assert "meta" in data


def test_upload_invalid_file_type(client, tmp_path):
    fake_file = tmp_path / "test.csv"
    fake_file.write_text("a,b,c\n1,2,3")
    with open(fake_file, "rb") as f:
        response = client.post(
            "/api/upload-and-score",
            files={"file": ("test.csv", f, "text/csv")},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_file"


def test_upload_empty_excel(client, tmp_path):
    import openpyxl
    wb = openpyxl.Workbook()
    path = tmp_path / "empty.xlsx"
    wb.save(str(path))
    with open(path, "rb") as f:
        response = client.post(
            "/api/upload-and-score",
            files={"file": ("empty.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] in ("no_sheets", "empty_data")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source api/venv/bin/activate
python -m pytest api/tests/test_upload.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 3: Write FastAPI app**

Create `api/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routes.upload import router as upload_router
from .routes.rescore import router as rescore_router

app = FastAPI(title="Creative Analyzer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router, prefix="/api")
app.include_router(rescore_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Write upload route**

Create `api/routes/upload.py`:
```python
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..scoring.pipeline import process_upload

router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}


@router.post("/upload-and-score")
async def upload_and_score(file: UploadFile = File(...)):
    # Validate file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_file", "message": "Please upload an Excel file (.xlsx)"},
        )

    # Save to temp file and process
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = process_upload(tmp_path)
        return result
    except KeyError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_columns", "message": f"Required columns missing: {e}"},
        )
    except ValueError as e:
        error_msg = str(e)
        if "No matching sheets" in error_msg:
            raise HTTPException(
                status_code=400,
                detail={"error": "no_sheets", "message": error_msg},
            )
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_data", "message": error_msg},
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)
```

- [ ] **Step 5: Create stub rescore route** (needed for app import)

Create `api/routes/rescore.py`:
```python
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
source api/venv/bin/activate
python -m pytest api/tests/test_upload.py -v
```
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add api/main.py api/routes/upload.py api/routes/rescore.py api/tests/test_upload.py
git commit -m "feat(api): add FastAPI app with upload-and-score endpoint"
```

---

### Task 7: Rescore endpoint

**Files:**
- Modify: `api/routes/rescore.py`
- Create: `api/tests/test_rescore.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_rescore.py`:
```python
import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def uploaded_data(client, sample_excel_path):
    """Upload a file and return the response data."""
    with open(sample_excel_path, "rb") as f:
        response = client.post(
            "/api/upload-and-score",
            files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    return response.json()


def test_rescore_with_platform_filter(client, uploaded_data):
    response = client.post(
        "/api/rescore",
        json={
            "upload_id": uploaded_data["upload_id"],
            "filters": {"platform": "Meta"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["creatives"]) > 0
    for c in data["creatives"]:
        assert c["platform"] == "Meta"


def test_rescore_with_os_filter(client, uploaded_data):
    response = client.post(
        "/api/rescore",
        json={
            "upload_id": uploaded_data["upload_id"],
            "filters": {"os": "iOS"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["creatives"]) > 0
    for c in data["creatives"]:
        assert c["os_target"] == "iOS"


def test_rescore_expired_upload(client):
    response = client.post(
        "/api/rescore",
        json={
            "upload_id": "nonexistent",
            "filters": {},
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "upload_expired"


def test_rescore_empty_filter_returns_all(client, uploaded_data):
    response = client.post(
        "/api/rescore",
        json={
            "upload_id": uploaded_data["upload_id"],
            "filters": {},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total_rows"] == uploaded_data["meta"]["total_rows"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source api/venv/bin/activate
python -m pytest api/tests/test_rescore.py -v
```
Expected: FAIL — `405 Method Not Allowed` (stub route has no POST handler)

- [ ] **Step 3: Write rescore route**

Replace `api/routes/rescore.py` with:
```python
from fastapi import APIRouter, HTTPException
from ..models import RescoreRequest
from ..scoring.pipeline import process_rescore

router = APIRouter()


@router.post("/rescore")
async def rescore(request: RescoreRequest):
    result = process_rescore(request.upload_id, request.filters)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "upload_expired",
                "message": "Session expired. Please re-upload your file.",
            },
        )
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source api/venv/bin/activate
python -m pytest api/tests/test_rescore.py -v
```
Expected: 4 passed

- [ ] **Step 5: Run full backend test suite**

```bash
source api/venv/bin/activate
python -m pytest api/tests/ -v
```
Expected: All tests pass (cache + pipeline + upload + rescore)

- [ ] **Step 6: Commit**

```bash
git add api/routes/rescore.py api/tests/test_rescore.py
git commit -m "feat(api): add rescore endpoint with filter-to-column mapping"
```

---

## Chunk 3: Frontend Foundation

### Task 8: Scaffold Next.js project with shadcn/ui

**Files:**
- Create: `web/` directory with Next.js project
- Modify: `web/app/layout.tsx` (dark theme, Geist fonts)

- [ ] **Step 1: Create Next.js project**

```bash
cd ~/Projects/creative-analyzer
npx create-next-app@latest web --typescript --tailwind --eslint --app --src-dir=false --import-alias="@/*" --turbopack
```

- [ ] **Step 2: Install shadcn/ui**

```bash
cd ~/Projects/creative-analyzer/web
npx shadcn@latest init -d
```

Select: New York style, Zinc base color, CSS variables.

- [ ] **Step 3: Install required shadcn components**

```bash
cd ~/Projects/creative-analyzer/web
npx shadcn@latest add table card badge select button tabs separator skeleton
```

- [ ] **Step 4: Configure dark theme in layout.tsx**

Replace `web/app/layout.tsx` with:
```tsx
import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";

export const metadata: Metadata = {
  title: "Creative Performance Analyzer",
  description: "Interactive creative scoring dashboard",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${GeistSans.variable} ${GeistMono.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Install Geist font package**

```bash
cd ~/Projects/creative-analyzer/web
npm install geist
```

- [ ] **Step 6: Verify build passes**

```bash
cd ~/Projects/creative-analyzer/web
npm run build
```
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
cd ~/Projects/creative-analyzer
git add web/
git commit -m "feat(web): scaffold Next.js project with shadcn/ui dark theme"
```

---

### Task 9: TypeScript types and API helpers

**Files:**
- Create: `web/lib/types.ts`
- Create: `web/lib/api.ts`

- [ ] **Step 1: Write types**

Create `web/lib/types.ts`:
```typescript
export interface Creative {
  creative_name: string;
  concept: string;
  platform: string;
  objective: string;
  format: string;
  placement: string;
  os_target: string;
  asset_type_canonical: string;
  buying_type: string;
  campaign_normalized: string;
  composite_score: number;
  tier: string;
  action: string;
  spend: number;
  reach: number;
  impressions: number;
  vtr_2s: number;
  completion_rate: number;
  ctr: number;
  engagement_rate: number;
  share_rate: number;
  cpm: number;
  frequency: number;
  cost_per_complete_view: number | null;
  reach_per_pound: number | null;
  completion_vs_expected: number | null;
  scoring_group: string;
  explanation: string;
  low_confidence: boolean;
}

export interface FilterOptions {
  campaigns: string[];
  platforms: string[];
  os: string[];
  placements: string[];
  objectives: string[];
  formats: string[];
  asset_types: string[];
  buying_types: string[];
  concepts: string[];
}

export interface UploadMeta {
  total_rows: number;
  platforms_found: string[];
  brand: string;
}

export interface UploadResponse {
  upload_id: string;
  creatives: Creative[];
  filters: FilterOptions;
  meta: UploadMeta;
}

export interface RescoreResponse {
  creatives: Creative[];
  filters: FilterOptions;
  meta: UploadMeta;
}

export interface ApiError {
  error: string;
  message: string;
}

export type ActiveFilters = Partial<Record<string, string>>;

export type GroupBy = "creative_name" | "concept";

export interface ConceptGroup {
  concept: string;
  composite_score: number;
  tier: string;
  n_variations: number;
  spend: number;
  reach: number;
  impressions: number;
  vtr_2s: number;
  ctr: number;
  engagement_rate: number;
  completion_rate: number;
  cpm: number;
  frequency: number;
  best_variation_score: number;
  worst_variation_score: number;
  creatives: Creative[];
}

export const TIER_COLORS: Record<string, string> = {
  "Top Performer": "#22c55e",
  Strong: "#3b82f6",
  Average: "#a1a1aa",
  "Below Average": "#f97316",
  Poor: "#ef4444",
};

export function getTier(score: number): string {
  if (score >= 85) return "Top Performer";
  if (score >= 70) return "Strong";
  if (score >= 50) return "Average";
  if (score >= 25) return "Below Average";
  return "Poor";
}
```

- [ ] **Step 2: Write API helpers**

Create `web/lib/api.ts`:
```typescript
import type { UploadResponse, RescoreResponse, ApiError, ActiveFilters } from "./types";

const API_BASE = "/api";

export async function uploadAndScore(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API_BASE}/upload-and-score`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const err: { detail: ApiError } = await res.json();
    throw new Error(err.detail?.message || "Upload failed");
  }

  return res.json();
}

export async function rescore(
  uploadId: string,
  filters: ActiveFilters
): Promise<RescoreResponse> {
  const res = await fetch(`${API_BASE}/rescore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ upload_id: uploadId, filters }),
  });

  if (!res.ok) {
    const err: { detail: ApiError } = await res.json();
    throw new Error(err.detail?.message || "Rescore failed");
  }

  return res.json();
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd ~/Projects/creative-analyzer/web
npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/creative-analyzer
git add web/lib/types.ts web/lib/api.ts
git commit -m "feat(web): add TypeScript types and API fetch helpers"
```

---

### Task 10: Client-side filter and concept aggregation logic

**Files:**
- Create: `web/lib/filters.ts`

- [ ] **Step 1: Write filter and aggregation logic**

Create `web/lib/filters.ts`:
```typescript
import type { Creative, ActiveFilters, ConceptGroup } from "./types";
import { getTier } from "./types";

const FILTER_TO_FIELD: Record<string, keyof Creative> = {
  campaign: "campaign_normalized",
  platform: "platform",
  os: "os_target",
  placement: "placement",
  objective: "objective",
  format: "format",
  asset_type: "asset_type_canonical",
  buying_type: "buying_type",
  concept: "concept",
};

export function applyFilters(
  creatives: Creative[],
  filters: ActiveFilters
): Creative[] {
  return creatives.filter((c) =>
    Object.entries(filters).every(([key, value]) => {
      if (!value || value === "All") return true;
      const field = FILTER_TO_FIELD[key];
      if (!field) return true;
      return String(c[field]) === value;
    })
  );
}

export function aggregateByConcept(creatives: Creative[]): ConceptGroup[] {
  const groups = new Map<string, Creative[]>();

  for (const c of creatives) {
    const key = c.concept || c.creative_name;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(c);
  }

  return Array.from(groups.entries())
    .map(([concept, items]) => {
      const totalSpend = items.reduce((s, c) => s + c.spend, 0);
      const totalImpressions = items.reduce((s, c) => s + c.impressions, 0);
      const totalReach = items.reduce((s, c) => s + c.reach, 0);
      const totalClicks = items.reduce((s, c) => s + c.ctr * c.impressions / 100, 0);
      const totalEngagements = items.reduce((s, c) => s + c.engagement_rate * c.impressions / 100, 0);
      const totalCompletions = items.reduce((s, c) => s + c.completion_rate * c.impressions / 100, 0);

      const weightedScore =
        totalSpend > 0
          ? items.reduce((s, c) => s + c.composite_score * c.spend, 0) / totalSpend
          : items.reduce((s, c) => s + c.composite_score, 0) / items.length;

      const weightedVtr =
        totalImpressions > 0
          ? items.reduce((s, c) => s + c.vtr_2s * c.impressions, 0) / totalImpressions
          : 0;

      return {
        concept,
        composite_score: Math.round(weightedScore * 10) / 10,
        tier: getTier(weightedScore),
        n_variations: items.length,
        spend: totalSpend,
        reach: totalReach,
        impressions: totalImpressions,
        vtr_2s: Math.round(weightedVtr * 10) / 10,
        ctr: totalImpressions > 0 ? Math.round((totalClicks / totalImpressions) * 100 * 1000) / 1000 : 0,
        engagement_rate: totalImpressions > 0 ? Math.round((totalEngagements / totalImpressions) * 100 * 1000) / 1000 : 0,
        completion_rate: totalImpressions > 0 ? Math.round((totalCompletions / totalImpressions) * 100 * 100) / 100 : 0,
        cpm: totalImpressions > 0 ? Math.round((totalSpend / totalImpressions) * 1000 * 100) / 100 : 0,
        frequency: totalReach > 0 ? Math.round((totalImpressions / totalReach) * 100) / 100 : 0,
        best_variation_score: Math.max(...items.map((c) => c.composite_score)),
        worst_variation_score: Math.min(...items.map((c) => c.composite_score)),
        creatives: items.sort((a, b) => b.composite_score - a.composite_score),
      };
    })
    .sort((a, b) => b.composite_score - a.composite_score);
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd ~/Projects/creative-analyzer/web
npx tsc --noEmit
```
Expected: No errors

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/creative-analyzer
git add web/lib/filters.ts
git commit -m "feat(web): add client-side filter and concept aggregation logic"
```

---

## Chunk 4: Frontend Dashboard Components

### Task 11: Tier badge component

**Files:**
- Create: `web/components/tier-badge.tsx`

- [ ] **Step 1: Write component**

Create `web/components/tier-badge.tsx`:
```tsx
import { Badge } from "@/components/ui/badge";
import { TIER_COLORS } from "@/lib/types";

export function TierBadge({ tier, score }: { tier: string; score: number }) {
  const color = TIER_COLORS[tier] || "#a1a1aa";
  return (
    <Badge
      variant="outline"
      className="font-mono text-xs"
      style={{ borderColor: color, color }}
    >
      {score.toFixed(1)}
    </Badge>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/components/tier-badge.tsx
git commit -m "feat(web): add tier badge component"
```

---

### Task 12: Stat cards component

**Files:**
- Create: `web/components/stat-cards.tsx`

- [ ] **Step 1: Write component**

Create `web/components/stat-cards.tsx`:
```tsx
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
```

- [ ] **Step 2: Commit**

```bash
git add web/components/stat-cards.tsx
git commit -m "feat(web): add stat cards component"
```

---

### Task 13: Upload zone component

**Files:**
- Create: `web/components/upload-zone.tsx`

- [ ] **Step 1: Write component**

Create `web/components/upload-zone.tsx`:
```tsx
"use client";

import { useCallback, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";

interface UploadZoneProps {
  onUpload: (file: File) => void;
  isLoading: boolean;
  loadingMessage?: string;
}

export function UploadZone({ onUpload, isLoading, loadingMessage }: UploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file && (file.name.endsWith(".xlsx") || file.name.endsWith(".xls"))) {
        onUpload(file);
      }
    },
    [onUpload]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) onUpload(file);
    },
    [onUpload]
  );

  if (isLoading) {
    return (
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="flex flex-col items-center justify-center py-16">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-200" />
          <p className="mt-4 text-sm text-zinc-400">{loadingMessage || "Processing..."}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className={`bg-zinc-900 border-2 border-dashed transition-colors cursor-pointer ${
        isDragging ? "border-zinc-400 bg-zinc-800" : "border-zinc-700 hover:border-zinc-500"
      }`}
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => document.getElementById("file-input")?.click()}
    >
      <CardContent className="flex flex-col items-center justify-center py-16">
        <p className="text-lg font-medium text-zinc-300">
          Drop your campaign Excel file here
        </p>
        <p className="mt-2 text-sm text-zinc-500">
          or click to browse (.xlsx)
        </p>
        <input
          id="file-input"
          type="file"
          accept=".xlsx,.xls"
          onChange={handleFileSelect}
          className="hidden"
        />
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/components/upload-zone.tsx
git commit -m "feat(web): add drag-and-drop upload zone component"
```

---

### Task 14: Filter bar component

**Files:**
- Create: `web/components/filter-bar.tsx`

- [ ] **Step 1: Write component**

Create `web/components/filter-bar.tsx`:
```tsx
"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { FilterOptions, ActiveFilters, GroupBy } from "@/lib/types";

interface FilterBarProps {
  filters: FilterOptions;
  activeFilters: ActiveFilters;
  onFilterChange: (key: string, value: string) => void;
  onRescore: () => void;
  isRescoring: boolean;
  groupBy: GroupBy;
  onGroupByChange: (g: GroupBy) => void;
}

const FILTER_DEFS: { key: string; label: string; optionsKey: keyof FilterOptions }[] = [
  { key: "campaign", label: "Campaign", optionsKey: "campaigns" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "os", label: "OS", optionsKey: "os" },
  { key: "placement", label: "Placement", optionsKey: "placements" },
  { key: "objective", label: "Objective", optionsKey: "objectives" },
  { key: "format", label: "Format", optionsKey: "formats" },
  { key: "asset_type", label: "Asset Type", optionsKey: "asset_types" },
  { key: "buying_type", label: "Buying Type", optionsKey: "buying_types" },
];

export function FilterBar({
  filters,
  activeFilters,
  onFilterChange,
  onRescore,
  isRescoring,
  groupBy,
  onGroupByChange,
}: FilterBarProps) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3 items-center">
        {FILTER_DEFS.map((def) => (
          <div key={def.key} className="flex flex-col gap-1">
            <label className="text-xs text-zinc-500 uppercase tracking-wider">
              {def.label}
            </label>
            <Select
              value={activeFilters[def.key] || "All"}
              onValueChange={(v) => onFilterChange(def.key, v)}
            >
              <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">All</SelectItem>
                {filters[def.optionsKey].map((opt) => (
                  <SelectItem key={opt} value={opt}>
                    {opt}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-4">
        <Button
          variant="outline"
          size="sm"
          onClick={onRescore}
          disabled={isRescoring}
          className="border-zinc-600"
        >
          {isRescoring ? (
            <>
              <span className="h-3 w-3 animate-spin rounded-full border border-zinc-400 border-t-transparent mr-2" />
              Re-scoring...
            </>
          ) : (
            "Re-score within filters"
          )}
        </Button>
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-xs text-zinc-500">Group by:</span>
          <Select
            value={groupBy}
            onValueChange={(v) => onGroupByChange(v as GroupBy)}
          >
            <SelectTrigger className="w-[160px] bg-zinc-900 border-zinc-700 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="creative_name">Creative Name</SelectItem>
              <SelectItem value="concept">Concept</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/components/filter-bar.tsx
git commit -m "feat(web): add filter bar with dimension dropdowns and rescore button"
```

---

### Task 15: Score table component (Action View)

**Files:**
- Create: `web/components/score-table.tsx`

- [ ] **Step 1: Write component**

Create `web/components/score-table.tsx`:
```tsx
"use client";

import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TierBadge } from "./tier-badge";
import type { Creative } from "@/lib/types";

interface ScoreTableProps {
  creatives: Creative[];
  isLoading?: boolean;
}

type SortKey = "composite_score" | "spend" | "vtr_2s" | "ctr" | "engagement_rate" | "completion_rate" | "cpm";

export function ScoreTable({ creatives, isLoading }: ScoreTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("composite_score");
  const [sortAsc, setSortAsc] = useState(false);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const sorted = [...creatives].sort((a, b) => {
    const av = a[sortKey] ?? 0;
    const bv = b[sortKey] ?? 0;
    return sortAsc ? av - bv : bv - av;
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(!sortAsc);
    else { setSortKey(key); setSortAsc(false); }
  };

  const sortIcon = (key: SortKey) =>
    sortKey === key ? (sortAsc ? " \u2191" : " \u2193") : "";

  return (
    <div className={`relative ${isLoading ? "opacity-50" : ""}`}>
      <Table>
        <TableHeader>
          <TableRow className="border-zinc-800 hover:bg-transparent">
            <TableHead className="text-zinc-500 w-12">#</TableHead>
            <TableHead className="text-zinc-500">Creative</TableHead>
            <TableHead className="text-zinc-500 cursor-pointer" onClick={() => handleSort("composite_score")}>
              Score{sortIcon("composite_score")}
            </TableHead>
            <TableHead className="text-zinc-500">Platform</TableHead>
            <TableHead className="text-zinc-500">Objective</TableHead>
            <TableHead className="text-zinc-500">Format</TableHead>
            <TableHead className="text-zinc-500 cursor-pointer font-mono" onClick={() => handleSort("vtr_2s")}>
              VTR{sortIcon("vtr_2s")}
            </TableHead>
            <TableHead className="text-zinc-500 cursor-pointer font-mono" onClick={() => handleSort("completion_rate")}>
              Comp%{sortIcon("completion_rate")}
            </TableHead>
            <TableHead className="text-zinc-500 cursor-pointer font-mono" onClick={() => handleSort("ctr")}>
              CTR{sortIcon("ctr")}
            </TableHead>
            <TableHead className="text-zinc-500 cursor-pointer font-mono" onClick={() => handleSort("spend")}>
              Spend{sortIcon("spend")}
            </TableHead>
            <TableHead className="text-zinc-500">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((c, i) => (
            <React.Fragment key={`${c.creative_name}-${c.os_target}-${c.placement}-${i}`}>
              <TableRow
                className="border-zinc-800 cursor-pointer hover:bg-zinc-900/50"
                onClick={() =>
                  setExpandedRow(
                    expandedRow === `${i}` ? null : `${i}`
                  )
                }
              >
                <TableCell className="font-mono text-zinc-500">{i + 1}</TableCell>
                <TableCell className="max-w-[280px] truncate font-medium">
                  {c.creative_name}
                </TableCell>
                <TableCell>
                  <TierBadge tier={c.tier} score={c.composite_score} />
                </TableCell>
                <TableCell className="text-sm">{c.platform}</TableCell>
                <TableCell className="text-sm">{c.objective}</TableCell>
                <TableCell className="text-sm">{c.format}</TableCell>
                <TableCell className="font-mono text-sm">{c.vtr_2s?.toFixed(1)}%</TableCell>
                <TableCell className="font-mono text-sm">{c.completion_rate?.toFixed(2)}%</TableCell>
                <TableCell className="font-mono text-sm">{c.ctr?.toFixed(3)}%</TableCell>
                <TableCell className="font-mono text-sm">
                  {"\u20AC"}{c.spend?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </TableCell>
                <TableCell className="text-sm text-zinc-400">{c.action}</TableCell>
              </TableRow>
              {expandedRow === `${i}` && (
                <TableRow key={`${i}-exp`} className="border-zinc-800 bg-zinc-900/30">
                  <TableCell colSpan={11} className="text-sm text-zinc-400 py-4 px-6">
                    <div className="space-y-1">
                      <p>{c.explanation}</p>
                      <p className="text-xs text-zinc-600 font-mono">
                        OS: {c.os_target} | Asset: {c.asset_type_canonical} | Group: {c.scoring_group}
                        {c.low_confidence && " | LOW CONFIDENCE"}
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 2: Verify build passes**

```bash
cd ~/Projects/creative-analyzer/web
npm run build
```
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
cd ~/Projects/creative-analyzer
git add web/components/score-table.tsx
git commit -m "feat(web): add sortable score table with expandable explanations"
```

---

### Task 16: Main dashboard page

**Files:**
- Modify: `web/app/page.tsx`
- Modify: `web/next.config.ts`

- [ ] **Step 1: Configure API rewrite in next.config.ts**

Replace `web/next.config.ts` with:
```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
```

- [ ] **Step 2: Write main dashboard page**

Replace `web/app/page.tsx` with:
```tsx
"use client";

import { useState, useCallback } from "react";
import { UploadZone } from "@/components/upload-zone";
import { FilterBar } from "@/components/filter-bar";
import { ScoreTable } from "@/components/score-table";
import { StatCards } from "@/components/stat-cards";
import { uploadAndScore, rescore } from "@/lib/api";
import { applyFilters } from "@/lib/filters";
import type {
  Creative,
  FilterOptions,
  UploadMeta,
  ActiveFilters,
  GroupBy,
} from "@/lib/types";

export default function Dashboard() {
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [allCreatives, setAllCreatives] = useState<Creative[]>([]);
  const [filters, setFilters] = useState<FilterOptions | null>(null);
  const [meta, setMeta] = useState<UploadMeta | null>(null);
  const [activeFilters, setActiveFilters] = useState<ActiveFilters>({});
  const [groupBy, setGroupBy] = useState<GroupBy>("creative_name");
  const [isUploading, setIsUploading] = useState(false);
  const [isRescoring, setIsRescoring] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleUpload = useCallback(async (file: File) => {
    setIsUploading(true);
    setLoadingMessage("Uploading and scoring...");
    setError(null);
    try {
      const result = await uploadAndScore(file);
      setUploadId(result.upload_id);
      setAllCreatives(result.creatives);
      setFilters(result.filters);
      setMeta(result.meta);
      setActiveFilters({});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleRescore = useCallback(async () => {
    if (!uploadId) return;
    // Strip "All" values from filters
    const cleanFilters = Object.fromEntries(
      Object.entries(activeFilters).filter(([, v]) => v && v !== "All")
    );
    if (Object.keys(cleanFilters).length === 0) return;

    setIsRescoring(true);
    try {
      const result = await rescore(uploadId, cleanFilters);
      setAllCreatives(result.creatives);
      setFilters(result.filters);
      setMeta(result.meta);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rescore failed");
    } finally {
      setIsRescoring(false);
    }
  }, [uploadId, activeFilters]);

  const handleFilterChange = useCallback((key: string, value: string) => {
    setActiveFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Client-side filter (instant, does not change scores)
  const displayedCreatives = filters
    ? applyFilters(allCreatives, activeFilters)
    : allCreatives;

  const hasData = allCreatives.length > 0 && filters && meta;

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100 p-6">
      <div className="max-w-[1400px] mx-auto space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Creative Performance Analyzer
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            Upload campaign data to score and rank creatives dynamically
          </p>
        </div>

        {!hasData && (
          <UploadZone
            onUpload={handleUpload}
            isLoading={isUploading}
            loadingMessage={loadingMessage}
          />
        )}

        {error && (
          <div className="rounded-md bg-red-950/50 border border-red-900 p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {hasData && (
          <>
            <StatCards creatives={displayedCreatives} totalCount={meta.total_rows} />

            <FilterBar
              filters={filters}
              activeFilters={activeFilters}
              onFilterChange={handleFilterChange}
              onRescore={handleRescore}
              isRescoring={isRescoring}
              groupBy={groupBy}
              onGroupByChange={setGroupBy}
            />

            {/* Task 17 replaces this with groupBy conditional */}
            <ScoreTable
              creatives={displayedCreatives}
              isLoading={isRescoring}
            />
          </>
        )}
      </div>
    </main>
  );
}
```

- [ ] **Step 3: Verify build passes**

```bash
cd ~/Projects/creative-analyzer/web
npm run build
```
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/creative-analyzer
git add web/app/page.tsx web/next.config.ts
git commit -m "feat(web): add main dashboard page with upload, filters, and score table"
```

---

## Chunk 5: Frontend Advanced Views

### Task 17: Concept view component

**Files:**
- Create: `web/components/concept-view.tsx`
- Modify: `web/app/page.tsx` (wire in concept toggle)

- [ ] **Step 1: Write concept view component**

Create `web/components/concept-view.tsx`:
```tsx
"use client";

import React, { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TierBadge } from "./tier-badge";
import type { ConceptGroup } from "@/lib/types";

interface ConceptViewProps {
  concepts: ConceptGroup[];
  isLoading?: boolean;
}

export function ConceptView({ concepts, isLoading }: ConceptViewProps) {
  const [expandedConcept, setExpandedConcept] = useState<string | null>(null);

  return (
    <div className={`relative ${isLoading ? "opacity-50" : ""}`}>
      <Table>
        <TableHeader>
          <TableRow className="border-zinc-800 hover:bg-transparent">
            <TableHead className="text-zinc-500 w-12">#</TableHead>
            <TableHead className="text-zinc-500">Concept</TableHead>
            <TableHead className="text-zinc-500">Score</TableHead>
            <TableHead className="text-zinc-500 font-mono">Variations</TableHead>
            <TableHead className="text-zinc-500 font-mono">Best</TableHead>
            <TableHead className="text-zinc-500 font-mono">Worst</TableHead>
            <TableHead className="text-zinc-500 font-mono">VTR</TableHead>
            <TableHead className="text-zinc-500 font-mono">CTR</TableHead>
            <TableHead className="text-zinc-500 font-mono">Spend</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {concepts.map((g, i) => (
            <React.Fragment key={g.concept}>
              <TableRow
                className="border-zinc-800 cursor-pointer hover:bg-zinc-900/50"
                onClick={() =>
                  setExpandedConcept(expandedConcept === g.concept ? null : g.concept)
                }
              >
                <TableCell className="font-mono text-zinc-500">{i + 1}</TableCell>
                <TableCell className="font-medium">{g.concept}</TableCell>
                <TableCell>
                  <TierBadge tier={g.tier} score={g.composite_score} />
                </TableCell>
                <TableCell className="font-mono text-sm">{g.n_variations}</TableCell>
                <TableCell className="font-mono text-sm text-green-400">
                  {g.best_variation_score.toFixed(1)}
                </TableCell>
                <TableCell className="font-mono text-sm text-red-400">
                  {g.worst_variation_score.toFixed(1)}
                </TableCell>
                <TableCell className="font-mono text-sm">{g.vtr_2s.toFixed(1)}%</TableCell>
                <TableCell className="font-mono text-sm">{g.ctr.toFixed(3)}%</TableCell>
                <TableCell className="font-mono text-sm">
                  {"\u20AC"}{g.spend.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </TableCell>
              </TableRow>
              {expandedConcept === g.concept &&
                g.creatives.map((c, j) => (
                  <TableRow
                    key={`${g.concept}-${j}`}
                    className="border-zinc-800/50 bg-zinc-900/20"
                  >
                    <TableCell />
                    <TableCell className="text-sm text-zinc-400 pl-8">
                      {c.creative_name}
                    </TableCell>
                    <TableCell>
                      <TierBadge tier={c.tier} score={c.composite_score} />
                    </TableCell>
                    <TableCell className="text-sm text-zinc-500">{c.platform}</TableCell>
                    <TableCell className="text-sm text-zinc-500">{c.os_target}</TableCell>
                    <TableCell className="text-sm text-zinc-500">{c.placement}</TableCell>
                    <TableCell className="font-mono text-sm text-zinc-400">
                      {c.vtr_2s?.toFixed(1)}%
                    </TableCell>
                    <TableCell className="font-mono text-sm text-zinc-400">
                      {c.ctr?.toFixed(3)}%
                    </TableCell>
                    <TableCell className="font-mono text-sm text-zinc-400">
                      {"\u20AC"}{c.spend?.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </TableCell>
                  </TableRow>
                ))}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
```

- [ ] **Step 2: Wire concept view into page.tsx**

In `web/app/page.tsx`, add the import at the top:
```tsx
import { ConceptView } from "@/components/concept-view";
import { aggregateByConcept } from "@/lib/filters";
```

Then replace the `<ScoreTable>` section with a conditional:
```tsx
{groupBy === "creative_name" ? (
  <ScoreTable creatives={displayedCreatives} isLoading={isRescoring} />
) : (
  <ConceptView
    concepts={aggregateByConcept(displayedCreatives)}
    isLoading={isRescoring}
  />
)}
```

- [ ] **Step 3: Verify build passes**

```bash
cd ~/Projects/creative-analyzer/web
npm run build
```
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/creative-analyzer
git add web/components/concept-view.tsx web/app/page.tsx
git commit -m "feat(web): add concept view with expandable grouped table"
```

---

### Task 18: Comparison view component

**Files:**
- Create: `web/components/comparison-view.tsx`
- Modify: `web/app/page.tsx` (add Comparison tab)

- [ ] **Step 1: Write comparison view component**

Create `web/components/comparison-view.tsx`:
```tsx
"use client";

import { useState, useCallback } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { TierBadge } from "./tier-badge";
import { rescore } from "@/lib/api";
import type { Creative, FilterOptions } from "@/lib/types";

interface ComparisonViewProps {
  uploadId: string;
  filters: FilterOptions;
}

const DIMENSION_OPTIONS: { key: string; label: string; optionsKey: keyof FilterOptions }[] = [
  { key: "os", label: "OS", optionsKey: "os" },
  { key: "platform", label: "Platform", optionsKey: "platforms" },
  { key: "asset_type", label: "Asset Type", optionsKey: "asset_types" },
  { key: "placement", label: "Placement", optionsKey: "placements" },
  { key: "buying_type", label: "Buying Type", optionsKey: "buying_types" },
];

interface ComparisonRow {
  creative_name: string;
  left_score: number | null;
  right_score: number | null;
  left_tier: string;
  right_tier: string;
  delta: number | null;
}

export function ComparisonView({ uploadId, filters }: ComparisonViewProps) {
  const [dimension, setDimension] = useState("os");
  const [leftValue, setLeftValue] = useState("");
  const [rightValue, setRightValue] = useState("");
  const [rows, setRows] = useState<ComparisonRow[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const currentDef = DIMENSION_OPTIONS.find((d) => d.key === dimension)!;
  const options = filters[currentDef.optionsKey];

  const handleCompare = useCallback(async () => {
    if (!leftValue || !rightValue) return;
    setIsLoading(true);
    try {
      const [leftRes, rightRes] = await Promise.all([
        rescore(uploadId, { [dimension]: leftValue }),
        rescore(uploadId, { [dimension]: rightValue }),
      ]);

      const leftMap = new Map(
        leftRes.creatives.map((c) => [c.creative_name, c])
      );
      const rightMap = new Map(
        rightRes.creatives.map((c) => [c.creative_name, c])
      );

      const allNames = new Set([...leftMap.keys(), ...rightMap.keys()]);
      const compared: ComparisonRow[] = Array.from(allNames)
        .map((name) => {
          const l = leftMap.get(name);
          const r = rightMap.get(name);
          return {
            creative_name: name,
            left_score: l?.composite_score ?? null,
            right_score: r?.composite_score ?? null,
            left_tier: l?.tier ?? "",
            right_tier: r?.tier ?? "",
            delta:
              l && r ? Math.round((l.composite_score - r.composite_score) * 10) / 10 : null,
          };
        })
        .sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0));

      setRows(compared);
    } catch {
      // Error handled silently — user sees empty table
    } finally {
      setIsLoading(false);
    }
  }, [uploadId, dimension, leftValue, rightValue]);

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Dimension</label>
          <Select value={dimension} onValueChange={setDimension}>
            <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DIMENSION_OPTIONS.map((d) => (
                <SelectItem key={d.key} value={d.key}>{d.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Left</label>
          <Select value={leftValue} onValueChange={setLeftValue}>
            <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {options.map((o) => (
                <SelectItem key={o} value={o}>{o}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-zinc-500 uppercase">Right</label>
          <Select value={rightValue} onValueChange={setRightValue}>
            <SelectTrigger className="w-[140px] bg-zinc-900 border-zinc-700">
              <SelectValue placeholder="Select..." />
            </SelectTrigger>
            <SelectContent>
              {options.map((o) => (
                <SelectItem key={o} value={o}>{o}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          onClick={handleCompare}
          disabled={!leftValue || !rightValue || isLoading}
          className="bg-zinc-800 hover:bg-zinc-700"
        >
          {isLoading ? "Comparing..." : "Compare"}
        </Button>
      </div>

      {rows.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-500">Creative</TableHead>
              <TableHead className="text-zinc-500">{leftValue} Score</TableHead>
              <TableHead className="text-zinc-500">{rightValue} Score</TableHead>
              <TableHead className="text-zinc-500">Delta</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={r.creative_name} className="border-zinc-800">
                <TableCell className="font-medium">{r.creative_name}</TableCell>
                <TableCell>
                  {r.left_score !== null ? (
                    <TierBadge tier={r.left_tier} score={r.left_score} />
                  ) : (
                    <span className="text-zinc-600">--</span>
                  )}
                </TableCell>
                <TableCell>
                  {r.right_score !== null ? (
                    <TierBadge tier={r.right_tier} score={r.right_score} />
                  ) : (
                    <span className="text-zinc-600">--</span>
                  )}
                </TableCell>
                <TableCell>
                  {r.delta !== null ? (
                    <span
                      className={`font-mono text-sm ${
                        Math.abs(r.delta) > 15
                          ? r.delta > 0
                            ? "text-green-400 font-bold"
                            : "text-red-400 font-bold"
                          : "text-zinc-400"
                      }`}
                    >
                      {r.delta > 0 ? "+" : ""}
                      {r.delta}
                    </span>
                  ) : (
                    <span className="text-zinc-600">--</span>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire comparison view into page.tsx with tabs**

In `web/app/page.tsx`, add imports:
```tsx
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ComparisonView } from "@/components/comparison-view";
```

Wrap the table/concept section in tabs:
```tsx
<Tabs defaultValue="rankings" className="space-y-4">
  <TabsList className="bg-zinc-900 border border-zinc-800">
    <TabsTrigger value="rankings">Rankings</TabsTrigger>
    <TabsTrigger value="compare">Compare</TabsTrigger>
  </TabsList>
  <TabsContent value="rankings">
    {groupBy === "creative_name" ? (
      <ScoreTable creatives={displayedCreatives} isLoading={isRescoring} />
    ) : (
      <ConceptView
        concepts={aggregateByConcept(displayedCreatives)}
        isLoading={isRescoring}
      />
    )}
  </TabsContent>
  <TabsContent value="compare">
    <ComparisonView uploadId={uploadId!} filters={filters} />
  </TabsContent>
</Tabs>
```

- [ ] **Step 3: Verify build passes**

```bash
cd ~/Projects/creative-analyzer/web
npm run build
```
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
cd ~/Projects/creative-analyzer
git add web/components/comparison-view.tsx web/app/page.tsx
git commit -m "feat(web): add comparison view with side-by-side dimension scoring"
```

---

## Chunk 6: Integration & Deployment

### Task 19: Local end-to-end test

**Files:** None new — verify the full stack works locally.

- [ ] **Step 1: Start the FastAPI backend**

```bash
cd ~/Projects/creative-analyzer
source api/venv/bin/activate
uvicorn api.main:app --reload --port 8000
```
Expected: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 2: Start the Next.js frontend** (in a second terminal)

```bash
cd ~/Projects/creative-analyzer/web
npm run dev
```
Expected: `Ready on http://localhost:3000`

- [ ] **Step 3: Manual smoke test**

1. Open `http://localhost:3000`
2. Upload a test Excel file
3. Verify: dashboard appears with stat cards, filter dropdowns, ranked table
4. Change a filter (e.g., Platform -> Meta) — table should filter instantly
5. Click "Re-score within filters" — table should update with new scores
6. Switch to Concept grouping — table should show grouped concepts
7. Switch to Compare tab, select OS dimension, iOS vs Android, click Compare

- [ ] **Step 4: Run full backend test suite one final time**

```bash
cd ~/Projects/creative-analyzer
source api/venv/bin/activate
python -m pytest api/tests/ -v
```
Expected: All tests pass

- [ ] **Step 5: Commit any fixes from smoke test**

```bash
git add -A
git commit -m "fix: address issues found during local end-to-end testing"
```

---

### Task 20: Vercel deployment configuration

**Files:**
- Create: `api/vercel.json` (Python function config)
- Create: `web/.env.example`

- [ ] **Step 1: Create API Vercel config**

Create `api/vercel.json`:
```json
{
  "builds": [
    {
      "src": "main.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "main.py"
    }
  ]
}
```

- [ ] **Step 2: Create web env example**

Create `web/.env.example`:
```
NEXT_PUBLIC_API_URL=https://your-api-project.vercel.app
```

- [ ] **Step 3: Add .gitignore entries**

Ensure these are in `.gitignore`:
```
api/venv/
web/node_modules/
web/.next/
.env*.local
```

- [ ] **Step 4: Commit**

```bash
git add api/vercel.json web/.env.example .gitignore
git commit -m "chore: add Vercel deployment config and env example"
```

- [ ] **Step 5: Notify user — ready for Vercel project creation and deploy**

The code is ready. User needs to:
1. Create two Vercel projects (one for `api/`, one for `web/`)
2. Set `NEXT_PUBLIC_API_URL` in the web project's env vars to point to the API project URL
3. Deploy both

---

## Summary

| Chunk | Tasks | What it delivers |
|---|---|---|
| 1: Backend Foundation | 1-5 | API scaffold, cache, models, scoring modules, pipeline |
| 2: Backend API Routes | 6-7 | Upload and rescore endpoints with full test coverage |
| 3: Frontend Foundation | 8-10 | Next.js + shadcn/ui scaffold, types, API helpers, filter logic |
| 4: Frontend Dashboard | 11-16 | Upload zone, filter bar, score table, stat cards, main page |
| 5: Frontend Advanced Views | 17-18 | Concept view with grouping, comparison view with parallel rescore |
| 6: Integration & Deployment | 19-20 | End-to-end test, Vercel config |

**Total: 20 tasks across 6 chunks.**
