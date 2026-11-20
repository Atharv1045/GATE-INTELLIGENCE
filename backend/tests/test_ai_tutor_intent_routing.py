"""
Automated Unit and Integration Regression Test Suite for AI Tutor Intent Routing,
Relevance Guard, Conceptual Knowledge Base, and Exact Question Lookup (Phase 1).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

TEST_TMP_DIR = tempfile.mkdtemp(prefix="gate_tutor_test_")
os.environ["SQLITE_DB_PATH"] = os.path.join(TEST_TMP_DIR, "test_tutor.db")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi.testclient import TestClient

from app.core.config import settings
from app.database.session import get_db_connection, init_database, utcnow_iso
from app.main import app
from app.rag.tutor_engine import (
    RagTutorEngine,
    classify_tutor_intent,
    is_retrieval_relevant,
)


class AiTutorIntentRoutingTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        init_database()
        cls.client = TestClient(app)
        conn = get_db_connection()
        now = utcnow_iso()
        try:
            # Seed test gate_paper and question_paper
            gp = conn.execute("SELECT id FROM gate_papers WHERE code = 'CS'").fetchone()
            gp_id = gp[0] if gp else "gp_cs"
            conn.execute(
                """
                INSERT OR IGNORE INTO question_papers (
                    id, paper_id, paper_code, examination_year, session_set, title,
                    filename, file_path, file_checksum, processing_status, total_extracted_questions,
                    created_at, updated_at
                ) VALUES (
                    'qp_tutor_test', ?, 'CS', 2012, 'Set-1', 'GATE CS 2012 Test',
                    'test.pdf', '/tmp/test.pdf', 'chk_tutor_test', 'completed', 3,
                    ?, ?
                )
                """,
                (gp_id, now, now),
            )
            # Seed Q.32 (Dijkstra algorithm) with official answer key
            conn.execute(
                """
                INSERT OR IGNORE INTO questions (
                    id, question_paper_id, paper_code, examination_year, question_number,
                    source_question_label, question_type, question_text, marks, negative_marks,
                    page_number, source_page_start, source_page_end, subject_name, primary_topic_name,
                    created_at, updated_at
                ) VALUES (
                    'q_dijkstra_32', 'qp_tutor_test', 'CS', 2012, 32,
                    'Q.32', 'MCQ',
                    'Consider a directed graph with positive edge weights. What is the time complexity of Dijkstra algorithm using a binary min-heap?',
                    2.0, 0.67, 8, 8, 8, 'Algorithms', 'Graph Algorithms',
                    ?, ?
                )
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO question_options (id, question_id, option_label, option_text, is_correct, created_at, updated_at)
                VALUES
                ('opt_32_A', 'q_dijkstra_32', 'A', 'O((V + E) log V)', 1, ?, ?),
                ('opt_32_B', 'q_dijkstra_32', 'B', 'O(V^3)', 0, ?, ?),
                ('opt_32_C', 'q_dijkstra_32', 'C', 'O(E^2)', 0, ?, ?),
                ('opt_32_D', 'q_dijkstra_32', 'D', 'O(V + E)', 0, ?, ?)
                """,
                (now, now, now, now, now, now, now, now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO answer_keys (
                    id, question_id, answer_type, correct_options_json, provenance, explanation, created_at, updated_at
                ) VALUES (
                    'ak_32', 'q_dijkstra_32', 'MCQ', '["A"]', 'official_key',
                    'Dijkstra algorithm using a binary min-heap runs in O((V + E) log V) time.',
                    ?, ?
                )
                """,
                (now, now),
            )

            # Seed Q.52 (Compiler Design FIRST and FOLLOW sets)
            conn.execute(
                """
                INSERT OR IGNORE INTO questions (
                    id, question_paper_id, paper_code, examination_year, question_number,
                    source_question_label, question_type, question_text, marks, negative_marks,
                    page_number, source_page_start, source_page_end, subject_name, primary_topic_name,
                    created_at, updated_at
                ) VALUES (
                    'q_compiler_52', 'qp_tutor_test', 'CS', 2012, 52,
                    'Q.52', 'MCQ',
                    'The FIRST and FOLLOW sets for the non-terminals A and B in the given grammar are',
                    2.0, 0.67, 15, 15, 15, 'Compiler Design', 'Lexical Analysis and Parsing',
                    ?, ?
                )
                """,
                (now, now),
            )
            conn.commit()
        finally:
            conn.close()

    def test_01_explain_deadlock_conceptual_route_no_retrieval(self) -> None:
        """Test 1: 'Explain deadlock...' routes to conceptual, never calls retrieve_context, returns structured explanation."""
        engine = RagTutorEngine()
        conn = get_db_connection()
        try:
            with patch.object(engine, "retrieve_context", wraps=engine.retrieve_context) as mock_ret:
                res = engine.answer_student_query(conn, "Explain deadlock in operating systems with a simple example.", paper_code="CS")
                mock_ret.assert_not_called()
                self.assertEqual(res["answer_provenance"], "conceptual_explanation")
                self.assertIn("Deadlock", res["answer_markdown"])
                self.assertIn("Coffman", res["answer_markdown"])
                self.assertEqual(res["citations"], [])
                self.assertEqual(res["related_questions"], [])
        finally:
            conn.close()

    def test_02_explain_semaphores_conceptual_route_no_retrieval(self) -> None:
        """Test 2: 'What is a semaphore? Explain binary and counting semaphores...' routes to conceptual without PYQs."""
        engine = RagTutorEngine()
        conn = get_db_connection()
        try:
            with patch.object(engine, "retrieve_context", wraps=engine.retrieve_context) as mock_ret:
                res = engine.answer_student_query(
                    conn,
                    "What is a semaphore? Explain binary and counting semaphores with a simple example.",
                    paper_code="CS",
                )
                mock_ret.assert_not_called()
                self.assertEqual(res["answer_provenance"], "conceptual_explanation")
                self.assertIn("Binary Semaphore", res["answer_markdown"])
                self.assertIn("Counting Semaphore", res["answer_markdown"])
                self.assertNotIn("FIRST and FOLLOW", res["answer_markdown"])
                self.assertEqual(res["citations"], [])
        finally:
            conn.close()

    def test_03_explicit_negative_retrieval_constraint_bypasses_retrieval(self) -> None:
        """Test 3: 'Do not search the question bank. Explain paging conceptually.' explicitly overrides retrieval."""
        parsed = classify_tutor_intent("Do not search the question bank. Explain paging conceptually.")
        self.assertEqual(parsed["intent"], "conceptual")
        self.assertTrue(parsed["negative_retrieval"])

        engine = RagTutorEngine()
        conn = get_db_connection()
        try:
            with patch.object(engine, "retrieve_context", wraps=engine.retrieve_context) as mock_ret:
                res = engine.answer_student_query(
                    conn,
                    "Do not search the question bank. Explain paging conceptually.",
                    paper_code="CS",
                )
                mock_ret.assert_not_called()
                self.assertEqual(res["answer_provenance"], "conceptual_explanation")
                self.assertIn("Paging", res["answer_markdown"])
                self.assertIn("Page Table", res["answer_markdown"])
                self.assertEqual(res["citations"], [])
        finally:
            conn.close()

    def test_04_pyq_search_for_semaphores_returns_no_unrelated_questions(self) -> None:
        """Test 4: 'Find GATE previous-year questions about semaphores' returns honest 'no questions found' rather than Compiler Q.52."""
        engine = RagTutorEngine()
        conn = get_db_connection()
        try:
            res = engine.answer_student_query(
                conn,
                "Find GATE previous-year questions about semaphores.",
                paper_code="CS",
            )
            self.assertIn("No matching previous-year questions found", res["answer_markdown"])
            self.assertNotIn("FIRST and FOLLOW", res["answer_markdown"])
            self.assertEqual(res["citations"], [])
            self.assertEqual(res["related_questions"], [])
            self.assertEqual(res["provenance_badge"], "No Uploaded PYQs Found")
        finally:
            conn.close()

    def test_05_solve_cs_2012_q32_exact_question_lookup(self) -> None:
        """Test 5: 'Solve GATE CS 2012 Question 32' performs exact lookup and solves Q.32 with official key."""
        engine = RagTutorEngine()
        conn = get_db_connection()
        try:
            res = engine.answer_student_query(
                conn,
                "Solve GATE CS 2012 Question 32.",
                paper_code="CS",
            )
            self.assertEqual(res["answer_provenance"], "official_key")
            self.assertIn("GATE CS 2012, Q.32", res["answer_markdown"])
            self.assertIn("O((V + E) log V)", res["answer_markdown"])
            self.assertEqual(len(res["citations"]), 1)
            self.assertIn("Q.32", res["citations"][0])
            self.assertEqual(res["related_questions"][0]["question_number"], 32)
        finally:
            conn.close()

    def test_06_dijkstra_hybrid_request_explanation_first_pyqs_second(self) -> None:
        """Test 6: 'Explain Dijkstra algorithm and then find related GATE PYQs' delivers concept first, then matching PYQ."""
        engine = RagTutorEngine()
        conn = get_db_connection()
        try:
            res = engine.answer_student_query(
                conn,
                "Explain Dijkstra's algorithm and then find related GATE PYQs.",
                paper_code="CS",
            )
            self.assertEqual(res["answer_provenance"], "conceptual_explanation")
            self.assertIn("Dijkstra's Shortest Path Algorithm", res["answer_markdown"])
            self.assertIn("Related GATE Previous-Year Questions", res["answer_markdown"])
            self.assertIn("Q.32", res["answer_markdown"])
            self.assertTrue(len(res["citations"]) >= 1)
        finally:
            conn.close()

    def test_07_low_relevance_candidates_rejected_by_guard(self) -> None:
        """Test 7: Verify is_retrieval_relevant rejects arbitrary low scores and noise."""
        # Pure noise score (Compiler Design matching Semaphore)
        self.assertFalse(is_retrieval_relevant(combined_score=0.1478, tfidf_sim=0.0, emb_sim=0.26))
        # Zero lexical overlap and low embedding similarity
        self.assertFalse(is_retrieval_relevant(combined_score=0.22, tfidf_sim=0.0, emb_sim=0.40))
        # True lexical overlap on concept keywords
        self.assertTrue(is_retrieval_relevant(combined_score=0.35, tfidf_sim=0.18, emb_sim=0.45))
        # High vector similarity
        self.assertTrue(is_retrieval_relevant(combined_score=0.40, tfidf_sim=0.0, emb_sim=0.55))

    def test_08_no_api_key_fallback_does_not_hijack_query(self) -> None:
        """Test 8: In local mode without GEMINI_API_KEY, a conceptual query returns the concept rather than hijacking to retrieved[0]."""
        orig_key = settings.GEMINI_API_KEY
        try:
            settings.GEMINI_API_KEY = ""
            engine = RagTutorEngine()
            conn = get_db_connection()
            try:
                res = engine.answer_student_query(
                    conn,
                    "What is a binary semaphore and counting semaphore?",
                    paper_code="CS",
                )
                self.assertNotIn("Retrieved Previous-Year Question Statement", res["answer_markdown"])
                self.assertNotIn("Option Breakdown", res["answer_markdown"])
                self.assertIn("Binary Semaphore", res["answer_markdown"])
                self.assertIn("Counting Semaphore", res["answer_markdown"])
                self.assertEqual(res["model_used"], "offline-concept-knowledge-base")
            finally:
                conn.close()
        finally:
            settings.GEMINI_API_KEY = orig_key

    def test_09_conceptual_provenance_not_inherited_from_retrieved_records(self) -> None:
        """Test 9: Conceptual synthesis uses 'conceptual_explanation', never inheriting 'official_key' from DB questions."""
        engine = RagTutorEngine()
        conn = get_db_connection()
        try:
            res = engine.answer_student_query(
                conn,
                "Explain the concept of deadlock prevention.",
                paper_code="CS",
            )
            self.assertEqual(res["answer_provenance"], "conceptual_explanation")
            self.assertNotEqual(res["answer_provenance"], "official_key")
            self.assertEqual(res["citations"], [])
        finally:
            conn.close()

    def test_10_missing_exact_question_honest_response_no_substitution(self) -> None:
        """Test 10: Asking for a non-existent question returns honest 404/not-found text without silent substitution."""
        engine = RagTutorEngine()
        conn = get_db_connection()
        try:
            res = engine.answer_student_query(
                conn,
                "Solve GATE CS 2012 Question 99.",
                paper_code="CS",
            )
            self.assertIn("Question 99 Not Found", res["answer_markdown"])
            self.assertEqual(res["provenance_badge"], "Question Not Found")
            self.assertEqual(res["citations"], [])
            self.assertEqual(res["related_questions"], [])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
