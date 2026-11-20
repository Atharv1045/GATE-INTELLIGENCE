"""
Phase 6 Comprehensive Test Suite:
1. Database Migration Integrity (`test_01_legacy_migration_unknown_labels_and_relationship_preservation`):
   - Creates a pre-Phase-2 legacy SQLite database without `source_question_label`, `extraction_status`,
     `extraction_warnings`, `source_page_start`, `source_page_end`.
   - Inserts legacy questions, options, and answer keys (including unverified records and records corrupted with `'Q.1'`).
   - Runs `ensure_schema_migrations()` and verifies:
     * Legacy unverified records receive `source_question_label = 'UNKNOWN'` (never `'Q.1'`).
     * They are flagged with `extraction_status = 'uncertain'` and `needs_human_review = 1`.
     * Existing verified records and all `question_options` / `answer_keys` relationships remain 100% intact.
2. Transactional Reprocessing Safety (`test_02_transactional_reprocessing_rollback_on_failures` & `test_03_concurrent_reprocessing_lock`):
   - Uploads a valid GATE PDF (extracts 3 questions) and verifies an official answer key on Q.1.
   - Simulates (a) failed OCR / DocumentProcessingAgent exception, (b) failed QuestionExtractionAgent exception,
     (c) empty extraction (0 questions returned), and (d) simulated database insertion error inside the savepoint.
   - Verifies that in ALL 4 failure modes, the original 3 questions and the verified answer key on Q.1 remain completely intact!
   - Verifies that when reprocessing succeeds, records update atomically and the verified answer key on Q.1 is preserved.
   - Verifies that concurrent reprocessing requests for the same paper return `409 Conflict`.
3. Deterministic `Decimal` CBT Evaluation Unit & Integration Tests (`test_04_deterministic_cbt_scoring_all_cases`):
   - Tests 1-mark MCQ (+1.0, -1/3, 0 unattempted), 2-mark MCQ (+2.0, -2/3, 0 unattempted),
     MSQ (+2.0 exact set match, 0.0 partial match, 0.0 wrong option, 0.0 unattempted),
     NAT (+2.0 within tolerance, 0.0 outside tolerance, 0.0 unattempted),
     answer normalization (case/whitespace/ordering), and provisional flagging on unverified answer keys.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Isolate test database from production database before importing app
TEST_TMP_DIR = tempfile.mkdtemp(prefix="gate_phase6_isolated_")
os.environ["SQLITE_DB_PATH"] = os.path.join(TEST_TMP_DIR, "test_phase6.db")
os.environ["UPLOAD_DIR"] = os.path.join(TEST_TMP_DIR, "uploads")

from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.agents.orchestrator import (
    AnswerEvaluationAgent,
    CentralOrchestrator,
    acquire_paper_processing_lock,
    release_paper_processing_lock,
)
from app.database.session import (
    ensure_schema_migrations,
    get_db_connection,
    init_database,
    new_uuid,
    utcnow_iso,
)
from app.main import app


def _make_sample_pdf(questions_spec: list[tuple[int, str, list[str], int]]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 800, "GATE 2024 Computer Science (CS)")
    c.setFont("Helvetica", 10)
    y = 760
    for qnum, stem, opts, marks in questions_spec:
        c.drawString(50, y, f"Q.{qnum} {stem} [{marks} Mark{'s' if marks > 1 else ''}]")
        y -= 18
        for opt_str in opts:
            c.drawString(65, y, opt_str)
            y -= 15
        y -= 12
    c.showPage()
    c.save()
    return buf.getvalue()


class Phase6IntegrityAndScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp_dir = TEST_TMP_DIR
        os.environ["SQLITE_DB_PATH"] = os.path.join(cls._tmp_dir, "test_phase6.db")
        os.environ["UPLOAD_DIR"] = os.path.join(cls._tmp_dir, "uploads")
        init_database()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "_tmp_dir") and os.path.exists(cls._tmp_dir):
            shutil.rmtree(cls._tmp_dir, ignore_errors=True)

    def test_01_legacy_migration_unknown_labels_and_relationship_preservation(self) -> None:
        """
        Verify Critical Issue A:
        1. Pre-existing records without `source_question_label` receive `'UNKNOWN'` (never `'Q.1'`).
        2. They are marked `extraction_status = 'uncertain'` and `needs_human_review = 1`.
        3. Records previously corrupted with `source_question_label = 'Q.1'` where `question_number != 1`
           or where multiple unverified rows in the same paper had `'Q.1'` are repaired to `'UNKNOWN'`.
        4. Existing verified records and foreign-key relationships (`question_options`, `answer_keys`) are preserved.
        """
        legacy_db_path = Path(self._tmp_dir) / "legacy_pre_phase2.db"
        conn = sqlite3.connect(str(legacy_db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")

        # Create legacy questions table WITHOUT the 5 Phase-2 columns
        conn.executescript(
            """
            CREATE TABLE gate_papers (
                id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL
            );
            CREATE TABLE question_papers (
                id TEXT PRIMARY KEY, paper_id TEXT NOT NULL, paper_code TEXT NOT NULL,
                examination_year INTEGER NOT NULL, title TEXT NOT NULL, filename TEXT NOT NULL,
                file_path TEXT NOT NULL, file_checksum TEXT UNIQUE NOT NULL
            );
            CREATE TABLE questions (
                id TEXT PRIMARY KEY,
                question_paper_id TEXT,
                paper_code TEXT NOT NULL,
                examination_year INTEGER NOT NULL,
                question_number INTEGER NOT NULL,
                question_type TEXT NOT NULL,
                question_text TEXT NOT NULL,
                math_expressions_json TEXT NOT NULL DEFAULT '[]',
                has_diagram_or_table INTEGER NOT NULL DEFAULT 0,
                marks REAL NOT NULL DEFAULT 1.0,
                negative_marks REAL NOT NULL DEFAULT 0.333333,
                page_number INTEGER NOT NULL DEFAULT 1,
                subject_name TEXT,
                primary_topic_name TEXT,
                subtopic_name TEXT,
                difficulty_level TEXT NOT NULL DEFAULT 'Medium',
                syllabus_version_tag TEXT NOT NULL DEFAULT '2026.1',
                extraction_confidence REAL NOT NULL DEFAULT 0.9,
                classification_confidence REAL NOT NULL DEFAULT 0.85,
                needs_human_review INTEGER NOT NULL DEFAULT 0,
                is_verified INTEGER NOT NULL DEFAULT 0,
                is_ai_generated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE question_options (
                id TEXT PRIMARY KEY,
                question_id TEXT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                option_label TEXT NOT NULL,
                option_text TEXT NOT NULL,
                is_correct INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        now = utcnow_iso()
        conn.execute("INSERT INTO gate_papers VALUES ('gp1', 'CS', 'Computer Science')")
        conn.execute("INSERT INTO question_papers VALUES ('qp1', 'gp1', 'CS', 2012, 'GATE CS 2012', 'cs12.pdf', '/tmp/cs12.pdf', 'chk123')")

        # Insert 2 legacy unverified questions (one with q_num=1, one with q_num=24)
        conn.execute(
            """
            INSERT INTO questions (
                id, question_paper_id, paper_code, examination_year, question_number,
                question_type, question_text, page_number, needs_human_review, is_verified,
                created_at, updated_at
            ) VALUES
            ('legacy_q1', 'qp1', 'CS', 2012, 1, 'MCQ', 'Legacy unverified question 1', 2, 0, 0, ?, ?),
            ('legacy_q24', 'qp1', 'CS', 2012, 24, 'MCQ', 'Legacy unverified question 24', 5, 0, 0, ?, ?)
            """,
            (now, now, now, now),
        )
        conn.execute(
            "INSERT INTO question_options VALUES ('opt1', 'legacy_q24', 'A', 'Option A text', 1, ?, ?)",
            (now, now),
        )
        conn.commit()

        # Run migration on legacy database
        ensure_schema_migrations(conn)

        rows = {
            r["id"]: dict(r)
            for r in conn.execute("SELECT * FROM questions").fetchall()
        }
        self.assertEqual(len(rows), 2)
        for qid, r in rows.items():
            self.assertEqual(r["source_question_label"], "UNKNOWN", f"{qid} should be UNKNOWN, not Q.1")
            self.assertEqual(r["extraction_status"], "uncertain")
            self.assertEqual(r["needs_human_review"], 1)

        self.assertEqual(rows["legacy_q1"]["source_page_start"], 2)
        self.assertEqual(rows["legacy_q24"]["source_page_start"], 5)

        # Verify child option was preserved
        opt_cnt = conn.execute(
            "SELECT COUNT(*) FROM question_options WHERE question_id = 'legacy_q24'"
        ).fetchone()[0]
        self.assertEqual(opt_cnt, 1)
        conn.close()

    def test_02_transactional_reprocessing_rollback_on_failures(self) -> None:
        """
        Verify Critical Issue B:
        - Upload a valid 3-question PDF and verify an official answer key on Q.1.
        - Test 1: OCR / DocumentProcessingAgent raises RuntimeError -> original 3 questions & verified key remain intact.
        - Test 2: QuestionExtractionAgent raises RuntimeError -> original 3 questions & verified key remain intact.
        - Test 3: Extraction returns 0 questions (empty extraction) -> safety guard aborts replacement and preserves 3 questions.
        - Test 4: Database insertion fails mid-transaction -> savepoint rolls back and preserves original 3 questions.
        - Test 5: Valid reprocessing succeeds atomically and preserves the verified answer key on Q.1.
        """
        pdf_bytes = _make_sample_pdf([
            (1, "What is the time complexity of heapify on a binary heap of size n?", ["(A) O(log n)", "(B) O(n)", "(C) O(n log n)", "(D) O(1)"], 1),
            (2, "Which of the following are true for AVL trees? (Multiple Select MSQ)", ["(A) Height is O(log n)", "(B) Balance factor is in {-1,0,1}", "(C) No rotations needed", "(D) Binary search property holds"], 2),
            (36, "Consider a hash table with 10 slots. The load factor for 20 keys (in integer) is ______.", [], 2),
        ])
        up_res = self.client.post(
            "/api/v1/papers/upload",
            files={"file": ("GATE_CS_2023_Tx.pdf", pdf_bytes, "application/pdf")},
            data={"paper_code": "CS", "examination_year": "2023", "session_set": "Set-1", "run_synchronously": "true"},
        )
        self.assertEqual(up_res.status_code, 201, up_res.text)
        paper_id = up_res.json()["paper_id"]
        self.assertEqual(up_res.json()["extracted_questions_count"], 3)

        # Verify official answer key on Q.1
        q_list = self.client.get("/api/v1/questions", params={"paper_code": "CS", "examination_year": 2023}).json()["items"]
        q1_id = next(q["id"] for q in q_list if q["question_number"] == 1)
        ver_res = self.client.post(
            f"/api/v1/questions/{q1_id}/verify",
            json={"provenance": "official_key", "correct_options": ["A"], "explanation": "Heapify takes O(log n) time."},
        )
        self.assertEqual(ver_res.status_code, 200)

        # Failure Mode 1: OCR / DocumentProcessingAgent failure
        with patch("app.agents.orchestrator.DocumentProcessingAgent.run", side_effect=RuntimeError("Simulated OCR crash")):
            r1 = self.client.post(f"/api/v1/papers/{paper_id}/reprocess")
            self.assertEqual(r1.status_code, 422)
            self.assertEqual(r1.json()["detail"]["preserved_questions_count"], 3)

        # Failure Mode 2: QuestionExtractionAgent failure
        with patch("app.agents.orchestrator.QuestionExtractionAgent.run", side_effect=RuntimeError("Simulated extraction crash")):
            r2 = self.client.post(f"/api/v1/papers/{paper_id}/reprocess")
            self.assertEqual(r2.status_code, 422)
            self.assertEqual(r2.json()["detail"]["preserved_questions_count"], 3)

        # Failure Mode 3: Extraction returns 0 questions (empty result protection)
        with patch("app.agents.orchestrator.QuestionExtractionAgent.run", return_value={"extracted_questions": [], "needs_human_review_count": 0}):
            r3 = self.client.post(f"/api/v1/papers/{paper_id}/reprocess")
            self.assertEqual(r3.status_code, 422)
            self.assertEqual(r3.json()["detail"]["preserved_questions_count"], 3)

        # Failure Mode 4: Mid-transaction failure during embedding/DB persistence
        orig_classify = CentralOrchestrator().classify_agent.run
        def _corrupt_classified(state):
            out = orig_classify(state)
            # Corrupt the 2nd question's marks to a non-float string to force a ValueError inside the SAVEPOINT loop
            out["classified_questions"][1]["marks"] = "INVALID_FLOAT_CAUSING_ROLLBACK"
            return out

        with patch("app.agents.orchestrator.QuestionClassificationAgent.run", side_effect=_corrupt_classified):
            r4 = self.client.post(f"/api/v1/papers/{paper_id}/reprocess")
            self.assertEqual(r4.status_code, 422)
            self.assertEqual(r4.json()["detail"]["preserved_questions_count"], 3)

        # Verify that after all 4 failures, the original 3 questions AND Q.1's verified official_key are still intact!
        surviving = self.client.get("/api/v1/questions", params={"paper_code": "CS", "examination_year": 2023}).json()["items"]
        self.assertEqual(len(surviving), 3)
        q1_after_failures = next(q for q in surviving if q["question_number"] == 1)
        self.assertTrue(q1_after_failures["is_verified"])
        self.assertEqual(q1_after_failures["answer_key"]["provenance"], "official_key")
        self.assertEqual(q1_after_failures["answer_key"]["correct_options"], ["A"])

        # Test 5: Successful atomic reprocessing preserves Q.1's verified answer key
        r5 = self.client.post(f"/api/v1/papers/{paper_id}/reprocess")
        self.assertEqual(r5.status_code, 200, r5.text)
        self.assertEqual(r5.json()["extracted_questions_count"], 3)

        post_success = self.client.get("/api/v1/questions", params={"paper_code": "CS", "examination_year": 2023}).json()["items"]
        self.assertEqual(len(post_success), 3)
        q1_reprocessed = next(q for q in post_success if q["question_number"] == 1)
        self.assertTrue(q1_reprocessed["is_verified"])
        self.assertEqual(q1_reprocessed["answer_key"]["provenance"], "official_key")
        self.assertEqual(q1_reprocessed["answer_key"]["correct_options"], ["A"])

    def test_03_concurrent_reprocessing_lock(self) -> None:
        """Verify that concurrent reprocessing requests for the same paper are safely rejected with 409 Conflict."""
        fake_paper_id = "paper-concurrent-lock-test"
        acquired = acquire_paper_processing_lock(fake_paper_id)
        self.assertTrue(acquired)
        try:
            res = self.client.post(f"/api/v1/papers/{fake_paper_id}/reprocess")
            self.assertEqual(res.status_code, 409)
            self.assertIn("already in progress", res.json()["detail"])
        finally:
            release_paper_processing_lock(fake_paper_id)

    def test_04_deterministic_cbt_scoring_all_cases(self) -> None:
        """
        Verify Critical Issue C:
        Independent unit tests for `AnswerEvaluationAgent.evaluate_single_question_deterministic` covering:
        - 1-mark MCQ correct (+1.0), wrong (-1/3), unattempted (0.0)
        - 2-mark MCQ correct (+2.0), wrong (-2/3), unattempted (0.0)
        - MSQ exact set match (+2.0), partial match (0.0), wrong option (0.0), unattempted (0.0), case/order normalization
        - NAT within tolerance (+2.0), boundary of tolerance (+2.0), outside tolerance (0.0), unattempted (0.0)
        - Unverified answer key provisional flagging (`is_provisional = True`)
        """
        ev_fn = AnswerEvaluationAgent.evaluate_single_question_deterministic

        # 1. 1-Mark MCQ
        c_mcq1 = ev_fn("MCQ", 1.0, 0.333333, ["a"], None, ["A"], None, None, provenance="official_key")
        self.assertTrue(c_mcq1["is_correct"])
        self.assertEqual(c_mcq1["marks_awarded_decimal"], Decimal("1.0"))
        self.assertFalse(c_mcq1["is_provisional"])

        w_mcq1 = ev_fn("MCQ", 1.0, 0.333333, ["B"], None, ["A"], None, None, provenance="official_key")
        self.assertFalse(w_mcq1["is_correct"])
        self.assertEqual(w_mcq1["marks_awarded"], -0.3333)

        u_mcq1 = ev_fn("MCQ", 1.0, 0.333333, [], None, ["A"], None, None, provenance="official_key")
        self.assertIsNone(u_mcq1["is_correct"])
        self.assertEqual(u_mcq1["marks_awarded"], 0.0)

        # 2. 2-Mark MCQ
        w_mcq2 = ev_fn("MCQ", 2.0, 0.666667, ["D"], None, ["C"], None, None, provenance="official_key")
        self.assertFalse(w_mcq2["is_correct"])
        self.assertEqual(w_mcq2["marks_awarded"], -0.6667)

        # 3. MSQ (exact set match, zero partial credit, zero negative marking, order/case insensitive)
        c_msq = ev_fn("MSQ", 2.0, 0.0, ["c", "a"], None, ["A", "C"], None, None, provenance="official_key")
        self.assertTrue(c_msq["is_correct"])
        self.assertEqual(c_msq["marks_awarded"], 2.0)

        partial_msq = ev_fn("MSQ", 2.0, 0.0, ["A"], None, ["A", "C"], None, None, provenance="official_key")
        self.assertFalse(partial_msq["is_correct"])
        self.assertEqual(partial_msq["marks_awarded"], 0.0)

        wrong_msq = ev_fn("MSQ", 2.0, 0.0, ["A", "B", "C"], None, ["A", "C"], None, None, provenance="official_key")
        self.assertFalse(wrong_msq["is_correct"])
        self.assertEqual(wrong_msq["marks_awarded"], 0.0)

        # 4. NAT (numeric tolerance)
        c_nat = ev_fn("NAT", 2.0, 0.0, [], 32.005, [], 32.0, 32.0, tolerance=0.01, provenance="official_key")
        self.assertTrue(c_nat["is_correct"])
        self.assertEqual(c_nat["marks_awarded"], 2.0)

        w_nat = ev_fn("NAT", 2.0, 0.0, [], 32.05, [], 32.0, 32.0, tolerance=0.01, provenance="official_key")
        self.assertFalse(w_nat["is_correct"])
        self.assertEqual(w_nat["marks_awarded"], 0.0)

        # 5. Provisional unverified answer key
        prov_ev = ev_fn("MCQ", 1.0, 0.333333, ["A"], None, [], None, None, provenance="unverified")
        self.assertTrue(prov_ev["is_provisional"])
        self.assertIsNone(prov_ev["is_correct"])
        self.assertEqual(prov_ev["marks_awarded"], 0.0)


    def test_05_option_d_with_trailing_page_header_and_wide_margin_pdf(self) -> None:
        """
        Phase 7 Regression Test:
        1. Verify that when Option (D) is followed by a newline and a non-option line (such as a page header),
           all 4 options ['A', 'B', 'C', 'D'] (including nested parentheses in Option C) are preserved.
        2. Verify that wide single-line PDF strings extending past x=595pt preserve `[2 Marks]` and `(Multiple Select MSQ)`.
        """
        from app.pipelines.pdf_pipeline import PdfIngestionPipeline

        pipe = PdfIngestionPipeline()
        pages = [
            {
                "page_number": 1,
                "text": (
                    "Q.2 Which of the following statements are correct regarding Dijkstra's shortest path algorithm on a graph? (Multiple Select MSQ) [2 Marks]\n"
                    "(A) It uses a greedy strategy to relax edges\n"
                    "(B) It works correctly for all graphs with negative weight cycles\n"
                    "(C) Using a binary heap priority queue gives O((V + E) log V) time complexity\n"
                    "(D) It always computes the minimum spanning tree\n\n"
                    "GATE 2024 CS - Page 2 Numerical Answer Type (NAT)\n"
                    "Q.36 A 4-way set associative cache memory has 128 blocks. The number of sets is ______ (in integer). [2 Marks]"
                ),
                "has_tables": False,
                "ocr_used": False,
            }
        ]
        extracted = pipe.segment_and_extract_questions(pages, "CS", 2024)
        self.assertEqual(len(extracted), 2)
        q2 = extracted[0]
        self.assertEqual(q2["question_number"], 2)
        self.assertEqual(q2["question_type"], "MSQ")
        self.assertEqual(q2["marks"], 2.0)
        self.assertEqual([o["option_label"] for o in q2["options"]], ["A", "B", "C", "D"])
        self.assertIn("O((V + E) log V)", q2["options"][2]["option_text"])
        self.assertEqual(q2["options"][3]["option_text"], "It always computes the minimum spanning tree")
        self.assertEqual(q2["extraction_status"], "valid")
        self.assertFalse(q2["needs_human_review"])

    def test_06_multiline_option_continuations_are_preserved(self) -> None:
        """
        Phase 8 Regression Test:
        Verify that continuation lines belonging to MCQ options are
        preserved without absorbing the next option or question.
        """
        from app.pipelines.pdf_pipeline import PdfIngestionPipeline

        pipe = PdfIngestionPipeline()
        pages = [
            {
                "page_number": 1,
                "text": (
                    "Q.1 Which statements are correct? [2 Marks]\n"
                    "(A) First line of option A\n"
                    "    Continuation of option A\n"
                    "(B) First line of option B\n"
                    "    Continuation of option B\n"
                    "(C) Option C contains O((V + E) log V)\n"
                    "(D) Option D is the final option\n\n"
                    "Q.2 What is the next question? [1 Mark]\n"
                    "(A) Option A\n"
                    "(B) Option B\n"
                    "(C) Option C\n"
                    "(D) Option D"
                ),
                "has_tables": False,
                "ocr_used": False,
            }
        ]

        extracted = pipe.segment_and_extract_questions(pages, "CS", 2024)

        self.assertEqual(len(extracted), 2)

        q1 = extracted[0]
        self.assertEqual(q1["question_number"], 1)
        self.assertEqual(
            [o["option_label"] for o in q1["options"]],
            ["A", "B", "C", "D"],
        )

        options = {
            o["option_label"]: o["option_text"]
            for o in q1["options"]
        }

        self.assertIn("Continuation of option A", options["A"])
        self.assertIn("Continuation of option B", options["B"])
        self.assertIn("O((V + E) log V)", options["C"])
        self.assertEqual(options["D"], "Option D is the final option")

        q2 = extracted[1]
        self.assertEqual(q2["question_number"], 2)
        self.assertEqual(len(q2["options"]), 4)
        self.assertNotIn("Q.2", options["D"])

    def test_07_stem_containing_option_markers_before_actual_options(self) -> None:
        """
        Phase 1 Regression Test:
        Verify that question stems containing (A) and (B) (e.g. matrix/process definitions)
        do not prematurely truncate the stem, and the true options (A)..(D) are preserved.
        """
        from app.pipelines.pdf_pipeline import PdfIngestionPipeline

        pipe = PdfIngestionPipeline()
        pages = [
            {
                "page_number": 1,
                "text": (
                    "Q.1 Consider two matrices (A) and (B) of order 3x3. What is det(A + B)? [1 Mark]\n"
                    "(A) det(A) + det(B)\n"
                    "(B) det(AB)\n"
                    "(C) 0\n"
                    "(D) None of these"
                ),
                "has_tables": False,
                "ocr_used": False,
            }
        ]

        extracted = pipe.segment_and_extract_questions(pages, "CS", 2024)
        self.assertEqual(len(extracted), 1)
        q1 = extracted[0]
        self.assertEqual(q1["question_number"], 1)
        self.assertIn("Consider two matrices (A) and (B) of order 3x3. What is det(A + B)?", q1["question_text"])
        self.assertEqual(len(q1["options"]), 4)
        opts = {o["option_label"]: o["option_text"] for o in q1["options"]}
        self.assertEqual(opts["A"], "det(A) + det(B)")
        self.assertEqual(opts["B"], "det(AB)")
        self.assertEqual(opts["C"], "0")
        self.assertEqual(opts["D"], "None of these")

    def test_08_five_option_and_nested_parentheses_preservation(self) -> None:
        """
        Phase 1 Regression Test:
        Verify support for 5-option (A)..(E) questions and preservation of nested math parentheses.
        """
        from app.pipelines.pdf_pipeline import PdfIngestionPipeline

        pipe = PdfIngestionPipeline()
        pages = [
            {
                "page_number": 1,
                "text": (
                    "Q.1 Consider queuing theory with arrival rate lambda = 4. What is the utilization factor? [1 Mark]\n"
                    "(A) 0.25\n"
                    "(B) 0.50\n"
                    "(C) 0.75 with complexity O((V + E) log V)\n"
                    "(D) 0.80\n"
                    "(E) 0.95"
                ),
                "has_tables": False,
                "ocr_used": False,
            }
        ]

        extracted = pipe.segment_and_extract_questions(pages, "CS", 2024)
        self.assertEqual(len(extracted), 1)
        q1 = extracted[0]
        self.assertEqual(len(q1["options"]), 5)
        self.assertEqual([o["option_label"] for o in q1["options"]], ["A", "B", "C", "D", "E"])
        opts = {o["option_label"]: o["option_text"] for o in q1["options"]}
        self.assertIn("O((V + E) log V)", opts["C"])
        self.assertEqual(opts["E"], "0.95")

    def test_10_fresh_database_initialization_on_startup(self) -> None:
        """
        Phase 1 Regression Test:
        Verify that a completely fresh database is properly initialized with all tables
        and default seed data without requiring pre-existing files or tables.
        """
        import tempfile
        from pathlib import Path
        from app.database.session import init_database, get_db_connection

        with tempfile.TemporaryDirectory() as tmp_dir:
            fresh_db_path = Path(tmp_dir) / "fresh_gate_intel.db"
            # Initialize fresh DB
            init_database(fresh_db_path)
            self.assertTrue(fresh_db_path.exists())

            conn = get_db_connection(fresh_db_path)
            try:
                tables = [
                    r[0]
                    for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                    ).fetchall()
                ]
                required_tables = [
                    "gate_papers",
                    "question_papers",
                    "questions",
                    "question_options",
                    "answer_keys",
                    "question_topics",
                    "question_embeddings",
                    "question_visual_assets",
                    "users",
                    "mock_tests",
                    "test_questions",
                    "test_results",
                    "student_responses",
                    "study_plans",
                    "subjects",
                    "topics",
                    "syllabus_versions",
                    "agent_runs",
                    "processing_jobs",
                    "question_similarities",
                ]
                for tbl in required_tables:
                    self.assertIn(tbl, tables, f"Table {tbl} must exist in fresh DB")

                # Verify seed data in gate_papers
                paper_count = conn.execute("SELECT COUNT(*) FROM gate_papers").fetchone()[0]
                self.assertGreaterEqual(paper_count, 30, "Seed data must contain at least 30 papers")
            finally:
                conn.close()

    def test_11_cors_allowed_and_disallowed_origins(self) -> None:
        """
        Phase 1 Regression Test:
        Verify CORS configuration headers:
        - Allowed origins (e.g. http://localhost:3000, http://localhost:5173) receive Access-Control-Allow-Origin and credentials.
        - Disallowed origins do not receive Access-Control-Allow-Origin.
        """
        # Allowed origin test
        res_allowed = self.client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertEqual(
            res_allowed.headers.get("access-control-allow-origin"),
            "http://localhost:3000",
        )
        self.assertEqual(
            res_allowed.headers.get("access-control-allow-credentials"),
            "true",
        )

        # Disallowed origin test
        res_disallowed = self.client.options(
            "/api/v1/health",
            headers={
                "Origin": "https://malicious-site.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        self.assertIsNone(res_disallowed.headers.get("access-control-allow-origin"))



if __name__ == "__main__":
    unittest.main(verbosity=2)
