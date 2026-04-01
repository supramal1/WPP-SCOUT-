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
