"""
Unit and Integration Tests for Visual Asset Extraction Pipeline and REST APIs.
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

TEST_TMP_DIR = tempfile.mkdtemp(prefix="gate_visual_test_")
os.environ["SQLITE_DB_PATH"] = os.path.join(TEST_TMP_DIR, "test_gate_visual.db")
os.environ["UPLOAD_DIR"] = os.path.join(TEST_TMP_DIR, "uploads")
os.environ["VISUAL_ASSETS_DIR"] = os.path.join(TEST_TMP_DIR, "visual_assets")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.core.config import settings
from app.database.session import get_db_connection, init_database, new_uuid, utcnow_iso
from app.main import app
from app.pipelines.visual_pipeline import VisualPipeline, cluster_page_visuals

try:
    import fitz
except ImportError:
    fitz = None


def make_pdf_with_drawings() -> bytes:
    """Create a PDF with vector rectangles simulating a diagram question."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    # Page 1
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 800, "GATE 2026 CS")
    c.drawString(50, 750, "Q.1 Which of the following state machines recognizes the language? [2 Marks]")
    # Draw vector diagram for stem
    c.rect(100, 600, 150, 100, stroke=1, fill=0)
    c.circle(150, 650, 20, stroke=1, fill=0)

    # Option A
    c.drawString(50, 550, "(A)")
    c.rect(100, 480, 80, 50, stroke=1, fill=0)

    # Option B
    c.drawString(250, 550, "(B)")
    c.rect(300, 480, 80, 50, stroke=1, fill=0)

    # Option C
    c.drawString(50, 420, "(C)")
    c.rect(100, 350, 80, 50, stroke=1, fill=0)

    # Option D
    c.drawString(250, 420, "(D)")
    c.rect(300, 350, 80, 50, stroke=1, fill=0)

    c.showPage()
    c.save()
    return buf.getvalue()


class VisualAssetsTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_database()
        cls.client = TestClient(app)
        conn = get_db_connection()
        now = utcnow_iso()
        try:
            # Look up seeded gate_paper id for CS
            gp = conn.execute("SELECT id FROM gate_papers WHERE code = 'CS'").fetchone()
            gp_id = gp[0] if gp else "gp1"
            if not gp:
                conn.execute("INSERT OR IGNORE INTO gate_papers (id, code, name) VALUES ('gp1', 'CS', 'Computer Science')")

            # Seed test question_paper
            conn.execute(
                """
                INSERT OR IGNORE INTO question_papers (
                    id, paper_id, paper_code, examination_year, session_set, title,
                    filename, file_path, file_checksum, processing_status, total_extracted_questions,
                    created_at, updated_at
                ) VALUES (
                    'qp_test', ?, 'CS', 2026, 'Set-1', 'GATE CS 2026 Mock',
                    'test.pdf', '/tmp/test.pdf', 'chk_test_visual', 'completed', 0,
                    ?, ?
                )
                """,
                (gp_id, now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def test_01_clustering_and_extraction(self) -> None:
        if fitz is None:
            self.skipTest("fitz (PyMuPDF) not available")

        pdf_bytes = make_pdf_with_drawings()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc[0]
        clusters = cluster_page_visuals(page)
        self.assertGreaterEqual(len(clusters), 1, "Should detect at least 1 visual cluster")
        doc.close()

        vpipe = VisualPipeline(Path(settings.VISUAL_ASSETS_DIR))
        q_id = new_uuid()
        questions = [
            {
                "id": q_id,
                "question_number": 1,
                "source_page_start": 1,
                "source_page_end": 1,
                "page_number": 1,
            }
        ]
        assets = vpipe.extract_and_map_visual_assets(
            pdf_bytes=pdf_bytes,
            paper_id="test_paper_1",
            questions=questions,
            paper_code="CS",
            exam_year=2026,
        )
        self.assertGreaterEqual(len(assets), 1)

        # Verify DB persistence
        conn = get_db_connection()
        try:
            now = utcnow_iso()
            conn.execute(
                """
                INSERT INTO questions (
                    id, question_paper_id, paper_code, examination_year, question_number,
                    source_question_label, question_type, question_text, marks, negative_marks,
                    page_number, source_page_start, source_page_end, created_at, updated_at
                ) VALUES (?, 'qp_test', 'CS', 2026, 1, 'Q.1', 'MCQ', 'Stem with diagram', 2, 0.67, 1, 1, 1, ?, ?)
                """,
                (q_id, now, now),
            )
            conn.commit()

            inserted = vpipe.persist_visual_assets_to_db(conn, assets)
            self.assertEqual(inserted, len(assets))

            # Check that questions.has_diagram_or_table was set to 1
            has_diag = conn.execute("SELECT has_diagram_or_table FROM questions WHERE id = ?", (q_id,)).fetchone()[0]
            self.assertEqual(has_diag, 1)
        finally:
            conn.close()

    def test_02_visual_assets_api_and_security(self) -> None:
        # Create a test question and a test visual asset
        conn = get_db_connection()
        now = utcnow_iso()
        q_id = new_uuid()
        asset_id = new_uuid()
        asset_filename = f"test_asset_{asset_id[:8]}.png"
        asset_path = settings.VISUAL_ASSETS_DIR / asset_filename
        # Write dummy png bytes
        asset_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

        try:
            conn.execute(
                """
                INSERT INTO questions (
                    id, question_paper_id, paper_code, examination_year, question_number,
                    source_question_label, question_type, question_text, marks, negative_marks,
                    page_number, source_page_start, source_page_end, created_at, updated_at
                ) VALUES (?, 'qp_test', 'CS', 2026, 99, 'Q.99', 'MCQ', 'Visual test question', 1, 0.33, 1, 1, 1, ?, ?)
                """,
                (q_id, now, now),
            )
            conn.execute(
                """
                INSERT INTO question_visual_assets (
                    id, question_id, asset_role, asset_type, option_label, relative_path,
                    source_page, bbox_json, confidence, review_status, created_at, updated_at
                ) VALUES (?, ?, 'stem', 'diagram', NULL, ?, 1, '[10, 10, 100, 100]', 0.95, 'approved', ?, ?)
                """,
                (asset_id, q_id, f"visual_assets/{asset_filename}", now, now),
            )
            conn.commit()
        finally:
            conn.close()

        # 1. GET /questions/{id}/assets
        res_assets = self.client.get(f"/api/v1/questions/{q_id}/assets")
        self.assertEqual(res_assets.status_code, 200)
        items = res_assets.json()["visual_assets"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], asset_id)
        self.assertEqual(items[0]["asset_role"], "stem")

        # 2. GET /questions/{id} contains hydrated visual_assets
        res_q = self.client.get(f"/api/v1/questions/{q_id}")
        self.assertEqual(res_q.status_code, 200)
        self.assertIn("visual_assets", res_q.json())
        self.assertEqual(len(res_q.json()["visual_assets"]), 1)

        # 3. GET /assets/{id}/image
        res_img = self.client.get(f"/api/v1/assets/{asset_id}/image")
        self.assertEqual(res_img.status_code, 200)
        self.assertEqual(res_img.headers.get("content-type"), "image/png")
        self.assertGreater(len(res_img.content), 0)

        # 4. Review status update: POST /assets/{id}/review
        res_rev = self.client.post(f"/api/v1/assets/{asset_id}/review?review_status=rejected")
        self.assertEqual(res_rev.status_code, 200)
        self.assertEqual(res_rev.json()["review_status"], "rejected")

        # 5. Non-existent asset returns 404
        res_404 = self.client.get("/api/v1/assets/non_existent_id/image")
        self.assertEqual(res_404.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
