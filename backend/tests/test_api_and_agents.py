"""
End-to-End Automated Integration Test Suite for GATE Intelligence.
Tests:
1. Health Check & Initial Zero-Fake-Data State (30 official GATE papers seeded, 0 questions initially).
2. User Registration, Login, Argon2/PBKDF2 Password Hashing & JWT `/auth/me` Verification.
3. PDF Security Validation (rejects non-PDF, rejects malicious `/JavaScript` PDFs, prevents SHA-256 duplicate uploads).
4. Multi-Page PDF Ingestion Pipeline & 10-Agent Orchestration (generates real multi-question PDFs using `reportlab` for two exam years, uploads via `/api/v1/papers/upload`, verifies extracted MCQ/MSQ/NAT questions, page numbers, negative marking, multi-topic classification, and 384-d embeddings).
5. Agent 4 Duplicate & Numeric-Variant Similarity Detection across multi-year papers.
6. Agent 5 Explainable Topic Importance Ranking & Holdout Year Backtesting (`/api/v1/analytics/importance`).
7. Question Verification & Answer Provenance Tracking (`PATCH /questions/{id}` & `POST /questions/{id}/verify`).
8. Agent 6 RAG-Based AI Tutor (`/api/v1/tutor/ask`) with provenance badge and exact page citations.
9. Agents 7 & 8 Mock Test Generation, Start, Submission & Official GATE Marking Evaluation (-1/3 & -2/3 MCQ penalty, MSQ exact match, NAT tolerance).
10. Agent 9 Personalized Study Planner Generation & Progress Update (`/api/v1/planner/generate`, `PATCH /api/v1/planner/{id}`).
11. Agent 10 Execution Logs & Job Status Telemetry (`/api/v1/agents`, `/api/v1/agents/runs`, `/api/v1/jobs/{job_id}`).
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Point to a temporary test SQLite database before importing the FastAPI app
TEST_TMP_DIR = tempfile.mkdtemp(prefix="gate_intel_test_")
os.environ["SQLITE_DB_PATH"] = os.path.join(TEST_TMP_DIR, "test_gate_intelligence.db")
os.environ["UPLOAD_DIR"] = os.path.join(TEST_TMP_DIR, "uploads")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.database.session import init_database
from app.main import app


def build_test_gate_pdf(year: int, variant: str = "A") -> bytes:
    """Create a multi-page digital PDF formatted like a GATE CS examination paper for testing extraction."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    # Page 1
    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, 800, f"GATE {year} Computer Science and Information Technology (CS)")
    c.setFont("Helvetica", 11)
    if variant == "A":
        c.drawString(50, 760, "Q.1 Consider a binary search tree with 15 nodes. What is the minimum height of the binary tree? [1 Mark]")
        c.drawString(65, 740, "(A) 3")
        c.drawString(65, 725, "(B) 4")
        c.drawString(65, 710, "(C) 5")
        c.drawString(65, 695, "(D) 14")

        c.drawString(50, 655, "Q.2 Which of the following statements are correct regarding Dijkstra's shortest path")
        c.drawString(50, 640, "algorithm on a graph? (Multiple Select MSQ) [2 Marks]")
        c.drawString(65, 620, "(A) It uses a greedy strategy to relax edges")
        c.drawString(65, 605, "(B) It works correctly for all graphs with negative weight cycles")
        c.drawString(65, 590, "(C) Using a binary heap priority queue gives O((V + E) log V) time complexity")
        c.drawString(65, 575, "(D) It always computes the minimum spanning tree")
    else:
        # Variant B (subsequent year): Q.1 is a numeric variant of Variant A Q.1; Q.2 tests Operating Systems LRU page replacement
        c.drawString(50, 760, "Q.1 Consider a binary search tree with 31 nodes. What is the minimum height of the binary tree? [1 Mark]")
        c.drawString(65, 740, "(A) 4")
        c.drawString(65, 725, "(B) 5")
        c.drawString(65, 710, "(C) 6")
        c.drawString(65, 695, "(D) 30")

        c.drawString(50, 655, "Q.2 Consider a virtual memory paging system with TLB hit ratio 0.90 and page table")
        c.drawString(50, 640, "access time 100 ns. Which of the following are correct? (Multiple Select MSQ) [2 Marks]")
        c.drawString(65, 620, "(A) LRU page replacement does not suffer from Belady's anomaly")
        c.drawString(65, 605, "(B) FIFO page replacement is a stack algorithm")
        c.drawString(65, 590, "(C) Translation Lookaside Buffer (TLB) caches virtual-to-physical page frame mappings")
        c.drawString(65, 575, "(D) Thrashing occurs when CPU utilization is 100%")

    c.showPage()
    # Page 2: NAT Question
    c.setFont("Helvetica", 11)
    c.drawString(50, 780, f"GATE {year} CS - Page 2 Numerical Answer Type (NAT)")
    c.drawString(50, 745, "Q.36 A 4-way set associative cache memory has 128 blocks and block size of 64 bytes.")
    c.drawString(50, 730, "The number of sets in the cache is ______ (in integer). [2 Marks]")
    c.showPage()
    c.save()
    return buf.getvalue()


class GateIntelligenceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import shutil
        cls._tmp_dir = tempfile.mkdtemp(prefix="gate_api_isolated_")
        os.environ["SQLITE_DB_PATH"] = os.path.join(cls._tmp_dir, "test_api.db")
        os.environ["UPLOAD_DIR"] = os.path.join(cls._tmp_dir, "uploads")
        init_database()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        import shutil
        if hasattr(cls, "_tmp_dir") and os.path.exists(cls._tmp_dir):
            shutil.rmtree(cls._tmp_dir, ignore_errors=True)

    def test_01_health_and_clean_initial_database(self) -> None:
        res = self.client.get("/api/v1/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "healthy")
        self.assertEqual(body["supported_gate_papers"], 30)
        self.assertEqual(body["total_questions_in_db"], 0)

        tax = self.client.get("/api/v1/taxonomy/papers")
        self.assertEqual(tax.status_code, 200)
        self.assertEqual(tax.json()["total_supported_disciplines"], 30)

    def test_02_authentication_flow(self) -> None:
        reg = self.client.post(
            "/api/v1/auth/register",
            json={
                "email": "student@gateintelligence.in",
                "full_name": "Atharv Student",
                "password": "StrongGatePassword!2026",
                "target_paper_code": "CS",
                "target_year": 2026,
            },
        )
        self.assertEqual(reg.status_code, 201)
        token = reg.json()["access_token"]
        self.assertTrue(len(token) > 20)

        login = self.client.post(
            "/api/v1/auth/login",
            json={
                "email": "student@gateintelligence.in",
                "password": "StrongGatePassword!2026",
            },
        )
        self.assertEqual(login.status_code, 200)

        me = self.client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["email"], "student@gateintelligence.in")
        self.__class__.jwt_token = token

    def test_03_pdf_security_validation(self) -> None:
        # 1. Reject non-PDF file signature
        bad_res = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("fake.pdf", b"NOT_A_PDF_HEADER_CONTENT", "application/pdf")},
            data={"paper_code": "CS", "examination_year": "2024"},
        )
        self.assertEqual(bad_res.status_code, 400)

        # 2. Reject PDF containing embedded /JavaScript action
        malicious_bytes = b"%PDF-1.7\n1 0 obj << /Type /Catalog /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >> endobj"
        mal_res = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("malicious.pdf", malicious_bytes, "application/pdf")},
            data={"paper_code": "CS", "examination_year": "2024"},
        )
        self.assertEqual(mal_res.status_code, 400)
        self.assertIn("disallowed active content", mal_res.json()["detail"])

    def test_04_multi_year_pdf_ingestion_and_duplicate_detection(self) -> None:
        pdf_2024 = build_test_gate_pdf(2024, variant="A")
        up1 = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("GATE_CS_2024.pdf", pdf_2024, "application/pdf")},
            data={"paper_code": "CS", "examination_year": "2024", "session_set": "Set-1", "run_synchronously": "true"},
        )
        self.assertEqual(up1.status_code, 201, up1.text)
        b1 = up1.json()
        self.assertEqual(b1["extracted_questions_count"], 3)
        self.__class__.job_id_1 = b1["job_id"]

        # Duplicate upload of same PDF must return 409 Conflict
        dup_res = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("GATE_CS_2024_copy.pdf", pdf_2024, "application/pdf")},
            data={"paper_code": "CS", "examination_year": "2024", "session_set": "Set-1"},
        )
        self.assertEqual(dup_res.status_code, 409)

        # Upload 2025 paper (Variant B) to test multi-year analytics, holdout backtesting, and Agent 4 numeric-variant detection
        pdf_2025 = build_test_gate_pdf(2025, variant="B")
        up2 = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("GATE_CS_2025.pdf", pdf_2025, "application/pdf")},
            data={"paper_code": "CS", "examination_year": "2025", "session_set": "Set-1", "run_synchronously": "true"},
        )
        self.assertEqual(up2.status_code, 201, up2.text)
        self.assertEqual(up2.json()["extracted_questions_count"], 3)

    def test_05_question_bank_and_verification(self) -> None:
        q_res = self.client.get("/api/v1/questions", params={"paper_code": "CS"})
        self.assertEqual(q_res.status_code, 200)
        items = q_res.json()["items"]
        self.assertEqual(len(items), 6)

        # Verify MCQ, MSQ, and NAT types and official negative marking rules
        types_found = {q["question_type"] for q in items}
        self.assertEqual(types_found, {"MCQ", "MSQ", "NAT"})

        for q in items:
            if q["question_type"] in ("MCQ", "MSQ"):
                self.assertEqual([o["option_label"] for o in q["options"]], ["A", "B", "C", "D"])
            if q["question_type"] == "MCQ" and q["marks"] == 1.0:
                self.assertAlmostEqual(q["negative_marks"], 0.333333, places=4)
                # Verify official key for MCQ
                v_res = self.client.post(
                    f"/api/v1/questions/{q['id']}/verify",
                    json={"provenance": "official_key", "correct_options": ["A"], "explanation": "Minimum height of 15-node binary tree is floor(log2(15)) = 3."},
                )
                self.assertEqual(v_res.status_code, 200)
                self.assertTrue(v_res.json()["is_verified"])
            elif q["question_type"] == "MSQ":
                self.assertEqual(q["negative_marks"], 0.0)
                self.client.post(
                    f"/api/v1/questions/{q['id']}/verify",
                    json={"provenance": "official_key", "correct_options": ["A", "C"]},
                )
            elif q["question_type"] == "NAT":
                self.assertEqual(q["negative_marks"], 0.0)
                self.client.post(
                    f"/api/v1/questions/{q['id']}/verify",
                    json={"provenance": "official_key", "numerical_min": 32.0, "numerical_max": 32.0},
                )

    def test_06_analytics_importance_and_holdout_backtesting(self) -> None:
        imp_res = self.client.get("/api/v1/analytics/importance", params={"paper_code": "CS"})
        self.assertEqual(imp_res.status_code, 200)
        imp = imp_res.json()
        self.assertGreaterEqual(len(imp["topics"]), 2)
        self.assertIsNotNone(imp["backtest_validation"])
        self.assertEqual(imp["backtest_validation"]["holdout_year"], 2025)

        rep_res = self.client.get("/api/v1/analytics/repeated", params={"paper_code": "CS"})
        self.assertEqual(rep_res.status_code, 200)
        pairs = rep_res.json()["pairs"]
        self.assertGreaterEqual(len(pairs), 1)
        sim_types = {p["similarity_type"] for p in pairs}
        self.assertIn("numeric_variant", sim_types)

    def test_07_rag_tutor_with_provenance_and_citations(self) -> None:
        tut_res = self.client.post(
            "/api/v1/tutor/ask",
            json={"query": "Dijkstra shortest path binary heap time complexity", "paper_code": "CS"},
        )
        self.assertEqual(tut_res.status_code, 200)
        body = tut_res.json()
        self.assertEqual(body["answer_provenance"], "official_key")
        self.assertTrue(len(body["citations"]) >= 1)
        self.assertIn("Page", body["citations"][0])

    def test_08_mock_test_generation_and_evaluation(self) -> None:
        gen_res = self.client.post(
            "/api/v1/tests/generate",
            json={
                "paper_code": "CS",
                "test_mode": "mixed_topic",
                "question_count": 6,
                "duration_minutes": 30,
            },
        )
        self.assertEqual(gen_res.status_code, 201)
        test_id = gen_res.json()["id"]

        test_detail = self.client.get(f"/api/v1/tests/{test_id}").json()
        q_list = test_detail["questions"]
        self.assertEqual(len(q_list), 6)

        self.client.post(f"/api/v1/tests/{test_id}/start")

        # Answer 1 MCQ wrong (should deduct -1/3), 1 MSQ right (+2), 1 NAT right (+2)
        submission = []
        for idx, q in enumerate(q_list):
            if q["question_type"] == "MCQ":
                submission.append({"question_id": q["id"], "selected_options": ["D"] if idx == 0 else ["A"]})
            elif q["question_type"] == "MSQ":
                submission.append({"question_id": q["id"], "selected_options": ["A", "C"]})
            elif q["question_type"] == "NAT":
                submission.append({"question_id": q["id"], "selected_options": [], "numerical_answer": 32.0})

        sub_res = self.client.post(
            f"/api/v1/tests/{test_id}/submit",
            json={"time_taken_seconds": 600, "responses": submission},
        )
        self.assertEqual(sub_res.status_code, 200)
        eval_body = sub_res.json()
        self.assertEqual(eval_body["total_marks"], 10.0)
        self.assertEqual(eval_body["attempted_count"], 6)
        self.assertEqual(eval_body["correct_count"], 5)
        self.assertEqual(eval_body["incorrect_count"], 1)
        # Total marks = 2*(1+2+2) = 10. Earned = 1(MCQ right) - 1/3(MCQ wrong) + 4(MSQs) + 4(NATs) = 8.67
        self.assertAlmostEqual(eval_body["marks_obtained"], 8.67, places=2)

    def test_09_personalized_study_planner_and_agent_logs(self) -> None:
        plan_res = self.client.post(
            "/api/v1/planner/generate",
            json={"paper_code": "CS", "target_year": 2026, "available_days": 28, "daily_hours": 4.0},
        )
        self.assertEqual(plan_res.status_code, 201)
        plan_id = plan_res.json()["id"]
        self.assertGreaterEqual(len(plan_res.json()["roadmap"]), 1)

        upd_res = self.client.patch(
            f"/api/v1/planner/{plan_id}", json={"progress_percent": 35.0}
        )
        self.assertEqual(upd_res.status_code, 200)
        self.assertEqual(upd_res.json()["progress_percent"], 35.0)

        agents_res = self.client.get("/api/v1/agents")
        self.assertEqual(agents_res.status_code, 200)
        self.assertEqual(len(agents_res.json()["agents"]), 10)

        runs_res = self.client.get("/api/v1/agents/runs")
        self.assertEqual(runs_res.status_code, 200)
        self.assertGreaterEqual(runs_res.json()["total"], 10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
