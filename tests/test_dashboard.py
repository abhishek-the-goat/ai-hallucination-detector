"""
tests/test_dashboard.py
-----------------------
Unit and integration tests for the dashboard Flask app and SQLite persistence.
"""

import pytest
import json
from dashboard.app import app, get_db, save_check


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with app.app_context():
            get_db()
        yield client


def test_index_route(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Hallucination" in html
    assert "Paste AI Answer" in html


def test_history_route_empty_or_existing(client):
    response = client.get("/history")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Verification History" in html


def test_save_and_retrieve_history(client):
    with app.app_context():
        report_data = {
            "verdicts": [
                {
                    "claim_id": "1",
                    "label": "SUPPORTED",
                    "confidence": 0.95,
                    "evidence": [{"source_title": "Test Source", "score": 0.88, "text": "Sample text", "source_url": ""}]
                },
                {
                    "claim_id": "2",
                    "label": "CONTRADICTED",
                    "confidence": 0.82,
                    "evidence": []
                }
            ],
            "hallucination_score": 50.0
        }
        check_id = save_check("Photosynthesis occurs in plants and algae. DNA carries genetic instructions.", report_data)
        assert check_id > 0

    # Retrieve history
    response = client.get("/history")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "50%" in html

    # Retrieve history detail
    detail = client.get(f"/history/{check_id}")
    assert detail.status_code == 200
    detail_html = detail.get_data(as_text=True)
    assert "SUPPORTED" in detail_html
    assert "CONTRADICTED" in detail_html


def test_empty_check_shows_paste_an_answer_first(client):
    response = client.post("/check", data={"answer_text": "   "})
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "paste an answer first" in html
