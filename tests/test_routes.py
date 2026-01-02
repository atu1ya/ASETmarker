"""Route integration tests."""
import io
import json
import zipfile


def test_dashboard_requires_auth(client):
    response = client.get("/")
    assert response.status_code == 401


def test_dashboard_authenticated(authenticated_client):
    response = authenticated_client.get("/")
    assert response.status_code == 200
    assert b"Dashboard" in response.content


def test_configure_route(authenticated_client):
    reading = io.BytesIO(b"A\nB\n")
    qrar = io.BytesIO(b"A\nB\n")
    concept = io.BytesIO(
        json.dumps(
            {
                "Reading": {"Area": ["q1", "q2"]},
                "Quantitative Reasoning": {"Area": ["qr1", "qr2"]},
                "Abstract Reasoning": {"Area": ["ar1", "ar2"]},
            }
        ).encode("utf-8")
    )

    files = {
        "reading_answers": ("reading.txt", reading, "text/plain"),
        "qrar_answers": ("qrar.txt", qrar, "text/plain"),
        "concept_mapping": ("concept.json", concept, "application/json"),
    }

    response = authenticated_client.post("/configure", files=files)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["summary"]["configured"] is True


def test_single_marking_process(configured_client, sample_png_bytes):
    files = {
        "reading_sheet": ("reading.png", io.BytesIO(sample_png_bytes), "image/png"),
        "qrar_sheet": ("qrar.png", io.BytesIO(sample_png_bytes), "image/png"),
    }
    data = {"student_name": "Test Student", "writing_score": "88"}

    response = configured_client.post("/mark/single/process", data=data, files=files)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"


def test_batch_process(configured_client, sample_png_bytes):
    manifest = {
        "students": [
            {
                "name": "Student One",
                "writing_score": 80,
                "reading_file": "one_reading.png",
                "qrar_file": "one_qrar.png",
            }
        ]
    }
    manifest_file = io.BytesIO(json.dumps(manifest).encode("utf-8"))

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("one_reading.png", sample_png_bytes)
        zf.writestr("one_qrar.png", sample_png_bytes)
    zip_buffer.seek(0)

    manifest_file.seek(0)
    zip_buffer.seek(0)

    files = {
        "manifest": ("manifest.json", manifest_file, "application/json"),
        "sheets_zip": ("sheets.zip", io.BytesIO(zip_buffer.read()), "application/zip"),
    }

    response = configured_client.post("/batch/process", files=files)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
