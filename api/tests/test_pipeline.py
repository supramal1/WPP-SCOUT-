import pandas as pd
from scoring.pipeline import process_upload, process_rescore


def test_process_upload_returns_expected_shape(sample_excel_path):
    result = process_upload(sample_excel_path)
    assert "upload_id" in result
    assert "creatives" in result
    assert "filters" in result
    assert "meta" in result
    assert len(result["creatives"]) > 0
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
    rescore_result = process_rescore(upload_id, {"platform": "Meta"})
    assert rescore_result is not None
    assert len(rescore_result["creatives"]) > 0
    for c in rescore_result["creatives"]:
        assert c["platform"] == "Meta"


def test_process_rescore_missing_upload_returns_none():
    result = process_rescore("nonexistent", {})
    assert result is None
