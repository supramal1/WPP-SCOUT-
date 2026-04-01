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
            files={
                "file": (
                    "test.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
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
            files={
                "file": (
                    "empty.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert response.status_code == 400
    assert response.json()["detail"]["error"] in ("no_sheets", "empty_data")
