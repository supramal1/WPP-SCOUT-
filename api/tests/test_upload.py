import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_upload_valid_json(client, sample_sheets_json):
    response = client.post(
        "/api/upload-and-score",
        json={"sheets": sample_sheets_json},
    )
    assert response.status_code == 200
    data = response.json()
    assert "upload_id" in data
    assert len(data["creatives"]) > 0
    assert "filters" in data
    assert "meta" in data


def test_upload_empty_sheets(client):
    response = client.post(
        "/api/upload-and-score",
        json={"sheets": {}},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "no_sheets"


def test_upload_no_matching_sheets(client):
    response = client.post(
        "/api/upload-and-score",
        json={"sheets": {"Random Sheet": [["a", "b"], [1, 2]]}},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "no_sheets"
