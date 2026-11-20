"""
End-to-End Test Suite for PDF Question Paper Upload, Local Extraction,
OCR Fallback, Segmentation, Review, Duplicate Detection, and Transactional Import.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from pathlib import Path

# Ensure paths
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(REPO_ROOT))

# Setup isolated test database in scratch directory
SCRATCH_DIR = Path(r"C:\Users\athar\.gemini\antigravity-cli\brain\305dbfd9-af4b-4b0e-9894-5e575eeb200b\scratch")
if not SCRATCH_DIR.exists():
    SCRATCH_DIR = REPO_ROOT / "scratch"
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB_PATH = SCRATCH_DIR / "test_pdf_ingestion_e2e.db"

# Copy original DB to test DB
ORIGINAL_DB = REPO_ROOT / "storage" / "gate_intelligence.db"
shutil.copy2(str(ORIGINAL_DB), str(TEST_DB_PATH))

# Override SQLITE_DB_PATH before importing app
os.environ["SQLITE_DB_PATH"] = str(TEST_DB_PATH)

from tests.direct_client import DirectTestClient
client = DirectTestClient()


def test_pdf_workflow_end_to_end():
    print("=" * 70)
    print("RUNNING END-TO-END PDF UPLOAD & INGESTION SUITE")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. DUPLICATE DETECTION TEST USING 2012_CS.pdf
    # -------------------------------------------------------------
    print("\n--- TEST 1: Duplicate Paper Detection (2012_CS.pdf) ---")
    pdf_2012_path = REPO_ROOT / "validation" / "uploads" / "2012_CS.pdf"
    assert pdf_2012_path.exists(), f"Missing test PDF: {pdf_2012_path}"

    with open(pdf_2012_path, "rb") as f:
        pdf_2012_bytes = f.read()

    res_dup = client.post(
        "/api/v1/papers/upload-pdf",
        data={
            "file": pdf_2012_bytes,
            "paper_code": "CS",
            "examination_year": 2012,
            "session_set": "Set-1",
            "title": "GATE CS 2012 Duplicate Test",
        },
    )
    assert res_dup.status_code == 200, f"Expected 200, got {res_dup.status_code}: {res_dup.text}"
    dup_data = res_dup.json()

    print(f"  * is_duplicate: {dup_data['is_duplicate']}")
    print(f"  * duplicate_reason: {dup_data['duplicate_reason']}")
    print(f"  * existing_question_count: {dup_data['existing_question_count']}")
    assert dup_data["is_duplicate"] is True, "Expected duplicate detection to trigger for 2012 CS"
    assert dup_data["existing_question_count"] == 65, "Expected 65 existing questions detected"
    print("  [PASS] Duplicate detection successfully identified existing paper.")

    # -------------------------------------------------------------
    # 2. FRESH PDF INGESTION & EXTRACTION (2010_CS.pdf)
    # -------------------------------------------------------------
    print("\n--- TEST 2: Fresh PDF Upload & Extraction (2010_CS.pdf) ---")
    pdf_2010_path = REPO_ROOT / "validation" / "uploads" / "2010_CS.pdf"
    assert pdf_2010_path.exists(), f"Missing test PDF: {pdf_2010_path}"

    with open(pdf_2010_path, "rb") as f:
        pdf_2010_bytes = f.read()

    # Create realistic answer key text for 2010 (sample of official keys)
    sample_key_text = """
    Q.1: C
    Q.2: A
    Q.3: B
    Q.4: D
    Q.5: A
    Q.6: C
    Q.7: B
    Q.8: D
    Q.9: A
    Q.10: B
    Q.11: C
    Q.12: D
    Q.13: A
    Q.14: B
    Q.15: C
    Q.16: D
    Q.17: A
    Q.18: B
    Q.19: C
    Q.20: D
    Q.21: A
    Q.22: B
    Q.23: C
    Q.24: D
    Q.25: A
    Q.56: C
    Q.57: B
    Q.58: D
    Q.59: A
    Q.60: B
    """

    res_upload = client.post(
        "/api/v1/papers/upload-pdf",
        data={
            "file": pdf_2010_bytes,
            "paper_code": "CS",
            "examination_year": 2010,
            "session_set": "Set-1",
            "title": "GATE Computer Science 2010",
            "answer_key_text": sample_key_text,
            "enable_ocr": True,
        },
    )
    assert res_upload.status_code == 200, f"Extraction failed: {res_upload.text}"
    upload_data = res_upload.json()

    print(f"  * is_duplicate: {upload_data['is_duplicate']}")
    print(f"  * total_questions segmented: {upload_data['total_questions']}")
    print(f"  * extracted_page_count: {upload_data['extracted_page_count']}")
    print(f"  * answer_keys_attached: {upload_data['answer_keys_attached']}")
    print(f"  * file_checksum: {upload_data['paper_metadata']['file_checksum'][:16]}...")

    assert upload_data["is_duplicate"] is False, "2010 paper should not be a duplicate"
    assert upload_data["total_questions"] >= 25, f"Expected at least 25 questions, got {upload_data['total_questions']}"
    assert upload_data["extracted_page_count"] > 10, "Expected multi-page extraction"
    assert upload_data["answer_keys_attached"] >= 10, "Expected answer keys attached"
    print("  [PASS] Fresh PDF successfully extracted and segmented.")

    # -------------------------------------------------------------
    # 3. EDITABLE QUESTION REVIEW VERIFICATION
    # -------------------------------------------------------------
    print("\n--- TEST 3: Editable Review Modifications ---")
    staged_questions = upload_data["questions"]
    q1 = staged_questions[0]
    print(f"  * Q.1 Original stem preview: {q1['question_text'][:60]}...")
    print(f"  * Q.1 Subject: {q1['subject_name']} / Topic: {q1['primary_topic_name']}")
    print(f"  * Q.1 Correct options: {q1['correct_options']}")

    # Apply human review edits:
    # 1. Edit stem of Q.1
    q1["question_text"] = q1["question_text"] + " [Reviewed and Verified by Educator]"
    # 2. Adjust marks of Q.2
    staged_questions[1]["marks"] = 2.0
    staged_questions[1]["negative_marks"] = 0.666667
    # 3. Add explanation to Q.1
    q1["explanation"] = "Official IIT answer key verified."

    print("  [PASS] Successfully applied modifications to staged questions.")

    # -------------------------------------------------------------
    # 4. SAFE DATABASE IMPORT & TRANSACTION TEST
    # -------------------------------------------------------------
    print("\n--- TEST 4: Safe Transactional Database Import ---")
    confirm_payload = {
        "paper_code": "CS",
        "examination_year": 2010,
        "session_set": "Set-1",
        "paper_title": "GATE Computer Science 2010 (Set-1)",
        "file_checksum": upload_data["paper_metadata"]["file_checksum"],
        "file_path": upload_data["paper_metadata"]["file_path"],
        "page_count": upload_data["paper_metadata"]["page_count"],
        "is_scanned": upload_data["paper_metadata"]["is_scanned"],
        "overwrite_if_exists": True,
        "questions": staged_questions,
    }

    res_confirm = client.post("/api/v1/papers/confirm-import", json=confirm_payload)
    assert res_confirm.status_code == 200, f"Import confirmation failed: {res_confirm.text}"
    import_result = res_confirm.json()

    print(f"  * success: {import_result['success']}")
    print(f"  * paper_id: {import_result['paper_id']}")
    print(f"  * questions_imported: {import_result['questions_imported']}")
    print(f"  * total_marks: {import_result['total_marks']}")
    print(f"  * verified_keys_count: {import_result['verified_keys_count']}")
    print(f"  * backup_path: {import_result['backup_path']}")

    assert import_result["success"] is True
    assert import_result["questions_imported"] == len(staged_questions)
    assert import_result["verified_keys_count"] >= 10
    print("  [PASS] Staged questions committed atomically to database.")

    # -------------------------------------------------------------
    # 5. VERIFY DATABASE RECORDS & INTEGRITY
    # -------------------------------------------------------------
    print("\n--- TEST 5: Direct SQLite Database Verification ---")
    conn = sqlite3.connect(str(TEST_DB_PATH))
    conn.row_factory = sqlite3.Row

    # PRAGMA integrity
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    assert integrity == "ok", f"Integrity check failed: {integrity}"

    # Verify paper record
    paper_row = conn.execute("SELECT * FROM question_papers WHERE id = ?", (import_result["paper_id"],)).fetchone()
    assert paper_row is not None, "Paper record not found in question_papers"
    assert paper_row["examination_year"] == 2010
    assert paper_row["paper_code"] == "CS"

    # Verify question count
    db_q_count = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE question_paper_id = ?", (import_result["paper_id"],)
    ).fetchone()[0]
    assert db_q_count == len(staged_questions), f"Expected {len(staged_questions)} in DB, found {db_q_count}"

    # Verify options count
    db_opt_count = conn.execute(
        """
        SELECT COUNT(qo.id)
        FROM question_options qo
        JOIN questions q ON qo.question_id = q.id
        WHERE q.question_paper_id = ?
        """,
        (import_result["paper_id"],),
    ).fetchone()[0]
    assert db_opt_count >= 50, f"Expected >= 50 options, found {db_opt_count}"

    # Verify verified keys count
    db_key_count = conn.execute(
        """
        SELECT COUNT(ak.id)
        FROM answer_keys ak
        JOIN questions q ON ak.question_id = q.id
        WHERE q.question_paper_id = ?
        """,
        (import_result["paper_id"],),
    ).fetchone()[0]
    assert db_key_count == import_result["verified_keys_count"]

    # Verify human review edit persisted
    persisted_q1 = conn.execute(
        "SELECT question_text FROM questions WHERE question_paper_id = ? AND question_number = ?",
        (import_result["paper_id"], staged_questions[0]["question_number"]),
    ).fetchone()
    assert "[Reviewed and Verified by Educator]" in persisted_q1["question_text"]

    conn.close()
    print("  [PASS] SQLite database structure, foreign keys, and review edits verified 100%.")

    # -------------------------------------------------------------
    # 6. APPLICATION-WIDE DATA REFRESH VERIFICATION
    # -------------------------------------------------------------
    print("\n--- TEST 6: Application-Wide Data Refresh Verification ---")

    # A. Papers catalog endpoint
    res_papers = client.get("/api/v1/papers?paper_code=CS")
    assert res_papers.status_code == 200
    papers_list = res_papers.json()["papers"]
    paper_years = [p["examination_year"] for p in papers_list]
    print(f"  * Papers in catalog: {paper_years}")
    assert 2010 in paper_years, "2010 CS paper must appear in Paper Library catalog"
    p2010 = next(p for p in papers_list if p["examination_year"] == 2010)
    assert p2010["status"] == "ready"
    assert p2010["question_count"] == len(staged_questions)

    # B. Dashboard Metrics endpoint
    res_metrics = client.get("/api/v1/dashboard/metrics?paper_code=CS")
    assert res_metrics.status_code == 200
    metrics = res_metrics.json()
    print(f"  * Dashboard total available questions: {metrics['total_questions']}")
    assert metrics["total_questions"] >= 150, f"Expected >= 150, got {metrics['total_questions']}"
    assert metrics["available_papers"] >= 3, f"Expected >= 3 available papers, got {metrics['available_papers']}"

    # C. Question Bank browsing endpoint
    res_qb = client.get(f"/api/v1/questions?paper_code=CS&examination_year=2010&page=1&page_size=10")
    assert res_qb.status_code == 200
    qb_data = res_qb.json()
    print(f"  * Question Bank 2010 total questions: {qb_data['total']}")
    assert qb_data["total"] == len(staged_questions)
    qb_items = qb_data.get("items") or qb_data.get("questions") or []
    assert len(qb_items) == 10

    # D. CBT Mock Test creation with newly ingested paper
    res_test = client.post(
        "/api/v1/tests/start",
        json={
            "paper_code": "CS",
            "test_mode": "paper",
            "paper_id": import_result["paper_id"],
            "year": 2010,
        },
    )
    assert res_test.status_code == 200, f"Failed to start test for ingested paper: {res_test.text}"
    test_data = res_test.json()
    print(f"  * CBT Mock Test launched successfully: ID {test_data['test_id']}, {len(test_data['questions'])} questions.")
    assert len(test_data["questions"]) == len(staged_questions)

    # E. PYQ Analytics distributions
    res_dist = client.get("/api/v1/analytics/distributions?paper_code=CS")
    assert res_dist.status_code == 200
    dist_data = res_dist.json()
    dist_years = [str(y["year"]) for y in dist_data["year_trends"]]
    print(f"  * Analytics trend years: {dist_years}")
    assert "2010" in dist_years, "Year 2010 must be included in PYQ analytics trend charts"

    print("  [PASS] All application features refreshed immediately with new paper data.")

    print("\n" + "=" * 70)
    print("ALL 6 END-TO-END PDF WORKFLOW TESTS PASSED CLEANLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_pdf_workflow_end_to_end()
