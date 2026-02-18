"""
tests/test_advisor.py
=====================
Unit tests for the AI Readiness Advisor.
All tests run without a live Anthropic API key.

Run: pytest tests/ -v
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Ingestion tests
# ---------------------------------------------------------------------------

class TestIngestion:

    def test_extract_txt(self, tmp_path):
        from ingestion.pipeline import extract_txt
        f = tmp_path / "test.txt"
        f.write_text("Hello, this is a test document with important content.")
        doc = extract_txt(f)
        assert doc.filename == "test.txt"
        assert "Hello" in doc.content
        assert doc.file_type == "txt"
        assert doc.page_count >= 1

    def test_unsupported_file_type_raises(self, tmp_path):
        from ingestion.pipeline import extract_document
        f = tmp_path / "test.xlsx"
        f.write_bytes(b"fake content")
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_document(f)

    def test_chunker_splits_long_text(self):
        from ingestion.pipeline import chunk_text
        long_text = ("This is a sentence with many words. " * 50 + "\n\n") * 10
        chunks = chunk_text(long_text, chunk_size=500, chunk_overlap=50)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 600  # Allow some overflow for overlap

    def test_chunker_short_text_single_chunk(self):
        from ingestion.pipeline import chunk_text
        short = "This is a very short document."
        chunks = chunk_text(short, chunk_size=1000, chunk_overlap=100)
        assert len(chunks) == 1
        assert chunks[0] == short

    def test_chunker_preserves_content(self):
        from ingestion.pipeline import chunk_text
        text = "Alpha paragraph.\n\nBeta paragraph.\n\nGamma paragraph."
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)
        full = " ".join(chunks)
        assert "Alpha" in full
        assert "Beta" in full
        assert "Gamma" in full


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestModels:

    def test_get_maturity_nascent(self):
        from models import get_maturity
        label, color, _ = get_maturity(1.5)
        assert label == "Nascent"
        assert color == "red"

    def test_get_maturity_leading(self):
        from models import get_maturity
        label, color, _ = get_maturity(9.5)
        assert label == "Leading"
        assert color == "blue"

    def test_get_maturity_boundary(self):
        from models import get_maturity
        # Exactly at 4.0 should be Developing
        label, color, _ = get_maturity(4.0)
        assert label == "Developing"

    def test_dimension_score_valid(self):
        from models import DimensionScore, Dimension
        ds = DimensionScore(
            dimension=Dimension.DATA_READINESS,
            score=6.5,
            maturity_level="Developing",
            maturity_color="yellow",
            key_strengths=["Good data warehouse"],
            key_gaps=["No data catalogue"],
            recommendations=["Implement data catalogue"],
        )
        assert ds.score == 6.5
        assert ds.maturity_level == "Developing"

    def test_dimension_score_invalid_range(self):
        from models import DimensionScore, Dimension
        with pytest.raises(Exception):
            DimensionScore(
                dimension=Dimension.DATA_READINESS,
                score=11.0,  # Invalid: > 10
                maturity_level="Leading",
                maturity_color="blue",
            )

    def test_assessment_report_serialisable(self):
        from models import AssessmentReport, DimensionScore, Dimension
        ds = DimensionScore(
            dimension=Dimension.DATA_READINESS,
            score=5.0,
            maturity_level="Developing",
            maturity_color="yellow",
        )
        report = AssessmentReport(
            report_id="RPT-TEST001",
            organisation_name="Test Corp",
            documents_analysed=["doc1.pdf"],
            total_pages_analysed=10,
            overall_score=5.0,
            overall_maturity="Developing",
            overall_maturity_color="yellow",
            executive_summary="Test summary.",
            dimension_scores=[ds],
            use_case_candidates=[],
            roadmap_phases=[],
            critical_blockers=["Blocker 1"],
            quick_wins=["Quick win 1"],
        )
        dumped = report.model_dump()
        assert dumped["organisation_name"] == "Test Corp"
        assert dumped["overall_score"] == 5.0
        # Should be JSON-serialisable
        json_str = json.dumps(dumped)
        assert "Test Corp" in json_str


# ---------------------------------------------------------------------------
# API tests (mocked LLM)
# ---------------------------------------------------------------------------

class TestAPI:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.app import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    def test_upload_requires_auth(self, client):
        resp = client.post("/v1/assessment/upload")
        assert resp.status_code == 403

    def test_upload_wrong_key(self, client):
        resp = client.post(
            "/v1/assessment/upload",
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 403

    def test_get_nonexistent_session(self, client):
        resp = client.get(
            "/v1/assessment/nonexistent-session-id",
            headers={"X-API-Key": "sk-advisor-demo-001"},
        )
        assert resp.status_code == 404

    def test_upload_unsupported_file_type(self, client, tmp_path):
        bad_file = tmp_path / "test.xlsx"
        bad_file.write_bytes(b"fake xlsx content")
        with open(bad_file, "rb") as f:
            resp = client.post(
                "/v1/assessment/upload",
                headers={"X-API-Key": "sk-advisor-demo-001"},
                files=[("files", ("test.xlsx", f, "application/vnd.ms-excel"))],
                data={"organisation_name": "Test Corp"},
            )
        assert resp.status_code == 400
        assert "Unsupported file type" in resp.json()["detail"]

    def test_upload_valid_txt_file(self, client, tmp_path):
        txt_file = tmp_path / "strategy.txt"
        txt_file.write_text("Our data strategy focuses on cloud migration and AI adoption. "
                            "We have a strong team of data engineers and cloud architects.")
        with open(txt_file, "rb") as f:
            resp = client.post(
                "/v1/assessment/upload",
                headers={"X-API-Key": "sk-advisor-demo-001"},
                files=[("files", ("strategy.txt", f, "text/plain"))],
                data={"organisation_name": "Test Corp"},
            )
        # Should return 200 with session_id (assessment runs async)
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "processing"
        assert "strategy.txt" in data["files_received"]


# ---------------------------------------------------------------------------
# Dimension description coverage
# ---------------------------------------------------------------------------

class TestDimensionCoverage:
    def test_all_dimensions_have_descriptions(self):
        from models import Dimension, DIMENSION_DESCRIPTIONS
        for dim in Dimension:
            assert dim in DIMENSION_DESCRIPTIONS
            assert len(DIMENSION_DESCRIPTIONS[dim]) > 20

    def test_all_dimensions_count(self):
        from models import Dimension
        assert len(list(Dimension)) == 6
