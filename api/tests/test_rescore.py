import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def uploaded_data(client, sample_sheets_json):
    """Upload JSON sheet data and return the response data."""
    response = client.post(
        "/api/upload-and-score",
        json={"sheets": sample_sheets_json},
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
