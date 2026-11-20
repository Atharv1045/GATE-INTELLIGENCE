import os
import shutil
import sys
from pathlib import Path

# Add backend and tests directories to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_DB = REPO_ROOT / "storage" / "gate_intelligence.db"
SCRATCH_DIR = Path(r"C:\Users\athar\.gemini\antigravity-cli\brain\305dbfd9-af4b-4b0e-9894-5e575eeb200b\scratch")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = SCRATCH_DIR / "test_cbt_scoring.db"
shutil.copy2(ORIGINAL_DB, TEST_DB)
os.environ["SQLITE_DB_PATH"] = str(TEST_DB)

from tests.direct_client import DirectTestClient

client = DirectTestClient()

def test_cbt_scoring_edge_cases():
    print("=== CBT SCORING EDGE CASES TEST ===")

    # 1. Start a full CS 2012 mock test (has 65 questions, 100 marks, all 100% verified official keys)
    res = client.post("/api/v1/tests/start", json={"paper_code": "CS", "test_mode": "full", "duration_minutes": 180})
    assert res.status_code == 200, f"Failed to start test: {res.text}"
    data = res.json()
    test_id = data["test_id"]
    questions = data["questions"]
    assert len(questions) == 65, f"Expected 65 questions, got {len(questions)}"
    assert data["total_marks"] == 100.0, f"Expected 100.0 marks, got {data['total_marks']}"

    # Get details of Question 1 (1 mark MCQ), Question 26 (2 mark MCQ)
    q1 = next(q for q in questions if q["question_number"] == 1)
    q26 = next(q for q in questions if q["question_number"] == 26)

    assert q1["marks"] == 1.0, f"Expected Q1 marks=1.0, got {q1['marks']}"
    assert q26["marks"] == 2.0, f"Expected Q26 marks=2.0, got {q26['marks']}"

    # Verification of official negative marking:
    # - Q1: Correct 1-mark MCQ (official is B, select B) -> +1.0
    # - Q26: Wrong 2-mark MCQ (official is C, select A) -> -2/3 = -0.6667
    # - Remaining: 63 unattempted -> 0.0 marks
    responses = [
        {"question_id": q1["question_id"], "selected_options": ["B"], "time_spent_seconds": 45},
        {"question_id": q26["question_id"], "selected_options": ["A"], "time_spent_seconds": 90},
    ]

    sub_res = client.post(f"/api/v1/tests/{test_id}/submit", json={"responses": responses})
    assert sub_res.status_code == 200, f"Submission failed: {sub_res.text}"
    result = sub_res.json()

    print(f"Result Total Marks: {result['total_marks']}")
    print(f"Marks Obtained: {result['marks_obtained']}")
    print(f"Correct Count: {result['correct_count']}, Incorrect Count: {result['incorrect_count']}, Unattempted: {result['unattempted_count']}")

    assert result["correct_count"] == 1, "Expected 1 correct"
    assert result["incorrect_count"] == 1, "Expected 1 incorrect"
    assert result["unattempted_count"] == 63, f"Expected 63 unattempted, got {result['unattempted_count']}"
    assert abs(result["marks_obtained"] - 0.33) < 0.05, f"Marks obtained mismatch: {result['marks_obtained']}"

    # Verify review breakdown
    reviews = result["question_reviews"]
    rev_q1 = next(r for r in reviews if r["question_id"] == q1["question_id"])
    assert rev_q1["is_correct"] is True
    assert rev_q1["marks_awarded"] == 1.0

    rev_q26 = next(r for r in reviews if r["question_id"] == q26["question_id"])
    assert rev_q26["is_correct"] is False
    assert abs(rev_q26["marks_awarded"] - (-0.6667)) < 0.01

    # Verify unattempted question
    q3 = next(q for q in questions if q["question_number"] == 3)
    rev_q3 = next(r for r in reviews if r["question_id"] == q3["question_id"])
    assert rev_q3["user_selected_options"] == []
    assert rev_q3["marks_awarded"] == 0.0

    # 2. Test results retrieval endpoint with both test_result_id and mock_test_id
    res_get = client.get(f"/api/v1/tests/results/{test_id}")
    assert res_get.status_code == 200
    assert res_get.json()["mock_test_id"] == test_id

    res_get2 = client.get(f"/api/v1/tests/results/{result['test_result_id']}")
    assert res_get2.status_code == 200
    assert res_get2.json()["test_result_id"] == result["test_result_id"]

    # 3. Test history endpoint
    res_hist = client.get("/api/v1/tests/history?paper_code=CS")
    assert res_hist.status_code == 200
    hist = res_hist.json().get("history", [])
    assert len(hist) > 0
    assert any(h["mock_test_id"] == test_id for h in hist)

    # 4. Test 2013 paper (unverified keys) handling in CBT
    # Should not penalize or reward candidate for unverified keys
    res_2013 = client.get("/api/v1/papers?paper_code=CS")
    assert res_2013.status_code == 200
    p2013 = next(p for p in res_2013.json()["papers"] if p["examination_year"] == 2013)
    
    t_2013 = client.post("/api/v1/tests/start", json={"paper_code": "CS", "test_mode": "paper_based", "paper_id": p2013["id"], "duration_minutes": 180})
    assert t_2013.status_code == 200
    d_2013 = t_2013.json()
    q_2013 = d_2013["questions"][0]

    sub_2013 = client.post(f"/api/v1/tests/{d_2013['test_id']}/submit", json={
        "responses": [{"question_id": q_2013["question_id"], "selected_options": ["A"], "time_spent_seconds": 30}]
    })
    assert sub_2013.status_code == 200
    r_2013 = sub_2013.json()
    # Should have attempted=1, correct=0, incorrect=0, unattempted=64, marks_obtained=0.0
    assert r_2013["attempted_count"] == 1
    assert r_2013["correct_count"] == 0
    assert r_2013["incorrect_count"] == 0
    assert r_2013["marks_obtained"] == 0.0

    print(">>> ALL CBT SCORING EDGE CASES PASSED SUCCESSFULLY <<<")

if __name__ == "__main__":
    test_cbt_scoring_edge_cases()
